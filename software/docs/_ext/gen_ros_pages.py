"""Introspect a ROS 2 colcon workspace and emit Markdown reference pages.

This module is the heart of the documentation pipeline. It reads the *actual*
source of every package under ``src/`` (``package.xml``, ``setup.py`` /
``CMakeLists.txt``, launch files, YAML parameter files and ``.msg`` interface
definitions) and renders a set of MyST-Markdown pages into ``docs/_generated/reference/``.

It is wired into ``conf.py`` via the Sphinx ``builder-inited`` event and runs
when you build the docs (``./docs/build.sh``). Nothing runs in the background.

The parsing is deliberately static (``xml.etree`` + ``ast``): nothing in the
workspace is imported, so docs build without a sourced ROS environment.
"""

from __future__ import annotations

import ast
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - yaml is a declared dependency
    yaml = None


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #
@dataclass
class LaunchArg:
    name: str
    default: str | None = None
    description: str | None = None


@dataclass
class LaunchFile:
    path: Path
    docstring: str | None = None
    args: list[LaunchArg] = field(default_factory=list)


@dataclass
class ConfigFile:
    path: Path
    text: str = ""
    params: dict = field(default_factory=dict)


@dataclass
class MessageFile:
    path: Path
    text: str = ""


@dataclass
class Package:
    name: str
    path: Path
    description: str = ""
    maintainers: list[str] = field(default_factory=list)
    license: str = ""
    version: str = ""
    build_type: str = "unknown"
    depends: dict[str, list[str]] = field(default_factory=dict)
    entry_points: list[tuple[str, str]] = field(default_factory=list)
    launch_files: list[LaunchFile] = field(default_factory=list)
    config_files: list[ConfigFile] = field(default_factory=list)
    messages: list[MessageFile] = field(default_factory=list)
    has_python_api: bool = False

    @property
    def is_python(self) -> bool:
        return self.build_type == "ament_python"


# --------------------------------------------------------------------------- #
# Parsing helpers
# --------------------------------------------------------------------------- #
def _literal_or_none(node: ast.AST):
    """Return the literal value of an AST node, or ``None`` if not constant."""
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError):
        return None


def _parse_package_xml(pkg_xml: Path) -> dict:
    root = ET.parse(pkg_xml).getroot()

    def _text(tag: str) -> str:
        el = root.find(tag)
        return (el.text or "").strip() if el is not None else ""

    depend_tags = {
        "build_depend": "Build",
        "buildtool_depend": "Build tool",
        "build_export_depend": "Build (exported)",
        "exec_depend": "Runtime",
        "depend": "Build + runtime",
        "test_depend": "Test",
    }
    depends: dict[str, list[str]] = {}
    for tag, label in depend_tags.items():
        vals = [e.text.strip() for e in root.findall(tag) if e.text]
        if vals:
            depends[label] = sorted(set(vals))

    export = root.find("export")
    build_type = "unknown"
    if export is not None:
        bt = export.find("build_type")
        if bt is not None and bt.text:
            build_type = bt.text.strip()

    maintainers = [e.text.strip() for e in root.findall("maintainer") if e.text]

    return {
        "name": _text("name"),
        "version": _text("version"),
        "description": _text("description"),
        "license": _text("license"),
        "maintainers": maintainers,
        "build_type": build_type,
        "depends": depends,
    }


def _parse_entry_points(setup_py: Path) -> list[tuple[str, str]]:
    """Extract ``console_scripts`` entries from a ``setup.py`` via AST."""
    try:
        tree = ast.parse(setup_py.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return []

    scripts: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
        if name != "setup":
            continue
        for kw in node.keywords:
            if kw.arg != "entry_points":
                continue
            ep = _literal_or_none(kw.value)
            if isinstance(ep, dict):
                for entry in ep.get("console_scripts", []):
                    if "=" in entry:
                        cmd, target = entry.split("=", 1)
                        scripts.append((cmd.strip(), target.strip()))
    return sorted(scripts)


def _parse_launch_file(path: Path) -> LaunchFile:
    lf = LaunchFile(path=path)
    try:
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src)
    except (OSError, SyntaxError):
        return lf

    lf.docstring = ast.get_docstring(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        fname = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
        if fname != "DeclareLaunchArgument":
            continue
        name = default = desc = None
        if node.args:
            name = _literal_or_none(node.args[0])
        for kw in node.keywords:
            if kw.arg == "name":
                name = _literal_or_none(kw.value)
            elif kw.arg == "default_value":
                default = _literal_or_none(kw.value)
            elif kw.arg == "description":
                desc = _literal_or_none(kw.value)
        if name:
            lf.args.append(LaunchArg(name=str(name), default=default, description=desc))
    return lf


def _parse_config_file(path: Path) -> ConfigFile:
    cf = ConfigFile(path=path)
    try:
        cf.text = path.read_text(encoding="utf-8")
    except OSError:
        return cf
    if yaml is not None:
        try:
            cf.params = yaml.safe_load(cf.text) or {}
        except yaml.YAMLError:
            cf.params = {}
    return cf


def discover_packages(src_dir: Path) -> list[Package]:
    packages: list[Package] = []
    for pkg_xml in sorted(src_dir.glob("*/package.xml")):
        pkg_dir = pkg_xml.parent
        meta = _parse_package_xml(pkg_xml)
        pkg = Package(
            name=meta["name"] or pkg_dir.name,
            path=pkg_dir,
            description=meta["description"],
            maintainers=meta["maintainers"],
            license=meta["license"],
            version=meta["version"],
            build_type=meta["build_type"],
            depends=meta["depends"],
        )

        setup_py = pkg_dir / "setup.py"
        if setup_py.exists():
            pkg.entry_points = _parse_entry_points(setup_py)

        for launch in sorted(pkg_dir.glob("launch/*.launch.py")):
            pkg.launch_files.append(_parse_launch_file(launch))

        for cfg in sorted(pkg_dir.glob("config/*.yaml")):
            pkg.config_files.append(_parse_config_file(cfg))

        for msg in sorted(pkg_dir.glob("msg/*.msg")):
            try:
                text = msg.read_text(encoding="utf-8")
            except OSError:
                text = ""
            pkg.messages.append(MessageFile(path=msg, text=text))

        inner = pkg_dir / pkg.name
        pkg.has_python_api = (inner / "__init__.py").exists()

        packages.append(pkg)
    return packages


# --------------------------------------------------------------------------- #
# Rendering helpers
# --------------------------------------------------------------------------- #
def _md_escape(text: str) -> str:
    return text.replace("|", "\\|")


def _build_type_badge(pkg: Package) -> str:
    color = {"ament_python": "info", "ament_cmake": "warning"}.get(pkg.build_type, "muted")
    return f"{{bdg-{color}}}`{pkg.build_type}`"


def _render_package_page(pkg: Package, src_dir: Path) -> str:
    lines: list[str] = []
    lines.append(f"# `{pkg.name}`")
    lines.append("")

    desc = pkg.description or "_No description provided in `package.xml`._"
    if desc.lower().startswith("todo"):
        desc = f"```{{warning}}\n`package.xml` description is still a placeholder: *{desc}*\n```"
    lines.append(desc)
    lines.append("")

    # Metadata field list.
    lines.append(f"- **Build type:** {_build_type_badge(pkg)}")
    lines.append(f"- **Version:** `{pkg.version or 'n/a'}`")
    lines.append(f"- **License:** {pkg.license or 'n/a'}")
    if pkg.maintainers:
        lines.append(f"- **Maintainer(s):** {', '.join(pkg.maintainers)}")
    lines.append(f"- **Source:** `src/{pkg.name}/`")
    lines.append("")

    # Executables / entry points.
    if pkg.entry_points:
        lines.append("## Executables")
        lines.append("")
        lines.append("| Command (`ros2 run`) | Target |")
        lines.append("| --- | --- |")
        for cmd, target in pkg.entry_points:
            lines.append(f"| `ros2 run {pkg.name} {cmd}` | `{_md_escape(target)}` |")
        lines.append("")

    # Launch files.
    if pkg.launch_files:
        lines.append("## Launch files")
        lines.append("")
        for lf in pkg.launch_files:
            rel = lf.path.relative_to(src_dir)
            lines.append(f"### `{lf.path.name}`")
            lines.append("")
            lines.append(f"```bash\nros2 launch {pkg.name} {lf.path.name}\n```")
            lines.append("")
            if lf.docstring:
                lines.append(lf.docstring.strip())
                lines.append("")
            if lf.args:
                lines.append("| Launch argument | Default | Description |")
                lines.append("| --- | --- | --- |")
                for a in lf.args:
                    default = f"`{a.default}`" if a.default is not None else "_dynamic_"
                    description = _md_escape(a.description or "")
                    lines.append(f"| `{a.name}` | {default} | {description} |")
                lines.append("")
            lines.append(f"<sub>Source: `{rel}`</sub>")
            lines.append("")

    # Parameters (from YAML config).
    if pkg.config_files:
        lines.append("## Parameters & configuration")
        lines.append("")
        for cf in pkg.config_files:
            rel = cf.path.relative_to(src_dir)
            lines.append(f"### `{cf.path.name}`")
            lines.append("")
            _render_param_tables(lines, cf.params)
            lines.append(":::{dropdown} Full file")
            lines.append("```yaml")
            lines.append(cf.text.rstrip())
            lines.append("```")
            lines.append(":::")
            lines.append("")
            lines.append(f"<sub>Source: `{rel}`</sub>")
            lines.append("")

    # Messages.
    if pkg.messages:
        lines.append("## Interface definitions")
        lines.append("")
        for msg in pkg.messages:
            rel = msg.path.relative_to(src_dir)
            lines.append(f"### `{msg.path.stem}.msg`")
            lines.append("")
            lines.append("| Field | Type |")
            lines.append("| --- | --- |")
            for raw in msg.text.splitlines():
                line = raw.split("#", 1)[0].strip()
                if not line:
                    continue
                parts = line.split(None, 1)
                if len(parts) == 2:
                    ftype, fname = parts
                    lines.append(f"| `{fname}` | `{ftype}` |")
            lines.append("")
            lines.append(f"<sub>Source: `{rel}`</sub>")
            lines.append("")

    # Dependencies.
    if pkg.depends:
        lines.append("## Dependencies")
        lines.append("")
        for label, deps in pkg.depends.items():
            badges = " ".join(f"`{d}`" for d in deps)
            lines.append(f"- **{label}:** {badges}")
        lines.append("")

    # Link to the auto-generated Python API.
    if pkg.has_python_api:
        lines.append("## Python API")
        lines.append("")
        lines.append(
            f"Full module/class/function reference for `{pkg.name}` is generated "
            f"automatically:"
        )
        lines.append("")
        lines.append(f"- {{doc}}`/_generated/autoapi/{pkg.name}/index`")
        lines.append("")

    return "\n".join(lines) + "\n"


def _render_param_tables(lines: list[str], params: dict, prefix: str = "") -> None:
    """Render ROS 2 ``<node>: ros__parameters:`` blocks as readable tables."""
    if not isinstance(params, dict):
        return
    for node_name, body in params.items():
        ros_params = None
        if isinstance(body, dict) and "ros__parameters" in body:
            ros_params = body["ros__parameters"]
        if ros_params is None:
            continue
        lines.append(f"**Node `{node_name}`**")
        lines.append("")
        lines.append("| Parameter | Default | Type |")
        lines.append("| --- | --- | --- |")
        for key, value in _flatten(ros_params):
            lines.append(f"| `{key}` | `{value!r}` | `{type(value).__name__}` |")
        lines.append("")


def _flatten(d: dict, prefix: str = ""):
    for key, value in d.items():
        full = f"{prefix}{key}"
        if isinstance(value, dict):
            yield from _flatten(value, prefix=f"{full}.")
        else:
            yield full, value


def _render_index(packages: list[Package]) -> str:
    lines: list[str] = []
    lines.append("# Package Reference")
    lines.append("")
    lines.append(
        "Auto-generated from each package's `package.xml`, `setup.py`, launch "
        "files, YAML parameters and message definitions. This page rebuilds on "
        "every documentation build, so it always reflects the current workspace."
    )
    lines.append("")
    lines.append("| Package | Type | Executables | Launch | Description |")
    lines.append("| --- | --- | --- | --- | --- |")
    for pkg in packages:
        desc = pkg.description.split("\n")[0]
        if desc.lower().startswith("todo") or not desc:
            desc = "—"
        lines.append(
            f"| [`{pkg.name}`](packages/{pkg.name}.md) | `{pkg.build_type}` | "
            f"{len(pkg.entry_points)} | {len(pkg.launch_files)} | {_md_escape(desc)} |"
        )
    lines.append("")
    lines.append("```{toctree}")
    lines.append(":maxdepth: 1")
    lines.append(":hidden:")
    lines.append(":glob:")
    lines.append("")
    lines.append("packages/*")
    lines.append("```")
    lines.append("")
    return "\n".join(lines) + "\n"


def _render_api_index(packages: list[Package]) -> str:
    """Landing page that gathers every ament_python package's AutoAPI index."""
    python_pkgs = [p for p in packages if p.has_python_api]
    lines: list[str] = []
    lines.append("# Python API Reference")
    lines.append("")
    lines.append(
        "Module, class and function reference for every `ament_python` package, "
        "generated by `sphinx-autoapi` via static analysis (no imports required, "
        "so it builds without a sourced ROS 2 environment)."
    )
    lines.append("")
    if not python_pkgs:
        lines.append("_No Python packages discovered in the workspace._")
        return "\n".join(lines) + "\n"
    lines.append("```{toctree}")
    lines.append(":maxdepth: 2")
    lines.append("")
    for pkg in python_pkgs:
        lines.append(f"/_generated/autoapi/{pkg.name}/index")
    lines.append("```")
    lines.append("")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Public entry point (called from conf.py)
# --------------------------------------------------------------------------- #
def generate(src_dir: Path, out_dir: Path) -> list[Package]:
    """Generate reference Markdown for every package under ``src_dir``.

    Args:
        src_dir: The colcon workspace ``src/`` directory.
        out_dir: Destination directory (e.g. ``docs/reference``). It is created
            if missing; stale per-package pages are removed first.

    Returns:
        The list of discovered :class:`Package` objects (handy for tests).
    """
    src_dir = Path(src_dir)
    out_dir = Path(out_dir)
    packages_dir = out_dir / "packages"
    packages_dir.mkdir(parents=True, exist_ok=True)

    # Remove stale generated pages so deleted packages don't linger.
    for stale in packages_dir.glob("*.md"):
        stale.unlink()

    packages = discover_packages(src_dir)
    for pkg in packages:
        (packages_dir / f"{pkg.name}.md").write_text(
            _render_package_page(pkg, src_dir), encoding="utf-8"
        )

    (out_dir / "index.md").write_text(_render_index(packages), encoding="utf-8")
    (out_dir / "api.md").write_text(_render_api_index(packages), encoding="utf-8")
    return packages


if __name__ == "__main__":
    # Allow standalone invocation for debugging:  python gen_ros_pages.py
    import sys

    here = Path(__file__).resolve()
    ws_src = here.parents[2] / "src"
    target = here.parents[1] / "_generated" / "reference"
    pkgs = generate(ws_src, target)
    print(f"Generated reference pages for {len(pkgs)} packages in {target}")
    for p in pkgs:
        print(f"  - {p.name} ({p.build_type})")

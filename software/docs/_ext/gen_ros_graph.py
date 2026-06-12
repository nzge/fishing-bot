"""Introspect ROS 2 nodes/topics from Python source and emit reference pages.

Parses ``create_publisher`` / ``create_subscription`` calls via AST (no imports)
and merges them with known ros2_control broadcaster topics from ``controllers.yaml``.
Also copies standalone ``.mmd`` diagram sources into ``_static/diagrams/`` so they
are downloadable from the built site and usable in external reports.
"""

from __future__ import annotations

import ast
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


@dataclass
class Endpoint:
    topic: str
    msg_type: str
    direction: str  # 'pub' | 'sub'
    source_file: str
    line: int


@dataclass
class RosNode:
    name: str
    package: str
    executable: str
    file: str
    pubs: list[Endpoint] = field(default_factory=list)
    subs: list[Endpoint] = field(default_factory=list)
    mode: str = "both"  # 'sim' | 'hw' | 'both' | 'conditional'


# ros2_control topics not visible in application Python sources.
_CONTROL_TOPICS: list[tuple[str, str, str, str]] = [
    (
        "joint_state_broadcaster",
        "bringup",
        "/joint_states",
        "sensor_msgs/JointState",
    ),
    (
        "position_trajectory_controller",
        "bringup",
        "/position_trajectory_controller/joint_trajectory",
        "trajectory_msgs/JointTrajectory",
    ),
    (
        "position_trajectory_controller",
        "bringup",
        "/position_trajectory_controller/state",
        "control_msgs/JointTrajectoryControllerState",
    ),
    (
        "fish_effort_controller",
        "bringup",
        "/fish_effort_controller/commands",
        "std_msgs/Float64MultiArray",
    ),
    (
        "tension_sensor_broadcaster",
        "bringup",
        "/tension_sensor_broadcaster/wrench",
        "geometry_msgs/WrenchStamped",
    ),
    (
        "robot_state_publisher",
        "bringup",
        "/robot_description",
        "std_msgs/String",
    ),
    (
        "robot_state_publisher",
        "bringup",
        "/tf",
        "tf2_msgs/TFMessage",
    ),
    (
        "robot_state_publisher",
        "bringup",
        "/tf_static",
        "tf2_msgs/TFMessage",
    ),
]

# Manual metadata for nodes whose launch conditions aren't parseable statically.
_NODE_META: dict[str, dict] = {
    "fish_agent": {"mode": "sim", "package": "planning", "executable": "fish_agent"},
    "recorder": {"mode": "sim", "package": "diagnostics", "executable": "recorder",
                 "note": "Launched when record:=true (sim runs)"},
    "hardware_check": {"mode": "both", "package": "diagnostics",
                       "executable": "hardware_check",
                       "note": "Launched when hardware_check:=true; suppresses controller"},
    "load_cell_node": {"mode": "both", "package": "sensors",
                       "executable": "load_cell_publisher",
                       "note": "source:=sim_fts (sim) or hardware (real)"},
    "admittance_controller": {"mode": "both", "package": "control",
                              "executable": "admittance_node"},
    "force_feedback_controller": {"mode": "both", "package": "control",
                                  "executable": "force_feedback_node"},
    "mujoco_ros2_control": {"mode": "sim", "package": "mujoco_ros2_control",
                            "executable": "ros2_control_node"},
    "controller_manager": {"mode": "hw", "package": "controller_manager",
                           "executable": "ros2_control_node"},
}


def _literal(node: ast.AST):
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError):
        return None


def _parse_endpoints(py_path: Path) -> tuple[str | None, list[Endpoint]]:
    """Return (node_name_from_super_init, endpoints) for a ROS node file."""
    try:
        src = py_path.read_text(encoding="utf-8")
        tree = ast.parse(src)
    except (OSError, SyntaxError):
        return None, []

    node_name: str | None = None
    endpoints: list[Endpoint] = []

    for item in ast.walk(tree):
        if not isinstance(item, ast.Call):
            continue
        func = item.func
        attr = getattr(func, "attr", None)
        if attr not in ("create_publisher", "create_subscription"):
            continue

        direction = "pub" if attr == "create_publisher" else "sub"
        topic = msg_type = None
        if len(item.args) >= 2:
            msg_type = _literal(item.args[0])
            topic = _literal(item.args[1])
        endpoints.append(Endpoint(
            topic=str(topic or "?"),
            msg_type=str(msg_type or "?"),
            direction=direction,
            source_file=py_path.name,
            line=item.lineno,
        ))

    for item in ast.walk(tree):
        if not isinstance(item, ast.Call):
            continue
        func = item.func
        if getattr(func, "attr", None) != "__init__":
            continue
        if not isinstance(func, ast.Attribute):
            continue
        if func.attr != "__init__":
            continue
        if item.args:
            val = _literal(item.args[0])
            if isinstance(val, str):
                node_name = val

    return node_name, endpoints


def discover_nodes(src_dir: Path) -> list[RosNode]:
    nodes: dict[str, RosNode] = {}

    for py in sorted(src_dir.glob("*/*/*.py")):
        if "/test/" in str(py) or py.name.startswith("test_"):
            continue
        nname, eps = _parse_endpoints(py)
        if not eps and not nname:
            continue
        pkg = py.parent.parent.name
        key = nname or py.stem
        if key not in nodes:
            meta = _NODE_META.get(key, {})
            nodes[key] = RosNode(
                name=key,
                package=meta.get("package", pkg),
                executable=meta.get("executable", py.stem),
                file=str(py.relative_to(src_dir)),
                mode=meta.get("mode", "both"),
            )
        for ep in eps:
            if ep.direction == "pub":
                nodes[key].pubs.append(ep)
            else:
                nodes[key].subs.append(ep)

    return sorted(nodes.values(), key=lambda n: n.name)


def _render_topic_index(nodes: list[RosNode]) -> str:
    lines = [
        "# ROS 2 Topic & Node Reference",
        "",
        "Auto-generated from Python source (`create_publisher` / "
        "`create_subscription`) plus known `ros2_control` broadcaster topics. "
        "Rebuild with `./docs/build.sh`.",
        "",
        "For narrative explanations and mode-specific graphs see:",
        "",
        "- {doc}`/ros2/index`",
        "- {doc}`/ros2/simulation`",
        "- {doc}`/ros2/hardware`",
        "",
        "## Application nodes",
        "",
        "| Node | Package | Mode | Publishes | Subscribes |",
        "| --- | --- | --- | --- | --- |",
    ]
    for n in nodes:
        pubs = ", ".join(f"`{e.topic}`" for e in n.pubs) or "—"
        subs = ", ".join(f"`{e.topic}`" for e in n.subs) or "—"
        lines.append(
            f"| `{n.name}` | `{n.package}` | {n.mode} | {pubs} | {subs} |"
        )

    lines += [
        "",
        "## ros2_control & infrastructure topics",
        "",
        "| Component | Topic | Message | Direction | Mode |",
        "| --- | --- | --- | --- | --- |",
    ]
    for comp, _pkg, topic, msg in _CONTROL_TOPICS:
        direction = "pub"
        if "joint_trajectory" in topic and not topic.endswith("/state"):
            direction = "sub (cmd) / pub (state)"
        elif topic.endswith("/state"):
            direction = "pub"
        mode = "both"
        if comp in ("fish_effort_controller", "tension_sensor_broadcaster",
                    "mujoco_ros2_control"):
            mode = "sim"
        if comp == "controller_manager":
            mode = "hw"
        lines.append(
            f"| `{comp}` | `{topic}` | `{msg}` | {direction} | {mode} |"
        )

    lines += [
        "",
        "## Custom messages",
        "",
        "| Message | Package | Fields | Used on |",
        "| --- | --- | --- | --- |",
        "| `interfaces/FishingTension` | `interfaces` | "
        "`header`, `tension_newtons`, `target_tension_newtons` | "
        "`/fishing_arm/tension` |",
        "",
        "See also {doc}`/packages/interfaces` and "
        "{doc}`/_generated/reference/index`.",
        "",
    ]
    return "\n".join(lines) + "\n"


def _render_diagrams_index(diagram_names: list[str]) -> str:
    lines = [
        "# Standalone Diagrams",
        "",
        "These Mermaid source files are copied into the built site at "
        "`_static/diagrams/` during every docs build. Use them directly in "
        "reports, presentations, or [mermaid.live](https://mermaid.live).",
        "",
        "```{note}",
        "The HTML site renders the same diagrams inline via "
        "`sphinxcontrib-mermaid`. The `.mmd` files are the portable, "
        "version-controlled source of truth.",
        "```",
        "",
        "| Diagram file | Description | Repo source | Built site copy |",
        "| --- | --- | --- | --- |",
    ]
    descriptions = {
        "simulation_ros2_graph.mmd": "Full ROS 2 graph — MuJoCo simulation mode",
        "hardware_ros2_graph.mmd": "Full ROS 2 graph — Dynamixel hardware mode",
        "package_architecture.mmd": "Package dependencies and launch delegation",
        "control_loop.mmd": "Closed-loop tension control (mode-agnostic)",
        "fishing_state_machine.mmd": "Controller state machine (MONITOR/HOOK/REGULATE)",
        "sim_data_flow.mmd": "MuJoCo physics chain below the ROS layer",
        "hardware_data_flow.mmd": "Hardware sensing/actuation chain below ROS",
    }
    for name in diagram_names:
        desc = descriptions.get(name, "")
        lines.append(
            f"| `{name}` | {desc} | `software/docs/diagrams/{name}` | "
            f"`_static/diagrams/{name}` (after build) |"
        )
    lines += [
        "",
        "## Export to SVG/PNG for LaTeX reports",
        "",
        "After `./docs/build.sh`, downloadable Mermaid sources are at "
        "`docs/_build/html/_static/diagrams/*.mmd`.",
        "",
        "Install [Mermaid CLI](https://github.com/mermaid-js/mermaid-cli) "
        "(`npm i -g @mermaid-js/mermaid-cli`) then:",
        "",
        "```bash",
        "cd software/docs",
        "for f in diagrams/*.mmd; do",
        "  mmdc -i \"$f\" -o \"exports/$(basename \"${f%.mmd}\").svg\"",
        "done",
        "```",
        "",
        "Or paste any `.mmd` file into [mermaid.live](https://mermaid.live) "
        "and export PNG/SVG from the editor.",
        "",
    ]
    return "\n".join(lines) + "\n"


def _include_mermaid(mmd_path: Path) -> str:
    """Return a MyST markdown block embedding a .mmd file."""
    text = mmd_path.read_text(encoding="utf-8")
    # Strip leading comment lines for cleaner rendered output.
    body = "\n".join(
        ln for ln in text.splitlines()
        if not ln.strip().startswith("%%")
    ).strip()
    return f"```{{mermaid}}\n{body}\n```\n"


def copy_diagrams(diagrams_dir: Path, static_dir: Path) -> list[str]:
    static_dir.mkdir(parents=True, exist_ok=True)
    names: list[str] = []
    for mmd in sorted(diagrams_dir.glob("*.mmd")):
        shutil.copy2(mmd, static_dir / mmd.name)
        names.append(mmd.name)
    return names


def generate(
    src_dir: Path,
    docs_dir: Path,
    out_dir: Path,
) -> list[RosNode]:
    """Generate ROS graph reference pages and copy diagram assets."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    diagrams_src = docs_dir / "diagrams"
    static_diagrams = docs_dir / "_static" / "diagrams"
    diagram_names = copy_diagrams(diagrams_src, static_diagrams)

    nodes = discover_nodes(src_dir)
    (out_dir / "topic_index.md").write_text(
        _render_topic_index(nodes), encoding="utf-8",
    )
    (out_dir / "diagrams.md").write_text(
        _render_diagrams_index(diagram_names), encoding="utf-8",
    )

    # Write include-ready fragments for ros2 pages.
    fragments = out_dir / "fragments"
    fragments.mkdir(exist_ok=True)
    mapping = {
        "simulation_ros2_graph": "simulation_ros2_graph.mmd",
        "hardware_ros2_graph": "hardware_ros2_graph.mmd",
        "control_loop": "control_loop.mmd",
        "fishing_state_machine": "fishing_state_machine.mmd",
        "sim_data_flow": "sim_data_flow.mmd",
        "hardware_data_flow": "hardware_data_flow.mmd",
        "package_architecture": "package_architecture.mmd",
    }
    for key, fname in mapping.items():
        path = diagrams_src / fname
        if path.exists():
            (fragments / f"{key}.md").write_text(
                _include_mermaid(path), encoding="utf-8",
            )

    return nodes


if __name__ == "__main__":
    here = Path(__file__).resolve()
    docs = here.parents[1]
    ws_src = docs.parent / "src"
    target = docs / "_generated" / "ros_graph"
    found = generate(ws_src, docs, target)
    print(f"Generated ROS graph reference ({len(found)} nodes) -> {target}")

"""Sphinx configuration for the fishing-robot ROS 2 workspace documentation.

Key design choices:
  * ``sphinx-autoapi`` (static analysis) instead of ``autodoc`` (which imports
    modules) so docs build without a sourced ROS 2 environment.
  * A custom workspace introspection generator (``_ext/gen_ros_pages.py``) runs
    when you build the docs, keeping the package reference in sync with the source.
  * Generated pages land in ``_generated/`` (git-ignored) so your source tree stays
    clean between builds.
  * MyST so pages can be authored in Markdown.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parent
WS_DIR = DOCS_DIR.parent          # the colcon workspace (software/)
SRC_DIR = WS_DIR / "src"
GENERATED_DIR = DOCS_DIR / "_generated"

sys.path.insert(0, str(DOCS_DIR / "_ext"))

# --------------------------------------------------------------------------- #
# Project information
# --------------------------------------------------------------------------- #
project = "Fishing Robot (MAE 263C)"
author = "nzge"
copyright = "2026, nzge"
release = "0.0.1"

# --------------------------------------------------------------------------- #
# General configuration
# --------------------------------------------------------------------------- #
extensions = [
    "myst_parser",
    "autoapi.extension",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx.ext.todo",
    "sphinx_copybutton",
    "sphinx_design",
    "sphinxcontrib.mermaid",
]

templates_path = ["_templates"]
exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    ".venv",
    "**/.venv",
    "requirements.txt",
    "README.md",
]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

# --------------------------------------------------------------------------- #
# MyST (Markdown) configuration
# --------------------------------------------------------------------------- #
myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "fieldlist",
    "tasklist",
    "attrs_inline",
    "substitution",
]
myst_heading_anchors = 3

# --------------------------------------------------------------------------- #
# AutoAPI: automatic Python API docs via static analysis (no imports).
# --------------------------------------------------------------------------- #
def _find_python_pkg_dirs() -> list[str]:
    """Return relative paths to every ament_python module directory."""
    dirs: list[str] = []
    for pkg_xml in sorted(SRC_DIR.glob("*/package.xml")):
        pkg_dir = pkg_xml.parent
        inner = pkg_dir / pkg_dir.name
        if (inner / "__init__.py").exists():
            dirs.append(os.path.relpath(inner, DOCS_DIR))
    return dirs


autoapi_type = "python"
autoapi_dirs = _find_python_pkg_dirs()
autoapi_root = "_generated/autoapi"
autoapi_keep_files = False
autoapi_add_toctree_entry = False
autoapi_member_order = "groupwise"
autoapi_python_class_content = "both"
autoapi_options = [
    "members",
    "undoc-members",
    "show-inheritance",
    "show-module-summary",
    "special-members",
    "imported-members",
]
# ROS nodes commonly subclass rclpy.node.Node; ignore noisy test scaffolding.
autoapi_ignore = ["*/test/*", "*/tests/*", "*conftest*"]

# --------------------------------------------------------------------------- #
# Napoleon (Google / NumPy docstrings)
# --------------------------------------------------------------------------- #
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True

# --------------------------------------------------------------------------- #
# Intersphinx
# --------------------------------------------------------------------------- #
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}
intersphinx_disabled_reftypes = ["*"]

# --------------------------------------------------------------------------- #
# todo extension
# --------------------------------------------------------------------------- #
todo_include_todos = True

# --------------------------------------------------------------------------- #
# HTML output (Furo theme)
# --------------------------------------------------------------------------- #
html_theme = "furo"
html_title = "Fishing Robot Docs"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_theme_options = {
    "sidebar_hide_name": False,
    "navigation_with_keys": True,
    "source_repository": "https://github.com/nzge/fishing-bot",
    "source_branch": "main",
    "source_directory": "software/docs/",
}

# Mermaid: render diagrams client-side.
mermaid_version = "10.9.1"


# --------------------------------------------------------------------------- #
# Workspace introspection: regenerate the package reference on manual build.
# --------------------------------------------------------------------------- #
def _run_ros_generator(app):  # noqa: ANN001 - Sphinx app
    from gen_ros_pages import generate

    packages = generate(SRC_DIR, GENERATED_DIR / "reference")
    app.builder.info(
        f"[gen_ros_pages] regenerated reference for {len(packages)} packages"
    ) if hasattr(app.builder, "info") else None


def setup(app):  # noqa: ANN001, ANN201 - Sphinx extension hook
    app.connect("builder-inited", _run_ros_generator)

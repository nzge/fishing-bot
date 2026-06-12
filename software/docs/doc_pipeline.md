# The Documentation Pipeline

This page explains how the docs are built. Documentation is **not** updated
automatically in the background — you rebuild it when you want with a single
command.

## What generates the docs

```{mermaid}
flowchart LR
    subgraph sources["Workspace sources"]
        PX[package.xml]
        SP[setup.py]
        LF[*.launch.py]
        YML[config/*.yaml]
        MSG[msg/*.msg]
        PY[Python modules]
        MMD[diagrams/*.mmd]
    end

    subgraph build["./docs/build.sh"]
        GEN["gen_ros_pages.py"]
        GRAPH["gen_ros_graph.py"]
        AUTOAPI["sphinx-autoapi"]
        MERMAID["sphinxcontrib-mermaid"]
    end

    PX --> GEN
    SP --> GEN
    LF --> GEN
    YML --> GEN
    MSG --> GEN
    PY --> AUTOAPI
    PY --> GRAPH
    MMD --> GRAPH

    GEN --> REF["_generated/reference/"]
    GRAPH --> RG["_generated/ros_graph/"]
    GRAPH --> STATIC["_static/diagrams/"]
    AUTOAPI --> API["_generated/autoapi/"]
    REF --> HTML[(HTML)]
    RG --> HTML
    STATIC --> HTML
    API --> HTML
    MERMAID --> HTML
```

Three generators feed the site when you run a build:

1. **`sphinx-autoapi`** statically parses every `ament_python` package and emits
   a module/class/function API reference. It never *imports* your code, so it
   works without a sourced ROS 2 environment.
2. **`gen_ros_pages.py`** (in `docs/_ext/`) introspects each package and renders
   Markdown reference pages covering executables, launch arguments, YAML
   parameters, message fields, and dependencies.
3. **`gen_ros_graph.py`** parses `create_publisher` / `create_subscription` from
   Python sources, emits a topic/node index, embeds Mermaid fragments for ROS
   graph pages, and copies standalone `.mmd` files to `_static/diagrams/`.

Both `_generated/` trees are git-ignored. Diagram sources in `docs/diagrams/`
are **tracked in git** and are the portable export for reports.

## Build the docs

```bash
cd ~/fishing-bot/software
./docs/build.sh
```

First-time setup (once):

```bash
python3 -m venv docs/.venv
source docs/.venv/bin/activate
pip install -r docs/requirements.pip
```

Other commands:

```bash
make -C docs html             # same as build.sh
make -C docs clean            # remove _build/ and _generated/
make -C docs export-diagrams  # SVG export (needs mermaid-cli)
```

Output: `docs/_build/html/index.html`

Standalone diagram sources after build:
`docs/_build/html/_static/diagrams/*.mmd`

## Publish to GitHub Pages

The CI workflow (`.github/workflows/docs.yml`) rebuilds and deploys the site
when you push to `main` (paths under `software/`). Enable Pages once in the
repo settings:

1. Open **Settings → Pages** on [github.com/nzge/fishing-bot/settings/pages](https://github.com/nzge/fishing-bot/settings/pages).
2. Under **Build and deployment → Source**, choose **GitHub Actions**.
3. Push to `main`, or run the **Docs** workflow from the Actions tab.

Published site: <https://nzge.github.io/fishing-bot/>

## Documentation structure

| Path | Authored | Content |
| --- | --- | --- |
| `docs/getting_started.md` | Manual | Build & launch commands |
| `docs/overview.md` | Manual | Architecture hub + embedded graphs |
| `docs/packages/*.md` | Manual | Narrative package guide |
| `docs/ros2/*.md` | Manual | Sim/HW ROS graphs + topic reference |
| `docs/diagrams/*.mmd` | Manual | Standalone Mermaid (report export) |
| `docs/_generated/reference/` | Auto | Per-package launch/param tables |
| `docs/_generated/autoapi/` | Auto | Python API |
| `docs/_generated/ros_graph/` | Auto | Topic index + diagram fragments |

## Extending the docs

- **Add a narrative page:** drop a `.md` file in `docs/` and add it to a
  `{toctree}` (e.g. in `index.md`).
- **Add a diagram:** create `docs/diagrams/my_diagram.mmd`, reference it from a
  `.md` page via `{include} ../_generated/ros_graph/fragments/...` after adding
  it to `gen_ros_graph.py`'s `mapping` dict, or embed inline with a `{mermaid}` block.
- **Document a node:** add a module/class docstring (Google or NumPy style);
  `autoapi` + `napoleon` pick it up on the next build.
- **Improve a package summary:** edit the `<description>` in its `package.xml`.
- **Change the look:** edit `docs/_static/custom.css` or the Furo options in
  `conf.py`.

## Export diagrams for LaTeX reports

**Option A — download after build**

```bash
./docs/build.sh
cp docs/_build/html/_static/diagrams/*.mmd ~/report/figures/
```

Paste into [mermaid.live](https://mermaid.live) → Export PNG/SVG.

**Option B — mermaid-cli**

```bash
npm i -g @mermaid-js/mermaid-cli
make -C software/docs export-diagrams
# → docs/exports/*.svg
```

See {doc}`ros2/diagram_exports` for the full diagram catalog.

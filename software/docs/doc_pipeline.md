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

Diagram PDFs are **exported automatically** when you build the docs. Only
diagrams whose `.mmd` source changed are re-rendered (incremental).

**One-time setup** (Node.js required):

```bash
cd ~/fishing-bot/software/docs
npm ci
```

**Build docs + refresh PDFs:**

```bash
./docs/build.sh
# PDFs land in: software/docs/exports/pdf/
# Also copied to: software/docs/_static/diagrams/ (downloadable from the site)
```

**PDF only** (no Sphinx HTML):

```bash
make -C software/docs diagrams-pdf
```

Each PDF uses `mmdc --pdfFit`: the page is cropped to the diagram bounds
(no US-letter whitespace).

**Skip PDF export:**

```bash
./docs/build.sh --no-pdf
```

### LaTeX

```latex
\usepackage{graphicx}
\includegraphics[width=\linewidth]{figures/simulation_ros2_graph.pdf}
```

Copy from `software/docs/exports/pdf/` into your report `figures/` folder.

### Two-column LaTeX tips

Diagrams are laid out **wide and shallow** (horizontal lanes) for IEEE-style
columns. Prefer:

```latex
% Single column — usually fits the wide layouts
\includegraphics[width=\columnwidth]{figures/simulation_ros2_graph.pdf}

% Spans both columns if a figure is still tight
\begin{figure*}[t]
  \centering
  \includegraphics[width=0.92\textwidth]{figures/simulation_ros2_graph.pdf}
  \caption{Simulation ROS~2 graph (lane 1: fish; lane 2: control; lane 3: sensing).}
\end{figure*}
```

### Manual / other formats

**Option A — download after build**

```bash
./docs/build.sh
cp docs/exports/pdf/*.pdf ~/report/figures/
```

**Option B — SVG** (vector, needs `\includesvg` + Inkscape)

```bash
make -C software/docs diagrams-svg
```

**Option C — mermaid.live**

Paste any `diagrams/*.mmd` into [mermaid.live](https://mermaid.live) → Export PNG/SVG.

See {doc}`ros2/diagram_exports` for the full diagram catalog.

## Export the full codebase as PDF

When simulation videos are recorded and the `software/` tree is finalized, export
the entire ROS 2 documentation bundle (narrative guides, auto-generated package
reference, Python API, ROS graphs) as a single print-ready PDF:

```bash
cd ~/fishing-bot/software/docs
./export_codebase_pdf.sh
```

The script checks readiness before building:

1. **Simulation videos** — `admittance_*` and `force_feedback_*` runs with
   `animation.mp4` under `software/recordings/` (from
   `ros2 launch bringup robot.launch.py headless:=true record:=true`).
2. **Clean workspace** — no uncommitted changes under `software/`.

If you are not ready yet, the script exits with a checklist. Options:

```bash
./export_codebase_pdf.sh --wait          # poll every 60s until gates pass
./export_codebase_pdf.sh --force         # export now (skip gates)
./export_codebase_pdf.sh --with-plots    # also refresh simulate_controllers.py plots
./export_codebase_pdf.sh --output ~/report/fishing-robot.pdf
```

**Output:** `software/docs/exports/fishing-robot-ros2-codebase.pdf`

**How it works:**

1. `sphinx-build -b singlehtml` — one long HTML page with all docs content.
2. Headless Chromium (Puppeteer) prints the page with `print.css` (hides Furo
   chrome, page breaks at sections, waits for Mermaid diagrams to render).
3. Diagram PDFs are also refreshed via `make diagrams-pdf` (unless `--no-diagrams`).

Lower-level targets (without readiness gates):

```bash
make -C software/docs site-pdf     # singlehtml + PDF only
make -C software/docs singlehtml  # HTML only
```

## Export raw source code as PDF

To download every source file under `software/src/` (Python nodes, launch files,
YAML configs, URDF/xacro, messages, etc.) as a single syntax-highlighted PDF:

```bash
cd ~/fishing-bot/software/docs
./export_source_code_pdf.sh
```

**Output:** `software/docs/exports/fishing-robot-ros2-source.pdf`

This export has **no readiness gates** — it always reflects the current tree on
disk, including uncommitted changes. Use it when you need a code snapshot for
submission or archival; use `export_codebase_pdf.sh` for the narrative docs.

Options:

```bash
./export_source_code_pdf.sh --include-sim   # also include software/sim/ MJCF
./export_source_code_pdf.sh --output ~/Downloads/source.pdf
make -C software/docs source-pdf           # Makefile alias
```

Each file appears with line numbers, grouped by ROS 2 package, with a table of
contents at the front. Binary assets (STL meshes) are skipped automatically.

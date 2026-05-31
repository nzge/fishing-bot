# The Documentation Pipeline

This page explains how the docs are built. Documentation is **not** updated
automatically in the background — you rebuild it when you want with a single
command.

## What generates the docs

```{mermaid}
flowchart LR
    subgraph sources["Workspace sources (src/)"]
        PX[package.xml]
        SP[setup.py]
        LF[*.launch.py]
        YML[config/*.yaml]
        MSG[msg/*.msg]
        PY[Python modules]
    end

    subgraph build["./docs/build.sh"]
        GEN["gen_ros_pages.py"]
        AUTOAPI["sphinx-autoapi"]
    end

    PX --> GEN
    SP --> GEN
    LF --> GEN
    YML --> GEN
    MSG --> GEN
    PY --> AUTOAPI

    GEN --> REF["_generated/reference/"]
    AUTOAPI --> API["_generated/autoapi/"]
    REF --> HTML[(HTML in _build/html/)]
    API --> HTML
```

Two engines feed the site when you run a build:

1. **`sphinx-autoapi`** statically parses every `ament_python` package and emits
   a module/class/function API reference. It never *imports* your code, so it
   works without a sourced ROS 2 environment.
2. **`gen_ros_pages.py`** (in `docs/_ext/`) introspects each package and renders
   Markdown reference pages covering executables, launch arguments, YAML
   parameters, message fields, and dependencies.

Both write into `docs/_generated/` (git-ignored). Nothing is created or deleted
in your workspace until you explicitly build.

## Build the docs

```bash
cd ~/fishing-bot/software
./docs/build.sh
```

First-time setup (once):

```bash
python3 -m venv docs/.venv
source docs/.venv/bin/activate
pip install -r docs/requirements.txt
```

Other commands:

```bash
make -C docs html    # same as build.sh
make -C docs clean   # remove _build/ and _generated/
```

Output: `docs/_build/html/index.html`

## Publish to GitHub Pages

The CI workflow (`.github/workflows/docs.yml`) rebuilds and deploys the site
when you push to `main` (paths under `software/`). Enable Pages once in the
repo settings:

1. Open **Settings → Pages** on [github.com/nzge/fishing-bot/settings/pages](https://github.com/nzge/fishing-bot/settings/pages).
2. Under **Build and deployment → Source**, choose **GitHub Actions**.
3. Push to `main`, or run the **Docs** workflow from the Actions tab.

Published site: <https://nzge.github.io/fishing-bot/>

## Extending the docs

- **Add a narrative page:** drop a `.md` file in `docs/` and add it to a
  `{toctree}` (e.g. in `index.md`).
- **Document a node:** add a module/class docstring (Google or NumPy style);
  `autoapi` + `napoleon` pick it up on the next build.
- **Improve a package summary:** edit the `<description>` in its `package.xml`.
- **Change the look:** edit `docs/_static/custom.css` or the Furo options in
  `conf.py`.

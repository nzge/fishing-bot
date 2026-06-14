# Documentation toolchain

Sphinx-based docs for the `fishing-bot` ROS 2 workspace. Run `./docs/build.sh`
when you want updated docs — nothing runs in the background.

## Quick start

```bash
cd ~/fishing-bot/software

python3 -m venv docs/.venv
source docs/.venv/bin/activate
pip install -r docs/requirements.pip

./docs/build.sh
```

## Layout

| Path | Purpose |
| --- | --- |
| `conf.py` | Sphinx configuration (autoapi, MyST, Furo, Mermaid). |
| `index.md`, `overview.md`, `getting_started.md`, `doc_pipeline.md` | Hand-written guides. |
| `_ext/gen_ros_pages.py` | Introspects `src/` and generates the package reference. |
| `_static/custom.css` | Theme tweaks. |
| `_generated/` | Reference + API pages (git-ignored, created on build). |
| `build.sh`, `Makefile` | Build helpers. |

## Commands

```bash
./docs/build.sh        # build -> docs/_build/html/index.html
./docs/export_codebase_pdf.sh  # full codebase PDF (when videos + code are finalized)
make -C docs clean     # remove _build/ and _generated/
```

See {doc}`doc_pipeline` (rendered) for the full explanation.

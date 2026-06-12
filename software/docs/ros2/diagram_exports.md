# Standalone Diagram Exports

Diagram sources live in `software/docs/diagrams/*.mmd`. **PDF exports are
generated automatically** on every docs build (incremental — only changed
diagrams are re-rendered).

## Quick start

```bash
cd ~/fishing-bot/software/docs
npm ci                    # one-time: installs @mermaid-js/mermaid-cli
./build.sh                # exports PDFs + builds HTML
# PDFs: exports/pdf/*.pdf
```

PDF-only, no HTML:

```bash
make diagrams-pdf
```

## Built site + report copies

| Format | Location |
| --- | --- |
| Mermaid source | `diagrams/*.mmd` (git) |
| **PDF (LaTeX)** | `exports/pdf/*.pdf` (generated) |
| PDF (downloadable) | `_static/diagrams/*.pdf` (copied on export) |
| HTML render | inline on {doc}`simulation`, {doc}`hardware`, etc. |

```{include} ../_generated/ros_graph/diagrams.md
:start-line: 2
```

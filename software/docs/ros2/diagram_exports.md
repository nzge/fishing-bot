# Standalone Diagram Exports

Diagrams are maintained as **version-controlled Mermaid source** in
`software/docs/diagrams/*.mmd`. The Sphinx build copies them to
`_static/diagrams/` so they appear in the built site and can be downloaded.

```{include} ../_generated/ros_graph/diagrams.md
:start-line: 2
```

## Embedded vs standalone

| Use case | Location |
| --- | --- |
| Browse in docs site | {doc}`simulation`, {doc}`hardware`, {doc}`../packages/index` |
| Download raw Mermaid | `_build/html/_static/diagrams/*.mmd` after build |
| Edit source | `software/docs/diagrams/*.mmd` in the repo |
| LaTeX / Word report | Export SVG via `mmdc` or [mermaid.live](https://mermaid.live) |

## Makefile shortcut

```bash
make -C software/docs export-diagrams
```

Requires `@mermaid-js/mermaid-cli` (`npm i -g @mermaid-js/mermaid-cli`).
Writes SVGs to `software/docs/exports/`.

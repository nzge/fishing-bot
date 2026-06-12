#!/usr/bin/env bash
# Incrementally export diagrams/*.mmd → exports/pdf/*.pdf
#
# Only rebuilds a PDF when its source .mmd is newer (or the PDF is missing).
# Called automatically by docs/build.sh and `make diagrams-pdf`.
#
# Requires Node.js. Installs mermaid-cli locally on first run:
#   cd software/docs && npm ci
set -euo pipefail

DOCS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIAGRAMS_DIR="$DOCS_DIR/diagrams"
OUT_DIR="$DOCS_DIR/exports/pdf"
STATIC_DIR="$DOCS_DIR/_static/diagrams"
PUPPETEER_CFG="$DOCS_DIR/puppeteer-config.json"
MMDC_EXTRA=()
if [[ -f "$PUPPETEER_CFG" ]]; then
  MMDC_EXTRA=(-p "$PUPPETEER_CFG")
fi

if [[ ! -d "$DIAGRAMS_DIR" ]]; then
  echo "[export_diagram_pdfs] No diagrams/ directory; nothing to do." >&2
  exit 0
fi

# Resolve mmdc: local node_modules → global → npx (last resort).
_mmdc() {
  if [[ -x "$DOCS_DIR/node_modules/.bin/mmdc" ]]; then
    "$DOCS_DIR/node_modules/.bin/mmdc" "$@"
  elif command -v mmdc >/dev/null 2>&1; then
    mmdc "$@"
  elif command -v npx >/dev/null 2>&1; then
    npx --yes @mermaid-js/mermaid-cli "$@"
  else
    return 127
  fi
}

if ! _mmdc --version >/dev/null 2>&1; then
  echo "[export_diagram_pdfs] mermaid-cli not found — skipping PDF export." >&2
  echo "  Install once:  cd software/docs && npm ci" >&2
  echo "  Or globally:   npm i -g @mermaid-js/mermaid-cli" >&2
  exit 0
fi

# Bootstrap local install if package.json exists but node_modules is missing.
if [[ ! -x "$DOCS_DIR/node_modules/.bin/mmdc" ]] && [[ -f "$DOCS_DIR/package.json" ]]; then
  if command -v npm >/dev/null 2>&1; then
    echo "[export_diagram_pdfs] Installing local @mermaid-js/mermaid-cli ..."
    (cd "$DOCS_DIR" && npm ci --silent 2>/dev/null || npm install --silent)
  fi
fi

mkdir -p "$OUT_DIR"
mkdir -p "$STATIC_DIR"

built=0
skipped=0
shopt -s nullglob
for src in "$DIAGRAMS_DIR"/*.mmd; do
  base="$(basename "${src%.mmd}")"
  dest="$OUT_DIR/${base}.pdf"

  if [[ -f "$dest" && "$dest" -nt "$src" && "$dest" -nt "${BASH_SOURCE[0]}" ]]; then
    skipped=$((skipped + 1))
    continue
  fi

  echo "[export_diagram_pdfs] $base.mmd → exports/pdf/$base.pdf"
  # -f (--pdfFit): page size matches diagram bounds (no letter-size margins)
  _mmdc "${MMDC_EXTRA[@]}" -f -i "$src" -o "$dest" -b transparent -w 1600
  cp -f "$dest" "$STATIC_DIR/${base}.pdf"
  built=$((built + 1))
done

# Sync any PDFs that were built previously but already up-to-date.
for pdf in "$OUT_DIR"/*.pdf; do
  [[ -f "$pdf" ]] || continue
  cp -f "$pdf" "$STATIC_DIR/$(basename "$pdf")"
done

echo "[export_diagram_pdfs] Done: ${built} rebuilt, ${skipped} up-to-date → ${OUT_DIR}/"

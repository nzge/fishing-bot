#!/usr/bin/env bash
# Build the documentation site (run manually when you want updated docs).
#
# Usage (from anywhere):
#   ./software/docs/build.sh
#   ./software/docs/build.sh --no-pdf    # skip Mermaid → PDF export
set -euo pipefail

DOCS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DOCS_DIR"

SKIP_PDF=false
for arg in "$@"; do
  case "$arg" in
    --no-pdf) SKIP_PDF=true ;;
  esac
done

if [[ ! -d .venv ]]; then
  echo "Docs venv not found. Create it once:" >&2
  echo "  python3 -m venv docs/.venv && source docs/.venv/bin/activate && pip install -r docs/requirements.pip" >&2
  exit 1
fi

if [[ "$SKIP_PDF" == true ]]; then
  make html SPHINXBUILD="$DOCS_DIR/.venv/bin/sphinx-build" SKIP_DIAGRAM_PDF=1
else
  make html SPHINXBUILD="$DOCS_DIR/.venv/bin/sphinx-build"
fi

echo
echo "Open: file://${DOCS_DIR}/_build/html/index.html"
if [[ -d exports/pdf ]]; then
  echo "Diagram PDFs: file://${DOCS_DIR}/exports/pdf/"
fi

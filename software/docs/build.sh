#!/usr/bin/env bash
# Build the documentation site (run manually when you want updated docs).
#
# Usage (from anywhere):
#   ./software/docs/build.sh
set -euo pipefail

DOCS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DOCS_DIR"

if [[ ! -d .venv ]]; then
  echo "Docs venv not found. Create it once:" >&2
  echo "  python3 -m venv docs/.venv && source docs/.venv/bin/activate && pip install -r docs/requirements.pip" >&2
  exit 1
fi

make html SPHINXBUILD="$DOCS_DIR/.venv/bin/sphinx-build"
echo
echo "Open: file://${DOCS_DIR}/_build/html/index.html"

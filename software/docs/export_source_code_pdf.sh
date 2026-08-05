#!/usr/bin/env bash
# Export all ROS 2 workspace source files as a syntax-highlighted PDF.
#
# Unlike export_codebase_pdf.sh (Sphinx documentation), this dumps the raw
# Python, launch, YAML, URDF, message, and config files from software/src/.
#
# Usage:
#   ./software/docs/export_source_code_pdf.sh
#   ./software/docs/export_source_code_pdf.sh --include-sim
#   ./software/docs/export_source_code_pdf.sh --output ~/Downloads/source.pdf
#
# Output (default):
#   software/docs/exports/fishing-robot-ros2-source.pdf
set -euo pipefail

DOCS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$DOCS_DIR/../.." && pwd)"
DEFAULT_OUT="$DOCS_DIR/exports/fishing-robot-ros2-source.pdf"
HTML_OUT="$DOCS_DIR/_build/source_code/index.html"

OUTPUT="$DEFAULT_OUT"
INCLUDE_SIM=false

usage() {
  sed -n '2,14p' "$0"
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --include-sim) INCLUDE_SIM=true ;;
    --output)
      shift
      OUTPUT="${1:?--output requires a path}"
      ;;
    -h|--help) usage 0 ;;
    *) echo "Unknown option: $1" >&2; usage 1 ;;
  esac
  shift
done

if [[ ! -d "$DOCS_DIR/.venv" ]]; then
  echo "[export_source_code_pdf] Docs venv missing. Create it:" >&2
  echo "  python3 -m venv software/docs/.venv && source software/docs/.venv/bin/activate && pip install -r software/docs/requirements.pip" >&2
  exit 1
fi

BUILD_ARGS=(--output "$HTML_OUT")
if [[ "$INCLUDE_SIM" == true ]]; then
  BUILD_ARGS+=(--include-sim)
fi

echo "[export_source_code_pdf] Collecting source files …"
"$DOCS_DIR/.venv/bin/python" "$DOCS_DIR/scripts/build_source_code_html.py" "${BUILD_ARGS[@]}"

if [[ ! -f "$HTML_OUT" ]]; then
  echo "[export_source_code_pdf] HTML build failed — $HTML_OUT missing" >&2
  exit 1
fi

PDF_TITLE="Fishing Robot ROS 2 Source Code" \
  node "$DOCS_DIR/scripts/export_site_pdf.js" "$HTML_OUT" "$OUTPUT"

echo
echo "Source code PDF: file://$OUTPUT"
echo "Source HTML:     file://$HTML_OUT"

#!/usr/bin/env bash
# Export the full ROS 2 workspace documentation as a single print-ready PDF.
#
# The PDF includes auto-generated package reference, Python API, ROS graphs, and
# all narrative docs — the canonical "codebase documentation" bundle.
#
# Run this once simulation videos exist and the codebase is finalized:
#   ./software/docs/export_codebase_pdf.sh
#
# Options:
#   --force           Skip readiness gates (uncommitted changes, missing videos)
#   --wait            Poll until gates pass (checks every 60s)
#   --with-plots      Also refresh controller simulation plots (simulate_controllers.py)
#   --no-diagrams     Skip Mermaid → PDF diagram export
#   --output PATH     Override output PDF path
#
# Output (default):
#   software/docs/exports/fishing-robot-ros2-codebase.pdf
set -euo pipefail

DOCS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$DOCS_DIR/../.." && pwd)"
RECORDINGS_DIR="$REPO_ROOT/software/recordings"
DEFAULT_OUT="$DOCS_DIR/exports/fishing-robot-ros2-codebase.pdf"

FORCE=false
WAIT=false
WITH_PLOTS=false
SKIP_DIAGRAMS=false
OUTPUT="$DEFAULT_OUT"

usage() {
  sed -n '2,20p' "$0"
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force) FORCE=true ;;
    --wait) WAIT=true ;;
    --with-plots) WITH_PLOTS=true ;;
    --no-diagrams) SKIP_DIAGRAMS=true ;;
    --output)
      shift
      OUTPUT="${1:?--output requires a path}"
      ;;
    -h|--help) usage 0 ;;
    *) echo "Unknown option: $1" >&2; usage 1 ;;
  esac
  shift
done

# --------------------------------------------------------------------------- #
# Readiness gates
# --------------------------------------------------------------------------- #
_count_videos() {
  find "$RECORDINGS_DIR" -mindepth 2 -maxdepth 2 -name 'animation.mp4' 2>/dev/null | wc -l
}

_has_controller_videos() {
  local admittance force_fb
  admittance=false
  force_fb=false
  while IFS= read -r -d '' f; do
    case "$f" in
      *admittance*/animation.mp4) admittance=true ;;
      *force_feedback*/animation.mp4) force_fb=true ;;
    esac
  done < <(find "$RECORDINGS_DIR" -mindepth 2 -maxdepth 2 -name 'animation.mp4' -print0 2>/dev/null)
  $admittance && $force_fb
}

_worktree_dirty() {
  local rel
  while IFS= read -r rel; do
    [[ -n "$rel" ]] || continue
    return 0
  done < <(git -C "$REPO_ROOT" status --porcelain -- software/ 2>/dev/null)
  return 1
}

if [[ "$FORCE" != true ]]; then
  while true; do
    issues=()
    if ! _has_controller_videos; then
      issues+=("Missing controller simulation videos (need */admittance*/animation.mp4 and */force_feedback*/animation.mp4 under software/recordings/)")
    fi
    if _worktree_dirty; then
      issues+=("Uncommitted changes under software/ — finalize and commit before exporting")
    fi
    if [[ ${#issues[@]} -eq 0 ]]; then
      break
    fi
    echo "[export_codebase_pdf] Not ready:" >&2
    printf '  - %s\n' "${issues[@]}" >&2
    if [[ "$WAIT" != true ]]; then
      echo >&2
      echo "Re-run with --wait to block until ready, or --force to export anyway." >&2
      exit 2
    fi
    echo "[export_codebase_pdf] Waiting 60s …" >&2
    sleep 60
  done
fi

echo "[export_codebase_pdf] Readiness OK ($(_count_videos | tr -d ' ') simulation video(s) found)"

# --------------------------------------------------------------------------- #
# Optional: refresh controller simulation plots for report figures
# --------------------------------------------------------------------------- #
if [[ "$WITH_PLOTS" == true ]]; then
  echo "[export_codebase_pdf] Running controller simulation export …"
  python3 "$REPO_ROOT/scripts/simulate_controllers.py" \
    --output-dir "$RECORDINGS_DIR/sim_$(date +%Y%m%d_%H%M%S)"
fi

# --------------------------------------------------------------------------- #
# Build Sphinx singlehtml + diagram PDFs
# --------------------------------------------------------------------------- #
if [[ ! -d "$DOCS_DIR/.venv" ]]; then
  echo "[export_codebase_pdf] Docs venv missing. Create it:" >&2
  echo "  python3 -m venv software/docs/.venv && source software/docs/.venv/bin/activate && pip install -r software/docs/requirements.pip" >&2
  exit 1
fi

if [[ ! -x "$DOCS_DIR/node_modules/.bin/mmdc" ]] && command -v npm >/dev/null 2>&1; then
  echo "[export_codebase_pdf] Installing Node diagram tooling (npm ci) …"
  (cd "$DOCS_DIR" && npm ci --silent 2>/dev/null || npm install --silent)
fi

SPHINXBUILD="$DOCS_DIR/.venv/bin/sphinx-build"
HTML_OUT="$DOCS_DIR/_build/singlehtml"

if [[ "$SKIP_DIAGRAMS" == true ]]; then
  make -C "$DOCS_DIR" singlehtml SPHINXBUILD="$SPHINXBUILD" SKIP_DIAGRAM_PDF=1
else
  make -C "$DOCS_DIR" singlehtml SPHINXBUILD="$SPHINXBUILD"
fi

if [[ ! -f "$HTML_OUT/index.html" ]]; then
  echo "[export_codebase_pdf] Sphinx singlehtml build failed — $HTML_OUT/index.html missing" >&2
  exit 1
fi

# --------------------------------------------------------------------------- #
# HTML → PDF
# --------------------------------------------------------------------------- #
node "$DOCS_DIR/scripts/export_site_pdf.js" "$HTML_OUT/index.html" "$OUTPUT"

echo
echo "Codebase PDF: file://$OUTPUT"
echo "Diagram PDFs:  file://$DOCS_DIR/exports/pdf/ (if built)"
echo "Recordings:    file://$RECORDINGS_DIR/"

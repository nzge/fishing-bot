#!/usr/bin/env bash
# Resolve arduino-cli and project config. Source from other firmware scripts.
set -euo pipefail

FIRMWARE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_FILE="$FIRMWARE_ROOT/arduino-cli.yaml"
SKETCH="$FIRMWARE_ROOT/load_cell"

if [[ -x "$FIRMWARE_ROOT/bin/arduino-cli" ]]; then
  CLI="$FIRMWARE_ROOT/bin/arduino-cli"
elif [[ -n "${ARDUINO_CLI:-}" ]]; then
  CLI="$ARDUINO_CLI"
elif command -v arduino-cli >/dev/null 2>&1; then
  CLI="arduino-cli"
else
  CLI=""
fi

FQBN="${ARDUINO_FQBN:-arduino:avr:mega}"
HX711_LIB="${HX711_LIB:-HX711 Arduino Library}"

cli() {
  if [[ -z "$CLI" ]]; then
    echo "error: arduino-cli not found." >&2
    echo "Install locally (recommended):" >&2
    echo "  curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh \\" >&2
    echo "    | sh -s -- -b $FIRMWARE_ROOT/bin" >&2
    echo "Or system-wide: sudo apt install arduino-cli  (if available)" >&2
    exit 1
  fi
  "$CLI" --config-file "$CONFIG_FILE" "$@"
}

install_cli_hint() {
  cat <<EOF
Install arduino-cli, then re-run:

  curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh \\
    | sh -s -- -b $FIRMWARE_ROOT/bin

  $FIRMWARE_ROOT/scripts/setup.sh
EOF
}

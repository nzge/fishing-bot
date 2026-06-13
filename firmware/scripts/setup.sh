#!/usr/bin/env bash
# One-time (or idempotent) setup: AVR core + HX711 library + verify compile.
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
cd "$FIRMWARE_ROOT"

if [[ -z "$CLI" ]]; then
  install_cli_hint
  exit 1
fi

echo "Using $CLI ($("$CLI" version))"
echo "Config: $CONFIG_FILE"

echo "Updating board index..."
cli core update-index

echo "Installing AVR core (Arduino Mega 2560 → arduino:avr:mega)..."
cli core install arduino:avr

echo "Installing HX711 library..."
cli lib install "$HX711_LIB"

echo "Verifying compile..."
cli compile --fqbn "$FQBN" "$SKETCH"

echo ""
echo "Setup complete. Flash with:"
echo "  $FIRMWARE_ROOT/scripts/flash.sh"

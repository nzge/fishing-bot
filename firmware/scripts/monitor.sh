#!/usr/bin/env bash
# Stream Arduino serial output (9600 baud) for debugging.
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
cd "$FIRMWARE_ROOT"

PORT="${ARDUINO_PORT:-/dev/ttyACM0}"
exec cli monitor -p "$PORT" -c baudrate=9600

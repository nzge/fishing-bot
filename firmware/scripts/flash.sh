#!/usr/bin/env bash
# Compile and upload load_cell firmware to the Arduino.
#
# Usage:
#   ./firmware/scripts/flash.sh
#   ARDUINO_PORT=/dev/ttyACM0 ./firmware/scripts/flash.sh
#
# First time:
#   install arduino-cli (see firmware/scripts/env.sh), then ./firmware/scripts/setup.sh
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
cd "$FIRMWARE_ROOT"

if [[ -z "$CLI" ]]; then
  install_cli_hint
  exit 1
fi

if ! cli core list | grep -q 'arduino:avr.*installed'; then
  echo "AVR core not installed — running setup..."
  "$FIRMWARE_ROOT/scripts/setup.sh"
fi

PORT="${ARDUINO_PORT:-}"
if [[ -z "$PORT" ]]; then
  for candidate in /dev/ttyACM0 /dev/ttyACM1 /dev/ttyUSB0; do
    if [[ -e "$candidate" ]]; then
      PORT="$candidate"
      break
    fi
  done
fi

if [[ -z "$PORT" ]]; then
  echo "error: no Arduino serial port found. Set ARDUINO_PORT=/dev/ttyACM0" >&2
  exit 1
fi

echo "Compiling $SKETCH ($FQBN) ..."
cli compile --fqbn "$FQBN" "$SKETCH"

echo "Uploading to $PORT ..."
cli upload -p "$PORT" --fqbn "$FQBN" "$SKETCH"

echo ""
echo "Flashed successfully."
echo "  Monitor:  $FIRMWARE_ROOT/scripts/monitor.sh"
echo "  ROS hw:   ros2 launch bringup robot.launch.py use_sim:=false"

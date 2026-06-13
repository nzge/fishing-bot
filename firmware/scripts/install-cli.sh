#!/usr/bin/env bash
# Download arduino-cli into firmware/bin/ (no sudo required).
set -euo pipefail

FIRMWARE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN_DIR="$FIRMWARE_ROOT/bin"
VERSION="${ARDUINO_CLI_VERSION:-1.2.2}"
ARCH="${ARDUINO_CLI_ARCH:-Linux_64bit}"
TARBALL="arduino-cli_${VERSION}_${ARCH}.tar.gz"
URL="https://downloads.arduino.cc/arduino-cli/${TARBALL}"

mkdir -p "$BIN_DIR"
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

echo "Downloading $URL ..."
curl -fsSL -o "$tmpdir/$TARBALL" "$URL"
tar -xzf "$tmpdir/$TARBALL" -C "$BIN_DIR" arduino-cli
chmod +x "$BIN_DIR/arduino-cli"

echo "Installed $BIN_DIR/arduino-cli"
"$BIN_DIR/arduino-cli" version
echo ""
echo "Next: $FIRMWARE_ROOT/scripts/setup.sh"

#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

LIMO_SERIAL_PORT="${LIMO_SERIAL_PORT:-/dev/ttylimo}"
LIMO_SERIAL_BAUD="${LIMO_SERIAL_BAUD:-460800}"
LIMO_STARTUP_MODE="${LIMO_STARTUP_MODE:-passive}"

if [[ ! "$LIMO_SERIAL_PORT" =~ ^(/dev/)?[A-Za-z0-9._-]+$ ]]; then
  echo "Invalid LIMO_SERIAL_PORT: ${LIMO_SERIAL_PORT}" >&2
  exit 1
fi

case "$LIMO_SERIAL_BAUD" in
  9600|19200|38400|57600|115200|230400|460800|921600)
    ;;
  *)
    echo "Unsupported LIMO_SERIAL_BAUD: ${LIMO_SERIAL_BAUD}" >&2
    exit 1
    ;;
esac

case "$LIMO_STARTUP_MODE" in
  passive|commanded)
    ;;
  *)
    echo "Unsupported LIMO_STARTUP_MODE: ${LIMO_STARTUP_MODE}" >&2
    exit 1
    ;;
esac

export LIMO_SERIAL_PORT
export LIMO_SERIAL_BAUD
export LIMO_STARTUP_MODE

set +u
source /opt/ros/humble/setup.bash
set -u

cd "${ROOT}"

colcon build --symlink-install "$@"

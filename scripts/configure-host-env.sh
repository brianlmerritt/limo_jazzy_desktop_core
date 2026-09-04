#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DEV_USER="$(id -un)"
DEV_UID="$(id -u)"
DEV_GID="$(id -g)"
LIMO_SERIAL_HOST_DEVICE="/dev/ttyTHS1"
LIMO_SERIAL_PORT="/dev/ttylimo"
LIMO_SERIAL_BAUD="460800"
LIMO_STARTUP_MODE="passive"

if [[ ! "$LIMO_SERIAL_HOST_DEVICE" =~ ^/dev/[A-Za-z0-9._-]+$ ]]; then
  echo "Invalid LIMO host serial path: ${LIMO_SERIAL_HOST_DEVICE}" >&2
  exit 1
fi

if [[ ! "$LIMO_SERIAL_PORT" =~ ^/dev/[A-Za-z0-9._-]+$ ]]; then
  echo "Invalid LIMO container serial path: ${LIMO_SERIAL_PORT}" >&2
  exit 1
fi

if [[ ! "$LIMO_SERIAL_BAUD" =~ ^[0-9]+$ ]] || ((LIMO_SERIAL_BAUD < 1)); then
  echo "Invalid LIMO serial baud rate: ${LIMO_SERIAL_BAUD}" >&2
  exit 1
fi

if [[ ! -c "$LIMO_SERIAL_HOST_DEVICE" ]]; then
  echo "LIMO serial device is not available: ${LIMO_SERIAL_HOST_DEVICE}" >&2
  echo "Power the LIMO chassis and verify its serial connection before running the container." >&2
  exit 1
fi

cat > "${ROOT}/.env" <<ENVEOF
DEV_USER=${DEV_USER}
DEV_UID=${DEV_UID}
DEV_GID=${DEV_GID}
LIMO_SERIAL_HOST_DEVICE=${LIMO_SERIAL_HOST_DEVICE}
LIMO_SERIAL_PORT=${LIMO_SERIAL_PORT}
LIMO_SERIAL_BAUD=${LIMO_SERIAL_BAUD}
LIMO_STARTUP_MODE=${LIMO_STARTUP_MODE}
ENVEOF

echo "Created ${ROOT}/.env"
echo "DEV_USER=${DEV_USER}"
echo "DEV_UID=${DEV_UID}"
echo "DEV_GID=${DEV_GID}"
echo "LIMO_SERIAL_HOST_DEVICE=${LIMO_SERIAL_HOST_DEVICE}"
echo "LIMO_SERIAL_PORT=${LIMO_SERIAL_PORT}"
echo "LIMO_SERIAL_BAUD=${LIMO_SERIAL_BAUD}"
echo "LIMO_STARTUP_MODE=${LIMO_STARTUP_MODE}"

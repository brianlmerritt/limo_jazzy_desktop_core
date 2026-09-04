#!/usr/bin/env bash
set -euo pipefail

startup_mode="${1:-${LIMO_STARTUP_MODE:-passive}}"

case "$startup_mode" in
  passive|commanded)
    ;;
  *)
    echo "Unsupported LIMO startup mode: ${startup_mode}" >&2
    exit 1
    ;;
esac

if [[ ! -c "${LIMO_SERIAL_PORT:-}" ]]; then
  echo "LIMO serial device is unavailable: ${LIMO_SERIAL_PORT:-unset}" >&2
  exit 1
fi

set +u
source /opt/ros/humble/setup.bash
source /workspace/install/limo_msgs/share/limo_msgs/local_setup.bash
source /workspace/install/limo_base/share/limo_base/local_setup.bash
set -u

echo "Starting limo_base in ${startup_mode} mode on ${LIMO_SERIAL_PORT} at ${LIMO_SERIAL_BAUD} baud."
exec ros2 launch limo_base limo_base.launch.py startup_mode:="${startup_mode}"

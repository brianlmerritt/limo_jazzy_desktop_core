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

source "$(dirname "${BASH_SOURCE[0]}")/ros-env.sh"

echo "Starting limo_base in ${startup_mode} mode on ${LIMO_SERIAL_PORT} at ${LIMO_SERIAL_BAUD} baud."
source "$(dirname "${BASH_SOURCE[0]}")/robot-namespace.sh"
exec ros2 run limo_base limo_base --ros-args \
  -r "__ns:=${ROBOT_PREFIX:-/}" -r __node:=limo_base_node \
  -p "port_name:=${LIMO_SERIAL_PORT}" -p "baud_rate:=${LIMO_SERIAL_BAUD}" \
  -p "startup_mode:=${startup_mode}" -p pub_odom_tf:=true \
  -r /odom:=wheel/odom -r /cmd_vel:=cmd_vel -r /imu:=imu \
  -r /limo_status:=limo_status -r /tf:=tf -r /tf_static:=tf_static

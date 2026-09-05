#!/usr/bin/env bash
set -euo pipefail

if [[ "${YDLIDAR_AVAILABLE:-false}" != "true" ]] || [[ ! -c "${YDLIDAR_CONTAINER_PATH:-/dev/ydlidar}" ]]; then
  echo "YDLIDAR X2L is unavailable; run scripts/configure-host-env.sh after connecting it." >&2
  exit 1
fi

[[ "${YDLIDAR_BAUD:-}" =~ ^[0-9]+$ ]] && ((YDLIDAR_BAUD > 0 && YDLIDAR_BAUD <= 4000000)) || {
  echo "Invalid YDLIDAR_BAUD; regenerate .env from config." >&2
  exit 1
}
[[ "${YDLIDAR_ROS_CONFIG:-}" == /workspace/config/*.yaml && -r "$YDLIDAR_ROS_CONFIG" ]] || {
  echo "Missing YDLIDAR_ROS_CONFIG parameter file." >&2
  exit 1
}
set +u
source /opt/ros/humble/setup.bash
source /workspace/scripts/sensor-env.sh
source /workspace/install/ydlidar_ros2_driver/share/ydlidar_ros2_driver/local_setup.bash
set -u

exec ros2 run ydlidar_ros2_driver ydlidar_ros2_driver_node \
  --ros-args --params-file "$YDLIDAR_ROS_CONFIG" \
  -p "port:=$YDLIDAR_CONTAINER_PATH" -p "baudrate:=$YDLIDAR_BAUD"

#!/usr/bin/env bash
set -euo pipefail

if [[ "${REALSENSE_AVAILABLE:-false}" != "true" ]]; then
  echo "Front RealSense is unavailable; run scripts/configure-host-env.sh after connecting it." >&2
  exit 1
fi

[[ "${REALSENSE_SERIAL:-}" =~ ^[A-Za-z0-9_.:-]+$ ]] || {
  echo "Invalid REALSENSE_SERIAL; regenerate .env from config." >&2
  exit 1
}
[[ "${REALSENSE_ROS_CONFIG:-}" == /workspace/config/*.yaml && -r "$REALSENSE_ROS_CONFIG" ]] || {
  echo "Missing REALSENSE_ROS_CONFIG parameter file." >&2
  exit 1
}
set +u
source /opt/ros/humble/setup.bash
source /workspace/scripts/sensor-env.sh
source /workspace/install/realsense2_camera_msgs/share/realsense2_camera_msgs/local_setup.bash
source /workspace/install/realsense2_description/share/realsense2_description/local_setup.bash
source /workspace/install/realsense2_camera/share/realsense2_camera/local_setup.bash
set -u

exec ros2 launch realsense2_camera rs_launch.py \
  config_file:="$REALSENSE_ROS_CONFIG" \
  serial_no:="'${REALSENSE_SERIAL}'"

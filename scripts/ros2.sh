#!/usr/bin/env bash
set -euo pipefail

set +u
source /opt/ros/humble/setup.bash

source /workspace/install/limo_msgs/share/limo_msgs/local_setup.bash
source /workspace/install/limo_base/share/limo_base/local_setup.bash
if [[ -r /workspace/.deps/sensor-env.sh ]]; then
  source /workspace/scripts/sensor-env.sh
fi
for sensor_package in \
  ydlidar_ros2_driver \
  realsense2_camera_msgs \
  realsense2_description \
  realsense2_camera; do
  sensor_setup="/workspace/install/${sensor_package}/share/${sensor_package}/local_setup.bash"
  if [[ -f "$sensor_setup" ]]; then
    source "$sensor_setup"
  fi
done
set -u

exec ros2 "$@"

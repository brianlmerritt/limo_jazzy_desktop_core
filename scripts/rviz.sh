#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/robot-namespace.sh"
exec "$ROOT/scripts/x11.sh" ./scripts/ros2.sh run rviz2 rviz2 \
  -d /workspace/config/robot/navigation.rviz --ros-args \
  -r "__ns:=${ROBOT_PREFIX:-/}" -r /tf:=tf -r /tf_static:=tf_static

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
source "$(dirname "${BASH_SOURCE[0]}")/ros-env.sh"

exec ros2 launch /workspace/scripts/realsense.launch.py

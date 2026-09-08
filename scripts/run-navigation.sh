#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/robot-namespace.sh"
source "$(dirname "${BASH_SOURCE[0]}")/ros-env.sh"
check_orientation="${LIMO_CHECK_LIDAR_ORIENTATION:-true}"
[[ "$check_orientation" == true || "$check_orientation" == false ]] || { echo "LIMO_CHECK_LIDAR_ORIENTATION must be true or false" >&2; exit 2; }
exec ros2 launch /workspace/scripts/navigation.launch.py "mode:=${1:?mapping, navigation or exploration}" "check_lidar_orientation:=$check_orientation"

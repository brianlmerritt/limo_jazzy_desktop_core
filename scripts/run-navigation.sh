#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/robot-namespace.sh"
source "$(dirname "${BASH_SOURCE[0]}")/ros-env.sh"
exec ros2 launch /workspace/scripts/navigation.launch.py "mode:=${1:?mapping, navigation or exploration}"

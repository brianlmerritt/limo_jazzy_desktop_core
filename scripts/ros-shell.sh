#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f /opt/ros/${ROS_DISTRO:-jazzy}/setup.bash && "$ROOT" == /workspace ]]; then
  exec bash --rcfile "${ROOT}/scripts/ros-shell-rc.bash" -i
fi
exec docker compose --project-directory "$ROOT" -f "${ROOT}/compose.yaml" \
  exec dev bash --rcfile /workspace/scripts/ros-shell-rc.bash -i

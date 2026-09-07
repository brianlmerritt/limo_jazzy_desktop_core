#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/robot-namespace.sh"
source "$(dirname "${BASH_SOURCE[0]}")/ros-env.sh"
[[ -n "$LIMO_ROS_NAMESPACE" ]] || { echo "Missing robot namespace" >&2; exit 1; }
for node in slam_toolbox controller_server planner_server smoother_server behavior_server bt_navigator velocity_smoother collision_monitor; do
  ready=false
  for _ in {1..15}; do
    if timeout 4 ros2 lifecycle get "$ROBOT_PREFIX/$node" 2>/dev/null | grep -Fq 'active [3]'; then
      ready=true
      break
    fi
    sleep 1
  done
  [[ "$ready" == true ]] || { echo "Not active: $node" >&2; exit 1; }
done
exec python3 /workspace/scripts/check-navigation-data.py

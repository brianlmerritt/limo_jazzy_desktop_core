#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/robot-namespace.sh"
compose=(docker compose --project-directory "$ROOT" -f "$ROOT/compose.yaml")
[[ -n "$LIMO_ROS_NAMESPACE" ]] || { echo "Run configure-host-env.sh first." >&2; exit 1; }
case "${1:-}" in
  mapping)
    "${compose[@]}" exec -T dev ./scripts/ros2.sh pkg prefix slam_toolbox >/dev/null
    "${compose[@]}" --profile robot --profile navigation up -d robot-transforms mapping
    ;;
  start)
    if [[ $# == 3 && "$2" == --check-lidar-orientation && ( "$3" == true || "$3" == false ) ]]; then
      export LIMO_CHECK_LIDAR_ORIENTATION="$3"
    elif [[ $# != 1 ]]; then
      echo "Usage: $0 start [--check-lidar-orientation true|false]" >&2
      exit 2
    fi
    "${compose[@]}" --profile exploration --profile navigation stop hide-and-seek exploration navigation
    "$0" mapping
    "${compose[@]}" --profile navigation up -d --force-recreate navigation
    if ! "${compose[@]}" exec -T dev ./scripts/check-navigation.sh; then
      "${compose[@]}" --profile exploration --profile navigation stop hide-and-seek exploration navigation
      echo "Navigation readiness failed; navigation and exploration stopped." >&2
      exit 1
    fi
    ;;
  explore)
    "${compose[@]}" --profile game stop hide-and-seek
    "${compose[@]}" exec -T dev ./scripts/check-navigation.sh
    echo "Starting autonomous exploration now."
    "${compose[@]}" --profile exploration up -d exploration
    ;;
  stop)
    "${compose[@]}" --profile exploration --profile navigation stop hide-and-seek exploration navigation
    # Finish with explicit zeros after all autonomous command producers have stopped.
    "${compose[@]}" exec -T dev timeout 8 ./scripts/ros2.sh topic pub --wait-matching-subscriptions 0 --times 10 --rate 10 \
      "$ROBOT_PREFIX/cmd_vel" geometry_msgs/msg/Twist '{}'
    ;;
  reset)
    [[ $# == 1 ]] || { echo "Usage: $0 reset" >&2; exit 2; }
    "$0" stop
    "${compose[@]}" --profile navigation stop mapping
    "$0" mapping
    echo "Fresh live map started. Navigation, exploration and game remain stopped; saved maps and chassis odometry are unchanged."
    ;;
  save-map)
    [[ $# == 2 && "$2" =~ ^[A-Za-z0-9_-]+$ ]] || { echo "Usage: $0 save-map NAME" >&2; exit 2; }
    mkdir -p "$ROOT/.deps/maps"
    "${compose[@]}" exec -T dev ./scripts/ros2.sh run nav2_map_server map_saver_cli \
      -f "/workspace/.deps/maps/$2" --ros-args -r "__ns:=/$LIMO_ROS_NAMESPACE" \
      -p map_subscribe_transient_local:=true -p save_map_timeout:=10.0
    ;;
  *) echo "Usage: $0 {mapping|start|explore|stop|reset|save-map NAME}" >&2; exit 2 ;;
esac

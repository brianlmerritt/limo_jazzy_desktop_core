#!/usr/bin/env bash
# Four host launch modes. Explore/game explicitly start autonomous goals.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
usage() {
  echo 'Usage: ./scripts/launch-robot.sh {nav|yolo [nano|small]|explore|hide-and-seek [nano|small]|stop}'
}
mode="${1:-}"
model="${2:-nano}"
[[ $# -le 2 ]] || { usage >&2; exit 2; }
case "$mode" in
  yolo|hide-and-seek) [[ "$model" == nano || "$model" == small ]] || { usage >&2; exit 2; } ;;
  nav|explore|stop) [[ $# == 1 ]] || { usage >&2; exit 2; } ;;
  *) usage >&2; exit 2 ;;
esac
source ./scripts/robot-namespace.sh
case "$mode" in
  nav)
    docker compose --profile game stop hide-and-seek
    exec ./scripts/start-mapping.sh
    ;;
  yolo)
    export LIMO_YOLO_MODEL="$model"
    docker compose build vision
    # Refresh camera device discovery when starting camera without chassis/Nav2.
    ./scripts/configure-host-env.sh
    docker compose --profile sensors up -d realsense
    docker compose --profile vision up -d --force-recreate vision
    if ! ./scripts/check-vision.sh; then
      docker compose --profile vision stop vision
      exit 1
    fi
    ;;
  explore)
    docker compose --profile game stop hide-and-seek
    ./scripts/start-mapping.sh
    exec ./scripts/navigation.sh explore
    ;;
  hide-and-seek)
    docker compose --profile game --profile exploration stop hide-and-seek exploration
    ./scripts/start-mapping.sh
    "$0" yolo "$model"
    docker compose --profile game up -d --force-recreate hide-and-seek
    if ! docker compose exec -T hide-and-seek bash -c 'source ./scripts/ros-env.sh; python3 /workspace/scripts/check-game-data.py'; then
      ./scripts/navigation.sh stop
      exit 1
    fi
    echo 'Hide-and-seek prototype running: frontier search pauses after confirming a visible person.'
    ;;
  stop)
    docker compose --profile game --profile vision stop hide-and-seek vision
    exec ./scripts/bring_down_limo_base.sh
    ;;
esac

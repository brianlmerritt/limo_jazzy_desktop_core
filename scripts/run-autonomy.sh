#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/ros-env.sh"
set +u
source /opt/autonomy-install/local_setup.bash
set -u
namespace="${LIMO_ROS_NAMESPACE:-}"
[[ "$namespace" =~ ^[A-Za-z][A-Za-z0-9_]*$ ]] || { echo 'Invalid namespace' >&2; exit 2; }
case "${1:-}" in
  yolo)
    mkdir -p "${YOLO_CONFIG_DIR:-/tmp/ultralytics}"
    model="${LIMO_YOLO_MODEL:-nano}"
    [[ "$model" == nano || "$model" == small ]] || { echo 'Model must be nano or small' >&2; exit 2; }
    exec /opt/vision-venv/bin/python -m limo_vision.pose --ros-args \
      -r "__ns:=/$namespace" -p "model_size:=$model" -p "device:='${LIMO_YOLO_DEVICE:-0}'"
    ;;
  hide-and-seek)
    exec ros2 launch /workspace/scripts/hide-and-seek.launch.py
    ;;
  *) echo 'Expected yolo or hide-and-seek' >&2; exit 2 ;;
esac

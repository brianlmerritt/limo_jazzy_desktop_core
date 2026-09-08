#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source ./scripts/robot-namespace.sh
docker compose exec -T vision bash -c 'source ./scripts/ros-env.sh; exec /opt/vision-venv/bin/python /workspace/scripts/check-vision-data.py'

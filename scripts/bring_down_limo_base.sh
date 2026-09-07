#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ $# -gt 0 ]]; then
  echo "Usage: $0  (run on the host; stops all robot services and containers)" >&2
  exit 2
fi
if [[ -f /opt/ros/${ROS_DISTRO:-jazzy}/setup.bash && "$ROOT" == /workspace ]]; then
  echo "Run this shutdown script from the host repository, not inside Docker." >&2
  exit 2
fi

compose=(docker compose --project-directory "$ROOT" -f "$ROOT/compose.yaml")
dev_running="$("${compose[@]}" ps -q --status running dev 2>/dev/null || true)"

if [[ -n "$dev_running" ]]; then
  echo "Stopping navigation and publishing an explicit zero command..."
  ./scripts/navigation.sh stop
else
  echo "Development container is not running; stopping navigation producers..."
  "${compose[@]}" --profile exploration --profile navigation stop exploration navigation
fi

echo "Bringing down all Compose profiles..."
"${compose[@]}" \
  --profile robot \
  --profile sensors \
  --profile navigation \
  --profile exploration \
  --profile desktop \
  down

echo "All LIMO Compose services are stopped."
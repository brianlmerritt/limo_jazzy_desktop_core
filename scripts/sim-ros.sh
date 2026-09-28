#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")/.." && pwd)"
cd "$repo_root"
if [[ $# -eq 0 ]]; then set -- bash; fi
exec docker compose -f compose.sim.yaml exec ros bash -c 'source /opt/ros/jazzy/setup.bash; if [[ -f /workspace/install/jazzy/setup.bash ]]; then source /workspace/install/jazzy/setup.bash; fi; exec "$@"' bash "$@"

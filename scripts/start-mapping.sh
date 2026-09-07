#!/usr/bin/env bash
# Start a supervised mapping session; no exploration or navigation goal is sent.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ $# == 0 ]] || { echo "Usage: $0" >&2; exit 2; }
cd "$ROOT"
completed=false
cleanup() {
  if [[ "$completed" != true ]]; then
    docker compose --profile navigation --profile exploration stop exploration navigation mapping || true
    echo 'Mapping startup failed; navigation and exploration are stopped.' >&2
  fi
}
trap cleanup EXIT
./scripts/bring_up_limo_base.sh
./scripts/navigation.sh start
./scripts/desktop.sh start
completed=true
echo 'Mapping, Nav2 and browser RViz are ready. No movement goal was sent.'
echo 'On your Mac: ssh -N -o ExitOnForwardFailure=yes -L 6080:127.0.0.1:6080 blm@limo_wifi'
echo 'Browser: http://127.0.0.1:6080/vnc.html?autoconnect=1&resize=remote'
echo 'Inspect the map, scan alignment and footprint before sending any goal.'
echo 'Save map: ./scripts/navigation.sh save-map room'
echo 'Stop everything: ./scripts/bring_down_limo_base.sh'

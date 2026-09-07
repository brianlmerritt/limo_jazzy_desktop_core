#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose=(docker compose --project-directory "$ROOT" -f "$ROOT/compose.yaml" --profile desktop)
case "${1:-start}" in
  start)
    "${compose[@]}" build dev
    "${compose[@]}" build desktop
    "${compose[@]}" up -d --no-deps --force-recreate --wait --wait-timeout 90 desktop
    echo 'On your Mac: ssh -N -o ExitOnForwardFailure=yes -L 6080:127.0.0.1:6080 blm@limo_wifi'
    echo 'Then open: http://127.0.0.1:6080/vnc.html?autoconnect=1&resize=remote'
    ;;
  stop) "${compose[@]}" stop desktop ;;
  logs) "${compose[@]}" logs --tail=100 desktop ;;
  *) echo "Usage: $0 [start|stop|logs]" >&2; exit 2 ;;
esac

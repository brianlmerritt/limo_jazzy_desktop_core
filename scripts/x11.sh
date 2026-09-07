#!/usr/bin/env bash
# Run from the host SSH session or a terminal on the LIMO desktop.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ $# -gt 0 ]] || { echo "Usage: $0 COMMAND [ARGUMENT...]" >&2; exit 2; }
[[ -n "${DISPLAY:-}" ]] || { echo 'No DISPLAY. Connect from XQuartz with ssh -Y, then run this helper.' >&2; exit 1; }
command -v xauth >/dev/null || { echo 'The SSH host needs xauth for X11 forwarding.' >&2; exit 1; }
display_auth="${XAUTHORITY:-$HOME/.Xauthority}"
[[ -r "$display_auth" ]] || { echo 'No readable Xauthority file for this session.' >&2; exit 1; }
session_auth="$(mktemp)"
trap 'rm -f "$session_auth"' EXIT
# Resolve DISPLAY on the host, whose hostname matches the SSH cookie. FamilyWild
# lets the same cookie work with Docker's different hostname. No cookie is logged.
xauth -f "$display_auth" nlist "$DISPLAY" | sed 's/^..../ffff/' | xauth -f "$session_auth" nmerge -
[[ -s "$session_auth" ]] || { echo 'No authentication cookie matched DISPLAY.' >&2; exit 1; }
gl_options=()
# Mesa may treat even LIBGL_ALWAYS_INDIRECT=0 as enabled: leave it unset by default.
if [[ "${LIBGL_ALWAYS_INDIRECT:-0}" == 1 ]]; then
  gl_options+=(-e LIBGL_ALWAYS_INDIRECT=1)
fi
docker compose --project-directory "$ROOT" -f "$ROOT/compose.yaml" run --rm --no-deps -T \
  -e DISPLAY -e QT_X11_NO_MITSHM=1 \
  -e "LIBGL_ALWAYS_SOFTWARE=${LIBGL_ALWAYS_SOFTWARE:-1}" \
  "${gl_options[@]}" \
  -e XAUTHORITY=/tmp/limo.Xauthority \
  -v "$session_auth:/tmp/limo.Xauthority:ro" -v /tmp/.X11-unix:/tmp/.X11-unix:ro \
  dev "$@"

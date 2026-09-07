#!/usr/bin/env bash
set -euo pipefail
source /workspace/scripts/robot-namespace.sh
source /workspace/scripts/ros-env.sh
export DISPLAY=:1
export XDG_RUNTIME_DIR=/tmp/limo-desktop
export XAUTHORITY="$XDG_RUNTIME_DIR/Xauthority"
export LIBGL_ALWAYS_SOFTWARE=1
export GALLIUM_DRIVER=llvmpipe
export LP_NUM_THREADS=2
unset LIBGL_ALWAYS_INDIRECT MESA_GL_VERSION_OVERRIDE MESA_GLSL_VERSION_OVERRIDE
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"
umask 077
touch "$XAUTHORITY"
xauth -f "$XAUTHORITY" add "$DISPLAY" . "$(python3 -c 'import secrets; print(secrets.token_hex(16))')"
pids=()
cleanup() {
  trap - EXIT INT TERM
  if ((${#pids[@]})); then
    kill "${pids[@]}" 2>/dev/null || true
    wait "${pids[@]}" 2>/dev/null || true
  fi
  rm -f "$XAUTHORITY"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
# Authentication is supplied by SSH. Both network listeners are loopback-only.
Xtigervnc "$DISPLAY" -geometry 1280x800 -depth 24 -localhost yes \
  -rfbport 5901 -SecurityTypes None -AlwaysShared -nolisten tcp \
  -auth "$XAUTHORITY" -desktop "LIMO RViz2" &
pids+=("$!")
ready=false
for _ in {1..50}; do
  if xdpyinfo >/dev/null 2>&1; then ready=true; break; fi
  kill -0 "${pids[0]}" 2>/dev/null || break
  sleep 0.2
done
[[ "$ready" == true ]] || { echo 'Virtual display failed to start.' >&2; exit 1; }
glxinfo -B
openbox &
pids+=("$!")
websockify --web=/usr/share/novnc 127.0.0.1:6080 127.0.0.1:5901 &
pids+=("$!")
rviz2 -d /workspace/config/robot/navigation.rviz --ros-args \
  -r "__ns:=${ROBOT_PREFIX:-/}" -r /tf:=tf -r /tf_static:=tf_static &
pids+=("$!")
echo 'Browser desktop starting at http://127.0.0.1:6080/vnc.html (use an SSH tunnel).'
# If any required process exits, tear down the session rather than leaving a blank desktop.
wait -n "${pids[@]}"

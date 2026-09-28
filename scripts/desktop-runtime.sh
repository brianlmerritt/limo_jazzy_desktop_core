#!/usr/bin/env bash
# User-level lifecycle management; never kills unrelated processes.
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")/.." && pwd)"
name="$(basename -- "$0")"
if [[ "$name" == desktop-runtime.sh ]]; then name="${1:-help}"; shift || true; fi
action="${1:-status}"
if [[ $# -gt 0 ]]; then shift; fi
unit=isaac-limo.service
llama_unit=llama-qwen38.service
state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/limo-sim"
export LIMO_SIM_OUTPUT_DIR="${LIMO_SIM_OUTPUT_DIR:-$HOME/ai/outputs/limo-sim}"
mkdir -p "$state_dir" "$LIMO_SIM_OUTPUT_DIR"
cd "$repo_root"
compose() { docker compose -f "$repo_root/compose.sim.yaml" "$@"; }
active() { systemctl --user is-active --quiet "$1"; }
restore_llama() {
  if [[ -f "$state_dir/restore-llama" ]]; then
    systemctl --user start "$llama_unit"
    rm -- "$state_dir/restore-llama"
    echo 'Restored the previously running Qwen service.'
  fi
}
case "$action" in
  start|stop|restart)
    exec 9>"${XDG_RUNTIME_DIR:-/tmp}/limo-desktop-${UID}.lock"
    flock 9
    ;;
esac
case "$name:$action" in
  llama:start)
    if active "$unit" || pgrep -f "$HOME/isaacsim/(kit/kit|kit/python/bin/python3)" >/dev/null; then
      echo 'Isaac is using the GPU. Run: limo-sim stop' >&2; exit 1
    fi
    systemctl --user start "$llama_unit"
    echo 'Qwen starting at http://127.0.0.1:8080 (llama status / llama logs).'
    ;;
  llama:stop)
    systemctl --user stop "$llama_unit"
    rm -f -- "$state_dir/restore-llama"
    ;;
  llama:status) systemctl --user status --no-pager "$llama_unit" ;;
  llama:logs) exec journalctl --user -u "$llama_unit" -n 60 -f ;;
  limo-sim:start)
    if active "$unit"; then echo 'LIMO simulation is already running.'; exit 0; fi
    if pgrep -f "$HOME/isaacsim/(kit/kit|kit/python/bin/python3)" >/dev/null; then
      echo 'Another Isaac process is running. Close that session before starting the managed simulation.' >&2; exit 1
    fi
    compose up -d
    if active "$llama_unit"; then
      touch "$state_dir/restore-llama"
      systemctl --user stop "$llama_unit"
      echo 'Stopped Qwen to release GPU memory; limo-sim stop will restore it.'
    fi
    rm -f -- "$LIMO_SIM_OUTPUT_DIR/ready.json"
    if [[ -f "$LIMO_SIM_OUTPUT_DIR/isaac.log" ]]; then
      mv -- "$LIMO_SIM_OUTPUT_DIR/isaac.log" "$LIMO_SIM_OUTPUT_DIR/isaac-$(date +%Y%m%d-%H%M%S)-$$.log"
    fi
    systemctl --user reset-failed "$unit" 2>/dev/null || true
    if ! systemd-run --user --unit="$unit" --collect \
      --property=Type=exec --property=KillMode=control-group --property=TimeoutStopSec=30 \
      --property="WorkingDirectory=$repo_root" \
      --property="StandardOutput=append:$LIMO_SIM_OUTPUT_DIR/isaac.log" \
      --property="StandardError=append:$LIMO_SIM_OUTPUT_DIR/isaac.log" \
      --setenv="DISPLAY=${DISPLAY:-:1}" --setenv="XAUTHORITY=${XAUTHORITY:-}" \
      --setenv="LIMO_SIM_DOMAIN_ID=${LIMO_SIM_DOMAIN_ID:-73}" \
      --setenv="LIMO_SIM_OUTPUT_DIR=$LIMO_SIM_OUTPUT_DIR" \
      --setenv="LIMO_SIM_CONFIG=${LIMO_SIM_CONFIG:-$repo_root/config/robot/limo-sim.json}" \
      --setenv="ISAAC_LAUNCHER=${ISAAC_LAUNCHER:-$HOME/.local/bin/isaac}" \
      "$repo_root/scripts/run-limo-sim.sh" "$@"; then
      restore_llama; exit 1
    fi
    echo 'Isaac is starting. Run: limo-sim wait; limo-sim check; limo-sim rviz'
    ;;
  limo-sim:stop)
    if [[ "$(systemctl --user show "$unit" -p LoadState --value)" != not-found ]]; then
      systemctl --user stop "$unit"
    fi
    compose down
    rm -f -- "$LIMO_SIM_OUTPUT_DIR/ready.json"
    restore_llama
    ;;
  limo-sim:status)
    systemctl --user status --no-pager "$unit" || true
    compose ps
    if active "$unit" && [[ -f "$LIMO_SIM_OUTPUT_DIR/ready.json" ]]; then
      cat "$LIMO_SIM_OUTPUT_DIR/ready.json"
    fi
    ;;
  limo-sim:wait)
    for ((i=0; i<600; i++)); do
      if ! active "$unit"; then echo 'Isaac exited; inspect: limo-sim logs' >&2; exit 1; fi
      if [[ -f "$LIMO_SIM_OUTPUT_DIR/ready.json" ]]; then echo 'LIMO sensors ready.'; exit 0; fi
      sleep 1
    done
    echo 'Isaac startup timed out; inspect: limo-sim logs' >&2; exit 1
    ;;
  limo-sim:logs) exec tail -n 60 -F "$LIMO_SIM_OUTPUT_DIR/isaac.log" ;;
  limo-sim:check)
    exec "$repo_root/scripts/sim-ros.sh" python3 /workspace/scripts/check-limo-sim.py "$@"
    ;;
  limo-sim:rviz)
    exec "$repo_root/scripts/sim-ros.sh" rviz2 -d /workspace/config/robot/limo-sim.rviz --ros-args -p use_sim_time:=true "$@"
    ;;
  limo-sim:teleop)
    exec "$repo_root/scripts/sim-ros.sh" ros2 run teleop_twist_keyboard teleop_twist_keyboard \
      --ros-args -r cmd_vel:=/limo/cmd_vel -p speed:=0.2 -p turn:=0.6 -p repeat_rate:=10.0 -p key_timeout:=0.5 "$@"
    ;;
  limo-sim:shell) exec "$repo_root/scripts/sim-ros.sh" "$@" ;;
  ros-sim:start) compose up -d ;;
  ros-sim:stop) compose down ;;
  ros-sim:status) compose ps ;;
  ros-sim:shell) exec "$repo_root/scripts/sim-ros.sh" "$@" ;;
  *)
    echo 'Usage: llama {start|stop|status|logs}'
    echo '       limo-sim {start [--headless]|stop|status|wait|logs|check [--motion]|rviz|teleop|shell [command...]}'
    echo '       ros-sim {start|stop|status|shell [command...]}'
    exit 2
    ;;
esac

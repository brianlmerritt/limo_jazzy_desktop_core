#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f /opt/ros/humble/setup.bash ]]; then
  echo "Run this check inside the Humble development container." >&2
  exit 1
fi

if [[ "${LIMO_STARTUP_MODE:-}" != "passive" ]]; then
  echo "LIMO_STARTUP_MODE must be passive for this system check." >&2
  exit 1
fi

if [[ ! -c "${LIMO_SERIAL_PORT:-}" ]]; then
  echo "LIMO serial device is unavailable: ${LIMO_SERIAL_PORT:-unset}" >&2
  exit 1
fi

set +u
source /opt/ros/humble/setup.bash
source /workspace/install/limo_msgs/share/limo_msgs/local_setup.bash
source /workspace/install/limo_base/share/limo_base/local_setup.bash
set -u

check_dir="$(mktemp -d)"
launch_log="${check_dir}/limo-base.log"
node_info="${check_dir}/node-info.txt"
launch_pid=""

stop_launch() {
  local forced_stop=false
  if [[ -n "$launch_pid" ]] && kill -0 "$launch_pid" 2>/dev/null; then
    kill -INT "$launch_pid" 2>/dev/null || true
    for _ in $(seq 1 30); do
      kill -0 "$launch_pid" 2>/dev/null || break
      sleep 0.1
    done
    if kill -0 "$launch_pid" 2>/dev/null; then
      forced_stop=true
      kill -TERM "$launch_pid" 2>/dev/null || true
      for _ in $(seq 1 20); do
        kill -0 "$launch_pid" 2>/dev/null || break
        sleep 0.1
      done
    fi
    if kill -0 "$launch_pid" 2>/dev/null; then
      kill -KILL "$launch_pid" 2>/dev/null || true
    fi
    wait "$launch_pid" 2>/dev/null || true
  fi
  launch_pid=""
  [[ "$forced_stop" == "false" ]]
}

cleanup() {
  stop_launch || true
  rm -rf "$check_dir"
}
trap cleanup EXIT

(
  trap - INT TERM
  exec ros2 launch limo_base limo_base.launch.py startup_mode:=passive
) >"$launch_log" 2>&1 &
launch_pid="$!"

node_ready=false
for _ in $(seq 1 50); do
  if ros2 node list 2>/dev/null | grep -Fxq /limo_base_node; then
    node_ready=true
    break
  fi
  if ! kill -0 "$launch_pid" 2>/dev/null; then
    break
  fi
  sleep 0.2
done

if [[ "$node_ready" != "true" ]]; then
  echo "[FAIL] Passive limo_base node did not become ready." >&2
  sed -n '1,160p' "$launch_log" >&2
  exit 1
fi

ros2 node info /limo_base_node >"$node_info"
if grep -Fq /cmd_vel "$node_info"; then
  echo "[FAIL] Passive node unexpectedly exposes /cmd_vel." >&2
  exit 1
fi

startup_mode="$(ros2 param get /limo_base_node startup_mode)"
if [[ "$startup_mode" != "String value is: passive" ]]; then
  echo "[FAIL] Passive startup parameter was not applied: ${startup_mode}" >&2
  exit 1
fi

for topic in /limo_status /imu /wheel/odom; do
  sample_file="${check_dir}/${topic//\//_}.txt"
  if ! timeout 8s ros2 topic echo --once "$topic" >"$sample_file"; then
    echo "[FAIL] No message received from ${topic}." >&2
    sed -n '1,160p' "$launch_log" >&2
    exit 1
  fi
  echo "[PASS] Received ${topic}."
  sed -n '1,16p' "$sample_file"
done

status_sample="${check_dir}/_limo_status.txt"
if ! grep -Fxq "error_code: 0" "$status_sample"; then
  echo "[FAIL] LIMO reports a nonzero chassis error code." >&2
  exit 1
fi
if grep -Eq '^battery_voltage: 0([.]0+)?$' "$status_sample"; then
  echo "[FAIL] LIMO reports no battery voltage." >&2
  exit 1
fi
echo "[PASS] Chassis status reports no error and a nonzero battery voltage."

if grep -Fq "enableCommandedMode" "$launch_log"; then
  echo "[FAIL] Passive startup called enableCommandedMode." >&2
  exit 1
fi

if ! stop_launch; then
  echo "[FAIL] Passive node required forced shutdown." >&2
  sed -n '1,200p' "$launch_log" >&2
  exit 1
fi

if grep -Fq "process has died" "$launch_log"; then
  echo "[FAIL] Passive node did not shut down cleanly." >&2
  sed -n '1,200p' "$launch_log" >&2
  exit 1
fi

echo "[PASS] Passive LIMO system check completed without a command interface."

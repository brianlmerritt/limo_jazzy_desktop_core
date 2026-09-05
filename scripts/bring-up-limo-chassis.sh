#!/usr/bin/env bash
# Build and start only the chassis; passive diagnostics remain opt-in.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose=(docker compose --project-directory "$ROOT" -f "${ROOT}/compose.yaml")
startup_mode="${1:-commanded}"
[[ $# -le 1 && "$startup_mode" =~ ^(passive|commanded)$ ]] || {
  echo "Usage: $0 [commanded|passive]" >&2
  exit 2
}

# Works after docker compose down; the Docker daemon must be running.
"${compose[@]}" up -d --no-deps dev

# Build failures leave the existing hardware services untouched.
"${compose[@]}" exec -T dev ./scripts/build.sh --packages-up-to limo_base
"${compose[@]}" stop limo-base
completed=false
cleanup() {
  if [[ "$completed" != true ]]; then
    "${compose[@]}" stop limo-base || true
    echo "Chassis validation/startup failed; chassis service remains stopped." >&2
  fi
}
trap cleanup EXIT
# Run the hardware diagnostic only when explicitly requesting passive mode.
if [[ "$startup_mode" == passive ]]; then
  # Keep discovery separate from the sensor services and old ROS CLI daemons.
  "${compose[@]}" exec -T -e LIMO_STARTUP_MODE=passive -e ROS_DOMAIN_ID=174 \
    dev timeout --signal=INT --kill-after=10s 120s ./scripts/check-limo-system.sh
fi
LIMO_BASE_STARTUP_MODE="$startup_mode" "${compose[@]}" --profile robot \
  up -d --no-deps --force-recreate limo-base
ready=false
for _ in $(seq 1 20); do
  if [[ "$("${compose[@]}" exec -T limo-base ./scripts/ros2.sh param get \
      /limo_base_node startup_mode 2>/dev/null || true)" == "String value is: ${startup_mode}" ]]; then
    ready=true
    break
  fi
  sleep 0.5
done
[[ "$ready" == true ]] || { echo "Detached ${startup_mode} chassis did not become ready." >&2; exit 1; }
node_info="$("${compose[@]}" exec -T limo-base ./scripts/ros2.sh node info /limo_base_node)"
if [[ "$startup_mode" == passive && "$node_info" == *'/cmd_vel'* ]]; then
  echo "Passive chassis unexpectedly exposes /cmd_vel." >&2
  exit 1
fi
if [[ "$startup_mode" == commanded && "$node_info" != *'/cmd_vel'* ]]; then
  echo "Commanded chassis is missing its /cmd_vel subscription." >&2
  exit 1
fi
completed=true
echo "Jazzy chassis started detached in ${startup_mode} mode. Sensors were not restarted."
echo "Now: ./scripts/ros-shell.sh"
echo "Next: migrate the sensor drivers before using full robot bringup."

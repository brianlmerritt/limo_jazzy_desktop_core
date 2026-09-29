#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICES_TOUCHED=false

show_failure() {
  local exit_code=$?

  if ((exit_code != 0)) && [[ "$SERVICES_TOUCHED" == true ]]; then
    echo "Robot/sensor bringup failed; recent logs follow." >&2
    docker compose logs --tail=100 limo-base ydlidar realsense >&2 || true
    docker compose --profile robot --profile sensors stop limo-base ydlidar realsense exploration navigation mapping robot-transforms >/dev/null 2>&1 || true
    echo "Stopped chassis and sensor services after failed bringup." >&2
  fi

  exit "$exit_code"
}

trap show_failure EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

cd "$ROOT"

if [[ $# -gt 0 ]]; then
  echo "Usage: $0  (run on the host; brings up the chassis and configured sensors)" >&2
  exit 2
fi
if [[ -f /opt/ros/${ROS_DISTRO:-jazzy}/setup.bash && "$ROOT" == /workspace ]]; then
  echo "Run this bringup script from the host repository, not inside Docker." >&2
  exit 2
fi

echo "[1/9] Validating configuration and installing sensor access rules..."
./scripts/setup.sh validate
./scripts/configure-sensor-udev.sh install all

echo "[2/9] Checking devices and configuring Compose..."
./scripts/configure-host-env.sh
source "$(dirname "${BASH_SOURCE[0]}")/robot-namespace.sh"

echo "[3/9] Stopping previous chassis and sensor services before rebuilding..."
SERVICES_TOUCHED=true
docker compose --profile robot --profile sensors stop limo-base ydlidar realsense exploration navigation mapping robot-transforms

echo "[4/9] Building the current development image..."
docker compose build dev

echo "[5/9] Starting the development container..."
docker compose up -d --force-recreate dev

echo "[6/9] Building chassis and exploration packages from the current checkout..."
docker compose exec -T dev \
  ./scripts/build.sh --packages-up-to limo_base explore_lite

echo "[7/9] Building drivers selected by enabled sensor devices..."
./scripts/setup.sh build-drivers

echo "[8/9] Starting configured sensor services..."
./scripts/setup.sh start-drivers

echo "[9/9] Starting and checking commanded chassis bringup..."
LIMO_BASE_STARTUP_MODE=commanded docker compose --profile robot up -d --force-recreate limo-base

node_found=false
for _ in {1..20}; do
  if docker compose exec -T dev ./scripts/ros2.sh node list 2>/dev/null \
      | grep -Fxq "${ROBOT_PREFIX}/limo_base_node"; then
    node_found=true
    break
  fi
  sleep 1
done

if [[ "$node_found" != true ]]; then
  echo "Timed out waiting for ${ROBOT_PREFIX}/limo_base_node." >&2
  false
fi

# DDS may discover the node before its endpoints. Wait for the command
# subscription instead of treating a transient "Unknown topic" as failure.
cmd_vel_ready=false
cmd_vel_info=""
for _ in {1..20}; do
  if cmd_vel_info="$(docker compose exec -T dev ./scripts/ros2.sh topic info "${ROBOT_PREFIX}/cmd_vel" 2>/dev/null)"; then
    if ! grep -Fxq "Publisher count: 0" <<<"$cmd_vel_info"; then
      echo "Unexpected ${ROBOT_PREFIX}/cmd_vel publisher detected." >&2
      false
    fi
    if grep -Fxq "Subscription count: 1" <<<"$cmd_vel_info"; then
      cmd_vel_ready=true
      break
    fi
  fi
  sleep 1
done
echo "$cmd_vel_info"
if [[ "$cmd_vel_ready" != true ]]; then
  echo "Timed out waiting for one ${ROBOT_PREFIX}/cmd_vel subscriber." >&2
  false
fi

limo_status="$(
  docker compose exec -T dev timeout 10 \
    ./scripts/ros2.sh topic echo --once "${ROBOT_PREFIX}/limo_status"
)"
echo "$limo_status"

if ! grep -Fxq "control_mode: 1" <<<"$limo_status"; then
  echo "The chassis did not report commanded control mode." >&2
  false
fi

if ! grep -Fxq "error_code: 0" <<<"$limo_status"; then
  echo "The chassis reported an error." >&2
  false
fi

docker compose --profile robot up -d --force-recreate robot-transforms

trap - EXIT INT TERM

echo "LIMO base is ready to receive ${ROBOT_PREFIX}/cmd_vel; configured sensor services have been started."
echo "Open a ROS-ready shell with: ./scripts/ros-shell.sh"
echo "No velocity command was published."
echo "Stop all robot services with: ./scripts/bring_down_limo_base.sh"

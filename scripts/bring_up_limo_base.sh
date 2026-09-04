#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROBOT_STARTED=false

show_failure() {
  local exit_code=$?

  if [[ "$ROBOT_STARTED" == true ]]; then
    echo "LIMO base bringup failed; recent logs follow." >&2
    docker compose logs --tail=100 limo-base >&2 || true
    docker compose stop limo-base >/dev/null 2>&1 || true
    echo "Stopped the limo-base service after the failed readiness check." >&2
  fi

  exit "$exit_code"
}

trap show_failure ERR

cd "$ROOT"

echo "[1/6] Checking the LIMO device and configuring Compose..."
./scripts/configure-host-env.sh

echo "[2/6] Stopping any previous LIMO base service..."
docker compose stop limo-base

echo "[3/6] Building the current development image..."
docker compose build dev

echo "[4/6] Starting the development container..."
docker compose up -d --force-recreate dev

echo "[5/6] Building limo_base from the current checkout..."
docker compose exec -T dev \
  ./scripts/build.sh --packages-up-to limo_base

echo "[6/6] Starting and checking commanded chassis bringup..."
docker compose --profile robot up -d --force-recreate limo-base
ROBOT_STARTED=true

node_found=false
for _ in {1..20}; do
  if docker compose exec -T dev ./scripts/ros2.sh node list 2>/dev/null \
      | grep -Fxq "/limo_base_node"; then
    node_found=true
    break
  fi
  sleep 1
done

if [[ "$node_found" != true ]]; then
  echo "Timed out waiting for /limo_base_node." >&2
  false
fi

cmd_vel_info="$(
  docker compose exec -T dev ./scripts/ros2.sh topic info /cmd_vel
)"
echo "$cmd_vel_info"

if ! grep -Fxq "Publisher count: 0" <<<"$cmd_vel_info"; then
  echo "Unexpected /cmd_vel publisher detected." >&2
  false
fi

if ! grep -Fxq "Subscription count: 1" <<<"$cmd_vel_info"; then
  echo "Expected one /cmd_vel subscriber." >&2
  false
fi

limo_status="$(
  docker compose exec -T dev timeout 10 \
    ./scripts/ros2.sh topic echo --once /limo_status
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

trap - ERR

echo "LIMO base is running and ready to receive /cmd_vel."
echo "No velocity command was published."
echo "Stop it with: docker compose stop limo-base"

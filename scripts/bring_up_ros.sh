#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT"
if [[ -f /opt/ros/humble/setup.bash && "$ROOT" == /workspace ]]; then
  echo "Run this script from the host repository, not inside Docker." >&2
  exit 2
fi

echo "Configuring Docker for ROS 2 without LIMO hardware..."
./scripts/configure-host-env.sh --without-limo

echo "Building the development image..."
docker compose build dev

echo "Starting the ROS 2 development container..."
docker compose up -d --force-recreate dev

echo "ROS 2 environment is running without the robot service."
echo "Open a ROS-ready shell with: ./scripts/ros-shell.sh"
echo "Build workspace packages with: docker compose exec -T dev ./scripts/build.sh"
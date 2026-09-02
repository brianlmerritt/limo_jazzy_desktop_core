#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DEV_USER="$(id -un)"
DEV_UID="$(id -u)"
DEV_GID="$(id -g)"

cat > "${ROOT}/.env" <<ENVEOF
DEV_USER=${DEV_USER}
DEV_UID=${DEV_UID}
DEV_GID=${DEV_GID}
ENVEOF

echo "Created ${ROOT}/.env"
echo "DEV_USER=${DEV_USER}"
echo "DEV_UID=${DEV_UID}"
echo "DEV_GID=${DEV_GID}"

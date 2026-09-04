#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="/workspace/config/config.yaml"
SCHEMA="/workspace/config/config.schema.json"
COMMAND="${1:-check}"

usage() {
  cat <<'EOF'
Usage: scripts/setup.sh COMMAND

Commands:
  validate       Validate config/config.yaml against its schema.
  check          Check host prerequisites, sources, and devices.
  plan           Show missing prerequisites without applying changes.
  check-sources  Check configured Git submodules and revisions.
  check-devices  Check configured device paths and select ROS values.

All commands are read-only. This script does not install host packages,
write udev rules, or change Git state.
EOF
}

case "$COMMAND" in
  validate|check|plan|check-sources|check-devices)
    ;;
  -h|--help|help)
    usage
    exit 0
    ;;
  *)
    echo "Unknown command: ${COMMAND}" >&2
    usage >&2
    exit 2
    ;;
esac

if ! command -v docker >/dev/null 2>&1; then
  echo "[FAIL] Docker is required to run the configuration validator." >&2
  echo "[INFO] No host Python virtual environment is required or created." >&2
  exit 1
fi

export DEV_USER="${DEV_USER:-$(id -un)}"
export DEV_UID="${DEV_UID:-$(id -u)}"
export DEV_GID="${DEV_GID:-$(id -g)}"

compose=(docker compose --project-directory "$ROOT" -f "${ROOT}/compose.yaml")
configurator=("${compose[@]}" run --rm --no-deps configurator)

"${compose[@]}" build configurator

if [[ "$COMMAND" == "validate" ]]; then
  "${configurator[@]}" validate --config "$CONFIG" --schema "$SCHEMA"
  exit 0
fi

if [[ "$COMMAND" == "check" || "$COMMAND" == "plan" ]]; then
  mapfile -t host_arguments < <(
    "${configurator[@]}" host-arguments --config "$CONFIG" --schema "$SCHEMA"
  )

  host_status=0
  "${ROOT}/scripts/bootstrap-host.sh" \
    --mode "$COMMAND" \
    "${host_arguments[@]}" || host_status=$?

  config_status=0
  "${configurator[@]}" check \
    --config "$CONFIG" \
    --schema "$SCHEMA" \
    --workspace /workspace \
    --device-root /host/dev \
    --os-release /host/etc/os-release || config_status=$?

  if ((host_status != 0 || config_status != 0)); then
    exit 1
  fi
  exit 0
fi

"${configurator[@]}" "$COMMAND" \
  --config "$CONFIG" \
  --schema "$SCHEMA" \
  --workspace /workspace \
  --device-root /host/dev \
  --os-release /host/etc/os-release

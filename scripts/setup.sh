#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="/workspace/config/config.yaml"
SCHEMA="/workspace/config/config.schema.json"
COMMAND="${1:-check}"

usage() {
  cat <<'EOF'
Usage: scripts/setup.sh COMMAND

  validate          Validate config/config.yaml and driver references.
  check             Check host prerequisites, selected sources, and devices.
  plan              Report missing prerequisites without applying changes.
  check-sources     Check selected Git submodules and exact revisions.
  check-devices     Check enabled device paths and ROS values.
  plan-sources      Print a guarded source update script; no Git changes.
  apply-sources     Apply configured submodules within the agreed parent folders.
  build-drivers     Build enabled sensor drivers inside the running dev container.
  start-drivers     Refresh device discovery and start enabled sensor services.
  device-env        Print validated inputs for host device discovery.

apply-sources changes Git state; it never commits, pushes, resets, or cleans.
Agents may apply within drivers/ and src/ros2_devices/. Explicit state: absent
removes a checkout and its Git cache after preflight. Other Git work stays owner-managed.
Builds and startup never apply sources.
EOF
}

case "$COMMAND" in
  validate|check|plan|check-sources|check-devices|plan-sources|apply-sources|build-drivers|start-drivers|device-env|sensor-udev-env) ;;
  -h|--help|help) usage; exit 0 ;;
  *) echo "Unknown command: ${COMMAND}" >&2; usage >&2; exit 2 ;;
esac
[[ $# -le 1 ]] || { usage >&2; exit 2; }
command -v docker >/dev/null || { echo "Docker is required; no host Python packages are installed." >&2; exit 1; }

export DEV_USER="${DEV_USER:-$(id -un)}"
export DEV_UID="${DEV_UID:-$(id -u)}"
export DEV_GID="${DEV_GID:-$(id -g)}"
compose=(docker compose --project-directory "$ROOT" -f "${ROOT}/compose.yaml")
configurator=("${compose[@]}" run --rm -T --no-deps configurator)
# Keep stdout machine-readable for generated scripts and environment inputs.
"${compose[@]}" build configurator >&2

run_config() {
  local operation="$1"
  shift
  "${configurator[@]}" "$operation" --config "$CONFIG" --schema "$SCHEMA" "$@"
}

case "$COMMAND" in
  validate|device-env|sensor-udev-env)
    run_config "$COMMAND"
    exit 0
    ;;
  plan-sources|apply-sources)
    source_plan="$(mktemp)"
    trap 'rm -f "$source_plan"' EXIT
    run_config plan-sources --workspace /workspace > "$source_plan"
    bash -n "$source_plan"
    if [[ "$COMMAND" == "plan-sources" ]]; then
      cat "$source_plan"
    else
      bash "$source_plan" "$ROOT"
      run_config check-sources --workspace /workspace
    fi
    exit 0
    ;;
  build-drivers)
    run_config check-sources --workspace /workspace
    service="$(run_config driver-service)"
    build_plan="$(mktemp)"
    trap 'rm -f "$build_plan"' EXIT
    run_config build-driver-script > "$build_plan"
    bash -n "$build_plan"
    "${compose[@]}" exec -T "$service" bash -s < "$build_plan"
    exit 0
    ;;
  start-drivers)
    selected_services="$(run_config driver-services)"
    if [[ -z "$selected_services" ]]; then
      "${compose[@]}" --profile sensors stop ydlidar realsense
      echo "No enabled sensor drivers."
      exit 0
    fi
    expected_build="$(run_config driver-build-id)"
    if [[ ! -r "${ROOT}/.deps/driver-build.sha256" ]] ||
        [[ "$(<"${ROOT}/.deps/driver-build.sha256")" != "$expected_build" ]]; then
      echo "Driver build is missing or stale; run ./scripts/setup.sh build-drivers first." >&2
      exit 1
    fi
    "${ROOT}/scripts/configure-host-env.sh"
    available_ydlidar=false
    available_realsense=false
    while IFS='=' read -r key value; do
      case "$key" in
        YDLIDAR_AVAILABLE) available_ydlidar="$value" ;;
        REALSENSE_AVAILABLE) available_realsense="$value" ;;
      esac
    done < "${ROOT}/.env"
    services=()
    while IFS= read -r sensor; do
      availability="available_${sensor}"
      if [[ "${!availability}" == true ]]; then
        services+=("$sensor")
      else
        echo "Omitting unavailable optional sensor: $sensor"
      fi
    done <<< "$selected_services"
    # Stop previously running disabled services before starting the selected ones.
    for sensor in ydlidar realsense; do
      if [[ " ${services[*]} " != *" ${sensor} "* ]]; then
        "${compose[@]}" --profile sensors stop "$sensor"
      fi
    done
    ((${#services[@]} > 0)) || exit 0
    # Recreate dev as its environment/device mappings may have changed too.
    service="$(run_config driver-service)"
    "${compose[@]}" up -d --force-recreate "$service"
    "${compose[@]}" --profile sensors up -d --force-recreate "${services[@]}"
    exit 0
    ;;
esac

if [[ "$COMMAND" == "check" || "$COMMAND" == "plan" ]]; then
  host_output="$(run_config host-arguments)"
  mapfile -t host_arguments <<< "$host_output"
  host_status=0
  "${ROOT}/scripts/bootstrap-host.sh" --mode "$COMMAND" "${host_arguments[@]}" || host_status=$?
  config_status=0
  run_config check --workspace /workspace --device-root /host/dev \
    --os-release /host/etc/os-release || config_status=$?
  ((host_status == 0 && config_status == 0))
  exit
fi
run_config "$COMMAND" --workspace /workspace --device-root /host/dev \
  --os-release /host/etc/os-release

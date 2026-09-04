#!/usr/bin/env bash
set -euo pipefail

EXPECTED_UBUNTU=""
EXPECTED_ARCHITECTURE=""
L4T_REQUIRED="false"
NVIDIA_RUNTIME_REQUIRED="false"
MODE="check"
REQUIRED_COMMANDS=()
REQUIRED_PACKAGES=()
REQUIRED_KERNEL_MODULES=()
REQUIRED_GROUPS=()

usage() {
  cat <<'EOF'
Usage: bootstrap-host.sh [options]

Read-only host prerequisite checker. Options are normally generated from
config/config.yaml by scripts/setup.sh.

Options:
  --mode check|plan
  --expected-ubuntu VERSION
  --expected-architecture ARCH
  --l4t-required true|false
  --nvidia-runtime-required true|false
  --require-command COMMAND
  --require-package PACKAGE
  --require-kernel-module MODULE
  --require-group GROUP
EOF
}

while (($# > 0)); do
  case "$1" in
    --mode)
      MODE="$2"
      shift 2
      ;;
    --expected-ubuntu)
      EXPECTED_UBUNTU="$2"
      shift 2
      ;;
    --expected-architecture)
      EXPECTED_ARCHITECTURE="$2"
      shift 2
      ;;
    --l4t-required)
      L4T_REQUIRED="$2"
      shift 2
      ;;
    --nvidia-runtime-required)
      NVIDIA_RUNTIME_REQUIRED="$2"
      shift 2
      ;;
    --require-command)
      REQUIRED_COMMANDS+=("$2")
      shift 2
      ;;
    --require-package)
      REQUIRED_PACKAGES+=("$2")
      shift 2
      ;;
    --require-kernel-module)
      REQUIRED_KERNEL_MODULES+=("$2")
      shift 2
      ;;
    --require-group)
      REQUIRED_GROUPS+=("$2")
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "$MODE" != "check" && "$MODE" != "plan" ]]; then
  echo "--mode must be 'check' or 'plan'." >&2
  exit 2
fi

failures=0

pass() {
  echo "[PASS] $*"
}

fail() {
  echo "[FAIL] $*" >&2
  failures=$((failures + 1))
}

if [[ -r /etc/os-release ]]; then
  # shellcheck disable=SC1091
  source /etc/os-release
  if [[ "${ID:-}" == "ubuntu" && "${VERSION_ID:-}" == "$EXPECTED_UBUNTU" ]]; then
    pass "Host OS is Ubuntu ${VERSION_ID}."
  else
    fail "Expected Ubuntu ${EXPECTED_UBUNTU}; found ${ID:-unknown} ${VERSION_ID:-unknown}."
  fi
else
  fail "Cannot read /etc/os-release."
fi

host_architecture="$(uname -m)"
if [[ "$host_architecture" == "$EXPECTED_ARCHITECTURE" ]]; then
  pass "Host architecture is ${host_architecture}."
else
  fail "Expected architecture ${EXPECTED_ARCHITECTURE}; found ${host_architecture}."
fi

if [[ "$L4T_REQUIRED" == "true" ]]; then
  if [[ -r /etc/nv_tegra_release ]]; then
    pass "NVIDIA L4T release metadata is available."
  else
    fail "Expected /etc/nv_tegra_release on the Jetson host."
  fi
fi

for required_command in "${REQUIRED_COMMANDS[@]}"; do
  if command -v "$required_command" >/dev/null 2>&1; then
    pass "Host command '${required_command}' is available."
  else
    fail "Host command '${required_command}' is missing."
  fi
done

for required_package in "${REQUIRED_PACKAGES[@]}"; do
  package_status="$(dpkg-query --show --showformat='${db:Status-Status}' "$required_package" 2>/dev/null || true)"
  if [[ "$package_status" == "installed" ]]; then
    pass "Host package '${required_package}' is installed."
  else
    fail "Host package '${required_package}' is missing."
  fi
done

for required_module in "${REQUIRED_KERNEL_MODULES[@]}"; do
  module_path="/sys/module/${required_module//-/_}"
  if [[ -d "$module_path" ]]; then
    pass "Kernel module '${required_module}' is loaded."
  else
    fail "Kernel module '${required_module}' is not loaded."
  fi
done

host_groups="$(id -nG)"
for required_group in "${REQUIRED_GROUPS[@]}"; do
  if tr ' ' '\n' <<<"$host_groups" | grep -Fxq "$required_group"; then
    pass "User $(id -un) belongs to '${required_group}'."
  else
    fail "User $(id -un) does not belong to '${required_group}'."
  fi
done

if [[ "$NVIDIA_RUNTIME_REQUIRED" == "true" ]]; then
  if ! command -v docker >/dev/null 2>&1; then
    fail "Cannot inspect NVIDIA runtime because Docker is unavailable."
  elif docker info --format '{{json .Runtimes}}' 2>/dev/null | grep -q 'nvidia'; then
    pass "Docker reports the NVIDIA runtime."
  else
    fail "Docker does not report an NVIDIA runtime, or the daemon is inaccessible."
  fi
fi

if ((failures > 0)); then
  if [[ "$MODE" == "plan" ]]; then
    echo "[INFO] ${failures} host prerequisite change(s) are needed."
    echo "[INFO] No host changes were applied. Add a documented, idempotent action before automating each change."
  fi
  exit 1
fi

pass "All configured host prerequisites are satisfied."

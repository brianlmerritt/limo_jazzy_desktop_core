#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE="${ROOT}/config/robot/99-limo-serial.rules"
TARGET="/etc/udev/rules.d/99-limo-serial.rules"
COMMAND="${1:-check}"

usage() {
  cat <<'EOF'
Usage: scripts/configure-limo-udev.sh check|install|remove

  check    Compare the tracked rule with the installed host rule.
  install  Idempotently install the rule and reload udev.
  remove   Roll back an unchanged installed rule and reload udev.

Installation and removal use sudo. Power up the LIMO chassis before verifying
serial communication; the native Jetson device is /dev/ttyTHS1 and the rule
creates /dev/ttylimo.
EOF
}

reload_udev() {
  sudo udevadm control --reload-rules
  sudo udevadm trigger --action=add --sysname-match=ttyTHS1
}

check_rule() {
  if [[ ! -f "$TARGET" ]]; then
    echo "[FAIL] LIMO udev rule is not installed at ${TARGET}." >&2
    return 1
  fi
  if ! cmp -s "$SOURCE" "$TARGET"; then
    echo "[FAIL] Installed LIMO udev rule differs from ${SOURCE}." >&2
    return 1
  fi
  echo "[PASS] LIMO udev rule matches ${SOURCE}."
}

case "$COMMAND" in
  check)
    check_rule
    ;;
  install)
    if [[ -f "$TARGET" ]] && cmp -s "$SOURCE" "$TARGET"; then
      echo "[PASS] LIMO udev rule is already installed."
    elif [[ -e "$TARGET" ]]; then
      echo "[FAIL] Refusing to overwrite a differing host rule at ${TARGET}." >&2
      echo "[INFO] Review the existing rule and preserve or remove it explicitly before retrying." >&2
      exit 1
    else
      sudo install --owner=root --group=root --mode=0644 "$SOURCE" "$TARGET"
      echo "[PASS] Installed ${TARGET}."
    fi
    reload_udev
    if [[ -e /dev/ttylimo ]]; then
      echo "[PASS] /dev/ttylimo is available."
    else
      echo "[INFO] /dev/ttylimo is not present yet; power the LIMO chassis and re-run the device check."
    fi
    ;;
  remove)
    if [[ ! -e "$TARGET" ]]; then
      echo "[PASS] LIMO udev rule is already absent."
      exit 0
    fi
    if ! cmp -s "$SOURCE" "$TARGET"; then
      echo "[FAIL] Refusing to remove a host rule that differs from ${SOURCE}." >&2
      exit 1
    fi
    sudo rm -- "$TARGET"
    reload_udev
    echo "[PASS] Removed ${TARGET}."
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    echo "Unknown command: ${COMMAND}" >&2
    usage >&2
    exit 2
    ;;
esac

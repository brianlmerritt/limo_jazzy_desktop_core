#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMMAND="${1:-check}"
SELECTION="${2:-all}"
case "$COMMAND" in
  check|install|remove) ;;
  *) echo "Usage: $0 check|install|remove [all|ydlidar|realsense]" >&2; exit 2 ;;
esac
case "$SELECTION" in
  all) sensors=(ydlidar realsense) ;;
  ydlidar|realsense) sensors=("$SELECTION") ;;
  *) echo "Unknown sensor: $SELECTION" >&2; exit 2 ;;
esac
inputs="$(mktemp)"
work="$(mktemp -d)"
trap 'rm -f "$inputs"; rm -rf "$work"' EXIT
"${ROOT}/scripts/setup.sh" sensor-udev-env > "$inputs"
source "$inputs"
state="${ROOT}/.deps/udev"
selected=()

# Preflight all targets before changing any host rule.
for sensor in "${sensors[@]}"; do
  prefix="${sensor^^}"
  enabled="${prefix}_ENABLED"
  if [[ "$COMMAND" != remove && "${!enabled}" != true ]]; then
    echo "Skipping disabled sensor: $sensor"
    continue
  fi
  target_name="${prefix}_RULE_TARGET"
  source_name="${prefix}_RULE_SOURCE"
  content_name="${prefix}_RULE_CONTENT"
  [[ -n "${!target_name:-}" ]] || { echo "Retain device configuration until its rule is removed." >&2; exit 1; }
  target="${!target_name}"
  printf '%s' "${!content_name}" > "${work}/${sensor}.rules"
  if [[ -f "${state}/${sensor}.target" && "$(<"${state}/${sensor}.target")" != "$target" ]]; then
    echo "Rule target changed for $sensor; restore the previous target and remove its rule first." >&2
    exit 1
  fi
  if [[ "$COMMAND" == check ]]; then
    cmp -s "${work}/${sensor}.rules" "$target" || { echo "Rule missing or stale: $target; run install." >&2; exit 1; }
    echo "[PASS] $sensor host rule matches config/config.yaml."
    continue
  fi
  if [[ -e "$target" ]] &&
      ! cmp -s "$target" "${work}/${sensor}.rules" &&
      ! cmp -s "$target" "${state}/${sensor}.rules" &&
      ! cmp -s "$target" "${ROOT}/${!source_name}"; then
    echo "Refusing to change externally modified rule: $target" >&2
    exit 1
  fi
  selected+=("$sensor")
done
[[ "$COMMAND" != check ]] || exit 0
((${#selected[@]} > 0)) || exit 0
mkdir -p "$state"
for sensor in "${selected[@]}"; do
  target_name="${sensor^^}_RULE_TARGET"
  target="${!target_name}"
  if [[ "$COMMAND" == install ]]; then
    # Save the desired rule before installation so an interrupted apply can be retried.
    if [[ -f "$target" ]]; then
      cp -- "$target" "${state}/${sensor}.rules"
    fi
    printf '%s\n' "$target" > "${state}/${sensor}.target"
    sudo install --owner=root --group=root --mode=0644 "${work}/${sensor}.rules" "$target"
    cp -- "${work}/${sensor}.rules" "${state}/${sensor}.rules"
    echo "Installed $target"
  else
    sudo rm -f -- "$target"
    rm -f -- "${state}/${sensor}.rules" "${state}/${sensor}.target"
    echo "Removed $target"
  fi
done
sudo udevadm control --reload-rules
sudo udevadm trigger --action=add --subsystem-match=tty
sudo udevadm trigger --action=change --subsystem-match=usb
sudo udevadm trigger --action=change --subsystem-match=hidraw
sudo udevadm settle
echo "Sensor rules updated. Reconnect sensors if access has not refreshed."

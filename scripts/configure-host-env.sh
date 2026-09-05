#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
config_inputs="$(mktemp)"
env_output="$(mktemp "${ROOT}/.env.XXXXXX")"
trap 'rm -f "$config_inputs" "$env_output"' EXIT
"${ROOT}/scripts/setup.sh" device-env > "$config_inputs"
# Generated shell assignments use shlex.quote after schema validation.
source "$config_inputs"

LIMO_SERIAL_HOST_DEVICE=/dev/null
LIMO_SERIAL_PORT="${LIMO_CONTAINER_PATH:-/dev/ttylimo}"
LIMO_SERIAL_BAUD="${LIMO_BAUD:-460800}"
YDLIDAR_HOST_DEVICE=/dev/null
YDLIDAR_AVAILABLE=false
REALSENSE_USB_HOST_DEVICE=/dev/null
REALSENSE_USB_CONTAINER_DEVICE=/dev/bus/usb/000/000
REALSENSE_AVAILABLE=false
REALSENSE_SERIAL="${REALSENSE_SERIAL:-}"

select_serial() {
  local candidates="$1" candidate resolved selected=""
  while IFS= read -r candidate; do
    [[ -c "$candidate" ]] || continue
    resolved="$(readlink -f "$candidate")"
    if [[ -n "$selected" && "$selected" != "$resolved" ]]; then
      echo "Ambiguous serial devices: ${selected} and ${resolved}" >&2
      return 1
    fi
    selected="$resolved"
  done <<< "$candidates"
  printf '%s' "$selected"
}

if [[ "$LIMO_ENABLED" == true ]]; then
  LIMO_SERIAL_HOST_DEVICE="$(select_serial "$LIMO_CANDIDATES")"
  [[ -n "$LIMO_SERIAL_HOST_DEVICE" ]] || {
    echo "LIMO UART unavailable. Power the chassis and check config/config.yaml." >&2
    exit 1
  }
fi
if [[ "$YDLIDAR_ENABLED" == true ]]; then
  YDLIDAR_HOST_DEVICE="$(select_serial "$YDLIDAR_CANDIDATES")"
  if [[ -n "$YDLIDAR_HOST_DEVICE" ]]; then
    # Confirm identity even when a pre-existing alias happens to resolve.
    properties="$(udevadm info --query=property --name="$YDLIDAR_HOST_DEVICE")"
    for expected in "ID_VENDOR_ID=$YDLIDAR_VENDOR_ID" "ID_MODEL_ID=$YDLIDAR_PRODUCT_ID" "ID_SERIAL_SHORT=$YDLIDAR_SERIAL"; do
      if [[ $'\n'"$properties"$'\n' != *$'\n'"$expected"$'\n'* ]]; then
        echo "YDLIDAR identity mismatch: expected $expected" >&2
        exit 1
      fi
    done
    YDLIDAR_AVAILABLE=true
  else
    YDLIDAR_HOST_DEVICE=/dev/null
    if [[ "$YDLIDAR_REQUIRED" == true ]]; then
      echo "Required YDLIDAR unavailable; check its identity and udev rule." >&2
      exit 1
    fi
  fi
fi
if [[ "$REALSENSE_ENABLED" == true ]]; then
  for usb_device in /sys/bus/usb/devices/*; do
    [[ -r "${usb_device}/idVendor" && -r "${usb_device}/idProduct" && -r "${usb_device}/serial" ]] || continue
    [[ "$(<"${usb_device}/idVendor")" == "$REALSENSE_VENDOR_ID" &&
       "$(<"${usb_device}/idProduct")" == "$REALSENSE_PRODUCT_ID" &&
       "$(<"${usb_device}/serial")" == "$REALSENSE_SERIAL" ]] || continue
    [[ "$REALSENSE_AVAILABLE" == false ]] || { echo "Ambiguous RealSense identity" >&2; exit 1; }
    printf -v REALSENSE_USB_HOST_DEVICE '/dev/bus/usb/%03d/%03d' \
      "$((10#$(<"${usb_device}/busnum")))" "$((10#$(<"${usb_device}/devnum")))"
    [[ -c "$REALSENSE_USB_HOST_DEVICE" ]] || { echo "RealSense USB node disappeared; retry." >&2; exit 1; }
    REALSENSE_USB_CONTAINER_DEVICE="$REALSENSE_USB_HOST_DEVICE"
    REALSENSE_AVAILABLE=true
  done
  if [[ "$REALSENSE_AVAILABLE" == false && "$REALSENSE_REQUIRED" == true ]]; then
    echo "Required RealSense unavailable; check its configured USB identity." >&2
    exit 1
  fi
fi

# Values consumed by Compose must be single-line and contain no interpolation.
write_env() {
  local name="$1" value="$2"
  [[ "$value" =~ ^[A-Za-z0-9_./:+-]*$ ]] || { echo "Invalid Compose value for $name" >&2; exit 1; }
  printf '%s=%s\n' "$name" "$value" >> "$env_output"
}
write_env DEV_USER "$(id -un)"
write_env DEV_UID "$(id -u)"
write_env DEV_GID "$(id -g)"
for name in LIMO_SERIAL_HOST_DEVICE LIMO_SERIAL_PORT LIMO_SERIAL_BAUD LIMO_STARTUP_MODE \
    YDLIDAR_HOST_DEVICE YDLIDAR_AVAILABLE REALSENSE_USB_HOST_DEVICE \
    REALSENSE_USB_CONTAINER_DEVICE REALSENSE_AVAILABLE REALSENSE_SERIAL; do
  write_env "$name" "${!name}"
done
write_env YDLIDAR_CONTAINER_PATH "${YDLIDAR_CONTAINER_PATH:-/dev/ydlidar}"
write_env YDLIDAR_BAUD "${YDLIDAR_BAUD:-115200}"
write_env YDLIDAR_ROS_CONFIG "${YDLIDAR_ROS_CONFIG:-}"
write_env REALSENSE_ROS_CONFIG "${REALSENSE_ROS_CONFIG:-}"
mv "$env_output" "${ROOT}/.env"
echo "Updated ${ROOT}/.env from config/config.yaml and current device discovery."

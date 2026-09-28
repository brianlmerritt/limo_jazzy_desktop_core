#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")/.." && pwd)"
export ROS_DOMAIN_ID="${LIMO_SIM_DOMAIN_ID:-73}"
if [[ ! "$ROS_DOMAIN_ID" =~ ^[0-9]+$ ]] || ((ROS_DOMAIN_ID > 101)); then
  echo 'LIMO_SIM_DOMAIN_ID must be an integer from 0 to 101' >&2; exit 2
fi
# The XML enforces loopback. Jazzy LOCALHOST mode injects SHM and an extra UDP
# transport, overriding the transport restriction and breaking isolated IPC.
unset ROS_LOCALHOST_ONLY ROS_STATIC_PEERS
export ROS_AUTOMATIC_DISCOVERY_RANGE=SYSTEM_DEFAULT
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export FASTDDS_DEFAULT_PROFILES_FILE="$repo_root/config/networking/sim-fastdds.xml"
export FASTRTPS_DEFAULT_PROFILES_FILE="$FASTDDS_DEFAULT_PROFILES_FILE"
# Let the existing Isaac launcher load its own Jazzy/Python/CUDA environment.
unset ROS_DISTRO AMENT_PREFIX_PATH COLCON_PREFIX_PATH
export PYTHONUNBUFFERED=1
exec "${ISAAC_LAUNCHER:-$HOME/.local/bin/isaac}" python "$repo_root/scripts/limo-sim-scene.py" \
  --config "${LIMO_SIM_CONFIG:-$repo_root/config/robot/limo-sim.json}" \
  --output-dir "${LIMO_SIM_OUTPUT_DIR:-$HOME/ai/outputs/limo-sim}" "$@"

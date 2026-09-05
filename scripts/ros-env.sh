#!/usr/bin/env bash
# Source this file in Bash; do not enable strict mode in the caller's shell.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo "Use: source /workspace/scripts/ros-env.sh" >&2
  exit 2
fi

_limo_load_ros_environment() {
  local workspace underlay overlay package_setups package_setup restore_nounset=false result=0
  workspace="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)" || return
  underlay=/opt/ros/${ROS_DISTRO:-jazzy}/setup.bash
  overlay="${workspace}/install/${ROS_DISTRO:-jazzy}/local_setup.bash"
  if [[ ! -r "$underlay" ]]; then
    echo "ROS underlay missing. Rebuild and start the dev container; see ROS2_INSTRUCTIONS.md." >&2
    return 1
  fi
  [[ "$-" != *u* ]] || restore_nounset=true
  set +u
  source "$underlay" || result=$?
  if ((result == 0)) && [[ -r "${workspace}/.deps/sensor-env-${ROS_DISTRO}.sh" ]]; then
    source "${workspace}/.deps/sensor-env-${ROS_DISTRO}.sh" || result=$?
  fi
  if ((result == 0)) && [[ -r "$overlay" ]]; then
    # Resolve complete package setups from colcon's dependency index. Ignore stale
    # partial installs whose local_setup.bash is absent (for example old limo_car).
    package_setups="$(python3 "${workspace}/scripts/ros-env-packages.py" "${workspace}/install/${ROS_DISTRO}")" || result=$?
    if ((result == 0)); then
      while IFS= read -r package_setup; do
        [[ -n "$package_setup" ]] || continue
        source "$package_setup" || { result=$?; break; }
      done <<< "$package_setups"
    fi
  fi
  if [[ "$restore_nounset" == true ]]; then
    set -u
  fi
  return "$result"
}

_limo_load_ros_environment

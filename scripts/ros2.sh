#!/usr/bin/env bash
set -euo pipefail

set +u
source /opt/ros/humble/setup.bash

source /workspace/install/limo_msgs/share/limo_msgs/local_setup.bash
source /workspace/install/limo_base/share/limo_base/local_setup.bash
set -u

exec ros2 "$@"

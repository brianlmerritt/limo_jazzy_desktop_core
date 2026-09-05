#!/usr/bin/env bash
# Source this framework adapter before loading the sensor ROS packages.
if [[ ! -r /workspace/.deps/sensor-env.sh ]]; then
  echo "Sensor environment missing; run ./scripts/setup.sh build-drivers on the host." >&2
  return 1
fi
source /workspace/.deps/sensor-env.sh

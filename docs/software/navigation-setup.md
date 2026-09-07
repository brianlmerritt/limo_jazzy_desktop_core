# Namespaced navigation setup — 2026-09-07

## Installed and configured

ROS 2 Jazzy ARM64 Docker image: navigation2/nav2_bringup 1.3.12,
SLAM Toolbox 2.8.5, and RViz2. No robot_localization/EKF was added.
Exploration source: robo-friends/m-explore-ros2,
326cf8a0b487c34246bb8f3326afbcd69576dc60, built as explore_lite and
explore_lite_msgs under the approved src/ros2_navigation parent.

The running namespace is /limo1_explorer. Frame IDs remain local to its private
TF topics. Framework adapters handle absolute upstream topic remappings.
Camera diagnostics and SLAM map/metadata are namespaced too. Only ordinary
ROS infrastructure topics such as /rosout and /parameter_events remain global.

## Validation

- Docker image built successfully; source pins verified through the guarded workflow.
- Chassis, LiDAR, camera and nominal sensor-transform services restarted successfully.
- All 60 configurator regression tests passed, including namespace readiness,
  approved source boundaries, and namespace-independent sensor build caches.
- explore_lite focused CTest/gtest result: 2 tests, zero errors/failures.
- Isolated domain 174 integration test: synthetic map + private TF caused
  explore_lite to send a correctly namespaced goal to a fake Nav2 action server.
  No hardware interfaces or chassis publisher were present in that test.
- SLAM and all seven configured Nav2 servers became lifecycle active.
- Fresh scan, odometry, status, map and map-to-laser TF passed readiness checks.
- Final command routing: collision_monitor is the sole publisher to the chassis
  /limo1_explorer/cmd_vel subscription. No root robot topics are present.
- Initial stationary occupancy map saved successfully (158 x 60, 0.05 m/cell)
  to ignored .deps/maps/initial-stationary.{yaml,pgm}.
- RViz2 executable/Qt startup verified with --help in offscreen mode.
  Mac rendering and RViz panel interaction are not yet verified.
- Host SSH already has X11 forwarding enabled and xauth installed. No SSH host
  configuration changes were made. Normal bringup refreshed the existing sensor
  udev rules through its documented idempotent workflow.

The robot received no movement goal or nonzero velocity during setup.
Mapping and Nav2 remain active and idle; real exploration has not been launched.

## Physical assumptions and next steps

Nominal laser offset comes from the existing limo_four_diff.xacro:
base_link -> laser_frame = (0.103, 0, -0.034) metres, zero rotation.
Verify mounting/alignment physically and in RViz. Footprint is provisionally
0.40 x 0.30 m plus 0.02 m padding; confirm it encloses the actual robot and
attachments. The depth camera does not yet have a measured base extrinsic and
is not used by obstacle avoidance. Initial navigation is LiDAR-only.
Linear/angular limits are 0.10 m/s and 0.25 rad/s. The collision monitor's scan
stop behavior is configured but has not been physically exercised.

After XQuartz installation and Mac logout/login, connect with ssh -Y, run
scripts/rviz.sh in that SSH session, inspect map/scan/footprint alignment, then
perform a supervised Nav2 goal before using scripts/navigation.sh explore.
See ROS2_INSTRUCTIONS.md for the exact commands and stopping/map-saving workflow.
XQuartz OpenGL compatibility remains an end-to-end display test, not a guaranteed
working graphics path. No xhost or unauthenticated X-server access is used.

## Changed files

Only the new exploration gitlink and .gitmodules are staged by the authorized
source workflow. No commits or pushes were made; the chassis/sensor sources
remain unchanged. Generated build trees, map files and .env are ignored.

- `.gitmodules`
- `AGENTS.md`
- `Dockerfile`
- `ROS2_INSTRUCTIONS.md`
- `compose.yaml`
- `config/config.schema.json`
- `config/config.yaml`
- `config/lidar/ydlidar-x2l.yaml`
- `scripts/bring-up-limo-chassis.sh`
- `scripts/bring_up_limo_base.sh`
- `scripts/check-limo-system.sh`
- `scripts/configure-host-env.sh`
- `scripts/realsense.launch.py`
- `scripts/run-limo-base.sh`
- `scripts/run-realsense.sh`
- `scripts/run-ydlidar.sh`
- `scripts/setup.sh`
- `src/ros2_navigation/m_explore_ros2`
- `tools/configurator/limo_config/drivers.py`
- `tools/configurator/tests/test_bringup.py`
- `tools/configurator/tests/test_drivers.py`
- `config/robot/explore.yaml`
- `config/robot/geometry.json`
- `config/robot/navigation.rviz`
- `config/robot/navigation.yaml`
- `config/robot/slam.yaml`
- `docs/decisions/2026-09-07-navigation.md`
- `scripts/check-navigation-data.py`
- `scripts/check-navigation.sh`
- `scripts/navigation.launch.py`
- `scripts/navigation.sh`
- `scripts/robot-namespace.sh`
- `scripts/robot-transforms.launch.py`
- `scripts/run-navigation.sh`
- `scripts/rviz.sh`
- `tools/configurator/tests/check_exploration_runtime.py`
- `docs/software/navigation-setup.md` (this report)

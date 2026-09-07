# LIMO ROS 2 Roadmap

Updated 2026-09-05. **The chassis, YDLIDAR, and RealSense migration to Jazzy is complete.**
Normal startup remains `./scripts/bring_up_limo_base.sh`; it manages container
builds/restarts and starts the chassis in commanded mode with enabled sensors.
No intermediate migration commands are required for normal operation.

Checked items below describe demonstrated results, not blanket validation of
all packages in the upstream repositories. New work should preserve the standard
startup and the component/config boundaries.

## Completed — environment, configuration, and Humble baseline

- [x] Establish and validate the Humble container baseline before migrating; owner merged the work and created/used Jazzy branches in the parent and chassis repositories.
- [x] Keep ROS, Python dependencies, SDKs, and build tools in Docker, with a non-root development user and host UID/GID mapping.
- [x] Implement schema-validated `config/config.yaml`, device/source checks, build recipes, and config-driven source selection.
- [x] Register/pin non-ROS SDK submodules under `drivers/` and ROS sensor wrappers under `src/ros2_devices/`; retain the owner-managed chassis at `src/limo_ros2/`.
- [x] Implement guarded submodule updates/removals, including matching Git-cache cleanup for explicit removals; disabling a device does not remove its source.
- [x] Identify the powered chassis UART and persistent LiDAR/RealSense identities; implement device discovery, scoped Compose access, sensor udev setup, and rollback documentation.
- [x] Separate RealSense USB descriptor identity from its SDK serial number; preserve the leading zero in its ROS string parameter.
- [x] Automate ROS underlay, SDK, and installed-package sourcing through `ros-shell.sh` and `ros-env.sh`; keep interactive shells independent of detached bringup.
- [x] Validate passive chassis telemetry and commanded startup under Humble; preserve the recorded baseline and prior build artifacts.

Evidence: [configuration system](docs/hardware/central-configuration.md),
[UART setup](docs/hardware/orin-nano-limo-serial.md),
[sensor setup](docs/hardware/sensors.md).

## Completed — Jazzy hardware stack

- [x] Build Ubuntu 24.04 / ROS 2 Jazzy Desktop for ARM64; start the development container with the configured NVIDIA runtime and validate ROS message exchange.
- [x] Isolate ROS outputs under `build/jazzy`, `install/jazzy`, and `log/jazzy`; include the container platform in SDK cache keys and use distro-specific SDK environments.
- [x] Build `limo_msgs` and `limo_base`; fix SIGINT shutdown on an invalid ROS context and message-package lint failures; add a hardware-free passive serial regression test. Six reported package tests passed.
- [x] Build YDLIDAR SDK/wrapper on Jazzy using the pinned sources; verify `/scan` and `/point_cloud`. The wrapper's upstream `humble` branch label does not make the running node Humble.
- [x] Upgrade RealSense SDK/wrapper to 2.56.4/4.56.4; build all three wrapper packages and verify image/depth operation and `/camera/front/depth/color/points`.
- [x] Configure the ARM64 SDK's native `pointcloud__neon_.enable` parameter so the intended camera point cloud is actually published.
- [x] Add config-controlled sensor compiler parallelism (`platform.container.build_jobs: 2`) for the 8 GB Jetson.
- [x] Make standard bringup explicitly select commanded mode and wait for `/cmd_vel` endpoint discovery; cover inherited-passive settings and delayed discovery with regression tests. All 57 framework tests passed.
- [x] Remove all Compose containers and successfully start the complete configured Jazzy stack using only `./scripts/bring_up_limo_base.sh`.
- [x] Verify fresh chassis, LiDAR, camera-image, and camera-cloud messages in a 15-second check; verify one `/cmd_vel` subscriber and chassis `error_code: 0`.
- [x] Perform user-authorized low-speed forward/reverse and left/right wheel tests on a stand; verify odometry feedback signs, translation integration, and explicit stops. Leave zero command publishers afterward.

Evidence: [startup validation](ROS2_INSTRUCTIONS.md#validation-record-2026-09-05),
[wheel odometry measurements](docs/software/wheel-odometry-validation.md).
Pose heading currently comes from the IMU: lifted-wheel turns change reported
angular velocity but do not rotate the stationary chassis's odometry pose.

## Open — reliability and physical validation

- [ ] **P0 — Stop behavior:** establish controller command timeout and emergency-stop behavior; design/test a component-owned software command watchdog and zero-command shutdown policy. Explicit stops passed; publisher disappearance has not been validated as a stop mechanism.
- [ ] **P0 — Ground validation:** under separate motion-test authorization, measure forward/reverse distance, turning accuracy, wheel slip, and odometry scale on the floor. Stand tests are not distance calibration.
- [ ] **P1 — Sensor stability:** run a long-duration combined sensor test with topic rates, timestamp freshness, CPU/RAM load, USB bandwidth, and power observations. Investigate recurring RealSense USB control-transfer warnings and recovery after disconnect/reconnect.
- [ ] **P1 — Calibration:** verify LiDAR scan orientation/range filtering, camera intrinsics, measured camera/LiDAR extrinsics, and timestamp alignment. Fresh messages alone do not validate geometry.
- [ ] **P1 — Model/TF audit:** establish a complete, single-owner TF tree and validate it in RViz. Reconcile the configured `laser_frame` with legacy `laser_link`, and decide the `base_link`/`base_footprint` contract before navigation.
- [ ] Refresh a dated host baseline under `host/snapshots/`: JetPack/L4T, kernel, Docker/NVIDIA runtime, power, groups, and CAN/serial/USB/network inventory. Host/device documentation exists, but a complete committed snapshot was not found in this review.
- [ ] Validate the full VS Code Dev Container GUI workflow, display forwarding/RViz rendering, and file ownership end to end; successful container/CLI startup does not prove GUI operation.
- [ ] Audit remaining package manifests, compiler warnings, launch files, QoS, and architecture assumptions. Test description/simulation packages separately; the successful hardware build was not a build/test of every package.
- [ ] Implement the separately proposed [chassis telemetry/diagnostics enhancements](docs/software/limo_chassis_protocol.md); the current Jazzy port does not imply that enhancement plan is complete.

## Repository review — useful follow-up work

Source inspection on 2026-09-05; neither reference was installed, built, or run
against our robot during this review. Links pin the reviewed versions:

| Repository | Branch / commit | Main value |
| --- | --- | --- |
| [westonrobot/limo_ros2_docker](https://github.com/westonrobot/limo_ros2_docker/blob/ad2dba3a908a5401dc835c0f86dc63549eb6b6d7/README.md) | `humble` / `ad2dba3a908a5401dc835c0f86dc63549eb6b6d7` | Navigation, mapping, configurable launches, and a sample simulation world |
| [anshikasinha8/limo_ros2](https://github.com/anshikasinha8/limo_ros2/blob/a481d8814e3b4a89908b08b69a4798924b0c8067/Readme.md) | `jazzy` / `a481d8814e3b4a89908b08b69a4798924b0c8067` | Gazebo Sim launch, differential-drive model changes, and explicit ROS–Gazebo bridges |

### Weston Robot — adapt for Jazzy

- [ ] **P1 — Reusable bringup/model contract:** use the launch argument structure as a reference for exposing frames, odometry topics, and model options through our outer config. Verify one publisher per TF edge; do not copy its fixed IMU transform or serial defaults without measurement. [Bringup source](https://github.com/westonrobot/limo_ros2_docker/blob/ad2dba3a908a5401dc835c0f86dc63549eb6b6d7/src/limo_bringup/launch/limo_start.launch.py)
- [ ] **P1 — Odometry timestamp consistency:** compare its reuse of the received frame timestamp for odometry/TF with our publication-time stamps. Add timestamp-consistency tests before adopting the change; it is not a hardware-clock synchronization solution. [Driver source](https://github.com/westonrobot/limo_ros2_docker/blob/ad2dba3a908a5401dc835c0f86dc63549eb6b6d7/src/limo_base/src/limo_driver.cpp)
- [ ] **P2 — Mapping and map persistence:** evaluate its SLAM Toolbox launch/config and Cartographer alternative, then select a Jazzy-supported backend. Validate `/scan`, `/wheel/odom`, IMU use, map save/reload, and unique TF ownership with recorded data. Its Cartographer config sets `use_odometry=false` and `provide_odom_frame=true`, so it must not be copied unchanged alongside our odometry TF. [SLAM Toolbox launch](https://github.com/westonrobot/limo_ros2_docker/blob/ad2dba3a908a5401dc835c0f86dc63549eb6b6d7/src/limo_navigation/launch/slam_offline_map_launch.py), [Cartographer config](https://github.com/westonrobot/limo_ros2_docker/blob/ad2dba3a908a5401dc835c0f86dc63549eb6b6d7/src/limo_navigation/params/limo_lds_2d.lua)
- [ ] **P2 — Nav2 localization/controller lifecycle:** adapt its split and combined navigation launches for Jazzy, with config-selected maps and parameters. Validate localization, lifecycle startup, cancellation, and recovery in simulation before real navigation. Keep autonomy opt-in through the existing startup/config flow. [Combined launch](https://github.com/westonrobot/limo_ros2_docker/blob/ad2dba3a908a5401dc835c0f86dc63549eb6b6d7/src/limo_navigation/launch/limo_navigation.launch.py)
- [ ] **P2 — Costmaps and middleware:** derive measured footprint, obstacle/inflation settings, scan ranges, and conservative speed limits; reconcile mixed `use_sim_time` and base-frame settings and our odometry topic. Evaluate DDS/QoS on this system rather than assuming its historical Cyclone DDS workaround is needed. [Nav2 config](https://github.com/westonrobot/limo_ros2_docker/blob/ad2dba3a908a5401dc835c0f86dc63549eb6b6d7/src/limo_navigation/params/nav2_params.yaml), [DDS note](https://github.com/westonrobot/limo_ros2_docker/blob/ad2dba3a908a5401dc835c0f86dc63549eb6b6d7/README.md)
- [ ] **P2 — Simulation fixtures:** adapt the simple world and headless/GUI launch options as test fixtures for the modern simulator. Its launch uses `gazebo_ros`/Gazebo Classic, so this is a porting reference, not a Jazzy-ready simulator. [Simulation launch](https://github.com/westonrobot/limo_ros2_docker/blob/ad2dba3a908a5401dc835c0f86dc63549eb6b6d7/src/limo_gazebosim/launch/limo_gazebo_diff.launch.py), [world](https://github.com/westonrobot/limo_ros2_docker/blob/ad2dba3a908a5401dc835c0f86dc63549eb6b6d7/src/limo_gazebosim/worlds/simple.world)

### Anshika Sinha — complete the Gazebo Sim integration

- [ ] **P1 — Jazzy simulation foundation:** adapt the `ros_gz_sim` launch/spawn structure and Gazebo Sim differential-drive plugin into a config-selected simulation mode. Use Gazebo Harmonic, the [documented Jazzy pairing](https://gazebosim.org/docs/harmonic/ros_gz_vendor_pkgs/), and verify wheel dimensions/joint names against our robot. [Launch](https://github.com/anshikasinha8/limo_ros2/blob/a481d8814e3b4a89908b08b69a4798924b0c8067/limo_bringup/launch/limo_gazebo.launch.xml), [model](https://github.com/anshikasinha8/limo_ros2/blob/a481d8814e3b4a89908b08b69a4798924b0c8067/limo_description/urdf/limo_four_diff.xacro)
- [ ] **P1 — Complete bridge contract:** bridge clock, commands, joint states, TF, and odometry to our established topics. The reference bridges the first four but comments out odometry. Validate the hard-coded model/world names, simulation time, TF ownership, and `/wheel/odom`; add simulated scan/depth/IMU streams separately. [Bridge config](https://github.com/anshikasinha8/limo_ros2/blob/a481d8814e3b4a89908b08b69a4798924b0c8067/limo_bringup/config/gazebo_bridge.yaml)
- [ ] **P1 — Isolate simulation from hardware:** use a separate ROS domain and omit physical-device mappings; ensure simulation commands cannot reach the real chassis. Preserve the usual startup entry point with an explicit config mode. This isolation is our proposed requirement, not a verified feature of the fork.
- [ ] **P2 — Finish and test the model port:** audit joint-state plugin options, retained Classic sensor plugins, sensor frames, resource paths, and dependencies; add spawn/clock/odom/scan regression checks. Do not assume a Jazzy branch name means every inherited package is migrated. [Model](https://github.com/anshikasinha8/limo_ros2/blob/a481d8814e3b4a89908b08b69a4798924b0c8067/limo_description/urdf/limo_four_diff.xacro), [bringup manifest](https://github.com/anshikasinha8/limo_ros2/blob/a481d8814e3b4a89908b08b69a4798924b0c8067/limo_bringup/package.xml)

### Adoption boundaries and deferred work

- [x] Identify reasons to retain our working container/driver baseline: the Jazzy fork still contains a [Foxy Dockerfile](https://github.com/anshikasinha8/limo_ros2/blob/a481d8814e3b4a89908b08b69a4798924b0c8067/.devcontainer/Dockerfile) and the [post-spin ROS sleep](https://github.com/anshikasinha8/limo_ros2/blob/a481d8814e3b4a89908b08b69a4798924b0c8067/limo_base/src/limo_base_node.cpp) that caused our Jazzy shutdown failure. Weston's [Dev Container](https://github.com/westonrobot/limo_ros2_docker/blob/ad2dba3a908a5401dc835c0f86dc63549eb6b6d7/.devcontainer/devcontainer.json) requests broad privileged device access; retain our scoped mappings.
- [ ] Check licenses, dependency compatibility, and the exact diff before reusing source; port selected changes without replacing our validated serial configuration, passive-mode behavior, shutdown fix, or pinned sensors.
- [ ] Agree the parent folder for new navigation/simulation/AI components before adding repositories outside `drivers/` and `src/ros2_devices/`. Do not add either fork wholesale as a competing LIMO package tree.
- [ ] **P3 — Isaac Sim / AI:** evaluate separately after the common robot model, frame, clock, and command contracts are defined. Neither reviewed integration establishes an Isaac Sim workflow; do not treat it as completed by the Gazebo work.

**Now:** the hardware stack needs no further Jazzy migration steps. **Next:**
prioritize stop behavior, TF/calibration, and simulation foundations; mapping and
navigation build on those results.

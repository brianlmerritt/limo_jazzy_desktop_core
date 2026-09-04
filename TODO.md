# LIMO ROS 2 Roadmap

Use this checklist to validate the existing Humble fork first, then migrate it to Jazzy on separate branches. Record commands, failures, fixes, device identifiers, and results in this repository as work progresses.

## Phase 1 — Humble Baseline

- [ ] After the owner creates the root-project `humble` branch, keep all baseline fixes on that branch.
- [ ] Set up a central `config/config.yaml` and an idempotent Bash or Python companion script that uses it to verify required drivers and devices, apply the necessary setup safely, and confirm that the correct repositories and revisions are installed as submodules under `src/`.

### Ubuntu 24.04 Host

- [ ] Run `scripts/host-check.sh` and save a dated baseline under `host/snapshots/`.
- [ ] Record JetPack/L4T, kernel, Docker, NVIDIA runtime, architecture, and power configuration.
- [ ] Inventory CAN, serial, USB, Ethernet, cameras, and LiDAR without changing drivers or device names.
- [ ] Power up the LIMO chassis, not only the Jetson, before running serial-device tests.
- [ ] Document current permissions/groups and access to required devices.
- [ ] Add scripts and rollback notes for every unavoidable host driver, udev, group, or device-name change.

### Ubuntu 22.04 / ROS 2 Humble Container

- [x] Create a Humble development Dockerfile or clearly selectable Compose target based on Ubuntu 22.04.
- [ ] Pass through only the required host devices, networking, display, and NVIDIA runtime capabilities.
- [ ] Install ROS 2, Python, colcon, rosdep, build tools, and ROS dependencies in the image—not on the host.
- [ ] Pin or document package and upstream source versions for reproducibility.
- [ ] Verify the VS Code Dev Container workflow and non-root file ownership.

### Build and Test `src/limo_ros2`

- [ ] Confirm the submodule points to the intended fork and Humble revision.
- [ ] Run dependency resolution in the Humble container and document missing or obsolete dependencies.
- [ ] Build from a clean workspace with `colcon build --symlink-install`.
- [ ] Run `colcon test` and review `colcon test-result --verbose`.
- [ ] Fix or document compiler warnings, lint failures, launch errors, and architecture-specific issues.
- [ ] Capture exact clean-build and test commands in scripts or the README.

### Bringup and Robot Validation

- [ ] Review packages, launch files, parameters, URDF, topic names, frames, and hardware interfaces.
- [ ] Establish persistent device identification before changing launch/config files.
- [ ] Verify bringup without enabling motion; inspect nodes, topics, services, TF, and diagnostics.
- [ ] Confirm emergency-stop behavior, safe lifting/support, command timeout, and zero-command defaults.
- [ ] Test CAN/serial communication and sensors before controlled wheel or driving tests.
- [ ] Record known Humble behavior and inherited upstream/fork issues.

## Phase 2 — Jazzy Migration

- [ ] After the owner creates the root-project `jazzy` branch, create/use a `jazzy` branch in the `limo_ros2` fork.
- [ ] Switch the development image to Ubuntu 24.04 and ROS 2 Jazzy.
- [ ] Update package manifests, CMake/Python APIs, dependencies, launch files, parameters, and QoS assumptions.
- [ ] Build and test each package independently, then test the complete workspace.
- [ ] Compare Jazzy topics, TF, diagnostics, and bringup behavior against the Humble baseline.
- [ ] Document every migration fix and retain a clear list of remaining regressions.

## Phase 3 — Additional Hardware

- [ ] Select camera repositories/drivers; add approved repositories as sibling submodules under `src/`.
- [ ] Add camera calibration, launch, bandwidth, and device-mapping configuration under `config/cameras/`.
- [ ] Select and add the LiDAR repository/driver as a sibling submodule under `src/`.
- [ ] Add LiDAR network/serial settings, frame configuration, and calibration under `config/lidar/`.
- [ ] Add depth cameras and other sensors one at a time, with isolated smoke tests.
- [ ] Validate combined USB/network bandwidth, power demand, timestamps, TF, and ROS namespaces.
- [ ] Update container device access and host setup documentation for each addition.

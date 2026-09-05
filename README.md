# LIMO Desktop Core

Reproducible ROS 2 development environment and core platform configuration for
the AgileX LIMO running on NVIDIA Jetson Orin Nano. The current baseline uses
ROS 2 Jazzy in Ubuntu 24.04.

Start the chassis and all enabled sensors with `./scripts/bring_up_limo_base.sh`.
It manages the builds, container restarts, and commanded chassis startup.

See `ROS2_INSTRUCTIONS.md` for the current container, build, passive check, and
explicit commanded bringup commands.

## Goals

- Ubuntu 24.04 / JetPack host
- ROS 2 Jazzy Desktop in an Ubuntu 24.04 container
- Reproducible external ROS dependencies
- VS Code Remote SSH + Dev Containers workflow
- Multi-camera perception
- LiDAR and depth-camera support
- Indoor and outdoor experimentation
- Configurable ROS namespaces for future multi-robot use
- Explicit documentation of host, driver, power and hardware changes

## Current safety state

Low-speed forward, reverse, and turning wheel commands have been tested with
the chassis on a stand; odometry responded and explicit stops passed. See
[the validation record](docs/software/wheel-odometry-validation.md). On-ground
motion, command timeout, and emergency-stop behavior remain unverified.

The Jetson power wiring is still being completed. The Jetson uses a
separate 12 V battery from the LIMO chassis supply.

The LIMO chassis—not only the Jetson—must be powered before serial-device tests.

## Repository layout

```text
.
├── Dockerfile
├── compose.yaml
├── dependencies.repos
├── .devcontainer/
├── config/
├── docs/
├── host/
├── scripts/
└── src/
```

## Central configuration checks

The expected Ubuntu host, Jazzy container, chassis and sensor identities, and
source submodules are declared in `config/config.yaml` and validated inside
Docker:

```bash
./scripts/setup.sh validate
./scripts/setup.sh check
```

The checks accept the preferred `/dev/ttylimo` alias, native Jetson
`/dev/ttyTHS1`, and the AgileX `/dev/ttyUSB1` default. Configuration checks are
read-only and do not require a host Python virtual environment. The separate
`scripts/configure-limo-udev.sh` command explicitly installs or removes the
tracked alias rule. See `docs/hardware/central-configuration.md` for the full
workflow and safety boundaries.

On the verified Orin Nano hardware, Compose passes only `/dev/ttyTHS1` into the
development container and exposes it there as both `ttyTHS1` and `ttylimo`.
It exports `LIMO_SERIAL_PORT=/dev/ttylimo` and `LIMO_SERIAL_BAUD=460800`; the
standalone `limo_base` package understands those variables without reading this
repository's central configuration.

The framework also exports `LIMO_STARTUP_MODE=passive`. Passive mode receives
and publishes chassis telemetry without enabling commanded mode or subscribing
to `/cmd_vel`. Use `./scripts/check-limo-system.sh` inside the container for the
non-motion hardware check. Commanded operation must be selected explicitly.
The opt-in `limo-base` service under the Compose `robot` profile provides
lifecycle-managed commanded bringup when motion control is intended.

The connected YDLIDAR X2L and front Intel RealSense D435i have tracked device
identities, safe udev rules, ROS parameter files, Compose services, and
container-only SDK builds. Their SDKs and ROS wrappers are configured as four
pinned, separate submodules under `drivers/` (SDKs) and `src/ros2_devices/` (ROS wrappers); see `docs/hardware/sensors.md` for
the configuration-driven registration commands, host setup and rollback, and passive
smoke tests.

Generate the ignored environment file before using Compose, then build the base
driver and its dependencies inside the container:

```bash
./scripts/configure-host-env.sh
docker compose up -d dev
docker compose exec dev ./scripts/build.sh --packages-up-to limo_base
```

The environment is present in Dev Container shells and normal Compose commands.
An explicit ROS `port_name` or `baud_rate` parameter still takes precedence.

## Configured sensor drivers

YDLIDAR and Intel RealSense driver recipes are declared in `config/config.yaml`.
From the host, use `./scripts/setup.sh plan-sources` to inspect required source
changes and run `./scripts/setup.sh apply-sources` to register/update
submodules at their configured pins. Then `./scripts/setup.sh build-drivers`
builds enabled sensor drivers in Docker and `./scripts/setup.sh start-drivers`
refreshes discovery and starts their services. The complete first-run sequence,
including host access rules and passive checks, is in [ROS2_INSTRUCTIONS.md](ROS2_INSTRUCTIONS.md).

## Combined robot bringup and ROS shell

Run `./scripts/bring_up_limo_base.sh` on the host to rebuild and start the chassis
and configured enabled sensors. It installs sensor access rules, verifies source
pins, and checks chassis readiness without publishing velocity commands. It
restarts existing robot services; Git source updates remain a separate command.

Run `./scripts/ros-shell.sh` from the host for an interactive Docker shell with
Jazzy and any built Jazzy workspace packages already sourced. In an existing container shell,
use `source /workspace/scripts/ros-env.sh`. `scripts/ros2.sh` and the node launch
wrappers share that same environment loader.

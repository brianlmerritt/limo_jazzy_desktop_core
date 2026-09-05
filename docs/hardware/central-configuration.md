# Configuration System and Daily Workflow

`config/config.yaml` declares the expected Jetson host, Humble container,
hardware device paths, and Git submodules. `config/config.schema.json` rejects
unknown or malformed fields before any checks run. It now covers the LIMO base,
YDLIDAR X2L, front RealSense D435i, and their pinned source repositories.

The configuration tooling runs in the `configurator` Compose service. It does
not create a host Python virtual environment and does not install ROS or Python
packages on Ubuntu.

## How configuration becomes a running robot

The framework reads configuration on each setup/bringup invocation; it is not a
live configuration watcher. Edit tracked inputs, then run the appropriate command
to regenerate deployment values, rebuild, or restart.

| Input | Purpose |
| --- | --- |
| `config/config.yaml` | Platform expectations, physical device identities, enabled devices, driver selection, and exact source pins |
| `config/config.schema.json` | Accepted fields/types; configurator code also checks references, paths, and supported adapters |
| `config/lidar/*.yaml`, `config/cameras/*.yaml` | ROS parameters such as scan settings, camera streams, frame names, and point-cloud enablement |
| `Dockerfile` | Container OS and installed build/runtime dependencies |
| `compose.yaml` and framework scripts | Translate selected configuration into device mappings, environment, builds, and native ROS arguments |

The flow is:

```text
config + schema -> validate -> enabled devices -> driver recipes -> pinned sources
                           -> hardware discovery -> .env -> Compose -> ROS arguments
                           -> SDK/ROS builds -> generated environment + build fingerprint
```

Component repositories never read framework YAML directly. For example, the
YDLIDAR adapter passes the selected port and baud as explicit ROS parameters,
overriding those entries in its ROS parameter file. The RealSense adapter uses `usb_identity.serial` only for host discovery and
udev. Its SDK serial comes from `ros_parameter.value`, is passed as an explicitly
typed string, and overrides `serial_no` in the camera parameter file. These two
serials can differ. The framework launch adapter applies `camera_name` and
`camera_namespace` to the node as well as passing stream settings as parameters.

`enabled: false` excludes a sensor from build/start selection without deleting its
sources. `required: false` permits an enabled sensor to be disconnected; it does
not disable its driver build. Source-level `required` is separate: it selects a
repository independently of enabled devices. `state: absent` explicitly requests
source removal, subject to the safeguards described below.

## Everyday commands

Run from the **host repository root** with chassis power and required sensors
connected:

```bash
./scripts/bring_up_limo_base.sh
```

This checks source pins, installs configured sensor access rules, discovers
devices, rebuilds the image/LIMO/selected sensor drivers, starts sensors, then
starts and checks the commanded chassis. It does not apply Git changes or publish
velocity commands. It restarts existing services and recreates dev. On success,
containers remain detached and the command returns; no shell is opened.

An interactive ROS shell is independent of bringup:

```bash
./scripts/ros-shell.sh
```

Inside an existing Docker shell, use `source /workspace/scripts/ros-env.sh`.
This loads Humble, generated SDK paths, and complete installed ROS package setups
in dependency order. It does not start nodes. See
[ROS2_INSTRUCTIONS.md](../../ROS2_INSTRUCTIONS.md) for bringup checks and stop commands.

## What to run after editing configuration

All commands in this table run on the host. Validate changes first with
`./scripts/setup.sh validate`.

| Change | Apply it with |
| --- | --- |
| Source URL or revision | `./scripts/setup.sh plan-sources`, then `./scripts/setup.sh apply-sources`, then full bringup |
| Device enabled state | Full bringup, or `build-drivers` followed by `start-drivers` through `scripts/setup.sh` |
| USB identity or serial alias | Full bringup, or `./scripts/configure-sensor-udev.sh install all` followed by `./scripts/setup.sh start-drivers` |
| Sensor ROS parameters or parameter-file path | `./scripts/setup.sh start-drivers`; no SDK rebuild is needed |
| Sensor reconnect / changed USB bus address | `./scripts/setup.sh start-drivers` to rediscover and recreate mappings |
| Container dependencies | Full bringup rebuilds the image and recreates dev before building drivers |
| Explicit source removal | Disable consumers, set source `state: absent` and `required: false`, then inspect/apply the source plan |

Sensor-only startup recreates dev and interrupts its shells but does not restart
an already running chassis service. Changes to chassis parameters require full
bringup. The full bringup script explicitly selects commanded mode; the central
`startup_mode: passive` is the default for passive development/check workflows.

## Generated files and current limits

Do not hand-edit generated `.env` values to make a permanent configuration change:
regeneration replaces them. `.env` contains host UID/GID, resolved device paths,
availability, and selected runtime values. It is not a ROS component config file.

Builds publish `.deps/sensor-env.sh` and `.deps/driver-build.sha256` only after
successful completion. SDKs/build directories live under `.deps/drivers/` and
`.deps/build/`; ROS outputs use `build/`, `install/`, and `log/`. Startup checks the
driver fingerprint and rejects missing/stale builds after selection or pin changes.
Keep `.deps/udev/`: it records installed rule content/targets for safe updates and
removal. These generated paths remain untracked.

The current adapters support one X2L and one front D435i, with the LIMO UART
required by the combined deployment. Configuration chooses implemented recipes;
a new sensor family still needs adapter/schema support. Platform fields do not
automatically rewrite the Dockerfile or remaining Humble-specific shell paths.
Jazzy migration therefore requires code/image changes and fresh build outputs,
not just changing `ros_distribution` in YAML. Simulation is not implemented as a
configuration mode yet.

## Commands

From the repository root:

```bash
./scripts/setup.sh validate
./scripts/setup.sh check
./scripts/setup.sh plan
./scripts/setup.sh check-sources
./scripts/setup.sh check-devices
```

The five inspection commands above are read-only. `plan` reports missing host prerequisites
but deliberately does not run `apt`, change groups, install drivers, write udev
rules, or change Git state.

Add confirmed host-only dependencies to `host.required_packages` and loaded
driver modules to `host.required_kernel_modules`. Both lists start empty: items
must be justified by a hardware requirement rather than copied from a generic
desktop or ROS installation guide.

The first run builds the small configurator image and therefore needs access to
the configured container registry and Python package index. Later checks use the
local image unless its build inputs change.

## LIMO serial device

The Humble `limo_base` driver prepends `/dev/` to any `port_name` containing
`tty`, so the selected ROS parameter is a basename rather than a complete path.
The configuration accepts both existing repository conventions:

- Preferred persistent alias: `/dev/ttylimo`, passed as `port_name=ttylimo`
- Native Jetson UART: `/dev/ttyTHS1`, passed as `port_name=ttyTHS1`
- AgileX/upstream default: `/dev/ttyUSB1`, passed as `port_name=ttyUSB1`

The read-only checker accepts the legacy upstream path for diagnostics. Actual
Compose discovery prefers stable configured candidates and excludes entries
marked `fallback` or `upstream_default`; it does not select a numbered USB port
as a substitute for hardware identity. The native verified Jetson UART can be
used before its alias is installed.

The framework exports the package-owned runtime contract through Compose:

```text
LIMO_SERIAL_PORT=/dev/ttylimo
LIMO_SERIAL_BAUD=460800
```

`scripts/configure-host-env.sh` validates the host device and writes these
values, together with `LIMO_SERIAL_HOST_DEVICE=/dev/ttyTHS1`, to the ignored
`.env` file. `limo_base` remains usable outside this repository because it owns
the environment defaults and accepts explicit ROS parameter overrides.

The LIMO chassis must be powered for either serial path to appear. Powering only
the Jetson is sufficient for host and Docker checks, but not for device tests.

Existing software for the original Jetson Nano identified the base UART with
`KERNEL=="ttyTHS1"` and parent controller `KERNELS=="70006040.serial"`. That
parent address does not exist on the Jetson Orin Nano. Live inspection on this
robot identified `/dev/ttyTHS1` under `3100000.serial`, and a receive-only test
confirmed LIMO protocol telemetry on that UART. `/dev/ttyTHS2`, under
`3140000.serial`, produced no data during the same test.

The tracked Orin rule preserves the `/dev/ttylimo` alias but replaces the legacy
world-writable `MODE="0777"` with `GROUP="dialout", MODE="0660"`.

Review and install the host rule explicitly:

```bash
./scripts/configure-limo-udev.sh check
./scripts/configure-limo-udev.sh install
./scripts/setup.sh check-devices
```

Installation is idempotent, copies the tracked rule to
`/etc/udev/rules.d/99-limo-serial.rules`, reloads udev, and retriggers
`ttyTHS1`. Roll it back with `./scripts/configure-limo-udev.sh remove`. Removal
refuses to delete the host file if it no longer matches the tracked rule.

## Host versus container dependencies

Keep only Docker, NVIDIA container support, udev, firmware, kernel modules, and
unavoidable hardware drivers on the host. ROS 2, colcon, rosdep, compiler tools,
Python packages, userspace sensor libraries, and development headers belong in
Docker.

Source application is now available as the explicit configuration-driven command
`./scripts/setup.sh apply-sources`. It changes only source registration, selected
checkouts, and their staged Git records; it never installs host dependencies.
Sensor rule installation/removal is separately managed by
`scripts/configure-sensor-udev.sh`, with known-content checks and recorded state.
See `sensors.md` for affected paths, verification, and rollback.

## Sensor configuration

The sensor entries add model and USB identity data, stable accepted device
paths, ROS parameters, tracked parameter files, and explicit host-rule setup
commands. Serial sensors may define a persistent alias; USB devices may define
an access rule without pretending that one device node represents all camera
interfaces.

`scripts/configure-host-env.sh` discovers the stable X2L serial path and the
current RealSense USB bus address and writes them to ignored `.env`. Missing required
sensors stop generation; missing optional sensors are omitted by `start-drivers`.
The base UART remains mandatory for the current combined LIMO workflow.

See `docs/hardware/sensors.md` for source pins, host rule installation and
removal, container builds, runtime configuration, and passive smoke tests.

## Driver selection and source lifecycle

`drivers` maps named, supported build recipes (`ydlidar`, `realsense`) to SDK and
ROS source names. Each sensor device references one driver and has an `enabled`
boolean (default true). `required` controls missing-device failures, independently
of enablement. Active driver dependencies plus independently required sources
form the source selection; the validator rejects unknown references, unsafe or
nested source paths, unsupported recipes, and inconsistent sensor selectors.

```bash
./scripts/setup.sh plan-sources   # Read-only shell plan
./scripts/setup.sh apply-sources  # Updates/stages sources within approved parents
./scripts/setup.sh build-drivers  # Runs configured recipes in the dev container
./scripts/setup.sh start-drivers  # Refreshes config and starts selected sensors
```

Configuration selects maintained recipes, not arbitrary shell commands. URL/path/
revision changes flow into the generated source plan and build recipe. Device
identity, parameter-file path, baud, and enabled-state changes flow into `.env`
and the runtime adapters. Sensor udev rules derive from `usb_identity` and the
configured alias/target paths. The tracked `alias_setup.match` sensor metadata is
legacy descriptive data; generated sensor rules use `usb_identity`.

Generated deployment inputs never become component dependencies: framework launch
wrappers translate them into public ROS parameters/launch arguments. Exact pins
remain in YAML and must agree with Git's staged gitlinks. Branch labels never
select a moving revision. Disabled sources are retained. Detailed commands,
limitations, and failure recovery are documented in `sensors.md` and the root
`ROS2_INSTRUCTIONS.md`.

Run configurator tests without host Python dependencies:

```bash
docker compose build configurator
docker run --rm --network none -v "$PWD:/workspace:ro" \
  -e PYTHONPATH=/workspace/tools/configurator --entrypoint python \
  limo-configurator:dev -m unittest discover \
  -s /workspace/tools/configurator/tests -v
```

## Approved source folders

Non-ROS SDK roles must resolve to `drivers/<name>`; ROS sensor roles must resolve
to `src/ros2_devices/<name>`. Validation rejects other parent folders except the
existing, owner-managed `src/limo_ros2`. Ask the owner before adding future AI or
other ROS parent folders. `scripts/build.sh` restricts colcon discovery to `src`
so native SDKs are not accidentally built as ROS workspace packages.
`drivers/COLCON_IGNORE` also excludes that tree from direct recursive colcon scans.

Source `state: absent` is explicit removal intent and requires `required: false`
and no enabled driver consuming that source. Application removes both the gitlink/
checkout and the matching `.git/modules` cache after local-work checks. Disabled
devices retain their checkouts. See `sensors.md` for removal and recovery details.

## Jazzy container migration

The `jazzy` branch targets Ubuntu 24.04 / ROS 2 Jazzy in `platform.container`.
`Dockerfile` and Compose implement that platform; editing the platform declaration
alone does not change the image or migrate source pins. The development image is
`limo-jazzy-desktop-core:dev`, with container name `limo_jazzy`.

Build helpers isolate ROS outputs under `build/<distro>`, `install/<distro>`, and
`log/<distro>`. SDK cache hashes include the container platform as well as source
pins. Runtime helpers load only `.deps/sensor-env-<distro>.sh` and the matching ROS
overlay. Unbuilt workspaces can still open a shell with the base ROS installation.
The build fingerprint changes with platform changes, requiring sensor rebuilds.
Existing Humble outputs and udev installation records remain on disk.

See `ROS2_INSTRUCTIONS.md` for the container-only migration commands and the
remaining hardware package compatibility work before full bringup.

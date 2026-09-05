# Central Configuration and Host Checks

`config/config.yaml` declares the expected Jetson host, Humble container,
hardware device paths, and Git submodules. `config/config.schema.json` rejects
unknown or malformed fields before any checks run. It now covers the LIMO base,
YDLIDAR X2L, front RealSense D435i, and their pinned source repositories.

The configuration tooling runs in the `configurator` Compose service. It does
not create a host Python virtual environment and does not install ROS or Python
packages on Ubuntu.

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

The checker prefers the alias when both paths exist and falls back to the
upstream device when it does not. This permits standard bringup before a stable
alias has been installed.

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

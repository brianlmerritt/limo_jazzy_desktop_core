# Central Configuration and Host Checks

`config/config.yaml` declares the expected Jetson host, Humble container,
hardware device paths, and Git submodules. `config/config.schema.json` rejects
unknown or malformed fields before any checks run.

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

All commands are currently read-only. `plan` reports missing host prerequisites
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

Every future `apply` operation must be an explicit command with an idempotent
implementation, verification, affected-file documentation, and rollback. Until
such actions are reviewed, setup remains inspection-only and its rollback is
therefore simply to remove the configurator image if it is no longer wanted.

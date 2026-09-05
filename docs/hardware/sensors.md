# LIMO sensor setup

The verified sensor set is:

- YDLIDAR X2L through a Silicon Labs CP2102 adapter, USB `10c4:ea60`,
  adapter serial `0001`
- Intel RealSense D435i, USB `8086:0b3a`, serial `948123050084`

ROS 2, both userspace SDKs, and both ROS wrappers belong in the Ubuntu 22.04
container. The Ubuntu 24.04 host receives only the tracked udev access rules;
librealsense uses its RSUSB backend so no host kernel patch is required.

## Source repositories

The central configuration pins SDKs under `drivers/` and ROS 2 sensor wrappers
under `src/ros2_devices/`:

| Path | Purpose | Pinned revision |
| --- | --- | --- |
| `drivers/ydlidar_sdk` | YDLidar userspace SDK | `ad8e30f9e9315d4bd7544df85571072fdbcd31ea` (V1.2.7) |
| `src/ros2_devices/ydlidar_ros2_driver` | ROS 2 Humble wrapper | `4ef70d3f32a85704ade0be54b214f3763b1ab3e8` |
| `drivers/librealsense` | RealSense userspace SDK | `e196cefa896e312d79c2df400c7623aa1e9c62ac` (v2.55.1) |
| `src/ros2_devices/realsense_ros` | ROS 2 wrapper matched to SDK 2.55.1 | `8a86cb88a428bdefa204759c899b84adc81606ae` (4.55.1) |

`config/config.yaml` owns the URLs, source paths, and exact revisions. The
`drivers` entries map the `ydlidar` and `realsense` build recipes to their SDK
and ROS source names. Each sensor selects a driver with `driver` and participates
when `enabled: true`. `required` controls whether missing hardware is an error;
it does not disable a driver. Sensor sources have `required: false` because
enabled devices select them through their driver dependencies. Independently
required sources, including `limo_ros2`, are always selected.

From the host repository root:

```bash
./scripts/setup.sh validate
./scripts/setup.sh plan-sources
./scripts/setup.sh apply-sources
./scripts/setup.sh check-sources
```

`plan-sources` prints a shell plan without changing Git. `apply-sources` generates
and preflights a fresh plan, registers missing submodules, initializes registered
ones, reconciles URLs, fetches missing pinned commits, checks out changed pins,
and stages only the selected gitlinks and changed `.gitmodules`. Agents may run this
config-driven workflow within `drivers/` and `src/ros2_devices/`. Other parents
require discussion first; the existing `src/limo_ros2/` remains owner-managed. Review `git diff --cached`
afterward. The command never commits, pushes, resets, or follows a branch tip. It removes
checkouts only when their configuration explicitly declares `state: absent`. Branch names in config are provenance; exact revisions
control setup. An existing branch already at the pin is preserved.

All selected sources are checked before any mutation. Dirty checkouts, unrelated
existing paths, symlink paths, and inconsistent registrations block application.
Generated plans also reject changed source/config state at execution. A network
failure can leave a partial application; fix the failure and rerun the command.
Do not run concurrent source updates. Nested upstream submodules are not
recursively updated by this workflow.

To upgrade a driver, edit its source revision(s), run `plan-sources`, run
`apply-sources`, then rebuild. To disable a sensor, set its device's
`enabled` to `false`, rebuild, and run `start-drivers`. Sources and old build
artifacts are retained. To change hardware, edit its `usb_identity`, persistent
paths, and ROS selector in config, reinstall the generated rules, then run
`start-drivers`. Runtime-only parameter changes do not require a driver rebuild.
The current adapters support one X2L (`ydlidar_x2l`) and one front D435i
(`realsense_front`); another sensor family or multiple instances require an
explicit adapter/schema extension.

## Host access rules

Rules are generated from `usb_identity` and the configured alias/target paths;
USB identity is authoritative for sensor rule matching. No hand editing of
`.rules` files is needed when an identity changes.

```bash
./scripts/configure-sensor-udev.sh install all
./scripts/configure-sensor-udev.sh check all
./scripts/setup.sh check-devices
```

`install` uses sudo to write the configured files under `/etc/udev/rules.d/`,
reload udev, and retrigger tty, USB, and HID devices. The X2L rule creates the
configured alias with group `dialout` and mode `0660`. The camera rule grants
its USB and HID interfaces to `plugdev` with mode `0660`. Disabled sensors are
skipped by `install` and `check`.

The script preflights all targets and only replaces an absent rule, the desired
rule, the last rule it installed, or the original tracked bootstrap rule. It
refuses externally modified rules. Last-installed content and target paths are
recorded under ignored `.deps/udev/`; retain that state to permit later identity
changes and removal. The original tracked rules remain migration references.
Changing a target filename requires removing the old rule first.

Rollback, including rules for disabled sensors:

```bash
./scripts/configure-sensor-udev.sh remove all
```

Removal accepts only known rule content and reloads udev. Keep device entries
until their rules have been removed. Reconnect sensors if permissions or aliases
have not refreshed. No host SDK, ROS package, or kernel patch is installed by
these scripts.

## Container build and launch

Power the LIMO chassis and connect the configured sensors. After applying the
sources and installing the rules above, run on the host:

```bash
./scripts/configure-host-env.sh
docker compose build dev
docker compose up -d --force-recreate dev
./scripts/setup.sh build-drivers
./scripts/setup.sh start-drivers
```

`build-drivers` verifies selected source pins and generates a build script for the
configured development Compose service. The configurator parses YAML in Docker;
no host Python dependencies are installed. Native SDKs use isolated prefixes under
ignored `.deps/drivers/`, and only selected ROS wrappers are built with colcon. Their CMake caches are
refreshed so changed SDK prefixes do not retain old dependency selections.
The RealSense recipe uses `FORCE_RSUSB_BACKEND=ON`. A successful build atomically
publishes `.deps/sensor-env.sh` and `.deps/driver-build.sha256`; startup refuses
missing or stale builds after driver selection or pin changes. Old prefixes are
retained rather than deleted. `scripts/build-sensors.sh` is a host-side alias;
replace old `docker compose exec ... build-sensors.sh` commands with
`./scripts/setup.sh build-drivers`.

`configure-host-env.sh` reads validated config, resolves stable serial candidates,
checks the X2L USB identity, and discovers the camera's current USB bus address.
It rejects ambiguous matches and unavailable required sensors, then atomically
updates ignored `.env`. It does not use numbered `/dev/ttyUSB*` fallback discovery.
The current combined Compose deployment still requires the LIMO UART.

`start-drivers` refreshes that discovery, stops disabled or unavailable optional
sensor services, recreates the development container, and starts only selected
available sensor services. Recreating dev interrupts interactive dev sessions.
It does not start `limo-base` or change its startup mode. Missing required devices
block startup. Parameter files are passed from config to native ROS interfaces;
explicit X2L port/baud and camera serial selections override values in those files.
Upstream components do not read framework configuration directly.

After camera reconnection or reboot, run `./scripts/setup.sh start-drivers` to
refresh its USB address and recreate the affected deployment. Direct Compose
startup bypasses this config/build verification; use the setup command for sensors.

Initial smoke tests are deliberately passive:

```bash
docker compose exec dev ./scripts/ros2.sh topic echo --once /scan
docker compose exec dev ./scripts/ros2.sh topic list | rg '^/camera/front/'
docker compose logs --tail=100 ydlidar realsense
```

The initial D435i profile enables color and depth at 640x480, 15 Hz, aligned
depth, and synchronization. Infrared, IMU, and point-cloud streams remain off
until basic USB stability and bandwidth are verified.

Stop the sensor services with:

```bash
docker compose --profile sensors stop ydlidar realsense
```

## X2L parameters

`config/lidar/ydlidar-x2l.yaml` follows the LIMO X2L specification: 115200 baud,
3 kHz sample rate, single-channel operation, 0.12-8.0 m range, and 6 Hz scan
frequency. The tracked values intentionally override the broader generic X2
sample configuration shipped by the ROS wrapper.

## Explicit source removal

Source `state` defaults to `present`. To remove a sensor stack, disable its device
and set the corresponding SDK and ROS source entries to `state: absent` and
`required: false`. Keep those entries as removal records until application has
succeeded. Merely disabling a device, deleting a source entry from YAML, or changing
its path does not implicitly delete its old checkout.

```bash
./scripts/setup.sh validate
./scripts/setup.sh plan-sources
./scripts/setup.sh apply-sources
```

Removal is restricted to immediate children of `drivers/` and `src/ros2_devices/`.
It preflights dirty, untracked, and ignored files and commits not reachable from
remote-tracking refs (including reflogs). Local work must be preserved first.
It deinitializes the selected submodule, runs `git rm -f`, and deletes its verified
matching cache under `.git/modules/`. Custom registered submodule names are resolved
from `.gitmodules`; cache paths must stay inside the repository's Git storage.
Nested submodule caches require review. A repeated apply can finish cache cleanup
after an interrupted removal when the source used the standard path-based name;
a custom-name interrupted cleanup requires retaining/recovering that name manually.

Restore a removed dependency by setting `state: present`, enabling its device,
and applying/building again. Restoration fetches the configured revision; it does
not recover deleted local-only work. No new parent folder is needed for these
sensors. Discuss future AI or other ROS parent folders with the owner first.

## Combined bringup and environment loading

`./scripts/bring_up_limo_base.sh` now includes the enabled sensor stack. It
verifies sources, installs sensor rules, resolves devices, stops chassis/sensors
before rebuilding, builds LIMO and selected drivers, starts sensors, then starts
and checks the commanded chassis. It does not apply source configuration to Git.
If a later step fails, it stops the chassis and sensor services started by this
workflow. Run it from the host with chassis power and required sensors connected.
The standalone setup/build/start commands above remain available for sensor-only
work. Sensor data smoke tests remain separate from chassis readiness checks.

`./scripts/ros-shell.sh` opens an interactive Docker shell with ROS ready.
`source /workspace/scripts/ros-env.sh` loads the same environment in an existing
container shell. The shared loader sources Humble, optional built sensor SDK
paths, and complete installed package setups in colcon dependency order, so newly built packages become
available without editing shell scripts. Startup still follows config enablement;
the shell can see all installed packages. Missing workspace setup is an error.

## YDLIDAR linker search path

The pinned SDK installs `libydlidar_sdk.a` into its configured prefix's `lib/`
directory, but its CMake package export leaves `YDLIDAR_SDK_LIBRARY_DIRS` empty.
The wrapper consequently links with bare `-lydlidar_sdk`. The framework recipe
sets GCC's `LIBRARY_PATH` to selected SDK library directories for link-time lookup,
and publishes it in the generated sensor environment for subsequent shell builds.
`LD_LIBRARY_PATH` remains the separate runtime library search path. Source pins
and upstream repositories are unchanged. Re-run `setup.sh build-drivers` (or full
bringup) after updating the recipe; no manual SDK installation is necessary.

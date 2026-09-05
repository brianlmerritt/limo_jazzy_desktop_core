# ROS 2 Humble robot bringup

## Bring up the latest checked-out version

Power the LIMO chassis and keep the robot safely supported before starting
commanded mode. From the repository root, run:

```bash
./scripts/bring_up_limo_base.sh
```

The existing script now brings up the chassis **and enabled sensors**. It checks
configured source pins, installs/updates sensor udev rules (sudo), discovers
devices, stops existing chassis/sensor services, rebuilds the image and LIMO
packages, builds selected sensor drivers, and starts the sensors before commanded
chassis bringup. It checks chassis discovery, `/cmd_vel`, control mode, and errors
without publishing a velocity command. Sensor service startup is not a substitute
for checking live sensor data with the commands below.

Bringup does **not** open a shell or attach to the running robot. Containers run
in detached mode; once readiness checks finish the script returns to your host
prompt. Opening or closing `ros-shell.sh` is independent of robot operation.

This restarts the robot services and interrupts existing development-container
shells. A failure after services have been stopped also stops newly started
chassis/sensor services. Source verification failures leave running services alone.
It does not apply Git source changes; use `setup.sh apply-sources` separately when
adding sources or changing pins.

## Enter the ROS 2 environment

From the host repository, open a shell with ROS already loaded:

```bash
./scripts/ros-shell.sh
```

Then run ROS commands directly:

```bash
ros2 node list
ros2 topic list
```

If you are already inside Docker, load the same environment with one command:

```bash
source /workspace/scripts/ros-env.sh
```

The helper loads ROS 2 Humble, the generated sensor SDK environment when present,
and complete installed package setup files in colcon dependency order. Stale
partial installs without `local_setup.bash` are skipped. No package-by-package source list needs maintaining. It preserves
the shell's nounset setting and reports missing underlay/workspace setup files.
It loads all installed packages; enabled-device selection controls running services,
not which installed packages are visible in a shell. Re-source it after a rebuild,
or open a new ROS shell.

For one command from the host without opening a shell:

```bash
docker compose exec dev ./scripts/ros2.sh topic list
```

## Sensor-only setup and bringup

For a full robot bringup, use `./scripts/bring_up_limo_base.sh` above. The
following sequence remains available for source setup or sensor-only work.

Non-ROS SDKs live in `drivers/`; ROS sensor packages live in
`src/ros2_devices/`. The existing chassis fork remains in `src/limo_ros2/`.
The sensor sources, enabled devices, and driver selection are declared in
`config/config.yaml`. Run these commands on the **host**, from the repository
root. Power the LIMO chassis and connect the configured LiDAR and camera first.

```bash
./scripts/setup.sh validate
./scripts/setup.sh plan-sources
# Registers/updates configured submodules in the agreed parent folders.
./scripts/setup.sh apply-sources
./scripts/configure-sensor-udev.sh install all
./scripts/configure-sensor-udev.sh check all
./scripts/configure-host-env.sh
docker compose build dev
docker compose up -d --force-recreate dev
./scripts/setup.sh build-drivers
./scripts/setup.sh start-drivers
```

Review the staged source changes with `git diff --cached`. No commit or push is
automatic. `build-drivers` builds only drivers selected by enabled sensor devices.
`start-drivers` checks the build fingerprint, refreshes discovery, stops disabled
or unavailable optional sensors, and recreates dev and the selected sensor
services. It interrupts existing dev shells, but does not start the chassis
service. See `docs/hardware/sensors.md` for source-update safeguards and udev
verification/rollback.

After changing source pins, repeat `plan-sources`, `apply-sources`,
`build-drivers`, and `start-drivers`. After changing sensor identities, reinstall
the rules and run `start-drivers`. After reconnection or runtime parameter changes,
run `start-drivers` again. Set a sensor's `enabled` to `false` to exclude it from
source/build selection; rebuild and restart to apply that selection. Its checkout
is retained. For deliberate removal, disable the consuming device, set its source
entries to `state: absent` with `required: false`, then run `plan-sources` and
`apply-sources`. This also deletes their matching `.git/modules/` caches after
checking for local changes and local-only commits.

Check for a LiDAR scan and the namespaced camera topics without commanding the
chassis:

```bash
docker compose exec dev ./scripts/ros2.sh topic echo --once /scan
docker compose exec dev ./scripts/ros2.sh topic list | rg '^/camera/front/'
```

## Stop the robot

```bash
docker compose --profile sensors stop ydlidar realsense
docker compose stop limo-base
```

## Motion safety

The current driver has no software command watchdog. It forwards each received
`Twist` but does not automatically send zero if the publisher disappears. The
chassis controller's own timeout has not yet been verified. Keep the robot
supported and do not send a nonzero command until timeout and emergency-stop
behaviour have been agreed and tested.

To verify the command path without requesting movement, publish one all-zero
command:

```bash
docker compose exec dev ./scripts/ros2.sh topic pub --once \
  /cmd_vel geometry_msgs/msg/Twist '{}'
docker compose exec dev ./scripts/ros2.sh topic info /cmd_vel --verbose
docker compose exec dev ./scripts/ros2.sh topic echo --once /wheel/odom
```

After the one-shot publisher exits, `/cmd_vel` should again report zero
publishers.

## Reference: passive chassis check

Passive mode receives `/limo_status`, `/imu`, and `/wheel/odom` without sending
the commanded-mode frame or subscribing to `/cmd_vel`:

```bash
docker compose exec dev ./scripts/check-limo-system.sh
```

## Reference: container commands

The following starts the same services manually; use the main script for its
chassis readiness checks and failure cleanup:

```bash
./scripts/setup.sh check-sources
./scripts/configure-sensor-udev.sh install all
./scripts/configure-host-env.sh
docker compose --profile robot --profile sensors stop limo-base ydlidar realsense
docker compose build dev
docker compose up -d --force-recreate dev
docker compose exec -T dev ./scripts/build.sh --packages-up-to limo_base
./scripts/setup.sh build-drivers
./scripts/setup.sh start-drivers
docker compose --profile robot up -d --force-recreate limo-base
```

Inspect a running chassis service manually:

```bash
docker compose logs --tail=100 limo-base
docker compose exec dev ./scripts/ros2.sh node info /limo_base_node
docker compose exec dev ./scripts/ros2.sh topic info /cmd_vel --verbose
docker compose exec dev ./scripts/ros2.sh topic echo --once /limo_status
```

Open an interactive development shell with ROS loaded:

```bash
./scripts/ros-shell.sh
```

Stop all project containers:

```bash
docker compose down
```

Run a one-off command in a temporary container:

```bash
docker compose run --rm --no-deps dev <command> [arguments...]
```

Examples:

```bash
docker compose run --rm --no-deps dev \
  ./scripts/build.sh --packages-up-to limo_base

docker compose run --rm --no-deps dev \
  ./scripts/check-limo-system.sh

docker compose run --rm --no-deps dev bash
```

The Ubuntu 24.04 host contains hardware access, Docker, and JetPack support.
ROS 2 Humble and its development dependencies run in the Ubuntu 22.04
containers. The development and robot services share host network and IPC
namespaces so ROS 2 discovery works between them.

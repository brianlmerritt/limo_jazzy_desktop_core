# ROS 2 Humble robot bringup

## Bring up the latest checked-out version

Power the LIMO chassis and keep the robot safely supported before starting
commanded mode. From the repository root, run:

```bash
./scripts/bring_up_limo_base.sh
```

The script rebuilds the current image and LIMO packages, starts commanded
chassis bringup, and checks ROS discovery, `/cmd_vel`, control mode, and chassis
errors. It leaves the verified robot service running without publishing a
velocity command.

## Enter the ROS 2 environment

Enter the running development container:

```bash
docker compose exec dev bash
```

Inside the container, source ROS 2 Humble and the built LIMO packages:

```bash
source /opt/ros/humble/setup.bash
source /workspace/install/limo_msgs/share/limo_msgs/local_setup.bash
source /workspace/install/limo_base/share/limo_base/local_setup.bash
```

ROS 2 commands can now be run directly, for example:

```bash
ros2 node list
ros2 topic list
```

## Bring up the LiDAR and front camera

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

The manual equivalent of the main bringup script is:

```bash
./scripts/configure-host-env.sh
docker compose stop limo-base
docker compose build dev
docker compose up -d --force-recreate dev
docker compose exec -T dev ./scripts/build.sh --packages-up-to limo_base
docker compose --profile robot up -d --force-recreate limo-base
```

Inspect a running chassis service manually:

```bash
docker compose logs --tail=100 limo-base
docker compose exec dev ./scripts/ros2.sh node info /limo_base_node
docker compose exec dev ./scripts/ros2.sh topic info /cmd_vel --verbose
docker compose exec dev ./scripts/ros2.sh topic echo --once /limo_status
```

Open an interactive development shell:

```bash
docker compose exec dev bash
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

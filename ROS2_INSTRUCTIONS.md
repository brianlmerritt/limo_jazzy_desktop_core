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

## Stop the robot

```bash
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

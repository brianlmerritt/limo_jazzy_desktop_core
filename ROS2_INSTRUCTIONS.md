# ROS 2 Humble quick start

The host runs Ubuntu 24.04. ROS 2 Humble and its development tools run inside
the Ubuntu 22.04 container.

## Start the development container

From the repository root:

```bash
./scripts/configure-host-env.sh
docker compose build dev
docker compose up -d dev
```

Build the LIMO base packages:

```bash
docker compose exec dev \
  ./scripts/build.sh --packages-up-to limo_base
```

Run the passive, receive-only chassis check:

```bash
docker compose exec dev ./scripts/check-limo-system.sh
```

Passive mode receives `/limo_status`, `/imu`, and `/wheel/odom` without sending
the commanded-mode frame or subscribing to `/cmd_vel`.

## Commanded chassis bringup

Only use commanded mode when the chassis is safely positioned and motion is
intended. Start the lifecycle-managed robot service explicitly:

```bash
docker compose --profile robot up -d limo-base
docker compose logs --tail=100 limo-base
```

The `limo-base` service sends the commanded-mode frame and subscribes to
`/cmd_vel`, but does not publish a velocity command itself. Inspect it from the
development container:

```bash
docker compose exec dev ./scripts/ros2.sh node info /limo_base_node
docker compose exec dev ./scripts/ros2.sh topic info /cmd_vel --verbose
docker compose exec dev ./scripts/ros2.sh topic echo --once /limo_status
```

Before a motion test, confirm `/cmd_vel` reports the expected subscriber and
no unexpected publishers. The development and robot services share host
network and IPC namespaces so ROS 2 discovery works between the containers.

With the chassis safely supported, verify the command path without requesting
movement by publishing one all-zero command:

```bash
docker compose exec dev ./scripts/ros2.sh topic pub --once \
  /cmd_vel geometry_msgs/msg/Twist '{}'
docker compose exec dev ./scripts/ros2.sh topic info /cmd_vel --verbose
docker compose exec dev ./scripts/ros2.sh topic echo --once /wheel/odom
```

After the one-shot publisher exits, `/cmd_vel` should again report zero
publishers. Do not substitute a nonzero command until the motion-test safety
checks have been agreed. The current driver has no software command watchdog:
it forwards each received `Twist` but does not send zero automatically if a
publisher disappears. Any chassis-controller timeout is still unverified.

Stop commanded bringup independently of the development container:

```bash
docker compose stop limo-base
```

Open an interactive shell when needed:

```bash
docker compose exec dev bash
```

Stop the development container:

```bash
docker compose down
```

## Pass a command when creating a container

`docker compose up` uses the service command from `compose.yaml` (`sleep
infinity`). To create a temporary container and replace that command, use
`docker compose run`:

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

Use `docker compose exec dev ...` instead when the `dev` service is already
running. The `robot` profile and `limo-base` service are the preferred commanded
bringup path; do not publish `/cmd_vel` until a motion test is explicitly
intended.

# LIMO ROS 2 cheat sheet

Single-column reference for portrait viewing/printing.
Namespace: `limo1_explorer`. Full detail: [ROS2_INSTRUCTIONS.md](ROS2_INSTRUCTIONS.md).

## 1. Connect and open RViz

**On your Mac or Windows PC** — terminal with SSH available:

```bash
ssh -L 6080:127.0.0.1:6080 blm@limo.local
```

`blm@limo_wifi` is an alternative if that SSH alias is configured.
Keep this connection open. In your local browser, paste:

```text
http://127.0.0.1:6080/vnc.html?autoconnect=1&resize=remote
```

**On the Jetson host** — use this directory for commands below:

```bash
cd /home/blm/dev/docker/limo_jazzy_desktop_core
```

## 2. Full robot startup — no goal sent

Starts chassis, configured sensors, SLAM, Nav2 and browser RViz.
Startup rebuilds/restarts services and may take several minutes.

```bash
./scripts/launch-robot.sh nav
```

Before movement: check live camera, map/scan alignment and physical forward.
In RViz, select **Nav2 Goal**, click the destination, then drag/release
for the final heading. Start with a short forward goal in clear space.

Check navigation readiness:

```bash
docker compose exec -T dev ./scripts/check-navigation.sh
```

## 3. Exploration — starts autonomous movement

**After the corridor Nav2 check**, with navigation already running:

```bash
./scripts/navigation.sh explore
```

**From stopped services**, start the full stack and then explore:

```bash
./scripts/launch-robot.sh explore
```

Save the current occupancy map (`downstairs` is an example name):

```bash
./scripts/navigation.sh save-map downstairs
```

Files go into `.deps/maps/`. This command does not save the SLAM pose graph.
Do not send separate RViz goals during exploration or a game.

## 4. YOLO pose — select model at launch

Starts camera and vision; does not start chassis or navigation.
It also does not stop navigation if navigation is already running.
Choose **one** command; switching recreates the vision service.

```bash
./scripts/launch-robot.sh yolo nano
```

```bash
./scripts/launch-robot.sh yolo small
```

Check fresh inference:

```bash
./scripts/check-vision.sh
```

RViz **Image** topics (under `/limo1_explorer/`):

- Original camera: `camera/front/color/image_raw`
- YOLO pose overlay: `vision/pose/image`

## 5. Hide-and-seek — starts autonomous movement

Choose one model:

```bash
./scripts/launch-robot.sh hide-and-seek nano
```

```bash
./scripts/launch-robot.sh hide-and-seek small
```

Prototype: searches frontiers while mapping, then pauses on a confirmed
person. No speech, identity recognition or complete-map viewpoint search yet.
Use launch commands to switch between game and exploration modes.

## 6. Stop, shutdown and battery change

**Stop navigation/game/exploration; keep mapping and camera running:**

```bash
./scripts/navigation.sh stop
```

**Stop all robot services, including vision and browser RViz:**

```bash
./scripts/launch-robot.sh stop
```

**Then shut down the Jetson before changing the power source:**

```bash
sudo shutdown -h now
```

Wait for shutdown before disconnecting the PSU and connecting the battery.
Software stop commands require a responsive computer and connection.

## 7. Stationary stair observation

Before carrying LIMO, stop motion services and the chassis driver.
Run these on the Jetson host; camera/LiDAR and RViz remain available:

```bash
docker compose stop \
  hide-and-seek exploration navigation mapping limo-base
```

Secure LIMO against rolling/falling; keep every wheel supported. Observe
RGB, depth and point clouds at manually chosen angles. Use sensor-frame
views, not the old corridor map pose. No goals or exploration at the stairs.
**Cliff detection is not implemented. Missing depth is not clear floor.**

Back downstairs: re-establish the map pose, check a short Nav2 goal, then
start exploration. Carrying the robot can invalidate its previous map pose.

## 8. RViz and service diagnostics

Start/restart browser RViz only:

```bash
./scripts/desktop.sh start
```

Service status and recent logs:

```bash
docker compose ps
./scripts/desktop.sh logs
docker compose logs --tail=40 navigation
docker compose logs --tail=40 exploration
docker compose logs --tail=40 vision
docker compose logs --tail=40 hide-and-seek
```

## 9. ROS topic checks — inside the container

Enter a ROS-ready shell from the Jetson host:

```bash
./scripts/ros-shell.sh
```

**Inside that shell**, set a shorthand and inspect live data:

```bash
R=/limo1_explorer
ros2 node list
ros2 topic list
ros2 topic echo "$R/navigation_guard/status" --once
ros2 topic echo "$R/vision/people" --once
ros2 topic echo "$R/hide_and_seek/status" --once
ros2 topic hz "$R/scan"
ros2 topic hz "$R/camera/front/color/image_raw"
```

`Ctrl+C` ends a continuous topic check; `exit` returns to the host shell.
Alignment checks are advisory by default. Collision and stale-sensor
protection still apply; navigation rejects reverse commands.

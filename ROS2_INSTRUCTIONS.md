# ROS 2 Jazzy robot bringup

Quick reference: [ROS2_CHEAT_SHEET.md](ROS2_CHEAT_SHEET.md) — grouped commands for portrait viewing/printing.

## Remote mapping session: Mac to LIMO

Both `blm@limo.local` and `blm@limo_wifi` work from this Mac. The latter can be
used as your SSH alias; it need not be a DNS name. Use either address below.

On the **Mac**, open a terminal and connect with the browser tunnel and an
interactive Jetson shell in the same session:

```bash
ssh -o ExitOnForwardFailure=yes -L 6080:127.0.0.1:6080 blm@limo_wifi
```

If the tunnel from an earlier session is still running, keep it and use a normal
`ssh blm@limo_wifi` shell instead; do not bind local port 6080 twice.

In that **Jetson host shell**, with the chassis and sensors powered:

```bash
cd /home/blm/dev/docker/limo_jazzy_desktop_core
./scripts/start-mapping.sh
```

This calls the standard robot bringup, starts SLAM and Nav2, verifies live data
and command routing, and opens RViz in the noVNC desktop. It stops any old
exploration session during bringup. **It sends no movement goal and does not
start exploration.** Startup can take a few minutes and restarts robot services.

On the **Mac browser**, paste this URL (plain text for copying):

```text
http://127.0.0.1:6080/vnc.html?autoconnect=1&resize=remote
```

Wait for startup to finish, then inspect the Map and Laser displays, the robot's
TF position, and Footprint. The fixed frame should be `map`, with ROS topics
under `/limo1_explorer`. Check that scan returns align with nearby walls, glass
coverings are visible, and the footprint encloses the physical robot. The map
initially covers what the stationary LiDAR can see; it expands as the robot moves.
Nav2 is active, so RViz's goal tool can command motion: leave it unused until the
alignment and clearance checks are complete. The first movement should be a
small supervised goal. Autonomous exploration remains a separate explicit step.

Useful commands in another **Jetson host shell**:

```bash
# Repeat the read-only readiness check:
docker compose exec -T dev ./scripts/check-navigation.sh
# Save the current map:
./scripts/navigation.sh save-map room
# Stop autonomous navigation but keep mapping and the browser desktop:
./scripts/navigation.sh stop
# Stop all robot and desktop services:
./scripts/bring_down_limo_base.sh
```

Closing the browser or SSH tunnel does not stop ROS or the desktop. Use the stop
commands above. To enable exploration after a successful supervised goal, use
`./scripts/navigation.sh explore`; this starts autonomous movement immediately.

## Bring up the latest checked-out version

Power the LIMO chassis and keep the robot safely stationary with clear space before starting
commanded mode. Autonomous exploration requires a separate explicit command. From the repository root, run:

```bash
./scripts/bring_up_limo_base.sh
```

The script brings up the chassis **and enabled sensors**. It checks
configured source pins, installs/updates sensor udev rules (sudo), discovers
devices, stops existing chassis/sensor services, rebuilds the image and LIMO
packages, builds selected sensor drivers, and starts the sensors before commanded
chassis bringup. It checks chassis discovery, `/limo1_explorer/cmd_vel`, control mode, and errors
without publishing a velocity command. The script returns to the host prompt after startup.

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

The helper loads ROS 2 Jazzy, the generated sensor SDK environment when present,
and complete installed package setup files in colcon dependency order. Stale
partial installs without `local_setup.bash` are skipped. No package-by-package source list needs maintaining. It preserves
the shell's nounset setting. Before packages are built it loads the Jazzy underlay alone.
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

RealSense uses separate USB-discovery and SDK-selection serials; see
`docs/hardware/sensors.md` when replacing a camera. Camera topics are under
`/limo1_explorer/camera/front/`, not a single `/camera` topic.

Check for a LiDAR scan and the namespaced camera topics without commanding the
chassis:

```bash
docker compose exec dev ./scripts/ros2.sh topic echo --once /limo1_explorer/scan
docker compose exec dev ./scripts/ros2.sh topic list | rg '^/limo1_explorer/camera/front/'
```

## Stop the robot

Use the canonical host-side shutdown script. It stops navigation first, sends
an explicit zero command while the development container is still available,
and then brings down every Compose profile:

```bash
./scripts/bring_down_limo_base.sh
```

It is safe to run when the development container is already stopped; in that
case it skips the zero-command publication and stops the remaining navigation
producers before bringing down the stack.

For individual service control, the lower-level commands remain available:

```bash
docker compose --profile sensors stop ydlidar realsense
./scripts/navigation.sh stop
docker compose --profile robot stop limo-base robot-transforms
```

## Motion safety

The current driver has no software command watchdog. It forwards each received
`Twist` but does not automatically send zero if the publisher disappears. The
owner confirmed the chassis controller has an automatic timeout (2026-09-07);
its duration is not recorded here. Navigation adds a velocity smoother and
collision monitor. Keep physical stopping access available during supervised tests.

To verify the command path without requesting movement, publish one all-zero
command:

```bash
docker compose exec dev ./scripts/ros2.sh topic pub --once \
  /limo1_explorer/cmd_vel geometry_msgs/msg/Twist '{}'
docker compose exec dev ./scripts/ros2.sh topic info /limo1_explorer/cmd_vel --verbose
docker compose exec dev ./scripts/ros2.sh topic echo --once /limo1_explorer/wheel/odom
```

After the one-shot publisher exits, `/limo1_explorer/cmd_vel` should again report zero
publishers.

## Reference: passive chassis check

Passive mode receives `/limo1_explorer/limo_status`, `/imu`, and `/limo1_explorer/wheel/odom` without sending
the commanded-mode frame or subscribing to `/limo1_explorer/cmd_vel`:

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
docker compose exec dev ./scripts/ros2.sh node info /limo1_explorer/limo_base_node
docker compose exec dev ./scripts/ros2.sh topic info /limo1_explorer/cmd_vel --verbose
docker compose exec dev ./scripts/ros2.sh topic echo --once /limo1_explorer/limo_status
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
ROS 2 Jazzy and its development dependencies run in the Ubuntu 24.04
containers. The development and robot services share host network and IPC
namespaces so ROS 2 discovery works between them.

## Build layout and optional chassis diagnostics

ROS outputs are isolated in `build/jazzy`, `install/jazzy`, and `log/jazzy`.
Sensor SDK environments use `.deps/sensor-env-jazzy.sh`; SDK cache hashes include
source revisions and the container platform. Humble outputs remain untouched.
`platform.container.build_jobs` controls sensor compiler parallelism (2 on this
8 GB Jetson). Use framework build helpers to preserve these paths.

The standard startup is always `./scripts/bring_up_limo_base.sh`. For deliberate
chassis-only diagnosis, `./scripts/bring-up-limo-chassis.sh passive` is still
available; it is not a prerequisite for normal startup. Passive mode has no
`/limo1_explorer/cmd_vel` subscription and does not reset the controller's remembered mode.
The earlier Jazzy shutdown crash was fixed and covered by a virtual serial test.

The RealSense SDK is pinned to 2.56.4 and its ROS wrapper to 4.56.4, which includes
[Jazzy support](https://github.com/realsenseai/realsense-ros/releases/tag/4.56.4).
The YDLIDAR wrapper retains its configured upstream `humble` branch label and
exact source pin; the branch label does not choose the build's ROS distribution.

## Namespaced mapping, navigation and exploration

The robot namespace is `limo1_explorer` (underscores are valid), configured by
`platform.container.ros_namespace` in `config/config.yaml`. Regenerate `.env`
and restart services after changing it. Nodes, topics, actions, `/tf` and
`/tf_static` are scoped under `/limo1_explorer`. Frame IDs stay local: `map`,
`odom`, `base_link`, `laser_frame`. Remap both TF topics in external tools.
There is no additional odometry/IMU fusion.

Nav2, SLAM Toolbox and RViz2 are apt dependencies in the Dockerfile.
`explore_lite` is built from the pinned `src/ros2_navigation/m_explore_ros2`
submodule during normal bringup. For a fresh checkout or changed source pin:

```bash
./scripts/setup.sh plan-sources
./scripts/setup.sh apply-sources
./scripts/bring_up_limo_base.sh
```

Normal bringup starts the chassis, sensors and configured sensor transforms;
it stops any previous navigation/exploration and never starts those automatically.
Run from the host repository:

```bash
# Mapping only: builds a map from scans; issues no movement commands.
./scripts/navigation.sh mapping
# Start mapping plus Nav2 and check lifecycle states/data/TF. No goal is sent.
./scripts/navigation.sh start
# Only after checking scan alignment, footprint and a supervised Nav2 goal:
# THIS COMMAND STARTS AUTONOMOUS MOVEMENT.
./scripts/navigation.sh explore
# Stop exploration and navigation, send zero, leave mapping running.
./scripts/navigation.sh stop
# Save occupancy map into ignored .deps/maps/room.{yaml,pgm}.
./scripts/navigation.sh save-map room
```

Before autonomous motion, verify nominal LiDAR extrinsics in
`config/robot/geometry.json` against the actual mounting. The configured 0.40 m
by 0.30 m footprint plus 0.02 m padding is provisional: verify it encloses all
attachments. Scan geometry comes from the existing LIMO description, with
`laser_frame` matching the actual scanner header. Camera streams are namespaced,
but no guessed base-to-camera transform or depth obstacle layer is enabled.
Navigation initially uses LiDAR only; cover glass at scan height and verify
returns in RViz. Do not assume a 2D scanner detects drop-offs or obstacles outside
its scan plane.

Limits are 0.10 m/s linear and 0.25 rad/s angular. The pipeline is
`cmd_vel_nav -> velocity_smoother -> cmd_vel_smoothed -> collision_monitor -> cmd_vel`.
The collision monitor stops on stale scans (0.5 s), with a configured stop polygon.
Direct teleop/test publication to `cmd_vel` bypasses that pipeline; use
`cmd_vel_nav` for manual commands with the monitor active and no Nav2 goal.
The low-level chassis still consumes unstamped `Twist`, explicitly selected in
Nav2 configuration. Upstream explore_lite starts immediately when launched;
the framework isolates it in an opt-in Compose profile and separate command.

## RViz2 in a browser with noVNC

Use this instead of XQuartz for RViz. The optional `desktop` image extends the
dev image with TigerVNC, noVNC/websockify, Openbox, and fonts. RViz renders on the
Jetson using Mesa llvmpipe (two rendering threads); the browser receives pixels.
The host does not need a desktop/VNC package installation, XQuartz, or a monitor.

On the Jetson host, from this repository:

```bash
./scripts/desktop.sh start
```

This builds the dev image and derived desktop image, then starts only the desktop
service and waits for readiness. It does not start the chassis, mapping, navigation,
or exploration. RViz opens automatically with the namespaced navigation view.
A missing map/TF warning is expected until the robot and mapping are running.

In a separate Mac terminal, keep this SSH tunnel running:

```bash
ssh -N -o ExitOnForwardFailure=yes -L 6080:127.0.0.1:6080 blm@limo_wifi
```

Alternatively use `blm@limo.local`. Open this URL in your Mac browser:

```text
http://127.0.0.1:6080/vnc.html?autoconnect=1&resize=remote
```

No VNC client or X11 forwarding is required. SSH authenticates access; the VNC
service itself has no additional password. VNC listens on loopback port 5901 and
noVNC on 127.0.0.1:6080, not the Wi-Fi interface. Only the noVNC port needs an SSH
forward. X11 TCP listening is disabled, and local X clients use a container-owned
cookie. Disconnecting the browser or tunnel leaves the desktop running.

```bash
# On the Jetson:
./scripts/desktop.sh logs
./scripts/desktop.sh stop
# To reopen after closing RViz (which ends the desktop session):
./scripts/desktop.sh start
```

Validation (2026-09-07): desktop health passed, Mesa llvmpipe advertised OpenGL
4.5, RViz successfully created its render window and reported OpenGL/GLSL 4.5.
The noVNC page returned HTTP 200, and its WebSocket proxy delivered the VNC
protocol greeting. Both listening ports were verified loopback-only. The final
Mac browser interaction still needs the user's tunnel and connection.

Restarting the desktop does not restart or command the robot. Browser Nav2 goal
controls can command motion when navigation is active, just like local RViz.
All dependencies and display processes live inside Docker. The image is declared
in `Dockerfile.desktop`; display settings and supervision are in
`scripts/run-desktop.sh`. Remove the optional desktop service/image to roll back;
there are no host desktop configuration changes to undo.

## XQuartz diagnostics (RViz rendering failed on this Mac)

Finish installing XQuartz and log out/in on the Mac. Start XQuartz, then open a
new Mac terminal and connect (substitute your usual address if `limo.local`
does not resolve):

```bash
ssh -Y blm@limo.local
cd /home/blm/dev/docker/limo_jazzy_desktop_core
./scripts/rviz.sh
```

Test ordinary X11 forwarding from a container before RViz. Run these on the
Jetson host, in the SSH session where host `xeyes` already works:

```bash
./scripts/x11.sh xdpyinfo
./scripts/x11.sh xeyes
# Close the eyes window, then check OpenGL and launch RViz:
./scripts/x11.sh glxinfo -B
./scripts/rviz.sh
```

`x11.sh` launches a temporary container from the dev image with this SSH session's
current display and a scoped authentication cookie. Plain `docker compose exec dev`
does not inherit the host SSH display/cookie. Reconnects can change `DISPLAY`, so
run the helper again from the new SSH session. Close each graphical application
to remove its temporary container and authentication file.

The Dockerfile installs `xauth`, `x11-apps` (including `xeyes`), `x11-utils`
(including `xdpyinfo`), `mesa-utils` (including `glxinfo`), and Mesa software
rendering libraries. After changing these dependencies:

```bash
docker compose build dev
docker compose up -d --no-deps --force-recreate dev
```

The helper defaults to software rendering and does not force an OpenGL version.
For an explicit indirect-GLX diagnostic, use
`LIBGL_ALWAYS_INDIRECT=1 ./scripts/x11.sh glxinfo -B`.
A successful `xeyes` test verifies X11, not RViz's OpenGL compatibility.

Run the helper in that SSH terminal, not the IDE's non-forwarded terminal.
It preserves SSH's `DISPLAY` value, shares the host network and X11 socket,
and imports only the matching authentication cookie into a temporary file mounted read-only in the container and removed on exit. It does not use `xhost +`, enable unauthenticated TCP access, or install
ROS/display application dependencies on the host. RViz configuration shows the
map, scan, transforms, footprint, planned path, and Nav2 goal controls.

Container X11 was verified on 2026-09-07 through the live SSH display: `xdpyinfo`
succeeded, and `xeyes` ran without display errors until the six-second test timeout.
The OpenGL diagnostic still failed with `GLXBadCurrentWindow`, reporting an Apple
M4 renderer and OpenGL `1.4 (2.1 Metal - 90.5)`. This establishes working X11
authentication/transport but does not establish working RViz rendering.
The helper removes forced OpenGL/GLSL version overrides; they do not add driver
capabilities. Mac RViz rendering still requires end-to-end validation.
XQuartz/OpenGL compatibility can prevent RViz rendering even when basic X11
works. If a GLX error occurs, capture it rather than assuming RViz or ROS is
missing. See the [XQuartz FAQ](https://www.xquartz.org/FAQs.html).

## Validation record (2026-09-05)

After removing all Compose containers, `./scripts/bring_up_limo_base.sh` completed
successfully with the chassis, LiDAR, and RealSense all on the Jazzy image.
Commanded mode reported one `/cmd_vel` subscriber, zero publishers, and chassis
`error_code: 0`. A 15-second subscriber check received fresh messages on `/scan`,
`/point_cloud`, `/camera/front/color/image_raw`,
`/camera/front/depth/color/points`, `/imu`, `/wheel/odom`, and `/limo_status`.
The camera image and cloud each delivered over 200 messages in that check.
All 57 framework regression tests passed. No velocity command was published.

The startup readiness check now waits for `/cmd_vel` discovery after discovering
the node. Camera config uses `pointcloud__neon_.enable` for the pinned ARM64 SDK;
see `docs/hardware/sensors.md`. USB control-transfer warnings appeared during
camera startup but did not prevent the verified image/depth/cloud streams.
This was a startup and short streaming check, not a long-duration soak test.

A subsequent user-authorized wheel test on the stand exercised forward, reverse,
and both turning directions. Odometry feedback and explicit stops passed;
see [the recorded results](docs/software/wheel-odometry-validation.md).
Pose heading uses the IMU and therefore stays nearly fixed during lifted-wheel
turning. The test does not validate the controller's command timeout.

## LiDAR orientation correction (2026-09-07)

The owner's physical box test showed forward correctly but left on the right.
`config/lidar/ydlidar-x2l.yaml` now uses `inverted: true` and `reversion: false`.
The pinned SDK implements inversion as angle -> 2*pi - angle; reversion would
rotate by 180 degrees and would not fix this reflection. No mounting transform
or chassis odometry change is needed for this scan-direction correction.

When changing scan orientation, stop exploration/navigation/mapping before
restarting the LiDAR, then create a fresh SLAM session:

```bash
docker compose --profile exploration --profile navigation stop exploration navigation mapping
docker compose --profile sensors up -d --no-deps --force-recreate ydlidar
./scripts/navigation.sh start
```

Maps saved before this correction may be mirrored; do not use them for navigation.
Repeat the stationary front/left box test in RViz before any movement goal.

## Heading correction and passive timing checks (`jazzy_plus`)

The chassis submodule's `jazzy_plus` branch fixes lost slow rotations in odometry.
The previous driver discarded increments below 0.1 degrees and left its heading
state uninitialised. Odometry now starts at zero on the first IMU yaw reading,
preserves small changes, and unwraps +/-180-degree crossings. The raw `imu`
orientation keeps the chassis reference. Restart mapping after restarting the
base driver; do not reuse the distorted map from before this correction.

Build and run chassis regression tests inside Docker (virtual UART, no movement):

```bash
docker compose exec -T dev ./scripts/build.sh --packages-up-to limo_base --cmake-args -DBUILD_TESTING=ON
docker compose exec -T dev bash -c 'source ./scripts/ros-env.sh && colcon --log-base log/jazzy test --build-base build/jazzy --install-base install/jazzy --packages-select limo_base && colcon test-result --test-result-base build/jazzy/limo_base --verbose'
```

Passively check scan arrival timing and transforms at each scan timestamp:

```bash
docker compose exec -T dev bash -c 'source ./scripts/ros-env.sh; python3 ./scripts/check-scan-timing.py --seconds 20'
```

This uses `LIMO_ROS_NAMESPACE` from the container environment. It sends no motion
commands, warms its TF buffer for three seconds, then reports scan arrival gaps,
stamp age, and immediate/delayed/unavailable transforms. Scan age includes sensor
acquisition time; it is not purely transport latency. This subscriber cannot
measure other subscribers' queue losses or establish a DDS packet-loss rate.
Keep the robot stationary for a baseline, then compare under supervised load.

To load a rebuilt chassis driver and create a fresh live map, leaving autonomous
navigation stopped (odometry and the unsaved live map reset):

```bash
./scripts/navigation.sh stop
docker compose --profile navigation stop mapping
docker compose --profile robot restart limo-base
./scripts/navigation.sh mapping
```

Verify a small supervised turn against raw IMU and LiDAR before resuming goals.
The correction does not itself calibrate IMU drift or chassis geometry.

## Front/back scan alignment correction

The owner confirmed that the computed forward path pointed physically backwards.
`config/robot/geometry.json` now gives `base_link -> laser_frame` a yaw of pi
radians (180 degrees). This rotates the scan into the chassis frame; it does not
change chassis motion commands or the corrected IMU heading calculation. The
existing `inverted: true` scan ordering remains in place; `reversion` stays false
so the same half-turn is not applied twice. The laser translation is still the
nominal chassis-description value and has not been physically remeasured.

After changing this static transform, restart `robot-transforms` and mapping,
and start a fresh RViz session if its cached static transform does not refresh.
Do not navigate using maps created with the previous orientation. Verify the
computed forward path against the physical corridor before sending a motion goal.

After the 180-degree mounting correction, the first map retained obstacle cells
near the forward test goal that disagreed with current scans. Restarting mapping
again with the corrected transform settled resolved the discrepancy. The
planning-only check then reached the exact 0.50 m forward goal, with a 0.522 m
path and at most 0.024 m lateral deviation. No movement was executed for this
check; physical navigation validation remains pending.

For the battery-interrupted test results, remaining validation and tomorrow's
startup commands, see [Navigation checkpoint](docs/software/navigation-checkpoint.md).

## Live camera in RViz

The saved RViz configuration includes **Front Camera**, a plain `Image` display
subscribing to `camera/front/color/image_raw` with best-effort QoS. It displays
640x480 RGB video at the configured 15 fps without a camera-to-map transform.
The `Camera` display instead projects a calibrated image into the 3D scene and
requires camera information and a connected transform to the fixed frame. The
camera-to-chassis mounting transform has not been measured/configured, so use
`Image` for the live feed. A small Camera Info lost-message count does not count
all images discarded by the transform filter.

For a stationary camera-only session (including operation on a lab PSU):

```bash
docker compose --profile sensors up -d --no-deps realsense
docker compose --profile desktop up -d --no-deps --force-recreate --wait desktop
```

Recreating the desktop also clears stale X server locks after abrupt power loss.
These commands do not start chassis control or Nav2. Map/TF displays will warn
while the mapping and robot services are stopped; the image still works.

## Default-on orientation checks, forward-only Nav2 and 15 cm body clearance

Navigation now includes a 1 Hz scan/TF consistency check and a forward-only
velocity gate. Alignment disagreement is advisory by default, without stopping
or latching; it never guesses a new scanner rotation from missing returns. The fixed scanner mounting yaw stays at pi.

```bash
./scripts/navigation.sh start
# Optional startup override; disabling checks does not enable reverse:
./scripts/navigation.sh start --check-lidar-orientation false
# The combined startup accepts the same option:
./scripts/start-mapping.sh --check-lidar-orientation true
docker compose exec -T dev ./scripts/ros2.sh topic echo /limo1_explorer/navigation_guard/status --once
```

The 15 cm margin is measured outside the provisional robot body: stop polygon
0.70 x 0.60 m, costmap padding 0.15 m, inflation radius 0.35 m. Automatic backup
and recovery spins are removed. A startup failure stops navigation. The configurable matrix in
`config/robot/alignment-policy.json` maps each alignment state to `continue`,
`slow` (half speed), or `hold` (zero), all defaulting to `continue`. Decisions
recover automatically; stale sensors and collision hazards still inhibit motion.
SLAM remains the pose authority. Automatic global re-localization after carrying
is planned, not supplied by this check.

See [alignment guard details](docs/software/navigation-alignment-guard.md) for
thresholds, limitations, precedence, tests and the required physical validation.
This section supersedes the earlier provisional clearance and velocity-chain
values. The current chain adds `navigation_guard` between the smoother and
collision monitor. No scanner accuracy claim substitutes for measured stopping
clearance, and blind-rear turning remains a separate concern.

## Four robot launch modes: navigation, pose vision, exploration and game

Run these on the Jetson host from this repository:

```bash
# Full chassis + configured sensors + SLAM + Nav2 + browser RViz; no goal sent:
./scripts/launch-robot.sh nav

# Camera + YOLO pose only; no chassis/navigation start. Select at each launch:
./scripts/launch-robot.sh yolo nano
./scripts/launch-robot.sh yolo small

# Full navigation startup, then autonomous frontier exploration (robot moves):
./scripts/launch-robot.sh explore

# Full navigation + selected pose model + frontier-search game (robot moves):
./scripts/launch-robot.sh hide-and-seek nano
./scripts/launch-robot.sh hide-and-seek small

# Stop game, vision and all robot services:
./scripts/launch-robot.sh stop
```

`explore_lite` is already built from the pinned m_explore_ros2 submodule. The
vision image is separate from dev; both weights are included at build time.
`nano` selects yolo26n-pose, `small` selects yolo26s-pose. Switching recreates only
the vision service after checking camera configuration. Default device is CUDA
GPU 0; CPU mode must be explicit via `LIMO_YOLO_DEVICE=cpu` and is not the normal
performance target. The first vision image build downloads several GB of CUDA
and PyTorch dependencies. Later model switches reuse the image and weights.

Add an RViz **Image** display for
`/limo1_explorer/vision/pose/image`. Pose/depth JSON is on
`/limo1_explorer/vision/people`; game state/events are on
`/limo1_explorer/hide_and_seek/status` and `hide_and_seek/events`.
The original RGB/depth feeds remain available for future floor/drop processing.

```bash
./scripts/check-vision.sh
docker compose logs --tail=40 vision
docker compose logs --tail=40 hide-and-seek
```

The game is the first frontier-search prototype: it pauses exploration after
three confident fresh person detections and publishes “I found someone!” as an
event. It does not yet search viewpoints on a fully mapped floor, identify
individual children, speak audio, or protect against stairs. Use the full game
planner backlog in HIDE_AND_SEEK.md for those extensions. Explore and game modes
are mutually exclusive in these launch commands. Use these commands to switch
modes; do not start competing exploration instances or RViz goals during a game.

Package source now lives in the owner-created `src/ros2_hide_and_seek` Git
submodule (https://github.com/brianlmerritt/ros2_hide_and_seek.git), containing
`limo_vision` and `limo_hide_and_seek`. Docker copies/builds that checkout.
The prepared package additions remain uncommitted; the configured revision is
the owner's current initial commit. When publishing a new component revision,
update the framework source pin and gitlink together.

Validated on the current Orin: both models load on CUDA and publish fresh ROS
results; nano/small/nano switching and a 640x480 annotated image passed. The
initial five-sample warm benchmark was approximately 43–45 ms per prediction,
with no claim of sustained-load performance or person-detection accuracy.
The game/exploration launch tests used synthetic data and fake Nav2, not floor
motion. Model weights are checked against `config/cameras/yolo-models.sha256`
during image builds. Nano was left running after setup.

## Next physical session — agreed preparation checklist

This is a plan, not an instruction to start services or move the robot now.

1. **Switch to battery.** Stop the robot services with
   `./scripts/launch-robot.sh stop`, then shut down Ubuntu normally before
   disconnecting the lab PSU. Connect the charged battery and power up.
2. **Corridor: RViz and short Nav2 movement.** Place LIMO facing down the corridor
   and run `./scripts/launch-robot.sh nav`. Confirm the Front Camera Image display
   shows a live, updating feed on `camera/front/color/image_raw`; confirm map,
   scan and physical forward direction agree. Try a short forward goal before
   starting any autonomous exploration. This stage does not need YOLO.
3. **Top of stairs: stationary sensor observation only.** Before carrying LIMO,
   stop the command-producing services and the chassis driver:
   `docker compose stop hide-and-seek exploration navigation mapping limo-base`.
   Leave camera/LiDAR and RViz available for observation. Secure the robot against
   rolling or falling and manually position it at several angles, with wheels
   entirely supported. Observe RGB, depth and point-cloud coverage of the landing
   edge, first step and missing/invalid depth. Use camera/sensor coordinates for
   this observation, not the old corridor map pose. Do not send goals, velocity
   commands or run exploration during this test. Missing depth is not evidence
   of clear floor, and no cliff detector or automatic stair stop exists yet.
4. **Return downstairs and try exploration.** Re-establish the downstairs map
   pose after carrying; if mapping alignment was lost, start a fresh mapping
   session before movement. Recheck a short Nav2 goal. With navigation running
   and satisfactory, use `./scripts/navigation.sh explore` to begin autonomous
   frontier mapping. Keep stair access excluded from this session. Stop using
   `./scripts/launch-robot.sh stop` when finished.

A successful stationary stair observation is sensor evidence for future drop
protection, not approval for autonomous navigation near the stair opening.

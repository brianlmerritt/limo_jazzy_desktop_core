# Desktop Isaac Sim 6.1 and ROS 2 Jazzy

## Ownership and layout

The `external_robot_jazzy` branch owns the desktop launch/configuration overlay. NVIDIA's LIMO USD is referenced through Isaac's asset API; there is no robot fork or copied upstream source. The owner's existing `src/limo_ros2`, RealSense ROS and librealsense checkouts are preserved. The physical Jetson workflow in `compose.yaml` remains separate from `compose.sim.yaml`.

Isaac runs from the existing installation and uses its bundled Python/ROS libraries. ROS tools, RViz and teleoperation run inside the Jazzy Docker image built from this repository's Dockerfile. No host ROS/Python packages are installed. The existing `~/.local/bin/isaac` launcher and its CUDA preload fix are retained.

Validated installation: `6.1.0-rc.26+release.49347.2d230af4.gl` on Ubuntu 24.04, RTX 3090 Ti 24 GB. This is a release candidate; the installation is not upgraded or replaced by these scripts.

## Start and stop

From the repository, once:

```bash
./scripts/install-desktop-helpers.sh
docker compose -f compose.sim.yaml build
```

Everyday use, with `~/.local/bin` on PATH:

```bash
limo-sim start             # GUI, simulated LIMO, ROS Docker container
limo-sim wait              # wait for camera/scene readiness
limo-sim check             # read-only ROS sensor, clock and TF validation
limo-sim rviz              # optional ROS view, separate terminal
limo-sim teleop            # keyboard control, separate terminal
limo-sim stop              # stop owned Isaac/ROS processes; restore prior Qwen
```

First use of Motion BVH can take several minutes to compile shaders; subsequent startups are much faster. `limo-sim wait` allows ten minutes.

`limo-sim start --headless` starts the same scene without an Isaac window. `limo-sim check --motion` drives the simulated robot forward and turns it, and verifies command timeout braking. Use it in the default clear starting area, with no concurrent controller/keyboard publisher. Restart the scene before repeating a motion acceptance run near obstacles.

`limo-sim shell` enters the ROS container; `limo-sim shell ros2 topic list` runs one command. `limo-sim status` and `limo-sim logs` inspect the managed session. Use `ros-sim start|stop|status|shell` for the ROS container alone.

`llama start|stop|status|logs` manages the existing `llama-qwen38.service` on loopback port 8080. Its 256k context allocation occupies almost all 24 GB of VRAM. Starting the simulation stops this service if it was running and records that state. `limo-sim stop` restores it. An explicit `llama stop` also cancels the pending restoration. `llama start` refuses while Isaac is running. If Isaac exits or its GUI is closed, still run `limo-sim stop` to clean up the container and restore Qwen.

Only the transient user unit `isaac-limo.service` and Compose project `limo-sim` are stopped. No broad `pkill` or system service changes are used. These helpers do not enable boot-time startup. An unrelated Isaac session must be closed before starting the managed session. The original `isaac sim`, `isaac python`, etc. remain available for manual work; such sessions are not managed by `limo-sim stop`.

## Configuration contract

The framework launcher passes explicit `--config` and `--output-dir` arguments to `scripts/limo-sim-scene.py`. The scene does not search for repository configuration itself. `--foundation` runs only the physical robot/room, without ROS sensors; use `--duration` for a bounded run.

Defaults and overrides:

| Input | Default / purpose |
|---|---|
| `LIMO_SIM_CONFIG` | `config/robot/limo-sim.json` in this checkout |
| `LIMO_SIM_OUTPUT_DIR` | `$HOME/ai/outputs/limo-sim`; mounted as `/sim-output` in Docker |
| `LIMO_SIM_DOMAIN_ID` | `73`; accepted integer 0–101; use same value for host and container |
| `ISAAC_LAUNCHER` | `$HOME/.local/bin/isaac`; must accept `python SCRIPT ARGUMENTS` |
| `DISPLAY`, `XAUTHORITY` | Desktop session values, passed to Isaac and RViz |

Export overrides consistently for the session before starting/stopping. ROS namespace, wheel radius/track, speed limits, command timeout, sensor mounts and resolutions are in the JSON. The default RViz and teleop commands target namespace `limo`; update/remap their topics when introducing another namespace. Multiple robot instances are a future extension, not enabled by changing this one namespace alone.

Outputs are outside Git: `isaac.log`, `limo-scene.usda`, `front-camera.png`, `front-depth.npy`, `overview.png`, `sensor-settings.json`, `ready.json`, `last-run.json` and `ros-check.json`. Isaac's asset root is resolved using `get_assets_root_path()`; first use needs access to the configured asset source. The saved USD references upstream assets and describes the scene; launch the Python script to enable controllers and ROS publishers.

## ROS interface

Fast DDS uses domain 73 by default, UDP transport restricted to loopback, and explicit localhost peers. The latter are necessary for discovery with a loopback-only transport. `ROS_AUTOMATIC_DISCOVERY_RANGE=SYSTEM_DEFAULT` delegates restriction to this XML: Jazzy's `LOCALHOST` mode injects additional UDP/shared-memory transports, so it is deliberately not used. Host IPC is **not** shared with the container; publisher/reader data sharing is disabled. Both Isaac and Docker use `config/networking/sim-fastdds.xml`. Docker uses host networking to reach the same loopback interface, with no USB/serial devices and no physical chassis/sensor services.

| Topic | Type / meaning |
|---|---|
| `/limo/cmd_vel` | `geometry_msgs/Twist`; differential drive, forward x and yaw z |
| `/limo/odom` | `nav_msgs/Odometry`; simulated ground truth, **not wheel-integrated odometry** |
| `/limo/joint_states` | Four actual simulated wheel joints |
| `/limo/scan` | `sensor_msgs/LaserScan`; planar RTX lidar |
| `/limo/point_cloud` | `sensor_msgs/PointCloud2`; lidar returns |
| `/limo/camera/front/color/image_raw` | `sensor_msgs/Image`, RGB8, 640×480 |
| `/limo/camera/front/depth/image_raw` | `sensor_msgs/Image`, 32FC1 axial depth in metres |
| `/limo/camera/front/{color,depth}/camera_info` | Pinhole camera intrinsics |
| `/clock` | Simulation time; set ROS consumers' `use_sim_time:=true` |
| `/tf`, `/tf_static` | `limo/odom → limo/base_link → limo/laser` and camera frames |

Sensor consumers may use best-effort QoS. Images use a small reliable queue (depth 2) for RViz compatibility. The controller clips commands to 0.5 m/s and 1.0 rad/s, rejects non-finite values, and sets wheel targets to zero after 0.5 wall seconds without a new command. Teleop uses a 0.2 m/s default. This watchdog is for simulation behavior, not a hardware safety certification.

The simulation uses PhysX, gravity and actual wheel/ground contact. A bounded PI yaw-rate controller compensates four-wheel tire scrub by adjusting differential wheel targets; its feedback currently uses ideal simulated angular velocity. Four wheel velocity targets drive the chassis; transforms are read from physics tensors, not authored USD poses. The simple 8×6 m room has collision walls and colored obstacles. Rendering/sensor simulation uses RTX with Motion BVH enabled.

The hosted `Example_Rotary_2D` asset currently contains 128 planar emitters; the local USD overlay explicitly selects one emitter/return, a horizontal ray and 720 samples/revolution at 10 Hz. The camera is an ideal pinhole RGB/depth camera; the lidar is a generic 360° planar RTX sensor with indoor 0.08–12 m range, not a calibrated YDLIDAR X2L or RealSense D435i model. Sensor mounts are explicit simulation choices. Ground truth odometry, exact range sensing and ideal camera imagery are useful for initial integration; noise, latency, hardware extrinsics and wheel-slip calibration should be added before comparing behavior to the real LIMO. No Nav2, SLAM or autonomous driving stack is enabled yet.

## Host modifications and rollback

`install-desktop-helpers.sh` is idempotent, creates only `~/.local/bin/{llama,limo-sim,ros-sim}` symlinks, and refuses to replace unrelated existing files. Runtime state is under `${XDG_STATE_HOME:-$HOME/.local/state}/limo-sim`; the temporary unit lives in the user's systemd manager. Docker holds its image/container layers; generated simulation data lives in the output directory.

Rollback:

```bash
limo-sim stop
rm "$HOME/.local/bin/llama" "$HOME/.local/bin/limo-sim" "$HOME/.local/bin/ros-sim"
```

This leaves the original Isaac and llama.cpp launchers, upstream repositories, Docker image and output files intact. No changes are staged or committed by the setup workflow.

## MicroDuck remains parked

Keep `/media/blm/EC4857274856EFB6/dev/microduck_home.zip` and its Windows training checkpoints as provenance. Do not restore its environment or resume training as part of LIMO setup.

The best candidate identified for a later **Isaac PhysX** RL trial is [dreamerarun/isaaclab_microduck](https://github.com/dreamerarun/isaaclab_microduck), branch `5usu/microduck-port`, researched at `deb10a39e59504a8093a30bf8376b853020fa0ee`. It extends [5usu/IsaacLab](https://github.com/5usu/IsaacLab/tree/microduck-port) and includes actuator/backlash work. Its published smoke run is not proof of a converged gait. It targets the 6.0 generation and needs a separate 6.1 compatibility trial. Preserve it as a pinned upstream checkout/submodule when that work is authorized, with local launch/configuration overlays in our own repository.

[Pollen's official microduck_rl](https://github.com/pollen-robotics/microduck_rl) remains the MuJoCo baseline for eventual hardware transfer. The Newton port was less ready in the earlier source review. The full research, source pins and Windows archive inventory are in `$HOME/ai/outputs/microduck-research-2026-09-28/`. No MicroDuck/MicroCat training environment is installed by this setup.

## Real LIMO frame and lidar observations (owner, 2026-09-28)

The real robot previously had its base TF reversed front/back, lidar azimuths
mirrored left/right, and approximately the rear third of the lidar obscured by
the robot. These are recorded hardware observations, not assumed-correct frame
conventions to copy into all sensors.

This simulation uses +X forward, +Y left, +Z up; positive yaw turns left. The
camera optical frame uses +Z forward, +X right, +Y down. The acceptance check
compares scan ranges against asymmetric room landmarks to catch mirrored angles
or reversed mounting transforms. Physical forward travel is checked against the
reported base orientation; a positive angular command must produce positive yaw.

`lidar_rear_occlusion_degrees` defaults to 120. A small physical ray occluder at
the emitter approximates the chassis blocking the rear sector. Set it to 0 for
an unobstructed comparison; the default acceptance check expects the 120° sector.
The size is an approximation of the owner's observation, not a measurement of
the exact real mount. When integrating the real robot, check chassis orientation,
laser mounting transform and scan angle ordering separately: a yaw transform can
rotate front/back, but cannot repair a left/right reflection. Do not apply the
same 180° rotation to the camera merely because the lidar needs correction.

## Validation on this server

Both headless and GUI runs passed end-to-end Docker subscriber checks: RGB/depth
and intrinsics, 720-bin scan, planar point cloud, advancing simulation timestamps,
connected TF, forward travel, positive left turn and the wall-clock command
watchdog. The GUI test measured 0.432 m forward travel, 0.45 mm residual drift
after timeout, and 0.686 rad of left turn. Scan distances agreed with asymmetric
room geometry within 3.2 cm at the 90th percentile; no far returns passed through
the modeled rear sector. This establishes working simulation integration, not
calibration of real-robot motion or sensing.

The launcher conflict guard, Qwen health after automatic restoration, GUI/RViz
startup, keyboard teleop startup, shell/Python syntax and Compose validation were
also checked. Evidence and the implementation work log are under
`$HOME/ai/outputs/limo-sim-2026-09-28/`. A transient RViz TF extrapolation warning
can occur while it first joins the running scan stream; live scan/camera display
and subsequent message validation passed.

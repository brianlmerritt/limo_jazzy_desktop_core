# Navigation alignment guard and 15 cm clearance

Implemented 8 September 2026. No physical movement was performed to validate
these changes; bench software tests are listed below.

## What stays fixed, and what may change

`base_link -> laser_frame` describes the scanner mount, not the robot's heading
in the house. It remains the measured/configured rigid transform (currently yaw
pi). Rotating or lifting the whole robot does not change that mount. Chassis
odometry tracks relative yaw; SLAM/localization estimates `map -> odom`.

Missing scan returns are not a dependable forward-direction reference. They can
mean housing occlusion, distant surfaces, glass, low reflectivity or missing data. A
confirmed housing mask could help validate mounting on a bench, but its midpoint
cannot determine where the robot was carried. Do not rotate TF automatically
from scene-dependent gaps: that can make the map internally consistent while
reversing physical commands.

The implemented option is a **consistency check**, not automatic mounting
calibration or a guaranteed pickup detector. Following the owner's revised
request, alignment disagreement is advisory by default: no stop and no restart
latch. SLAM Toolbox remains the sole map-pose authority. It already has scan
matching and loop closure enabled in `config/robot/slam.yaml`.

Correct orientation makes LiDAR usable for mapping; it does not prove a unique
global pose. Repeated corridors and self-consistent wrong scan matches can evade
this check. Carrying the robot may exceed SLAM's local matching capture range;
automatic global re-localization remains a separate autonomy backlog item.
Disabling the alignment stop does not implement global re-localization.

## Startup interface

Default: enabled. Host startup examples:

```bash
./scripts/navigation.sh start
./scripts/start-mapping.sh
# Explicit setting (same default):
./scripts/navigation.sh start --check-lidar-orientation true
# Diagnostic override only; reverse blocking and sensor freshness remain enabled:
./scripts/navigation.sh start --check-lidar-orientation false
./scripts/start-mapping.sh --check-lidar-orientation false
```

The CLI flag overrides `LIMO_CHECK_LIDAR_ORIENTATION`; otherwise Compose uses
that environment value (including normal Compose .env substitution) or `true`.
Only literal `true` and `false` are accepted. `navigation.sh start` stops old
navigation/exploration and recreates navigation, so changed settings actually
apply and old goals are not retained. It does not send a movement goal.

The native launch argument is `check_lidar_orientation:=true|false`, default
`true`. The guard's native ROS parameters are `check_lidar_orientation` (bool),
`expected_laser_xyz` (three finite metres), and `expected_laser_rpy` (three finite
radians). Standalone defaults describe the current upright LIMO scanner; the
framework passes geometry.json explicitly. Nonzero expected roll/pitch is
rejected because this check supports an upright planar scan only. No runtime
parameter-change interface is provided; restart to apply settings.

## Configurable decision matrix

Edit `config/robot/alignment-policy.json`, then use the normal navigation startup
to load it. The framework validates the file and passes it as the native string
parameter `alignment_policy_json`; the guard validates it again. Standalone
defaults are identical. Parameters are startup-only; the component does not read
framework paths. An invalid or incomplete policy fails startup.

| State | Evidence | Default action |
|---|---|---|
| aligned | Map matches; mount and odometry checks agree | continue |
| orientation_disagreement | Map matches; mount or odometry check disagrees | continue |
| map_disagreement | Map does not match; mount/odometry checks agree | continue |
| both_disagree | Both checks disagree | continue |
| insufficient_geometry | Fewer than 30 known map endpoints | continue |
| unavailable | Map/TF evidence absent or invalid | continue |

Every row accepts `continue`, `slow`, or `hold`. Continue passes the valid
command; slow scales both forward and angular speed by 0.5; hold emits zero.
Missing evidence takes precedence over disagreement and is never reported as
agreement. Mount and odometry results are reported separately in status.
All decisions re-evaluate at 1 Hz without latching. For example, change
`"map_disagreement": "slow"` to halve speed during a mismatch; restoring matching
evidence automatically restores normal speed. Default rows impose **no
alignment-related stop**, including during new-map creation.

This matrix controls command handling, not competing pose estimators. It does
not publish TF, overwrite the mount, choose a guessed location, or reset the
map. SLAM supplies `map -> odom`; chassis odometry supplies `odom -> base_link`.
Map agreement is conditional on the current SLAM pose, not independent proof
that SLAM is correct. Large-displacement re-localization needs a separate
candidate-search and validation component, described in HIDE_AND_SEEK.md.

## How it checks

At 1 Hz, when checking is enabled:

- Compare the actual mount with configured translation (1 cm tolerance) and
  rotation (2 degrees tolerance).
- Compare successive `odom -> base_link` poses at scan timestamps. Report jumps
  above 0.15 m/s + 0.10 m, or 0.35 rad/s + 0.10 rad over the check interval.
  A discontinuity becomes the next reference, so it does not stay stuck forever.
- Independently project sampled scan endpoints through `map -> laser_frame`.
  Require 30 known endpoints and 55% within 15 cm of occupied map cells for
  a match. Unknown map cells are not corroboration. These are provisional
  diagnostics, not calibrated confidence probabilities.

Independently of the alignment policy, require fresh scan/IMU receipts and
headers (0.5 s limit, at most 0.1 s future timestamps). These health holds recover
automatically when fresh inputs return. The 20 Hz command gate also requires a
check less than 1.5 seconds old and a command less than 0.3 seconds old, rejecting
reverse, lateral, nonfinite and excessive commands. Limits stay 0.10 m/s forward
and +/-0.25 rad/s turn. Normal Nav2 TF requirements and collision stops still
apply: an advisory guard cannot make Nav2 plan without a valid transform.
The chassis yaw-only IMU does not supply dependable lift/tilt detection.

Inspect status:

```bash
docker compose exec -T dev ./scripts/ros2.sh topic echo /limo1_explorer/navigation_guard/status --once
```

The JSON gives readiness, reason, latch state and scan-map match statistics.
Startup preflight checks this status and the guarded command publisher. A guard
process exit tears down its Nav2 launch. The existing chassis timeout remains
necessary if the process/container/computer fails outright.

## Command routing and reverse prohibition

`cmd_vel_nav -> velocity_smoother -> cmd_vel_smoothed -> navigation_guard -> cmd_vel_guarded -> collision_monitor -> cmd_vel`

The collision monitor remains the sole normal publisher to final `cmd_vel`.
The smoother minimum forward speed is zero; RPP reversing stays disabled; backup
and drive-on-heading behavior servers are removed. Default single-goal and
multi-goal behavior trees omit automatic backup and spin recovery. They may
clear costmaps and wait; normal controller rotation toward a path remains.

Manual navigation-session tests must use `cmd_vel_nav`. Direct publication to
`cmd_vel` bypasses this software chain and is not protected by this guard. This
is not a security boundary against arbitrary ROS publishers. Turning can still
sweep a rear corner through an unseen region; preventing negative linear speed
does not make a blind rear hemisphere safe for all motion. Measure actual scan
coverage and turn clearance before confined manoeuvres.

## Clearance interpretation

The user's 15 cm is interpreted as a margin **outside the body outline**, not a
15 cm scanner range. The existing provisional footprint is 0.40 x 0.30 m.

| Setting | Previous | New |
|---|---:|---:|
| Costmap footprint padding | 0.02 m | 0.15 m |
| Planner inflation radius | 0.40 m | 0.35 m |
| Collision stop-zone half length | 0.30 m | 0.35 m |
| Collision stop-zone half width | 0.23 m | 0.30 m |

The stop polygon is therefore 0.70 x 0.60 m around base_link. This **increases**
the old 8–10 cm immediate body margin, while reducing the outer planner cost
field. Inflation radius is not a guaranteed wall clearance. Padding and the
stop polygon establish the requested nominal body margin; corner geometry,
cell resolution, stopping distance and footprint accuracy still matter.

A nominal corridor must exceed 0.60 m for a straight 0.30 m-wide robot with
15 cm on both sides; do not assume exactly 0.60 m is usable. The current 5 cm
map cells and unmeasured attachments need allowance. The 15 cm is not a proven
safe stopping distance solely because LiDAR range measurements are accurate.
Obstacle sensing still uses the configured collision monitor timeout and
minimum-point rule. Glass and surfaces outside the laser plane remain limitations.

## Validation and next physical check

Current results: 70 regression tests and four isolated ROS runtime scenarios
passed. An isolated launch also confirmed that the configured matrix reaches
the native guard parameter. No physical navigation test was performed.
Use the configurator image for the full suite; it supplies jsonschema, which
is not installed in dev. The guard runtime fixtures use dev's ROS libraries.

Hardware-free tests, inside Docker:

```bash
docker compose exec -T dev bash -c 'source ./scripts/ros-env.sh; python3 -m unittest discover -s tools/configurator/tests -p test_navigation_guard.py -v'
docker compose exec -T dev bash -c 'source ./scripts/ros-env.sh; python3 tools/configurator/tests/check_navigation_guard_runtime.py'
```

The runtime fixture uses domain 177 and synthetic data; it does not connect to
the physical robot. It checks forward pass-through, reverse rejection, stale
sensor stop and automatic recovery, advisory scan-map disagreement, the
disabled-orientation override, configurable slow/hold/continue decisions and
clean process shutdown. The full launch
smoke check uses domain 178 without hardware drivers. All servers configured,
but activation waited for absent TF; forced shutdown triggered an upstream
controller abort. This is not a successful full navigation lifecycle test. Unit tests cover map origin
rotation, angle wrapping, unknown cells, invalid velocities and both recovery
trees. Bash/Compose/launch syntax is also checked.

Pending floor validation: initial alignment score in the corridor, policy
transitions near moving people/new rooms, a supervised forward goal,
and measured stop clearance on carpet/tile. Keep wheel-supported tests separate
from floor navigation. No automatic lifting/reorientation experiment or movement
is authorized merely by enabling the startup option.

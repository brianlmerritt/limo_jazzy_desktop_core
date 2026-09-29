# Map and navigation diagnosis, 8 September 2026

Initial diagnosis used read-only live inspection and offline analysis of the
existing drive. The validated adapter was then built and activated; the old map
and graph were preserved, navigation was stopped, and mapping was restarted.
No nonzero velocity or movement goal was commanded. Clearance and TF settings
were not changed.

## Confirmed collision stop

The navigation log records `Robot to stop due to StopZone polygon` at ROS time
1788870957.204, followed by brief continue/stop transitions and a final stop at
1788870957.945. The first progress failure follows at 1788870971.228; the
navigation goal ultimately aborts at 1788871183.100. This establishes an obstacle
stop before the progress failures; it does not identify the physical object from
logs alone.

A later stationary scan has four returns inside the live stop polygon in the
front-left quadrant, approximately x=0.345 m, y=0.276–0.299 m in `base_link`.
The configured trigger is two points. This is consistent with the owner's
reported front-left furniture, although the diagnostic box was also present
for this later capture.

## What the 15 cm setting means

Live parameters match the tracked configuration:

- Provisional body footprint: x=±0.20 m, y=±0.15 m.
- Costmap footprint padding: 0.15 m.
- Collision stop rectangle: x=±0.35 m, y=±0.30 m, measured from `base_link`.
- Costmap inflation radius: 0.35 m, a separate obstacle-cost setting.

The stop rectangle adds 15 cm to each body side. Its diagonal corners are about
21 cm from the unpadded body corners; it is not a constant-distance rounded
outline. The sampled front-left returns are about 19–21 cm from the configured
body corner. These calculations use provisional geometry, not a measured body
clearance. A 15 cm minimum margin is not a requested final stopping distance;
path costs, approach direction and stopping motion can produce a larger gap.
Do not interpret the 30 cm lateral coordinate from the robot centre as a 30 cm
body margin. No clearance values were changed during this diagnosis.

## Map error predates the obstacle stop

The owner measured about 4 m of actual travel, with no other motion since startup.
The live chassis odometry reports x=3.992 m, y=-0.163 m. Live SLAM reports
x=0.942 m, y=-0.016 m. Repeated stationary measurements show unchanged
`map -> odom`; this is not evidence of continuing stationary map drift.

Exporting SLAM's dataset recovered 57 stored scans and their odometric and
corrected poses. Selected entries:

| Stored scan | Odometry x (m) | Corrected map x (m) |
|---|---:|---:|
| 0 | 0.0004 | 0.0004 |
| 1 | 0.0911 | 0.0311 |
| 2 | 0.1912 | 0.0612 |
| 56 | 3.9189 | 0.8714 |

These are the corrected poses in the exported dataset, potentially including
later graph optimization, not a recorded history of every live TF update.

Overlaying the stored scans using odometry produces closely aligned wall
outlines. Overlaying the same scans using corrected SLAM poses produces the
observed compression and fan-like wall distortion. An independent nearest-point
fit, initialized from odometry, estimates 0.089 m versus 0.091 m odometry early
in the drive and 1.041 m versus 1.004 m at scan 16. This supports investigating
SLAM matching/graph processing before altering odometry scale or sensor mounting.
It is a diagnostic fit on one drive, not independent localization ground truth.

The forward-box test separately observed a front surface at about 0.53 m.
It checks forward direction but cannot by itself establish left/right handedness.
The alignment guard only checks consistency and publishes no TF. Scan matching
in SLAM owns `map -> odom`; the sensor mounting remains static.

## Preserved evidence

Ignored local artifacts are under `.deps/validation/map-diagnosis/`:

- `navigation.log`, `obstacle-report.json`: stop timeline and stationary geometry.
- `confused-graph.posegraph`, `confused-graph.data`: SLAM graph and stored scans.
- `trajectory.csv`, `ranges.csv`: extracted poses and laser readings.
- `scan-overlay.png`, `scan-comparison.json`: offline comparison.
- `read-dataset.cpp`, `compare-scans.py`: extraction and comparison sources.

The occupancy map is saved as `.deps/maps/confused-map-20260908.{yaml,pgm}`.
Generated captures and build outputs must remain untracked. Offline tools run
inside the existing ROS development container; no host dependencies were added.

## Reproduced fault and correction

The installed Karto matcher was replayed offline using the saved scans, default
matcher settings, 0.05 m/rad scan acceptance thresholds and loop closing disabled.
This is a controlled comparison, not an exact reproduction of all live settings.
With original zero-valued missing returns it ended at x=0.241 m; changing only
readings below the sensor minimum to NaN ended at x=3.989 m, against x=3.919 m
odometry for the last stored scan. Disabling scan barycenter alone did not fix it.
The installed lookup code skips NaN/Inf but does not skip finite zero there.
Artifacts: `replay.cpp`, `replay-barycenter.csv`, `replay-sensor.csv`, `replay-nan.csv`.

The standalone `src/ros2_devices/limo_scan_adapter` package normalizes invalid
ranges before downstream consumers receive `scan`. The original driver's
`scan_raw` is retained. The normal driver build includes the adapter and
`scripts/ydlidar.launch.py` starts both processes through the existing bringup.
No mounting, odometry, SLAM heading correction, or clearance values are changed.

## Are the missing returns lost data?

An eight-second pre-fix capture received 73 scans, with scan-stamp intervals
0.1108–0.1121 s, and 289–296 valid readings out of 460 bins. The rear sectors
(-180 to -150 and +150 to +180 degrees in robot orientation) had no valid returns;
most other sectors had high valid-return fractions. Matching point-cloud messages
accounted for populated scan bins, with a few raw points sharing the same bin.
The wrapper zero-initializes the full range vector and fills bins with valid SDK
points, leaving other bins zero.

This indicates a persistent directional absence of returns plus angle binning,
not evidence of whole-scan transport loss in that interval. The owner subsequently confirmed the standard LIMO chassis blocks the rear
beams. Other isolated missing returns can still depend on the scene or acquisition.
There were no repeated scan timeout/reconnect errors in the inspected driver log;
there was one initial baseplate-information failure and one incompatible subscriber
QoS warning. Neither alone proves measurement packet loss. The raw stream remains
available. The persistent rear blind sector is now confirmed by the owner as
chassis occlusion; exact angular boundaries have not been calibrated.

## Validation and handoff

The adapter package built successfully and its colcon test report has seven
tests, zero failures. All 48 affected configurator/bringup regression tests pass
in the configurator container. A live comparison matched 35 raw/output scan
pairs: every valid range and all metadata were unchanged, and 5,572 invalid
readings became NaN. The initial launch routing check caught an absolute-versus-
relative remapping error; this was corrected and the full comparison passed.

The corrected pipeline is running. The old map has been saved and a fresh
stationary mapping session started; navigation/exploration remain stopped.
A supervised drive is still needed to validate the fix on live moving hardware.
The owner confirmed the rear blind sector is caused by the standard chassis.
See `docs/hardware/sensors.md`. Do not shrink clearance to address unrelated
mapping or acquisition issues.

The standard `./scripts/setup.sh build-drivers` workflow also completed with the
adapter included and refreshed its build record. Existing RealSense informational
stderr (`rs-enumerate-devices` unavailable) did not fail its build. No dependencies
were installed on the host.

## Owner-requested cleanup for repositioning

The owner requested the old map and logs be cleared before moving the robot back
to the start. Mapping and navigation containers were removed, clearing their
live graph and container/launch logs. The old map files and local map-diagnosis
captures listed above were deleted; the numerical findings remain documented
here. These artifact names describe the completed investigation, not files still
available for replay. Build/test history is separate from the old mapping run.
Mapping and autonomous navigation remain stopped until repositioning is complete.

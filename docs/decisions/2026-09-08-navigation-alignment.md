# Default-on navigation consistency gate

Owner requested continuing direction/TF alignment checks, a default-on startup
option, 15 cm clearance and no blind reversing. Implement a platform-owned
navigation interlock in scripts, consuming only native ROS topics/parameters;
the framework launch translates its geometry and startup option into those
parameters. It is a platform diagnostic adapter, not a dependency introduced
into upstream Nav2, SLAM or sensor/chassis components. No new source parent or
submodule is introduced.

Do not infer global heading from missing scan sectors or modify mounting TF
while moving. The calibrated mount is rigid. Scan/map matching is a consistency
check with explicit uncertainty, not automatic calibration
or guaranteed kidnapping detection. Preserve independent collision monitoring.
Future reuse should package the native interface as an independently testable
ROS component under an owner-agreed source location.

Interpret 15 cm outside the body rather than from the LiDAR origin. Preserve
speed limits. Remove blind backup recovery, reject negative translation before
the collision monitor, and require physical clearance validation before claims
about narrow-corridor performance.

## Revised owner policy: advisory alignment and autonomous recovery

The owner explicitly rejected alignment stops and restart latches. All alignment
matrix rows now default to continue; configurable slow/hold choices are available
per evidence state. Sensor-health holds automatically recover with fresh data.
Collision monitoring and reverse blocking remain independent. Neither the
policy nor status pretends to switch pose sources: SLAM remains map-pose owner.
Autonomous global re-localization and higher-level search planning are planned
separately in HIDE_AND_SEEK.md. No floor movement was requested for this change.

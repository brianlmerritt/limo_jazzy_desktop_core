# Navigation checkpoint after battery interruption

## Verified

- Chassis source is on `jazzy_plus`; the outer environment repository is on
  `navigation`. Changes are uncommitted.
- Heading initialization and small-angle accumulation are corrected. Virtual
  UART tests cover the actual serial decoder and published odometry.
- The supervised left-turn retest measured 14.5 degrees in both IMU and odometry,
  approximately 14.0 degrees from LiDAR alignment. The owner confirmed the
  physical rotation against a cardboard marker.
- The owner confirmed the forward path was physically backwards. The framework
  laser mounting yaw is now pi radians; scan `inverted: true` and
  `reversion: false` remain. The owner confirmed the corrected forward direction.
- After a second map reset with the corrected transform settled, a planning-only
  path reached the exact 0.50 m forward destination: 0.522 m path length and
  at most 0.024 m sideways deviation.

## Not yet verified

The subsequent physical half-metre Nav2 test was interrupted by battery loss.
The last captured feedback showed about 0.114 m odometry travel; there is no
confirmed success result or reliable final physical distance. Do not count it
as a passed navigation test.

A chassis process previously remained alive while disappearing from the ROS
graph. Restarting restored it, but the cause remains unresolved. Occasional
startup discovery/TF delays and a command-publisher preflight failure also
occurred. Rechecks passed; a middleware fault has not been established.

RViz's Navigation panel can retain stale status after Nav2 stops. Use container
state and readiness checks, not that panel alone, to establish readiness.

## Current shutdown and next session

Robot hardware services, mapping, desktop and navigation are stopped. Only the
development container may be running for software tests; it runs `sleep infinity`
and does not start the chassis driver. No saved navigation goal will be replayed
by these framework startup scripts.

After charging, place the robot on the floor with a clear test corridor. Use a
fresh map: movement onto blocks invalidates the previous session's pose context.
The first physical test should be a supervised half-metre goal, followed by
checking actual direction, distance, scan/map alignment and chassis voltage.
Do not begin autonomous exploration until that test passes.

```bash
# On the Jetson, after the robot is positioned and powered:
./scripts/start-mapping.sh
```

This starts mapping, Nav2 and the browser desktop, but sends no movement goal.
On the Mac, restore the tunnel if it is no longer running:

```bash
ssh -N -o ExitOnForwardFailure=yes -L 6080:127.0.0.1:6080 blm@limo_wifi
```

Browser address:

```text
http://127.0.0.1:6080/vnc.html?autoconnect=1&resize=remote
```

Check battery telemetry before the supervised movement test:

```bash
docker compose exec -T dev ./scripts/ros2.sh topic echo /limo1_explorer/limo_status --once
```

Voltage is telemetry, not a calibrated state-of-charge estimate. No new voltage
cutoff has been guessed. Preserve the chassis's built-in protection.

The battery-interrupted container logs are saved locally at
`.deps/diagnostics/battery-interrupted-session.log`; recordings, planning results
and screenshots are also under `.deps/diagnostics/` and are not tracked.

## Subsequent camera bench session

The owner switched the chassis to a lab PSU, with wheels off the ground.
Camera-only testing verified 640x480 RGB at approximately 15 fps. RViz now has a
saved plain Image display, avoiding the unavailable camera-to-map transform.
Development, camera and desktop services are running for this session; chassis
control, mapping and navigation remain stopped. This supersedes the shutdown
state above. Camera/video checks do not validate navigation on the blocks.

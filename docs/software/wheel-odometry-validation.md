# Wheel odometry stand test — 2026-09-05

Tested the running Jazzy `limo_base` through its public `/cmd_vel` interface,
with the user confirming the LIMO was on a stand. Chassis motion mode was
four-wheel differential (`motion_mode: 0`), with no other command publisher.
Commands were published at approximately 20 Hz for 1.5 seconds each, separated
by one-second zero-command periods. Final cleanup sent zero for two seconds.
The test monitored fresh odometry/status and aborted on chassis errors or a
competing publisher. No on-ground motion or distance calibration was tested.

| Phase | Command | Mean reported velocity after initial 0.4 s | Pose displacement along initial heading |
| --- | --- | --- | --- |
| Forward | +0.100 m/s | +0.0986 m/s | +0.1406 m |
| Reverse | −0.100 m/s | −0.0981 m/s | −0.1393 m |
| Left turn | +0.300 rad/s | +0.3149 rad/s | +0.00026 m |
| Right turn | −0.300 rad/s | −0.2884 rad/s | +0.00036 m |

All four directions produced the expected sign of odometry twist. Translation
integrated in the expected direction. Each stop met the test thresholds
(|linear velocity| < 0.02 m/s, |angular velocity| < 0.05 rad/s); the final sample
reported exactly zero linear and angular velocity. The test publisher exited,
leaving zero `/cmd_vel` publishers and one chassis subscriber. The normal stack
remained running in commanded mode.

`limo_driver.cpp::publishOdometry` integrates controller-reported translational
velocity but uses IMU-derived heading for pose orientation. The chassis stayed
still on its stand, so pose yaw was unchanged during both turning phases even
though odometry angular velocity changed sign. This is the driver's current
behavior, not evidence that rotational feedback failed. It is not pure
wheel-integrated pose odometry.

The result verifies feedback direction, position integration, and response to
explicit stop commands. It does not establish wheel calibration, slip behavior,
controller timeout, or emergency-stop behavior. Odometry here is the driver's
interpretation of controller telemetry, not an independent measurement of wheel
rotation or physical displacement.

Raw samples and summaries are in the local ignored artifact
`.deps/validation/wheel-odometry.json`.

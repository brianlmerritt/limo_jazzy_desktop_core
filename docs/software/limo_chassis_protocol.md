# LIMO chassis driver enhancement (not implemented yet)

## Software source

https://pypi.org/project/pylimo/ Python library which uses more features than the ROS 2 drivers

 ## LIMO chassis driver improvement: Humble first, then Jazzy

 We are currently bringing up the existing LIMO stack under **ROS 2 Humble in an Ubuntu 22.04 Docker container**. Do not start the Jazzy port of this work until he Humble implementation builds and its non-motion telemetry has been validated.

 The existing AgileX LIMO driver leaves useful controller telemetry unused. The goal is to turn the chassis driver into a well-documented, diagnostic-friendly ardware interface rather than merely preserving the legacy `/cmd_vel`, `/odom`, `/imu`, `/limo_status` behaviour.

 ### Important constraints

 * Preserve existing working behaviour unless there is a documented reason to change it.
 * Do not assume device names, usernames, paths or hardware configuration. Read existing project configuration or discover them.
 * Do not perform physical motion tests unless explicitly authorised.
 * Do not assume that AgileX generic UGV actuator-frame layouts are byte-for-byte identical to LIMO. Use them as a reference, but verify actual LIMO frames efore decoding them as authoritative data.
 * Keep changes small, reviewable and documented.
 * Humble is the validation baseline. Jazzy should be a port of the validated implementation, not a separate rewrite.

 ---

 # Phase 1 — Humble

 ## 1. Document the current LIMO serial protocol

 Inspect the current LIMO driver and protocol definitions and create clear documentation covering at least:

 * framing:

   * header `0x55`
   * frame length
   * message ID
   * 8-byte payload
   * checksum
 * known message IDs:

   * `0x111` motion command
   * `0x211` system state
   * `0x221` motion state
   * `0x251–0x254` actuator high-speed state
   * `0x261–0x264` actuator low-speed state
   * `0x311` wheel odometry
   * `0x321` IMU acceleration
   * `0x322` IMU gyro
   * `0x323` IMU Euler orientation
   * `0x421` control-mode configuration
 * which frames are currently decoded
 * which frames are received but ignored
 * units and scaling for every field already confirmed by the driver

 Clearly distinguish:

 **confirmed LIMO protocol fields**

 from

 **candidate fields inferred from AgileX common UGV protocol code**.

 Add references in the documentation to the relevant source files used to establish each interpretation.

 ## 2. Expose wheel odometry that is already being decoded

 The existing driver parses the `0x311` frame into:

 * left wheel odometry
 * right wheel odometry

 but currently discards those values.

 Preserve them and publish them in a useful ROS interface.

 Prefer a small explicit message in `limo_msgs` if no suitable standard ROS message represents the raw left/right controller counts cleanly.

 The output should retain the raw controller values rather than prematurely converting them into another integrated pose.

 Document:

 * whether these are encoder counts, accumulated pulses or another unit
 * signedness
 * rollover behaviour if known
 * update rate observed on the real chassis

 Do not guess unknown conversion factors.

 ## 3. Add raw chassis-frame diagnostics

 Add an optional debug mode, disabled by default, that allows us to inspect received LIMO protocol frames without changing normal driver behaviour.

 It should make it possible to observe:

 * message ID
 * eight payload bytes
 * arrival timestamp

 especially for:

 * `0x251–0x254`
 * `0x261–0x264`

 Avoid flooding normal logs. Use either a dedicated ROS diagnostic/debug topic or controlled/throttled logging.

 The purpose is to establish what the real controller is actually transmitting.

 ## 4. Investigate actuator high-speed frames

 AgileX's common UGV protocol uses the corresponding high-speed actuator IDs for data resembling:

 * motor ID
 * RPM
 * motor current
 * encoder/pulse count

 Verify this empirically on the LIMO.

 Before publishing decoded values:

 1. capture actual frames
 2. compare their behaviour with known physical conditions
 3. compare field layout with AgileX common UGV protocol definitions
 4. document the evidence

 If confirmed, add a per-actuator ROS message containing at least:

 * actuator index
 * RPM
 * current
 * pulse/encoder count
 * source timestamp

 Do not silently treat an inferred field layout as confirmed.

 ## 5. Investigate actuator low-speed frames

 AgileX's common UGV protocol uses the corresponding low-speed actuator IDs for values resembling:

 * driver voltage
 * driver temperature
 * motor temperature
 * driver status/state bits

 Perform the same empirical validation before relying on these fields.

 If confirmed, expose them as structured ROS data.

 ## 6. Improve chassis diagnostics

 Retain the current system-state information:

 * battery voltage
 * vehicle state
 * control mode
 * motion mode
 * controller error code

 Replace print-only error handling with useful ROS diagnostics while preserving compatibility with `/limo_status`.

 Prefer `diagnostic_msgs/DiagnosticArray` for health/status reporting where appropriate.

 Include:

 * low battery
 * remote-control disconnect
 * motor-driver faults
 * drive-status fault
 * actuator-specific faults if confirmed from low-speed frames

 ## 7. Add stall and slip observability, not autonomous recovery

 Do **not** add autonomous recovery behaviour at this stage.

 Add the telemetry necessary for a later higher-level detector.

 Document how future logic could distinguish:

 **probable stall**

 * commanded motion is non-zero
 * measured wheel RPM remains near zero
 * motor current is elevated

 **probable wheel slip**

 * wheel RPM indicates motion
 * chassis velocity / fused localisation indicates little or inconsistent motion

 **individual-wheel obstruction/fault**

 * one actuator differs significantly from expected kinematics or neighbouring actuators

 Any thresholds should remain configuration parameters and should not be invented until real data has been collected.

 ## 8. Preserve separate IMU information

 The controller provides:

 * accelerometer
 * gyro
 * Euler orientation

 Preserve access to the raw sensor measurements.

 Do not assume that the controller's Euler orientation is an authoritative fused heading unless its filtering algorithm is documented or experimentally haracterised.

 Document the distinction between:

 * raw IMU measurements
 * controller-derived Euler orientation
 * ROS-side fused localisation

 ## 9. Prepare for ROS-side sensor fusion

 Do not implement a complex estimator inside the chassis driver.

 The driver should expose clean measurements so another package can later fuse:

 * wheel odometry
 * body velocity
 * IMU
 * LiDAR localisation
 * visual odometry
 * GNSS if added later

 Keep `robot_localization` EKF/UKF as the likely ROS-side fusion layer, but do not couple the low-level driver to it.

 ## 10. Humble acceptance criteria

 Before moving to Jazzy:

 * workspace builds cleanly under Humble
 * existing `/cmd_vel` behaviour remains compatible
 * `/odom`, `/imu` and `/limo_status` remain available
 * wheel odometry is exposed rather than discarded
 * raw-frame inspection can confirm whether actuator frames are present
 * confirmed actuator telemetry is exposed in structured messages
 * diagnostics are available without excessive logging
 * all new protocol interpretations are documented as either confirmed or provisional
 * non-motion tests are recorded
 * any motion tests require explicit approval

 Update the project documentation and TODO as each stage is completed.

 ---

 # Phase 2 — Jazzy

 Only begin this after the Humble implementation above is working.

 Port the **validated Humble driver**, rather than independently modifying the old AgileX Jazzy/Humble code.

 ## Jazzy goals

 * ROS 2 Jazzy / Ubuntu 24.04
 * same protocol implementation and ROS interfaces as the validated Humble driver
 * preserve message definitions where possible
 * preserve topic names and parameters unless a deliberate migration is documented
 * update CMake/package metadata only where required for Jazzy
 * remove genuinely obsolete ROS APIs rather than adding compatibility hacks
 * ensure namespace support remains configurable

 ## Jazzy validation

 Compare Humble and Jazzy side-by-side for:

 * chassis status
 * wheel odometry
 * IMU
 * motion state
 * actuator telemetry
 * diagnostics
 * raw-frame decoding

 Given the same controller data, the two implementations should produce equivalent ROS-visible values.

 Once parity is established, Jazzy becomes the main development branch and Humble remains the known-good reference implementation.

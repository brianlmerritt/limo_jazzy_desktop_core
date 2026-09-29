# LIMO scan adapter

Standalone ROS 2 adapter for drivers that encode missing LaserScan readings as
zero. Invalid readings (nonfinite, zero, below range_min or above range_max) become
NaN. Valid ranges, beam count, ordering, frame, timestamps and intensities remain
unchanged. Invalid range limits cause that scan to be rejected with an error.
NaN represents an unknown measurement, not a detected obstacle or confirmed free
space. This node does not publish TF or movement commands.

Build with `colcon build --packages-select limo_scan_adapter` in a ROS workspace.
Run `ros2 run limo_scan_adapter scan_sanitizer`. Input is `scan_raw`, output is
`scan`, both sensor-data QoS LaserScan topics. Use ROS namespace and remapping
arguments to select topics; do not remap input and output to the same topic.
There are no deployment files, framework dependencies or custom parameters.

Test with `colcon test --packages-select limo_scan_adapter` and `colcon test-result`.

# Namespaced navigation and exploration

The owner approved `src/ros2_navigation/` for non-device navigation source
submodules on 2026-09-07. The guarded source workflow supports this parent.
The chassis remains owner-managed. Navigation libraries come from Jazzy apt
packages inside Docker; explore_lite is pinned in the source configuration.

The robot namespace is `limo1_explorer`, declared in platform.container.ros_namespace.
Topics, actions, nodes and TF topics are scoped to the robot. Frame IDs remain
local (`map`, `odom`, `base_link`, `laser_frame`) on its private TF topics.
Framework adapters remap absolute upstream topics without modifying components.
No extra odometry/IMU fusion is introduced. Navigation and exploration require
explicit startup and are never started by ordinary chassis bringup.

Hardware geometry starts from the existing description and requires visual
verification against the physical installation before autonomous motion.

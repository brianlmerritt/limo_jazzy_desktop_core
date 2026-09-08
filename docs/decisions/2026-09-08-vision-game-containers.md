# Pose vision and game deployment

Owner requested both YOLO26 nano and small pose models in Docker, selectable at
runtime, plus navigation, YOLO, exploration and game launch modes. Use a dedicated
vision image extending the existing Jazzy dev image. Keep the current camera
publisher; inference subscribes to ROS RGB/aligned-depth messages. CUDA inference
is explicit and fails startup if unavailable; it does not silently fall back to
slow CPU operation. CPU is an explicit diagnostic option.

New standalone ament_python packages live in the owner-created
src/ros2_hide_and_seek submodule. This exact path is approved for read/build
configuration but remains outside automatic source mutation/removal. They
receive native ROS parameters/topics, never framework paths. Docker copies and
builds them into /opt/autonomy-install. The framework supplies namespace and
model choice. The remote is https://github.com/brianlmerritt/ros2_hide_and_seek.git.
The owner staged its registration; integration preserves that staging and adds
the package files without committing or publishing them.

The first game coordinates explore_lite through its native resume topic; only
explore_lite sends Nav2 goals. A found event pauses exploration. This is explicitly
a frontier-search prototype; semantic viewpoint selection on a complete map and
person identity are future work. Full nav startup sends no goal; explore/game
commands are explicit autonomous movement triggers. No live floor test performed
as part of this setup.

## Validation completed

- Both pinned pose weights loaded on Orin with torch 2.10.0+cu130 / CUDA 13.0.
  Five warm predictions of one live 640x480 ROS camera frame measured median
  45.3 ms nano and 42.8 ms small. This small sample establishes functionality,
  not relative model speed, detection accuracy or worst-case throughput.
- Live ROS inference passed nano -> small -> nano switching. An explicit Image
  subscriber received the 640x480 bgr8 pose overlay. Nano was left running;
  chassis, navigation and exploration remained stopped.
- 72 framework regression tests passed; colcon reported three component tests,
  zero errors/failures/skips. The game decision fixture passed stale/fresh vision
  handling and confirmed-find pause. Exploration and the combined game launch
  passed against a synthetic map and fake Nav2 on isolated DDS domain 174.
- Source-pin validation passed for the existing modules; compose config,
  shell syntax and git diff whitespace validation passed.
- Owner-created submodule registration is integrated. Package files remain
  uncommitted in that submodule; its initial commit remains the source pin.

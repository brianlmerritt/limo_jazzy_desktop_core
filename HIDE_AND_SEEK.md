# Hide and seek with the grandchildren

Status: future project / research-backed to-do plan. Research checked 7 September
2026 and updated 8 September 2026. The final section records the implemented
alignment policy and revised autonomy plan. This document does not enable
autonomous play or install anything.

## Intended experience

Map the downstairs rooms, let the children hide in agreed places, then have LIMO
visit safe observation positions and announce when it sees somebody. Start with
one room and an adult supervising. Expand to the downstairs floor only after
reliable navigation and detection. Upstairs is a separate milestone requiring
validated protection against falling down stairs.

The first version seeks people; it does not chase them, squeeze into hiding
places, open doors, or physically tag anyone. Finding someone means observing
and announcing from a stand-off position. Fully hidden people cannot be seen
through furniture: choose another viewpoint or offer a playful hint request.

## Starting point and outstanding prerequisites

- [x] ROS 2 Jazzy, Nav2, SLAM Toolbox and the explore_lite source are available in
  Docker under the `limo1_explorer` namespace.
- [x] Chassis heading correction passed software tests and a supervised turn:
  14.5 degrees IMU and odometry, approximately 14 degrees from LiDAR.
- [x] Owner confirmed the corrected 180-degree LiDAR mounting orientation.
- [x] RealSense D435i RGB and point cloud work; RViz has a persistent Image view.
  The bench stream measured approximately 15 fps at 640x480.
- [ ] Complete the physical half-metre Nav2 test. The previous attempt was
  interrupted by battery failure; it is not a passed test.
- [ ] Resolve or bound the intermittent chassis-node disappearance and startup
  discovery/TF failures. A process being alive is not proof that data are fresh.
- [ ] Measure the camera-to-chassis transform. Current object distances are
  camera-relative, not ready-made navigation coordinates.
- [ ] Measure the full footprint, protrusions, turning clearance and stopping
  distances on carpet and tile, including low battery and maximum intended load.

The robot is currently on blocks using a lab PSU. Camera/software work is
appropriate in this state; floor navigation is not validated by spinning wheels
on blocks. See [navigation checkpoint](docs/software/navigation-checkpoint.md).
No extra IMU/odometry fusion node is proposed at this stage.

## Phase 1 — a dependable downstairs map

- [ ] Survey doors, thresholds, narrow gaps, rugs, cables, glass, low furniture
  and any changes in floor level. Draw an initial permitted play boundary.
- [ ] Map with SLAM Toolbox under adult supervision, initially by deliberate
  short routes. Save both an occupancy map and the SLAM pose graph if continued
  mapping is desired. SLAM Toolbox supports mapping and localization workflows.
  [SLAM Toolbox](https://github.com/SteveMacenski/slam_toolbox)
- [ ] Use explore_lite only during a bounded mapping session after supervised
  goals work. Frontier exploration discovers unknown map space; it does not
  reason about children or hiding places, and its default startup initiates
  exploration. [ROS 2 exploration source](https://github.com/robo-friends/m-explore-ros2)
- [ ] Freeze a reviewed map for games and configure localization against it
  (evaluate AMCL versus SLAM Toolbox localization). Avoid continuously changing
  the play map because a child moves a chair or sits behind a sofa.
- [ ] Add named rooms, doorway transitions, safe observation poses and a home
  pose. Keep these semantic annotations separate from the occupancy image.
- [ ] Add forbidden areas and slow zones. Include keepout filters in both global
  and local costmaps; verify the chosen margins with the actual footprint.
  Map masks remain dependent on correct localization.
  [Jazzy keepout tutorial](https://docs.nav2.org/jazzy/tutorials/general_tutorials/navigation2_with_keepout_filter/navigation2_with_keepout_filter/)
- [ ] Re-localize after carrying the robot, changing floors or resetting odometry.
  Never reuse a downstairs pose upstairs.

Acceptance: repeat room-to-room routes with changed door states and temporary
obstacles; stop rather than push through a blocked doorway. Log actual outcomes,
not only Nav2 success flags. Start the game only after the adult enables it.

## Phase 2 — camera coverage and hiding places

Measure the mounted camera height, pitch, yaw and clearance; do not choose angles
from a screenshot alone. Use the active CameraInfo and calibrated extrinsics.
OpenCV provides calibration, projection and pose-estimation primitives.
[OpenCV calibration](https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html)

- [ ] Capture a coverage grid: standing adult, child-height target, seated target,
  crouched target, partly visible head/arm, and floor-level target at several
  distances. Begin with props/adults before involving children.
- [ ] Test a fixed camera first. Compare level and modest upward/downward pitches
  for the actual mounting height; record near blind spots and RGB/depth overlap.
- [ ] Evaluate a pan/tilt mount only if stationary coverage is inadequate. It
  needs joint transforms, repeatable limits and protected pinch points. A raised
  mount also changes footprint clearance and stability.
- [ ] Keep a dedicated downward floor sensor fixed if the viewing camera tilts.
  Looking up at a child must not remove ground coverage.
- [ ] Measure distances from valid depth points inside an object's mask, excluding
  background and edge pixels. Reject sparse, stale or inconsistent depth. Use
  full image calibration, synchronized timestamps and TF before map placement.
- [ ] Test doors/glass, bright windows, dark fabric and shiny surfaces. Our office
  capture already produced unreliable glass returns; a numeric depth is not
  automatically a valid surface measurement.

For each hiding place record: room, description, permitted observation poses,
expected occlusion, camera angle, stand-off limit and forbidden approach area.
Examples: look behind the side of a sofa from the doorway; look under a table
from outside its legs. Do not drive into the hiding place or pin a child against
furniture. Never invite hiding on stairs or in unsafe enclosed spaces.

## Phase 3 — vision libraries and model shortlist

These are candidates for benchmarks, not claims of measured performance on this
8 GB Jetson. Use the existing 15 fps input initially, dropping old inference
frames instead of building an increasing queue. Pin library versions, model
weights and licenses when selecting a stack.

| Candidate | Proposed job | Why evaluate it / limitations | Delivery approach |
|---|---|---|---|
| OpenCV + NumPy | Calibration, masks, overlays, geometry and simple baselines | Small starting layer; does not itself supply robust hidden-person recognition | Ubuntu packages or pinned Python packages inside Docker |
| Ultralytics YOLO11n detector, then nano segmentation/pose if needed | Person candidates and visible body regions | Start with a small established model; compare current nano alternatives on our scenes rather than selecting by release date | Pinned Python package and separately pinned weights; assess its AGPL/enterprise options |
| ByteTrack or BoT-SORT via Ultralytics | Temporal person tracks | Reduces repeated announcements; a track ID is not identity and can change after occlusion | Included tracking integration; configure and benchmark |
| MediaPipe Pose Landmarker | Optional posture/keypoint evidence | Useful for visible people; do not require a complete skeleton to find a partly hidden child | Verify Linux ARM64/Python wheel support before committing; source build may be needed |
| AprilTag | First-game props, known observation markers or optional wearable tokens | Deterministic, easy to score; only works when a tag is visible and is optional for the game | Pinned upstream source/appropriate ROS adapter |
| Open3D or PCL | Point-cloud filtering, clustering and floor-plane prototypes | Useful offline and in bounded live processing; benchmark memory and CPU cost | Prefer distro packages where suitable, otherwise pinned container build |
| Grounding DINO | Experimental text-conditioned search for objects/body parts | Useful for semantic experiments; latency and false detections need evaluation | Pinned upstream source/model in a separate experiment container |
| SmolVLM2-500M-Video-Instruct | Occasional scene descriptions and playful commentary | Small VLM candidate; test whether it describes these low-angle scenes accurately; never treat generated text as a measured distance | Pinned Transformers/model dependencies; benchmark local inference |
| Isaac ROS acceleration | Later optimization of a demonstrated bottleneck | Release-specific Jetson/JetPack/CUDA/ROS requirements; not a drop-in assumption for this Ubuntu 24.04 Orin installation | Verify the exact support matrix before adopting its containers/packages |

Primary references: [Ultralytics models/source](https://github.com/ultralytics/ultralytics),
[tracking integration](https://docs.ultralytics.com/modes/track/),
[MediaPipe pose](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker),
[AprilTag](https://github.com/AprilRobotics/apriltag),
[Open3D point-cloud operations](https://www.open3d.org/docs/release/tutorial/geometry/pointcloud.html),
[Grounding DINO](https://github.com/IDEA-Research/GroundingDINO),
[SmolVLM2 model card](https://huggingface.co/HuggingFaceTB/SmolVLM2-500M-Video-Instruct),
[Isaac ROS platform requirements](https://nvidia-isaac-ros.github.io/getting_started/index.html).

Recommended first experiment: AprilTag/prop baseline, followed by a small person
detector plus depth and tracking. Add VLM narration only after that baseline
works. Run inference locally initially; no cloud upload of children's imagery
by default. Use ephemeral game IDs rather than face recognition. Any retained
clips should be explicitly agreed with the family and easy to delete.

Benchmark identical recorded scenes for: missed partly visible people, false
finds per minute, time to confirm a person, track swaps, distance error against
measured targets, p50/p95 latency, peak RAM, GPU load, temperature and concurrent
Nav2/TF timing. Include posters/reflections, adults, multiple people, low light,
children sitting/crawling and toys. COCO person accuracy is not a substitute for
these tests. A provisional detector target is 5–10 updates/second; measure
feasibility rather than promising it. Navigation must remain responsive under
worst-case inference load.

## Phase 4 — game behaviour

Proposed state machine:

`idle -> adult starts -> count down -> visit observation pose -> look -> verify
candidate -> announce found -> continue or return home`

Any state can enter `paused/fault`; recovery requires fresh valid inputs and an
explicit resume policy. A restart returns to idle, not an old chase/search goal.

- [ ] Implement a small deterministic game coordinator. Use existing Nav2 actions
  for approved observation poses; permit only one navigation goal owner.
- [ ] Pick viewpoints based on visibility and rooms already checked. Randomize
  ties for variety. Do not use frontier exploration to pursue a person mid-game.
- [ ] Stop at each viewpoint, inspect several frames, and require consistent
  evidence before announcing. Permit adult confirmation in early versions.
- [ ] If occluded, choose a safe alternate viewpoint or say “I need a clue”.
  Store “not observed”, not “room definitely empty”.
- [ ] Start with one seeker and one hider. Later distinguish tracks across a
  round and handle someone leaving/re-entering view without repeatedly winning.
- [ ] Add modest sound/light feedback and a visible pause button. Voice stop
  recognition can supplement, but must not replace, a physical stop control.
- [ ] Stop/slow near any person, including an undetected child occupying the
  depth/laser obstacle region. Test ankles and hands below the 2D scan plane.
- [ ] Suppress blind automatic backup/spin recoveries around people or edges;
  stop and ask the adult when safe recovery cannot be established.

AI may suggest a named viewpoint or sentence. Validate suggestions against the
allowed map/poses; AI must not publish velocity commands or override a stop.

## Phase 5 — upstairs and stair-edge protection (separate prerequisite)

**Do not operate near an unprotected stair opening with the current setup.**
A horizontal 2D LiDAR detects surfaces in its scan plane, not dependable support
under the wheels. An obstacle-free costmap is not evidence of a floor. Carrying
the robot upstairs is permitted as a future workflow; autonomous stair climbing
or descending is outside this project's scope.

The following is a proposed engineering design, not a certified protection system:

1. Start with a physical barrier across the stairs, an adult present, and a
   conservative keepout region. Keep the barrier during development even when
   software appears to work. Do not rely on localization alone for edge safety.
2. Evaluate dedicated downward-looking short-range sensors ahead of the wheels,
   covering front, rear and lateral swept paths during turns. Compare multiple
   ToF/IR ranging sensors and a downward depth view; select hardware only after
   tests on the actual floor materials. No sensor purchase is assumed here.
3. Estimate expected ground height and support across the upcoming wheel paths.
   Detect a drop in support, a depth discontinuity or insufficient valid ground
   observations. Treat invalid/missing/occluded readings as a reason to stop,
   not as confirmation that the floor is clear.
4. The existing D435i can prototype ground-plane analysis, but its minimum usable
   range, mounting geometry and active stream profile determine the blind area.
   A front camera tilted toward faces cannot be the only cliff sensor.
   [D435i product specifications](https://www.realsenseai.com/products/depth-camera-d435i/)
5. Add a latched cliff-stop input independent of semantic AI. Prefer an
   independent watchdog/motor-inhibit path that still works if ROS or the
   computer hangs; establish the chassis electrical interface before designing
   it. Do not assume dropping all power guarantees the best mechanical braking.
6. Integrate the same hazard into the software command gate. Nav2 Collision
   Monitor supplies stop/slowdown and sensor-timeout mechanisms, but is not
   safety-certified and does not automatically turn absent floor returns into
   a cliff event. A dedicated detector and explicit stop integration are needed.
   [Jazzy Collision Monitor](https://docs.nav2.org/jazzy/configuration_and_development/configuration_guide/core_servers/collision_monitor/configuring_collision_monitor_node/)

Size the sensing look-ahead using measured worst-case stopping performance:

`required wheel-to-edge reserve > v * total_latency + v² / (2 * minimum_deceleration) + margin`

This is a preliminary straight-line estimate, not a guarantee. Include sensor
position relative to the foremost wheel, body overhang, turn sweep, downhill
coasting, traction, scheduling delays and actuator response. Measure reverse and
rotational stopping separately; do not copy a nominal distance from a datasheet.

- [ ] Replay synthetic/recorded drops with wheels supported; then use a protected
  shallow mock edge with a catch platform/tether and an adult. Never prove the
  first implementation by driving toward the real stairs.
- [ ] Test all approach angles, reverse/turn manoeuvres, carpet edges, dark rugs,
  polished tile, direct light, sensor blockage, unplugged sensors, stale data,
  CPU/GPU overload, ROS crash and power interruption.
- [ ] Record detection-to-stop latency and remaining wheel support in every test.
  Set measurable pass criteria before trials. Any missed edge blocks upstairs
  use; a finite set of successful trials does not establish general safety.
- [ ] Make a separate upstairs map and keepout mask behind the barrier. Select
  the floor explicitly after carrying and validate localization before enabling
  commands. Never explore toward unknown space adjacent to the stairwell.

## Component boundaries and deployment

Use the apt-installed Nav2/SLAM stack and existing approved explore_lite submodule.
Install experimental Python/C++ libraries in Docker only. Verify apt availability
on ARM64 and pin versions; do not replace stable drivers to try a model. Export
or accelerate a detector only after a baseline works, checking exact CUDA,
TensorRT, JetPack and model compatibility on this machine.

Proposed separate components: person perception, scene description, game
coordinator, and ground-support/cliff monitor. Each should accept native ROS
parameters/topics/actions and own its tests; the framework supplies namespace,
calibration, devices and play-area files. Seek owner agreement on where new AI
or game source packages belong before creating a new source parent. This plan
creates no new component dependency on the framework configuration.

## Prioritized backlog and deferred decisions

| Priority | Deliverable | Evidence needed before advancing |
|---|---|---|
| P0 | Stable motion, heading, transforms and power/session handling | Repeated supervised short goals, clean stops and recovery from sensor/process loss |
| P1 | Downstairs map and permitted play area | Reviewed room map, doorway tests, keepouts and saved localization workflow |
| P1 | Camera extrinsics and coverage report | Measured target locations, low/occluded target coverage and depth-error results |
| P2 | Stationary find-a-prop/person demo | Annotated recordings, false-find/missed-find counts and resource measurements |
| P2 | One-room adult-supervised game | Approved viewpoints, reliable pause/stop and no chasing or contact |
| P3 | Multiple downstairs rooms and playful narration | Repeatable search rounds without impairing navigation timing |
| Separate gate | Upstairs protection | Physical barrier, dedicated sensing/interlock tests and reviewed stopping margins |

Later decisions, not questions requiring answers tonight: permitted rooms and
hiding places; grandchildren's age/height ranges relevant to coverage; camera
mount options; sensor budget; game sounds; desired use of tags; retention of test
clips; whether an additional stationary room camera is desirable. External
cameras would be optional game sensors, not substitutes for onboard collision
or cliff protection.

Next practical step is still the supervised half-metre floor-navigation test,
then a small downstairs mapping session. No new hardware or model installation
is required to finish that prerequisite.

## Autonomous operation update — 8 September 2026

The intended outcome is autonomous floor mapping and adaptive seeking, not a
fixed sequence of waypoints or a system requiring a restart whenever moved.
The earlier supervised routes are validation exercises, not the final mission
planner. RGB/depth recognition is a future input; current navigation still uses
2D LiDAR, odometry, SLAM and Nav2.

### Implemented now: alignment policy

- [x] Keep the corrected scanner mount fixed and orientation checking enabled by
  default. Check mount/odometry and scan/map evidence separately at 1 Hz.
- [x] Add `config/robot/alignment-policy.json`: agreement, orientation disagreement,
  map disagreement, both disagreeing, insufficient geometry and unavailable
  evidence each select continue/slow/hold. **Every row defaults to continue.**
- [x] Remove alignment latching; sensor-health holds also recover automatically.
  Collision stops, command freshness and forward-only enforcement remain.
- [x] Publish the selected row/action and supporting measurements on
  `navigation_guard/status` for a future mission coordinator.

The matrix currently changes velocity handling only. It does not switch pose
estimators or implement autonomous re-localization. SLAM Toolbox owns
`map -> odom`; chassis odometry owns `odom -> base_link`; the scanner mount stays
rigid. Existing `slam.yaml` enables scan matching and loop closure, so LiDAR
already contributes to correcting map pose. It is usable for mapping with the
corrected orientation, subject to the outstanding physical navigation tests.

A scan/map match is evidence conditional on the estimated pose, not an
independent compass. A newly built map can match a wrongly interpreted scan;
repeated corridors can support several plausible locations. Neither missing
returns nor a high overlap score can prove a unique heading after being carried.
SLAM Toolbox provides pose initialization/localization interfaces, but those
need a valid pose hypothesis; arbitrary relocation is not solved merely by
turning scan matching on. [SLAM Toolbox interfaces](https://github.com/SteveMacenski/slam_toolbox)

### To do: pose recovery without routine operator intervention

- [ ] Add an estimator adapter with a native contract: candidate map pose,
  timestamp, score, score definition, covariance/uncertainty and evidence age.
  Do not interpret the current endpoint-match fraction as a calibrated probability.
- [ ] Separate a mount configuration discrepancy from a robot-pose discrepancy.
  Never change the scanner mount to explain a carried robot.
- [ ] Prefer a uniquely supported LiDAR/map pose for global localization;
  retain wheel/IMU odometry for short-term motion prediction. Compare candidate
  poses in one frame and timestamp before declaring disagreement.
- [ ] For large relocation, generate candidates over the permitted floor map,
  test several fresh scans, and require a margin over competing candidates.
  Publish accepted initialization through the chosen SLAM/localization native
  interface; keep exactly one owner of each TF edge.
- [ ] Rate-limit updates and require persistence/hysteresis before changing
  hypotheses. Invalidate/replan an old goal when its map pose changes materially.
- [ ] Record ambiguous/unresolved outcomes. Continue advisory reporting with the
  current policy; do not report a successful recovery unless measured evidence
  supports it. A future bounded recovery policy should expire stale missions
  rather than repeatedly attempting the same inaccessible goal.
- [ ] Test translated/rotated pickup cases using recorded/synthetic scans first,
  including two similar corridors and relocation between floors. Select the
  floor explicitly until multi-floor recognition is demonstrated.

### Recognition stack for this Orin Nano 8 GB

Local read-only inventory today: L4T 39.2.1, NVIDIA container toolkit 1.19.1 and
registered `nvidia` Docker runtime. This does not establish that the current ROS
image has usable CUDA/TensorRT/PyTorch. Keep all inference dependencies in a
separate reproducible Docker image and exchange ROS messages through native
interfaces. No host installs or inference packages were added by this update.

Recommended benchmark stack:

1. OpenCV/NumPy for RGB preparation and depth geometry; Ultralytics YOLO11n as
   the existing baseline candidate, compared with current YOLO26n. Start with
   person detection, adding segmentation only if background depth contamination
   justifies it. Use existing tracking support to stabilize observations.
2. Export the selected small model to TensorRT FP16 on the target-compatible
   stack. Start at 640 input, batch one, newest-frame-only queue, provisional
   5–10 inference Hz. These are test settings, not measured throughput promises.
3. Combine detections with aligned depth: robust median/interquartile spread of
   valid interior pixels, minimum valid fraction, and timestamps. Report optical
   Z versus Euclidean range explicitly. Transform positions with measured camera
   extrinsics before using them for map goals; unknown depth remains unknown.
4. Keep heavy open-vocabulary/VLM models optional and off the continuous control
   path. Start with detector + tracker + measured depth, then benchmark occasional
   scene descriptions against the remaining memory and latency budget.

Ultralytics documents Orin deployment and recommends TensorRT, but its current
JetPack 7 container guidance does not claim every image supports Orin on 7.2.
Do not blindly pull a generic `latest` image or generic ARM64 GPU wheel.
[Jetson deployment guide](https://docs.ultralytics.com/guides/nvidia-jetson/)
TensorRT compatibility depends on platform and version; treat serialized engines
as target-specific unless the documented compatibility conditions are met.
[NVIDIA support matrix](https://docs.nvidia.com/deeplearning/tensorrt/latest/getting-started/support-matrix.html)

- [ ] Capture exact host driver, container CUDA, TensorRT, Python and PyTorch
  versions; prove GPU access and a small inference before choosing pins.
- [ ] Pin image digest, model checksum and license alongside preprocessing settings.
- [ ] Measure total shared RAM with camera, SLAM, Nav2 and RViz active. Require
  at least 1.5 GB observed headroom as an initial engineering target; avoid swap
  growth and stale ROS data under load. Reduce model/input/rate before adding AI.
- [ ] Compare partly hidden-person recall, false finds, p95 end-to-end latency,
  depth error and system resource use. Benchmark with camera-relative distances
  first; do not silently promote them to navigation coordinates.

### To do: configurable mission decisions and adaptive routes

Use Nav2's existing BehaviorTree.CPP-based navigation execution, with a small
mission coordinator owning the single active goal. Nav2 already supports
feedback-based replanning; the coordinator decides **where to search next**.
[Nav2 behavior trees](https://docs.nav2.org/behavior_trees/index.html)
Keep policy thresholds/weights in configuration and transitions in tested code.
No language model should be required to keep planning or to recover a blocked
route. Proposed rules below are design work, not implemented robot behavior.

Evaluate mission rules in priority order; each records its reason and transition.
Use freshness, minimum dwell times and bounded retries to avoid rapid switching.

| Evidence / condition | Proposed decision | Automatic next step |
|---|---|---|
| Collision or stale required sensor | Inhibit commands via existing protection | Resume only with fresh clear evidence and still-valid mission |
| Fresh scan/map agrees; odometry discontinuity | Prefer accepted SLAM pose for global planning | Replan from current pose; retain rigid mount |
| Map mismatch or competing location hypotheses | Mark pose uncertain; apply alignment matrix | Collect/score localization candidates; report ambiguity honestly |
| Mapping mode, reachable frontiers exist | Select highest-value frontier | Nav2 plans a fresh route from the current pose |
| Frontier/door repeatedly blocked | Temporary exclusion with expiry | Select another frontier/room; revisit if evidence changes |
| No reachable frontier | Check coverage and inaccessible regions | Save map, report completion or partial completion, return home if reachable |
| Search mode, person candidate seen | Visit/retain a valid observation pose | Confirm over frames and valid depth before announcing |
| Candidate occluded / depth unreliable | Do not claim a find or fabricate range | Select a different visible, reachable viewpoint |
| Area recently inspected without detection | Lower its immediate priority | Search another area; retain uncertainty about hidden people |
| Low energy / mission budget reached | End search | Return home if reachable, otherwise finish in a permitted position |

For autonomous mapping, first use the existing explore_lite frontier selection;
it selects goals from the changing occupancy grid rather than replaying a fixed
route. It is not a semantic game planner. Evaluate its existing travel/gain and
progress controls before replacing it. [Existing exploration implementation](https://github.com/robo-friends/m-explore-ros2)

For the later coordinator, generate candidate frontiers in mapping mode and
observation viewpoints in search mode. Reject forbidden or unreachable candidates
first, then rank normalized features:

`utility = w_gain * expected_visibility_gain + w_person * person_evidence
         - w_travel * path_cost - w_recent * recent_visit_penalty
         - w_failure * recent_failure_penalty`

Use different configurable weights for mapping and games. Travel cost comes from
an actual planned path, not straight-line distance through walls. Visibility gain
accounts for camera field of view and occlusion; unexplored map area alone does
not mean a useful view of a hiding place. Recompute after observation, map/door
changes, goal outcomes and a bounded timer. Commit briefly to the chosen target
to prevent oscillation. Randomize near-ties with a logged seed; do not randomize
into forbidden areas just to make routes different.

- [ ] Define mission modes idle/map/search/return and an explicit startup trigger.
  Starting ROS does not automatically launch a game or exploration mission.
- [ ] Build the configurable rule evaluator and a single-goal coordinator; reuse
  Nav2 action feedback/cancellation rather than publishing direct velocities.
- [ ] Store visited viewpoints, last inspection time, blocked-door expiry and
  person-track evidence across a round. Separate persistent map from round memory.
- [ ] Test route diversity with identical rooms but changed door/obstacle/person
  evidence. A good planner may legitimately reuse the only viable corridor.
- [ ] Replay the same scenario and seed for deterministic regression testing;
  assert bounded retries, no goal-owner conflicts and eventual completion/report.

The runtime alignment matrix is implemented now. Global pose recovery, GPU
recognition, and the richer mission coordinator remain explicit to-do work.
Existing explore_lite is the available autonomous mapping baseline; this update
has not launched exploration or moved the robot.

## Docker launch implementation — 8 September 2026

- [x] Separate `Dockerfile.vision` with pinned CUDA PyTorch/Ultralytics and both
  YOLO26 nano/small pose weights included. Runtime model selection uses the
  `nano` or `small` argument; inference uses CUDA FP16 PyTorch initially. TensorRT
  engine export remains a later optimization, not a claim of this implementation.
- [x] ROS image subscriber with pose keypoints, person boxes, optional approximate
  optical-depth statistics, and an RViz overlay topic. Original camera feeds stay
  intact for independent depth/drop research.
- [x] Four host launch modes through `scripts/launch-robot.sh`: `nav`,
  `yolo nano|small`, `explore`, and `hide-and-seek nano|small`.
- [x] Existing pinned explore_lite package verified; no duplicate install/source.
- [x] First hide-and-seek ROS prototype: one explorer owns Nav2 goals, fresh vision
  permits search, consecutive detections produce a found event and pause search.
  Stale images pause exploration, and timeout/no-frontiers produce explicit states.
- [x] Integrate the owner-created `src/ros2_hide_and_seek` submodule containing
  limo_vision and limo_hide_and_seek. Package additions remain uncommitted.

This prototype searches frontiers while mapping. It does not yet inspect a set
of viewpoints on a fully mapped floor, recognize individual children, infer
lying posture reliably, speak announcements, or provide stair/drop protection.
Those remain the earlier backlog. See the standalone package README for native
parameters, topic schemas, units and test commands, and ROS2_INSTRUCTIONS.md for
host launch commands. Setup/validation does not itself authorize floor motion.

Validation of this implementation: both models ran on the Orin GPU from a live
640x480 ROS camera frame; nano/small/nano live switching and the annotated Image
output passed. Five warm predictions measured about 43–45 ms per model, which
is not an accuracy test or sustained-load guarantee. The 72 framework tests,
three registered component tests, isolated game decisions and combined game
launch with fake Nav2 passed. Nano is left running for inspection; motion
services were not started. The owner-created submodule is now integrated at src/ros2_hide_and_seek.

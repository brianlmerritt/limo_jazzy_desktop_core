# Repository Guidelines

## Project Scope and Layout

This repository owns the reproducible development environment and platform configuration for an AgileX LIMO on a Jetson Orin Nano 8 GB. The host is newly flashed Ubuntu 24.04; keep it as clean as possible.

- `Dockerfile`, `compose.yaml`, and `.devcontainer/` define container workflows.
- `src/limo_ros2/` is the LIMO ROS 2 fork, maintained as a Git submodule. Keep this existing chassis checkout in place. Non-ROS SDKs and hardware libraries belong under `drivers/<name>/`; ROS 2 sensor/device submodules belong under `src/ros2_devices/<name>/`. Owner-approved navigation/exploration submodules belong under `src/ros2_navigation/<name>/`. Ask the owner before introducing another parent folder, including future AI or non-device ROS work.
- `src/ros2_hide_and_seek/` is the owner-created ROS 2 vision/game submodule. This exact path is approved and owner-managed, like the chassis checkout; it does not expand automatic mutation/removal to arbitrary `src/` paths.
- `config/{robot,cameras,lidar,networking}/` holds tracked device and runtime configuration.
- `scripts/` contains repeatable setup, build, and host-configuration scripts.
- `docs/hardware/` documents wiring, drivers, device names, and manual host steps; `docs/decisions/` records design choices.
- `host/snapshots/` stores useful diagnostic captures. Never commit generated `build/`, `install/`, or `log/` trees.

## Environment and Host Policy

Put Python, ROS 2, ROS packages, build tools, and application dependencies in Docker. Do not install them on Ubuntu 24.04 merely for convenience. Only hardware access, Docker/JetPack support, and unavoidable kernel/device-driver changes belong on the host. Every host modification must have an idempotent script where feasible and accompanying documentation describing purpose, commands, affected files, verification, and rollback. Do not assume stable `/dev/ttyUSB*` names; capture identifiers and define persistent rules under repository configuration before relying on them.

## Component Boundaries and Configuration

Keep repositories and reusable components under `src/` and `drivers/` independently buildable, runnable, configurable, testable, and documented. They must not read this framework's root `config/`, Compose files, `.env`, or helper scripts directly. A component owns its public runtime contract and safe standalone defaults; the outer framework translates platform-specific configuration into that contract and validates the translation.

Use the narrowest native interface for each value: ROS parameters for ROS node behavior, command-line arguments for tools, environment variables for deployment-level defaults, and component-owned files for structured configuration. Unless a component documents a different precedence, use explicit parameter or argument, then environment value, then standalone default. Document names, types, accepted values, precedence, and safety effects within the component that consumes them.

Keep hardware discovery, host paths, udev rules, secrets, and deployment topology in the outer framework. Pass only the selected devices and values across the component boundary. Validate values both where the framework produces them and where the component consumes them; do not rely on duplicated unchecked constants. Normal declared build and runtime dependencies do not violate self-sufficiency.

For an externally maintained repository that should not be changed, prefer a sibling adapter package or launch/configuration overlay. If a task appears to require a component to depend on this framework, or the appropriate boundary is unclear, stop implementation and discuss the interface and tradeoffs first. Record an accepted exception under `docs/decisions/` before introducing the dependency.

## Development Commands

- Keep `ROS2_INSTRUCTIONS.md` synchronized whenever container startup, build,
  passive-check, or ROS bringup commands change.
- `./scripts/configure-host-env.sh`: create the ignored UID/GID `.env` file.
- `docker compose build dev`: build the selected development image.
- `docker compose up -d dev && docker compose exec dev bash`: start and enter it.
- `./scripts/build.sh`: run `colcon build --symlink-install` inside the container.
- `colcon --log-base log/jazzy test --build-base build/jazzy --install-base install/jazzy` then `colcon test-result --test-result-base build/jazzy --verbose`: run and inspect package tests.
- `./scripts/host-check.sh`: capture host, Jetson, Docker, USB, and network state.

This `jazzy` branch targets Ubuntu 24.04 / ROS 2 Jazzy in Docker. Container validation comes first; the inherited Humble hardware source pins still need separate Jazzy compatibility validation. Use distro-specific build, install, and log directories through the framework helpers.

## Style and Testing

Use Bash with quoted variables, two-space indentation, kebab-case filenames, and `set -euo pipefail` unless a diagnostic script intentionally tolerates failures. Use standard ROS naming (`snake_case` packages, nodes, topics, and parameters), four-space Python indentation, and package ament linters. Add focused tests to each package and register them in `CMakeLists.txt` or `setup.py`; name Python tests `test_*.py`.

## Git Ownership and Reviews

Agents may use the validated configuration workflow to add, initialize, update, and remove submodules under the agreed parents `drivers/`, `src/ros2_devices/`, and `src/ros2_navigation/`, including staging the affected gitlinks and `.gitmodules`. A removal must also remove that submodule's matching repository under `.git/modules/`; never leave that cache behind after `git rm`. Preflight local changes, ignored/untracked files, and local-only commits before removal. Do not infer removal from a disabled device: declare `state: absent` explicitly in the source configuration. Ask the owner before using another parent folder. The existing `src/limo_ros2/` is outside this automatic mutation scope and remains owner-managed. The owner retains control of unrelated staging, commits, pulls, pushes, branch creation/switching, merges, and rebases. Agents may inspect Git status, history, and diffs. Keep proposed changes focused. In handoff notes, list changed files, validation performed, hardware assumptions, and any manual or safety-sensitive steps. Never commit `.env`, credentials, or generated artifacts.

When completed work requires the user to take a follow-up action, end the final
response with clear, directly executable instructions describing exactly what
the user should do next. Do not leave required user actions only in earlier
commentary, documentation links, or the middle of the handoff.

## Progress and explicit handoffs

At the end of every user-facing response, explicitly state whether the user has
an action to take or whether an assumption needs clarification. If neither is
needed, say so briefly and continue the authorised work rather than ending the
turn with a promise or proposed next step. Do not use a final response merely to
announce work that can already be performed.

End a working turn only when the requested work is complete or progress actually
requires user input or an external change. When input is needed, state the exact
action or question and why it is necessary; continue independent work first.
When work is complete, explicitly say that no user action is required if that
is the case. Do not imply unrequested robot movement is authorised.

### Mandatory continuation check before ending a turn

A final response ends execution; it does not schedule the promised work. Never
write "I will continue", "I will investigate", or an equivalent promise in a
final response while an authorised next step remains executable.

Before every final response:

1. Check the active user request and any unfinished authorised work.
2. If the next step can be performed with available tools, perform it in this
   turn. Use commentary for progress updates, then immediately continue with
   tools. Do not require the user to say "go ahead" again for that work.
3. If a command is still running, collect its result and act on it before ending,
   unless the user explicitly requests stopping or a handoff.
4. End only with completed results, a specific unavoidable blocker requiring
   user input, or an explicit user-requested pause. State which applies.
5. Do not claim work will continue in the background unless a real background
   task has been started and its status is accurately reported.

When the user asks to fix the collaboration workflow first, complete and verify
that change before resuming the technical task. Respect an explicit pause.
Do not substitute repeated apologies, self-criticism, or statements such as
"I stopped when I should have acted" for execution. Report the concrete change
and verification instead. These rules change agent behaviour; they do not claim
to alter VS Code, extension scheduling, or the model's runtime implementation.

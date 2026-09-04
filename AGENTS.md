# Repository Guidelines

## Project Scope and Layout

This repository owns the reproducible development environment and platform configuration for an AgileX LIMO on a Jetson Orin Nano 8 GB. The host is newly flashed Ubuntu 24.04; keep it as clean as possible.

- `Dockerfile`, `compose.yaml`, and `.devcontainer/` define container workflows.
- `src/limo_ros2/` is the LIMO ROS 2 fork, maintained as a Git submodule. Add future camera, LiDAR, and other upstream repositories as sibling submodules under `src/`.
- `config/{robot,cameras,lidar,networking}/` holds tracked device and runtime configuration.
- `scripts/` contains repeatable setup, build, and host-configuration scripts.
- `docs/hardware/` documents wiring, drivers, device names, and manual host steps; `docs/decisions/` records design choices.
- `host/snapshots/` stores useful diagnostic captures. Never commit generated `build/`, `install/`, or `log/` trees.

## Environment and Host Policy

Put Python, ROS 2, ROS packages, build tools, and application dependencies in Docker. Do not install them on Ubuntu 24.04 merely for convenience. Only hardware access, Docker/JetPack support, and unavoidable kernel/device-driver changes belong on the host. Every host modification must have an idempotent script where feasible and accompanying documentation describing purpose, commands, affected files, verification, and rollback. Do not assume stable `/dev/ttyUSB*` names; capture identifiers and define persistent rules under repository configuration before relying on them.

## Component Boundaries and Configuration

Keep repositories and reusable components under `src/` independently buildable, runnable, configurable, testable, and documented. They must not read this framework's root `config/`, Compose files, `.env`, or helper scripts directly. A component owns its public runtime contract and safe standalone defaults; the outer framework translates platform-specific configuration into that contract and validates the translation.

Use the narrowest native interface for each value: ROS parameters for ROS node behavior, command-line arguments for tools, environment variables for deployment-level defaults, and component-owned files for structured configuration. Unless a component documents a different precedence, use explicit parameter or argument, then environment value, then standalone default. Document names, types, accepted values, precedence, and safety effects within the component that consumes them.

Keep hardware discovery, host paths, udev rules, secrets, and deployment topology in the outer framework. Pass only the selected devices and values across the component boundary. Validate values both where the framework produces them and where the component consumes them; do not rely on duplicated unchecked constants. Normal declared build and runtime dependencies do not violate self-sufficiency.

For an externally maintained repository that should not be changed, prefer a sibling adapter package or launch/configuration overlay. If a task appears to require a component to depend on this framework, or the appropriate boundary is unclear, stop implementation and discuss the interface and tradeoffs first. Record an accepted exception under `docs/decisions/` before introducing the dependency.

## Development Commands

- `./scripts/configure-host-env.sh`: create the ignored UID/GID `.env` file.
- `docker compose build dev`: build the selected development image.
- `docker compose up -d dev && docker compose exec dev bash`: start and enter it.
- `./scripts/build.sh`: run `colcon build --symlink-install` inside the container.
- `colcon test && colcon test-result --verbose`: run and inspect package tests.
- `./scripts/host-check.sh`: capture host, Jetson, Docker, USB, and network state.

The current validation target is the Humble fork in an Ubuntu 22.04 container. Jazzy migration belongs on a later `jazzy` branch with an Ubuntu 24.04/ROS 2 Jazzy image.

## Style and Testing

Use Bash with quoted variables, two-space indentation, kebab-case filenames, and `set -euo pipefail` unless a diagnostic script intentionally tolerates failures. Use standard ROS naming (`snake_case` packages, nodes, topics, and parameters), four-space Python indentation, and package ament linters. Add focused tests to each package and register them in `CMakeLists.txt` or `setup.py`; name Python tests `test_*.py`.

## Git Ownership and Reviews

The repository owner manages all Git mutations: staging, commits, pulls, pushes, branch creation/switching, merges, rebases, and submodule registration or updates. Agents may inspect `git status`, history, and diffs, but must not perform those mutations. Keep proposed changes focused. In handoff notes, list changed files, validation performed, hardware assumptions, and any manual or safety-sensitive steps. Never commit `.env`, credentials, or generated artifacts.

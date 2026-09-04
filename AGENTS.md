# Repository Guidelines

## Project Structure & Module Organization

This repository defines the ROS 2 Jazzy development environment for an AgileX LIMO on NVIDIA Jetson. `Dockerfile` supplies the Ubuntu Noble/ROS toolchain, while `compose.yaml` runs the long-lived `dev` container and mounts the repository at `/workspace`. `.devcontainer/` supports the VS Code Dev Containers workflow. Put ROS packages under `src/`; keep robot, camera, LiDAR, and network settings in the matching `config/` subdirectories. Record hardware notes in `docs/hardware/`, architecture decisions in `docs/decisions/`, and host-state captures in `host/snapshots/`. Do not commit generated `build/`, `install/`, or `log/` trees.

## Build, Test, and Development Commands

- `./scripts/configure-host-env.sh` creates the ignored `.env` file with the current user's UID/GID for container permissions.
- `docker compose build dev` builds the ROS 2 Jazzy desktop image.
- `docker compose up -d dev` starts the workspace container; use `docker compose exec dev bash` to enter it.
- `./scripts/build.sh` runs `colcon build --symlink-install`; execute it inside the container.
- `./scripts/host-check.sh` reports Jetson, Docker, USB, disk, and network details for diagnostics.
- `colcon test && colcon test-result --verbose` runs package tests and reports failures.

## Coding Style & Naming Conventions

Shell scripts must use Bash, two-space indentation, quoted variables, and strict error handling (`set -euo pipefail`) unless diagnostic commands deliberately tolerate failure. Name scripts with lowercase kebab-case. Follow standard ROS 2 conventions in packages: lowercase `snake_case` package, node, topic, and parameter names; four-space Python indentation; and existing ament lint rules (`ament_flake8`, `ament_pep257`, `ament_lint_cmake`, and `ament_xmllint`). Keep YAML indentation at two spaces.

## Testing Guidelines

Add tests within each ROS package and register them through its `CMakeLists.txt` or `setup.py`. Name Python tests `test_*.py`. Before submitting, build from a sourced Jazzy environment, run `colcon test`, and inspect `colcon test-result --verbose`. No repository-wide coverage threshold is currently defined; new behavior should include focused tests where practical.

## Commit & Pull Request Guidelines

History is currently sparse, so use concise, imperative commit subjects such as `Add camera configuration`. Keep each commit focused. Pull requests should explain the change and validation performed, link relevant issues, and call out hardware, networking, power, or container assumptions. Include logs for build/runtime fixes and screenshots only for visual tooling changes. Never commit `.env`, credentials, device secrets, or generated colcon output.

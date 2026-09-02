#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"

if [[ -z "$ROOT" || "$ROOT" != "$PWD" ]]; then
    echo "Run this script from the root of the Git repository."
    exit 1
fi

echo "Creating LIMO Jazzy Desktop Core structure in:"
echo "$ROOT"

mkdir -p \
    .devcontainer \
    config/robot \
    config/cameras \
    config/lidar \
    config/networking \
    docs/hardware \
    docs/decisions \
    scripts \
    src \
    host/snapshots

touch \
    config/robot/.gitkeep \
    config/cameras/.gitkeep \
    config/lidar/.gitkeep \
    config/networking/.gitkeep \
    docs/decisions/.gitkeep \
    src/.gitkeep \
    host/snapshots/.gitkeep

cat > Dockerfile <<'EOF'
FROM ros:jazzy-ros-base-noble

ARG ROS_DISTRO=jazzy
ARG DEV_USER
ARG DEV_UID
ARG DEV_GID

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ros-jazzy-desktop-full \
        ros-dev-tools \
        python3-vcstool \
        python3-colcon-common-extensions \
        git \
        sudo \
        bash-completion \
    && rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    if getent group "${DEV_GID}" >/dev/null; then \
        DEV_GROUP="$(getent group "${DEV_GID}" | cut -d: -f1)"; \
    else \
        groupadd --gid "${DEV_GID}" "${DEV_USER}"; \
        DEV_GROUP="${DEV_USER}"; \
    fi; \
    useradd \
        --uid "${DEV_UID}" \
        --gid "${DEV_GROUP}" \
        --create-home \
        --shell /bin/bash \
        "${DEV_USER}"; \
    echo "${DEV_USER} ALL=(ALL) NOPASSWD:ALL" \
        > "/etc/sudoers.d/${DEV_USER}"; \
    chmod 0440 "/etc/sudoers.d/${DEV_USER}"

RUN echo "source /opt/ros/${ROS_DISTRO}/setup.bash" \
    >> /etc/bash.bashrc

ENV DEBIAN_FRONTEND=dialog

WORKDIR /workspace

USER ${DEV_USER}

CMD ["bash"]
EOF

cat > compose.yaml <<'EOF'
services:
  dev:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        DEV_USER: ${DEV_USER}
        DEV_UID: ${DEV_UID}
        DEV_GID: ${DEV_GID}

    image: limo-jazzy-desktop-core:dev

    network_mode: host

    working_dir: /workspace

    volumes:
      - .:/workspace

    stdin_open: true
    tty: true
    init: true

    command: sleep infinity
EOF

cat > .devcontainer/devcontainer.json <<'EOF'
{
    "name": "LIMO Jazzy Desktop Core",
    "dockerComposeFile": "../compose.yaml",
    "service": "dev",
    "workspaceFolder": "/workspace",
    "shutdownAction": "stopCompose",
    "customizations": {
        "vscode": {
            "extensions": [
                "ms-python.python",
                "ms-vscode.cpptools",
                "ms-vscode.cmake-tools",
                "redhat.vscode-yaml",
                "ms-azuretools.vscode-docker"
            ]
        }
    }
}
EOF

cat > dependencies.repos <<'EOF'
repositories:
  limo_ros2:
    type: git
    url: https://github.com/anshikasinha8/limo_ros2.git
    version: a481d8814e3b4a89908b08b69a4798924b0c8067
EOF

cat > .gitignore <<'EOF'
# ROS / colcon
build/
install/
log/

# Host-specific container identity
.env

# Python
__pycache__/
*.pyc
.venv/

# Editors
.vscode/
.idea/

# OS
.DS_Store

# Temporary files
*.swp
*.tmp
EOF

cat > scripts/configure-host-env.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DEV_USER="$(id -un)"
DEV_UID="$(id -u)"
DEV_GID="$(id -g)"

cat > "${ROOT}/.env" <<ENVEOF
DEV_USER=${DEV_USER}
DEV_UID=${DEV_UID}
DEV_GID=${DEV_GID}
ENVEOF

echo "Created ${ROOT}/.env"
echo "DEV_USER=${DEV_USER}"
echo "DEV_UID=${DEV_UID}"
echo "DEV_GID=${DEV_GID}"
EOF

cat > scripts/import-sources.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

mkdir -p "${ROOT}/src"

cd "${ROOT}"

vcs import src < dependencies.repos
EOF

cat > scripts/build.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

source /opt/ros/jazzy/setup.bash

cd "${ROOT}"

colcon build --symlink-install
EOF

cat > scripts/host-check.sh <<'EOF'
#!/usr/bin/env bash
set -u

echo "=== DATE ==="
date --iso-8601=seconds
echo

echo "=== HOST ==="
hostnamectl 2>/dev/null || true
echo

echo "=== OS ==="
cat /etc/os-release
echo

echo "=== JETSON / L4T ==="
cat /etc/nv_tegra_release 2>/dev/null || echo "No /etc/nv_tegra_release found"
echo

echo "=== KERNEL ==="
uname -a
echo

echo "=== DISK ==="
df -h /
echo

echo "=== DOCKER ==="
docker --version 2>/dev/null || true
echo

echo "=== DOCKER RUNTIMES ==="
docker info 2>/dev/null | grep -E 'Runtimes|Default Runtime' || true
echo

echo "=== USB ==="
lsusb 2>/dev/null || true
echo

echo "=== NETWORK ==="
ip -brief address 2>/dev/null || true
EOF

cat > README.md <<'EOF'
# LIMO Jazzy Desktop Core

Reproducible ROS 2 Jazzy development environment and core platform
configuration for the AgileX LIMO running on NVIDIA Jetson Orin Nano.

## Goals

- Ubuntu 24.04 / JetPack host
- ROS 2 Jazzy Desktop Full inside Docker
- Reproducible external ROS dependencies
- VS Code Remote SSH + Dev Containers workflow
- Multi-camera perception
- LiDAR and depth-camera support
- Indoor and outdoor experimentation
- Configurable ROS namespaces for future multi-robot use
- Explicit documentation of host, driver, power and hardware changes

## Current safety state

Motion testing is not yet enabled.

The Jetson power wiring is still being completed. The Jetson uses a
separate 12 V battery from the LIMO chassis supply.

## Repository layout

```text
.
├── Dockerfile
├── compose.yaml
├── dependencies.repos
├── .devcontainer/
├── config/
├── docs/
├── host/
├── scripts/
└── src/
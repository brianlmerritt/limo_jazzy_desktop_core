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

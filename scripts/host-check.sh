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

# Jetson Orin Nano LIMO serial identification

## Verified platform

- Device: NVIDIA Jetson Orin Nano Engineering Reference Developer Kit Super
- Memory class: 8 GB
- Jetson Linux/L4T: R39.2.1
- Native LIMO UART: `/dev/ttyTHS1`
- UART controller: `3100000.serial`
- Compatibility alias: `/dev/ttylimo`
- Driver baud rate: 460800, raw 8N1

## Evidence

With the LIMO chassis powered and the serial cable connected, sysfs resolved the
available Tegra UARTs as follows:

```text
ttyTHS1 -> /sys/devices/platform/bus@0/3100000.serial/...
ttyTHS2 -> /sys/devices/platform/bus@0/3140000.serial/...
```

A three-second, receive-only test at 460800 baud captured 256 bytes from
`ttyTHS1` and zero bytes from `ttyTHS2`. The `ttyTHS1` sample contained repeated
14-byte LIMO frames beginning `55 0e`, including message IDs `0x321`, `0x322`,
`0x323`, `0x221`, and `0x311`. This confirms `ttyTHS1` is the chassis telemetry
UART without issuing a motion command.

The original Jetson Nano rule matched parent `70006040.serial`. That address is
specific to the older platform and does not match this Orin Nano. The tracked
rule therefore uses:

```udev
KERNEL=="ttyTHS1", KERNELS=="3100000.serial", GROUP="dialout", MODE="0660", SYMLINK+="ttylimo"
```

## Permissions and installation

Both native UART nodes are owned by `root:dialout` with mode `0660`. The current
host user must be added to `dialout` before opening them directly on Ubuntu. The
development container already adds the `dialout` supplementary group.

Compose exposes only the verified host UART. It is available inside the
development container as both `/dev/ttyTHS1` and `/dev/ttylimo`, so the native
name and the existing LIMO driver default both work. `/dev/ttyTHS2` is not
passed through because it produced no chassis telemetry.

Install and verify the compatibility alias with:

```bash
./scripts/configure-limo-udev.sh install
./scripts/setup.sh check-devices
```

Rollback is `./scripts/configure-limo-udev.sh remove`. The removal command
refuses to delete a host rule that differs from the tracked file.

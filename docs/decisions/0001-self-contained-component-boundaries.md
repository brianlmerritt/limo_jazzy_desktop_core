# Decision 0001: Self-contained component boundaries

- Status: Accepted
- Date: 2026-09-04

## Context

This repository combines host configuration, Docker orchestration, hardware
selection, and reusable ROS repositories under `src/`. If a ROS package reads
the root configuration or assumes this Compose layout, it becomes difficult to
build, test, or reuse in another workspace. Conversely, hardware discovery and
Jetson-specific paths do not belong in a generic ROS package.

## Decision

Components under `src/` own their runtime interfaces, validation, documentation,
and safe standalone defaults. They do not depend on files or scripts in the
outer framework.

The outer framework owns deployment choices. It discovers hardware, selects
host resources, and passes only the resulting values and resources through the
component's public interface. It also checks that the selected host state and
the supplied values agree.

Choose the interface according to the value:

1. Explicit ROS parameters configure ROS node behavior.
2. Command-line arguments configure standalone tools.
3. Environment variables provide deployment-level defaults.
4. Component-owned files hold larger or structured configuration.

The normal precedence is explicit parameter or argument, environment value,
then standalone default. The consuming component must validate every value.
The framework must validate generated environment values, mounted devices, and
other platform mappings before use.

The `limo_base` serial contract is the first application of this decision:
`port_name` and `baud_rate` override `LIMO_SERIAL_PORT` and
`LIMO_SERIAL_BAUD`, which in turn override the package defaults. The framework
maps the verified Orin UART and exports those variables, but `limo_base` does
not read the framework configuration.

## Consequences

- A component can be cloned into another ROS workspace and configured without
  copying this repository.
- Platform changes normally affect framework configuration rather than package
  source.
- Some deployment values and component defaults may look similar; boundary
  checks and documentation must prevent silent drift.
- Environment variables remain a small deployment interface, not a replacement
  for typed ROS parameters or structured configuration files.
- External upstream repositories should remain unmodified when practical; use
  adapter packages or launch/configuration overlays instead.

## Exceptions

If a component-to-framework dependency appears necessary, pause implementation
and discuss why an owned interface or adapter is insufficient. Record the
accepted exception and its migration path in a new decision document before
adding the dependency.

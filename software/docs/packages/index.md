# Package Guide

This section is a **narrative, developer-oriented reference** for every package in
the `software/src/` colcon workspace. It explains *what each package does*, *how
its nodes and modules interact*, and *where to look in the source*.

For machine-generated launch/parameter tables (always in sync with the repo),
see {doc}`../_generated/reference/index`. For the Python API, see
{doc}`../_generated/reference/api`.

```{toctree}
:maxdepth: 2
:caption: Packages

bringup
control
sensors
planning
diagnostics
description
interfaces
```

## Package map

The workspace is organised into seven packages. Five are application or asset
packages; two (`bringup`, `interfaces`) are shared infrastructure.

```{include} ../_generated/ros_graph/fragments/package_architecture.md
```

## Quick reference

```{list-table}
:header-rows: 1
:widths: 14 12 10 64

* - Package
  - Build
  - Runs on HW?
  - Primary responsibility
* - {doc}`bringup`
  - ament_cmake
  - Yes
  - Top-level launch, `use_sim` switch, controller spawners, delegation to app packages.
* - {doc}`control`
  - ament_python
  - Yes
  - Tension-to-motion controllers (Julie admittance, Chaoyi force feedback).
* - {doc}`sensors`
  - ament_python
  - Yes
  - Publishes `FishingTension` from HX711 (HW) or MuJoCo line model (sim).
* - {doc}`planning`
  - ament_python
  - **Sim only**
  - Virtual fish disturbance via `fish_agent`.
* - {doc}`diagnostics`
  - ament_python
  - Yes†
  - Run recorder (sim) and hardware bring-up self-test (both modes).
* - {doc}`description`
  - ament_cmake
  - Yes
  - URDF/xacro, MJCF, STL meshes; defines ros2_control hardware plugin.
* - {doc}`interfaces`
  - ament_cmake
  - Yes
  - Custom `FishingTension.msg` shared across control, sensors, diagnostics.
```

† `recorder` is launched only when `record:=true` (typically sim). `hardware_check`
runs in both modes when `hardware_check:=true`.

## Cross-package data flow

Every tension-control run follows the same closed loop regardless of mode:

```{include} ../_generated/ros_graph/fragments/control_loop.md
```

The controller state machine is identical in both controller implementations:

```{include} ../_generated/ros_graph/fragments/fishing_state_machine.md
```

See {doc}`../ros2/index` for mode-specific ROS 2 graphs and topic tables.

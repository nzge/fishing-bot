# ROS 2 Communication Graph

This section documents every **node**, **topic**, and **message type** in the
fishing-arm stack, with explicit separation between **MuJoCo simulation** and
**Dynamixel hardware** modes.

## Mode selection recap

A single launch argument — **`use_sim`** — drives all structural differences.
Application nodes (`control`, `sensors`) run in both modes; only their *data
sources* and *which ros2_control controllers spawn* change.

```{list-table}
:header-rows: 1
:widths: 22 39 39

* - Concern
  - Simulation (`use_sim:=true`)
  - Hardware (`use_sim:=false`)
* - ros2_control host
  - `mujoco_ros2_control/ros2_control_node`
  - `controller_manager/ros2_control_node`
* - Hardware plugin (URDF)
  - `mujoco_ros2_control/MujocoSystemInterface`
  - `dynamixel_hardware/DynamixelHardware`
* - Extra controllers
  - `fish_effort_controller`, `tension_sensor_broadcaster`
  - *(none)*
* - Disturbance
  - `planning/fish_agent`
  - Real fish / manual load
* - Tension source param
  - `sensors`: `source:=sim_fts`
  - `sensors`: `source:=hardware`
* - Sim-only nodes
  - `fish_agent`, `recorder` (when recording)
  - —
* - Time
  - `use_sim_time:=true` on MuJoCo node
  - wall clock
```

```{toctree}
:maxdepth: 2

simulation
hardware
topic_reference
diagram_exports
```

## Shared closed-loop (both modes)

Regardless of mode, tension control follows the same ROS-level loop:

```{include} ../_generated/ros_graph/fragments/control_loop.md
```

## Side-by-side node presence

```{list-table}
:header-rows: 1
:widths: 30 15 15

* - Node / component
  - Simulation
  - Hardware
* - `robot_state_publisher`
  - ✓
  - ✓
* - `mujoco_ros2_control` / `ros2_control_node`
  - ✓
  - —
* - `controller_manager` / `ros2_control_node`
  - —
  - ✓
* - `joint_state_broadcaster`
  - ✓
  - ✓
* - `position_trajectory_controller`
  - ✓
  - ✓
* - `fish_effort_controller`
  - ✓
  - ✗
* - `tension_sensor_broadcaster`
  - ✓
  - ✗
* - `admittance_controller` / `force_feedback_controller`
  - ✓
  - ✓
* - `load_cell_node`
  - ✓
  - ✓
* - `fish_agent`
  - ✓
  - ✗
* - `recorder`
  - ✓ (if `record:=true`)
  - optional†
* - `hardware_check`
  - ✓ (if flag set)
  - ✓ (if flag set)
```

† Recorder is sim-oriented (MuJoCo animation) but will still capture plots if launched on hardware.

## Controller manager services

Both modes expose the standard ros2_control service API on `/controller_manager`:

- `~/list_controllers`
- `~/load_controller` / `~/unload_controller`
- `~/switch_controller`

Spawner nodes exit after loading; the manager and loaded controllers persist.

## TF tree

Published by `robot_state_publisher` from the processed URDF:

**Both modes:** `base_link` → `Link_1` → `Link_2` → `rod_tip_link`

**Simulation only:** `base_link` → `fish_link` (via `fish_swim` prismatic joint)

`sensors/load_cell_node` uses TF (`rod_tip_link` ↔ `fish_link`) in sim to
compute line length for the stretch tension model.

## Quick topic index

See {doc}`topic_reference` for the auto-generated full table, or the mode-specific pages:

- {doc}`simulation` — complete sim graph + physics-layer explanation
- {doc}`hardware` — HW graph + HX711/Dynamixel path
- {doc}`diagram_exports` — standalone `.mmd` files for reports

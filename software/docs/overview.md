# Architecture Overview

The stack is built around a **single sim-to-real switch** (`use_sim`). The same
application nodes and topic *names* run in both modes; the hardware plugin,
optional controllers, and tension data source change.

This page is the **navigation hub**. For exhaustive detail, follow the links below.

## Start here

| I want to… | Go to |
| --- | --- |
| Understand each Python package in depth | {doc}`packages/index` |
| See all ROS 2 nodes & topics (sim vs HW) | {doc}`ros2/index` |
| Download diagrams for my report | {doc}`ros2/diagram_exports` |
| Look up launch args / YAML params | {doc}`_generated/reference/index` |
| Read Python class/function docs | {doc}`_generated/reference/api` |
| Build and run the stack | {doc}`getting_started` |

## System context

```{include} _generated/ros_graph/fragments/package_architecture.md
```

## The sim-to-real switch

The `use_sim` launch argument is resolved at **xacro preprocess time**, which
swaps the `<hardware>` plugin in the URDF *before* the controller manager loads
it:

```{list-table}
:header-rows: 1
:widths: 20 40 40

* - Concern
  - `use_sim:=true` (simulation)
  - `use_sim:=false` (hardware)
* - Hardware plugin
  - `mujoco_ros2_control`
  - `dynamixel_hardware`
* - Controller host
  - MuJoCo's bundled `ros2_control_node`
  - Standalone `controller_manager`
* - Extra ros2_control
  - `fish_effort_controller`, `tension_sensor_broadcaster`
  - *(none beyond arm controllers)*
* - Tension source
  - MuJoCo line stretch model (+ FTS fallback)
  - HX711 load cell
* - Disturbance
  - `planning/fish_agent`
  - Real fish / manual load
* - Sim-only URDF
  - `fish_swim` joint, `tension_sensor` FTS
  - Omitted from HW URDF
```

Full branching logic: {doc}`packages/bringup`.

## Closed-loop control

Both modes implement the same ROS-level tension regulation loop:

```{include} _generated/ros_graph/fragments/control_loop.md
```

Controller internals (state machine, admittance vs force-feedback):
{doc}`packages/control`.

## ROS 2 graphs at a glance

### Simulation

```{include} _generated/ros_graph/fragments/simulation_ros2_graph.md
```

Detailed node/topic tables: {doc}`ros2/simulation`.

### Hardware

```{include} _generated/ros_graph/fragments/hardware_ros2_graph.md
```

Detailed node/topic tables: {doc}`ros2/hardware`.

## Packages at a glance

```{list-table}
:header-rows: 1
:widths: 18 18 64

* - Package
  - Build type
  - Role
* - {doc}`packages/bringup`
  - ament_cmake
  - Top-level launch orchestration, controller config.
* - {doc}`packages/control`
  - ament_python
  - Admittance & force-feedback tension controllers.
* - {doc}`packages/sensors`
  - ament_python
  - `FishingTension` publisher (HX711 or sim stretch model).
* - {doc}`packages/planning`
  - ament_python
  - Virtual fish disturbance (**sim only**).
* - {doc}`packages/diagnostics`
  - ament_python
  - Run recorder + hardware bring-up self-test.
* - {doc}`packages/description`
  - ament_cmake
  - URDF/xacro, MuJoCo MJCF, STL meshes.
* - {doc}`packages/interfaces`
  - ament_cmake
  - `FishingTension.msg`.
```

## Layered architecture

```{mermaid}
flowchart TB
    subgraph L0["Layer 0 — Physical"]
        SIM["MuJoCo physics + tendon"]
        HW["Dynamixel + HX711"]
    end
    subgraph L1["Layer 1 — ros2_control"]
        CM["controller_manager / mujoco_ros2_control"]
        CTRL["joint_state_broadcaster · position_trajectory_controller"]
        SIMCTRL["fish_effort · tension_sensor (sim)"]
    end
    subgraph L2["Layer 2 — Application (Python)"]
        APP["control · sensors · planning · diagnostics"]
    end
    subgraph L3["Layer 3 — Orchestration"]
        BR["bringup/robot.launch.py"]
    end
    L0 --> L1
    L1 --> L2
    L3 --> L1
    L3 --> L2
```

## Data-flow summary

| Signal | Sim origin | HW origin | Consumer(s) |
| --- | --- | --- | --- |
| Joint positions | MuJoCo → `joint_state_broadcaster` | Dynamixel encoders | `control`, `diagnostics` |
| Line tension | Stretch model / FTS → `load_cell_node` | HX711 → `load_cell_node` | `control`, `diagnostics` |
| Joint commands | `control` → `position_trajectory_controller` | same | MuJoCo / Dynamixel |
| Fish force | `fish_agent` → `fish_effort_controller` | N/A | MuJoCo only |

Auto-generated topic index: {doc}`_generated/ros_graph/topic_index`.

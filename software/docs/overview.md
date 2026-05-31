# Architecture Overview

The stack is built around a **single sim-to-real switch** (`use_sim`). The same
controllers, application nodes and topics run in both modes; only the hardware
interface and the data sources change.

## System diagram

```{mermaid}
flowchart TB
    subgraph bringup_pkg["bringup &mdash; robot.launch.py"]
        RSP[robot_state_publisher]
        CM["controller_manager<br/>(real) / mujoco_ros2_control (sim)"]
        Spawners["joint_state_broadcaster<br/>position_trajectory_controller<br/>fish_effort_controller (sim)<br/>tension_sensor_broadcaster (sim)"]
    end

    subgraph apps["Application packages"]
        CTRL["control<br/>admittance_node"]
        SENS["sensors<br/>load_cell_publisher"]
        PLAN["planning<br/>fish_agent (sim)"]
        DIAG["diagnostics<br/>recorder / hardware_check"]
    end

    subgraph desc["description"]
        URDF["fishing-robot.urdf.xacro"]
        MJCF["fishing-robot_sim.xml (MJCF)"]
    end

    subgraph ifaces["interfaces"]
        MSG["FishingTension.msg"]
    end

    URDF --> RSP
    URDF --> CM
    CM --> Spawners
    bringup_pkg --> CTRL
    bringup_pkg --> SENS
    bringup_pkg --> PLAN
    bringup_pkg --> DIAG
    MSG --> CTRL
    MSG --> SENS
    MSG --> DIAG
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
* - Tension source
  - MuJoCo FTS wrench → `sim_fts`
  - HX711 load cell → `hardware`
* - Disturbance
  - virtual `fish_agent`
  - real fish 🐟
```

## Packages at a glance

```{list-table}
:header-rows: 1
:widths: 18 18 64

* - Package
  - Build type
  - Role
* - `bringup`
  - ament_cmake
  - Top-level launch orchestration, controller config (`controllers.yaml`, `params.yaml`).
* - `control`
  - ament_python
  - Admittance controller that maps measured tension to motion.
* - `sensors`
  - ament_python
  - Publishes line tension from the load cell (hardware) or MuJoCo FTS (sim).
* - `planning`
  - ament_python
  - Virtual "fish" disturbance agent for simulation.
* - `diagnostics`
  - ament_python
  - Run recorder (plots + animation) and a motor/sensor bring-up self-test.
* - `description`
  - ament_cmake
  - URDF/xacro, MuJoCo MJCF and STL meshes.
* - `interfaces`
  - ament_cmake
  - Custom messages (`FishingTension.msg`).
```

For the full, always-up-to-date detail on each package — executables, launch
arguments, parameters and message fields — see the {doc}`_generated/reference/index`.

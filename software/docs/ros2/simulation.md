# Simulation ROS 2 Graph

Launch command:

```bash
ros2 launch bringup robot.launch.py
# optional: headless:=true record:=true run_duration:=30
```

## Complete ROS 2 graph

The diagram below is the **authoritative sim-mode communication graph**. The same
source file is available for reports at
[`diagrams/simulation_ros2_graph.mmd`](../_static/diagrams/simulation_ros2_graph.mmd)
(also copied to `_static/diagrams/` on every build).

```{include} ../_generated/ros_graph/fragments/simulation_ros2_graph.md
```

```{tip}
**Download for your report:** after building docs, open
`_build/html/_static/diagrams/simulation_ros2_graph.mmd` or use
[diagram_exports](diagram_exports.md) for SVG export instructions.
```

## Node reference

### Infrastructure

| Node | Package | Role |
| --- | --- | --- |
| `robot_state_publisher` | `robot_state_publisher` | Publishes `/tf`, `/tf_static`, `/robot_description` from URDF |
| `mujoco_ros2_control` (`ros2_control_node`) | `mujoco_ros2_control` | MuJoCo physics + hosts `/controller_manager`; loads `fishing-robot_sim.xml` |

### ros2_control controllers

| Controller | Type | Joint(s) | ROS interface |
| --- | --- | --- | --- |
| `joint_state_broadcaster` | `JointStateBroadcaster` | all | Pubs `/joint_states` |
| `position_trajectory_controller` | `JointTrajectoryController` | `Joint_1`, `Joint_2` | Subs `.../joint_trajectory` |
| `fish_effort_controller` | `ForwardCommandController` | `fish_swim` | Subs `.../commands` |
| `tension_sensor_broadcaster` | `ForceTorqueSensorBroadcaster` | FTS sensor | Pubs `.../wrench` |

Controller manager update rate: **100 Hz** (`controllers.yaml`).

### Application nodes

| Node | Package | Condition |
| --- | --- | --- |
| `admittance_controller` or `force_feedback_controller` | `control` | unless `hardware_check` |
| `load_cell_node` | `sensors` | always (`source:=sim_fts`) |
| `fish_agent` | `planning` | always in sim |
| `recorder` | `diagnostics` | `record:=true` |

## Topic catalog (simulation)

```{list-table}
:header-rows: 1
:widths: 28 22 18 32

* - Topic
  - Message
  - Publisher → Subscriber
  - Notes
* - `/joint_states`
  - `sensor_msgs/JointState`
  - `joint_state_broadcaster` → `control`, `recorder`
  - Includes `fish_swim` position
* - `/position_trajectory_controller/joint_trajectory`
  - `trajectory_msgs/JointTrajectory`
  - `control` → `position_trajectory_controller`
  - 50 Hz commands typical
* - `/fishing_arm/tension`
  - `interfaces/FishingTension`
  - `load_cell_node` → `control`, `recorder`
  - Primary feedback signal
* - `/tension_sensor_broadcaster/wrench`
  - `geometry_msgs/WrenchStamped`
  - `tension_sensor_broadcaster` → `load_cell_node`
  - Fallback if TF stretch model unavailable
* - `/fish_effort_controller/commands`
  - `std_msgs/Float64MultiArray`
  - `fish_agent` → `fish_effort_controller`
  - Single effort value (N)
* - `/tf`, `/tf_static`
  - `tf2_msgs/TFMessage`
  - `robot_state_publisher` → `load_cell_node`
  - Needed for line length
* - `/robot_description`
  - `std_msgs/String`
  - `robot_state_publisher`
  - URDF string
* - `/clock`
  - `rosgraph_msgs/Clock`
  - sim time source
  - `use_sim_time:=true`
```

## Physics layer (below ROS)

ROS messages are the boundary; inside MuJoCo the causal chain is:

```{include} ../_generated/ros_graph/fragments/sim_data_flow.md
```

### Key MJCF parameters (must stay consistent)

| Parameter | MJCF location | `sensors` param |
| --- | --- | --- |
| Line stiffness 220 N/m | tendon | `sim_line_stiffness` |
| Rest length 0.20 m | tendon | `sim_line_springlength` |
| Damping 1.5 | tendon | `sim_line_damping` |

Mismatch between MJCF and `sensor_params.yaml` will cause sim/HW tuning divergence.

## Typical message flow (one control cycle)

```{mermaid}
sequenceDiagram
    participant F as fish_agent
    participant FEC as fish_effort_controller
    participant MJ as MuJoCo
    participant TSB as tension_sensor_broadcaster
    participant LC as load_cell_node
    participant C as admittance_controller
    participant PTC as position_trajectory_controller

    F->>FEC: Float64MultiArray (effort)
    FEC->>MJ: fish_swim effort
    MJ->>MJ: tendon dynamics
    LC->>LC: TF stretch model
    TSB-->>LC: WrenchStamped (fallback)
    LC->>C: FishingTension
    C->>PTC: JointTrajectory
    PTC->>MJ: Joint_1/2 position
    MJ->>C: JointState (via /joint_states)
```

## Related

- Hardware counterpart: {doc}`hardware`
- Package details: {doc}`../packages/index`
- Export diagram: {doc}`diagram_exports`

# Hardware ROS 2 Graph

Launch command:

```bash
ros2 launch bringup robot.launch.py use_sim:=false
# optional: controller_type:=force_feedback hardware_check:=true
```

## Complete ROS 2 graph

```{include} ../_generated/ros_graph/fragments/hardware_ros2_graph.md
```

**Standalone source:** [`diagrams/hardware_ros2_graph.mmd`](../_static/diagrams/hardware_ros2_graph.mmd)

## What is absent on hardware

These sim-only components are **not spawned** and have **no URDF entries**
when `use_sim:=false`:

| Component | Why absent |
| --- | --- |
| `mujoco_ros2_control` node | Replaced by `controller_manager` |
| `fish_swim` joint | No virtual fish in URDF |
| `fish_effort_controller` | No fish joint to command |
| `tension_sensor_broadcaster` | No MuJoCo FTS sensor |
| `fish_agent` | Launch gated on `use_sim` |
| `/tension_sensor_broadcaster/wrench` | Topic never created |
| `/fish_effort_controller/commands` | Topic never created |
| `fish_link` TF frame | Not in HW URDF |

The dashed **"NOT present"** region in the diagram above summarises this.

## Node reference

### Infrastructure

| Node | Package | Role |
| --- | --- | --- |
| `robot_state_publisher` | `robot_state_publisher` | TF + robot description |
| `controller_manager` (`ros2_control_node`) | `controller_manager` | Realtime loop + `dynamixel_hardware` plugin |

### ros2_control controllers

| Controller | Joints | Notes |
| --- | --- | --- |
| `joint_state_broadcaster` | `Joint_1`, `Joint_2` | Publishes `/joint_states` |
| `position_trajectory_controller` | `Joint_1`, `Joint_2` | Position commands only |

No effort controllers, no sensor broadcasters.

### Application nodes

| Node | Package | Notes |
| --- | --- | --- |
| `admittance_controller` or `force_feedback_controller` | `control` | Same as sim |
| `load_cell_node` | `sensors` | `source:=hardware` — HX711 path |
| `hardware_check` | `diagnostics` | Only when `hardware_check:=true` |

## Topic catalog (hardware)

```{list-table}
:header-rows: 1
:widths: 28 22 18 32

* - Topic
  - Message
  - Publisher → Subscriber
  - Notes
* - `/joint_states`
  - `sensor_msgs/JointState`
  - `joint_state_broadcaster` → `control`, `hardware_check`
  - Dynamixel feedback
* - `/position_trajectory_controller/joint_trajectory`
  - `trajectory_msgs/JointTrajectory`
  - `control` → `position_trajectory_controller`
  - Same interface as sim
* - `/fishing_arm/tension`
  - `interfaces/FishingTension`
  - `load_cell_node` → `control`, `hardware_check`
  - From HX711 (not FTS)
* - `/tf`, `/tf_static`
  - `tf2_msgs/TFMessage`
  - `robot_state_publisher`
  - No `fish_link`
* - `/robot_description`
  - `std_msgs/String`
  - `robot_state_publisher`
  - HW URDF (no fish)
```

### Topics that exist in sim but NOT on hardware

| Topic | Sim publisher |
| --- | --- |
| `/fish_effort_controller/commands` | `fish_agent` |
| `/tension_sensor_broadcaster/wrench` | `tension_sensor_broadcaster` |
| `/clock` (sim time) | MuJoCo sim |

## Physical layer (below ROS)

```{include} ../_generated/ros_graph/fragments/hardware_data_flow.md
```

### Dynamixel path

```
JointTrajectory → position_trajectory_controller → ros2_control → DynamixelHardware
  → USB /dev/ttyUSB0 → XL430 servos (ID 1, 2) → joint encoders → /joint_states
```

### Load cell path

```
Line tension → HX711 ADC → load_cell_node.read_raw_adc()
  → calibration → moving average → /fishing_arm/tension
```

```{warning}
Implement real HX711 I/O in `read_raw_adc()` before deployment. The current
stub generates a synthetic sine wave for development.
```

## Controller differences on hardware

| Concern | Simulation | Hardware |
| --- | --- | --- |
| Jacobian for admittance | Can use TF tip/fish geometry | Falls back to `rod_length * |cos θ|` |
| Disturbance | Deterministic sine from `fish_agent` | Unpredictable real load |
| Latency | Sim-step bound | USB serial + servo response |
| Safety | Physics clamp in MJCF | `safety_tension_limit` E-stop in controller |

## Pre-flight checklist

```bash
# 1. Validate pipeline in sim first
ros2 launch bringup robot.launch.py hardware_check:=true

# 2. Run same check on hardware (controller disabled)
ros2 launch bringup robot.launch.py use_sim:=false hardware_check:=true

# 3. Closed-loop on hardware
ros2 launch bringup robot.launch.py use_sim:=false
```

## Related

- Simulation counterpart: {doc}`simulation`
- Sensor calibration: {doc}`../packages/sensors`
- Export diagram: {doc}`diagram_exports`

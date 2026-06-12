# `description` — Robot Model Assets

The `description` package holds all ** kinematic and simulation assets** for the
fishing arm: URDF/xacro, MuJoCo MJCF, and STL meshes.

**Source:** `software/src/description/`  
**Auto-generated tables:** {doc}`../_generated/reference/packages/description`

There is no runtime Python node — this package is consumed at launch time when
xacro generates the URDF and when MuJoCo loads the MJCF scene.

## Asset inventory

| Asset | Path | Used by |
| --- | --- | --- |
| Xacro macro | `urdf/fishing-robot.urdf.xacro` | `bringup` → `robot_state_publisher`, ros2_control |
| Sim URDF | `urdf/fishing-robot_sim.urdf` | Preprocessed reference |
| HW URDF | `urdf/fishing-robot_hw.urdf` | Preprocessed reference |
| MJCF scene | `urdf/fishing-robot_sim.xml` | `mujoco_ros2_control` plugin |
| Meshes | `meshes/*.STL` | Visual/collision geometry |

## Kinematic tree (both modes)

```{mermaid}
flowchart TB
    BL["base_link"]
    L1["Link_1"]
    L2["Link_2"]
    RT["rod_tip_link"]
    BL -->|"Joint_1 revolute (yaw)"| L1
    L1 -->|"Joint_2 revolute (pitch)"| L2
    L2 -->|"rod_tip_joint fixed"| RT
```

| Joint | Type | Axis | ros2_control interfaces |
| --- | --- | --- | --- |
| `Joint_1` | revolute | Z | position cmd; pos/vel/effort state |
| `Joint_2` | revolute | Y | position cmd; pos/vel/effort state |
| `rod_tip_joint` | fixed | — | Defines load cell frame |

Simulation adds:

| Joint | Type | Purpose |
| --- | --- | --- |
| `fish_swim` | prismatic | Virtual fish slide DOF |
| `fish_link` | — | Fish body frame |

## The `use_sim` xacro switch

`fishing-robot.urdf.xacro` accepts:

| Argument | Default | Effect |
| --- | --- | --- |
| `use_sim` | `true` | Select hardware plugin and sim-only joints/sensors |
| `headless` | `false` | MuJoCo viewer visibility (sim only) |

### Simulation block (`use_sim:=true`)

```xml
<plugin>mujoco_ros2_control/MujocoSystemInterface</plugin>
<param name="mujoco_model">.../fishing-robot_sim.xml</param>
<param name="initial_keyframe">starting_pose</param>
<param name="headless">...</param>
```

Additional ros2_control entries:

- **`fish_swim`** joint with effort command interface
- **`tension_sensor`** FTS sensor mapped from MJCF `tension_sensor` sensor

### Hardware block (`use_sim:=false`)

```xml
<plugin>dynamixel_hardware/DynamixelHardware</plugin>
<param name="usb_port">/dev/ttyUSB0</param>
<param name="baud_rate">57600</param>
```

No fish joint, no FTS sensor — only `Joint_1` and `Joint_2`.

## MJCF simulation scene

`fishing-robot_sim.xml` defines:

- Arm bodies matching URDF kinematics
- **Line tendon** between rod tip and fish (stiffness, rest length, damping —
  must match {doc}`sensors` `sim_line_*` parameters)
- **`tension_sensor`** force/torque sensor at rod tip
- **`fish_force`** motor on `fish_swim`
- **`starting_pose`** keyframe applied on boot

The MuJoCo plugin reads the MJCF path from the URDF `<param>` tag — no separate
launch argument needed.

## ros2_control joint ↔ Dynamixel mapping

| Joint | Dynamixel ID | Limits |
| --- | --- | --- |
| `Joint_1` | 1 | ±π rad |
| `Joint_2` | 2 | ±π rad |

Effort limit: 2.5 N·m; velocity limit: 5.76 rad/s (from URDF).

## Interactions

| Package | How it uses `description` |
| --- | --- |
| {doc}`bringup` | Processes xacro with `use_sim`, `headless`; passes URDF to all nodes |
| `mujoco_ros2_control` | Loads MJCF, steps physics, exposes sim joints/sensors |
| `dynamixel_hardware` | Maps URDF joints to USB servos |
| {doc}`sensors` | TF frame names; tendon parameter consistency |
| {doc}`planning` | Fish joint exists in sim URDF/MJCF |
| {doc}`diagnostics` | MJCF path for animation renderer |

## Related

- Full URDF source: [`fishing-robot.urdf.xacro`](https://github.com/nzge/fishing-bot/blob/main/software/src/description/urdf/fishing-robot.urdf.xacro)
- Sim vs HW ROS graphs: {doc}`../ros2/simulation`, {doc}`../ros2/hardware`

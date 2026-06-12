# `interfaces` — Custom Messages

The `interfaces` package defines **shared ROS 2 message types** used across
multiple application packages. It is an `ament_cmake` interface package — no
runtime nodes.

**Source:** `software/src/interfaces/msg/`  
**Auto-generated tables:** {doc}`../_generated/reference/packages/interfaces`

## Messages

### `FishingTension.msg`

```
std_msgs/Header header
float32 tension_newtons
float32 target_tension_newtons
```

| Field | Type | Semantics |
| --- | --- | --- |
| `header.stamp` | `builtin_interfaces/Time` | Sample time |
| `header.frame_id` | `string` | Typically `rod_tip_link` |
| `tension_newtons` | `float32` | Measured line tension (N) — **primary control input** |
| `target_tension_newtons` | `float32` | Reserved for future feedforward/display; currently `0.0` from sensor node |

Built as `interfaces/msg/FishingTension` → included in Python as:

```python
from interfaces.msg import FishingTension
```

## Topic usage

| Topic | Publisher | Subscribers |
| --- | --- | --- |
| `/fishing_arm/tension` | {doc}`sensors` / `load_cell_node` | {doc}`control` (admittance or force_feedback), {doc}`diagnostics` (recorder, hardware_check) |

```{mermaid}
flowchart LR
    S["sensors<br/>load_cell_node"] -->|"/fishing_arm/tension<br/>FishingTension"| C["control<br/>tension controller"]
    S --> D1["diagnostics<br/>recorder"]
    S --> D2["diagnostics<br/>hardware_check"]
```

## Design rationale

A custom message (rather than reusing `geometry_msgs/WrenchStamped` or
`std_msgs/Float64`) provides:

1. **Semantic clarity** — tension in Newtons along the line, not a generic wrench.
2. **Stable API** — controllers depend on one field (`tension_newtons`).
3. **Room for extension** — `target_tension_newtons` for future overlay/debug.

The sim path internally uses `WrenchStamped` from `tension_sensor_broadcaster`
but converts to `FishingTension` before the control layer.

## Build dependency graph

Any package that imports `FishingTension` must declare:

```xml
<depend>interfaces</depend>
```

Current dependents: `control`, `sensors`, `diagnostics`.

## Related standard messages

The stack also uses these **non-custom** types (not in `interfaces`):

| Message | Topic(s) | Package |
| --- | --- | --- |
| `trajectory_msgs/JointTrajectory` | `/position_trajectory_controller/joint_trajectory` | `control`, `diagnostics` |
| `sensor_msgs/JointState` | `/joint_states` | all controllers, diagnostics |
| `geometry_msgs/WrenchStamped` | `/tension_sensor_broadcaster/wrench` | `sensors` (sim fallback) |
| `std_msgs/Float64MultiArray` | `/fish_effort_controller/commands` | `planning` |

See {doc}`../ros2/index` for the complete topic catalog.

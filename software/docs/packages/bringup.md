# `bringup` — Launch Orchestration

The `bringup` package is the **single entry point** for the entire fishing-arm stack.
It owns no application logic; instead it wires together `ros2_control`, TF, and
delegates to the other packages via `IncludeLaunchDescription`.

**Source:** `software/src/bringup/`  
**Auto-generated tables:** {doc}`../_generated/reference/packages/bringup`

## Role in the stack

`robot.launch.py` is the only launch file most operators need. It:

1. Resolves the **`use_sim`** flag at xacro time, selecting the hardware plugin.
2. Starts **`robot_state_publisher`** (both modes).
3. Starts either **`mujoco_ros2_control`** (sim) or **`controller_manager`** (HW).
4. Spawns ros2_control controllers via **`controller_manager/spawner`** nodes.
5. Includes application launches from `control`, `sensors`, `planning`, and `diagnostics`.

```{mermaid}
flowchart TB
    RL["robot.launch.py"]
    RL --> RSP["robot_state_publisher"]
    RL -->|"use_sim=true"| MJ["mujoco_ros2_control"]
    RL -->|"use_sim=false"| CM["controller_manager"]
    RL --> SP["controller spawners"]
    RL --> CL["control.launch.py"]
    RL --> SL["sensor.launch.py"]
    RL --> FL["fish.launch.py<br/>(sim only)"]
    RL --> DL["diagnostics.launch.py<br/>(record:=true)"]
    RL --> HC["hardware_check<br/>(hardware_check:=true)"]
```

## Launch arguments

| Argument | Default | Effect |
| --- | --- | --- |
| `use_sim` | `true` | MuJoCo simulation vs Dynamixel hardware |
| `headless` | `false` | Hide MuJoCo GUI (sim only) |
| `run_duration` | `0` | Auto-shutdown after N seconds (0 = until Ctrl-C) |
| `record` | `false` | Enable diagnostics recorder + animation (sim) |
| `hardware_check` | `false` | Open-loop motor/sensor test; **disables controller** |
| `controller_type` | `admittance` | `admittance`, `force_feedback`, or `none` |

Full argument list with descriptions is regenerated in the
{doc}`../_generated/reference/packages/bringup` page on every build.

## Sim vs hardware branching

The **`use_sim`** argument is passed into xacro when the URDF is generated:

```bash
xacro fishing-robot.urdf.xacro use_sim:=true headless:=false
```

This swaps the `<hardware>` plugin inside `<ros2_control>` *before* any controller
loads. See {doc}`description` and {doc}`../ros2/index` for the resulting
differences in nodes and topics.

### Controller spawners

These spawners talk to `/controller_manager` and are **identical in both modes**
for the arm controllers:

| Spawner | Controller | Mode |
| --- | --- | --- |
| `joint_state_broadcaster` | Publishes `/joint_states` | both |
| `position_trajectory_controller` | Accepts `JointTrajectory` commands | both |
| `fish_effort_controller` | Forwards fish effort to MuJoCo | **sim only** |
| `tension_sensor_broadcaster` | Publishes rod-tip FTS wrench | **sim only** |

Configuration lives in `config/controllers.yaml`.

### Application delegation

Rather than declaring application nodes inline, `robot.launch.py` delegates:

| Included launch | Package | Condition |
| --- | --- | --- |
| `control.launch.py` | `control` | `unless hardware_check` |
| `sensor.launch.py` | `sensors` | always |
| `fish.launch.py` | `planning` | `if use_sim` |
| `diagnostics.launch.py` | `diagnostics` | `if record` |

The sensor source is set programmatically:

```python
source = 'sim_fts' if use_sim else 'hardware'
```

## Configuration files

### `config/controllers.yaml`

Declares the ros2_control controller types and joint lists. Key entries:

- **`position_trajectory_controller`** — joints `Joint_1`, `Joint_2`; position command interface.
- **`fish_effort_controller`** (sim) — joint `fish_swim`; effort interface for the virtual fish.
- **`tension_sensor_broadcaster`** (sim) — sensor `tension_sensor` → `/tension_sensor_broadcaster/wrench`.

### `config/params.yaml`

Shared tuning for both tension controllers (`admittance_controller` and
`force_feedback_controller` namespaces). Passed to whichever controller node
`control.launch.py` starts. See {doc}`control` for parameter semantics.

## Interactions with other packages

```{list-table}
:header-rows: 1
:widths: 22 78

* - Package
  - Interaction
* - `description`
  - Supplies xacro/URDF processed with `use_sim` and `headless`; MJCF path embedded in URDF for sim.
* - `control`
  - Included via `control.launch.py`; receives `controller_type` launch arg.
* - `sensors`
  - Included via `sensor.launch.py`; receives `source` launch arg derived from `use_sim`.
* - `planning`
  - Included only in sim; fish disturbance drives `fish_effort_controller`.
* - `diagnostics`
  - `recorder` when `record:=true`; `hardware_check` when `hardware_check:=true`.
* - `interfaces`
  - Indirect — all app nodes use `FishingTension` published by sensors, consumed by control.
```

## Typical launch commands

```bash
# Default simulation
ros2 launch bringup robot.launch.py

# Headless sim with 30 s recording
ros2 launch bringup robot.launch.py headless:=true record:=true run_duration:=30

# Hardware with Chaoyi controller
ros2 launch bringup robot.launch.py use_sim:=false controller_type:=force_feedback

# Pre-flight open-loop check (works in sim or HW)
ros2 launch bringup robot.launch.py hardware_check:=true
```

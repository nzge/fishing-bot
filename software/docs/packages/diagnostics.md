# `diagnostics` — Recording & Bring-Up Tests

The `diagnostics` package provides **observability** (run recording, plots,
animation) and **validation** (open-loop hardware check) for the fishing stack.

**Source:** `software/src/diagnostics/diagnostics/`  
**Python API:** {doc}`../_generated/autoapi/diagnostics/index`  
**Config:** `config/diagnostics_params.yaml`

## Components overview

```{mermaid}
flowchart LR
    subgraph diag["diagnostics package"]
        REC["recorder"]
        HWC["hardware_check"]
        REN["render_animation.py<br/>(subprocess, not a node)"]
    end
    REC -->|"on shutdown"| REN
    BR["bringup"] -->|"record:=true"| REC
    BR -->|"hardware_check:=true"| HWC
```

| Executable | Node name | Launched when | Mode |
| --- | --- | --- | --- |
| `recorder` | `recorder` | `record:=true` | Typically sim |
| `hardware_check` | `hardware_check` | `hardware_check:=true` | Sim or HW |
| `render_animation.py` | — | Spawned by recorder | Sim artifacts |

Utility scripts in `scripts/` (`motor_test.py`, `sensor_test.py`) are manual
dev tools, not part of the default launch graph.

## `recorder` — Run capture & visualization

### Purpose

When `record:=true`, the recorder subscribes to joint states and tension,
buffers time series, and on shutdown:

1. Saves **`recording.npz`** (raw arrays + MJCF path).
2. Renders **`diagnostics.png`** (3-panel plot: positions, efforts, tension).
3. Spawns **`render_animation.py`** in a detached subprocess → **`animation.mp4`**.

### Subscriptions

| Topic | Type | Buffer |
| --- | --- | --- |
| `/joint_states` | `sensor_msgs/JointState` | `qpos` for `Joint_1`, `Joint_2`, `fish_swim` |
| `/fishing_arm/tension` | `interfaces/FishingTension` | measured + target tension |

### Parameters

| Parameter | Purpose |
| --- | --- |
| `output_dir` | Base directory; each run creates a timestamped subfolder |
| `mjcf_path` | Scene for offscreen render (default: `description/.../fishing-robot_sim.xml`) |
| `render_script` | Path to `render_animation.py` |
| `venv_python` | Python with MuJoCo installed (project `.venv`) |
| `auto_render` | Spawn renderer on shutdown |
| `video_format` | `mp4` or `gif` |
| `video_fps` | Animation frame rate |
| `qpos_joints` | Joint order for trajectory reconstruction |
| `arm_joints` | Joints whose effort is plotted |

Default output: `software/recordings/<timestamp>/`.

### Why a subprocess for rendering?

MuJoCo is installed in the project virtualenv, not the ROS Python environment.
The recorder uses `subprocess.Popen(..., start_new_session=True)` so launch
teardown does not kill the renderer mid-export.

### Interactions

- Reads data published by {doc}`control`, {doc}`sensors`, and `joint_state_broadcaster`.
- Uses MJCF from {doc}`description`.
- Launched by {doc}`bringup` when `record:=true`.

## `hardware_check` — Open-loop self-test

### Purpose

Verifies the ROS pipeline reaches the physical layer **without closed-loop control**:

1. **Motor test** — command each joint a small slow move via trajectory controller;
   confirm `/joint_states` reaches target within tolerance.
2. **Sensor test** — sample `/fishing_arm/tension` for N seconds; confirm finite,
   in-range values.

When `hardware_check:=true`, {doc}`bringup` **does not launch** the tension
controller, so nothing competes with test commands.

### ROS 2 interfaces

| Direction | Topic | Type |
| --- | --- | --- |
| Subscribe | `/joint_states` | `sensor_msgs/JointState` |
| Subscribe | `/fishing_arm/tension` | `interfaces/FishingTension` |
| Publish | `/position_trajectory_controller/joint_trajectory` | `trajectory_msgs/JointTrajectory` |

### Exit codes

- `0` — all checks passed
- `1` — one or more failures (printed summary table)

Works in **both sim and hardware** — validate in sim first:

```bash
ros2 launch bringup robot.launch.py hardware_check:=true
ros2 launch bringup robot.launch.py use_sim:=false hardware_check:=true
```

### Safety parameters

Tuned for gentle motion: `move_delta=0.2` rad, `move_time=2.0` s,
`position_tolerance=0.08` rad. Adjust in `diagnostics_params.yaml` for your rig.

## Launch

```bash
# Recording (via bringup)
ros2 launch bringup robot.launch.py record:=true run_duration:=30

# Hardware check (via bringup)
ros2 launch bringup robot.launch.py hardware_check:=true

# Standalone recorder (unusual)
ros2 launch diagnostics diagnostics.launch.py
```

## Related

- Recordings directory: `software/recordings/` (gitignored contents)
- Animation script: `diagnostics/scripts/render_animation.py`

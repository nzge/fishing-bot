# `planning` — Virtual Fish (Simulation Only)

The `planning` package provides an **environmental disturbance source** for
MuJoCo simulation. It models a fish fighting on the line without any direct
coupling to the tension controller.

**Source:** `software/src/planning/planning/fish_agent.py`  
**Python API:** {doc}`../_generated/autoapi/planning/index`  
**Config:** `config/fish_params.yaml`

```{important}
`fish_agent` is launched **only when `use_sim:=true`**. It does not run on
real hardware — the disturbance there comes from an actual fish (or manual load).
```

## Design: indirect coupling

The fish never publishes to the controller. The causal chain is:

```{include} ../_generated/ros_graph/fragments/sim_data_flow.md
```

1. `fish_agent` publishes effort commands.
2. `fish_effort_controller` (ros2_control) forwards them to MuJoCo's `fish_force` motor.
3. MuJoCo applies force on the `fish_swim` prismatic joint.
4. The line tendon transmits force to the rod tip.
5. {doc}`sensors` measures resulting tension.
6. {doc}`control` reacts to measured tension.

This mirrors real fishing: the controller only sees the load cell, not the fish.

## Node: `fish_agent`

### Disturbance model

Sinusoidal "fight" superimposed on a steady pull:

```
force(t) = mean_force + amplitude * sin(2π * frequency * t)
```

Default profile (from `fish_params.yaml`):

| Parameter | Value | Meaning |
| --- | --- | --- |
| `mean_force` | 3.5 N | Steady pull — centred on controller `target_tension` |
| `amplitude` | 1.2 N | Fight oscillation peak |
| `frequency` | 0.5 Hz | Thrash rate |
| `publish_frequency` | 50 Hz | Command update rate |

### ROS 2 interfaces

| Direction | Topic | Type |
| --- | --- | --- |
| **Publish** | `/fish_effort_controller/commands` | `std_msgs/Float64MultiArray` |

The message `data` field contains a single element: effort in Newtons applied
along the fish slide joint axis.

### ros2_control path

Configured in `bringup/config/controllers.yaml`:

```yaml
fish_effort_controller:
  ros__parameters:
    joints: [fish_swim]
    interface_name: effort
```

The spawner runs only in sim (`robot.launch.py`, `IfCondition(use_sim)`).

## URDF / MJCF requirements

The fish exists only in simulation:

- **URDF** (`fishing-robot.urdf.xacro`): `fish_link` + `fish_swim` prismatic joint
  gated on `use_sim`.
- **MJCF** (`fishing-robot_sim.xml`): fish body, `fish_force` motor, line tendon.

See {doc}`description` for asset details.

## Interactions

| Component | Interaction |
| --- | --- |
| {doc}`bringup` | Includes `fish.launch.py` when `use_sim:=true` |
| `fish_effort_controller` | Subscribes to commands; writes effort to MuJoCo |
| {doc}`sensors` | Indirect — fish force → line tension → `/fishing_arm/tension` |
| {doc}`control` | Indirect — regulates tension caused by fish |
| {doc}`diagnostics` / `recorder` | Logs resulting joint/tension time series |

## Tuning tips

- Increase `amplitude` or `frequency` to stress-test controller stability.
- Match `mean_force` to `target_tension` in `params.yaml` for steady-state tracking tests.
- Disable fish entirely by not launching planning (would require custom launch) or
  set `mean_force:=0 amplitude:=0`.

## Launch

```bash
# Included automatically in sim bringup; standalone:
ros2 launch planning fish.launch.py
```

Only useful when `fish_effort_controller` is already active in MuJoCo.

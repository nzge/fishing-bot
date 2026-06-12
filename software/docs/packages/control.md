# `control` — Tension Controllers

The `control` package implements **closed-loop line-tension regulation** for the
2-DOF fishing arm. It maps measured tension (from {doc}`sensors`) to joint
trajectory commands consumed by `position_trajectory_controller`.

**Source:** `software/src/control/control/`  
**Python API:** {doc}`../_generated/autoapi/control/index`  
**Parameters:** `bringup/config/params.yaml` (keyed by node name)

## Architecture

The package separates **pure control math** from **ROS 2 I/O**:

```{mermaid}
flowchart LR
    subgraph core["fishing_control_core.py (pure Python)"]
        ADM["AdmittanceControllerCore"]
        FFB["ForceFeedbackControllerCore"]
        SM["get_fishing_state()"]
    end
    subgraph ros["fishing_controller_node.py"]
        BASE["FishingControllerBase"]
        ADN["AdmittanceControllerNode"]
        FFN["ForceFeedbackControllerNode"]
    end
    subgraph entry["entry points"]
        E1["admittance_controller.py"]
        E2["force_feedback_controller.py"]
    end
    E1 --> ADN
    E2 --> FFN
    ADN --> BASE
    FFN --> BASE
    ADN --> ADM
    FFN --> FFB
    ADM --> SM
    FFB --> SM
```

| Module | Responsibility |
| --- | --- |
| `fishing_control_core.py` | State machine, tension filtering, admittance & force-feedback algorithms (notebook ports) |
| `fishing_controller_node.py` | ROS subscriptions, safety checks, trajectory publishing, config loading |
| `admittance_controller.py` | Thin `main()` → `AdmittanceControllerNode` |
| `force_feedback_controller.py` | Thin `main()` → `ForceFeedbackControllerNode` |
| `position_test_publisher.py` | Standalone open-loop sinusoid for motor validation (not launched by bringup) |

## Executables

| Command | Node name | Description |
| --- | --- | --- |
| `ros2 run control admittance_node` | `admittance_controller` | Julie's virtual admittance controller |
| `ros2 run control force_feedback_node` | `force_feedback_controller` | Chaoyi's asymmetric P controller |
| `ros2 run control position_test_publisher` | `position_test_publisher` | Manual motor sweep test |

Select at launch: `controller_type:=admittance|force_feedback|none`.

## ROS 2 interfaces

### Subscriptions

| Topic | Type | Callback | Purpose |
| --- | --- | --- | --- |
| `/fishing_arm/tension` | `interfaces/FishingTension` | `_tension_cb` | Measured line tension (N) |
| `/joint_states` | `sensor_msgs/JointState` | `_joint_state_cb` | Current `Joint_1`/`Joint_2` pos & vel |

### Publications

| Topic | Type | Content |
| --- | --- | --- |
| `/position_trajectory_controller/joint_trajectory` | `trajectory_msgs/JointTrajectory` | Position setpoints for active joints |

In **1-DOF mode** (`control_dof:=1`, default), each trajectory point sets
`Joint_1 = joint_1_hold` (locked base yaw) and `Joint_2 = pitch_cmd`.

## Control loop timing

`FishingControllerBase` runs a timer at `control_rate_hz` (default **50 Hz**):

1. **Safety gate** — if no tension received yet, or `|tension| > safety_tension_limit`, hold position (E-stop).
2. **State machine** — `get_fishing_state(t)` → `MONITOR`, `HOOK_SET`, or `REGULATE`.
3. **Tension filter** — exponential smoothing (`tension_filter_alpha`).
4. **Controller update** — algorithm-specific; produces pitch command.
5. **Publish** — `JointTrajectory` with 100 ms horizon.

See the state machine diagram in {doc}`index`.

## State machine

| State | Time window | Behaviour |
| --- | --- | --- |
| `MONITOR` | `t < bite_time` (2.4 s) | Hold `q_init`; admittance uses `f_desired = 0` |
| `HOOK_SET` | `bite_time ≤ t < bite_time + hook_duration` | Smoothstep from `q_init` → `q_hook` |
| `REGULATE` | thereafter | Track `target_tension` (3.5 N default) |

Parameters `bite_time`, `hook_duration`, and angle setpoints (`q_init`, `q_hook`,
`q_neutral`, `q_min`, `q_max`) are shared between both controllers.

## Admittance controller (Julie)

**Class:** `AdmittanceControllerCore` in `fishing_control_core.py`  
**Origin:** `scripts/mojocowithJulieController.ipynb`

Virtual **mass–spring–damper** outer loop with a force–Jacobian mapping:

1. Compute force error `f_desired - f_measured`.
2. Estimate scalar Jacobian `∂(line length)/∂θ` (geometry from TF when available, else `rod_length * |cos θ|` fallback for hardware).
3. Virtual dynamics: `m_v θ̈ = τ_force + τ_spring - b_v θ̇`.
4. Integrate to `theta_cmd`, clip to joint limits.
5. Inner PD loop computes diagnostic torque (not sent directly — `position_trajectory_controller` tracks position).

Key parameters: `m_v`, `b_v`, `k_v`, `k_f`, `kp_track`, `kd_track`, `rod_length`, `j_alpha`.

## Force-feedback controller (Chaoyi)

**Class:** `ForceFeedbackControllerCore`  
**Origin:** `scripts/mojocowithchaoyi'scontroller.ipynb`

Asymmetric proportional mapping from tension error to equilibrium pitch:

- **Below target** (`tension_error < 0`): raise rod with gain `raise_gain`.
- **Above target**: lower rod with gain `lower_gain`.
- Output smoothed via `qeq_alpha` with per-step limit `max_qeq_step`.

Key parameters: `tension_to_angle_gain`, `qeq_alpha`, `max_qeq_step`, `raise_gain`, `lower_gain`.

## Configuration loading

Parameters are declared in `load_admittance_config()` / `load_force_feedback_config()`
by iterating dataclass fields. The node name in launch (`admittance_controller` or
`force_feedback_controller`) must match the key in `params.yaml`:

```yaml
admittance_controller:
  ros__parameters:
    target_tension: 3.5
    ...
force_feedback_controller:
  ros__parameters:
    target_tension: 3.5
    ...
```

## Interactions

```{list-table}
:header-rows: 1
:widths: 22 78

* - Upstream
  - Provides measured tension and joint feedback
* - `sensors` / `load_cell_node`
  - Publishes `/fishing_arm/tension` (`FishingTension`)
* - `joint_state_broadcaster`
  - Publishes `/joint_states`
* - Downstream
  - Executes motion commands
* - `position_trajectory_controller`
  - Subscribes to `/position_trajectory_controller/joint_trajectory`
* - `bringup`
  - Selects which controller executable to launch; suppresses control during `hardware_check`
* - `diagnostics`
  - `recorder` logs tension and joint states; `hardware_check` uses same trajectory topic for open-loop moves
* - `interfaces`
  - Imports `FishingTension` message type
```

## Future: 2-DOF control

`control_dof:=2` is declared but **not yet implemented** — the node logs a warning
and continues in 1-DOF pitch-only mode. The trajectory publisher already has a
stub code path for 2-DOF joint lists.

## Related

- Tuning script: `scripts/tune_tension_control.py` (repo root)
- Compare algorithms: launch with `controller_type:=admittance` vs `force_feedback`
- API reference: {doc}`../_generated/autoapi/control/fishing_control_core/index`

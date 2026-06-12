# `sensors` — Line Tension Sensing

The `sensors` package publishes **`/fishing_arm/tension`** as an
`interfaces/FishingTension` message. A single node — `load_cell_node` — serves
both hardware and simulation by switching its **`source`** parameter.

**Source:** `software/src/sensors/sensors/load_cell_publisher.py`  
**Python API:** {doc}`../_generated/autoapi/sensors/index`  
**Config:** `config/sensor_params.yaml`

## Design principle: one node, two backends

The tension controller ({doc}`control`) always subscribes to `/fishing_arm/tension`.
It never needs to know whether tension came from a physical HX711 or a MuJoCo
simulation model. `bringup` sets the backend at launch:

```python
source = 'sim_fts' if use_sim else 'hardware'
```

```{mermaid}
flowchart TB
    LC["load_cell_node"]
    LC -->|"always"| TOP["/fishing_arm/tension<br/>FishingTension"]

    subgraph hw["source:=hardware"]
        HX["HX711 ADC<br/>read_raw_adc()"]
        CAL["calibration_offset · calibration_scale"]
        HX --> CAL --> LC
    end

    subgraph sim["source:=sim_fts"]
        TF["TF: rod_tip_link → fish_link<br/>line length L"]
        STR["Hooke's law:<br/>k(L-L0) + c dL/dt"]
        WRENCH["/tension_sensor_broadcaster/wrench<br/>(fallback)"]
        TF --> STR --> LC
        WRENCH -.->|"if TF unavailable"| LC
    end
```

## Node: `load_cell_node`

### Parameters (from `sensor_params.yaml`)

| Parameter | Default | Purpose |
| --- | --- | --- |
| `calibration_offset` | `1245.0` | HX711 zero-load ADC reading |
| `calibration_scale` | `0.0023` | N per ADC bit |
| `use_moving_average` | `true` | Enable sliding-window smoothing |
| `window_size` | `10` | Moving average length |
| `publish_frequency` | `80.0` | Timer rate (Hz) |
| `tension_max_threshold` | `20.0` | Log warning above this (N) |
| `noise_floor` | `0.1` | Zero out sub-threshold readings |
| `frame_id` | `rod_tip_link` | Message header frame |
| `source` | `hardware` | `hardware` or `sim_fts` (overridden by launch) |
| `sim_line_stiffness` | `220.0` | Must match MJCF tendon stiffness |
| `sim_line_springlength` | `0.20` | Rest length L₀ (m) |
| `sim_line_damping` | `1.5` | Damping on stretch rate |
| `sim_rod_frame` | `rod_tip_link` | TF frame at rod tip |
| `sim_fish_frame` | `fish_link` | TF frame at fish |

### Hardware path (`source:=hardware`)

1. `read_raw_adc()` reads the HX711 (currently a **placeholder** with simulated
   sine disturbance for development).
2. Apply `(raw - calibration_offset) * calibration_scale` → Newtons.
3. Zero out below `noise_floor`.
4. Optional moving average over `window_size` samples.
5. Publish `FishingTension`.

```{warning}
`read_raw_adc()` is still a stub. Replace with real SPI/serial HX711 driver
before trusting hardware tension values.
```

### Simulation path (`source:=sim_fts`)

Primary method — **stretch model** matching the MJCF tendon:

1. Lookup TF transform `rod_tip_link` → `fish_link`.
2. Compute line length `L = ||translation||`.
3. Stretch `= max(L - sim_line_springlength, 0)`.
4. Tension `= k * stretch + c * dL/dt` (damping only on lengthening).
5. Fallback: if TF unavailable, subscribe to
   `/tension_sensor_broadcaster/wrench` and use force magnitude.

The stretch model is preferred because it matches the controller's physical
expectation and is independent of the FTS frame orientation.

## ROS 2 interfaces

### Publications

| Topic | Type | Rate |
| --- | --- | --- |
| `/fishing_arm/tension` | `interfaces/FishingTension` | `publish_frequency` (80 Hz) |

Message fields:

- `tension_newtons` — measured tension (primary signal for controllers)
- `target_tension_newtons` — reserved (currently always `0.0`; controllers use params instead)

### Subscriptions (sim only)

| Topic | Type | When |
| --- | --- | --- |
| `/tension_sensor_broadcaster/wrench` | `geometry_msgs/WrenchStamped` | `source==sim_fts`, TF fallback |

### TF (sim only)

Uses `tf2_ros.Buffer` + `TransformListener` to compute inter-frame distance.
Depends on `robot_state_publisher` publishing the tree that includes `fish_link`
(sim URDF only).

## Signal processing pipeline

Each timer tick (`timer_callback`):

```
raw reading → noise floor → moving average → FishingTension publish
                ↓
         threshold warning (log)
```

The moving average uses a fixed-length `collections.deque` — O(1) append and
bounded memory.

## Interactions

| Package / node | Relationship |
| --- | --- |
| {doc}`control` | Subscribes to `/fishing_arm/tension`; E-stop on missing/stale data |
| {doc}`bringup` | Sets `source` from `use_sim`; always includes `sensor.launch.py` |
| {doc}`diagnostics` | `recorder` and `hardware_check` subscribe to tension topic |
| {doc}`description` | Defines `rod_tip_link`, `fish_link` frames; MJCF tendon params |
| `tension_sensor_broadcaster` | Sim-only ros2_control broadcaster → wrench topic |
| {doc}`interfaces` | Defines `FishingTension.msg` |

## Physical layer diagrams

- Simulation chain: {doc}`../ros2/simulation` (data flow section)
- Hardware chain: {doc}`../ros2/hardware` (data flow section)

## Launch

```bash
# Normally launched by bringup; standalone:
ros2 launch sensors sensor.launch.py source:=hardware
ros2 launch sensors sensor.launch.py source:=sim_fts
```

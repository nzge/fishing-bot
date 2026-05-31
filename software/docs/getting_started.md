# Getting Started

## Prerequisites

- **ROS 2 Jazzy** (Ubuntu 24.04, Python 3.12)
- `colcon` and `rosdep`
- Simulation extras: `mujoco`, `mujoco_ros2_control` (built from source)
- Hardware extras: `dynamixel_hardware`

## Build the workspace

```bash
cd ~/fishing-bot/software

# Install declared dependencies
rosdep install --from-paths src --ignore-src -r -y

# Build
colcon build --symlink-install

# Source the overlay (every new shell)
source install/setup.bash
```

## Run it

::::{tab-set}
:::{tab-item} Simulation (default)
```bash
ros2 launch bringup robot.launch.py
```
:::
:::{tab-item} Headless + recording
```bash
ros2 launch bringup robot.launch.py headless:=true record:=true run_duration:=30
```
:::
:::{tab-item} Real hardware
```bash
ros2 launch bringup robot.launch.py use_sim:=false
```
:::
:::{tab-item} Bring-up self-test
```bash
ros2 launch bringup robot.launch.py hardware_check:=true
```
:::
::::

The full set of launch arguments is documented on the
[`bringup` reference page](_generated/reference/packages/bringup.md), and is
regenerated when you run `./docs/build.sh`.

## Build the documentation locally

```bash
cd ~/fishing-bot/software

# One-time: create an isolated docs environment
python3 -m venv docs/.venv
source docs/.venv/bin/activate
pip install -r docs/requirements.pip

./docs/build.sh
```

Then open `docs/_build/html/index.html`. See {doc}`doc_pipeline` for details.

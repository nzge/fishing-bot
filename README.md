# fishing-bot (MAE 263C)
A fishing robot



Tweak your fishing-robot.urdf.xacro (in your text editor).
Compile the Xacro: xacro fishing-robot.urdf.xacro use_sim:=true > fishing-robot_sim.urdf
Launch the viewer: python3 -m mujoco.viewer --file fishing-robot_sim.urdf
Inspect your meshes and joints.



## Loading mujoco viewer

# Navigate to the workspace root
cd ~/fishing-bot

# Activate your virtual environment
source .venv/bin/activate

# Launch the viewer with your XML file
python3 -m mujoco.viewer --file sim/fishing_robot.xml

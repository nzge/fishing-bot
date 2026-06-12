import mujoco

# Load the URDF file
model = mujoco.MjModel.from_xml_path('fishing-robot_sim.urdf')

# Save as a MuJoCo MJCF XML file
mujoco.mj_saveLastXML('fishing-robot_sim.xml', model)
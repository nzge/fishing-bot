import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import UnlessCondition
from launch.substitutions import Command, FindExecutable, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

def generate_launch_description():
    # 1. Declare Launch Arguments (The Sim-to-Real Swap Flag)
    use_sim = LaunchConfiguration('use_sim')
    
    # 2. Locate Packages dynamically
    description_pkg = FindPackageShare('description')
    bringup_pkg = FindPackageShare('bringup')

    urdf_file = PathJoinSubstitution([description_pkg, 'urdf', 'fishing-robot.urdf.xacro'])
    controllers_file = PathJoinSubstitution([bringup_pkg, 'config', 'controllers.yaml'])

    # 3. Process the URDF with xacro, passing the use_sim argument so the URDF knows which plugin to load
    robot_description_content = Command(
        [PathJoinSubstitution([FindExecutable(name='xacro')]), ' ', urdf_file, ' use_sim:=', use_sim]
    )
    robot_description = {'robot_description': robot_description_content}

    # 4. Define Core Nodes
    # The Robot State Publisher broadcasts TF frames (coordinate frames) based on the URDF
    robot_state_pub_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='both',
        parameters=[robot_description]
    )

    # The Controller Manager (Native ROS 2 hardware loop)
    # Note: If use_sim=true, MuJoCo usually spins its own controller manager via plugin. 
    # Therefore, we only launch this explicitly for the real hardware using the UnlessCondition.
    controller_manager_node = Node(
        package='controller_manager',
        executable='ros2_control_node',
        parameters=[robot_description, controllers_file],
        output='both',
        condition=UnlessCondition(use_sim) 
    )

    # 5. Spawner Nodes (Booting the controllers defined in controllers.yaml)
    joint_state_broadcaster_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['joint_state_broadcaster', '--controller-manager', '/controller_manager'],
    )

    position_controller_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['position_trajectory_controller', '--controller-manager', '/controller_manager'],
    )

    return LaunchDescription([
        # Default is physical hardware (false) to prevent accidental simulation launches when plugged into real motors
        DeclareLaunchArgument('use_sim', default_value='false', description='Use physical Dynamixel hardware by default'),
        robot_state_pub_node,
        controller_manager_node,
        joint_state_broadcaster_spawner,
        position_controller_spawner
    ])
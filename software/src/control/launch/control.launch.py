from launch import LaunchDescription
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    # Gains and limits live in config (No Magic Numbers), injected here.
    admittance_params = PathJoinSubstitution(
        [FindPackageShare('bringup'), 'config', 'params.yaml'])

    admittance_node = Node(
        package='control',
        executable='admittance_node',
        name='admittance_controller',
        output='screen',
        parameters=[admittance_params],
    )

    return LaunchDescription([
        admittance_node,
    ])

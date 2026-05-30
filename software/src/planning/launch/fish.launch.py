from launch import LaunchDescription
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    # Disturbance profile lives in config (No Magic Numbers).
    fish_params = PathJoinSubstitution(
        [FindPackageShare('planning'), 'config', 'fish_params.yaml'])

    fish_agent_node = Node(
        package='planning',
        executable='fish_agent',
        name='fish_agent',
        output='screen',
        parameters=[fish_params],
    )

    return LaunchDescription([
        fish_agent_node,
    ])

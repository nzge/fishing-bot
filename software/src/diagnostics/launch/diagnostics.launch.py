from launch import LaunchDescription
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    # Recorder settings (paths, video format/fps, venv python) live in config.
    recorder_params = PathJoinSubstitution(
        [FindPackageShare('diagnostics'), 'config', 'diagnostics_params.yaml'])

    recorder_node = Node(
        package='diagnostics',
        executable='recorder',
        name='recorder',
        output='screen',
        parameters=[recorder_params],
    )

    return LaunchDescription([
        recorder_node,
    ])

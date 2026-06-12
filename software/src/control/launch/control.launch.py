from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import (
    EqualsSubstitution, LaunchConfiguration, PathJoinSubstitution,
)
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    controller_type = LaunchConfiguration('controller_type')
    controller_type_arg = DeclareLaunchArgument(
        'controller_type',
        default_value='admittance',
        description=(
            'Tension controller: admittance (Julie), '
            'force_feedback (Chaoyi), or none'
        ),
    )

    params_file = PathJoinSubstitution(
        [FindPackageShare('bringup'), 'config', 'params.yaml'],
    )

    admittance_node = Node(
        package='control',
        executable='admittance_node',
        name='admittance_controller',
        output='screen',
        parameters=[params_file],
        condition=IfCondition(
            EqualsSubstitution(controller_type, 'admittance'),
        ),
    )

    force_feedback_node = Node(
        package='control',
        executable='force_feedback_node',
        name='force_feedback_controller',
        output='screen',
        parameters=[params_file],
        condition=IfCondition(
            EqualsSubstitution(controller_type, 'force_feedback'),
        ),
    )

    return LaunchDescription([
        controller_type_arg,
        admittance_node,
        force_feedback_node,
    ])

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import (
    LaunchConfiguration, PathJoinSubstitution, PythonExpression,
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

    use_sim = LaunchConfiguration('use_sim')
    use_sim_arg = DeclareLaunchArgument(
        'use_sim',
        default_value='true',
        description='Layer params_hw.yaml when false (skip FSM on real hardware)',
    )

    bringup_pkg = FindPackageShare('bringup')
    params_file = PathJoinSubstitution([bringup_pkg, 'config', 'params.yaml'])
    params_hw_file = PathJoinSubstitution([bringup_pkg, 'config', 'params_hw.yaml'])

    admittance_hw = PythonExpression([
        "'", use_sim, "' == 'false' and '", controller_type, "' == 'admittance'",
    ])
    admittance_sim = PythonExpression([
        "'", use_sim, "' == 'true' and '", controller_type, "' == 'admittance'",
    ])
    ffb_hw = PythonExpression([
        "'", use_sim, "' == 'false' and '", controller_type, "' == 'force_feedback'",
    ])
    ffb_sim = PythonExpression([
        "'", use_sim, "' == 'true' and '", controller_type, "' == 'force_feedback'",
    ])

    return LaunchDescription([
        controller_type_arg,
        use_sim_arg,
        Node(
            package='control',
            executable='admittance_node',
            name='admittance_controller',
            output='screen',
            parameters=[params_file, params_hw_file],
            condition=IfCondition(admittance_hw),
        ),
        Node(
            package='control',
            executable='admittance_node',
            name='admittance_controller',
            output='screen',
            parameters=[params_file],
            condition=IfCondition(admittance_sim),
        ),
        Node(
            package='control',
            executable='force_feedback_node',
            name='force_feedback_controller',
            output='screen',
            parameters=[params_file, params_hw_file],
            condition=IfCondition(ffb_hw),
        ),
        Node(
            package='control',
            executable='force_feedback_node',
            name='force_feedback_controller',
            output='screen',
            parameters=[params_file],
            condition=IfCondition(ffb_sim),
        ),
    ])

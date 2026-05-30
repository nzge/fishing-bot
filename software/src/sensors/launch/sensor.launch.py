from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    # Tension source: 'hardware' (HX711) or 'sim_fts' (MuJoCo force sensor).
    source = LaunchConfiguration('source')
    source_arg = DeclareLaunchArgument('source', default_value='hardware')

    # Calibration offsets and limits live in config (No Magic Numbers).
    sensor_params = PathJoinSubstitution(
        [FindPackageShare('sensors'), 'config', 'sensor_params.yaml'])

    load_cell_node = Node(
        package='sensors',
        executable='load_cell_publisher',
        name='load_cell_node',
        output='screen',
        parameters=[sensor_params, {'source': source}],
    )

    return LaunchDescription([
        source_arg,
        load_cell_node,
    ])

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction, Shutdown,
    TimerAction)
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    Command, FindExecutable, LaunchConfiguration, PathJoinSubstitution,
    PythonExpression)
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    # 1. Architecture flag: the single sim-to-real switch for the whole stack.
    use_sim = LaunchConfiguration('use_sim')
    use_sim_arg = DeclareLaunchArgument(
        'use_sim',
        default_value='true',
        description='Launch MuJoCo simulation (true) or the physical Dynamixel arm (false)')

    # Run MuJoCo with or without its GUI window (sim only).
    headless = LaunchConfiguration('headless')
    headless_arg = DeclareLaunchArgument(
        'headless', default_value='false',
        description='Run MuJoCo without the GUI viewer window (sim only)')

    # Optional self-imposed time limit: auto-shutdown the whole launch after N
    # seconds. 0 (default) means run until Ctrl-C.
    run_duration = LaunchConfiguration('run_duration')
    run_duration_arg = DeclareLaunchArgument(
        'run_duration', default_value='0',
        description='Auto-shutdown the launch after N seconds (0 = until Ctrl-C)')

    # Record the run: time-series plots + an isometric MuJoCo animation.
    record = LaunchConfiguration('record')
    record_arg = DeclareLaunchArgument(
        'record', default_value='false',
        description='Capture diagnostics plots + animation of the run (sim only)')

    # 2. Package shares.
    description_pkg = FindPackageShare('description')
    bringup_pkg = FindPackageShare('bringup')
    control_pkg = FindPackageShare('control')
    sensors_pkg = FindPackageShare('sensors')
    planning_pkg = FindPackageShare('planning')
    diagnostics_pkg = FindPackageShare('diagnostics')

    # 3. Xacro -> URDF. Passing use_sim here is what swaps the <hardware> plugin
    #    (dynamixel_hardware vs mujoco_ros2_control) at preprocess time, BEFORE
    #    the controller manager ever loads it.
    urdf_xacro = PathJoinSubstitution([description_pkg, 'urdf', 'fishing-robot.urdf.xacro'])
    robot_description_content = Command(
        [FindExecutable(name='xacro'), ' ', urdf_xacro,
         ' use_sim:=', use_sim, ' headless:=', headless])
    # Wrap as a string parameter so launch does not try to YAML-parse the URDF.
    robot_description = {
        'robot_description': ParameterValue(robot_description_content, value_type=str)}

    controllers_yaml = PathJoinSubstitution([bringup_pkg, 'config', 'controllers.yaml'])

    # 4. TF broadcaster (runs in both modes).
    robot_state_pub_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='both',
        parameters=[robot_description],
    )

    # 5a. REAL HARDWARE path: a standalone controller_manager owns the realtime
    #     loop and instantiates the dynamixel_hardware plugin named in the URDF.
    controller_manager_node = Node(
        package='controller_manager',
        executable='ros2_control_node',
        parameters=[robot_description, controllers_yaml],
        output='both',
        condition=UnlessCondition(use_sim),
    )

    # 5b. SIMULATION path: mujoco_ros2_control ships its OWN ros2_control_node
    #     (required for compatibility) that wraps MuJoCo's Simulate app: it opens
    #     the viewer, steps physics, and hosts the controller_manager. The MJCF
    #     path + initial keyframe are declared in the URDF hardware block, so we
    #     only pass robot_description, the controllers, and use_sim_time.
    mujoco_node = Node(
        package='mujoco_ros2_control',
        executable='ros2_control_node',
        parameters=[robot_description, controllers_yaml, {'use_sim_time': True}],
        output='both',
        condition=IfCondition(use_sim),
    )

    # 6. Controller spawners. Either host above exposes the manager at
    #    /controller_manager, so these are identical in both modes.
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

    # Sim-only controllers: the fish effort command forwarder and the load-cell
    # FTS broadcaster. They exist only in the MuJoCo scene.
    fish_effort_controller_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['fish_effort_controller', '--controller-manager', '/controller_manager'],
        condition=IfCondition(use_sim),
    )
    tension_broadcaster_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['tension_sensor_broadcaster', '--controller-manager', '/controller_manager'],
        condition=IfCondition(use_sim),
    )

    # 7. Delegation Pattern: each application layer comes from its own package's
    #    launch file rather than being re-declared inline here.
    control_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([control_pkg, 'launch', 'control.launch.py'])),
    )
    # The load cell runs in both modes; only its data source changes. On hardware
    # it reads the HX711; in sim it converts the MuJoCo FTS wrench to tension.
    sensor_source = PythonExpression(
        ["'sim_fts' if '", use_sim, "' == 'true' else 'hardware'"])
    sensor_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([sensors_pkg, 'launch', 'sensor.launch.py'])),
        launch_arguments={'source': sensor_source}.items(),
    )
    # The virtual "fish" disturbance only runs in simulation.
    fish_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([planning_pkg, 'launch', 'fish.launch.py'])),
        condition=IfCondition(use_sim),
    )
    # Diagnostics recorder: plots + animation, captured only when record:=true.
    diagnostics_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([diagnostics_pkg, 'launch', 'diagnostics.launch.py'])),
        condition=IfCondition(record),
    )

    # Resolve run_duration at launch time and, if positive, schedule a shutdown.
    def _schedule_shutdown(context, *_args, **_kwargs):
        seconds = float(run_duration.perform(context))
        if seconds <= 0.0:
            return []
        return [TimerAction(
            period=seconds,
            actions=[Shutdown(reason=f'run_duration {seconds:g}s reached')])]

    shutdown_timer = OpaqueFunction(function=_schedule_shutdown)

    return LaunchDescription([
        use_sim_arg,
        headless_arg,
        run_duration_arg,
        record_arg,
        shutdown_timer,
        robot_state_pub_node,
        controller_manager_node,
        mujoco_node,
        joint_state_broadcaster_spawner,
        position_controller_spawner,
        fish_effort_controller_spawner,
        tension_broadcaster_spawner,
        control_launch,
        sensor_launch,
        fish_launch,
        diagnostics_launch,
    ])

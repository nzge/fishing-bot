config = os.path.join(get_package_share_directory('sensors'), 'config', 'sensor_params.yaml')

Node(
    package='sensors',
    executable='load_cell_publisher',
    parameters=[config] 
)
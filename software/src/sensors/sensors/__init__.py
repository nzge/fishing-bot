def __init__(self):
    super().__init__('load_cell_node')
    # This automatically looks for 'calibration_scale' in the YAML file.
    # If it's not found, it defaults to 1.0.
    self.declare_parameter('calibration_scale', 1.0)
    self.scale = self.get_parameter('calibration_scale').get_parameter_value().double_value
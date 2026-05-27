import os
from glob import glob
from setuptools import find_packages, setup

package_name = 'sensors'

setup(
    name=package_name,
    version='0.0.1',
    packages=find_packages(exclude=['test']),
    data_files=[
        # Register the package marker
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        # Include package.xml
        ('share/' + package_name, ['package.xml']),
        # Include all launch files (if you create a launch directory)
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        # Include all config files (if you create a config directory)
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
    ],
    install_requires=['setuptools', 'rclpy', 'std_msgs'], # Add your dependencies here
    zip_safe=True,
    maintainer='nzge',
    maintainer_email='nathange784@gmail.com',
    description='Sensor node package for robotic fishing arm',
    license='Apache-2.0', # Or your preferred license
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            # The format is 'command_name = package_name.script_name:main_function'
            'load_cell_publisher = sensors.load_cell_publisher:main',
        ],
    },
)
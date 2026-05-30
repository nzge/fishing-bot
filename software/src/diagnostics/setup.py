import os
from glob import glob
from setuptools import find_packages, setup

package_name = 'diagnostics'

setup(
    name=package_name,
    version='0.0.1',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
        # The render script runs under the .venv python (it needs mujoco), so it
        # is shipped as a data file rather than a console_scripts entry point.
        (os.path.join('share', package_name, 'scripts'), glob('scripts/*.py')),
    ],
    install_requires=['setuptools', 'rclpy', 'sensor_msgs', 'interfaces'],
    zip_safe=True,
    maintainer='nzge',
    maintainer_email='nathange784@gmail.com',
    description='Recording + visualization tools for the robotic fishing arm',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'recorder = diagnostics.recorder:main',
        ],
    },
)

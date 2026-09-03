from glob import glob
from setuptools import find_packages, setup

package_name = 'slam_robot_base'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml', 'README.md']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Tom',
    maintainer_email='tom@example.com',
    description='ROS 2 base interface for the tracked SLAM robot Arduino Nano motor/encoder controller.',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'arduino_base_node = slam_robot_base.arduino_base_node:main',
            'fake_base_node = slam_robot_base.fake_base_node:main',
            'fake_lidar_node = slam_robot_base.fake_lidar_node:main',
        ],
    },
)

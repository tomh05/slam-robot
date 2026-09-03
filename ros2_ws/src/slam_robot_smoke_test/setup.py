from setuptools import find_packages, setup

package_name = 'slam_robot_smoke_test'

setup(
    name=package_name,
    version='0.0.1',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Tom',
    maintainer_email='tom@example.com',
    description='Minimal ROS 2 smoke-test package for validating the slam-robot build/deploy loop.',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'smoke_publisher = slam_robot_smoke_test.smoke_publisher:main',
        ],
    },
)

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    track_width = LaunchConfiguration('track_width')
    wheel_radius = LaunchConfiguration('wheel_radius')
    max_linear = LaunchConfiguration('max_linear')
    max_angular = LaunchConfiguration('max_angular')

    return LaunchDescription([
        DeclareLaunchArgument('track_width', default_value='0.155'),
        DeclareLaunchArgument('wheel_radius', default_value='0.029'),
        DeclareLaunchArgument('max_linear', default_value='0.20'),
        DeclareLaunchArgument('max_angular', default_value='1.0'),
        Node(
            package='slam_robot_base',
            executable='fake_base_node',
            name='fake_base_node',
            output='screen',
            parameters=[
                {
                    'track_width_m': track_width,
                    'wheel_radius_m': wheel_radius,
                    'max_linear_mps': max_linear,
                    'max_angular_rps': max_angular,
                }
            ],
        ),
    ])

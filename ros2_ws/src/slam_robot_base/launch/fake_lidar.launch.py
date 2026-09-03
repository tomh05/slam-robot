from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    frame_id = LaunchConfiguration('frame_id')
    publish_rate = LaunchConfiguration('publish_rate')
    range_min = LaunchConfiguration('range_min')
    range_max = LaunchConfiguration('range_max')

    return LaunchDescription([
        DeclareLaunchArgument('frame_id', default_value='lidar_link'),
        DeclareLaunchArgument('publish_rate', default_value='10.0'),
        DeclareLaunchArgument('range_min', default_value='0.1'),
        DeclareLaunchArgument('range_max', default_value='10.0'),
        Node(
            package='slam_robot_base',
            executable='fake_lidar_node',
            name='fake_lidar_node',
            output='screen',
            parameters=[
                {
                    'frame_id': frame_id,
                    'publish_rate_hz': publish_rate,
                    'range_min': range_min,
                    'range_max': range_max,
                }
            ],
        ),
    ])

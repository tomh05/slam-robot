from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    config_file = LaunchConfiguration('config_file')
    motors_enabled = LaunchConfiguration('motors_enabled')

    default_config = PathJoinSubstitution([
        FindPackageShare('slam_robot_base'),
        'config',
        'arduino_base.yaml',
    ])

    return LaunchDescription([
        DeclareLaunchArgument(
            'config_file',
            default_value=default_config,
            description='Path to arduino_base_node parameter YAML file.',
        ),
        DeclareLaunchArgument(
            'motors_enabled',
            default_value='false',
            description='Set true only when the robot is safe to move.',
        ),
        Node(
            package='slam_robot_base',
            executable='arduino_base_node',
            name='arduino_base_node',
            output='screen',
            parameters=[
                config_file,
                {'motors_enabled': motors_enabled},
            ],
        ),
    ])

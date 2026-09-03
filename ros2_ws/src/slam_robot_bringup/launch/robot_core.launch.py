from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    motors_enabled = LaunchConfiguration('motors_enabled')

    description_launch = PathJoinSubstitution([
        FindPackageShare('slam_robot_description'),
        'launch',
        'robot_state_publisher.launch.py',
    ])
    base_launch = PathJoinSubstitution([
        FindPackageShare('slam_robot_base'),
        'launch',
        'arduino_base.launch.py',
    ])

    return LaunchDescription([
        DeclareLaunchArgument(
            'motors_enabled',
            default_value='false',
            description='Set true only when robot is safe to move. Default false prevents motion.',
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(description_launch),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(base_launch),
            launch_arguments={'motors_enabled': motors_enabled}.items(),
        ),
    ])

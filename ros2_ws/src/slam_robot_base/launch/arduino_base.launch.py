from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    config_file = LaunchConfiguration('config_file')
    motors_enabled = LaunchConfiguration('motors_enabled')
    publish_tf = LaunchConfiguration('publish_tf')

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
        DeclareLaunchArgument(
            'publish_tf',
            default_value='true',
            description='Publish odom->base_link TF. Set false when robot_localization EKF publishes it.',
        ),
        Node(
            package='slam_robot_base',
            executable='arduino_base_node',
            name='arduino_base_node',
            output='screen',
            parameters=[
                config_file,
                {
                    'motors_enabled': ParameterValue(motors_enabled, value_type=bool),
                    'publish_tf': ParameterValue(publish_tf, value_type=bool),
                },
            ],
        ),
    ])

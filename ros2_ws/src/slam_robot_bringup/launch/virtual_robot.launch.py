from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    use_fake_base = LaunchConfiguration('use_fake_base')
    use_fake_lidar = LaunchConfiguration('use_fake_lidar')
    use_sim_time = LaunchConfiguration('use_sim_time')

    description_launch = FindPackageShare('slam_robot_description')
    fake_base_launch = FindPackageShare('slam_robot_base')
    fake_lidar_launch = FindPackageShare('slam_robot_base')

    return LaunchDescription([
        DeclareLaunchArgument('use_fake_base', default_value='true'),
        DeclareLaunchArgument('use_fake_lidar', default_value='true'),
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([
                description_launch, '/launch/robot_state_publisher.launch.py',
            ]),
            launch_arguments={'use_sim_time': use_sim_time}.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([
                fake_base_launch, '/launch/fake_base.launch.py',
            ]),
            condition=IfCondition(use_fake_base),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([
                fake_lidar_launch, '/launch/fake_lidar.launch.py',
            ]),
            condition=IfCondition(use_fake_lidar),
        ),
    ])

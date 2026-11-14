from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    EmitEvent,
    IncludeLaunchDescription,
    RegisterEventHandler,
)
from launch.conditions import IfCondition
from launch.events import matches_action
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, PythonExpression
from launch_ros.actions import LifecycleNode, Node
from launch_ros.descriptions import ParameterFile
from launch_ros.event_handlers import OnStateTransition
from launch_ros.events.lifecycle import ChangeState
from launch_ros.substitutions import FindPackageShare
from lifecycle_msgs.msg import Transition


def generate_launch_description():
    use_sim_time = LaunchConfiguration('use_sim_time')
    params_file = LaunchConfiguration('slam_params_file')
    odom_source = LaunchConfiguration('odom_source')
    include_robot_core = LaunchConfiguration('include_robot_core')
    motors_enabled = LaunchConfiguration('motors_enabled')
    start_lidar = LaunchConfiguration('start_lidar')
    lidar_port = LaunchConfiguration('lidar_port')
    lidar_baud = LaunchConfiguration('lidar_baud')
    lidar_frame_id = LaunchConfiguration('lidar_frame_id')

    default_params = PathJoinSubstitution([
        FindPackageShare('slam_robot_bringup'),
        'config',
        'slam_toolbox_mapping.yaml',
    ])
    core_ekf_launch = PathJoinSubstitution([
        FindPackageShare('slam_robot_bringup'),
        'launch',
        'robot_core_ekf.launch.py',
    ])
    core_raw_launch = PathJoinSubstitution([
        FindPackageShare('slam_robot_bringup'),
        'launch',
        'robot_core.launch.py',
    ])

    slam_params_file = ParameterFile(params_file, allow_substs=True)
    slam_toolbox = LifecycleNode(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        namespace='',
        output='screen',
        parameters=[
            slam_params_file,
            {'use_sim_time': use_sim_time},
        ],
    )
    configure_slam_toolbox = EmitEvent(
        event=ChangeState(
            lifecycle_node_matcher=matches_action(slam_toolbox),
            transition_id=Transition.TRANSITION_CONFIGURE,
        ),
    )
    activate_slam_toolbox = RegisterEventHandler(
        OnStateTransition(
            target_lifecycle_node=slam_toolbox,
            start_state='configuring',
            goal_state='inactive',
            entities=[
                EmitEvent(event=ChangeState(
                    lifecycle_node_matcher=matches_action(slam_toolbox),
                    transition_id=Transition.TRANSITION_ACTIVATE,
                )),
            ],
        ),
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='false',
            description='Use /clock time if true.',
        ),
        DeclareLaunchArgument(
            'slam_params_file',
            default_value=default_params,
            description='Path to slam_toolbox mapping parameters.',
        ),
        DeclareLaunchArgument(
            'odom_source',
            default_value='ekf',
            description='Odometry source: ekf or raw.',
        ),
        DeclareLaunchArgument(
            'include_robot_core',
            default_value='true',
            description='Start robot core launch stack in this launch if true.',
        ),
        DeclareLaunchArgument(
            'motors_enabled',
            default_value='false',
            description='Set true only when robot motion is verified safe.',
        ),
        DeclareLaunchArgument(
            'start_lidar',
            default_value='true',
            description='Start lidar_scan_publisher in this launch if true.',
        ),
        DeclareLaunchArgument(
            'lidar_port',
            default_value='/dev/lidar',
            description='Serial device for YDLIDAR-compatible scanner.',
        ),
        DeclareLaunchArgument(
            'lidar_baud',
            default_value='153600',
            description='Serial baud rate for lidar.',
        ),
        DeclareLaunchArgument(
            'lidar_frame_id',
            default_value='lidar_link',
            description='Frame id used in /scan messages.',
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(core_ekf_launch),
            launch_arguments={'motors_enabled': motors_enabled}.items(),
            condition=IfCondition(PythonExpression([
                "'",
                include_robot_core,
                "' == 'true' and '",
                odom_source,
                "' == 'ekf'",
            ])),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(core_raw_launch),
            launch_arguments={'motors_enabled': motors_enabled}.items(),
            condition=IfCondition(PythonExpression([
                "'",
                include_robot_core,
                "' == 'true' and '",
                odom_source,
                "' == 'raw'",
            ])),
        ),
        Node(
            package='lidar_scan_publisher',
            executable='lidar_scan_publisher',
            name='lidar_scan_publisher',
            output='screen',
            arguments=[
                '--port',
                lidar_port,
                '--baud',
                lidar_baud,
                '--frame-id',
                lidar_frame_id,
            ],
            condition=IfCondition(start_lidar),
        ),
        slam_toolbox,
        configure_slam_toolbox,
        activate_slam_toolbox,
    ])

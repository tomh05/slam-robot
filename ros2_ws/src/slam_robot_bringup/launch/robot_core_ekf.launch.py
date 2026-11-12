from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    motors_enabled = LaunchConfiguration('motors_enabled')
    imu_i2c_bus = LaunchConfiguration('imu_i2c_bus')
    imu_i2c_address = LaunchConfiguration('imu_i2c_address')
    imu_frame_id = LaunchConfiguration('imu_frame_id')
    imu_topic = LaunchConfiguration('imu_topic')
    ekf_params_file = LaunchConfiguration('ekf_params_file')
    imu_gyro_bias_x = LaunchConfiguration('imu_gyro_bias_x')
    imu_gyro_bias_y = LaunchConfiguration('imu_gyro_bias_y')
    imu_gyro_bias_z = LaunchConfiguration('imu_gyro_bias_z')
    imu_accel_offset_x = LaunchConfiguration('imu_accel_offset_x')
    imu_accel_offset_y = LaunchConfiguration('imu_accel_offset_y')
    imu_accel_offset_z = LaunchConfiguration('imu_accel_offset_z')

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
    default_ekf_params = PathJoinSubstitution([
        FindPackageShare('slam_robot_bringup'),
        'config',
        'ekf.yaml',
    ])

    return LaunchDescription([
        DeclareLaunchArgument(
            'motors_enabled',
            default_value='false',
            description='Set true only when the robot is safe to move. Default false prevents motion.',
        ),
        DeclareLaunchArgument(
            'imu_i2c_bus',
            default_value='1',
            description='I2C bus for the BM160 IMU (Raspberry Pi header is usually bus 1).',
        ),
        DeclareLaunchArgument(
            'imu_i2c_address',
            default_value='105',  # 0x69
            description='I2C address for the BM160 IMU (decimal). This robot detected 0x69 = 105.',
        ),
        DeclareLaunchArgument(
            'imu_frame_id',
            default_value='imu_link',
            description='TF frame for IMU data; must match slam_robot_description URDF.',
        ),
        DeclareLaunchArgument(
            'imu_topic',
            default_value='/imu/data',
            description='sensor_msgs/Imu topic published by the BM160 node.',
        ),
        DeclareLaunchArgument(
            'ekf_params_file',
            default_value=default_ekf_params,
            description='Path to robot_localization EKF parameter YAML file.',
        ),
        DeclareLaunchArgument(
            'imu_gyro_bias_x',
            default_value='0.0',
            description='BMI160 gyro bias x (rad/s) to subtract. Calibrate with scripts/calibrate_imu.py.',
        ),
        DeclareLaunchArgument(
            'imu_gyro_bias_y',
            default_value='0.0',
            description='BMI160 gyro bias y (rad/s) to subtract.',
        ),
        DeclareLaunchArgument(
            'imu_gyro_bias_z',
            default_value='0.0',
            description='BMI160 gyro bias z (rad/s) to subtract.',
        ),
        DeclareLaunchArgument(
            'imu_accel_offset_x',
            default_value='0.0',
            description='BMI160 accel zero-g offset x (m/s^2) to subtract. Calibrate with scripts/calibrate_imu.py.',
        ),
        DeclareLaunchArgument(
            'imu_accel_offset_y',
            default_value='0.0',
            description='BMI160 accel zero-g offset y (m/s^2) to subtract.',
        ),
        DeclareLaunchArgument(
            'imu_accel_offset_z',
            default_value='0.0',
            description='BMI160 accel zero-g offset z (m/s^2) to subtract.',
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(description_launch),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(base_launch),
            launch_arguments={
                'motors_enabled': motors_enabled,
                # EKF publishes odom -> base_link in ekf.yaml; avoid dual TF publishers.
                'publish_tf': 'false',
            }.items(),
        ),
        Node(
            package='slam_robot_base',
            executable='bm160_imu_node',
            name='bm160_imu_node',
            output='screen',
            parameters=[{
                'i2c_bus': ParameterValue(imu_i2c_bus, value_type=int),
                'i2c_address': ParameterValue(imu_i2c_address, value_type=int),
                'frame_id': imu_frame_id,
                'topic': imu_topic,
                'gyro_bias_x': ParameterValue(imu_gyro_bias_x, value_type=float),
                'gyro_bias_y': ParameterValue(imu_gyro_bias_y, value_type=float),
                'gyro_bias_z': ParameterValue(imu_gyro_bias_z, value_type=float),
                'accel_offset_x': ParameterValue(imu_accel_offset_x, value_type=float),
                'accel_offset_y': ParameterValue(imu_accel_offset_y, value_type=float),
                'accel_offset_z': ParameterValue(imu_accel_offset_z, value_type=float),
            }],
        ),
        Node(
            package='robot_localization',
            executable='ekf_node',
            name='ekf_filter_node',
            output='screen',
            parameters=[ekf_params_file],
        ),
    ])

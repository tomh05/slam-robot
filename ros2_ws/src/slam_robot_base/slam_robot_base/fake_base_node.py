import math

import rclpy
from geometry_msgs.msg import Twist
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy
from tf2_ros import TransformBroadcaster


class FakeBaseNode(Node):
    """Publish /odom and odom -> base_link from /cmd_vel without hardware.

    This implements a simple differential-drive odometry integrator so the
    robot can be driven entirely in software for testing, simulation, or
    development away from the real hardware.
    """

    def __init__(self) -> None:
        super().__init__('fake_base_node')

        self.declare_parameter('base_frame_id', 'base_link')
        self.declare_parameter('odom_frame_id', 'odom')
        self.declare_parameter('track_width_m', 0.155)
        self.declare_parameter('wheel_radius_m', 0.029)
        self.declare_parameter('max_linear_mps', 0.20)
        self.declare_parameter('max_angular_rps', 1.0)
        self.declare_parameter('publish_tf', True)
        self.declare_parameter('publish_rate_hz', 50.0)

        self.base_frame_id = str(self.get_parameter('base_frame_id').value)
        self.odom_frame_id = str(self.get_parameter('odom_frame_id').value)
        self.track_width_m = float(self.get_parameter('track_width_m').value)
        self.wheel_radius_m = float(self.get_parameter('wheel_radius_m').value)
        self.max_linear_mps = abs(float(self.get_parameter('max_linear_mps').value))
        self.max_angular_rps = abs(float(self.get_parameter('max_angular_rps').value))
        self.publish_tf = bool(self.get_parameter('publish_tf').value)
        publish_rate_hz = float(self.get_parameter('publish_rate_hz').value)
        if publish_rate_hz <= 0.0:
            raise ValueError('publish_rate_hz must be positive')

        qos = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=1,
        )
        self.odom_pub = self.create_publisher(Odometry, '/odom', qos)
        self.cmd_sub = self.create_subscription(Twist, '/cmd_vel', self.cmd_vel_callback, 10)
        self.tf_broadcaster = TransformBroadcaster(self) if self.publish_tf else None

        self.target_linear_mps = 0.0
        self.target_angular_rps = 0.0
        self.last_cmd_vel_time = self.get_clock().now()

        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0
        self.last_time = self.get_clock().now()

        self.create_timer(1.0 / publish_rate_hz, self.publish_timer)

        self.get_logger().info(
            'Fake base node started: '
            f'track_width_m={self.track_width_m:.3f} '
            f'wheel_radius_m={self.wheel_radius_m:.4f} '
            f'max_linear_mps={self.max_linear_mps:.2f} '
            f'max_angular_rps={self.max_angular_rps:.2f}'
        )

    def cmd_vel_callback(self, msg: Twist) -> None:
        self.target_linear_mps = max(-self.max_linear_mps, min(self.max_linear_mps, msg.linear.x))
        self.target_angular_rps = max(-self.max_angular_rps, min(self.max_angular_rps, msg.angular.z))
        self.last_cmd_vel_time = self.get_clock().now()

    def publish_timer(self) -> None:
        now = self.get_clock().now()
        dt = (now - self.last_time).nanoseconds / 1e9
        if dt <= 0.0:
            return

        # Apply simple command timeout: drift to zero after 0.5 s of no input
        time_since_cmd = (now - self.last_cmd_vel_time).nanoseconds / 1e9
        if time_since_cmd > 0.5:
            decay = max(0.0, 1.0 - (time_since_cmd - 0.5) / 0.5)
            linear = self.target_linear_mps * decay
            angular = self.target_angular_rps * decay
        else:
            linear = self.target_linear_mps
            angular = self.target_angular_rps

        # Differential drive kinematics
        left_mps = linear - angular * self.track_width_m / 2.0
        right_mps = linear + angular * self.track_width_m / 2.0

        distance = (left_mps + right_mps) / 2.0 * dt
        delta_yaw = (right_mps - left_mps) / self.track_width_m * dt

        mid_yaw = self.yaw + delta_yaw / 2.0
        self.x += distance * math.cos(mid_yaw)
        self.y += distance * math.sin(mid_yaw)
        self.yaw = self.normalize_angle(self.yaw + delta_yaw)

        self.last_time = now
        self.publish_odometry(now, left_mps, right_mps)

    def publish_odometry(self, stamp, left_mps: float, right_mps: float) -> None:
        linear_velocity = (left_mps + right_mps) / 2.0
        angular_velocity = (right_mps - left_mps) / self.track_width_m

        qz = math.sin(self.yaw / 2.0)
        qw = math.cos(self.yaw / 2.0)

        odom = Odometry()
        odom.header.stamp = stamp.to_msg()
        odom.header.frame_id = self.odom_frame_id
        odom.child_frame_id = self.base_frame_id
        odom.pose.pose.position.x = self.x
        odom.pose.pose.position.y = self.y
        odom.pose.pose.position.z = 0.0
        odom.pose.pose.orientation.z = qz
        odom.pose.pose.orientation.w = qw
        odom.twist.twist.linear.x = linear_velocity
        odom.twist.twist.angular.z = angular_velocity

        odom.pose.covariance[0] = 0.01
        odom.pose.covariance[7] = 0.01
        odom.pose.covariance[35] = 0.05
        odom.twist.covariance[0] = 0.01
        odom.twist.covariance[35] = 0.05
        self.odom_pub.publish(odom)

        if self.tf_broadcaster is not None:
            transform = TransformStamped()
            transform.header.stamp = odom.header.stamp
            transform.header.frame_id = self.odom_frame_id
            transform.child_frame_id = self.base_frame_id
            transform.transform.translation.x = self.x
            transform.transform.translation.y = self.y
            transform.transform.translation.z = 0.0
            transform.transform.rotation.z = qz
            transform.transform.rotation.w = qw
            self.tf_broadcaster.sendTransform(transform)

    @staticmethod
    def normalize_angle(angle: float) -> float:
        while angle > math.pi:
            angle -= 2.0 * math.pi
        while angle < -math.pi:
            angle += 2.0 * math.pi
        return angle


def main(args=None) -> None:
    rclpy.init(args=args)
    node = FakeBaseNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()

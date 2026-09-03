import math
from typing import List, Optional, Tuple

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Header


class FakeLidarNode(Node):
    """Simulate a 2D laser scanner publishing /scan without hardware.

    The simulated environment is a simple rectangular room with a few
    interior obstacles defined as line segments in the ``odom`` frame.
    Rays are cast from the current robot pose and intersected against
    those segments so the scan changes realistically as the robot moves.
    """

    def __init__(self) -> None:
        super().__init__('fake_lidar_node')

        self.declare_parameter('frame_id', 'lidar_link')
        self.declare_parameter('scan_topic', '/scan')
        self.declare_parameter('publish_rate_hz', 10.0)
        self.declare_parameter('range_min', 0.1)
        self.declare_parameter('range_max', 10.0)
        self.declare_parameter('angle_min', -math.pi)
        self.declare_parameter('angle_max', math.pi)
        self.declare_parameter('angle_increment', math.radians(1.0))
        self.declare_parameter('noise_std', 0.02)

        self.frame_id = str(self.get_parameter('frame_id').value)
        scan_topic = str(self.get_parameter('scan_topic').value)
        publish_rate_hz = float(self.get_parameter('publish_rate_hz').value)
        self.range_min = float(self.get_parameter('range_min').value)
        self.range_max = float(self.get_parameter('range_max').value)
        self.angle_min = float(self.get_parameter('angle_min').value)
        self.angle_max = float(self.get_parameter('angle_max').value)
        self.angle_increment = float(self.get_parameter('angle_increment').value)
        self.noise_std = float(self.get_parameter('noise_std').value)

        if publish_rate_hz <= 0.0:
            raise ValueError('publish_rate_hz must be positive')
        if self.angle_increment <= 0.0:
            raise ValueError('angle_increment must be positive')

        qos = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=1,
        )
        self.scan_pub = self.create_publisher(LaserScan, scan_topic, qos)
        self.odom_sub = self.create_subscription(Odometry, '/odom', self.odom_callback, qos)
        self.timer = self.create_timer(1.0 / publish_rate_hz, self.publish_scan)

        # Simple room + obstacles in odom frame as line segments.
        # Each segment is ((x1, y1), (x2, y2)).
        self.walls: List[Tuple[Tuple[float, float], Tuple[float, float]]] = [
            # Outer room 6m x 6m centered at origin.
            ((-3.0, -3.0), (3.0, -3.0)),
            ((3.0, -3.0), (3.0, 3.0)),
            ((3.0, 3.0), (-3.0, 3.0)),
            ((-3.0, 3.0), (-3.0, -3.0)),
            # Interior obstacle blocks.
            ((-1.5, -1.5), (-1.5, 1.5)),
            ((-1.5, 1.5), (0.5, 1.5)),
            ((0.5, 1.5), (0.5, -0.5)),
            ((0.5, -0.5), (-1.5, -0.5)),
            # Second block.
            ((1.0, -2.5), (2.5, -2.5)),
            ((2.5, -2.5), (2.5, -0.8)),
            ((2.5, -0.8), (1.0, -0.8)),
            ((1.0, -0.8), (1.0, -2.5)),
        ]

        self.current_odom: Optional[Odometry] = None
        self.get_logger().info(
            'Fake lidar node started: '
            f'frame_id={self.frame_id} rate={publish_rate_hz:.1f} Hz '
            f'range=[{self.range_min}, {self.range_max}] '
            f'angle_increment={math.degrees(self.angle_increment):.1f} deg'
        )

    def odom_callback(self, msg: Odometry) -> None:
        self.current_odom = msg

    def publish_scan(self) -> None:
        if self.current_odom is None:
            return

        x = self.current_odom.pose.pose.position.x
        y = self.current_odom.pose.pose.position.y
        qz = self.current_odom.pose.pose.orientation.z
        qw = self.current_odom.pose.pose.orientation.w
        yaw = 2.0 * math.atan2(qz, qw)

        num_points = int((self.angle_max - self.angle_min) / self.angle_increment) + 1
        ranges: List[float] = []

        for i in range(num_points):
            angle = self.angle_min + i * self.angle_increment
            world_angle = yaw + angle
            dx = math.cos(world_angle)
            dy = math.sin(world_angle)

            min_dist = self.range_max
            for (ax, ay), (bx, by) in self.walls:
                dist = self.ray_segment_distance(x, y, dx, dy, ax, ay, bx, by)
                if dist is not None and dist < min_dist:
                    min_dist = dist

            if min_dist < self.range_min:
                min_dist = float('nan')
            elif min_dist >= self.range_max:
                min_dist = self.range_max

            ranges.append(min_dist)

        scan = LaserScan()
        scan.header = Header(stamp=self.get_clock().now().to_msg(), frame_id=self.frame_id)
        scan.angle_min = self.angle_min
        scan.angle_max = self.angle_max
        scan.angle_increment = self.angle_increment
        scan.time_increment = 0.0
        scan.scan_time = 1.0 / self.get_parameter('publish_rate_hz').value
        scan.range_min = self.range_min
        scan.range_max = self.range_max
        scan.ranges = ranges
        self.scan_pub.publish(scan)

    @staticmethod
    def ray_segment_distance(
        ox: float, oy: float, dx: float, dy: float, ax: float, ay: float, bx: float, by: float
    ) -> Optional[float]:
        """Return distance along ray to segment, or None if no intersection."""
        sx = bx - ax
        sy = by - ay
        denom = dx * sy - dy * sx
        if abs(denom) < 1e-8:
            return None
        t = ((ax - ox) * sy - (ay - oy) * sx) / denom
        u = ((ax - ox) * dy - (ay - oy) * dx) / denom
        if t >= 0.0 and 0.0 <= u <= 1.0:
            return t
        return None


def main(args=None) -> None:
    rclpy.init(args=args)
    node = FakeLidarNode()
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

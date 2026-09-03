import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class SmokePublisher(Node):
    def __init__(self) -> None:
        super().__init__('slam_robot_smoke_publisher')
        self.publisher = self.create_publisher(String, '/slam_robot/smoke', 10)
        self.count = 0
        self.timer = self.create_timer(1.0, self.publish_smoke)
        self.get_logger().info('slam_robot_smoke_publisher started')

    def publish_smoke(self) -> None:
        msg = String()
        msg.data = f'slam robot smoke test #{self.count}'
        self.publisher.publish(msg)
        self.get_logger().info(f'Published: {msg.data}')
        self.count += 1


def main(args=None) -> None:
    rclpy.init(args=args)
    node = SmokePublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

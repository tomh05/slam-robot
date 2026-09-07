#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=robot_env.sh
source "${SCRIPT_DIR}/robot_env.sh"

echo "Watching /odom pose on ${ROBOT_HOST}... (Ctrl-C to stop)"

ssh -t "${ROBOT_SSH}" bash -s <<'REMOTE_EOF'
set -e
source /opt/ros/jazzy/setup.bash
source /home/ubuntu/slam-robot/ros2_ws/install/setup.bash

python3 <<'PYEOF'
import rclpy
from nav_msgs.msg import Odometry

rclpy.init()
node = rclpy.create_node('odom_pose_viewer')


def cb(msg: Odometry) -> None:
    p = msg.pose.pose.position
    o = msg.pose.pose.orientation
    t = msg.twist.twist
    print(
        f"pose  x={p.x:+.4f}  y={p.y:+.4f}  z={p.z:+.4f}"
        f"  q=({o.x:+.4f} {o.y:+.4f} {o.z:+.4f} {o.w:+.4f})"
        f" | twist  lin.x={t.linear.x:+.4f}  ang.z={t.angular.z:+.4f}"
    )


node.create_subscription(Odometry, '/odom', cb, 10)
rclpy.spin(node)
PYEOF
REMOTE_EOF

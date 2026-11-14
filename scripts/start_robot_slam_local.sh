#!/usr/bin/env bash
set -euo pipefail

# Script to run ON the robot to start local SLAM bring-up.
# Starts: robot_core_ekf (or raw core), lidar_scan_publisher, and slam_toolbox mapping.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ROS_WS="$PROJECT_ROOT/ros2_ws"

# Source ROS 2
if [ -f /opt/ros/jazzy/setup.bash ]; then
    set +u
    # shellcheck disable=SC1091
    source /opt/ros/jazzy/setup.bash
    set -u
elif [ -f /opt/ros/humble/setup.bash ]; then
    set +u
    # shellcheck disable=SC1091
    source /opt/ros/humble/setup.bash
    set -u
else
    echo "ROS 2 not found in /opt/ros/{jazzy,humble}" >&2
    exit 1
fi

# Source workspace if built
if [ -f "$ROS_WS/install/setup.bash" ]; then
    set +u
    # shellcheck disable=SC1091
    source "$ROS_WS/install/setup.bash"
    set -u
else
    echo "Workspace not built at $ROS_WS/install/setup.bash" >&2
    echo "Build it with: cd $ROS_WS && colcon build" >&2
    exit 1
fi

export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"

ODOM_SOURCE="${ODOM_SOURCE:-ekf}"
MOTORS_ENABLED="${MOTORS_ENABLED:-false}"
LIDAR_PORT="${LIDAR_PORT:-/dev/lidar}"
LIDAR_BAUD="${LIDAR_BAUD:-153600}"
LIDAR_FRAME_ID="${LIDAR_FRAME_ID:-lidar_link}"

echo "=== Starting robot SLAM stack (local on robot) ==="
echo "Project: $PROJECT_ROOT"
echo "ROS_DOMAIN_ID: $ROS_DOMAIN_ID"
echo "Odometry source: $ODOM_SOURCE"
echo "Motors enabled: $MOTORS_ENABLED"
echo "Lidar: $LIDAR_PORT @ $LIDAR_BAUD (frame: $LIDAR_FRAME_ID)"
echo ""

echo "Starting slam_mapping.launch.py..."
exec ros2 launch slam_robot_bringup slam_mapping.launch.py \
    odom_source:="$ODOM_SOURCE" \
    motors_enabled:="$MOTORS_ENABLED" \
    start_lidar:=true \
    lidar_port:="$LIDAR_PORT" \
    lidar_baud:="$LIDAR_BAUD" \
    lidar_frame_id:="$LIDAR_FRAME_ID"

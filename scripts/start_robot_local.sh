#!/usr/bin/env bash
set -euo pipefail

# Script to run ON the robot to start the full ROS 2 stack.
# Starts: robot core (with motors enabled) + lidar_scan_publisher

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

# Lidar configuration
LIDAR_PORT="${LIDAR_PORT:-/dev/ttyUSB0}"
LIDAR_BAUD="${LIDAR_BAUD:-153600}"
LIDAR_FRAME_ID="${LIDAR_FRAME_ID:-lidar_link}"

echo "=== Starting robot stack (local on robot) ==="
echo "Project: $PROJECT_ROOT"
echo "ROS_DOMAIN_ID: $ROS_DOMAIN_ID"
echo "Motors: enabled"
echo "Lidar: $LIDAR_PORT @ $LIDAR_BAUD (frame: $LIDAR_FRAME_ID)"
echo ""

# Start lidar scan publisher in background (uses its own CLI args, not ROS params)
echo "Starting lidar_scan_publisher..."
ros2 run lidar_scan_publisher lidar_scan_publisher \
    --port "$LIDAR_PORT" \
    --baud "$LIDAR_BAUD" \
    --frame-id "$LIDAR_FRAME_ID" &
LIDAR_PID=$!

# Give lidar a moment to start
sleep 2

# Start robot core with motors enabled
echo "Starting robot_core (motors enabled)..."
ros2 launch slam_robot_bringup robot_core.launch.py motors_enabled:=true &
CORE_PID=$!

cleanup() {
    echo ""
    echo "Shutting down..."
    kill "$LIDAR_PID" "$CORE_PID" 2>/dev/null || true
    wait "$LIDAR_PID" "$CORE_PID" 2>/dev/null || true
}

trap cleanup INT TERM

# Wait for either process to exit
wait -n "$LIDAR_PID" "$CORE_PID" 2>/dev/null || wait
cleanup

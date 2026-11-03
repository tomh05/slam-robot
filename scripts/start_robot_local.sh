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

echo "=== Starting robot stack (local on robot) ==="
echo "Project: $PROJECT_ROOT"
echo "ROS_DOMAIN_ID: $ROS_DOMAIN_ID"
echo "Motors: enabled"
echo "Lidar: starting lidar_scan_publisher (installed version)"
echo ""

# Start lidar scan publisher in background (installed version takes no args)
setsid bash -c "ros2 run lidar_scan_publisher lidar_scan_publisher" &
LIDAR_PID=$!

sleep 2

# Start robot core with motors enabled
setsid bash -c "ros2 launch slam_robot_bringup robot_core.launch.py motors_enabled:=true" &
CORE_PID=$!

CLEANED_UP=0
cleanup() {
    if [ "$CLEANED_UP" -eq 1 ]; then
        return
    fi
    CLEANED_UP=1
    echo ""
    echo "Shutting down..."
    kill -TERM -"$LIDAR_PID" 2>/dev/null || true
    kill -TERM -"$CORE_PID" 2>/dev/null || true
    sleep 2
    kill -KILL -"$LIDAR_PID" 2>/dev/null || true
    kill -KILL -"$CORE_PID" 2>/dev/null || true
    wait 2>/dev/null || true
}

trap cleanup INT TERM EXIT

wait -n "$LIDAR_PID" "$CORE_PID" 2>/dev/null || wait
cleanup

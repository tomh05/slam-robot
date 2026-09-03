#!/usr/bin/env bash
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ROS_WS="$PROJECT_ROOT/ros2_ws"
RVIZ_CONFIG="$PROJECT_ROOT/ros2_ws/src/slam_robot_bringup/rviz/slam_robot.rviz"

# If this script is being run from inside the Ubuntu VM, detect the standard
# ROS 2 install location. Otherwise fall back to sourcing from the project dir
# so the script also works from the Pi or another dev machine.
if [ -f /opt/ros/jazzy/setup.bash ]; then
    set +u
    source /opt/ros/jazzy/setup.bash
    set -u
elif [ -f "$HOME/ros2_humble/setup.bash" ]; then
    set +u
    source "$HOME/ros2_humble/setup.bash"
    set -u
fi

if [ -f "$ROS_WS/install/setup.bash" ]; then
    set +u
    source "$ROS_WS/install/setup.bash"
    set -u
fi

export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"

echo "=== Starting virtual SLAM robot ==="
echo "ROS_DOMAIN_ID=$ROS_DOMAIN_ID"

# Launch the simulated robot stack in the background.
# This runs: robot_state_publisher + fake_base_node + fake_lidar_node.
ros2 launch slam_robot_bringup virtual_robot.launch.py \
    use_fake_base:=true \
    use_fake_lidar:=true \
    use_sim_time:=false &
LAUNCH_PID=$!

# Give nodes a moment to start and discover each other.
sleep 4

echo "=== Launching RViz2 ==="
rviz2 -d "$RVIZ_CONFIG"
RVIZ_EXIT=$?

# When RViz2 closes, stop the background launch tree.
echo "=== Shutting down ==="
kill "$LAUNCH_PID" 2>/dev/null || true
wait "$LAUNCH_PID" 2>/dev/null || true

exit $RVIZ_EXIT

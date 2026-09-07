#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=robot_env.sh
source "${SCRIPT_DIR}/robot_env.sh"

# rviz2 requires a display. It runs locally on the laptop, connecting to the
# robot over DDS (ROS_DOMAIN_ID must match — see robot_env.sh).
RVIZ_CONFIG="${SCRIPT_DIR}/../ros2_ws/src/slam_robot_bringup/rviz/slam_robot.rviz"

# Source the local ROS 2 installation so rviz2 and its DDS middleware are
# fully initialised with the right environment.
# ROS 2 setup scripts reference variables (e.g. AMENT_TRACE_SETUP_FILES) that
# may be unset, so temporarily disable `set -u` around the source calls.
set +u
if [ -f /opt/ros/jazzy/setup.bash ]; then
    # shellcheck source=/opt/ros/jazzy/setup.bash
    source /opt/ros/jazzy/setup.bash
fi

# Local workspace (if built) provides package-level resources like robot
# descriptions. Optional — topics arrive from the robot over DDS.
if [ -f "${SCRIPT_DIR}/../ros2_ws/install/setup.bash" ]; then
    source "${SCRIPT_DIR}/../ros2_ws/install/setup.bash"
fi
set -u

# Allow DDS to discover remote machines (not just localhost).
unset ROS_LOCALHOST_ONLY

echo "Launching rviz2 to monitor ${ROBOT_HOST} (ROS_DOMAIN_ID=${ROS_DOMAIN_ID})..."
echo "  config: ${RVIZ_CONFIG}"
echo "  Press Ctrl-C to stop."

exec rviz2 -d "${RVIZ_CONFIG}"

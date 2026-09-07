#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=robot_env.sh
source "${SCRIPT_DIR}/robot_env.sh"

# rviz2 requires a display. It runs locally on the laptop, connecting to the
# robot over DDS (ROS_DOMAIN_ID must match — see robot_env.sh).
RVIZ_CONFIG="${SCRIPT_DIR}/../ros2_ws/src/slam_robot_bringup/rviz/slam_robot.rviz"

echo "Launching rviz2 to monitor ${ROBOT_HOST} (ROS_DOMAIN_ID=${ROS_DOMAIN_ID})..."
echo "  config: ${RVIZ_CONFIG}"
echo "  Press Ctrl-C to stop."

exec rviz2 -d "${RVIZ_CONFIG}"

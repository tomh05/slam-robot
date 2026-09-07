#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=robot_env.sh
source "${SCRIPT_DIR}/robot_env.sh"

echo "Starting robot core (motors enabled) on ${ROBOT_HOST}..."
ssh -t "${ROBOT_SSH}" \
    "source /opt/ros/jazzy/setup.bash && \
     source ${ROBOT_PROJECT_DIR}/ros2_ws/install/setup.bash && \
     ros2 launch slam_robot_bringup robot_core.launch.py motors_enabled:=true $*"

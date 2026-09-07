#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=robot_env.sh
source "${SCRIPT_DIR}/robot_env.sh"

# rviz2 requires a display. It runs locally on the laptop, connecting to the
# robot over DDS (ROS_DOMAIN_ID must match — see robot_env.sh).
RVIZ_CONFIG="${SCRIPT_DIR}/../ros2_ws/src/slam_robot_bringup/rviz/slam_robot.rviz"

# --------------------------------------------------------------------------
# Source the local ROS 2 installation so rviz2 and its DDS middleware are
# fully initialised with the right environment.
# ROS 2 setup scripts reference variables (e.g. AMENT_TRACE_SETUP_FILES) that
# may be unset, so temporarily disable `set -u` around the source calls.
# --------------------------------------------------------------------------
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

# --------------------------------------------------------------------------
# Configure DDS unicast discovery via ROS_STATIC_PEERS.
# By default Fast DDS uses UDP multicast for discovery, which many routers
# and WiFi networks block or rate-limit. Setting ROS_STATIC_PEERS tells
# Fast DDS to also send unicast discovery packets directly to the robot's
# IP, bypassing the need for working multicast.
# --------------------------------------------------------------------------
ROBOT_IP=""
if [[ "${ROBOT_HOST}" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    ROBOT_IP="${ROBOT_HOST}"
else
    ROBOT_IP="$(getent hosts "${ROBOT_HOST}" 2>/dev/null | awk '{print $1}' | head -n1 || true)"
fi

if [ -n "${ROBOT_IP}" ]; then
    export ROS_STATIC_PEERS="${ROBOT_IP}"
    echo "Using ROS_STATIC_PEERS=${ROS_STATIC_PEERS}"
else
    echo "Could not resolve ${ROBOT_HOST} to an IP — skipping ROS_STATIC_PEERS."
    echo "  Set ROBOT_HOST to an IP address in robot_env.sh for best results."
fi

echo "ROS_DOMAIN_ID=${ROS_DOMAIN_ID}"

# --------------------------------------------------------------------------
# Pre-flight: check that the robot's topics are visible over DDS.
# --------------------------------------------------------------------------
echo "Checking DDS discovery..."

if timeout 5 ros2 topic list --no-daemon 2>/dev/null | grep -qE "^/odom$|^/tf$"; then
    echo "  ✓ Robot topics visible over DDS — discovery OK"
else
    echo "  ✗ Cannot see /odom or /tf from the robot."
    echo ""
    echo "  Possible causes:"
    echo "  1. Robot core is not running. Start it with:"
    echo "       ./scripts/ros_start_no_motors.sh"
    echo "     (the old 'ros-start' script is gone — restart the robot.)"
    echo "  2. ROS_DOMAIN_ID mismatch. Robot and laptop must both use ${ROS_DOMAIN_ID}."
    echo "  3. Network multicast blocked or robot on a different subnet."
    echo "     ROS_STATIC_PEERS=${ROS_STATIC_PEERS:-unset} should help with this."
    echo "  4. Firewall on the robot blocking UDP traffic."
    echo ""
    echo "  Starting rviz2 anyway — you can re-check with: ros2 topic list"
fi

echo ""
echo "Launching rviz2 to monitor ${ROBOT_HOST}..."
echo "  config: ${RVIZ_CONFIG}"
echo "  Press Ctrl-C to stop."

exec rviz2 -d "${RVIZ_CONFIG}"

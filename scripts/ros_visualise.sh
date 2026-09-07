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
# Pre-flight: verify that the robot's topics and TF data are actually
# flowing over DDS, not just advertised.
# --------------------------------------------------------------------------
echo ""
echo "Checking DDS discovery and data flow..."

# 1. List visible topics
echo "  --- Visible topics ---"
timeout 5 ros2 topic list --no-daemon 2>/dev/null || true | sort | sed 's/^/  /'

# 2. Check for /tf and /odom specifically
echo ""
echo "  --- Key topic check ---"
TOPICS=$(timeout 5 ros2 topic list --no-daemon 2>/dev/null || true)

if echo "${TOPICS}" | grep -qx "/tf"; then
    echo "  ✓ /tf topic visible"
else
    echo "  ✗ /tf topic NOT visible"
    echo "     The robot's arduino_base_node may not be running."
    echo "     Restart it with: ./scripts/ros_start_no_motors.sh"
fi

if echo "${TOPICS}" | grep -qx "/odom"; then
    echo "  ✓ /odom topic visible"
else
    echo "  ✗ /odom topic NOT visible"
fi

# 3. Try to receive actual TF data
echo ""
echo "  --- Attempting to receive TF data (5s) ---"
TF_LINE=""
if command -v timeout &>/dev/null; then
    TF_LINE=$(timeout 5 ros2 topic echo /tf --no-arr 2>/dev/null | head -1 || true)
fi

if [ -n "${TF_LINE}" ]; then
    echo "  ✓ TF data received!"
elif echo "${TOPICS}" | grep -q "/tf"; then
    echo "  ~ /tf topic exists but no messages arrived in 5s."
    echo "    The robot is discovered but may not be sending TF."
    echo "    Check that the Arduino is connected and sending status lines."
    echo "    (arduino_base_node only publishes TF when it receives 'E' lines)"
else
    echo "  ✗ No /tf data received."
    echo "    Most likely: the robot is not running on ROS_DOMAIN_ID=${ROS_DOMAIN_ID}."
    echo "    1. Kill any old robot session: pkill -f 'ros2 launch'"
    echo "    2. Restart with: ./scripts/ros_start_no_motors.sh"
    echo "    3. If multicast is blocked, ROS_STATIC_PEERS=${ROS_STATIC_PEERS:-unset} handles it."
fi

echo ""
echo "Launching rviz2 to monitor ${ROBOT_HOST}..."
echo "  config: ${RVIZ_CONFIG}"
echo "  Press Ctrl-C to stop."

exec rviz2 -d "${RVIZ_CONFIG}"

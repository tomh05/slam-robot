#!/usr/bin/env bash
set -euo pipefail

# Record the ROS 2 inputs needed to diagnose map rotation/TF jumps.
# Run this on the same machine that is running the SLAM stack (normally the Pi).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
OUT_DIR="${1:-${PROJECT_ROOT}/diagnostic_bags}"
DURATION_SECONDS="${2:-${DURATION_SECONDS:-60}}"

if [ -f /opt/ros/jazzy/setup.bash ]; then
    set +u
    source /opt/ros/jazzy/setup.bash
    set -u
elif [ -f /opt/ros/humble/setup.bash ]; then
    set +u
    source /opt/ros/humble/setup.bash
    set -u
else
    echo "ROS 2 not found in /opt/ros/{jazzy,humble}" >&2
    exit 1
fi

mkdir -p "$OUT_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BAG_PATH="${OUT_DIR}/slam_diagnostic_${STAMP}"

export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"

echo "Recording SLAM diagnostics for ${DURATION_SECONDS}s"
echo "Bag: ${BAG_PATH}"

timeout "${DURATION_SECONDS}s" ros2 bag record \
    -o "$BAG_PATH" \
    /scan \
    /odom \
    /odometry/filtered \
    /imu/data \
    /cmd_vel \
    /tf \
    /tf_static \
    /map

#!/usr/bin/env bash
set -euo pipefail

# Optional helper: install YDLIDAR SDK and clone the ROS 2 driver into this repo's workspace.
# Use this only after the unknown lidar's raw serial stream looks YDLIDAR-compatible.
#
# Expected platform: Ubuntu 24.04 + ROS 2 Jazzy, or similar.
# The ydlidar_ros2_driver README currently recommends the 'humble' branch for Humble/Jazzy/etc.
#
# Usage from repo root on the robot:
#   ./scripts/install_ydlidar_ros2_driver.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
WS_DIR="${REPO_DIR}/ros2_ws"
VENDOR_DIR="${WS_DIR}/src/vendor_drivers"
SDK_DIR="${VENDOR_DIR}/YDLidar-SDK"
DRIVER_DIR="${VENDOR_DIR}/ydlidar_ros2_driver"

mkdir -p "${VENDOR_DIR}"

cat <<'EOF'
This will:
  1. Clone/update YDLIDAR/YDLidar-SDK.
  2. Build it.
  3. Run 'sudo make install' for the SDK.
  4. Clone/update YDLIDAR/ydlidar_ros2_driver branch 'humble'.
  5. Run rosdep and colcon build for the workspace.

Only continue if the lidar appears to speak a YDLIDAR-compatible protocol.
EOF

read -r -p "Continue? [y/N] " answer
case "${answer}" in
  y|Y|yes|YES) ;;
  *) echo "Aborted"; exit 0 ;;
esac

if [[ ! -d "${SDK_DIR}/.git" ]]; then
  git clone https://github.com/YDLIDAR/YDLidar-SDK.git "${SDK_DIR}"
else
  git -C "${SDK_DIR}" pull --ff-only
fi

cmake -S "${SDK_DIR}" -B "${SDK_DIR}/build" -DCMAKE_BUILD_TYPE=Release
cmake --build "${SDK_DIR}/build" --parallel "$(nproc)"
sudo cmake --install "${SDK_DIR}/build"

if [[ ! -d "${DRIVER_DIR}/.git" ]]; then
  git clone -b humble https://github.com/YDLIDAR/ydlidar_ros2_driver.git "${DRIVER_DIR}"
else
  git -C "${DRIVER_DIR}" fetch origin
  git -C "${DRIVER_DIR}" checkout humble
  git -C "${DRIVER_DIR}" pull --ff-only
fi

source /opt/ros/jazzy/setup.bash
cd "${WS_DIR}"
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install

cat <<EOF

Done.

Next steps:
  source ${WS_DIR}/install/setup.bash
  inspect ${DRIVER_DIR}/params/ydlidar.yaml
  set port, baudrate, lidar_type, frame_id
  try the driver's launch file

EOF

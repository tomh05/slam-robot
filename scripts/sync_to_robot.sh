#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
source "${SCRIPT_DIR}/robot_env.sh"

if ! command -v rsync >/dev/null 2>&1; then
  echo "rsync is required but was not found" >&2
  exit 1
fi

echo "Syncing ${REPO_DIR}/ to ${ROBOT_SSH}:${ROBOT_PROJECT_DIR}/"

ssh "${ROBOT_SSH}" "mkdir -p '${ROBOT_PROJECT_DIR}'"

rsync -az --delete \
  --exclude '.git/' \
  --exclude '.DS_Store' \
  --exclude 'ros2_ws/build/' \
  --exclude 'ros2_ws/install/' \
  --exclude 'ros2_ws/log/' \
  --exclude 'bags-from-robot/' \
  --exclude 'images/' \
  --exclude '*.bag' \
  --exclude '*.db3' \
  "${REPO_DIR}/" "${ROBOT_SSH}:${ROBOT_PROJECT_DIR}/"

echo "Done. To build on robot:"
echo "  ssh ${ROBOT_SSH}"
echo "  cd ${ROBOT_PROJECT_DIR}/ros2_ws"
echo "  source /opt/ros/jazzy/setup.bash"
echo "  rosdep install --from-paths src --ignore-src -r -y"
echo "  colcon build --symlink-install"

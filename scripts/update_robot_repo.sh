#!/usr/bin/env bash
# Sync the robot's local git clone to the latest commit, then rebuild the
# colcon workspace.  Run this after pushing changes to the repo's default
# branch so the robot picks up new code without a full rsync.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=robot_env.sh
source "${SCRIPT_DIR}/robot_env.sh"

REBUILD="${1:-yes}"
BRANCH="${2:-main}"

echo "Updating robot repo on ${ROBOT_HOST}..."
echo "  branch: ${BRANCH}"
echo "  rebuild: ${REBUILD}"
echo ""

ssh -t "${ROBOT_SSH}" bash -s <<REMOTE_EOF
set -e

cd "${ROBOT_PROJECT_DIR}"
echo "--- Fetching latest changes ---"
git fetch --all --prune
git checkout "${BRANCH}"
git pull origin "${BRANCH}"

echo "--- Stashing any uncommitted changes (preserved in git stash) ---"
if ! git diff --quiet; then
    git stash push -m "auto-stash before update_$(date +%s)"
    echo "  (stashed local changes — run 'git stash list' on the robot to recover)"
fi

if [ "${REBUILD}" = "yes" ]; then
    echo "--- Rebuilding workspace ---"
    source /opt/ros/jazzy/setup.bash
    rosdep install --from-paths src --ignore-src -r -y
    colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release
    echo ""
    echo "Build complete."
fi

echo ""
echo "Done. The robot's workspace is updated."
echo "Restart the robot with one of:"
echo "  ./scripts/ros_start_no_motors.sh    # safe — no motor control"
echo "  ./scripts/ros_start_with_motors.sh  # motors active — use with caution"
REMOTE_EOF

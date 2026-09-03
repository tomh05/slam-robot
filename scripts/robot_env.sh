#!/usr/bin/env bash
# Shared settings for helper scripts. Source this file, or let scripts source it.
# Edit these values for your robot.

export ROBOT_USER="ubuntu"
export ROBOT_HOST="slamrobot.local"
export ROBOT_SSH="${ROBOT_USER}@${ROBOT_HOST}"
export ROBOT_PROJECT_DIR="/home/${ROBOT_USER}/slam-robot"

# Must match on robot and laptop for ROS 2 discovery.
export ROS_DOMAIN_ID="42"

# Leave empty for default Fast DDS. Set to rmw_cyclonedds_cpp later if needed.
# export RMW_IMPLEMENTATION="rmw_cyclonedds_cpp"

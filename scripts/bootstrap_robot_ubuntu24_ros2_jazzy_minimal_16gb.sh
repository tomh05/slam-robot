#!/usr/bin/env bash
set -euo pipefail

# Minimal Raspberry Pi bootstrap for a 16 GB SD card.
# Target: Ubuntu Server 24.04 arm64 + ROS 2 Jazzy.
#
# This intentionally avoids large packages such as Nav2, ros2_control, Gazebo,
# and RViz. Add those later only if there is enough storage, or use a larger SD.
#
# Usage on the robot:
#   sudo ./scripts/bootstrap_robot_ubuntu24_ros2_jazzy_minimal_16gb.sh

if [[ $EUID -ne 0 ]]; then
  echo "Run as root, for example: sudo $0" >&2
  exit 1
fi

if ! grep -qi "ubuntu" /etc/os-release; then
  echo "This script expects Ubuntu. Aborting." >&2
  exit 1
fi

. /etc/os-release
if [[ "${VERSION_ID}" != "24.04" ]]; then
  echo "This script is for Ubuntu 24.04. Detected VERSION_ID=${VERSION_ID}." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y \
  software-properties-common \
  curl \
  gnupg \
  lsb-release \
  ca-certificates \
  locales

locale-gen en_US en_US.UTF-8
update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8

add-apt-repository universe -y

install -d -m 0755 /etc/apt/keyrings
curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
  -o /etc/apt/keyrings/ros-archive-keyring.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo "$UBUNTU_CODENAME") main" \
  > /etc/apt/sources.list.d/ros2.list

apt-get update
apt-get upgrade -y

apt-get install -y --no-install-recommends \
  ros-jazzy-ros-base \
  python3-rosdep \
  python3-colcon-common-extensions \
  python3-vcstool \
  python3-pip \
  python3-serial \
  git \
  build-essential \
  cmake \
  pkg-config \
  openssh-server \
  avahi-daemon \
  chrony \
  network-manager \
  htop \
  tmux \
  vim \
  rsync \
  usbutils \
  i2c-tools \
  gpiod \
  libgpiod-dev \
  ros-jazzy-robot-state-publisher \
  ros-jazzy-xacro \
  ros-jazzy-tf2-tools \
  ros-jazzy-teleop-twist-keyboard \
  ros-jazzy-slam-toolbox \
  ros-jazzy-diagnostic-updater

if [[ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]]; then
  rosdep init
fi

TARGET_USER="${SUDO_USER:-}"
if [[ -n "${TARGET_USER}" && "${TARGET_USER}" != "root" ]]; then
  sudo -u "${TARGET_USER}" rosdep update || true
  usermod -aG dialout,plugdev,video "${TARGET_USER}" || true
else
  rosdep update || true
fi

systemctl enable --now ssh
systemctl enable --now avahi-daemon
systemctl enable --now chrony
systemctl enable --now NetworkManager

if [[ -n "${TARGET_USER}" && "${TARGET_USER}" != "root" ]]; then
  USER_HOME="$(getent passwd "${TARGET_USER}" | cut -d: -f6)"
  BASHRC="${USER_HOME}/.bashrc"
  if ! grep -q "source /opt/ros/jazzy/setup.bash" "${BASHRC}"; then
    cat >> "${BASHRC}" <<'EOF'

# ROS 2 Jazzy
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=42
if [ -f "$HOME/slam-robot/ros2_ws/install/setup.bash" ]; then
  source "$HOME/slam-robot/ros2_ws/install/setup.bash"
fi
EOF
    chown "${TARGET_USER}:${TARGET_USER}" "${BASHRC}"
  fi
fi

apt-get autoremove -y
apt-get clean
rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

cat <<'EOF'

Minimal 16 GB bootstrap complete.

Recommended next steps:
  sudo hostnamectl set-hostname slamrobot
  sudo reboot

After reboot:
  df -h /
  ros2 run demo_nodes_cpp talker

Large packages intentionally NOT installed yet:
  - Nav2
  - ros2_control / ros2_controllers
  - RViz / desktop tools
  - Gazebo

EOF

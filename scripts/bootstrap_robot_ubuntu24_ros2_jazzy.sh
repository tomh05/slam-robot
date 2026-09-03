#!/usr/bin/env bash
set -euo pipefail

# Bootstrap a Raspberry Pi running Ubuntu Server 24.04 arm64 with ROS 2 Jazzy.
# Read before running. This script changes apt sources and installs packages.
#
# Usage on the robot:
#   chmod +x scripts/bootstrap_robot_ubuntu24_ros2_jazzy.sh
#   sudo scripts/bootstrap_robot_ubuntu24_ros2_jazzy.sh
#
# After it finishes, log out/in or source ~/.bashrc.

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
  echo "If you intentionally use another version, install ROS manually instead." >&2
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

# ROS 2 apt repository key and source.
install -d -m 0755 /etc/apt/keyrings
curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
  -o /etc/apt/keyrings/ros-archive-keyring.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo "$UBUNTU_CODENAME") main" \
  > /etc/apt/sources.list.d/ros2.list

apt-get update
apt-get upgrade -y

# Headless robot packages plus common robotics tools.
# ros-jazzy-ros-base is smaller than desktop. RViz normally runs on laptop.
apt-get install -y \
  ros-jazzy-ros-base \
  ros-dev-tools \
  python3-rosdep \
  python3-colcon-common-extensions \
  python3-vcstool \
  python3-pip \
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
  ros-jazzy-tf-transformations \
  ros-jazzy-teleop-twist-keyboard \
  ros-jazzy-joy \
  ros-jazzy-ros2-control \
  ros-jazzy-ros2-controllers \
  ros-jazzy-diff-drive-controller \
  ros-jazzy-joint-state-broadcaster \
  ros-jazzy-slam-toolbox \
  ros-jazzy-navigation2 \
  ros-jazzy-nav2-bringup \
  ros-jazzy-nav2-map-server \
  ros-jazzy-robot-localization \
  ros-jazzy-diagnostic-updater \
  ros-jazzy-rmw-cyclonedds-cpp

# Initialise rosdep if needed.
if [[ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]]; then
  rosdep init
fi

# Update rosdep as the invoking sudo user if possible.
TARGET_USER="${SUDO_USER:-}"
if [[ -n "${TARGET_USER}" && "${TARGET_USER}" != "root" ]]; then
  sudo -u "${TARGET_USER}" rosdep update || true
else
  rosdep update || true
fi

systemctl enable --now ssh
systemctl enable --now avahi-daemon
systemctl enable --now chrony
systemctl enable --now NetworkManager

# Serial/device access for Arduino Nano, USB-UART lidar adapters, cameras, etc.
if [[ -n "${TARGET_USER}" && "${TARGET_USER}" != "root" ]]; then
  usermod -aG dialout,plugdev,video "${TARGET_USER}" || true
fi

# Add convenient shell setup for the non-root user that invoked sudo.
if [[ -n "${TARGET_USER}" && "${TARGET_USER}" != "root" ]]; then
  USER_HOME="$(getent passwd "${TARGET_USER}" | cut -d: -f6)"
  BASHRC="${USER_HOME}/.bashrc"
  if ! grep -q "source /opt/ros/jazzy/setup.bash" "${BASHRC}"; then
    cat >> "${BASHRC}" <<'EOF'

# ROS 2 Jazzy
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=42
# Uncomment if Wi-Fi DDS discovery is unreliable and all machines use Cyclone DDS.
# export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
if [ -f "$HOME/slam-robot/ros2_ws/install/setup.bash" ]; then
  source "$HOME/slam-robot/ros2_ws/install/setup.bash"
fi
EOF
    chown "${TARGET_USER}:${TARGET_USER}" "${BASHRC}"
  fi
fi

cat <<'EOF'

Bootstrap complete.

Recommended next steps:
  1. Set hostname if needed:
       sudo hostnamectl set-hostname slamrobot
  2. Configure Wi-Fi if not already configured.
  3. Reboot:
       sudo reboot
  4. Test:
       ros2 run demo_nodes_cpp talker
       ros2 run demo_nodes_py listener

EOF

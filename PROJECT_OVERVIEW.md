# Tracked SLAM Robot Project

This repository is for planning and implementing the software stack for a small tracked robot using:

- Raspberry Pi, probably Raspberry Pi 4, as the onboard computer
- Two track drive motors with encoders
- A 2D lidar / laser range finder module (now confirmed to speak YDLIDAR packet protocol)
- ROS 2 as the robotics middleware

The goal is an autonomous robot that can run without a tethered computer, build a map of an unfamiliar indoor area, localise itself in that map, and expose enough ROS tooling over Wi-Fi that a laptop can inspect, debug, teleoperate, and visualise the robot.

## Documents

Use [`docs/README.md`](docs/README.md) as the single entry point for documentation.
It separates current reference docs from historical/session notes.

## Helper scripts

The scripts in [`scripts/`](scripts/) are starting points, not yet a complete installer:

- [`scripts/bootstrap_robot_ubuntu24_ros2_jazzy.sh`](scripts/bootstrap_robot_ubuntu24_ros2_jazzy.sh) — fuller package install for Ubuntu 24.04 + ROS 2 Jazzy on the Pi.
- [`scripts/bootstrap_robot_ubuntu24_ros2_jazzy_minimal_16gb.sh`](scripts/bootstrap_robot_ubuntu24_ros2_jazzy_minimal_16gb.sh) — leaner ROS 2 Jazzy bootstrap intended for a 16 GB SD card.
- [`scripts/setup_wifi_nmcli.sh`](scripts/setup_wifi_nmcli.sh) — example NetworkManager Wi-Fi setup.
- [`scripts/sync_to_robot.sh`](scripts/sync_to_robot.sh) — rsync-based deployment helper.
- [`scripts/robot_env.sh`](scripts/robot_env.sh) — local environment variables used by helper scripts.
- [`scripts/lidar_capture_serial.py`](scripts/lidar_capture_serial.py) — raw serial capture/baud probing helper for the unknown lidar.
- [`scripts/arduino_encoder_test.py`](scripts/arduino_encoder_test.py) — USB serial helper for manual motor-encoder bringup.
- [`scripts/flash_ubuntu_rpi_sd_macos.sh`](scripts/flash_ubuntu_rpi_sd_macos.sh) — macOS SD-card flashing helper for Ubuntu Raspberry Pi images; destructive and requires sudo.

Before running any script, read it and adjust hostnames, usernames, Wi-Fi details, and ROS domain IDs.

## Firmware starting points

- [`firmware/arduino_nano_base_controller/arduino_nano_base_controller.ino`](firmware/arduino_nano_base_controller/arduino_nano_base_controller.ino) — first Arduino Nano firmware skeleton for MX1508/HW-354 motor control and hall encoder counting.

## Current status

The repo now contains both planning docs and active ROS 2 packages under `ros2_ws/src/`.
The local `lidar-resources/` subtree remains reference material and includes ROS 1/catkin-era packages that should not be dropped into the ROS 2 workspace directly.

The lidar protocol has been validated as YDLIDAR-compatible in `docs/lidar-protocol-findings-2025-10-23.md`, and the active ROS 2 path is the in-repo `lidar_scan_publisher` package.

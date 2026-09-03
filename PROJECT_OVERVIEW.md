# Tracked SLAM Robot Project

This repository is for planning and implementing the software stack for a small tracked robot using:

- Raspberry Pi, probably Raspberry Pi 4, as the onboard computer
- Two track drive motors with encoders
- A 2D lidar / laser range finder kit, likely YDLIDAR based on the existing `lidar-resources/` folder
- ROS 2 as the robotics middleware

The goal is an autonomous robot that can run without a tethered computer, build a map of an unfamiliar indoor area, localise itself in that map, and expose enough ROS tooling over Wi-Fi that a laptop can inspect, debug, teleoperate, and visualise the robot.

## Documents

Read these in order:

1. [`docs/current-status.md`](docs/current-status.md) — current operational state and next-session entry point.
2. [`docs/raspberry-pi-setup-notes.md`](docs/raspberry-pi-setup-notes.md) — hard-won flashing, Wi-Fi, SSH, bootstrap, and recovery notes from the first successful Pi setup.
3. [`docs/requirements.md`](docs/requirements.md) — product requirements, constraints, assumptions, and acceptance criteria.
4. [`docs/architecture.md`](docs/architecture.md) — proposed ROS 2 architecture, node graph, data flow, package choices, and OS choice.
5. [`docs/implementation-plan.md`](docs/implementation-plan.md) — phased task plan from hardware inventory to autonomous navigation.
6. [`docs/development-workflow.md`](docs/development-workflow.md) — how to develop on a laptop and deploy to the robot quickly.
7. [`docs/hardware-inventory-template.md`](docs/hardware-inventory-template.md) — fill this in once exact part numbers, pins, and electrical details are known.
8. [`docs/lidar-module-notes.md`](docs/lidar-module-notes.md) — notes on the factory-test/MB_1R2T lidar module, YDLIDAR resources, pinout screenshots, and serial capture plan.
9. [`docs/lidar-mb-1r2t-ros2-port.md`](docs/lidar-mb-1r2t-ros2-port.md) — plan for porting the existing MB_1R2T community protocol/ROS 1 code to ROS 2.
10. [`docs/motor-control-arduino-nano-plan.md`](docs/motor-control-arduino-nano-plan.md) — proposed Raspberry Pi + Arduino Nano + HW-354 motor/encoder architecture.
11. [`docs/electrical-wiring-and-power-plan.md`](docs/electrical-wiring-and-power-plan.md) — concrete MX1508/HW-354 wiring, power warnings, and initial pin allocation.
12. [`docs/power-research-and-recommendation.md`](docs/power-research-and-recommendation.md) — internet-researched battery, regulator, runtime, safety, and shopping-list recommendation.
13. [`docs/aliexpress-power-shopping-list.md`](docs/aliexpress-power-shopping-list.md) — AliExpress-specific candidate parts, links, prices, and variant caveats.
14. [`docs/purchased-power-parts.md`](docs/purchased-power-parts.md) — actual power parts purchased, variants, prices, caveats, and arrival checklist.
15. [`docs/mains-bench-power-notes.md`](docs/mains-bench-power-notes.md) — recommendations for running the robot from a current-limited bench supply or regulated mains adapter during prototyping.
16. [`docs/encoder-bringup-test-plan.md`](docs/encoder-bringup-test-plan.md) — concrete Arduino encoder pinout and manual-spin test procedure.
13. [`docs/legacy-notes-summary.md`](docs/legacy-notes-summary.md) — cleaned-up summary of useful old notebook notes.
14. [`docs/old-sd-card-inspection.md`](docs/old-sd-card-inspection.md) — findings from inspecting the old Raspberry Pi SD card mounted at `/Volumes/writable`.
15. [`docs/open-questions.md`](docs/open-questions.md) — decisions and information still needed.

## Helper scripts

The scripts in [`scripts/`](scripts/) are starting points, not yet a complete installer:

- [`scripts/bootstrap_robot_ubuntu24_ros2_jazzy.sh`](scripts/bootstrap_robot_ubuntu24_ros2_jazzy.sh) — fuller package install for Ubuntu 24.04 + ROS 2 Jazzy on the Pi.
- [`scripts/bootstrap_robot_ubuntu24_ros2_jazzy_minimal_16gb.sh`](scripts/bootstrap_robot_ubuntu24_ros2_jazzy_minimal_16gb.sh) — leaner ROS 2 Jazzy bootstrap intended for a 16 GB SD card.
- [`scripts/setup_wifi_nmcli.sh`](scripts/setup_wifi_nmcli.sh) — example NetworkManager Wi-Fi setup.
- [`scripts/sync_to_robot.sh`](scripts/sync_to_robot.sh) — rsync-based deployment helper.
- [`scripts/robot_env.sh`](scripts/robot_env.sh) — local environment variables used by helper scripts.
- [`scripts/lidar_capture_serial.py`](scripts/lidar_capture_serial.py) — raw serial capture/baud probing helper for the unknown lidar.
- [`scripts/arduino_encoder_test.py`](scripts/arduino_encoder_test.py) — USB serial helper for manual motor-encoder bringup.
- [`scripts/install_ydlidar_ros2_driver.sh`](scripts/install_ydlidar_ros2_driver.sh) — optional YDLIDAR SDK/ROS 2 driver installer, only after raw data suggests YDLIDAR compatibility.
- [`scripts/flash_ubuntu_rpi_sd_macos.sh`](scripts/flash_ubuntu_rpi_sd_macos.sh) — macOS SD-card flashing helper for Ubuntu Raspberry Pi images; destructive and requires sudo.

Before running any script, read it and adjust hostnames, usernames, Wi-Fi details, and ROS domain IDs.

## Firmware starting points

- [`firmware/arduino_nano_base_controller/arduino_nano_base_controller.ino`](firmware/arduino_nano_base_controller/arduino_nano_base_controller.ino) — first Arduino Nano firmware skeleton for MX1508/HW-354 motor control and hall encoder counting.

## Current status

This repo currently only contains planning docs plus old lidar-related resources. The existing `lidar-resources/ydlidar_ros_driver-master` package appears to be a ROS 1 `catkin` package, so it should not be used directly in the future ROS 2 workspace. It can still help identify the lidar family and parameters.

The currently described lidar is very likely an MB_1R2T or compatible 5 V serial module. Existing community code has reverse engineered its `AA 55` packet protocol, so the preferred path is now to port that parser to ROS 2 rather than relying first on the generic YDLIDAR ROS 2 driver.

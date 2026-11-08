# slam-robot

A small indoor tracked robot project built around **ROS 2 Jazzy**, **2D LiDAR**, and **SLAM**. The robot is designed to run headless on a **Raspberry Pi 4** (2 GB), use an **Arduino Nano** for low-level motor/encoder control, and let a laptop connect over Wi-Fi for teleoperation, debugging, RViz visualisation, and map inspection.

This repository contains the project documentation, ROS 2 workspace packages, Arduino firmware, helper scripts, and notes from the hardware bring-up process. It is both a working project and a reference for others building a similar **ROS 2 + SLAM navigation robot** from modest hardware.

## Project aims

- Drive a tracked chassis under software control from ROS 2 (`/cmd_vel`).
- Read wheel/track encoder feedback and publish odometry.
- Publish 2D LiDAR scans as `sensor_msgs/LaserScan`.
- Build indoor maps with SLAM (`slam_toolbox`).
- Save and reload maps.
- Support localisation and Nav2-based navigation as the stack matures.
- Keep the robot autonomous on the Pi, with a laptop used for development and visualisation rather than core control.

## Current state

The project is actively in bring-up. What is already in place:

- Ubuntu Server 24.04 arm64 + ROS 2 Jazzy running on the Raspberry Pi 4.
- A ROS 2 workspace under `ros2_ws/src/` with project packages for the base, description, bringup, smoke test, and LiDAR scan publishing.
- Arduino Nano firmware for MX1508/HW-354 motor control and encoder counting over USB serial.
- A custom ROS 2 LiDAR publisher (`lidar_scan_publisher`) for the project’s YDLIDAR-compatible serial LiDAR module.
- URDF/TF setup for the measured chassis, with provisional platform/LiDAR mounting assumptions where hardware is not final.
- Detailed documentation covering architecture, wiring, Pi setup, workflow, LiDAR protocol findings, and open hardware decisions.

What still needs calibration/completion before relying on navigation:

- Encoder ticks-per-metre / effective wheel radius calibration on the floor.
- Skid-steer yaw/track-separation tuning.
- Final LiDAR mounting pose and scan-quality validation in the full robot stack.
- Final power architecture (battery, regulation, fuse, E-stop) for mobile operation.
- `slam_toolbox` mapping sessions and Nav2 tuning on the real robot.

For the latest session-level status, see [`docs/current-status.md`](docs/current-status.md).

## Hardware overview

The exact build is specific to this robot, but the architecture is reusable.

| Area | Current choice / notes |
|---|---|
| Compute | Raspberry Pi 4 Model B, 2 GB |
| OS / middleware | Ubuntu Server 24.04 LTS (arm64), ROS 2 Jazzy |
| Chassis | Small tracked/skid-steer base with two DC gear motors |
| Motor driver | HW-354 / MX1508 dual H-bridge; treat motor supply as **2–10 V** (do **not** apply 12 V directly) |
| Low-level controller | Arduino Nano clone (CH340 USB serial) for PWM motor outputs, encoder counting, and serial command timeout safety |
| Feedback | Motor hall encoders; currently used as single-channel tachometers with direction inferred from commanded motion (see encoder notes) |
| Range sensor | 5 V serial LiDAR module using a YDLIDAR-compatible packet protocol; integrated via `lidar_scan_publisher` |
| Development access | SSH over Wi-Fi, ROS 2 topics over the network, RViz/CLI tools from a laptop |

Hardware details, wiring, and provisional measurements are documented in [`docs/`](docs/README.md). If you are reproducing the project, verify your own motor driver ratings, encoder wiring, LiDAR serial level, and power budget before connecting hardware.

## Software architecture

```text
Laptop over Wi-Fi
  RViz 2 / ros2 CLI / teleop / logs
              |
              | SSH + ROS 2 DDS
              v
Raspberry Pi (ROS 2 Jazzy)
  lidar_scan_publisher      -> /scan
  slam_robot_base           -> /odom, odom -> base_link, Arduino serial bridge
  slam_robot_description    -> robot_state_publisher / TF
  slam_toolbox              -> /map, map -> odom        (mapping/localisation phase)
  Nav2                      -> /cmd_vel goals/planning  (navigation phase)
              |
              | USB serial
              v
Arduino Nano
  motor PWM + encoder counting + command timeout safety
              |
              v
HW-354 / MX1508 + motors/encoders
```

Key ROS interfaces:

- `/cmd_vel` (`geometry_msgs/Twist`) — velocity commands to the base.
- `/scan` (`sensor_msgs/LaserScan`) — 2D LiDAR data.
- `/odom` (`nav_msgs/Odometry`) — wheel/encoder odometry from the base node.
- `/arduino_base_node/status_raw` — raw Arduino status for bring-up/debugging.
- TF: `map -> odom -> base_link -> lidar_link` when SLAM/localisation is active.

For design details, see [`docs/architecture.md`](docs/architecture.md).

## Repository layout

```text
slam-robot/
├── README.md
├── PROJECT_OVERVIEW.md
├── docs/                         # project documentation and historical notes
├── firmware/                     # Arduino Nano base controller firmware
├── ros2_ws/src/
│   ├── slam_robot_base/          # /cmd_vel <-> Arduino serial, odom/TF publishing
│   ├── slam_robot_description/   # URDF/Xacro robot model and robot_state_publisher launch
│   ├── slam_robot_bringup/       # top-level bringup launch files and RViz config
│   ├── lidar_scan_publisher/     # custom ROS 2 LiDAR driver/decoder
│   └── slam_robot_smoke_test/    # simple ROS 2 smoke-test package
├── scripts/                      # bootstrap, sync, flashing, LiDAR/Arduino helpers
├── lidar-resources/              # vendor/reference LiDAR material (not ROS 2 packages to build directly)
├── laser-cuts/                   # chassis/platform design files
└── images/                       # local image artifacts (if present)
```

> Note: `lidar-resources/` contains reference material, including ROS 1/catkin-era packages. Do not drop it into the ROS 2 workspace as-is; the active ROS 2 LiDAR integration in this repo is `ros2_ws/src/lidar_scan_publisher`.

## Getting started

### 1. Read the docs

Start here:

1. [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md)
2. [`docs/README.md`](docs/README.md)
3. [`docs/current-status.md`](docs/current-status.md)
4. [`docs/requirements.md`](docs/requirements.md)
5. [`docs/architecture.md`](docs/architecture.md)
6. [`docs/development-workflow.md`](docs/development-workflow.md)

If you are working on specific subsystems:

- Wiring/power: [`docs/electrical-wiring-and-power-plan.md`](docs/electrical-wiring-and-power-plan.md)
- Motor/Arduino: [`docs/motor-control-arduino-nano-plan.md`](docs/motor-control-arduino-nano-plan.md), [`docs/encoder-bringup-test-plan.md`](docs/encoder-bringup-test-plan.md)
- LiDAR protocol: [`docs/lidar-protocol-findings-2025-10-23.md`](docs/lidar-protocol-findings-2025-10-23.md)
- Pi setup: [`docs/raspberry-pi-setup-notes.md`](docs/raspberry-pi-setup-notes.md)

### 2. Prepare the Raspberry Pi

The project targets **Ubuntu Server 24.04 arm64** and **ROS 2 Jazzy** on a Raspberry Pi. For small SD cards, use the minimal bootstrap:

```bash
cd ~/slam-robot
sudo ./scripts/bootstrap_robot_ubuntu24_ros2_jazzy_minimal_16gb.sh
```

Read any script before running it and adjust hostnames, usernames, Wi-Fi, and ROS domain settings. Helper scripts include:

- `scripts/flash_ubuntu_rpi_sd_macos.sh` — destructive macOS SD-card flashing helper.
- `scripts/bootstrap_robot_ubuntu24_ros2_jazzy_minimal_16gb.sh` — lean ROS 2 Jazzy bootstrap.
- `scripts/bootstrap_robot_ubuntu24_ros2_jazzy.sh` — fuller bootstrap for larger cards.
- `scripts/sync_to_robot.sh` / `scripts/robot_env.sh` — rsync deployment helpers.

### 3. Build the ROS 2 workspace

On the Pi (or a compatible ROS 2 Jazzy machine):

```bash
cd ~/slam-robot/ros2_ws
source /opt/ros/jazzy/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

For non-interactive SSH commands, remember to source `/opt/ros/jazzy/setup.bash` explicitly.

### 4. Start with safe bring-up

The base node is intentionally safe by default: `motors_enabled=false`, so `/cmd_vel` is ignored until explicitly enabled.

Example core bring-up:

```bash
source /opt/ros/jazzy/setup.bash
source ~/slam-robot/ros2_ws/install/setup.bash
ros2 launch slam_robot_bringup robot_core.launch.py
```

Useful checks:

```bash
ros2 topic echo /arduino_base_node/status_raw --once
ros2 topic echo /odom --once
ros2 topic echo /scan --once
```

Only enable motors when the robot is safely supported (tracks lifted for initial tests) and you have verified wiring, direction signs, and command timeout behaviour:

```bash
ros2 launch slam_robot_base arduino_base.launch.py motors_enabled:=true
```

## LiDAR notes

The project’s LiDAR module was initially undocumented in this repo, but its serial packet format was validated as YDLIDAR-compatible. Before modifying the LiDAR path, read:

- [`docs/lidar-module-notes.md`](docs/lidar-module-notes.md)
- [`docs/lidar-protocol-findings-2025-10-23.md`](docs/lidar-protocol-findings-2025-10-23.md)
- [`docs/lidar-mb-1r2t-ros2-port.md`](docs/lidar-mb-1r2t-ros2-port.md)

The active ROS 2 integration is `lidar_scan_publisher`. Helper scripts such as `scripts/lidar_capture_serial.py`, `scripts/lidar_debug.py`, `scripts/lidar_profile.py`, and `scripts/lidar_replay.py` are useful for capture and offline protocol/decoder checks.

## Using this repo as a reference

If you want to build your own ROS 2 SLAM robot, the most reusable parts of this project are:

- the **architecture split** between a Raspberry Pi (ROS, networking, SLAM) and a microcontroller (real-time motor/encoder I/O);
- the **incremental bring-up order**: SSH/ROS basics → LiDAR scans → TF/URDF → safe motor control → odometry → SLAM → navigation;
- the **documentation-first debugging trail** for unknown hardware (especially the LiDAR protocol notes);
- the practice of keeping **hardware-specific calibration in config** and using **standard ROS interfaces** (`/cmd_vel`, `/scan`, `/odom`, TF, map topics).

You will still need to adapt pin mappings, chassis geometry, encoder scaling, serial ports, motor driver limits, and power design to your own hardware.

## Safety

This is a mobile-robot hardware project. Treat it accordingly:

- Keep motor enablement off until wiring and direction are verified.
- Lift tracks off the ground for first motion tests.
- Use current-limited bench supplies during bring-up.
- Do not apply 12 V to the HW-354/MX1508 VCC rail unless your specific board is proven to support it.
- Add a physical power switch, fuse/current protection, and an emergency stop before untethered/mobile operation.
- Do not commit Wi-Fi credentials, passwords, SSH private keys, or other secrets.

## Documentation

Project docs live in [`docs/`](docs/README.md). Historical session notes are kept for traceability; when they disagree with newer reference docs, prefer the current reference docs listed in `docs/README.md` and the latest status in [`docs/current-status.md`](docs/current-status.md).

## License

This project is licensed under the MIT License. See [`LICENSE`](LICENSE) for details.

> Note: `lidar-resources/` and other third-party/reference materials included in this repository may have their own licenses or terms. Review those separately before redistributing them.


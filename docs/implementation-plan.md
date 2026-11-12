# Implementation Plan

This plan is written as a practical sequence of tasks. Each phase should end with something visible and testable before moving on.

## Phase 0: Repository and project setup

### Goals

- Keep all planning, scripts, configs, and code in this repository.
- Avoid losing context between future LLM sessions.

### Tasks

- [x] Create initial planning docs.
- [ ] Create a hardware inventory from [`hardware-inventory-template.md`](hardware-inventory-template.md).
- [ ] Decide final ROS 2 baseline: Jazzy on Ubuntu 24.04 unless blocked.
- [x] Create `ros2_ws/src/` once real ROS packages are started.
- [x] Add `.gitignore` for ROS build artifacts when workspace is created.

### Deliverables

- Human-readable docs.
- Scripts for repeatable setup.
- Hardware inventory populated with real part numbers and pinouts.

## Phase 1: Hardware identification and electrical sanity check

### Goals

Know exactly what is connected before writing GPIO/motor code.

### Tasks

- [x] Confirm Raspberry Pi model:
  - Pi 4 vs other.
  - RAM size.
  - SD card capacity.
  - Available USB ports.
- [ ] Identify lidar:
  - Manufacturer/model.
  - USB serial VID/PID.
  - Serial baud rate.
  - Supply voltage/current.
  - ROS 2 driver availability.
- [x] Identify motor driver as HW-354 / MX1508 with `VCC`, `GND`, `INA`, `INB`, `INC`, `IND`, `OUT1`-`OUT4`.
- [ ] Confirm HW-354 current rating and any board-specific jumpers/regulator/fault behaviour.
- [ ] Treat motor driver input voltage as 2-10 V; do not use 12 V directly.
- [ ] Identify motors and encoders:
  - Motor rated voltage/current.
  - Encoder signal type: quadrature A/B? Hall? single channel?
  - Encoder voltage level: 3.3 V or 5 V?
  - Ticks per motor revolution and gearbox ratio.
- [ ] Measure mechanical parameters:
  - [x] Track separation, centre-to-centre: measured/confirmed value 0.155 m.
  - [x] Effective sprocket/wheel radius: initial measured value 0.029 m.
  - [x] Track contact length: measured value 0.127 m.
  - [x] Overall footprint: measured value 0.185 m long x 0.204 m wide.
  - [x] Initial/provisional lidar pose: assume centred, 0.10 m scan-plane height above ground until mount is known.
  - [ ] Final lidar pose relative to robot centre after mount is built.
  - [ ] Floor-test effective ticks-per-metre and skid-steer yaw separation.
- [ ] Decide whether direct GPIO is safe.

### Acceptance test

- You can draw a wiring diagram and list every voltage crossing into the Pi.
- No 5 V signal is connected directly to Pi GPIO unless level shifted or confirmed safe.

## Phase 2: Provision Raspberry Pi OS and ROS 2

### Goals

Headless Pi with ROS 2, SSH, Wi-Fi, stable hostname, and package tooling.

### Recommended image

- Ubuntu Server 24.04 LTS arm64.
- ROS 2 Jazzy.

### Tasks

- [x] Flash OS image to SD card.
- [x] Configure initial Wi-Fi and SSH.
- [x] Boot Pi and update packages.
- [x] Set hostname, for example `slamrobot`.
- [x] Install ROS 2 Jazzy packages.
- [x] Install developer tools:
  - `git`
  - `python3-colcon-common-extensions`
  - `python3-rosdep`
  - `python3-vcstool`
  - `chrony`
  - `avahi-daemon`
- [x] Add robot user to serial/device groups, especially `dialout`, as the old SD card did:

```bash
sudo usermod -aG dialout $USER
```

- [x] Configure shell environment:
  - source `/opt/ros/jazzy/setup.bash`
  - set `ROS_DOMAIN_ID`
  - optionally set `RMW_IMPLEMENTATION`
- [x] Create SSH key login from laptop.

### Helpful scripts

For a normal/larger SD card, see [`../scripts/bootstrap_robot_ubuntu24_ros2_jazzy.sh`](../scripts/bootstrap_robot_ubuntu24_ros2_jazzy.sh).

For the current 16 GB card, prefer the leaner [`../scripts/bootstrap_robot_ubuntu24_ros2_jazzy_minimal_16gb.sh`](../scripts/bootstrap_robot_ubuntu24_ros2_jazzy_minimal_16gb.sh). It avoids Nav2, RViz, Gazebo, and ros2_control initially to preserve space.

### Acceptance test

On the robot:

```bash
ros2 --version
ros2 doctor
```

Across two terminals on the robot:

```bash
# Terminal 1
ros2 run demo_nodes_cpp talker

# Terminal 2
ros2 run demo_nodes_py listener
```

From laptop:

```bash
ssh robot@slamrobot.local
```

## Phase 3: Laptop development and remote deployment workflow

### Goals

Develop from the laptop but run hardware code on the Pi.

### Tasks

- [ ] Decide laptop environment:
  - Native Ubuntu, best for RViz.
  - Ubuntu VM/devcontainer, good from macOS/Windows.
  - SSH-only editor plus RViz on robot/laptop later.
- [x] Configure SSH key.
- [ ] Set matching `ROS_DOMAIN_ID` on laptop and robot.
- [x] Use `scripts/sync_to_robot.sh` to copy repo to robot.
- [x] Build on robot with `colcon build`.
- [ ] Use VS Code Remote SSH, terminal SSH, or equivalent for rapid iteration.

### Acceptance test

- Change a file locally, sync it to robot, build on robot, and run a trivial ROS 2 node or launch file.

## Phase 4: Lidar bringup

### Goals

Maintain and validate the current lidar integration and scan quality in ROS 2.

### Tasks

- [x] Read [`lidar-module-notes.md`](lidar-module-notes.md).
- [x] Read [`lidar-mb-1r2t-ros2-port.md`](lidar-mb-1r2t-ros2-port.md).
- [ ] Confirm connector orientation against the saved pinout screenshot.
- [ ] Power the lidar from a current-limited/stable 5 V supply.
- [ ] Measure serial output voltage level before connecting it to Pi UART/GPIO.
- [ ] Prefer initial capture using a USB-UART adapter with appropriate input-voltage tolerance or level shifting.
- [x] Capture raw serial data at the two likely baud rates:

```bash
python3 -m pip install pyserial
python3 scripts/lidar_capture_serial.py --list
python3 scripts/lidar_capture_serial.py --port /dev/ttyUSB0 --baud 158700 --seconds 5 --out captures/mb1r2t_158700.bin
python3 scripts/lidar_capture_serial.py --port /dev/ttyUSB0 --baud 153600 --seconds 5 --out captures/mb1r2t_153600.bin
```

- [x] Confirm packet framing/checksum and repeated `AA 55` headers in captures.
- [x] Implement ROS 2 lidar node in `ros2_ws/src/lidar_scan_publisher`.
- [x] Publish `sensor_msgs/LaserScan` on `/scan` using `frame_id:=lidar_link`.
- [ ] Optionally test `YDLIDAR/ydlidar_ros2_driver`, but treat it as secondary.
- [ ] Once a USB serial device is used on the Pi, find device path:

```bash
lsusb
ls -l /dev/serial/by-id/
dmesg -w
```

- [ ] Create udev rule for stable path, e.g. `/dev/ydlidar`.
- [ ] Configure lidar model/driver parameters:
  - serial port
  - baud rate
  - frame id, e.g. `lidar_link`
  - angle limits
  - range limits
  - scan frequency
- [ ] Run driver and echo scan:

```bash
ros2 topic list
ros2 topic echo /scan --once
ros2 topic hz /scan
```

- [ ] Visualise in RViz 2.

### Driver path

For this hardware, reference source material was:

- <https://github.com/stdlogicvector/MB_1R2T_LIDAR_Demo>
- <https://github.com/Vidicon/mb_1r2t_ros>

The official `YDLIDAR/ydlidar_ros2_driver` remains a fallback/experiment path rather than the primary in-repo integration.

### Acceptance test

- `/scan` publishes at expected rate.
- Obstacles appear in the correct direction in RViz.
- Lidar frame is correctly named and later transformable to `base_link`.

## Phase 5: Robot description and TF

### Goals

Define robot geometry in URDF/Xacro and establish the TF tree.

### Tasks

- [x] Create `slam_robot_description` package.
- [x] Define `base_link` and optionally `base_footprint`.
- [x] Add visual/collision approximations for chassis and tracks.
- [x] Add `lidar_link` at measured pose.
- [ ] Add wheel/track joints if using `diff_drive_controller` joint state integration.
- [x] Start `robot_state_publisher`.
- [ ] Create RViz config showing:
  - TF
  - robot model
  - laser scan
  - odometry
  - map later

### Acceptance test

```bash
ros2 run tf2_tools view_frames
```

- TF tree has no missing parent frames.
- RViz fixed frame can be set to `base_link` before SLAM and `map` during SLAM.

## Phase 6: Motor and encoder bringup

### Goals

Move the robot safely and read encoder feedback.

### Tasks

- [ ] Lift robot tracks off the ground for first powered tests.
- [ ] Verify motor driver enable/disable behaviour.
- [ ] Verify left/right motor direction.
- [ ] Read raw encoder counts without moving.
- [ ] Spin each track slowly and verify encoder signs.
- [ ] Read [`motor-control-arduino-nano-plan.md`](motor-control-arduino-nano-plan.md).
- [ ] Read [`electrical-wiring-and-power-plan.md`](electrical-wiring-and-power-plan.md).
- [x] Review/upload initial firmware skeleton at `firmware/arduino_nano_base_controller/arduino_nano_base_controller.ino`.
- [x] Implement/test Arduino Nano firmware skeleton for HW-354 and hall encoders:
  - serial command parsing
  - encoder counting
  - per-motor PWM/direction output
  - command timeout stop
  - periodic encoder/status report
- [x] Implement first ROS 2 base interface as a simple Pi-side node skeleton:
  - subscribe `/cmd_vel`
  - send left/right tick-rate commands to Arduino
  - read encoder reports
  - publish `/odom` and TF
- [ ] Consider `ros2_control` hardware interface later, after serial protocol is stable.
- [ ] Add command timeout safety on both Arduino and Pi side.
- [ ] Add speed limits.
- [ ] Publish diagnostics/raw counts for testing.
- [ ] Teleop at very low speed.

### Acceptance test

- With robot lifted, `/cmd_vel` forward drives both tracks forward.
- With robot on floor, robot drives slowly forward, backward, and turns.
- Releasing teleop key stops the robot quickly.
- Encoder counts and signs match commanded motion.

## Phase 7: Odometry calibration

### Goals

Make encoder odometry plausible enough for SLAM.

### Tasks

- [x] Set initial track separation and wheel/sprocket radius from measured values (`track_width_m=0.155`, `wheel_radius_m=0.029`).
- [ ] Drive forward a measured distance at low speed.
- [ ] Compare odometry distance vs tape-measure distance.
- [ ] Rotate in place by a measured angle.
- [ ] Compare odometry yaw vs actual yaw.
- [ ] Adjust parameters.
- [ ] Set odometry covariance realistically; tracked yaw will be noisy.
- [ ] Record rosbag of calibration runs.

### Acceptance test

- Driving straight 1 m produces odometry within a tolerable first-pass error, e.g. under 10-20% before lidar correction.
- Turning 90 degrees produces odometry yaw with correct sign and roughly correct magnitude.
- TF `odom -> base_link` is continuous and not jumping.

## Phase 8: SLAM bringup

### Goals

Generate a first usable 2D occupancy map while teleoperating, using existing lidar/base/TF/odometry components.

### Prerequisites (gates)

- [ ] Sync and build latest workspace on Pi: `./scripts/sync_to_robot.sh` then `cd ~/slam-robot/ros2_ws && source /opt/ros/jazzy/setup.bash && colcon build --symlink-install && source install/setup.bash`.
- [ ] Install SLAM deps on Pi (headless): `sudo apt install -y ros-jazzy-slam-toolbox` and optionally `ros-jazzy-nav2-map-server` for `map_saver_cli`.
- [ ] Odometry/TF contract chosen (exactly one `odom -> base_link` publisher):
  - Preferred: `ros2 launch slam_robot_bringup robot_core_ekf.launch.py` (EKF publishes TF, use `/odometry/filtered` as local odom).
  - Fallback: `ros2 launch slam_robot_bringup robot_core.launch.py` (raw `/odom`, base publishes TF) if EKF/IMU not validated.
- [ ] Input checks pass: `ros2 topic hz /scan` (and `/odometry/filtered` or `/odom`), `ros2 run tf2_ros tf2_echo odom base_link`, `ros2 run tf2_tools view_frames` shows `odom->base_link->lidar_link` with sane `/scan` `frame_id` and orientation.
- [ ] Calibration sanity: floor ticks-per-metre/yaw separation and lidar/IMU alignment good enough for slow mapping; motors safe (lifted for first motion tests).

### Planned bringup/config additions (`ros2_ws/src/slam_robot_bringup`)

- [ ] Add `config/slam_toolbox_mapping.yaml` (online async mapping): `use_sim_time: false`, frames `map`/`odom`/`base_link` (or consistent `base_footprint`), `scan_topic: /scan`, conservative update/timeout/resolution settings for slow tracked motion.
- [ ] Add `launch/slam_mapping.launch.py` to start `slam_toolbox` with the mapping params (keep base/lidar/description layers separable per `docs/architecture.md`).
- [ ] Update `slam_robot_bringup/CMakeLists.txt` and `package.xml` to install `config/` and new launch, and add `exec_depend` on `slam_toolbox` (and `nav2_map_server` if used for saving).

### Tasks

- [ ] Static sensor check: core stack + `lidar_scan_publisher` (e.g. `scripts/start_robot_local.sh` or separate terminals), confirm `/scan` in RViz.
- [ ] Start SLAM: launch `slam_mapping.launch.py` with selected odom/TF source; confirm `/map` and `map->odom` are published.
- [ ] Teleoperate slowly around a small area (smooth turns, minimal slip); visualise `/map`, `/scan`, TF, robot model in RViz (fixed frame `map`).
- [ ] Tune if distorted (in order): TF/odom rates & source, lidar pose/orientation/timestamps, odom/EKF calibration & covariances, then `slam_toolbox` params (transform timeout, min travel/heading update, resolution, matcher/buffer).
- [ ] Save map.

### Commands

```bash
# Example: core + lidar (separate terminals as needed), then SLAM
ros2 launch slam_robot_bringup slam_mapping.launch.py

# Save map (after ros-jazzy-nav2-map-server install)
mkdir -p ~/maps
ros2 run nav2_map_server map_saver_cli -f ~/maps/test_map
```

### Acceptance test

- A recognisable occupancy grid map is produced with stable `map -> odom -> base_link -> lidar_link` TF.
- The map can be saved as `.yaml` + image and reloaded for inspection.
- Restarting RViz can display the saved map.

## Phase 9: Localisation and Nav2

### Goals

Use a saved map to navigate to simple goals.

### Tasks

- [ ] Start map server with saved map.
- [ ] Start localisation:
  - AMCL, or
  - `slam_toolbox` localisation mode.
- [ ] Configure Nav2 costmaps using lidar obstacle layer.
- [ ] Configure robot footprint.
- [ ] Configure velocity and acceleration limits conservatively.
- [ ] Test global planning without motors enabled.
- [ ] Test navigation with tracks lifted, then on floor at low speed.
- [ ] Tune controller for tracked base behaviour.

### Acceptance test

- Robot localises in saved map after initial pose is set.
- Robot accepts a goal from RViz.
- Robot moves toward goal and stops safely.
- Obstacles appear in local costmap.

## Phase 10: Autostart and field operation

### Goals

Robot boots into a selected mode and can be debugged remotely.

### Tasks

- [ ] Create `systemd` service for robot bringup.
- [ ] Write service environment file with ROS variables.
- [ ] Add commands to stop/start/status logs:

```bash
sudo systemctl status slam-robot
journalctl -u slam-robot -f
```

- [ ] Store maps under a clear path, e.g. `/home/robot/maps`.
- [ ] Add log rotation or bag storage policy.
- [ ] Add battery monitor if hardware supports it.
- [ ] Add physical or software E-stop.

### Acceptance test

- Robot boots, joins Wi-Fi, and starts selected ROS launch file.
- Laptop can connect and view topics.
- Service can be stopped and robot motors disable.

## Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---:|---:|---|
| Lidar driver is ROS 1 only | Medium | High | Identify exact model; use current ROS 2 driver or write thin driver around SDK. |
| Pi misses encoder counts | Medium | Medium/High | Use MCU or motor controller for encoder counting. |
| Track slip makes odometry poor | High | Medium | Use lidar SLAM, low speeds, careful calibration, add IMU. |
| ROS 2 discovery unreliable over Wi-Fi | Medium | Medium | Use same domain, Cyclone DDS, direct AP/travel router, Foxglove bridge. |
| Power brownouts reset Pi | Medium | High | Separate regulator for Pi, adequate current, fuses, battery monitor. |
| Motor driver electrical mismatch | Unknown | High | Identify parts before connecting to Pi. Use level shifting and common ground correctly. |
| Nav2 tuning takes time | High | Medium | Start with teleop SLAM; test Nav2 at very low speed. |

## Suggested immediate next actions

1. **Validate SLAM prerequisites on Pi:** sync/build latest repo, install `ros-jazzy-slam-toolbox` (+ `nav2_map_server` if needed), and confirm a clean input set: `/scan`, chosen odom (`/odometry/filtered` preferred via `robot_core_ekf.launch.py` or raw `/odom`), and a single `odom->base_link` TF source.
2. **Check calibration/alignment before mapping:** floor-test ticks-per-metre and effective skid-steer yaw, confirm lidar/IMU mounting/orientation, and review odom/IMU covariances (tracked slip will dominate map quality).
3. **Add SLAM bringup in `slam_robot_bringup`:** `config/slam_toolbox_mapping.yaml`, `launch/slam_mapping.launch.py`, and package install/exec dependencies per Phase 8.
4. **Run first mapping session:** static scan check, slow teleop in a small area, save map to `~/maps/`, and tune from artifacts (TF/odom/lidar first, then SLAM params).
5. **After a good map:** proceed to Phase 9 (localization mode / Nav2) and resolve remaining power/safety/open hardware items in [`open-questions.md`](open-questions.md).

# Requirements Specification

## 1. Project vision

Build a small tracked mobile robot that can:

1. Drive under software control using two track motors.
2. Read wheel/track encoder positions for odometry.
3. Read 2D lidar scans.
4. Perform simultaneous localisation and mapping, SLAM, in an indoor environment.
5. Save a generated map.
6. Later localise within a saved map and navigate autonomously.
7. Run all core autonomy onboard the Raspberry Pi.
8. Allow a laptop to connect over Wi-Fi for debugging, teleoperation, logs, and map visualisation.

## 2. Known hardware

Known now:

- Onboard computer: Raspberry Pi 4 Model B, 2 GB RAM.
- Drive base: tracked chassis with two motors; old chassis link: <https://www.aliexpress.com/item/32800078967.html>.
- Feedback: motor hall-effect encoders/sensors.
- Range sensor: factory-test 5 V serial module with YDLIDAR-compatible packet protocol (validated in [`lidar-protocol-findings-2025-10-23.md`](lidar-protocol-findings-2025-10-23.md)).
- Low-level controller: an Arduino Nano was previously used to detect motor positions and drive motors.
- Motor driver: HW-354 dual motor controller, MX1508 based, with `INA`/`INB` for Motor A and `INC`/`IND` for Motor B. Motor driver VCC should be treated as 2-10 V, so 12 V must not be connected directly.

To be confirmed later:

- Raspberry Pi storage size and current SD card contents.
- Raspberry Pi OS currently installed, if any.
- Lidar exact retail model, serial voltage level, and final scan-rate configuration.
- Motor driver part number, voltage/current rating, and control interface.
- Encoder type: quadrature? ticks per revolution? voltage level? whether connected to motor shaft or output shaft.
- Battery voltage, regulator capacity, and power isolation.
- Whether an IMU exists or should be added.
- Physical dimensions: track width, track contact length, effective wheel radius/sprocket radius, lidar pose.

Use [`hardware-inventory-template.md`](hardware-inventory-template.md) to record these details.

## 3. Functional requirements

### 3.1 Base drive

- The robot shall support differential-drive/skid-steer velocity commands:
  - linear velocity `v` in m/s
  - angular velocity `omega` in rad/s
- The robot shall accept ROS 2 `geometry_msgs/Twist` commands on `/cmd_vel`.
- The robot shall translate `/cmd_vel` into left and right motor commands.
- The robot shall enforce speed, acceleration, and command-timeout safety limits.
- The robot shall stop if command input becomes stale.
- The robot shall expose encoder-derived odometry as `nav_msgs/Odometry`, normally on `/odom`.
- The robot shall publish the transform `odom -> base_link`.

### 3.2 Encoders and motor control

- The system shall read incremental encoder counts from both tracks.
- The system shall estimate wheel/track velocities and integrated pose.
- The software shall support calibration parameters:
  - left and right encoder ticks per revolution
  - left and right direction inversion
  - effective wheel/sprocket radius
  - track separation
  - gearbox ratio, if needed
- The motor control loop shall run fast enough for stable motion.
- Preferred implementation: use the Arduino Nano for low-level PID, PWM output, and encoder counting, with the Raspberry Pi sending velocity targets over USB serial.
- Acceptable later refactor: wrap the Arduino serial protocol in a `ros2_control` hardware interface and use `diff_drive_controller`.
- Raspberry Pi direct GPIO motor/encoder control is no longer the preferred first prototype because an Arduino Nano is available and better suited to interrupt-heavy encoder I/O.

### 3.3 Lidar

- The robot shall connect to a 2D laser range finder.
- The lidar driver shall publish `sensor_msgs/LaserScan`, normally on `/scan`.
- The lidar shall be mounted rigidly and its transform to `base_link` shall be published as `base_link -> laser` or `base_link -> lidar_link`.
- The lidar driver shall be ROS 2 compatible.
- The primary lidar path is the in-repo ROS 2 `lidar_scan_publisher` node publishing `sensor_msgs/LaserScan`.
- The existing `lidar-resources/ydlidar_ros_driver-master` package and `Vidicon/mb_1r2t_ros` are ROS 1/catkin and shall not be used directly as final packages.
- `YDLIDAR/ydlidar_ros2_driver` remains an optional comparison path, but current project integration uses the in-repo driver.
- The project shall still include a lidar validation step before depending on it for SLAM.
- If the lidar hardware is dead or data quality is poor, the project shall allow substituting a known ROS 2-supported 2D lidar without changing the rest of the stack.

### 3.4 SLAM and mapping

- The robot shall support online SLAM using wheel odometry plus lidar scans.
- The proposed first SLAM backend is `slam_toolbox`.
- While mapping, the system shall publish:
  - `/map` as `nav_msgs/OccupancyGrid`
  - `map -> odom` transform
  - robot pose in the map frame
- The system shall save generated maps to disk using ROS 2 map server tooling.
- The system shall allow map visualisation from a laptop using RViz 2 or Foxglove.

### 3.5 Localisation and navigation

Initial phase:

- The robot shall be manually teleoperated while building maps.
- The robot shall be able to stop safely from keyboard/controller teleop.

Later phase:

- The robot shall localise in a saved map.
- The robot shall accept navigation goals from RViz 2 or another UI.
- The robot shall plan paths and follow them using Nav2.
- The robot shall avoid obstacles detected by lidar.
- The robot shall recover or stop safely when navigation fails.

### 3.6 Laptop debugging and visualisation

- A laptop shall connect to the robot over Wi-Fi/SSH.
- The laptop shall be able to run RViz 2 and inspect ROS topics from the robot.
- The laptop shall be able to teleoperate the robot for testing.
- The laptop shall be able to view logs and restart robot services.
- The system shall support a repeatable deployment method from laptop to robot.

### 3.7 Optional future sensors

The architecture shall leave room for:

- Camera streaming or visual odometry.
- IMU fusion.
- Bumper switches.
- Battery voltage/current monitoring.
- Docking/charging behaviours.

## 4. Non-functional requirements

### 4.1 Autonomy and headless operation

- Core robot software shall start without monitor, keyboard, or laptop.
- The robot shall eventually run selected launch files as `systemd` services.
- Network loss shall not crash mapping/localisation, though remote visualisation will stop.

### 4.2 Reliability

- The robot shall fail safe: stopped motors are the default if software crashes or command timeout expires.
- Motor power and Pi power should be electrically robust against brownouts.
- Logs shall be kept for debugging after failures.
- Launch files shall make hardware assumptions explicit through config files.

### 4.3 Maintainability

- The software shall be organised as ROS 2 packages in a workspace.
- Hardware-specific configuration shall live in YAML/Xacro files, not scattered through code.
- Bringup launch files shall support sim/fake-hardware mode where practical.
- Scripts and docs shall be kept in version control.

### 4.4 Performance

Target starting values, to be refined after hardware testing:

- Lidar scan rate: 5-10 Hz or device default.
- Encoder/control update rate: at least 30 Hz, preferably 50-100 Hz.
- TF publication: 30-50 Hz.
- SLAM update: real-time on Raspberry Pi 4 for modest indoor environments.
- Robot speed for early testing: capped low, around 0.1-0.2 m/s.

### 4.5 Security and access

- SSH password login should eventually be disabled in favour of SSH keys.
- The robot should use a stable hostname, for example `slamrobot.local`.
- Wi-Fi credentials should not be committed to git.
- ROS 2 discovery should be scoped using a project-specific `ROS_DOMAIN_ID`.

## 5. Constraints and design assumptions

- The robot is a tracked/skid-steer platform. Odometry will be less accurate than ideal wheeled differential drive because tracks slip while turning.
- Lidar SLAM can correct much of the odometry drift, but good calibration still matters.
- Raspberry Pi GPIO is not ideal for hard real-time motor control or high-rate encoder counting. A dedicated motor controller or microcontroller is recommended if direct GPIO proves unreliable.
- ROS 2 package support is strongest on Ubuntu LTS releases. For new work, Ubuntu Server 24.04 arm64 + ROS 2 Jazzy is the recommended baseline.
- If a needed sensor driver is unavailable or unstable on Jazzy, Ubuntu 22.04 + ROS 2 Humble is the fallback baseline.

## 6. Acceptance criteria by milestone

### Milestone A: Pi provisioned

- Fresh 64-bit OS boots on Raspberry Pi.
- SSH works over Wi-Fi.
- ROS 2 command-line tools work.
- Laptop can ping/SSH the robot by hostname or stable IP.

### Milestone B: Lidar bringup

- Lidar appears as a stable device path, for example `/dev/ydlidar`.
- ROS 2 lidar driver publishes `/scan`.
- RViz 2 on laptop can visualise laser scans.

### Milestone C: Motor bringup

- Robot can drive forward/backward/turn under manual low-speed command.
- Motors stop on command timeout.
- Encoder counts increase/decrease consistently.
- Basic odometry is published.

### Milestone D: TF and robot model

- `base_link`, wheel/track frames, and lidar frame are represented in URDF/Xacro.
- TF tree is valid: `map -> odom -> base_link -> lidar_link` once SLAM is active.
- RViz displays robot model, scans, and odometry.

### Milestone E: SLAM

- Manual driving produces a coherent map of a room or hallway.
- Map can be saved and reloaded.
- Localisation drift is bounded well enough for indoor navigation experiments.

### Milestone F: Navigation

- Nav2 can accept a goal in a saved map.
- Robot plans and follows a path at low speed.
- Robot stops or replans around obstacles.

## 7. Out of scope for the first version

- Outdoor navigation.
- High-speed operation.
- Multi-floor mapping.
- Robust people avoidance beyond standard Nav2 obstacle handling.
- Fully unattended exploration until base motion, SLAM, and safety are reliable.

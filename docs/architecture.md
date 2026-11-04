# Proposed Architecture

## 1. Recommended software baseline

### Primary recommendation

Use:

- **OS:** Ubuntu Server 24.04 LTS, 64-bit arm64, on the Raspberry Pi 4.
- **ROS:** ROS 2 Jazzy Jalisco.
- **Middleware/RMW:** start with default Fast DDS; switch to Cyclone DDS if discovery or Wi-Fi reliability is poor.
- **Laptop visualisation:** RViz 2 on an Ubuntu machine/VM, or Foxglove Studio connected through ROS bridge tooling.

Why:

- ROS 2 Jazzy is an LTS release paired with Ubuntu 24.04.
- It has active support for `slam_toolbox`, Nav2, `ros2_control`, `robot_localization`, and modern ROS 2 tooling.
- Raspberry Pi 4 can run 64-bit Ubuntu Server and headless ROS 2 workloads.

### Fallback option

If lidar or motor-control package support is poor on Jazzy, use:

- Ubuntu Server 22.04 LTS arm64
- ROS 2 Humble Hawksbill

Humble has older but very broad driver support. Only choose this if a critical driver is easier there.

## 2. High-level ROS 2 stack

```text
                           Laptop over Wi-Fi
                 +--------------------------------+
                 | RViz 2 / Foxglove / ros2 CLI   |
                 | teleop_twist_keyboard / logs   |
                 +----------------+---------------+
                                  |
                                  | ROS 2 DDS + SSH
                                  |
+---------------------------------v----------------------------------+
|                        Raspberry Pi robot                          |
|                                                                    |
| +--------------------+      +------------------------------------+  |
| | lidar driver       | ---> | /scan sensor_msgs/LaserScan        |  |
| +--------------------+      +------------------------------------+  |
|                                                                    |
| +--------------------+      +------------------------------------+  |
| | motor/encoder I/O  | ---> | ros2_control hardware interface    |  |
| | or MCU bridge      | <--- | diff_drive_controller              |  |
| +--------------------+      +------------------------------------+  |
|                                      |                             |
|                                      v                             |
|                             /odom + odom->base_link                |
|                                                                    |
| +--------------------+      +------------------------------------+  |
| | robot_state_pub    | ---> | static/dynamic robot TF             |  |
| +--------------------+      +------------------------------------+  |
|                                                                    |
| +--------------------+      +------------------------------------+  |
| | slam_toolbox       | <--- | /scan + /odom + TF                  |  |
| |                    | ---> | /map + map->odom                    |  |
| +--------------------+      +------------------------------------+  |
|                                                                    |
| +--------------------+      +------------------------------------+  |
| | Nav2, later        | <--- | /map + /scan + /odom + TF + goals   |  |
| |                    | ---> | /cmd_vel                            |  |
| +--------------------+      +------------------------------------+  |
+--------------------------------------------------------------------+
```

## 3. Frames and transforms

Use standard ROS mobile-base frames:

- `map`: global frame produced by SLAM/localisation.
- `odom`: locally continuous odometry frame. Drifts over time.
- `base_link`: robot body frame.
- `base_footprint`: optional planar projection of base, useful for Nav2.
- `left_track_link`, `right_track_link`: visual/collision frames if modelling tracks.
- `lidar_link` or `laser`: physical lidar frame.
- `camera_link`: future optional camera.
- `imu_link`: future optional IMU.

Expected TF chain during SLAM:

```text
map -> odom -> base_link -> lidar_link
```

Responsibilities:

- `diff_drive_controller` or base driver publishes `odom -> base_link`.
- `robot_state_publisher` publishes static robot geometry from URDF/Xacro.
- `slam_toolbox` publishes `map -> odom`.
- Static transform publisher or URDF publishes `base_link -> lidar_link`.

## 4. Core ROS packages and why

### 4.1 Lidar driver

The lidar packet format has been validated as YDLIDAR-compatible and is integrated through an in-repo ROS 2 package.

Primary path for this module:

- Use `ros2_ws/src/lidar_scan_publisher` as the project lidar driver.
- Keep protocol logic in the unit-testable decoder module.
- Publish `sensor_msgs/LaserScan` on `/scan`.
- Use `frame_id:=lidar_link`.

Secondary experiment:

- `ydlidar_ros2_driver` from YDLIDAR's current ROS 2 repositories does exist.
- Its README currently says to use the `humble` branch for Humble/Jazzy-era ROS 2.
- It may be worth testing as a cross-check or fallback, but it is not the current integration path.

Alternatives depending on actual hardware:

- RPLIDAR: `sllidar_ros2` or maintained `rplidar_ros` ROS 2 branches.
- LDROBOT/LDLidar: `ldlidar_stl_ros2` or vendor package.
- Generic serial lidar: vendor ROS 2 package or direct `sensor_msgs/LaserScan` node.

Important note:

- The existing `lidar-resources/ydlidar_ros_driver-master` has a ROS 1 `catkin` `package.xml`, so it is useful as reference only.
- `Vidicon/mb_1r2t_ros` is also ROS 1/catkin and remains historical source material only.
- See [`lidar-module-notes.md`](lidar-module-notes.md) for pinout screenshots and serial capture procedure.
- See [`lidar-protocol-findings-2025-10-23.md`](lidar-protocol-findings-2025-10-23.md) for protocol validation and decoder notes.

### 4.2 Base drive and odometry

Confirmed available hardware suggests this pattern:

```text
Raspberry Pi ROS 2 node <-> USB serial <-> Arduino Nano <-> HW-354 motor controller <-> motors + hall encoders
```

This is now the recommended first architecture. See [`motor-control-arduino-nano-plan.md`](motor-control-arduino-nano-plan.md) and [`electrical-wiring-and-power-plan.md`](electrical-wiring-and-power-plan.md).

Why:

- Encoder edge counting is timing-sensitive.
- Arduino PWM and interrupts are simpler and more deterministic than Raspberry Pi userspace GPIO.
- The Pi stays focused on ROS 2, lidar, SLAM, networking, and high-level navigation.
- The Arduino can enforce a motor stop if serial commands time out.

ROS 2 integration can be staged:

#### Option A: Simple base node, recommended first

- A custom `slam_robot_base_node` subscribes to `/cmd_vel`.
- It converts velocity commands into left/right target tick rates.
- It sends serial commands to the Arduino.
- It reads encoder counts from the Arduino.
- It publishes `/odom` and `odom -> base_link`.

This is the quickest path to a ROS-controlled moving robot.

#### Option B: `ros2_control` hardware interface, cleaner later

- A custom `ros2_control` hardware interface talks to the Arduino over serial.
- `diff_drive_controller` handles `/cmd_vel`, odometry, limits, and TF.

This is a good refactor after the serial protocol and Arduino firmware are stable.

#### Option C: Raspberry Pi direct GPIO, fallback/prototype only

```text
Pi GPIO/PWM -> motor driver inputs
Pi GPIO interrupts/libgpiod/pigpio -> quadrature encoders
```

Advantages:

- Fewer boards.
- Fast initial experiment if motor driver is simple.

Risks:

- Encoder misses at high rate.
- PWM/loop timing jitter.
- Electrical damage if encoders are 5 V and Pi GPIO is 3.3 V only.
- More custom code.

Recommendation: do not start with Pi direct GPIO now that an Arduino Nano is available. Use direct GPIO only for isolated experiments if the Arduino path is blocked.

### 4.3 Robot model

Use:

- `robot_state_publisher`
- URDF/Xacro description package

Proposed package:

- `slam_robot_description`

Contents:

- `urdf/slam_robot.urdf.xacro`
- `config/physical_params.yaml`
- meshes later, simple boxes/cylinders first

### 4.4 State estimation

Initial:

- Encoder odometry directly from `diff_drive_controller`.
- Lidar SLAM consumes `/odom` and `/scan`.

Later:

- Add `robot_localization` `ekf_node` if an IMU is added.
- Fuse wheel odometry + IMU into `/odometry/filtered`.
- Configure SLAM/Nav2 to use filtered odometry.

For a tracked platform, an IMU is strongly recommended later because track slip during turns degrades encoder-only yaw.

### 4.5 SLAM

Use:

- `slam_toolbox`

Modes:

- Online async mapping for manual exploration.
- Localisation mode against a saved map for navigation.

Inputs:

- `/scan`
- TF tree including `odom -> base_link` and `base_link -> lidar_link`

Outputs:

- `/map`
- `map -> odom`
- pose graph services/actions

### 4.6 Navigation

Use:

- Nav2 stack
- `nav2_bringup`
- `controller_server`
- `planner_server`
- `bt_navigator`
- `costmap_2d`
- `map_server`
- `amcl` or `slam_toolbox` localisation mode

Recommended first navigation mode:

1. Build and save a map using `slam_toolbox`.
2. Start Nav2 using the saved map.
3. Use AMCL or `slam_toolbox` localisation mode.
4. Send goals from RViz.

Because this is a tracked robot, keep speeds low and tune acceleration limits conservatively.

## 5. Proposed workspace layout

The repository can evolve into this layout:

```text
slam-robot/
  PROJECT_OVERVIEW.md
  docs/
  scripts/
  ros2_ws/
    src/
      slam_robot_bringup/
        launch/
        config/
        package.xml
      slam_robot_description/
        urdf/
        meshes/
        rviz/
        package.xml
      slam_robot_base/
        src/
        include/
        config/
        package.xml
      lidar_scan_publisher/
      slam_robot_msgs/              # only if custom messages become necessary
```

Package responsibilities:

### `slam_robot_bringup`

- Top-level launch files.
- Hardware vs fake-hardware arguments.
- Robot-wide YAML configuration.
- Starts lidar, base controller, robot description, SLAM, and later Nav2.

### `slam_robot_description`

- URDF/Xacro.
- Static transforms embedded in robot model.
- RViz display configs.

### `slam_robot_base`

- Custom hardware interface or MCU bridge.
- Encoder conversion and motor command interface if not handled by off-the-shelf package.
- Diagnostics for battery/motor controller if available.

### `slam_robot_msgs`

Avoid custom messages at first. Add only if the base controller needs robot-specific diagnostics not covered by standard messages.

## 6. Runtime launch layers

Use multiple launch files rather than one huge launch file:

- `description.launch.py`
  - robot_state_publisher
  - static transforms if not in URDF
- `base.launch.py`
  - ros2_control controller manager
  - diff_drive_controller
  - base hardware interface/MCU bridge
- `lidar.launch.py`
  - lidar driver
  - device path and lidar model config
- `slam.launch.py`
  - `slam_toolbox` online mapping
- `localization.launch.py`
  - map server + AMCL or slam_toolbox localisation mode
- `navigation.launch.py`
  - Nav2
- `bringup.launch.py`
  - includes the required set for a chosen mode

Suggested bringup modes:

- `mode:=teleop` — base + lidar + description, no SLAM.
- `mode:=mapping` — base + lidar + description + SLAM.
- `mode:=navigation` — base + lidar + description + localisation + Nav2.
- `use_sim_time:=true/false` — for bag replay/simulation later.
- `use_fake_base:=true/false` — for laptop testing without hardware.

## 7. Network architecture

### Robot identity

- Hostname: `slamrobot`
- mDNS name: `slamrobot.local`
- SSH user: choose one, for example `robot`

### ROS 2 domain

Set the same domain on robot and laptop:

```bash
export ROS_DOMAIN_ID=42
```

Keep this out of common domains to avoid discovering unrelated robots/nodes.

### DDS over Wi-Fi

ROS 2 uses DDS discovery, often multicast. Home and university Wi-Fi networks may block or degrade multicast.

Start simple:

- Same Wi-Fi network.
- Same `ROS_DOMAIN_ID`.
- Test `ros2 topic list` from laptop.

If unreliable:

- Switch both robot and laptop to Cyclone DDS.
- Add explicit peer/discovery configuration.
- Consider a direct robot access point or travel router for field use.
- Consider Foxglove bridge if RViz/DDS discovery is painful from macOS.

### Time synchronisation

Install `chrony` on robot. Accurate wall time helps logs and bag analysis. TF itself uses robot-local ROS time, but multi-machine setups are easier when clocks are close.

## 8. Data logging

Use `ros2 bag` to record reproducible test data.

Recommended bags:

- Lidar-only:
  - `/scan`
  - `/tf`
  - `/tf_static`
- Base odometry:
  - `/odom`
  - `/joint_states`
  - `/cmd_vel`
  - `/tf`
  - `/tf_static`
- SLAM session:
  - `/scan`
  - `/odom`
  - `/map`
  - `/tf`
  - `/tf_static`
  - `/cmd_vel`

Bags let you tune SLAM and visualise failures without repeatedly driving the robot.

## 9. Safety architecture

Minimum software safety:

- `cmd_vel` timeout in base controller, e.g. 0.25-0.5 s.
- Max linear/angular speed limits.
- Acceleration limits.
- E-stop topic/service or physical switch if available.
- Motors disabled until base node is healthy.
- Motors disabled on node shutdown.

Recommended hardware safety:

- Physical power switch.
- Fuse or current limiting.
- Motor power separate from Pi power regulator.
- Do not feed 12 V directly into the HW-354/MX1508 motor driver; treat its VCC as 2-10 V unless a board-specific datasheet proves otherwise.
- Common ground only where required by motor driver design.
- Level shifters for any 5 V encoder outputs into Pi GPIO.

## 10. Development strategy

Work in vertical slices:

1. SSH and ROS 2 basics.
2. Lidar publishes scans.
3. Robot model and TF are correct.
4. Base moves slowly under teleop.
5. Encoder odometry looks plausible.
6. SLAM produces a simple map.
7. Save/reload map.
8. Nav2 sends safe low-speed goals.

Do not start by writing a full autonomy stack. Get each sensor/actuator observable in ROS first, then combine them.

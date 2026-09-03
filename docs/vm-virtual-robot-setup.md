# VM / Virtual Robot Development Setup

Last updated: 2026-09-03.

## Purpose

This document captures the local VM setup, fake/simulated robot nodes, launch files, RViz config, and helper scripts added so development can continue away from the Raspberry Pi. Read this at the start of any session that involves rviz2, bag replay, or local simulation on the laptop/VM.

## Target environment

- **Host:** macOS with UTM
- **Guest OS:** Ubuntu Desktop 24.04 LTS (not Server)
- **ROS distro:** ROS 2 Jazzy Jalisco
- **ROS domain ID:** `42`
- **Repo path in VM:** `~/slam-robot`
- **Workspace path:** `~/slam-robot/ros2_ws`

## Why Desktop, not Server

rviz2 needs a graphical display. Server can run it over SSH with software rendering, but it is slow and unreliable inside a VM. Desktop gives a normal X11/Wayland session and makes rviz2, debugging, and Gazebo usable.

## VM resource recommendations

- **CPU:** 4 cores
- **RAM:** 4 GB minimum, 6–8 GB preferred
- **Disk:** 25 GB dynamically expanding
- **Display:** enable OpenGL acceleration in UTM if available

## One-time setup inside the VM

```bash
# 1. Install ROS 2 Jazzy Desktop
# Follow https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debians.html
sudo apt update
sudo apt install ros-jazzy-desktop

# 2. Add ROS to shell
echo "source /opt/ros/jazzy/setup.bash" >> ~/.bashrc
echo "export ROS_DOMAIN_ID=42" >> ~/.bashrc
source ~/.bashrc

# 3. Get the repo
git clone <repo-url> ~/slam-robot
cd ~/slam-robot/ros2_ws

# 4. Install Python dependencies and build
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

## Quick start: launch the virtual robot and rviz2

```bash
cd ~/slam-robot
./scripts/start_virtual_robot.sh
```

This single command:
1. Sources ROS + workspace
2. Launches `virtual_robot.launch.py` in the background
3. Opens RViz2 with the pre-configured display config
4. Cleans up the launch tree when RViz2 closes

## Driving the virtual robot

Open a second terminal in the VM:

```bash
source /opt/ros/jazzy/setup.bash
source ~/slam-robot/ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=42
```

### Drive forward
```bash
rostopic pub /cmd_vel geometry_msgs/Twist \
  "{linear: {x: 0.1}, angular: {z: 0.0}}" \
  --rate 10 -l 30
```

### Turn in place
```bash
rostopic pub /cmd_vel geometry_msgs/Twist \
  "{linear: {x: 0.0}, angular: {z: 0.5}}" \
  --rate 10 -l 30
```

### Stop immediately
```bash
rostopic pub /cmd_vel geometry_msgs/Twist \
  "{linear: {x: 0.0}, angular: {z: 0.0}}" -1
```

### Verify topics
```bash
ros2 topic list
ros2 topic echo /odom --once
ros2 topic echo /scan --once
ros2 topic hz /scan
```

### Verify TF
```bash
ros2 run tf2_tools view_frames
evince frames.pdf
```

## Virtual robot architecture

```
/cmd_vel ──► fake_base_node ──► /odom + odom→base_link TF
                                    │
                                    ▼
                          fake_lidar_node (subscribes /odom)
                                    │
                                    ▼
                                  /scan
```

### fake_base_node
- **Package:** `slam_robot_base`
- **Executable:** `fake_base_node`
- **Source:** `ros2_ws/src/slam_robot_base/slam_robot_base/fake_base_node.py`
- **Behavior:** Subscribes `/cmd_vel`, integrates differential-drive kinematics, publishes `/odom` and `odom→base_link` TF at 50 Hz
- **Parameters:** `track_width_m`, `wheel_radius_m`, `max_linear_mps`, `max_angular_rps`, `publish_rate_hz`
- **Timeout:** Drifts to zero after 0.5 s of no `/cmd_vel` input

### fake_lidar_node
- **Package:** `slam_robot_base`
- **Executable:** `fake_lidar_node`
- **Source:** `ros2_ws/src/slam_robot_base/slam_robot_base/fake_lidar_node.py`
- **Behavior:** Ray-casts against a virtual rectangular room with interior obstacles in the `odom` frame; publishes `/scan` as `sensor_msgs/LaserScan`
- **Parameters:** `frame_id`, `publish_rate_hz`, `range_min`, `range_max`, `angle_min`, `angle_max`, `angle_increment`, `noise_std`
- **Default scan:** 1° increments, 10 Hz, ±π, range 0.1–10 m

## Launch files

| Launch file | Purpose |
|-------------|---------|
| `slam_robot_base/launch/fake_base.launch.py` | Starts `fake_base_node` |
| `slam_robot_base/launch/fake_lidar.launch.py` | Starts `fake_lidar_node` |
| `slam_robot_bringup/launch/virtual_robot.launch.py` | Starts `robot_state_publisher` + fake base + fake lidar |

### virtual_robot.launch.py arguments

```bash
ros2 launch slam_robot_bringup virtual_robot.launch.py \
  use_fake_base:=true \
  use_fake_lidar:=true \
  use_sim_time:=false
```

- `use_fake_base`: If `true`, starts `fake_base_node`. If `false`, starts `arduino_base_node` (real hardware).
- `use_fake_lidar`: If `true`, starts `fake_lidar_node`.
- `use_sim_time`: Passed to `robot_state_publisher`. Set `true` when replaying bags.

## RViz configuration

- **Config file:** `ros2_ws/src/slam_robot_bringup/rviz/slam_robot.rviz`
- **Fixed frame:** `odom`
- **Displays:** Grid, TF, RobotModel, Odometry arrow, LaserScan (flat squares, 3 px)
- **Installed by:** `slam_robot_bringup/CMakeLists.txt` installs the `rviz/` directory

## Helper scripts

| Script | Purpose |
|--------|---------|
| `scripts/start_virtual_robot.sh` | Builds workspace, launches virtual robot stack, opens RViz2, cleans up on exit |

## Differences from real robot stack

| Aspect | Real robot (Pi) | Virtual robot (VM) |
|--------|-----------------|-------------------|
| Base node | `arduino_base_node` (serial) | `fake_base_node` (simulated) |
| Lidar node | MB_1R2T parser (future) | `fake_lidar_node` (ray-cast) |
| Hardware dependencies | Arduino Nano, lidar, motors | None |
| Serial port | `/dev/ttyUSB0` | N/A |
| Use case | Hardware testing, calibration | rviz2, SLAM tuning, bag replay, development away from Pi |

## Developing on VM, deploying to Pi

1. Edit code on the VM (or Mac, synced to VM)
2. Build in VM: `colcon build --symlink-install`
3. Commit/push changes
4. Sync repo to Pi: `./scripts/sync_to_robot.sh`
5. Build on Pi: `ssh ubuntu@slamrobot.local 'cd ~/slam-robot/ros2_ws && colcon build --symlink-install'`

## Network / DDS notes

- Both Pi and VM must be on the same Wi-Fi network
- Both must have `ROS_DOMAIN_ID=42`
- If discovery is flaky, try switching both to Cyclone DDS:
  ```bash
  export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
  ```

## Recording and replaying bags

### Record on Pi (near hardware)
```bash
ros2 bag record -o ~/bags/test_drive_01 /scan /odom /tf /tf_static /cmd_vel
```

### Copy to Mac/VM
```bash
rsync -av ubuntu@slamrobot.local:~/bags/ ~/slam-robot/bags/
```

### Replay in VM
```bash
ros2 bag play ~/slam-robot/bags/test_drive_01 --clock
ros2 launch slam_robot_bringup virtual_robot.launch.py use_sim_time:=true
rviz2
```

## Known issues / gotchas

- **UTM OpenGL:** If rviz2 shows black screen or GL errors, try `export LIBGL_ALWAYS_SOFTWARE=1` before launching, or install `mesa-utils`.
- **ROS domain mismatch:** If topics don't appear in rviz2, confirm `ROS_DOMAIN_ID` matches on both machines (`echo $ROS_DOMAIN_ID`).
- **Multicast blocked:** Some Wi-Fi networks block DDS multicast. If topics don't cross machines, switch to Cyclone DDS or use a direct hotspot.
- **Serial port missing:** The fake base node does not need a serial port. Do not try to run `arduino_base_node` in the VM without hardware — it will fail on missing `/dev/ttyUSB0`.

## Files added in this setup

- `slam_robot_base/slam_robot_base/fake_base_node.py`
- `slam_robot_base/slam_robot_base/fake_lidar_node.py`
- `slam_robot_base/launch/fake_base.launch.py`
- `slam_robot_base/launch/fake_lidar.launch.py`
- `slam_robot_bringup/launch/virtual_robot.launch.py`
- `slam_robot_bringup/rviz/slam_robot.rviz`
- `scripts/start_virtual_robot.sh`

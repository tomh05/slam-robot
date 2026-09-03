# Development and Deployment Workflow

## 1. Design goal

The robot should run autonomy onboard, but development should be comfortable from a laptop.

The recommended workflow is:

1. Edit files on laptop.
2. Sync repository to Raspberry Pi over SSH.
3. Build and run on Raspberry Pi for hardware tests.
4. Use laptop for RViz 2/Foxglove/terminal debugging.
5. Record ROS bags on robot for repeatable offline analysis.

## 2. Machine roles

### Raspberry Pi robot

Runs:

- ROS 2 core robot nodes.
- Lidar driver.
- Motor/encoder interface.
- SLAM/localisation/Nav2.
- `systemd` service eventually.

The Pi is the source of truth for hardware integration.

### Laptop

Runs any combination of:

- Code editor.
- SSH terminal.
- RViz 2, if laptop has Ubuntu/ROS 2.
- Foxglove Studio, if preferred.
- `ros2` CLI tools, if ROS 2 installed locally.
- Git client.

If your laptop is macOS, native ROS 2 graphical tooling can be awkward. Practical options:

- Use VS Code Remote SSH into the Pi and run most commands on the Pi.
- Run Ubuntu in a VM for RViz 2.
- Use Foxglove Studio with a bridge on the robot for visualisation.
- Use a separate Ubuntu laptop/mini PC for heavy ROS visualisation.

## 3. Network setup

### Recommended names

- Robot hostname: `slamrobot`
- Robot mDNS name: `slamrobot.local`
- Robot SSH user: `robot` or your chosen Ubuntu user
- ROS domain: `42` or another project-specific number

Set `ROS_DOMAIN_ID` on every machine that should see robot topics:

```bash
export ROS_DOMAIN_ID=42
```

### SSH setup

From laptop:

```bash
ssh-keygen -t ed25519 -C "slamrobot"
ssh-copy-id robot@slamrobot.local
ssh robot@slamrobot.local
```

If `ssh-copy-id` is unavailable on macOS, copy the public key manually:

```bash
cat ~/.ssh/id_ed25519.pub
```

Then append it to `~/.ssh/authorized_keys` on the robot.

### Testing ROS 2 network visibility

On robot:

```bash
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=42
ros2 run demo_nodes_cpp talker
```

On laptop with ROS 2 installed:

```bash
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=42
ros2 topic list
ros2 topic echo /chatter
```

If laptop cannot see topics:

- Confirm both machines are on the same network.
- Confirm matching `ROS_DOMAIN_ID`.
- Check firewall rules.
- Check whether Wi-Fi blocks multicast.
- Try Cyclone DDS explicit peer configuration later.

## 4. Repository layout for development

This repo can contain both docs/scripts and the ROS workspace:

```text
slam-robot/
  docs/
  scripts/
  ros2_ws/
    src/
      slam_robot_bringup/
      slam_robot_description/
      slam_robot_base/
```

Build artifacts should not be committed:

```text
ros2_ws/build/
ros2_ws/install/
ros2_ws/log/
```

## 5. Sync-based deployment

For early development, simple `rsync` is enough.

1. Configure [`../scripts/robot_env.sh`](../scripts/robot_env.sh).
2. Run:

```bash
./scripts/sync_to_robot.sh
```

This copies the repository to the robot, excluding common build artifacts and large irrelevant files.

Then SSH in and build:

```bash
ssh robot@slamrobot.local
cd ~/slam-robot/ros2_ws
source /opt/ros/jazzy/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

`--symlink-install` makes Python/config/launch changes faster because many files do not require reinstall copies.

## 6. Git-based deployment alternative

Once the project is in a remote git repository:

On robot:

```bash
cd ~
git clone <repo-url> slam-robot
cd slam-robot
```

For updates:

```bash
git pull
cd ros2_ws
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
```

This is cleaner than rsync when the repo is pushed regularly. Rsync is still faster for local experiments.

## 7. Building on the robot

Typical command:

```bash
cd ~/slam-robot/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=RelWithDebInfo
source install/setup.bash
```

For a single package:

```bash
colcon build --symlink-install --packages-select slam_robot_base
```

For tests:

```bash
colcon test
colcon test-result --verbose
```

## 8. Running launch files

Eventually launch files should look like:

```bash
ros2 launch slam_robot_bringup bringup.launch.py mode:=mapping
```

Possible modes:

```bash
mode:=teleop
mode:=mapping
mode:=navigation
```

During development, run pieces separately:

```bash
ros2 launch slam_robot_description description.launch.py
ros2 launch slam_robot_bringup lidar.launch.py
ros2 launch slam_robot_bringup base.launch.py
ros2 launch slam_robot_bringup slam.launch.py
```

## 9. Teleoperation

Keyboard teleop example:

```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args -r /cmd_vel:=/cmd_vel
```

Safety rules:

- First tests with tracks lifted.
- Very low max velocity.
- Command timeout enabled in base controller.
- Keep power switch accessible.

## 10. Visualisation

### RViz 2

On Ubuntu laptop with ROS 2:

```bash
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=42
rviz2
```

Useful RViz displays:

- TF
- RobotModel
- LaserScan `/scan`
- Odometry `/odom`
- Map `/map`
- Nav2 costmaps later

### Foxglove

If ROS discovery to laptop is difficult, consider running a bridge on the robot and connecting Foxglove Studio from the laptop. This can be simpler from macOS.

Possible future package:

- `foxglove_bridge`

## 11. Recording debug data

Record bags on the robot:

```bash
mkdir -p ~/bags
ros2 bag record -o ~/bags/lidar_test /scan /tf /tf_static
```

For SLAM:

```bash
ros2 bag record -o ~/bags/slam_test /scan /odom /cmd_vel /tf /tf_static /map
```

Copy bags back to laptop:

```bash
rsync -av robot@slamrobot.local:~/bags/ ./bags-from-robot/
```

Replay:

```bash
ros2 bag play ./bags-from-robot/slam_test
```

## 12. Autostart later with systemd

Once bringup is stable, create a service similar to:

```ini
[Unit]
Description=SLAM Robot Bringup
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=robot
Environment=ROS_DOMAIN_ID=42
Environment=RMW_IMPLEMENTATION=rmw_fastrtps_cpp
ExecStart=/bin/bash -lc 'source /opt/ros/jazzy/setup.bash && source /home/robot/slam-robot/ros2_ws/install/setup.bash && ros2 launch slam_robot_bringup bringup.launch.py mode:=mapping'
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Commands:

```bash
sudo systemctl daemon-reload
sudo systemctl enable slam-robot
sudo systemctl start slam-robot
sudo systemctl status slam-robot
journalctl -u slam-robot -f
```

Do not enable autostart until motor safety has been tested thoroughly.

## 13. Recommended environment files

On robot, append to `~/.bashrc` after ROS is installed:

```bash
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=42
# export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp  # if using Cyclone DDS later
if [ -f ~/slam-robot/ros2_ws/install/setup.bash ]; then
  source ~/slam-robot/ros2_ws/install/setup.bash
fi
```

On laptop, set matching `ROS_DOMAIN_ID` when using ROS tools.

## 14. Common debug commands

```bash
# Topics and rates
ros2 topic list
ros2 topic hz /scan
ros2 topic hz /odom
ros2 topic echo /scan --once

# Nodes
ros2 node list
ros2 node info /some_node

# TF
ros2 run tf2_tools view_frames
ros2 run tf2_ros tf2_echo base_link lidar_link
ros2 run tf2_ros tf2_echo odom base_link

# Parameters
ros2 param list
ros2 param get /some_node some_param

# Services/actions
ros2 service list
ros2 action list

# System
journalctl -u slam-robot -f
htop
dmesg -w
ls -l /dev/serial/by-id/
```

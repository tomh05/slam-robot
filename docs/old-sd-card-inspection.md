# Old SD Card Inspection Notes

Mounted old Raspberry Pi root filesystem inspected at:

```text
/Volumes/writable
```

Date inspected: 2026-07-27.

## 1. Summary

The old SD card appears to contain an early Raspberry Pi ROS 2 setup, not a completed robot software stack.

Main findings:

- OS: Ubuntu 22.04.1 LTS, Jammy.
- Architecture: arm64 Raspberry Pi image.
- Hostname: `ubuntu`.
- User: `ubuntu`.
- ROS: ROS 2 Humble installed under `/opt/ros/humble`.
- Installed ROS package set appears to be `ros-humble-ros-base`, not desktop, Nav2, slam_toolbox, ros2_control, or custom robot packages.
- No custom robot `systemd` services found in accessible system directories.
- Boot config enabled I2C and SPI.
- User `ubuntu` is in `dialout`, useful for serial access to Arduino/lidar devices.
- The old user home directory exists but was not readable from the current macOS mount because of Unix permissions. Any old workspace/sketches are most likely there if they still exist.

## 2. OS details

From `/Volumes/writable/etc/os-release`:

```text
Ubuntu 22.04.1 LTS (Jammy Jellyfish)
VERSION_ID=22.04
VERSION_CODENAME=jammy
```

This matches ROS 2 Humble's supported Ubuntu release.

## 3. ROS installation

ROS apt source:

```text
/Volumes/writable/etc/apt/sources.list.d/ros2.list
```

Contains ROS 2 Jammy repository:

```text
http://packages.ros.org/ros2/ubuntu jammy main
```

Apt history shows:

```text
apt install ros-humble-ros-base
```

`/opt/ros/humble` exists and contains standard ROS 2 Humble packages.

Important packages present include:

- `ros-humble-ros-base`
- `ros-humble-rclcpp`
- `ros-humble-rclpy`
- `ros-humble-sensor-msgs`
- `ros-humble-nav-msgs`
- `ros-humble-geometry-msgs`
- `ros-humble-tf2-*`
- `ros-humble-robot-state-publisher`
- `ros-humble-rosbag2`

Packages not found as installed:

- `ros-humble-navigation2`
- `ros-humble-nav2-bringup`
- `ros-humble-slam-toolbox`
- `ros-humble-ros2-control`
- `ros-humble-ros2-controllers`
- `ros-humble-diff-drive-controller`
- `ros-humble-teleop-twist-keyboard`
- `ros-humble-rviz2`
- `ros-humble-xacro`
- `ros-humble-robot-localization`

Interpretation:

- The old Pi had a reasonable base ROS 2 installation.
- It probably had not yet reached the point of installing the full navigation/control stack on the robot image, at least not through apt.
- Any source-built packages would likely be in `/home/ubuntu`, which was not readable during this inspection.

## 4. Boot and hardware-related config

From `/Volumes/writable/boot/firmware/config.txt`:

```text
dtparam=i2c_arm=on
dtparam=spi=on
```

So I2C and SPI were enabled. That may have been for future sensors or general robotics experiments.

From `/Volumes/writable/boot/firmware/cmdline.txt`:

```text
console=ttyAMA0,115200
```

Implication:

- The primary UART had a serial console enabled.
- This matters only if trying to use Pi GPIO UART directly.
- For the current plan, Arduino and lidar should use USB serial adapters/devices, so this is not a blocker.
- If a future design uses Pi UART pins, disable the serial console first.

## 5. User/groups

From `/Volumes/writable/etc/passwd`:

```text
ubuntu:x:1000:1000:Ubuntu:/home/ubuntu:/bin/bash
```

From `/Volumes/writable/etc/group`, user `ubuntu` is in useful groups including:

```text
dialout
sudo
video
plugdev
netdev
```

`dialout` is important because it gives normal-user access to `/dev/ttyUSB*` and `/dev/ttyACM*` serial devices, which is useful for:

- Arduino Nano USB serial.
- USB-to-TTL lidar adapter.

This is worth reproducing in the new image.

## 6. Networking

The mounted image contains a netplan Wi-Fi configuration in:

```text
/Volumes/writable/etc/netplan/50-cloud-init.yaml
```

It includes an old Wi-Fi SSID and password. These are not copied into this repository. If reusing or publishing the SD card contents, scrub this file.

The hostname was simply:

```text
ubuntu
```

For the new robot image, prefer a stable project hostname such as:

```text
slamrobot
```

## 7. Services

No custom robot/ROS/lidar/motor `systemd` service files were found in accessible system service directories.

This suggests the old project probably had not reached a robust autostart setup.

## 8. User home access limitation

The most likely location for old workspaces is:

```text
/Volumes/writable/home/ubuntu
```

But the directory permissions are:

```text
drwxr-x--- 1000:1000 /Volumes/writable/home/ubuntu
```

The current macOS user could not read it. Therefore, this inspection could not check for:

- `~/ros2_ws`
- `~/dev_ws`
- old Arduino sketches
- `.bash_history`
- custom launch files
- old notes/scripts
- cloned repositories

If you want to recover any source code, copy the directory using elevated permissions into a local folder you own. Example, run manually on your Mac if appropriate:

```bash
mkdir -p old-sd-recovered
sudo rsync -a /Volumes/writable/home/ubuntu/ old-sd-recovered/home-ubuntu/
sudo chown -R "$USER" old-sd-recovered
```

Then future sessions can inspect `old-sd-recovered/home-ubuntu`.

Be careful not to commit private SSH keys, shell history, or Wi-Fi credentials.

## 9. Useful lessons for the new build

The old image mostly confirms the direction already chosen:

1. Ubuntu 22.04 + ROS 2 Humble was a sensible historical baseline.
2. For a fresh build, Ubuntu 24.04 + ROS 2 Jazzy is still preferred unless driver support pushes us back to Humble.
3. Add the robot user to `dialout` early.
4. Install more than `ros-base` this time: include `slam_toolbox`, Nav2, `ros2_control`/controllers, `xacro`, teleop tools, and diagnostics.
5. Keep project code in a version-controlled repo rather than only on the SD card.
6. Avoid storing Wi-Fi credentials in committed files.

## 10. Effect on current project plan

No major architecture change is needed from this SD card inspection.

The useful recoverable facts are:

- Old image was arm64 Ubuntu 22.04 / ROS 2 Humble.
- It likely did not contain a mature ROS robot stack in system locations.
- Serial access setup via `dialout` was already right.
- I2C/SPI were enabled, which may be useful again later.
- If there was custom code, it is probably under `/home/ubuntu` and needs a permission-aware recovery step.

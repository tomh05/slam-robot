# Raspberry Pi Setup Notes / Lessons Learned

Last updated: 2026-07-28.

These notes capture practical lessons from flashing and bootstrapping the Raspberry Pi 4 Model B, 2 GB, with Ubuntu Server 24.04 arm64 and ROS 2 Jazzy. They are intended to prevent repeating the same setup/debugging work later.

## Sensitive information policy

Do **not** commit any of the following to this repository:

- Wi-Fi passwords.
- Robot login passwords.
- Private SSH keys.
- Full shell histories containing credentials.

It is OK for operational docs to mention non-secret facts such as the robot hostname, current IP, usernames, package names, and command patterns.

## Flashing Ubuntu from macOS

The SD-card flashing helper is:

```bash
./scripts/flash_ubuntu_rpi_sd_macos.sh /dev/diskN
```

Important macOS/BSD `dd` lesson:

- Do **not** use `conv=sync` when piping `xzcat` into `dd` on macOS.
- With pipe input, `dd` can receive short reads and `conv=sync` pads them up to the full block size, corrupting/inflating the image.
- The symptom seen here was a 3.95 GiB Ubuntu image apparently writing until the full 15.5 GB card was exhausted, ending with:

```text
dd: /dev/rdiskN: Input/output error
```

That symptom by itself did **not** mean the SD card was damaged. Removing `conv=sync` fixed the flash. After a successful flash, macOS should mount the boot partition as:

```text
/Volumes/system-boot
```

The boot partition should contain files such as `network-config`, `user-data`, `meta-data`, `cmdline.txt`, `config.txt`, `vmlinuz`, and `initrd.img`.

## Headless first boot over Wi-Fi

For Ubuntu Raspberry Pi images, edit this boot-partition file before first boot:

```text
/Volumes/system-boot/network-config
```

Use cloud-init/netplan format. Multiple Wi-Fi networks can be listed under `access-points`; the Pi should connect to an available configured network. Listing the preferred network first is sensible, but strict priority between simultaneously visible networks is not guaranteed by this simple config.

Set the regulatory domain, e.g.:

```yaml
      regulatory-domain: GB
```

To allow SSH without enabling password SSH, put the laptop public key in `/Volumes/system-boot/user-data` using:

```yaml
ssh_authorized_keys:
- ssh-ed25519 ...
```

Keep:

```yaml
ssh_pwauth: false
```

The default Ubuntu first login is usually:

```text
username: ubuntu
password: ubuntu
```

Ubuntu expires this password and forces a change on first login. Do not store the new password in repo docs.

## Current robot identity from this setup

Current known facts after this setup:

```text
hostname: slamrobot
current IP on home network: 192.168.1.46
username: ubuntu
project path on robot: /home/ubuntu/slam-robot
ROS_DOMAIN_ID: 42
```

The SSH key-based login worked from the laptop. If `slamrobot.local` does not resolve before Avahi is installed/running, use the IP address.

## Syncing the repo to a 16 GB SD card

The repo contains large image files under `images/`. Do not sync those to the robot by default; space is limited. `scripts/sync_to_robot.sh` now excludes:

```text
images/
```

The helper environment currently targets the first-boot `ubuntu` user and IP:

```bash
export ROBOT_USER="ubuntu"
export ROBOT_HOST="192.168.1.46"
export ROBOT_PROJECT_DIR="/home/${ROBOT_USER}/slam-robot"
```

Update `scripts/robot_env.sh` if the robot gets a new IP or a dedicated `robot` user is created later.

## Running the minimal bootstrap safely

For a 16 GB SD card, use the minimal bootstrap, not the full one:

```bash
cd /home/ubuntu/slam-robot
sudo ./scripts/bootstrap_robot_ubuntu24_ros2_jazzy_minimal_16gb.sh
```

Better for long unattended runs: start it detached and log output so the laptop/agent can disconnect without killing the install:

```bash
cd /home/ubuntu/slam-robot
nohup sudo -n ./scripts/bootstrap_robot_ubuntu24_ros2_jazzy_minimal_16gb.sh > ~/bootstrap_minimal.log 2>&1 < /dev/null &
```

Monitor progress with:

```bash
ssh ubuntu@192.168.1.46 'pgrep -af "bootstrap_robot|apt-get|dpkg|rosdep" || true; tail -80 ~/bootstrap_minimal.log; df -h /'
```

The first install can take a long time on a Raspberry Pi 4 over Wi-Fi. It may appear slow while unpacking large packages such as Boost or firmware.

## If apt/SSH is interrupted during bootstrap

During one run, the remote harness timed out while apt was upgrading packages, and SSH temporarily returned `Connection refused`. The Pi still replied to ping. A power-cycle brought SSH back.

Recovery sequence used successfully:

```bash
sudo dpkg --configure -a
sudo apt-get -f install -y
sudo apt-get autoremove -y
```

Then rerun the bootstrap script. It is mostly idempotent and will continue from the package state.

Avoid intentionally power-cycling during apt/dpkg work unless SSH is already unusable and there is no better option.

## Post-bootstrap checks

After the bootstrap completed and the Pi rebooted, these checks passed:

```bash
hostname
uptime
df -h /
source /opt/ros/jazzy/setup.bash
ros2 --help
ros2 pkg list | grep -E '^(rclcpp|rclpy|slam_toolbox|teleop_twist_keyboard|robot_state_publisher)$'
groups
systemctl is-active ssh avahi-daemon chrony NetworkManager
```

Observed result:

```text
hostname: slamrobot
root filesystem: 14G size, 3.7G used, 9.5G available, 28% used
ROS 2 CLI: OK when /opt/ros/jazzy/setup.bash is sourced
services active: ssh, avahi-daemon, chrony, NetworkManager
ubuntu groups include: dialout, plugdev, video
```

`~/.bashrc` was updated by the bootstrap to include:

```bash
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=42
```

Directly running `/opt/ros/jazzy/bin/ros2` without sourcing the ROS setup file can fail with missing Python package metadata, e.g. `PackageNotFoundError: ros2cli`. Source `/opt/ros/jazzy/setup.bash` first, or use a normal interactive shell where `.bashrc` has loaded ROS.

## Package-size expectations

Even the minimal bootstrap pulls in a fairly large dependency set. Some graphical/visualisation libraries may appear as dependencies of packages such as `slam_toolbox`, `tf2-tools`, or related ROS tooling even though the script intentionally avoids installing the full desktop stack, Nav2, ros2_control, RViz desktop usage, and Gazebo.

After the successful minimal install, there was still enough headroom on the 16 GB card for early robot work, but continue to avoid large datasets, bag files, and desktop packages on the Pi.

# Current Status / Next Session Entry Point

Last updated: 2026-07-30.

## Immediate state

The SD card has been successfully flashed with Ubuntu Server 24.04.4 LTS arm64 preinstalled for Raspberry Pi and booted on the Raspberry Pi 4 Model B, 2 GB.

Current robot network/login facts for this session:

```text
IP: 192.168.1.46
hostname: slamrobot
username: ubuntu
```

Wi-Fi was configured on the boot partition for both `The LAN Before Time` and `Hackspace`, with the home network listed first. Do not commit Wi-Fi credentials or the robot password to the repo.

The user's SSH public key was injected via cloud-init and key-based SSH worked from the laptop. The user completed the forced first-login password change.

The project was synced to:

```text
/home/ubuntu/slam-robot
```

A remote run of the minimal bootstrap was first started with:

```bash
ssh ubuntu@192.168.1.46 'cd /home/ubuntu/slam-robot && sudo -n ./scripts/bootstrap_robot_ubuntu24_ros2_jazzy_minimal_16gb.sh'
```

The harness timed out after 1800 seconds while apt was still upgrading/installing packages. After the timeout, the Pi still replied to ping but SSH on port 22 returned `Connection refused`, probably because the interrupted apt/openssh upgrade left sshd stopped. The user power-cycled the Pi, SSH came back, and repair commands were run:

```bash
sudo dpkg --configure -a
sudo apt-get -f install -y
sudo apt-get autoremove -y
```

The bootstrap was then resumed detached on the Pi with `nohup`:

```bash
cd /home/ubuntu/slam-robot
nohup sudo -n ./scripts/bootstrap_robot_ubuntu24_ros2_jazzy_minimal_16gb.sh > ~/bootstrap_minimal.log 2>&1 < /dev/null &
```

The minimal bootstrap completed successfully. The Pi was rebooted afterwards and came back online at `192.168.1.46`.

Post-bootstrap and workflow checks passed:

```text
hostname: slamrobot
current IP: 192.168.1.46
mDNS SSH works as ubuntu@slamrobot.local; stale known_hosts entry on laptop was removed/replaced after reflash
root filesystem: 14G size, about 3.7G used, about 9.4G available, 28% used
ROS 2 CLI: OK when /opt/ros/jazzy/setup.bash is sourced
installed ROS packages include: rclcpp, rclpy, robot_state_publisher, slam_toolbox, teleop_twist_keyboard
services active: ssh, avahi-daemon, chrony, NetworkManager
ubuntu groups include: dialout, plugdev, video
~/.bashrc sources /opt/ros/jazzy/setup.bash and exports ROS_DOMAIN_ID=42 for interactive shells
```

Development loop smoke test completed:

```text
created ros2_ws/src/slam_robot_smoke_test
synced repo to /home/ubuntu/slam-robot
scripts/robot_env.sh now targets ubuntu@slamrobot.local
ran rosdep install --from-paths src --ignore-src -r -y
ran colcon build --symlink-install
ran ros2 run slam_robot_smoke_test smoke_publisher
verified /slam_robot/smoke with ros2 topic echo --once
```

For non-interactive SSH commands, source ROS explicitly, e.g. `source /opt/ros/jazzy/setup.bash`, because `.bashrc` only sets ROS variables for interactive shells.

Note: directly running `/opt/ros/jazzy/bin/ros2` without sourcing the ROS setup file fails with missing Python package metadata. This is expected; source `/opt/ros/jazzy/setup.bash` first or open a normal shell where `.bashrc` has sourced it.

Operational lessons from this setup have been consolidated in [`raspberry-pi-setup-notes.md`](raspberry-pi-setup-notes.md).

Hardware inventory has been partly populated in [`hardware-inventory-template.md`](hardware-inventory-template.md) with confirmed Pi setup plus measured chassis dimensions and provisional motor/power details from the user. The Arduino Nano clone has been connected to the Pi and identified as CH340 USB serial: `1a86:7523`, `/dev/ttyUSB0`, by-id path `/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0`.

Measured chassis geometry recorded on 2026-07-30:

```text
track contact length: 127 mm
wheel diameter including track: 58 mm => initial effective radius 29 mm
track width: 42 mm
inner gap between tracks: 113 mm
track centre-to-centre separation: 155 mm confirmed
outside track width: 197 mm derived from 113 + 2*42
overall robot footprint: 185 mm long x 204 mm wide
left track driven wheel: rear
right track driven wheel: front
centre platform underside height above ground: 43 mm
assumed centre platform: 170 mm long x 95 mm wide x 3 mm thick; not built yet
provisional lidar pose: centred, scan plane 100 mm above ground until actual mount is known
```

The ROS base config and URDF have been updated with the initial measured `track_width_m=0.155`, `wheel_radius_m=0.029`, track contact length `0.127`, track visual width/height, provisional platform dimensions, and provisional centred lidar height. Floor calibration is still required for actual ticks-per-metre and effective skid-steer yaw separation.

Arduino programming from the Pi is confirmed:

```text
arduino-cli 1.5.1 installed at /usr/local/bin/arduino-cli
Arduino AVR core installed
compile OK for firmware/arduino_nano_base_controller
upload OK using FQBN arduino:avr:nano:cpu=atmega328old
new/default Nano bootloader FQBN arduino:avr:nano failed with not-in-sync resp=0x66
serial test at 115200 baud showed BOOT message, E status lines, and OK stop response
```

Encoder pinout was updated to match the discovered existing-board mapping:

```text
Motor A / left:  S1 -> D4, S2 -> D2 / INT0
Motor B / right: S1 -> D7, S2 -> D3 / INT1
```

D2 and D3 are the classic Arduino Nano/ATmega328P external interrupt pins, so the firmware now counts `S2` rising edges and reads `S1` for direction. The updated firmware compiled and uploaded successfully from the Pi. `scripts/arduino_encoder_test.py` was added for safe zero-command/manual-spin encoder tests; a short smoke run showed serial status and raw pin reports.

Manual encoder tests then confirmed basic pinout correctness:

```text
right track moved: right count increased from 0 to about +133, left stayed 0
left track moved: left count changed while right stayed 0; count sign depended on movement direction
raw pin reports showed S1/S2 state changes
repeated one-output-wheel-rev forward tests: left -224 counts/rev, right +149/+150 counts/rev
backward one-output-wheel-rev tests: left +217/+218 counts/rev, right +149 then +86 counts/rev, still positive
```

This implies the left encoder direction is working, with provisional forward sign negative and about 224 counts/rev. The right encoder forward count is repeatable at about +150 counts/rev, but right backward tests also counted positive, so right-side direction decoding is not yet confirmed/fixed. It may be a test-direction/reference mistake, a disconnected/stuck right `S1` direction channel, a swapped channel, or an x1 edge-choice issue. **Decision taken on 2026-07-30:** because the right encoder hardware fault (only one of two signal wires produces pulses) is not trivial to repair, both encoders will be used as **single-channel (x1) tachometers for distance measurement only**. Direction is inferred from the motor's commanded direction in the firmware. This means:
- Encoder ISRs count every S2 rising edge as +1, with no hardware direction read.
- The firmware negates the tick delta when the previous PWM command was negative.
- Distance integration is correct under normal operation but slip or unexpected reversal cannot be detected from encoders alone.
- `docs/encoder-bringup-test-plan.md` has been updated to reflect the new approach.
- The right encoder live channel is on D7 (`S1`), not D3 (`S2`) as wired in firmware. Either swap the wires at the Arduino or change the firmware pin mapping to count D7.
- Provisional counts/rev: left ≈ 224, right ≈ 150. The ROS base node now supports separate left/right ticks-per-rev and ticks-per-meter parameters, with provisional config values `left_ticks_per_rev=224`, `right_ticks_per_rev=150`, `left_encoder_sign=-1`, `right_encoder_sign=1`; these signs now apply to the firmware-reported signed counts (which are already direction-corrected by the firmware). The helper script was updated to keep sending periodic `V 0 0` commands during tests, so measured `tps` should be more useful on subsequent runs instead of staying at zero after the Arduino command timeout. It now also prints final counts on exit.

For D7/right-`S1` debugging without a logic analyser, the firmware now reports raw encoder pin transition counters in response to `R`, and `scripts/arduino_d7_watch.py` was added. It specifically watches `RS1/D7` and reports whether its edge count increases. The updated firmware was compiled and uploaded from the Pi. During upload, a stale `python3 scripts/arduino_encoder_test.py` process was holding `/dev/ttyUSB0`; it was killed and the upload then succeeded.

D7/right-`S1` test result: when the right track was spun, `RS1/D7` changed level and `RS1_edges` rose to hundreds of transitions, so D7 is definitely receiving a signal. In that same output, `RS2/D3` stayed at `1` and `RS2` transition count stayed `0`, so the next suspicion is the D3/right-`S2` channel or the assumed S1/S2 mapping. Re-running `scripts/arduino_encoder_test.py` with the updated firmware and right track movement showed `RS1/D7` edges increasing to about 403, `RS2/D3` edges remaining 0, and normal right count `R` staying 0. Conclusion: current firmware/wiring receives right encoder pulses on D7, but not on D3; since firmware currently counts D3, right encoder count no longer moves. A manual D3-to-GND jumper test then made `RS2/D3` edges increase to hundreds and drove right count strongly negative, proving the Arduino D3 input and firmware interrupt path work. The right encoder signal wires were then swapped at the Arduino: the known-live signal moved onto D3 and the other signal moved onto D7. Result: `RS2/D3` edges increased to >1000 and normal right count moved again (`R=577` over the user’s spin), while `RS1/D7` stayed at 0 edges. Conclusion: Arduino pins D3 and D7 both work when fed with the live right encoder channel, but only one of the two right encoder signal wires/channels appears to be producing pulses. The other right encoder channel, currently on D7 after the swap, looks dead/disconnected/stuck.

**Decision (2026-07-30):** rather than continue debugging the dead right encoder channel, the approach is now single-channel tachometer with direction from the motor command. The firmware has been updated accordingly. The right encoder live wire should be on the interrupt pin (D3) for normal counting; if it is currently on D7, swap the wires or change the firmware to count on D7.

```bash
cd /home/ubuntu/slam-robot
arduino-cli compile --fqbn arduino:avr:nano:cpu=atmega328old firmware/arduino_nano_base_controller
arduino-cli upload -p /dev/serial/by-id/usb-1a86_USB_Serial-if00-port0 --fqbn arduino:avr:nano:cpu=atmega328old firmware/arduino_nano_base_controller
```

Key remaining hardware decisions are tracked in [`open-questions.md`](open-questions.md), especially final LiPo/regulator/fuse/E-stop architecture and encoder characterisation.

Additional ROS progress made while hardware was idle:

```text
ros2_ws/src/slam_robot_base
  - Python ROS 2 node arduino_base_node
  - subscribes /cmd_vel
  - talks to Arduino over /dev/serial/by-id/usb-1a86_USB_Serial-if00-port0
  - parses E status lines
  - publishes /arduino_base_node/status_raw
  - publishes /odom and odom -> base_link TF
  - safety default motors_enabled=false, so /cmd_vel is ignored until explicitly enabled

ros2_ws/src/slam_robot_description
  - URDF/Xacro with base_footprint, base_link, left_track_link, right_track_link, lidar_link
  - uses measured track geometry plus provisional platform/lidar assumptions
  - robot_state_publisher launch tested; /tf_static publishes expected fixed frames

ros2_ws/src/slam_robot_bringup
  - robot_core.launch.py starts robot_state_publisher + arduino_base_node
  - tested in safe mode with motors_enabled=false
```

Tested commands:

```bash
cd /home/ubuntu/slam-robot/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch slam_robot_bringup robot_core.launch.py
ros2 topic echo /arduino_base_node/status_raw --once
ros2 topic echo /odom --once
```

End-of-session state:

```text
All ROS packages build on the Pi.
No stale arduino_base_node, robot_state_publisher, or smoke_publisher processes were left running.
No process was holding /dev/ttyUSB0.
Root filesystem after adding Arduino CLI/ROS packages: about 14G total, 4.5G used, 8.6G free, 35% used.
A short handoff was also written outside the repo at /tmp/slam-robot-handoff-2026-07-28.md.
```

Important cleanup note: some earlier manual launch tests left child `robot_state_publisher`/`arduino_base_node` processes alive when the parent launch process was killed. Check/clean before uploading Arduino firmware or rerunning launch:

```bash
pgrep -af 'arduino_base_node|robot_state_publisher|smoke_publisher'
# kill specific stale PIDs if any are listed
fuser -v /dev/ttyUSB0
```

Earlier flashing note: the flash script had an early-exit checksum bug and a later macOS/BSD `dd conv=sync` pipe-padding bug; both were fixed. The `conv=sync` bug could make a 3.95 GiB image appear to write until the full 15.5 GB card was exhausted, ending with `dd: /dev/rdiskN: Input/output error` and leaving an unmountable FAT partition. That symptom alone did not imply the SD card was damaged.

## After flashing completes

1. Eject/remove SD card if the script did not already eject it.
2. Insert SD card into Raspberry Pi 4 Model B, 2 GB.
3. Prefer Ethernet for first boot if possible.
4. Ubuntu Raspberry Pi Server images usually use initial login:

```text
username: ubuntu
password: ubuntu
```

Then force a password change.

5. Set hostname:

```bash
sudo hostnamectl set-hostname slamrobot
sudo reboot
```

6. Get the project repo onto the Pi. Options:

```bash
# From laptop, if SSH works and scripts/robot_env.sh is configured
./scripts/sync_to_robot.sh
```

or clone/copy manually.

7. On the Pi, for the 16 GB SD card, run the minimal bootstrap, not the full one:

```bash
cd ~/slam-robot
sudo ./scripts/bootstrap_robot_ubuntu24_ros2_jazzy_minimal_16gb.sh
sudo reboot
```

8. Test ROS:

```bash
source /opt/ros/jazzy/setup.bash
ros2 run demo_nodes_cpp talker
# another terminal
ros2 run demo_nodes_py listener
```

9. Check free space:

```bash
df -h /
```

## Key project decisions so far

Do not rediscover these; details are in the linked docs.

- OS target: Ubuntu Server 24.04 arm64 + ROS 2 Jazzy.
- Because the SD card is 16 GB, start with `ros-jazzy-ros-base` plus minimal robot tools; avoid Nav2/RViz/Gazebo on the Pi initially.
- Main compute: Raspberry Pi 4 Model B, 2 GB RAM.
- Motor control architecture: Raspberry Pi ROS 2 over USB serial to Arduino Nano clone, Arduino controls HW-354/MX1508 and reads hall encoders.
- Motor driver: HW-354 / MX1508, VCC treated as 2-10 V. Do **not** connect 12 V directly.
- Arduino: Nano clone, CH340C, mini USB, likely 5 V logic.
- Motor output/control pins are decided: Arduino D5/D6/D9/D10 for HW-354 `INA`/`INB`/`INC`/`IND` respectively.
- Motor connector order: `M+`, `M-`, `GND`, `VCC`, `S1`, `S2`.
- Lidar: likely MB_1R2T or compatible 5 V serial lidar. Preferred path is to port community MB_1R2T parser to ROS 2. Official YDLIDAR ROS 2 driver exists but is secondary for this module.
- Spare adapter: MAX3232 RS232-TTL level converter. It is not a USB-to-TTL adapter by itself; do not connect RS232 side to lidar TTL or Pi GPIO.

## Most important docs

Start by reading:

- `PROJECT_OVERVIEW.md`
- `docs/current-status.md` — this file
- `docs/raspberry-pi-setup-notes.md`
- `docs/requirements.md`
- `docs/architecture.md`
- `docs/implementation-plan.md`
- `docs/development-workflow.md`
- `docs/electrical-wiring-and-power-plan.md`
- `docs/power-research-and-recommendation.md`
- `docs/mains-bench-power-notes.md`
- `docs/motor-control-arduino-nano-plan.md`
- `docs/lidar-mb-1r2t-ros2-port.md`
- `docs/old-sd-card-inspection.md`

## Important scripts/firmware

- `scripts/flash_ubuntu_rpi_sd_macos.sh` — destructive macOS SD flashing helper.
- `scripts/bootstrap_robot_ubuntu24_ros2_jazzy_minimal_16gb.sh` — recommended first bootstrap for this 16 GB card.
- `scripts/bootstrap_robot_ubuntu24_ros2_jazzy.sh` — fuller bootstrap for larger card/later use.
- `scripts/sync_to_robot.sh` and `scripts/robot_env.sh` — deployment helpers.
- `scripts/lidar_capture_serial.py` — serial baud/protocol capture helper for lidar.
- `firmware/arduino_nano_base_controller/arduino_nano_base_controller.ino` — initial Arduino Nano base-controller firmware skeleton.

## Suggested next development order

After the Pi boots and has minimal ROS installed:

1. Confirm SSH/networking and `ROS_DOMAIN_ID` setup.
2. Upload/test Arduino firmware over USB from laptop or Pi.
3. Bench-test HW-354 + one motor with current-limited 6-9 V, tracks lifted.
4. Verify encoder counts from Arduino serial.
5. Create Pi-side ROS 2 base node for `/cmd_vel` -> Arduino serial -> `/odom`.
6. Capture lidar serial data at `158700` and `153600` baud.
7. Implement/port MB_1R2T ROS 2 lidar node publishing `/scan`.
8. Bring up TF/URDF and `slam_toolbox` mapping.

## Sensitive information note

The old mounted SD card had Wi-Fi credentials in `/Volumes/writable/etc/netplan/50-cloud-init.yaml`. They were not copied into project docs. Avoid committing Wi-Fi credentials, SSH keys, or old shell histories.

# Open Questions and Decisions

This file tracks information that is still needed before implementation details can be finalised.

## Highest priority hardware questions

1. **Choose final battery/regulator/power-safety architecture.**
   - Pi setup is now confirmed: Raspberry Pi 4 Model B Rev 1.5, 2 GB class RAM, 16 GB microSD, Ubuntu Server 24.04.4 arm64, ROS 2 Jazzy.
   - Current Pi-only power is a nonofficial USB-C mains adapter that is adequate for setup.
   - Final robot power is undecided; likely LiPo, but nominal voltage/capacity must be chosen.
   - HW-354/MX1508 motor supply must be treated as 9 V max for initial tests; do not connect a 12 V battery directly to the motor driver.
   - Need advice/decision on LiPo cell count, capacity, motor supply path, 5 V regulator/BEC for Pi/lidar, fusing, switch, and emergency stop.

2. **Confirm lidar electrical details and exact baud.**
   - Old notes strongly suggest MB_1R2T or compatible.
   - Community code exists, but baud differs between examples: `158700` vs `153600`.
   - Need raw serial capture and voltage-level measurement.
   - See [`lidar-module-notes.md`](lidar-module-notes.md) and [`lidar-mb-1r2t-ros2-port.md`](lidar-mb-1r2t-ros2-port.md).

3. **What current and thermal limits does the HW-354/MX1508 board have in practice?**
   - Pinout/chip are now identified: MX1508 with `INA`, `INB`, `INC`, `IND`.
   - Voltage should be treated as 2-10 V, so do not use 12 V directly.
   - Need to confirm whether it can handle the tracked chassis motor current under load.

4. ~~What type and voltage are the encoders/hall sensors?~~ **RESOLVED**
   - Encoders are 5 V hall sensors powered from the Arduino Nano.
   - Pinout confirmed: `M+ M- GND VCC S1 S2`; left S1→D4, S2→D2/INT0; right S1→D7, S2→D3/INT1.
   - **Hardware fault:** both encoders only produce pulses on S1; S2 (D2/D3) is dead on both motors.
   - **Decision:** use both encoders as single-channel (x1) tachometers for distance only;
     direction is inferred from the motor's commanded direction (target velocity sign) in
     the firmware. The firmware counts on S1: D4 (left) and D7 (right), both via PCINT2
     pin-change interrupts. Signed positions are reported in the E line.
     See `docs/encoder-bringup-test-plan.md` and `docs/current-status.md`.
   - Provisional calibration: left ≈ 224 counts/rev, right ≈ 150 counts/rev.

## Software decisions

### D1: ROS 2 distribution

Recommended decision: **ROS 2 Jazzy on Ubuntu Server 24.04 arm64**.

Use Humble/22.04 only if a critical driver is not available on Jazzy.

### D2: Lidar driver

Decision: treat this as an MB_1R2T ROS 2 port task first.

Plan:

- Capture raw data at `158700` and `153600` baud.
- Port the community MB_1R2T parser to ROS 2 and publish `sensor_msgs/LaserScan`.
- Optionally test `YDLIDAR/ydlidar_ros2_driver`, likely its `humble` branch for Jazzy/Humble-era ROS 2, but this is secondary.

Do not use `lidar-resources/ydlidar_ros_driver-master` or `Vidicon/mb_1r2t_ros` directly because both are ROS 1/catkin.

### D3: Motor control architecture

Decision: use the Arduino Nano as the low-level motor/encoder controller first, connected to the Pi over USB serial.

Initial ROS 2 integration should be a simple custom base node. Later it can be refactored into a `ros2_control` hardware interface if desired.

See [`motor-control-arduino-nano-plan.md`](motor-control-arduino-nano-plan.md).

### D4: Visualisation strategy from laptop

If laptop is Ubuntu: use RViz 2 directly.

If laptop is macOS: likely easiest options are:

- VS Code Remote SSH + RViz in Ubuntu VM, or
- Foxglove Studio with a bridge running on the robot.

### D5: Networking strategy

Start with normal Wi-Fi client mode on the same network.

If discovery is unreliable, decide between:

- Cyclone DDS explicit peer config.
- Robot-hosted Wi-Fi access point.
- Dedicated travel router.
- Foxglove bridge for visualisation instead of relying on DDS discovery to laptop.

## Future feature decisions

1. Add IMU?
   - Recommendation: yes eventually, because tracks slip.

2. Add camera?
   - Useful for video inspection or later visual features, but not required for first 2D lidar SLAM.

3. Fully autonomous exploration?
   - Defer until manual SLAM and Nav2 goal navigation are reliable.

4. Physical emergency stop?
   - Strongly recommended before unattended autonomous driving.

## Information to provide in a future session

Please collect as much as possible:

- Photos of the robot chassis, motors, encoders, HW-354 motor driver, future battery/regulator, lidar labels, Arduino Nano, USB-to-TTL adapter, and RS232-TTL adapter.
- Output of Pi commands:

```bash
cat /proc/device-tree/model && echo
uname -a
lsusb
ls -l /dev/serial/by-id/
```

- Motor driver datasheet or product link, especially current/thermal limits.
- Lidar raw serial captures at 158700 and 153600 baud if possible.
- Encoder specs or product link, or measured logic analyser captures.
- Remaining physical measurements/calibration: robot mass with battery/electronics, actual lidar pose after mounting, and floor-test calibrated ticks-per-metre/effective skid-steer track separation. Basic chassis geometry is now measured in `hardware-inventory-template.md`; URDF currently assumes centred lidar at 0.10 m above ground and an unbuilt 170 x 95 x 3 mm centre platform.
- Battery/power constraints and desired runtime.
- How the motor driver is currently wired, if already wired.

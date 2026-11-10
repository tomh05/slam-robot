# BM160 IMU Wiring Session Notes

**Date:** 2025-10-15  
**Location:** /Users/tom/workspace/slam-robot  
**Author:** Session notes from PI wiring instructions

## Module Info
- **Sensor:** BM160 6-axis gyro + accelerometer
- **Module labeling:** "IIC I2C SPI" (breakout board)
- **Interface used:** I2C (recommended for ROS 2 integration)
- **Chip family:** BMI160 (common for BM160 labeled breakouts)
- **Default I2C addresses:** `0x68` (ADDR tied to GND) or `0x69` (ADDR tied to 3.3V). Actual address depends on ADDR/SA0 jumper/state.

## Wiring (Raspberry Pi 40-pin Header)
Wired to Raspberry Pi as follows (I2C1):

| Pi Physical Pin | Pi Function | BM160 Pin | Notes |
|---|---|---|---|
| 1 | 3.3V | VCC/3V3 | Powered from Pi 3.3V rail. **Do not use 5V.** |
| 3 | GPIO2 (SDA1) | SDA | I2C Data |
| 5 | GPIO3 (SCL1) | SCL | I2C Clock |
| 6 | GND | GND | Common ground |

**Unconnected (I2C mode):** CS, SDO/MISO, SCK/SCL (SPI), SDI/MOSI, INT (optional).

## Verification
Run the following on the Pi to confirm detection:

```bash
sudo apt install -y i2c-tools
sudo i2cdetect -y 1
```

- Expected result: device appears at `0x68` or `0x69`.
- If nothing appears: recheck power, SDA/SCL, common ground, and ADDR pin state. Try bus `0` only on very old Pi revisions (Pi 4 uses bus 1).

**Detected:** `0x69` on `/dev/i2c-1` (2026 user session). Pi also has `/dev/i2c-20`, `/dev/i2c-21` (not used for this header device). User `ubuntu` was not in `i2c` group initially; add with `sudo usermod -aG i2c ubuntu` and re-login for non-root access.

## Integration Plan (for future reference)
- **Attachment point:** Raspberry Pi (I2C). Not on Arduino (to avoid extending the motor control serial protocol).
- **ROS 2 usage:** Publish as `sensor_msgs/Imu` on e.g. `/imu/data` with proper `imu_link` frame.
- **Fusion:** Combine with wheel odometry via `robot_localization` EKF into `/odometry/filtered` (do **not** replace wheel odometry). Wheel odom is especially prone to slip on tracked drive; IMU helps with heading/yaw drift.
- **Mounting:** Rigidly mount to chassis, aligned with robot base frame, away from excessive motor vibration if possible.

## Session Notes / TODO
- [x] Record actual detected I2C address from `i2cdetect`: `0x69`
- [ ] Record exact breakout board name/silkscreen if different from assumed (fill in: `____`)
- [ ] Confirm ADDR pin state (GND/VCC/unconnected) (fill in: `____`)
- [x] Add TF transform `base_link` -> `imu_link` (provisional) in `ros2_ws/src/slam_robot_description/urdf/slam_robot.urdf.xacro`; measure/align `imu_*` args to physical mount
- [x] Add in-repo BMI160/BM160 IMU publisher: `ros2_ws/src/slam_robot_base/slam_robot_base/bm160_imu_node.py` (console script `bm160_imu_node`, publishes `/imu/data`, default `i2c_address=0x69`). No `ros-jazzy-*bmi160*` apt package found.
- [x] Add `robot_localization` EKF config: `ros2_ws/src/slam_robot_bringup/config/ekf.yaml` (fuses `/odom` + `/imu/data` -> `/odometry/filtered`).
- [x] Resolve TF ownership for EKF path: `arduino_base.launch.py` accepts `publish_tf` (default `true` for non-EKF compatibility); `slam_robot_bringup/launch/robot_core_ekf.launch.py` passes `publish_tf:=false` so only EKF publishes `odom -> base_link`.
- [x] Wire into bringup: `ros2_ws/src/slam_robot_bringup/launch/robot_core_ekf.launch.py` (description + base + `bm160_imu_node` + `ekf_filter_node`).
- [ ] On Pi: `sudo usermod -aG i2c ubuntu` (if needed), `sudo apt install -y ros-jazzy-robot-localization`, rebuild affected packages, verify `/imu/data` and `/odometry/filtered`.
- [ ] Measure/set physical `imu_*` x/y/z/roll/pitch/yaw in `slam_robot_description/urdf/slam_robot.urdf.xacro`.
- [ ] Calibrate IMU (gyro bias: `gyro_bias_x/y/z` params) and tune covariances/EKF after bringup.

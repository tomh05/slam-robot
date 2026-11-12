# slam_robot_base

ROS 2 base interface for the tracked SLAM robot's Arduino Nano motor/encoder controller.

## Safety default

The node defaults to:

```yaml
motors_enabled: false
```

In this mode it opens the Arduino serial port and publishes status/odometry, but ignores `/cmd_vel` and periodically sends a safe zero command. Set `motors_enabled:=true` only when the tracks are lifted or the robot is otherwise safe to move.

## Arduino protocol

Pi to Arduino:

```text
V <left_ticks_per_sec> <right_ticks_per_sec>
S
?
Z                 # zero encoder counts, bench-test helper
R                 # report raw encoder pin levels, bench-test helper
B                 # poll battery/supply voltage status
P <kp> <ki> <kd>
```

Arduino to Pi:

```text
BOOT arduino_nano_base_controller
E <millis> <left_position> <right_position> <left_tps> <right_tps> <left_pwm> <right_pwm>
R <millis> <left_s1> <left_s2> <right_s1> <right_s2> <left_s1_edges> <left_s2_edges> <right_s1_edges> <right_s2_edges>
B <millis> <source> <adc_raw> <v_supply_mV>   # source: 0=unknown, 1=battery, 2=dc_external
OK stop
OK zero
ERR ...
```

The firmware intentionally does not acknowledge every `V` velocity command to avoid serial chatter at control-loop rate. Battery status is polled by the ROS node (default every 5 s) rather than streamed continuously.

## Build

```bash
cd ~/slam-robot/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-select slam_robot_base
source install/setup.bash
```

## Run status-only/safe mode

```bash
ros2 launch slam_robot_base arduino_base.launch.py
```

Useful checks:

```bash
ros2 topic echo /arduino_base_node/status_raw --once
ros2 topic echo /odom --once
ros2 topic echo /arduino_base_node/battery_state --once
```

## Battery / supply voltage sensing

The Arduino samples `A0` through a 2:1 resistor divider (two 12kΩ resistors) on the sensed supply rail. The same divider sees ~9 V on DC adapter input and ~7.4–8.4 V on the 2S Li-ion battery, so the pin voltage stays in the ~3.7–4.5 V range (must remain below 5 V). The firmware assumes a 5 V ADC reference and reports supply voltage in millivolts.

`arduino_base_node` periodically sends `B` and publishes `sensor_msgs/msg/BatteryState` on `~/battery_state`:

- **DC/external supply:** `power_supply_status=NOT_CHARGING`, `present=true`
- **Battery:** `power_supply_status=DISCHARGING`, `power_supply_technology=LION`, `present=true`, approximate `percentage` derived from `battery_empty_voltage`/`battery_full_voltage` when configured

Key parameters (see `config/arduino_base.yaml`):

- `battery_poll_period_s` — polling interval in seconds (`<= 0` disables)
- `battery_frame_id`, `battery_location`
- `battery_voltage_scale` — ROS-side calibration multiplier applied to measured voltage
- `battery_source_dc_min_v` — voltage threshold for classifying external/DC supply
- `battery_voltage_min_v`, `battery_voltage_max_v` — plausible battery voltage bounds
- `battery_full_voltage`, `battery_empty_voltage` — rough percentage mapping bounds (2S Li-ion defaults)

## BM160 IMU calibration

`bm160_imu_node` publishes raw BMI160/BM160 data on `/imu/data`. Before the EKF
fuses it, two still-only calibrations must be done:

1. **Gyro bias** — while the robot sits still and level, the gyro should read 0.
2. **Accel zero-g offset** — while still and level, one axis should read ~+9.81 m/s^2.

Helper script: `scripts/calibrate_imu.py` (run on the robot with ROS sourced):

```bash
cd ~/slam-robot
source /opt/ros/jazzy/setup.bash && source ros2_ws/install/setup.bash
# 1. Start the IMU+EKF stack (motors off is fine):
ros2 launch slam_robot_bringup robot_core_ekf.launch.py
# 2. In another terminal, keep the robot STILL and LEVEL for ~60 s:
python3 scripts/calibrate_imu.py --duration 60
```

It prints the mean gyro and mean accel. Then pass the values to the launch
file (or set them as node params):

```bash
ros2 launch slam_robot_bringup robot_core_ekf.launch.py \
  imu_gyro_bias_x:=-0.0123 \
  imu_gyro_bias_y:=0.0045 \
  imu_gyro_bias_z:=-0.0021 \
  imu_accel_offset_x:=0.05 \
  imu_accel_offset_y:=-0.12 \
  imu_accel_offset_z:=9.70
```

`gyro_bias_*` is subtracted from the gyro in rad/s; `accel_offset_*` is
subtracted from the accel in m/s^2. After calibration, verify the orientation
sign: command a slow left/CCW turn and confirm `angular_velocity.z > 0`. If not,
flip `imu_yaw` in `slam_robot_description/urdf/slam_robot.urdf.xacro`.

## Enable motors only when safe

```bash
ros2 launch slam_robot_base arduino_base.launch.py motors_enabled:=true
```

Then publish very small `/cmd_vel` commands only with the tracks lifted for initial tests.

## Important provisional parameters

These need calibration before using odometry seriously:

- `track_width_m`
- `wheel_radius_m`
- `left_ticks_per_rev` / `right_ticks_per_rev`, or `left_ticks_per_meter` / `right_ticks_per_meter`
- `left_encoder_sign` / `right_encoder_sign` — fine-calibration signs applied to the firmware's already-direction-corrected signed positions. Default `1.0` for both; set to `-1.0` only if a specific motor is wired/mounted opposite to the standard convention.
- `left_command_sign`
- `right_command_sign`

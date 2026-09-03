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
P <kp> <ki> <kd>
```

Arduino to Pi:

```text
BOOT arduino_nano_base_controller
E <millis> <left_count> <right_count> <left_tps> <right_tps> <left_pwm> <right_pwm>
R <millis> <left_s1> <left_s2> <right_s1> <right_s2>
OK stop
OK zero
ERR ...
```

The firmware intentionally does not acknowledge every `V` velocity command to avoid serial chatter at control-loop rate.

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
```

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
- `left_encoder_sign` / `right_encoder_sign` — provisional manual test values are `-1.0` left and `1.0` right
- `left_command_sign`
- `right_command_sign`

# MB_1R2T Lidar ROS 2 Driver Plan

## 1. Updated identification

The lidar in the old notes appears to be the **MB_1R2T** low-cost serial lidar module, or a very close clone.

Evidence:

- The AliExpress description matches the previous seller text.
- The note explicitly says to search for `MB_1R2T_LIDAR_Demo`.
- The connector pinout in the note matches the saved screenshot.
- Existing community code targets this exact family:
  - <https://github.com/stdlogicvector/MB_1R2T_LIDAR_Demo>
  - <https://github.com/Vidicon/mb_1r2t_ros>
  - <https://github.com/Vidicon/Radar_MB_1R2T>
  - 3D model: <https://github.com/simonllopez/radar_mb_1r2t-3D-model>

## 2. Relationship to YDLIDAR drivers

Yes, there is an official YDLIDAR ROS 2 driver:

- <https://github.com/YDLIDAR/ydlidar_ros2_driver>

However, for this specific module it is probably **not the first driver to rely on**.

Reasons:

1. The module is described as a factory/test product with unknown format, not a named supported YDLIDAR model.
2. The community MB_1R2T driver indicates a non-standard baud rate and direct streaming behaviour.
3. Vendor YDLIDAR SDKs often expect command/response behaviour and model-specific startup/configuration.
4. The existing MB_1R2T protocol is already reverse engineered enough to write a ROS 2 node directly.

Recommended approach:

1. Use the MB_1R2T parser/protocol as the primary path.
2. Keep `ydlidar_ros2_driver` as a secondary experiment only if direct MB_1R2T parsing fails or if raw captures match a supported YDLIDAR model.

## 3. Known serial settings

From notebook and community demo:

- Connector: 8P JST-PH / 2.0 mm pitch.
- Pins from left to right according to the note:

```text
5V, Serial out, 158700 baud, x, GND, 0-5V rotation speed control, x, x, x
```

The exact wording is awkward because the baud rate is not a pin. Interpreted as:

```text
Pin 1: 5 V
Pin 2: serial output
Pin 3 or gap: unknown / not used depending on connector orientation
Pin 4/5: GND, based on screenshot/note
Pin 6: 0-5 V rotation speed control
Remaining pins: unknown / not used
```

Important: before powering, confirm connector orientation physically against the screenshot.

Baud rates found in code/notes:

- `158700` in `stdlogicvector/MB_1R2T_LIDAR_Demo`
- `153600` in `Vidicon/mb_1r2t_ros`

Start raw capture with both. The Python demo's `158700` is probably the more specific lead. Some serial adapters may tolerate nearby rates; others may not.

## 4. Known packet format

The community ROS 1 driver and Python demo use this packet structure:

```text
sync0       1 byte   0xAA
sync1       1 byte   0x55
header      8 bytes
sample data N * 3 bytes
```

Header bytes after `AA 55`:

```text
byte 0: package_type
byte 1: package_size / sample count
byte 2: start_angle low
byte 3: start_angle high
byte 4: stop_angle low
byte 5: stop_angle high
byte 6: checksum/crc? ignored by community code
byte 7: checksum/crc? ignored by community code
```

Community code treats:

```cpp
package.type = raw_bytes[2];
package.data_length = raw_bytes[3];
package.start_angle = raw_bytes[5] << 8 | raw_bytes[4];
package.stop_angle = raw_bytes[7] << 8 | raw_bytes[6];
```

Each sample is 3 bytes:

```text
byte 0: intensity
byte 1: distance low
byte 2: distance high
```

Distance conversion from the ROS 1 driver:

```cpp
uint16_t distance = (distanceH << 8) + distanceL;
float distance_m = distance / 4000.0;
```

Angle conversion:

```cpp
angle_raw_range = 0xB400; // 46080 decimal
angle_rad = raw_angle / 0xB400 * 2*pi
```

A scan boundary is detected when angle wraps from high to low.

## 5. Existing community implementations

### Python visual demo

Repository:

- <https://github.com/stdlogicvector/MB_1R2T_LIDAR_Demo>

Key details:

- Uses `pyserial`.
- Uses `baudrate=158700`.
- Looks for sync bytes `AA 55`.
- Parses 3-byte samples.
- Draws point cloud with pygame.

### ROS 1 driver

Repository:

- <https://github.com/Vidicon/mb_1r2t_ros>

Key details:

- ROS 1 Noetic / catkin.
- C++.
- Publishes:
  - `sensor_msgs/LaserScan` on `scan`
  - `sensor_msgs/PointCloud2` on `cloud`
- Uses Boost.Asio serial.
- Hardcoded `BAUDRATE 153600`.
- Uses Linux custom baud ioctl because standard Boost serial option may not support arbitrary baud rates.

This is the best starting point for a ROS 2 port.

## 6. ROS 2 port design

Create package:

```text
ros2_ws/src/slam_robot_lidar_mb1r2t/
```

Recommended implementation language: **Python first**, C++ later only if needed.

Why Python first:

- `pyserial` supports arbitrary baud rates more easily than Boost.Asio.
- The parser is simple.
- Performance should be enough for this low-cost lidar on a Raspberry Pi 4.
- Faster to debug and modify.

ROS 2 package dependencies:

- `rclpy`
- `sensor_msgs`
- `diagnostic_updater`, optional later
- Python dependency: `pyserial`

Node name:

```text
mb1r2t_lidar_node
```

Parameters:

```yaml
port: /dev/ttyUSB0
baudrate: 158700
frame_id: lidar_link
range_min: 0.11
range_max: 8.0
angle_min: 0.0
angle_max: 6.283185307179586
publish_point_cloud: false
scan_topic: scan
inverted: true
```

Published topics:

- `/scan` — `sensor_msgs/msg/LaserScan`
- `/cloud` — optional `sensor_msgs/msg/PointCloud2`
- diagnostics later

Initial implementation strategy:

1. Read bytes from serial in a background thread or timer loop.
2. Synchronise on `AA 55`.
3. Read 8-byte header.
4. Read `package_size * 3` sample bytes.
5. Ignore packets where `package_type & 0x01` is true.
6. Interpolate angles between start and stop angle.
7. Accumulate vectors until angle wrap.
8. Convert one full revolution into a `LaserScan`.
9. Publish with `header.stamp = now()` and `header.frame_id = frame_id`.

## 7. LaserScan construction choices

The ROS 1 driver simply publishes ranges in sample order and sets:

```cpp
angle_increment = 2*pi / vectors.size();
time_increment = 0.2 / vectors.size();
scan_time = 0.2;
```

For ROS 2, a slightly better first version:

- Sort or bin samples into fixed angular bins, e.g. 720 bins or 360 bins.
- Use `float('inf')` for missing ranges.
- Use nearest valid sample per bin or minimum range per bin.
- Publish stable metadata:

```text
angle_min = 0.0
angle_max = 2*pi
angle_increment = 2*pi / bins
scan_time = measured time between wrap events
time_increment = scan_time / bins
range_min = 0.11
range_max = 8.0
```

For SLAM, stable angle bins are usually better than variable-length scans.

## 8. Testing plan

### Raw capture first

Use:

```bash
python3 scripts/lidar_capture_serial.py --port /dev/ttyUSB0 --baud 158700 --seconds 5 --out captures/mb1r2t_158700.bin
python3 scripts/lidar_capture_serial.py --port /dev/ttyUSB0 --baud 153600 --seconds 5 --out captures/mb1r2t_153600.bin
```

Expected:

- Continuous data.
- Many `AA 55` headers.
- Reasonable `package_size` values.

### Standalone parser test

Before ROS 2, run a parser on saved `.bin` files and print:

- packet count
- scan count
- samples per scan
- min/max distance
- min/max angle
- approximate scan rate

### ROS 2 test

Once package exists:

```bash
ros2 run slam_robot_lidar_mb1r2t mb1r2t_lidar_node --ros-args -p port:=/dev/ttyUSB0 -p baudrate:=158700
ros2 topic hz /scan
ros2 topic echo /scan --once
```

Visualise in RViz 2:

- Fixed frame: `lidar_link` initially
- Add LaserScan display on `/scan`

## 9. Decision

The project should now consider the lidar path **mostly de-risked** compared with the earlier unknown-state plan, because a protocol and ROS 1 implementation exist.

New preferred path:

1. Port `Vidicon/mb_1r2t_ros` / `stdlogicvector/MB_1R2T_LIDAR_Demo` logic to ROS 2.
2. Publish standard `/scan`.
3. Use this with `slam_toolbox`.

Fallback path:

- Try `ydlidar_ros2_driver` with custom baud/model settings.
- Replace lidar if hardware is dead or data quality is too poor.

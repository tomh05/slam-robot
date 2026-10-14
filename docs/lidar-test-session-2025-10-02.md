# LiDAR Test Session - 2025-10-02

## Summary
Successfully identified and captured data from the factory test LiDAR module. It speaks standard **YDLIDAR protocol** at **153600 baud** (S4B model parameters).

## Hardware Setup
- **LiDAR**: Factory test module (MB_1R2T-like), STM32F302C8T6, 5V, 8-pin 2.0mm pitch
- **Connection**: LiDAR 5V/GND → external 5V supply (or Pi pins 2/6), LiDAR TX → CH340 RX, **common ground required**
- **Serial port**: `/dev/ttyUSB0` (CH340 USB-UART)
- **Note**: CH340 disappears if LiDAR powered from it — must use separate 5V supply

## Key Findings

### Baud Rate Scan Results
| Baud | AA55 Count | Notes |
|------|------------|-------|
| 153600 | **337** | ✓ Correct - standard YDLIDAR S4B rate |
| 158700 | 337 | Close but non-standard |
| 230400 | 0 | Garbled (only 55 unique bytes) |
| Others | 0 | No headers |

### Protocol Confirmation
- **1112 packets** captured in 10s at 153600 baud
- Packet structure: `AA 55` (PH) + CT + LSN + FSA + LSA + CS + samples...
- Idle padding: `01 D8 FE`
- Angle encoding: `(value >> 1) / 64.0` degrees
- Distance: raw units (need to verify scaling, likely mm/4)

### Model Match: S4B (per YDLIDAR dataset)
| Parameter | Value |
|-----------|-------|
| baudrate | 153600 |
| lidar_type | 1 (TYPE_TRIANGLE) |
| sample_rate | 4 |
| intensity | true (8-bit) |
| isSingleChannel | false |
| frequency | 5-12 Hz |
| range | 0.12-16m |

## ROS 2 Driver Status
- **ydlidar_ros2_driver** built successfully (after installing YDLidar-SDK to `/usr/local`)
- **Startup fails**: Driver sends `A5 00` (stop) then `A5 65` (start) commands, waits for ACK
- **Root cause**: LiDAR auto-streams on power-up, **TX not connected** → no ACK → timeout
- **Error**: "Failed to start the lidar" after startup sequence

## Next Steps

### Option A: Connect TX (Recommended for vendor driver)
- Wire CH340 TX → LiDAR RX (with 5V→3.3V divider if needed)
- Vendor driver should then work with S4B params

### Option B: Custom ROS 2 Node (RX-only, faster)
Write minimal node that:
1. Opens `/dev/ttyUSB0` at 153600 8N1
2. Parses `AA 55` packets from stream
3. Publishes `sensor_msgs/LaserScan` on `/scan`
4. No TX needed — works with current wiring

### Option C: Patch Vendor Driver
Modify `ydlidar_ros2_driver` to skip startup sequence for `device_type:=0` or add S4B-specific init.

## Files Created
- `/home/ubuntu/slam-robot/ros2_ws/src/ydlidar_ros2_driver` (cloned humble branch)
- `/home/ubuntu/slam-robot/ros2_ws/src/YDLidar-SDK` (built & installed to `/usr/local`)
- `/home/ubuntu/s4b_params.yaml` (S4B parameter file)
- `/Users/tom/workspace/slam-robot/lidar_153600.bin` (raw capture, 131KB, 1112 packets)

## Commands to Resume
```bash
# On robot:
ssh ubuntu@slamrobot.local
cd ~/slam-robot/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash

# Test capture again:
./scripts/lidar_capture_serial.py --port /dev/ttyUSB0 --baud 153600 --seconds 5

# Run vendor driver (after connecting TX):
ros2 run ydlidar_ros2_driver ydlidar_ros2_driver_node --ros-args \
  -p port:=/dev/ttyUSB0 -p baudrate:=153600 -p lidar_type:=1 \
  -p intensity:=true -p intensity_bit:=8 -p sample_rate:=4
```

## Reference
- Protocol details: `lidar-resources/ydlidar_ros_driver-master/details.md`
- S4B params from: `lidar-resources/YDLidar-SDK-master/doc/Dataset.md`
- Capture script: `scripts/lidar_capture_serial.py`
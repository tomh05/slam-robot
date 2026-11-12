"""Publish BMI160/BM160 IMU data as sensor_msgs/Imu over I2C.

This is a minimal in-repo bringup driver (Option C) for a BM160-labeled
BMI160-family breakout on the Raspberry Pi I2C bus. It publishes raw gyro and
accelerometer data; orientation is not estimated (orientation_covariance[0] = -1)
so robot_localization can fuse angular velocity / acceleration as configured.

Hardware notes (from docs/imu-bm160-session-notes.md):
- Default/observed I2C address for this robot: 0x69 on /dev/i2c-1.
- Use 3.3V. For I2C mode, CS must usually be high on BMI160 breakouts.
"""

from __future__ import annotations

import math
import struct
import time
from typing import Optional

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu

try:
    import smbus
except ImportError:  # pragma: no cover - runtime dependency on Pi
    smbus = None


# BMI160 register map (subset)
REG_CHIP_ID = 0x00
REG_ERR = 0x02
REG_PMU_STATUS = 0x03
REG_DATA = 0x0C  # GYR_X_L .. ACC_Z_H, 12 bytes little-endian
REG_ACC_CONF = 0x40
REG_ACC_RANGE = 0x41
REG_GYR_CONF = 0x42
REG_GYR_RANGE = 0x43
REG_CMD = 0x7E

CHIP_ID_BMI160 = 0xD1
CMD_ACC_NORMAL = 0x11
CMD_GYR_NORMAL = 0x15
CMD_SOFT_RESET = 0xB6

GRAVITY = 9.80665

# accel range reg -> (scale LSB/g, nominal g)
ACC_RANGES = {
    2: (0x03, 16384.0),
    4: (0x05, 8192.0),
    8: (0x08, 4096.0),
    16: (0x0C, 2048.0),
}
# gyro range reg -> (scale LSB/(deg/s), nominal dps)
GYR_RANGES = {
    125: (0x04, 262.4),
    250: (0x03, 131.2),
    500: (0x02, 65.6),
    1000: (0x01, 32.8),
    2000: (0x00, 16.4),
}


class Bm160ImuNode(Node):
    def __init__(self) -> None:
        super().__init__('bm160_imu_node')

        self.declare_parameter('i2c_bus', 1)
        self.declare_parameter('i2c_address', 0x69)
        self.declare_parameter('frame_id', 'imu_link')
        self.declare_parameter('topic', '/imu/data')
        self.declare_parameter('rate_hz', 100.0)
        self.declare_parameter('accel_range_g', 2)
        self.declare_parameter('gyro_range_dps', 250)
        # BMI160 acc_odr/gyr_odr=100Hz (0x08), normal/OSR2-like filter (0x20) => 0x28.
        self.declare_parameter('acc_conf', 0x28)
        self.declare_parameter('gyr_conf', 0x28)
        self.declare_parameter('publish_acceleration', True)
        self.declare_parameter('gyro_bias_x', 0.0)
        self.declare_parameter('gyro_bias_y', 0.0)
        self.declare_parameter('gyro_bias_z', 0.0)
        # Zero-g (still) accelerometer offset in m/s^2, subtracted after scaling.
        # Calibrate with scripts/calibrate_imu.py: set to the mean accel read while
        # the robot sits still and level (the level axis should read ~+9.81).
        self.declare_parameter('accel_offset_x', 0.0)
        self.declare_parameter('accel_offset_y', 0.0)
        self.declare_parameter('accel_offset_z', 0.0)
        # Conservative defaults; calibrate/tune for your mounting and vibration.
        self.declare_parameter('angular_velocity_covariance', 0.02)
        self.declare_parameter('linear_acceleration_covariance', 0.04)

        self.bus_num = int(self.get_parameter('i2c_bus').value)
        self.address = int(self.get_parameter('i2c_address').value)
        self.frame_id = str(self.get_parameter('frame_id').value)
        topic = str(self.get_parameter('topic').value)
        rate_hz = float(self.get_parameter('rate_hz').value)
        accel_range_g = int(self.get_parameter('accel_range_g').value)
        gyro_range_dps = int(self.get_parameter('gyro_range_dps').value)
        self.acc_conf = int(self.get_parameter('acc_conf').value)
        self.gyr_conf = int(self.get_parameter('gyr_conf').value)
        self.publish_acceleration = bool(self.get_parameter('publish_acceleration').value)
        self.gyro_bias = (
            float(self.get_parameter('gyro_bias_x').value),
            float(self.get_parameter('gyro_bias_y').value),
            float(self.get_parameter('gyro_bias_z').value),
        )
        self.accel_offset = (
            float(self.get_parameter('accel_offset_x').value),
            float(self.get_parameter('accel_offset_y').value),
            float(self.get_parameter('accel_offset_z').value),
        )
        ang_cov = float(self.get_parameter('angular_velocity_covariance').value)
        acc_cov = float(self.get_parameter('linear_acceleration_covariance').value)

        if rate_hz <= 0.0:
            raise ValueError('rate_hz must be positive')
        if accel_range_g not in ACC_RANGES:
            raise ValueError(f'accel_range_g must be one of {sorted(ACC_RANGES)}')
        if gyro_range_dps not in GYR_RANGES:
            raise ValueError(f'gyro_range_dps must be one of {sorted(GYR_RANGES)}')

        self.acc_range_reg, self.acc_lsb_per_g = ACC_RANGES[accel_range_g]
        self.gyr_range_reg, self.gyr_lsb_per_dps = GYR_RANGES[gyro_range_dps]
        self.acc_scale = GRAVITY / self.acc_lsb_per_g
        self.gyr_scale = math.radians(1.0) / self.gyr_lsb_per_dps

        self.angular_velocity_covariance = [0.0] * 9
        self.angular_velocity_covariance[0] = ang_cov
        self.angular_velocity_covariance[4] = ang_cov
        self.angular_velocity_covariance[8] = ang_cov
        self.linear_acceleration_covariance = [0.0] * 9
        self.linear_acceleration_covariance[0] = acc_cov
        self.linear_acceleration_covariance[4] = acc_cov
        self.linear_acceleration_covariance[8] = acc_cov

        self.publisher = self.create_publisher(Imu, topic, 10)
        self.bus = self._open_bus()
        self._init_device()

        self.timer = self.create_timer(1.0 / rate_hz, self._publish_sample)
        self.get_logger().info(
            f'BM160 IMU publishing on {topic} ({self.frame_id}) at {rate_hz:.1f} Hz, '
            f'addr=0x{self.address:02x}, bus={self.bus_num}, '
            f'acc=±{accel_range_g}g, gyr=±{gyro_range_dps}dps'
        )

    def _open_bus(self):
        if smbus is None:
            raise RuntimeError(
                'python3-smbus is not available. Install with: sudo apt install -y python3-smbus'
            )
        try:
            return smbus.SMBus(self.bus_num)
        except FileNotFoundError as exc:
            raise RuntimeError(f'I2C bus /dev/i2c-{self.bus_num} not found: {exc}') from exc
        except PermissionError as exc:
            raise RuntimeError(
                f'No permission for /dev/i2c-{self.bus_num}. '
                'Run as root, or add user to i2c group and re-login: '
                'sudo usermod -aG i2c $USER'
            ) from exc

    def _write_u8(self, reg: int, value: int) -> None:
        self.bus.write_byte_data(self.address, reg, value & 0xFF)

    def _read_u8(self, reg: int) -> int:
        return self.bus.read_byte_data(self.address, reg)

    def _read_block(self, reg: int, length: int):
        return self.bus.read_i2c_block_data(self.address, reg, length)

    def _init_device(self) -> None:
        try:
            chip_id = self._read_u8(REG_CHIP_ID)
        except OSError as exc:
            raise RuntimeError(
                f'Failed to read BMI160 chip ID at I2C 0x{self.address:02x} on bus {self.bus_num}: {exc}. '
                'Check wiring, address (SA0/ADDR), 3.3V power, and that CS is high for I2C mode.'
            ) from exc

        if chip_id != CHIP_ID_BMI160:
            self.get_logger().warn(
                f'Unexpected chip ID 0x{chip_id:02x} (expected 0x{CHIP_ID_BMI160:02x} for BMI160). '
                'Continuing, but verify the module is a BMI160/BM160.'
            )
        else:
            self.get_logger().info(f'BMI160 chip ID OK (0x{chip_id:02x})')

        # Soft reset for a known state.
        self._write_u8(REG_CMD, CMD_SOFT_RESET)
        time.sleep(0.01)

        # Power up accelerometer, then gyroscope.
        self._write_u8(REG_CMD, CMD_ACC_NORMAL)
        time.sleep(0.005)
        self._write_u8(REG_CMD, CMD_GYR_NORMAL)
        time.sleep(0.08)

        self._write_u8(REG_ACC_CONF, self.acc_conf)
        self._write_u8(REG_ACC_RANGE, self.acc_range_reg)
        self._write_u8(REG_GYR_CONF, self.gyr_conf)
        self._write_u8(REG_GYR_RANGE, self.gyr_range_reg)
        time.sleep(0.01)

        try:
            pmu = self._read_u8(REG_PMU_STATUS)
            err = self._read_u8(REG_ERR)
            self.get_logger().info(f'BMI160 PMU_STATUS=0x{pmu:02x} ERR_REG=0x{err:02x}')
        except OSError:
            pass

    def _read_sample(self) -> Optional[tuple[tuple[float, float, float], tuple[float, float, float]]]:
        try:
            data = self._read_block(REG_DATA, 12)
        except OSError as exc:
            self.get_logger().warn(f'I2C read failed: {exc}', throttle_duration_sec=2.0)
            return None
        if len(data) != 12:
            return None

        gyr_x, gyr_y, gyr_z, acc_x, acc_y, acc_z = struct.unpack('<hhhhhh', bytes(data))
        gyro = (
            gyr_x * self.gyr_scale - self.gyro_bias[0],
            gyr_y * self.gyr_scale - self.gyro_bias[1],
            gyr_z * self.gyr_scale - self.gyro_bias[2],
        )
        accel = (
            acc_x * self.acc_scale - self.accel_offset[0],
            acc_y * self.acc_scale - self.accel_offset[1],
            acc_z * self.acc_scale - self.accel_offset[2],
        )
        return gyro, accel

    def _publish_sample(self) -> None:
        sample = self._read_sample()
        if sample is None:
            return
        gyro, accel = sample

        msg = Imu()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.frame_id

        # No orientation estimate from this raw driver.
        msg.orientation_covariance[0] = -1.0

        msg.angular_velocity.x = gyro[0]
        msg.angular_velocity.y = gyro[1]
        msg.angular_velocity.z = gyro[2]
        msg.angular_velocity_covariance = list(self.angular_velocity_covariance)

        if self.publish_acceleration:
            msg.linear_acceleration.x = accel[0]
            msg.linear_acceleration.y = accel[1]
            msg.linear_acceleration.z = accel[2]
        msg.linear_acceleration_covariance = list(self.linear_acceleration_covariance)

        self.publisher.publish(msg)


def main(args=None) -> None:
    rclpy.init(args=args)
    node: Optional[Bm160ImuNode] = None
    try:
        node = Bm160ImuNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            try:
                node.bus.close()
            except Exception:
                pass
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()

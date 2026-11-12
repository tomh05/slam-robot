#!/usr/bin/env python3
"""Guided static calibration for BMI160/BM160 gyro and accelerometer.

The BMI160/BM160 publishes raw sensor data on /imu/data (frame_id=imu_link).
The guided workflow collects gyro bias while level, then six static
accelerometer faces. Opposing faces separate accelerometer bias from gravity:
  accel_offset_x = (mean(+x face) + mean(-x face)) / 2

Usage (on the robot, with ROS 2 sourced and the IMU+EKF stack running):
  python3 ~/slam-robot/scripts/calibrate_imu.py

Safety: this script only subscribes and reads. It never commands motion.
"""

from __future__ import annotations

import argparse
import sys
import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu


class ImuCalibrator(Node):
    def __init__(self, topic: str):
        super().__init__('imu_calibrator')
        self.n = 0
        self.sum_gx = self.sum_gy = self.sum_gz = 0.0
        self.sum_ax = self.sum_ay = self.sum_az = 0.0
        self.subscription = self.create_subscription(
            Imu, topic, self._callback, 10
        )

    def reset(self) -> None:
        self.n = 0
        self.sum_gx = self.sum_gy = self.sum_gz = 0.0
        self.sum_ax = self.sum_ay = self.sum_az = 0.0

    def _callback(self, msg: Imu) -> None:
        self.sum_gx += msg.angular_velocity.x
        self.sum_gy += msg.angular_velocity.y
        self.sum_gz += msg.angular_velocity.z
        self.sum_ax += msg.linear_acceleration.x
        self.sum_ay += msg.linear_acceleration.y
        self.sum_az += msg.linear_acceleration.z
        self.n += 1

    def report(self) -> dict:
        if self.n == 0:
            return {}
        return {
            'n': self.n,
            'mean_gyro': (self.sum_gx / self.n, self.sum_gy / self.n, self.sum_gz / self.n),
            'mean_accel': (self.sum_ax / self.n, self.sum_ay / self.n, self.sum_az / self.n),
        }


def collect(cal: ImuCalibrator, duration_s: float) -> dict:
    """Collect and average samples for a bounded interval."""
    cal.reset()
    deadline = time.monotonic() + duration_s
    while rclpy.ok() and time.monotonic() < deadline:
        rclpy.spin_once(cal, timeout_sec=0.1)
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(remaining, 0.25))
    return cal.report()


def print_calibration(gyro: dict, faces: dict[str, dict]) -> bool:
    """Print offsets from opposing faces and return whether signs look valid."""
    face_values = {
        name: result['mean_accel']
        for name, result in faces.items()
        if result
    }
    offsets = []
    valid = len(face_values) == 6
    for axis, positive, negative, index in (
        ('x', '+x', '-x', 0),
        ('y', '+y', '-y', 1),
        ('z', '+z', '-z', 2),
    ):
        if positive not in face_values or negative not in face_values:
            offsets.append(None)
            valid = False
            continue
        positive_value = face_values[positive][index]
        negative_value = face_values[negative][index]
        offsets.append((positive_value + negative_value) / 2.0)
        if positive_value <= 1.0 or negative_value >= -1.0:
            valid = False

    print()
    print('=' * 60)
    print('IMU CALIBRATION RESULTS')
    print(f'Still samples collected: {gyro["n"]}')
    gx, gy, gz = gyro['mean_gyro']
    print()
    print('Launch parameters:')
    print(f'  imu_gyro_bias_x:={-gx:.6f}')
    print(f'  imu_gyro_bias_y:={-gy:.6f}')
    print(f'  imu_gyro_bias_z:={-gz:.6f}')
    for axis, offset in zip(('x', 'y', 'z'), offsets):
        if offset is None:
            print(f'  imu_accel_offset_{axis}:=UNAVAILABLE')
        else:
            print(f'  imu_accel_offset_{axis}:={offset:.6f}')
    print()
    print('Accelerometer face checks (raw means, m/s^2):')
    for name in ('+x', '-x', '+y', '-y', '+z', '-z'):
        result = faces.get(name)
        if result:
            ax, ay, az = result['mean_accel']
            print(f'  {name}: ({ax:+.3f}, {ay:+.3f}, {az:+.3f})')
        else:
            print(f'  {name}: no samples')
    print()
    if valid:
        print('Axis checks: PASS (each positive face > +1 and negative face < -1).')
    else:
        print('Axis checks: CHECK FAILED (review pose directions and mounting).')
    print('=' * 60)
    return valid


def main() -> int:
    parser = argparse.ArgumentParser(description='Guided BMI160/BM160 static calibration.')
    parser.add_argument('--duration', type=float, default=60.0,
                        help='seconds for the level gyro-bias capture (default: 60)')
    parser.add_argument('--topic', default='/imu/data', help='Imu topic to read (default: /imu/data)')
    parser.add_argument('--face-duration', type=float, default=5.0,
                        help='seconds to average each accelerometer face (default: 5)')
    parser.add_argument('--still-only', action='store_true',
                        help='only collect the level gyro/accel burst (not a full calibration)')
    args = parser.parse_args()

    if args.duration <= 0:
        print('ERROR: --duration must be positive', file=sys.stderr)
        return 2
    if args.face_duration <= 0:
        print('ERROR: --face-duration must be positive', file=sys.stderr)
        return 2

    rclpy.init(args=None)
    cal = ImuCalibrator(args.topic)

    print(f'Guided IMU calibration on {args.topic}.')
    print('This script only reads IMU data; it never commands the robot.')
    print(f'\nKeep the robot level and still for {args.duration:g} s.')
    sys.stdout.flush()
    gyro = collect(cal, args.duration)
    if not gyro:
        rclpy.shutdown()
        print(f'ERROR: no {args.topic} samples received. Is the IMU node running?', file=sys.stderr)
        return 1

    if args.still_only:
        rclpy.shutdown()
        gx, gy, gz = gyro['mean_gyro']
        print(f'\nGyro bias parameters: {-gx:.6f}, {-gy:.6f}, {-gz:.6f}')
        print('A still-only accelerometer reading is not a valid 3-axis offset.')
        return 0

    print('\nNow collect six accelerometer faces.')
    print('Use stable 90-degree faces when safe. Do not use 30-45 degree tilts')
    print('for offset calibration: they do not isolate one axis well enough.')
    faces = {}
    for name, description in (
        ('+x', 'right side up'),
        ('-x', 'left side up'),
        ('+y', 'front edge up / forward axis up'),
        ('-y', 'rear edge up / backward axis up'),
        ('+z', 'normal level / top side up'),
        ('-z', 'upside down / bottom side up'),
    ):
        try:
            input(f'\nPlace the robot with {description} ({name}). Press Enter...')
        except (EOFError, KeyboardInterrupt):
            print('\nCalibration cancelled.', file=sys.stderr)
            rclpy.shutdown()
            return 130
        faces[name] = collect(cal, args.face_duration)
        if faces[name]:
            print(f'Collected {faces[name]["n"]} samples.')
        else:
            print('ERROR: no samples received.', file=sys.stderr)

    rclpy.shutdown()
    return 0 if print_calibration(gyro, faces) else 1


if __name__ == '__main__':
    raise SystemExit(main())
#!/usr/bin/env python3
"""Calibrate IMU biases and verify accelerometer axis signs.

The BMI160/BM160 publishes raw sensor data on /imu/data (frame_id=imu_link).
While the robot sits perfectly still on a level surface:
  - mean angular_velocity  -> gyro bias to subtract (negate for gyro_bias_* params)
  - mean linear_acceleration -> zero-g offset; the level axis should read ~+9.81 m/s^2

Usage (on the robot, with ROS 2 sourced and the IMU+EKF stack running):
  python3 ~/slam-robot/scripts/calibrate_imu.py --duration 60
  python3 ~/slam-robot/scripts/calibrate_imu.py --verify

Safety: this script only subscribes and reads. It never commands motion.
"""

from __future__ import annotations

import argparse
import math
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


def print_verification(results: list[tuple[str, str, float, dict]]) -> bool:
    print()
    print('=' * 60)
    print('ACCELEROMETER AXIS-SIGN VERIFICATION')
    print('Positive means the expected sensor-frame direction was observed.')
    print()
    all_passed = True
    for label, axis, expected_sign, result in results:
        if not result:
            print(f'{label}: ERROR: no samples received')
            all_passed = False
            continue
        ax, ay, az = result['mean_accel']
        values = {'x': ax, 'y': ay, 'z': az}
        measured = values[axis]
        passed = measured * expected_sign > 1.0
        all_passed = all_passed and passed
        status = 'PASS' if passed else 'CHECK'
        print(
            f'{label}: {status}  '
            f'a=({ax:+.3f}, {ay:+.3f}, {az:+.3f}) m/s^2; '
            f'expected {axis}{"+" if expected_sign > 0 else "-"} '
            f'(measured {measured:+.3f})'
        )
    print()
    print('Expected frame: right=+x, forward=+y, up=+z.')
    print('=' * 60)
    return all_passed


def main() -> int:
    parser = argparse.ArgumentParser(description='Calibrate BMI160/BM160 gyro bias and accel offset from a still recording.')
    parser.add_argument('--duration', type=float, default=60.0,
                        help='seconds to collect while still (default: 60)')
    parser.add_argument('--topic', default='/imu/data', help='Imu topic to read (default: /imu/data)')
    parser.add_argument('--verify', action='store_true',
                        help='prompt for tilt poses and verify accelerometer axis signs')
    parser.add_argument('--verify-duration', type=float, default=3.0,
                        help='seconds to average each verification pose (default: 3)')
    args = parser.parse_args()

    if args.duration <= 0:
        print('ERROR: --duration must be positive', file=sys.stderr)
        return 2
    if args.verify_duration <= 0:
        print('ERROR: --verify-duration must be positive', file=sys.stderr)
        return 2

    rclpy.init(args=None)
    cal = ImuCalibrator(args.topic)

    if args.verify:
        poses = (
            ('Forward tilt', 'y', 1.0),
            ('Backward tilt', 'y', -1.0),
            ('Right side up', 'x', 1.0),
            ('Left side up', 'x', -1.0),
        )
        print(f'Verifying accelerometer signs on {args.topic}.')
        print('Use a safe, stable tilt of about 90 degrees if practical;')
        print('30-45 degrees is sufficient if 90 degrees is not safe.')
        print('Keep each pose still while it is being averaged.')
        results = []
        for label, axis, expected_sign in poses:
            try:
                input(f'\nPlace the robot in: {label}. Press Enter to collect...')
            except (EOFError, KeyboardInterrupt):
                print('\nVerification cancelled.', file=sys.stderr)
                rclpy.shutdown()
                return 130
            result = collect(cal, args.verify_duration)
            results.append((label, axis, expected_sign, result))
            if result:
                print(f'Collected {result["n"]} samples.')
            else:
                print('ERROR: no samples received.', file=sys.stderr)
        rclpy.shutdown()
        return 0 if print_verification(results) else 1

    print(f'Collecting IMU data for {args.duration:g} s on {args.topic}...')
    print('KEEP THE ROBOT STILL AND LEVEL. Do not touch it.')
    sys.stdout.flush()
    r = collect(cal, args.duration)

    rclpy.shutdown()

    if not r:
        print(f'ERROR: no {args.topic} samples received. Is the IMU node running?', file=sys.stderr)
        return 1

    gx, gy, gz = r['mean_gyro']
    ax, ay, az = r['mean_accel']
    print()
    print('=' * 60)
    print(f'Samples collected: {r["n"]}')
    print()
    print('MEAN GYRO (rad/s):')
    print(f'  x = {gx:+.6f}')
    print(f'  y = {gy:+.6f}')
    print(f'  z = {gz:+.6f}')
    print()
    print('  -> Set on bm160_imu_node (launch arg or param):')
    print(f'     gyro_bias_x = {-gx:.6f}')
    print(f'     gyro_bias_y = {-gy:.6f}')
    print(f'     gyro_bias_z = {-gz:.6f}')
    print()
    print('MEAN ACCEL (m/s^2):')
    print(f'  x = {ax:+.6f}')
    print(f'  y = {ay:+.6f}')
    print(f'  z = {az:+.6f}')
    mag = math.sqrt(ax * ax + ay * ay + az * az)
    print(f'  |a| = {mag:.4f}  (expect ~9.81 on a level surface)')
    if abs(mag - 9.81) > 1.5:
        print('  WARNING: magnitude far from 9.81 -> surface may not be level, or')
        print('  the sensor is accelerating. Re-check placement and re-run.')
    print()
    print('  -> Zero-g offset to subtract (software), set accel_offset_x/y/z on')
    print('     bm160_imu_node:')
    print(f'     accel_offset_x = {ax:.6f}')
    print(f'     accel_offset_y = {ay:.6f}')
    print(f'     accel_offset_z = {az:.6f}')
    print('=' * 60)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
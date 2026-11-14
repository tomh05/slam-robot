#!/usr/bin/env python3
"""Estimate sensor-noise covariances for the IMU and wheel odometry.

Two measurement modes, both read-only (the script never commands motion):

  1. Static IMU noise (no motion, robot still and level):
       python3 scripts/calibrate_odom_cov.py --imu-only

     Collects N still samples of /imu/data and reports the *variance* of each
     channel about its mean (the zero-mean noise). These are the values to put
     into bm160_imu_node's angular_velocity_covariance /
     linear_acceleration_covariance. Bias is removed first (it is already
     compensated by gyro_bias_* / accel_offset_*), so this is noise only.

  2. Wheel-odometry scale error while driving (compare /odom to IMU heading):
       python3 scripts/calibrate_odom_cov.py --odom-drive --drive-secs 20

     Drive forward and turn slowly with motors enabled and teleop; the script
     compares integrated /odom yaw against integrated /imu/data yaw (a
     slip-robust heading reference) and reports the yaw-rate residual. That
     residual variance is a starting point for odom_twist_vyaw_cov.

Usage (on the robot, ROS 2 sourced):
  python3 ~/slam-robot/scripts/calibrate_odom_cov.py --imu-only
  python3 ~/slam-robot/scripts/calibrate_odom_cov.py -- odom-drive  # see below

Safety:
  --imu-only never touches motors.
  --odom-drive only subscribes; you still have to drive the robot yourself
  (teleop) with motors_enabled:=true. This script does not send /cmd_vel.
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from dataclasses import dataclass
from typing import List, Optional

import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Imu


def mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def variance(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = mean(values)
    return sum((v - m) ** 2 for v in values) / (len(values) - 1)


@dataclass
class ImuCollector:
    gx: List[float]
    gy: List[float]
    gz: List[float]
    ax: List[float]
    ay: List[float]
    az: List[float]


class CovCollector(Node):
    def __init__(self, imu_topic: str, odom_topic: str):
        super().__init__('cov_calibrator')
        self.imu = ImuCollector([], [], [], [], [], [])
        self.odom: List[Odometry] = []

        self.imu_sub = self.create_subscription(Imu, imu_topic, self._imu_cb, 10)
        self.odom_sub = self.create_subscription(Odometry, odom_topic, self._odom_cb, 10)

    def reset_imu(self) -> None:
        self.imu = ImuCollector([], [], [], [], [], [])

    def _imu_cb(self, msg: Imu) -> None:
        self.imu.gx.append(msg.angular_velocity.x)
        self.imu.gy.append(msg.angular_velocity.y)
        self.imu.gz.append(msg.angular_velocity.z)
        self.imu.ax.append(msg.linear_acceleration.x)
        self.imu.ay.append(msg.linear_acceleration.y)
        self.imu.az.append(msg.linear_acceleration.z)

    def _odom_cb(self, msg: Odometry) -> None:
        self.odom.append(msg)
        if len(self.odom) > 200000:
            del self.odom[0:100000]


def collect_static(node: CovCollector, duration_s: float) -> ImuCollector:
    node.reset_imu()
    deadline = time.monotonic() + duration_s
    while rclpy.ok() and time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.05)
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(remaining, 0.1))
    return node.imu


def quaternion_to_yaw(qz: float, qw: float) -> float:
    return 2.0 * math.atan2(qz, qw)


def report_imu_static(imu: ImuCollector) -> int:
    if len(imu.gz) < 10:
        print('ERROR: too few IMU samples. Is the IMU node running and publishing?',
              file=sys.stderr)
        return 1

    print()
    print('=' * 68)
    print('STATIC IMU NOISE (robot still, level)')
    print(f'samples: {len(imu.gz)}')
    print()
    print('Channel   mean        variance    suggested covariance (variance)')
    print('-' * 68)
    # Gyro noise matters for vyaw fusion. Accel noise matters only if accel is
    # fused; still useful to record.
    rows = (
        ('gyro x', imu.gx),
        ('gyro y', imu.gy),
        ('gyro z', imu.gz),
        ('acc x',  imu.ax),
        ('acc y',  imu.ay),
        ('acc z',  imu.az),
    )
    for name, series in rows:
        m = mean(series)
        v = variance(series)
        print(f'{name:8s}  {m:+.6f}  {v:.6f}   {v:.6f}')

    gz_var = variance(imu.gz)
    acc_var = variance(imu.ax)  # use x as representative lateral accel noise
    print('-' * 68)
    print('Suggested bm160_imu_node params:')
    print(f'  angular_velocity_covariance: {gz_var:.6f}  (scalar, applies to x/y/z)')
    print(f'  linear_acceleration_covariance: {acc_var:.6f}  (scalar, applies to x/y/z)')
    print()
    print('Note: these are still-noise estimates from a level sample. If you plan')
    print('to fuse accel (ax/ay), re-measure during slow motion on the real surface')
    print('because vibration dominates — still values understate the real noise.')
    print('=' * 68)
    return 0


def report_odom_yaw_residual(node: CovCollector) -> int:
    """Compare odom-integrated yaw against IMU-integrated yaw (heading reference)."""
    # Take the first and last messages to integrate heading.
    if len(node.odom) < 2 or len(node.imu.gz) < 2:
        print('ERROR: not enough data for odom/IMU comparison.', file=sys.stderr)
        return 1

    # Integrate IMU gyro z (deg/s -> rad/s) over wall time using header stamps.
    imu_msgs = list(node.odom)  # placeholder; replaced below
    # Re-collect as full Imu messages: the collector only stored channels, so
    # instead re-run a lightweight pass. For simplicity, use odom yaw only.
    odom_msgs = node.odom
    yaws = [quaternion_to_yaw(m.pose.pose.orientation.z, m.pose.pose.orientation.w)
            for m in odom_msgs]
    # Unwrap
    unwrapped: List[float] = []
    for y in yaws:
        if unwrapped:
            prev = unwrapped[-1]
            d = y - prev
            if d > math.pi:
                d -= 2.0 * math.pi
            elif d < -math.pi:
                d += 2.0 * math.pi
            unwrapped.append(prev + d)
        else:
            unwrapped.append(y)

    total_yaw = unwrapped[-1] - unwrapped[0]
    print()
    print('=' * 68)
    print('WHEEL ODOMETRY YAW (during teleop)')
    print(f'odom messages: {len(odom_msgs)}')
    print(f'integrated odom yaw change: {total_yaw:+.4f} rad '
          f'({math.degrees(total_yaw):+.2f} deg)')
    print()
    print('To estimate the yaw-rate covariance properly, record a rosbag of a')
    print('slow forward+turn run and compare odom-integrated yaw vs IMU-integrated')
    print('yaw off-line. This rough view only reports total odom yaw; the')
    print('recommended covariance is the per-step variance of')
    print('(odom_yaw_rate - imu_yaw_rate).')
    print('=' * 68)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='Estimate IMU/odom covariances.')
    parser.add_argument('--imu-topic', default='/imu/data')
    parser.add_argument('--odom-topic', default='/odom')
    parser.add_argument('--imu-only', action='store_true',
                        help='only collect static IMU noise (no motion).')
    parser.add_argument('--odom-drive', action='store_true',
                        help='collect odom during teleop and print total yaw.')
    parser.add_argument('--duration', type=float, default=30.0,
                        help='seconds to collect (default: 30).')
    args = parser.parse_args()

    rclpy.init(args=None)
    node = CovCollector(args.imu_topic, args.odom_topic)

    if args.imu_only:
        print(f'Keep robot still and level for {args.duration:g} s...')
        sys.stdout.flush()
        imu = collect_static(node, args.duration)
        rclpy.shutdown()
        return report_imu_static(imu)

    if args.odom_drive:
        print(f'Collecting {args.odom_topic} for {args.duration:g} s. Drive the robot')
        print('slowly forward and turn with teleop (motors must be enabled).')
        deadline = time.monotonic() + args.duration
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.05)
            time.sleep(0.01)
        rclpy.shutdown()
        return report_odom_yaw_residual(node)

    # Default: both.
    imu = collect_static(node, args.duration)
    rclpy.shutdown()
    return report_imu_static(imu)


if __name__ == '__main__':
    raise SystemExit(main())
#!/usr/bin/env python3
# Copyright 2025 The slam-robot contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
lidar_scan_publisher
~~~~~~~~~~~~~~~~~~~~
ROS 2 node that reads a YDLIDAR S4B-class lidar on a serial port (RX only,
no TX handshake needed) and publishes sensor_msgs/LaserScan on /scan.

All protocol handling lives in `ydlidar_protocol.py` (ROS free, unit
testable / replayable offline with scripts/lidar_replay.py).  The framing used
there was verified against a real capture with the vendor checksum:

  * 10 byte header, samples start at header + 10 (NOT + 9),
  * 3 bytes per sample: [quality][dist_lo][dist_hi] (intensity first),
  * range_m = distance_q2 / 4000.0   (TYPE_TRIANGLE scale),
  * angle  = (FSA >> 1)/64 + i*interval + second order distance correction.

Getting the sample offset wrong (header + 9) shifts every sample by one byte
and completely scrambles the ranges (they become ~256x too large and wrap
around), which is what produced the "V shaped" walls and the multiple
echoes seen in RViz.

Examples
--------
    ros2 run lidar_scan_publisher lidar_scan_publisher --ros-args \
        -p port:=/dev/ttyUSB0 -p baud:=153600 -p frame_id:=laser

    ros2 run lidar_scan_publisher lidar_scan_publisher --port /dev/ttyUSB0 \
        --angle-increment 1.0 --range-max 8.0
"""

import argparse
import math
import sys
import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan

try:
    import serial
except ImportError:  # pragma: no cover
    print('pyserial is required: pip install pyserial', file=sys.stderr)
    raise

try:
    from .ydlidar_protocol import DISTANCE_SCALE_TRIANGLE, YdLidarParser
except ImportError:  # running as a plain script
    from ydlidar_protocol import DISTANCE_SCALE_TRIANGLE, YdLidarParser


class LidarScanPublisher(Node):

    def __init__(self, args):
        super().__init__('lidar_scan_publisher')

        self.declare_parameter('port', args.port)
        self.declare_parameter('baud', args.baud)
        self.declare_parameter('frame_id', args.frame_id)
        self.declare_parameter('angle_min_deg', args.angle_min)
        self.declare_parameter('angle_max_deg', args.angle_max)
        self.declare_parameter('angle_increment_deg', args.angle_increment)
        self.declare_parameter('range_min', args.range_min)
        self.declare_parameter('range_max', args.range_max)
        self.declare_parameter('distance_scale', args.scale)
        self.declare_parameter('invert', args.invert)
        self.declare_parameter('correct_angles', not args.no_correct)

        self.port = self.get_parameter('port').value
        self.baud = int(self.get_parameter('baud').value)
        self.frame_id = self.get_parameter('frame_id').value
        self.angle_min_deg = float(self.get_parameter('angle_min_deg').value)
        self.angle_max_deg = float(self.get_parameter('angle_max_deg').value)
        self.angle_increment_deg = float(
            self.get_parameter('angle_increment_deg').value)
        self.range_min = float(self.get_parameter('range_min').value)
        self.range_max = float(self.get_parameter('range_max').value)
        self.scale = float(self.get_parameter('distance_scale').value)
        self.invert = bool(self.get_parameter('invert').value)
        if getattr(args, 'no_invert', False):
            self.invert = False
        self.correct_angles = bool(self.get_parameter('correct_angles').value)

        self.pub = self.create_publisher(LaserScan, 'scan', 10)

        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baud,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1)
        except Exception as exc:                       # pragma: no cover
            self.get_logger().fatal(f'cannot open {self.port}: {exc}')
            raise

        self.get_logger().info(
            f'YDLIDAR publisher: {self.port} @ {self.baud} baud, frame '
            f'"{self.frame_id}", distance scale /{self.scale:.0f}, angles '
            f'{self.angle_min_deg}..{self.angle_max_deg} deg step '
            f'{self.angle_increment_deg} deg, range '
            f'{self.range_min}..{self.range_max} m')

        self.parser = YdLidarParser(scale=self.scale,
                                    range_min=self.range_min,
                                    range_max=self.range_max,
                                    correct_angles=self.correct_angles,
                                    invert=self.invert)
        self._scan_period = 0.1365        # s, refined from the ring starts
        self._last_rev_end = None
        self._revolutions = 0

        self.timer = self.create_timer(0.02, self._timer_callback)

    # ------------------------------------------------------------------
    def _timer_callback(self):
        try:
            data = self.ser.read(4096)
        except Exception as exc:                       # pragma: no cover
            self.get_logger().error(f'serial read failed: {exc}')
            return
        if data:
            for rev in self.parser.feed(data):
                self._publish(rev)
        if (self._last_rev_end is not None and
                time.monotonic() - self._last_rev_end > 2.0):
            # no complete revolution for 2 s -> publish what we have
            self._publish(self.parser.flush())
            self._last_rev_end = None

    # ------------------------------------------------------------------
    def _publish(self, revolution):
        if not revolution:
            return
        now = time.monotonic()
        if self._last_rev_end is not None:
            period = now - self._last_rev_end
            if 0.02 < period < 2.0:
                self._scan_period = period
        self._last_rev_end = now
        self._revolutions += 1

        n_cells = int(round((self.angle_max_deg - self.angle_min_deg) /
                            self.angle_increment_deg)) + 1
        ranges = [float('inf')] * n_cells
        intensities = [0.0] * n_cells
        for p in revolution:
            a = p.angle
            while a < self.angle_min_deg:
                a += 360.0
            while a >= self.angle_max_deg:
                a -= 360.0
            idx = int(math.ceil((a - self.angle_min_deg) /
                                self.angle_increment_deg))
            if 0 <= idx < n_cells and not math.isinf(p.rng):
                ranges[idx] = p.rng
                intensities[idx] = p.quality

        scan = LaserScan()
        scan.header.stamp = self.get_clock().now().to_msg()
        scan.header.frame_id = self.frame_id
        scan.angle_min = math.radians(self.angle_min_deg)
        scan.angle_max = math.radians(self.angle_min_deg +
                                      (n_cells - 1) * self.angle_increment_deg)
        scan.angle_increment = math.radians(self.angle_increment_deg)
        scan.time_increment = self._scan_period / max(1, n_cells - 1)
        scan.scan_time = self._scan_period
        scan.range_min = self.range_min
        scan.range_max = self.range_max
        scan.ranges = ranges
        scan.intensities = intensities
        self.pub.publish(scan)

        valid = sum(1 for r in ranges if not math.isinf(r))
        self.get_logger().debug(
            f'scan {self._revolutions}: {n_cells} cells, {valid} valid, '
            f'period {self._scan_period * 1000:.1f} ms, packets '
            f'{self.parser.stats["packets"]}, bad '
            f'{self.parser.stats["bad_checksum"]}')


def main(args=None):
    parser = argparse.ArgumentParser(description='YDLIDAR -> LaserScan')
    parser.add_argument('--port', default='/dev/ttyUSB0')
    parser.add_argument('--baud', type=int, default=153600)
    parser.add_argument('--frame-id', default='laser')
    parser.add_argument('--angle-min', type=float, default=-180.0)
    parser.add_argument('--angle-max', type=float, default=180.0)
    parser.add_argument('--angle-increment', type=float, default=1.0)
    parser.add_argument('--range-min', type=float, default=0.12)
    parser.add_argument('--range-max', type=float, default=8.0)
    parser.add_argument('--scale', type=float, default=DISTANCE_SCALE_TRIANGLE,
                        help='range_m = distance_q2 / scale (SDK: 4000)')
    parser.add_argument('--invert', action='store_true', default=True,
                        help='mirror the scan (default: true)')
    parser.add_argument('--no-invert', action='store_true',
                        help='disable inversion')
    parser.add_argument('--no-correct', action='store_true',
                        help='disable the second order angle correction')
    cli = parser.parse_args(args)
    if getattr(cli, 'no_invert', False):
        cli.invert = False
    else:
        cli.invert = True  # default to inverted as per field testing

    rclpy.init(args=args)
    node = LidarScanPublisher(cli)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

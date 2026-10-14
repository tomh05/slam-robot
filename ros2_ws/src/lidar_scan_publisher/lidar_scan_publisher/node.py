#!/usr/bin/env python3
"""
lidar_scan_publisher
~~~~~~~~~~~~~~~~~~~~
ROS 2 node that reads a YDLIDAR S4B‑compatible lidar on /dev/ttyUSB0
(RX‑only, no TX needed) and publishes sensor_msgs/LaserScan on /scan.

Assumptions (matching your test‑session log):
  * Baud rate: 153600
  * Packet header: 0xAA 0x55
  * Angle encoding: (value >> 1) / 64.0  degrees
  * Distance: raw units = millimetres (if scaling differs, adjust DIST_SCALE)
  * Intensity: 8‑bit
  * Sample rate: 4 kHz (samples per second) – used to compute scan time.
"""

import math
import struct
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
import serial


class LidarScanPublisher(Node):
    def __init__(self):
        super().__init__('lidar_scan_publisher')
        # Publisher
        self.pub = self.create_publisher(LaserScan, 'scan', 10)

        # Serial configuration – adjust if your port differs
        self.ser = serial.Serial(
            port='/dev/ttyUSB0',
            baudrate=153600,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1
        )
        self.get_logger().info('Lidar scan publisher started on /dev/ttyUSB0 @ 153600 baud')

        # Timer to periodically process incoming bytes (≈50 Hz)
        self.timer = self.create_timer(0.02, self.timer_callback)

        # Buffer for incomplete packets that span reads
        self._buffer = b''

        # Accumulators for building a full scan
        self._acc_ranges = []        # distances in metres
        self._acc_intensities = []   # intensity as float
        self._acc_angles_raw = []    # raw angle in degrees [0,360) for unwrapping
        self._last_raw_angle = None  # last raw angle seen (degrees) for unwrapping
        self._angle_offset = 0.0     # cumulative offset to keep angle monotonic (degrees)
        self._last_packet_time = self.get_clock().now()

        # Constants
        self._SAMPLE_RATE_HZ = 4000.0   # samples per second (4 kHz)
        self._SCAN_TIMEOUT_SEC = 0.5    # if no packet for this long, force publish

    def timer_callback(self):
        """Read whatever is available, try to extract complete packets, publish scans."""
        data = self.ser.read(2048)
        if not data:
            return
        self._process_buffer(data)

        # Timeout check: if we have accumulated data but no new packet for a while, publish
        now = self.get_clock().now()
        if (now - self._last_packet_time).nanoseconds / 1e9 > self._SCAN_TIMEOUT_SEC:
            if self._acc_ranges:
                self._publish_accumulated_scan()
                self._acc_ranges.clear()
                self._acc_intensities.clear()
                self._acc_angles_raw = []
                self._last_raw_angle = None
                self._angle_offset = 0.0

    def _process_buffer(self, raw: bytes):
        """Append new data to internal buffer and extract as many full packets as possible."""
        buf = self._buffer + raw
        self._buffer = b''
        i = 0
        while i < len(buf) - 1:
            # Look for the packet header AA 55
            if buf[i] == 0xAA and i + 1 < len(buf) and buf[i + 1] == 0x55:
                # Minimum packet size: header + 9 bytes (CT LSN FSA LSA CS) + at least 1 sample (3 bytes)
                if i + 9 > len(buf):
                    # Not enough data yet – keep what we have and wait for more
                    self._buffer = buf[i:]
                    break

                CT = buf[i + 2]
                LSN = buf[i + 3]                     # number of samples in this packet
                FSA = struct.unpack('<H', buf[i + 4:i + 6])[0]   # First Sample Angle (raw)
                LSA = struct.unpack('<H', buf[i + 6:i + 8])[0]   # Last Sample Angle (raw)
                CS = buf[i + 8]                      # Checksum (we ignore it for simplicity)

                # Verify we have enough bytes for the samples
                samp_start = i + 9
                needed = samp_start + LSN * 3       # each sample = 3 bytes (distLo, distHi, intensity)
                if needed > len(buf):
                    self._buffer = buf[i:]
                    break

                # Parse samples (intensity first, then distance low/high)
                packet_ranges = []
                packet_intensities = []
                packet_angles_raw = []   # raw angle in degrees [0,360)
                for n in range(LSN):
                    off = samp_start + n * 3
                    intensity = buf[off]
                    dist_low = buf[off + 1]
                    dist_high = buf[off + 2]
                    distance_raw = dist_low | (dist_high << 8)   # little endian, raw units
                    # Apply mask and convert to metres: (raw & 0xfffc) / 4000.0
                    distance_q2 = distance_raw & 0xfffc
                    range_m = distance_q2 / 4000.0
                    # Invalid range -> inf
                    if range_m <= 0.0 or math.isinf(range_m) or range_m < 0.12 or range_m > 16.0:
                        range_m = float('inf')
                    packet_ranges.append(range_m)
                    packet_intensities.append(float(intensity))

                    # ---- Angle calculation (first‑order + second‑order correction) ----
                    fsa_angle = (FSA >> 1) / 64.0
                    lsa_angle = (LSA >> 1) / 64.0
                    if lsa_angle < fsa_angle:
                        lsa_angle += 360.0
                    raw_step = (lsa_angle - fsa_angle) / (LSN - 1) if LSN > 1 else 0.0
                    # Motor spins clockwise, lidar reports CCW -> invert step
                    step = -raw_step

                    # Base angle for this sample
                    angle_deg = fsa_angle + n * step

                    # Second‑order angle correction (YDLIDAR protocol)
                    if distance_q2 > 0:   # avoid division by zero
                        # AngCorrect = atan(21.8 * (155.3 - d) / (155.3 * d)) * (180/π)
                        ang_corr = math.atan2(
                            21.8 * (155.3 - distance_q2),
                            155.3 * distance_q2
                        ) * 180.0 / math.pi
                    else:
                        ang_corr = 0.0
                    angle_deg += ang_corr
                    # Keep angle in [0,360) for unwrapping later
                    if angle_deg < 0.0:
                        angle_deg += 360.0
                    elif angle_deg >= 360.0:
                        angle_deg -= 360.0
                    # --------------------------------------------------------------

                    packet_angles_raw.append(angle_deg)

                # Determine if this packet marks the start of a new ring
                ring_start = (CT & 0x01) == 1

                                # Unwrap angles and accumulate
                for angle_deg, range_m, intensity in zip(packet_angles_raw, packet_ranges, packet_intensities):
                    if self._last_raw_angle is not None:
                        # Detect big jump indicating wrap (new scan)
                        if angle_deg < self._last_raw_angle - 180.0:
                            # Publish accumulated scan if we have data
                            if self._acc_ranges:
                                self._publish_accumulated_scan()
                                # Reset accumulators for new scan
                                self._acc_ranges = []
                                self._acc_intensities = []
                                self._acc_angles_raw = []
                                self._last_raw_angle = None
                                # Keep angle_offset as is? Actually we need to adjust offset to maintain continuity.
                                # We'll add 360 to offset to keep angles increasing.
                                self._angle_offset += 360.0
                            # After reset, set last_raw_angle to None so next sample starts fresh
                            self._last_raw_angle = None
                        elif angle_deg > self._last_raw_angle + 180.0:
                            # Wrap the other way (unlikely but handle)
                            self._angle_offset -= 360.0
                    adjusted_angle = angle_deg + self._angle_offset
                    self._acc_ranges.append(range_m)
                    self._acc_intensities.append(intensity)
                    self._acc_angles_raw.append(adjusted_angle)
                    self._last_raw_angle = angle_deg

                # Update last packet time
                self._last_packet_time = self.get_clock().now()

                # Move index past this packet and continue looking for another header
                i = needed
            else:
                i += 1

        # Any trailing bytes that could be a split header are kept for next iteration
        if i > 0 and i < len(buf):
            self._buffer = buf[i:]

    def _publish_accumulated_scan(self):
        """Build and publish a LaserScan message from the accumulated data."""
        if not self._acc_ranges:
            return
        N = len(self._acc_ranges)
        if N < 2:
            # Not enough points to form a scan
            return

        # Angles are already unwrapped and monotonic increasing (in degrees)
        angle_min_deg = self._acc_angles_raw[0]
        angle_max_deg = self._acc_angles_raw[-1]
        # Ensure we have less than one full rotation (should be true)
        span_deg = angle_max_deg - angle_min_deg
        if span_deg >= 360.0:
            # More than one rotation; truncate to first 360 degrees
            # Find where angle exceeds angle_min_deg + 360
            limit = angle_min_deg + 360.0
            idx = 0
            while idx < N and self._acc_angles_raw[idx] < limit:
                idx += 1
            N = idx
            if N < 2:
                return
            angle_max_deg = self._acc_angles_raw[N-1]
            # Trim arrays
            self._acc_ranges = self._acc_ranges[:N]
            self._acc_intensities = self._acc_intensities[:N]
            self._acc_angles_raw = self._acc_angles_raw[:N]

        angle_min_rad = math.radians(angle_min_deg)
        angle_max_rad = math.radians(angle_max_deg)
        angle_increment_rad = (angle_max_rad - angle_min_rad) / (N - 1) if N > 1 else 0.0

        # Compute scan time based on sample rate and number of samples
        time_per_sample = 1.0 / self._SAMPLE_RATE_HZ
        scan_time = (N - 1) * time_per_sample
        time_increment = time_per_sample

        scan = LaserScan()
        scan.header.stamp = self.get_clock().now().to_msg()
        scan.header.frame_id = 'laser'
        scan.angle_min = angle_min_rad
        scan.angle_max = angle_max_rad
        scan.angle_increment = angle_increment_rad
        scan.time_increment = time_increment
        scan.scan_time = scan_time
        scan.range_min = 0.12   # from S4B spec (metres)
        scan.range_max = 16.0   # from S4B spec (metres)
        scan.ranges = self._acc_ranges
        scan.intensities = self._acc_intensities
        self.pub.publish(scan)
        self.get_logger().debug(f'Published scan with {N} points')


def main(args=None):
    rclpy.init(args=args)
    node = LidarScanPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
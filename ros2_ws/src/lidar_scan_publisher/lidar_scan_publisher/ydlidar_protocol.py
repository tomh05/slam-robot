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
ydlidar_protocol.py -- pure python YDLIDAR (S4B class) packet decoder.

No ROS, no serial: this module only turns a byte stream into points, so that
it can be unit tested / replayed offline (see scripts/lidar_replay.py).

Framing (verified by vendor checksum on a real capture, 100% of 1111 packets):

    AA 55 | CT | LSN | FSA(2) | LSA(2) | CS(2) | sample*LSN

    header = 10 bytes, samples start at header + 10
    sample = [quality][dist_lo][dist_hi]      (3 bytes, intensity first)
    distance_q2 = (dist_lo | dist_hi << 8) & 0xfffc
    range_m    = distance_q2 / 4000.0          (TYPE_TRIANGLE scale)
    angle      = (FSA >> 1)/64 + i*interval
                 + atan(21.8*(155.3 - d_mm)/(155.3*d_mm)) * 180/pi
                 with d_mm = distance_q2 / 4.0

The vendor checksum is:

    c  = 0x55AA ^ FSA ^ (CT + LSN*256) ^ LSA
    c ^= quality_byte
    c ^= distance_word        (per sample)
"""

import math
import struct

PH = 0x55AA
HEADER_LEN = 10
ANGLE_CHECK_BIT = 0x1
ANGLE_SHIFT = 1
ANGLE_SCALE = 64.0                 # angle word >> 1 -> 1/64 degree
FULL_CIRCLE_UNITS = 360 * 64
DISTANCE_SCALE_TRIANGLE = 4000.0   # range_m = distance_q2 / 4000


def checksum(ct, lsn, fsa, lsa, payload):
    """Vendor packet checksum (YDLIDAR-SDK/src/ydlidar_driver.cpp)."""
    c = PH ^ fsa ^ (ct + (lsn << 8)) ^ lsa
    for i in range(0, len(payload), 3):
        c ^= payload[i]                                  # quality byte
        c ^= payload[i + 1] | (payload[i + 2] << 8)      # 16 bit distance
    return c & 0xFFFF


def angle_correction_deg(distance_q2):
    """Second order, distance dependent angle correction (YDLIDAR protocol)."""
    d_mm = distance_q2 / 4.0
    if d_mm <= 0.0:
        return 0.0
    return math.atan(((21.8 * (155.3 - d_mm)) / 155.3) / d_mm) * 180.0 / math.pi


class Point:
    __slots__ = ('angle', 'rng', 'quality', 'raw', 'packet')

    def __init__(self, angle, rng, quality, raw, packet):
        self.angle = angle      # degrees, [0, 360)
        self.rng = rng          # metres (inf = invalid / out of range)
        self.quality = quality  # 8 bit intensity
        self.raw = raw          # raw distance word
        self.packet = packet    # index of the packet it came from


class YdLidarParser:
    """Incremental parser: feed() bytes, get revolutions of points back."""

    def __init__(self, scale=DISTANCE_SCALE_TRIANGLE, range_min=0.12,
                 range_max=8.0, correct_angles=True, invert=False,
                 validate_checksum=True):
        self.scale = scale
        self.range_min = range_min
        self.range_max = range_max
        self.correct_angles = correct_angles
        self.invert = invert
        self.validate_checksum = validate_checksum

        self._buffer = bytearray()
        self._last_interval = None
        self._revolution = []
        self._packet_index = 0
        self.stats = dict(packets=0, bad_checksum=0, bad_header=0,
                           samples=0, revolutions=0)

    # -- public ---------------------------------------------------------
    def feed(self, data):
        """Feed bytes, return a list of completed revolutions (lists of Point)."""
        buf = self._buffer + bytearray(data)
        i = 0
        n = len(buf)
        revolutions = []
        while i < n - 1:
            if buf[i] != 0xAA or buf[i + 1] != 0x55:
                i += 1
                continue
            if i + HEADER_LEN > n:
                break
            ct = buf[i + 2]
            lsn = buf[i + 3]
            fsa, lsa, cs = struct.unpack('<HHH', buf[i + 4:i + 10])
            if not (fsa & ANGLE_CHECK_BIT) or not (lsa & ANGLE_CHECK_BIT):
                self.stats['bad_header'] += 1
                i += 1
                continue
            start = i + HEADER_LEN
            end = start + lsn * 3
            if end > n:
                break
            payload = bytes(buf[start:end])
            i = end
            self.stats['packets'] += 1
            if self.validate_checksum and checksum(ct, lsn, fsa, lsa, payload) != cs:
                self.stats['bad_checksum'] += 1
                continue
            points, ring_start = self._decode_packet(ct, lsn, fsa, lsa, payload)
            self.stats['samples'] += len(points)
            if ring_start:
                if self._revolution:
                    revolutions.append(self._revolution)
                    self.stats['revolutions'] += 1
                self._revolution = []
            self._revolution.extend(points)
        self._buffer = bytearray(buf[i:])
        return revolutions

    def flush(self):
        """Return the points of an unfinished revolution (if any)."""
        if self._revolution:
            rev = self._revolution
            self._revolution = []
            return rev
        return []

    # -- internals ------------------------------------------------------
    def _packet_interval(self, lsn, fsa, lsa):
        """Sample angle step of a packet in 1/64 degree units (SDK logic)."""
        if lsn <= 1:
            return 0.0
        first = fsa >> ANGLE_SHIFT
        last = lsa >> ANGLE_SHIFT
        if last < first:
            if first > 270 * 64 and last < 90 * 64:
                return (FULL_CIRCLE_UNITS + last - first) / (lsn - 1)
            return None                    # unknown -> reuse previous
        return (last - first) / (lsn - 1)

    def _decode_packet(self, ct, lsn, fsa, lsa, payload):
        interval = self._packet_interval(lsn, fsa, lsa)
        if interval is None:
            interval = self._last_interval
        else:
            self._last_interval = interval
        if interval is None:
            return [], (ct & 0x01) == 1

        fsa_units = fsa >> ANGLE_SHIFT
        points = []
        for idx in range(lsn):
            off = idx * 3
            quality = payload[off]
            raw = payload[off + 1] | (payload[off + 2] << 8)
            distance_q2 = raw & 0xfffc
            rng = distance_q2 / self.scale
            if rng < self.range_min or rng > self.range_max:
                rng = float('inf')
            angle = fsa_units + interval * idx
            if self.correct_angles:
                angle += angle_correction_deg(distance_q2) * ANGLE_SCALE
            angle = (angle / ANGLE_SCALE) % 360.0
            if self.invert:
                angle = (360.0 - angle) % 360.0
            points.append(Point(angle, rng, float(quality), raw,
                                self._packet_index))
        self._packet_index += 1
        return points, (ct & 0x01) == 1

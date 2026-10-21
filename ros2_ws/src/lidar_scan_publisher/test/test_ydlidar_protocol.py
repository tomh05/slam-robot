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
Tests for the YDLIDAR protocol decoder.

Run locally:
    python3 -m pytest ros2_ws/src/lidar_scan_publisher/test -q
or on the robot after `colcon build`:
    colcon test --packages-select lidar_scan_publisher
"""

import math
import os
import struct
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PKG_PARENT = os.path.dirname(HERE)      # .../src/lidar_scan_publisher
if PKG_PARENT not in sys.path:
    sys.path.insert(0, PKG_PARENT)

from lidar_scan_publisher.ydlidar_protocol import (  # noqa: E402
    YdLidarParser, checksum)

REPO_CAPTURE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(HERE)))),
    'lidar_153600.bin')


def build_packet(ct, lsn, fsa, lsa, samples):
    """Build a raw packet (header + payload) with a correct checksum."""
    payload = b''.join(bytes(s) for s in samples)
    cs = checksum(ct, lsn, fsa, lsa, payload)
    return struct.pack('<BBBBHHH', 0xAA, 0x55, ct, lsn, fsa, lsa, cs) + payload


def raw_angle(deg):
    """16 bit angle word for a given angle in degrees (bit0 = check bit)."""
    return ((int(round(deg * 64)) << 1) | 1) & 0xFFFF


def make_samples(distances, qualities=None):
    out = []
    for i, d in enumerate(distances):
        q = 100 if qualities is None else qualities[i]
        out.append((q, d & 0xFF, (d >> 8) & 0xFF))
    return out


def test_checksum_rejects_corruption():
    payload = b''.join(bytes(s) for s in make_samples([1000, 2000, 3000]))
    assert checksum(0x28, 3, 0x8000, 0x8100, payload) is not None
    bad = bytearray(payload)
    bad[4] ^= 0xFF
    assert checksum(0x28, 3, 0x8000, 0x8100, bytes(bad)) != \
        checksum(0x28, 3, 0x8000, 0x8100, payload)


def test_sample_layout_and_scale():
    """3 byte samples [quality][lo][hi], distance_q2/4000 -> metres."""
    p = YdLidarParser(correct_angles=False)
    dists = [4000, 8000, 12000]          # 1.0 m, 2.0 m, 3.0 m
    fsa = raw_angle(100)                # 100 deg
    lsa = raw_angle(102)                # 102 deg
    raw = build_packet(0x28, 3, fsa, lsa, make_samples(dists))
    revs = p.feed(raw)
    assert p.stats['packets'] == 1
    assert p.stats['bad_checksum'] == 0
    rev = p.flush()
    assert len(rev) == 3
    assert [round(pt.rng, 3) for pt in rev] == [1.0, 2.0, 3.0]
    assert all(pt.quality == 100 for pt in rev)
    # angles: 100, 101, 102 deg (2 deg over 3 samples -> 1 deg step)
    assert abs(rev[0].angle - 100.0) < 1e-6
    assert abs(rev[1].angle - 101.0) < 1e-6
    assert abs(rev[2].angle - 102.0) < 1e-6


def test_second_order_angle_correction():
    """The SDK correction shifts the angle by atan(21.8*(155.3-d)/155.3/d)."""
    p = YdLidarParser(correct_angles=True)
    fsa = raw_angle(100)
    lsa = raw_angle(102)
    raw = build_packet(0x28, 3, fsa, lsa, make_samples([4000, 8000, 12000]))
    p.feed(raw)
    rev = p.flush()
    d_mm = 4000 / 4.0
    expected_corr = math.atan(((21.8 * (155.3 - d_mm)) / 155.3) / d_mm) * 180 / math.pi
    assert abs((rev[0].angle - 100.0) - expected_corr) < 1e-6
    assert expected_corr < 0.0            # close range -> negative correction


def test_ring_start_splits_revolutions():
    p = YdLidarParser()
    fsa = raw_angle(10)
    lsa = raw_angle(12)
    data = b''
    data += build_packet(0x28, 2, fsa, lsa, make_samples([4000, 4000]))
    data += build_packet(0x93, 1, fsa, fsa, make_samples([4000]))   # ring start
    data += build_packet(0x28, 2, fsa, lsa, make_samples([8000, 8000]))
    data += build_packet(0x93, 1, fsa, fsa, make_samples([8000]))   # ring start
    revs = p.feed(data)
    assert len(revs) == 2
    assert len(revs[0]) == 2          # the normal packet
    assert len(revs[1]) == 3          # ring start sample + the normal packet


def test_angle_wrap_special_case():
    """LSA < FSA across 0 deg must use the SDK's wrap formula."""
    p = YdLidarParser()
    fsa = raw_angle(349)
    lsa = raw_angle(15)
    step = p._packet_interval(40, fsa, lsa)
    expected = (360 * 64 + (15 * 64) - (349 * 64)) / 39
    assert abs(step - expected) < 1e-9
    assert abs(step / 64.0 - 0.6636) < 0.01


def test_corrupt_packet_is_dropped():
    p = YdLidarParser()
    fsa = raw_angle(10)
    lsa = raw_angle(12)
    raw = bytearray(build_packet(0x28, 2, fsa, lsa, make_samples([4000, 4000])))
    raw[12] ^= 0xFF                      # corrupt the first distance byte
    p.feed(bytes(raw))
    assert p.stats['packets'] == 1
    assert p.stats['bad_checksum'] == 1
    assert len(p.flush()) == 0


@pytest.mark.skipif(not os.path.exists(REPO_CAPTURE),
                    reason='sample capture not available')
def test_real_capture_regression():
    """The recorded capture must decode cleanly (this is the regression)."""
    with open(REPO_CAPTURE, 'rb') as f:
        data = f.read()
    p = YdLidarParser()
    revs = p.feed(data)
    assert p.stats['packets'] == 1111
    assert p.stats['bad_checksum'] == 0
    assert p.stats['bad_header'] == 0
    assert len(revs) >= 70
    sizes = [len(r) for r in revs]
    assert max(sizes) == 546            # 4 kHz / 7.33 Hz
    # every real (non sentinel) range must be inside the S4B spec
    for rev in revs:
        for pt in rev:
            if not math.isinf(pt.rng):
                assert 0.10 <= pt.rng <= 8.0

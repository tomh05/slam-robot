#!/usr/bin/env python3
"""
decode_packet.py -- quick look at the first few lidar packets.

SUPERSEDED by scripts/lidar_debug.py (which also validates the framing with
the vendor checksum).  Kept because it is handy for a 10 second sanity check.

    python3 decode_packet.py [port] [baud]

Note the two things that were wrong in the original version of this script
(and in the ROS 2 node):

  * the header is 10 bytes (AA 55 CT LSN FSA(2) LSA(2) CS(2)), so the samples
    start at header + 10, not header + 9,
  * a sample is [quality][dist_lo][dist_hi] - the intensity comes FIRST.
"""

import struct
import sys

import serial

port = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyUSB0'
baud = int(sys.argv[2]) if len(sys.argv) > 2 else 153600

ser = serial.Serial(port, baud, timeout=0.5)
ser.reset_input_buffer()
data = ser.read(8192)
ser.close()

i = 0
packets = 0
while i < len(data) - 1 and packets < 5:
    if data[i] == 0xAA and i + 1 < len(data) and data[i + 1] == 0x55:
        if i + 10 > len(data):
            break
        CT = data[i + 2]
        LSN = data[i + 3]
        FSA = struct.unpack('<H', data[i + 4:i + 6])[0]
        LSA = struct.unpack('<H', data[i + 6:i + 8])[0]
        CS = struct.unpack('<H', data[i + 8:i + 10])[0]
        samp_start = i + 10                     # <-- 10, not 9
        needed = samp_start + LSN * 3
        if needed > len(data):
            break
        fsa_deg = (FSA >> 1) / 64.0
        lsa_deg = (LSA >> 1) / 64.0
        if lsa_deg < fsa_deg:
            lsa_deg += 360.0
        step = (lsa_deg - fsa_deg) / (LSN - 1) if LSN > 1 else 0.0
        ring = 'RING_START' if (CT & 0x01) else 'normal'
        print(f"Packet {packets}: {ring} CT=0x{CT:02x} LSN={LSN} "
              f"FSA={fsa_deg:.2f}° LSA={lsa_deg:.2f}° step={step:.4f}° "
              f"CS=0x{CS:04x}")
        for n in range(min(3, LSN)):
            off = samp_start + n * 3
            intensity = data[off]               # <-- intensity first
            dist_lo = data[off + 1]
            dist_hi = data[off + 2]
            dist = (dist_lo | (dist_hi << 8)) & 0xfffc
            print(f"  sample {n}: raw={dist} ({dist / 4000.0:.3f} m) "
                  f"intensity={intensity}")
        packets += 1
        i = needed
    else:
        i += 1

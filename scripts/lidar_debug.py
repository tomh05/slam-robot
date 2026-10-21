#!/usr/bin/env python3
"""
lidar_debug.py -- YDLIDAR (S4B-class) packet inspector / protocol debugger.

Purpose
-------
The ROS 2 node (`ros2_ws/src/lidar_scan_publisher`) was producing bogus ranges
(distances too large, "V" shaped walls, multiple echoes, angle jitter).  This
tool is the ground-truth debugger for the raw UART stream:

  * finds and validates packets using the *vendor checksum* (the algorithm is
    taken verbatim from YDLIDAR-SDK `ydlidar_driver.cpp`),
  * brute-forces the candidate sample layouts / header offsets and reports
    which one actually produces valid checksums (this settles "is the sample
    [intensity][dist_lo][dist_hi] or [dist_lo][dist_hi][intensity]?" and
    "does the sample block start at header+9 or header+10?" objectively),
  * decodes a packet into angles/ranges with the *same* maths as the vendor
    SDK (interval angle + second order distance correction),
  * assembles complete revolutions and can dump them as CSV for plotting,
  * prints range histograms so that the distance scale can be sanity checked.

Usage
-----
    # live capture from the robot
    python3 lidar_debug.py --port /dev/ttyUSB0 --baud 153600 --seconds 5

    # offline analysis of a saved capture
    python3 lidar_debug.py --file lidar_153600.bin

    # dump one revolution as CSV
    python3 lidar_debug.py --port /dev/ttyUSB0 --csv /tmp/scan.csv --revolutions 1

    # show the packet stream (first 10 packets, hex)
    python3 lidar_debug.py --port /dev/ttyUSB0 --packets 10 --hex

No ROS 2 required; only `pyserial` for live capture.
"""

import argparse
import math
import os
import struct
import sys
from collections import Counter

# ----------------------------------------------------------------------------
# YDLIDAR protocol constants (from YDLIDAR-SDK core/common/ydlidar_protocol.h)
# ----------------------------------------------------------------------------
PH = 0x55AA                 # packet header (0xAA 0x55 on the wire)
PACKAGE_PAID_BYTES = 10     # AA 55 CT LSN FSA(2) LSA(2) CS(2)
PACKAGE_SAMPLE_MAX = 0x100
ANGLE_CHECK_BIT = 0x1       # bit0 of a 16 bit angle word must be set
ANGLE_SHIFT = 1             # angle word >> 1 -> 1/64 degree units
ANGLE_SCALE = 64.0          # 1/64 degree per unit
FULL_CIRCLE_UNITS = 360 * 64  # 23040


# ----------------------------------------------------------------------------
# Checksum (verbatim from YDLIDAR-SDK/src/ydlidar_driver.cpp)
# ----------------------------------------------------------------------------
def checksum(ct, lsn, fsa_raw, lsa_raw, payload, layout):
    """YDLIDAR packet checksum.

    layout 'A' = [quality, dist_lo, dist_hi]   (SDK: intensity first)
    layout 'B' = [dist_lo, dist_hi, quality]
    layout 'T' = [dist_lo, dist_hi]             (2 byte samples, no intensity)
    """
    c = PH
    c ^= fsa_raw
    c ^= (ct + (lsn << 8))
    c ^= lsa_raw
    if layout == 'A':
        for i in range(0, len(payload), 3):
            c ^= payload[i]                      # quality byte
            c ^= payload[i + 1] | (payload[i + 2] << 8)   # 16 bit word
    elif layout == 'B':
        for i in range(0, len(payload), 3):
            c ^= payload[i] | (payload[i + 1] << 8)
            c ^= payload[i + 2]
    elif layout == 'T':
        for i in range(0, len(payload), 2):
            c ^= payload[i] | (payload[i + 1] << 8)
    return c & 0xFFFF


# ----------------------------------------------------------------------------
# Packet parsing
# ----------------------------------------------------------------------------
class Packet:
    __slots__ = ('ct', 'lsn', 'fsa', 'lsa', 'cs', 'payload', 'offset',
                 'layout', 'header_len', 'checksum_ok')

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

    @property
    def ring_start(self):
        return (self.ct & 0x01) == 1

    @property
    def fsa_deg(self):
        return (self.fsa >> ANGLE_SHIFT) / ANGLE_SCALE

    @property
    def lsa_deg(self):
        return (self.lsa >> ANGLE_SHIFT) / ANGLE_SCALE

    def samples(self, layout):
        """Yield (quality, distance_q2) pairs for the packet."""
        p = self.payload
        if layout == 'A':
            for i in range(0, len(p), 3):
                yield p[i], p[i + 1] | (p[i + 2] << 8)
        elif layout == 'B':
            for i in range(0, len(p), 3):
                yield p[i + 2], p[i] | (p[i + 1] << 8)
        elif layout == 'T':
            for i in range(0, len(p), 2):
                yield 0, p[i] | (p[i + 1] << 8)


def find_packets(buf, header_len=10, sample_bytes=3):
    """Yield (offset, ct, lsn, fsa, lsa, cs, payload) for every AA 55 frame."""
    i = 0
    n = len(buf)
    while i < n - 1:
        if buf[i] == 0xAA and buf[i + 1] == 0x55:
            if i + header_len > n:
                break
            ct = buf[i + 2]
            lsn = buf[i + 3]
            fsa, lsa, cs = struct.unpack('<HHH', buf[i + 4:i + 10])
            start = i + header_len
            end = start + lsn * sample_bytes
            if end > n:
                # truncated tail
                break
            yield i, ct, lsn, fsa, lsa, cs, buf[start:end]
            i = end
        else:
            i += 1


def score_layout(buf, header_len, sample_bytes, layout, max_packets=200):
    """Return (n_ok, n_total) checksum statistics for a candidate layout."""
    ok = total = 0
    for (_off, ct, lsn, fsa, lsa, cs, payload) in find_packets(buf, header_len, sample_bytes):
        total += 1
        if checksum(ct, lsn, fsa, lsa, payload, layout) == cs:
            ok += 1
        if total >= max_packets:
            break
    return ok, total


def brute_force(buf):
    """Try every plausible framing and report which one validates."""
    results = []
    for header_len in (9, 10):
        for sample_bytes, layout in ((3, 'A'), (3, 'B'), (2, 'T'), (4, 'A4')):
            if sample_bytes == 4 and layout == 'A4':
                # 4 byte sample: [q_lo, q_hi, d_lo, d_hi]
                ok, total = 0, 0
                for (_off, ct, lsn, fsa, lsa, cs, payload) in find_packets(buf, header_len, 4):
                    total += 1
                    c = PH ^ fsa ^ (ct + (lsn << 8)) ^ lsa
                    for i in range(0, len(payload), 4):
                        c ^= payload[i] | (payload[i + 1] << 8)
                        c ^= payload[i + 2] | (payload[i + 3] << 8)
                    if (c & 0xFFFF) == cs:
                        ok += 1
                    if total >= 200:
                        break
            else:
                ok, total = score_layout(buf, header_len, sample_bytes, layout)
            results.append((ok, total, header_len, sample_bytes, layout))
    results.sort(key=lambda r: (-r[0], r[1]))
    return results


# ----------------------------------------------------------------------------
# Decoding a packet into points (same maths as the vendor SDK)
# ----------------------------------------------------------------------------
def angle_correction_deg(distance_q2):
    """Second order distance dependent angle correction (YDLIDAR protocol).

    The SDK uses distance_q2/4.0 == millimetres in the formula.
    """
    d_mm = distance_q2 / 4.0
    if d_mm <= 0:
        return 0.0
    return math.atan(((21.8 * (155.3 - d_mm)) / 155.3) / d_mm) * 180.0 / math.pi


def decode_packet(pk, layout, scale, correct=True):
    """Return list of (angle_deg, range_m, quality) for one packet."""
    lsn = pk.lsn
    fsa = pk.fsa >> ANGLE_SHIFT
    lsa = pk.lsa >> ANGLE_SHIFT
    if lsn > 1:
        if lsa < fsa:
            if fsa > 270 * 64 and lsa < 90 * 64:
                interval = (360 * 64 + lsa - fsa) / (lsn - 1)
            else:
                interval = None  # unknown, caller keeps previous
        else:
            interval = (lsa - fsa) / (lsn - 1)
    else:
        interval = 0.0

    if interval is None:
        return [], interval

    out = []
    for idx, (q, dq2) in enumerate(pk.samples(layout)):
        ang = fsa + interval * idx
        if correct:
            ang += angle_correction_deg(dq2) * ANGLE_SCALE
        ang = (ang / ANGLE_SCALE) % 360.0
        rng = dq2 / scale
        if rng <= 0.0 or math.isinf(rng) or rng < 0.12 or rng > 8.0:
            rng = float('inf')
        out.append((ang, rng, q))
    return out, interval


# ----------------------------------------------------------------------------
# Capture helpers
# ----------------------------------------------------------------------------
def read_serial(port, baud, seconds):
    try:
        import serial
    except ImportError:
        print('pyserial is required for live capture (pip install pyserial)',
              file=sys.stderr)
        sys.exit(2)
    ser = serial.Serial(port, baud, timeout=0.2)
    ser.reset_input_buffer()
    import time
    end = time.time() + seconds
    chunks = []
    while time.time() < end:
        data = ser.read(4096)
        if data:
            chunks.append(data)
    ser.close()
    return b''.join(chunks)


# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', help='serial port (e.g. /dev/ttyUSB0)')
    ap.add_argument('--baud', type=int, default=153600)
    ap.add_argument('--seconds', type=float, default=5.0)
    ap.add_argument('--file', help='analyse a previously captured .bin file')
    ap.add_argument('--packets', type=int, default=10,
                    help='number of packets to print in detail')
    ap.add_argument('--hex', action='store_true', help='hex dump the raw bytes')
    ap.add_argument('--scale', type=float, default=4000.0,
                    help='distance divisor: range_m = distance_q2 / scale '
                         '(SDK uses 4000 for TYPE_TRIANGLE lidars)')
    ap.add_argument('--layout', default='auto',
                    choices=['auto', 'A', 'B', 'T'],
                    help='sample layout: A=[q,lo,hi] B=[lo,hi,q] T=[lo,hi]')
    ap.add_argument('--header-len', type=int, default=0,
                    help='override header length (0 = auto detect)')
    ap.add_argument('--csv', help='write one revolution of points to this CSV')
    ap.add_argument('--revolutions', type=int, default=1)
    ap.add_argument('--no-correct', action='store_true',
                    help='disable the second order angle correction')
    ap.add_argument('--histogram', action='store_true',
                    help='print a range histogram')
    args = ap.parse_args()

    if args.file:
        with open(args.file, 'rb') as f:
            buf = f.read()
        src = args.file
    elif args.port:
        buf = read_serial(args.port, args.baud, args.seconds)
        src = f'{args.port}@{args.baud} ({len(buf)} bytes)'
    else:
        ap.error('need --file or --port')

    print(f'== source: {src} ==')
    if args.hex:
        for i in range(0, min(len(buf), 512), 16):
            chunk = buf[i:i + 16]
            hexs = ' '.join(f'{b:02x}' for b in chunk)
            asci = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
            print(f'{i:06x}: {hexs:<47}  {asci}')

    # ---- which framing validates? ----------------------------------------
    print('\n== framing brute force (checksum validation) ==')
    results = brute_force(buf)
    for ok, total, hlen, sbytes, layout in results:
        pct = (100.0 * ok / total) if total else 0.0
        print(f'  header={hlen:2d}  sample_bytes={sbytes}  layout={layout:2s}  '
              f'checksum ok {ok}/{total} ({pct:.1f}%)')
    best = results[0]
    if best[0] == 0:
        print('  !! no candidate framing produced a single valid checksum')
    auto_layout, auto_hlen = best[4], best[2]
    if args.layout != 'auto':
        auto_layout = args.layout
    if args.header_len:
        auto_hlen = args.header_len
    sample_bytes = 3 if auto_layout in ('A', 'B') else 2
    print(f'  -> using header_len={auto_hlen}, layout={auto_layout}, '
          f'sample_bytes={sample_bytes}')

    # ---- packet detail ----------------------------------------------------
    print('\n== packets ==')
    packets = []
    for (off, ct, lsn, fsa, lsa, cs, payload) in find_packets(buf, auto_hlen, sample_bytes):
        ok = checksum(ct, lsn, fsa, lsa, payload, auto_layout) == cs
        pk = Packet(ct=ct, lsn=lsn, fsa=fsa, lsa=lsa, cs=cs, payload=payload,
                    offset=off, layout=auto_layout, header_len=auto_hlen,
                    checksum_ok=ok)
        packets.append(pk)

    n_ok = sum(1 for p in packets if p.checksum_ok)
    print(f'  {len(packets)} packets, {n_ok} with valid checksum')

    for pk in packets[:args.packets]:
        pts, interval = decode_packet(pk, auto_layout, args.scale,
                                      correct=not args.no_correct)
        step = interval / 64.0 if interval else 0.0
        print(f'  @{pk.offset:#08x} CT=0x{pk.ct:02x} '
              f'{"RING_START" if pk.ring_start else "normal   "} '
              f'LSN={pk.lsn:3d} FSA={pk.fsa:5d}({pk.fsa_deg:7.2f}deg) '
              f'LSA={pk.lsa:5d}({pk.lsa_deg:7.2f}deg) step={step:+.4f}deg '
              f'CS=0x{pk.cs:04x} {"OK" if pk.checksum_ok else "BAD"}')
        show = pts[:6]
        for ang, rng, q in show:
            r = 'inf' if math.isinf(rng) else f'{rng:.3f}m'
            print(f'      angle={ang:8.3f}deg  range={r:>8}  quality={q:3d}')

    # ---- assemble revolutions ---------------------------------------------
    print('\n== revolutions ==')
    revs = []
    cur = []
    last_interval = None
    for pk in packets:
        if not pk.checksum_ok:
            continue
        pts, interval = decode_packet(pk, auto_layout, args.scale,
                                      correct=not args.no_correct)
        if interval is None:
            interval = last_interval
        else:
            last_interval = interval
        if pk.ring_start and cur:
            revs.append(cur)
            cur = []
        cur.extend(pts)
    if cur:
        revs.append(cur)

    for i, rev in enumerate(revs[:args.revolutions]):
        valid = [(a, r, q) for a, r, q in rev if not math.isinf(r)]
        angs = [a for a, _r, _q in rev]
        print(f'  revolution {i}: {len(rev)} points, {len(valid)} valid, '
              f'angle {min(angs):.1f}..{max(angs):.1f} deg')
        if valid:
            rs = sorted(r for _a, r, _q in valid)
            print(f'      range min={rs[0]:.3f}m  median={rs[len(rs)//2]:.3f}m  '
                  f'max={rs[-1]:.3f}m')
            if args.histogram:
                hist = Counter(round(r, 1) for _a, r, _q in valid)
                for bucket in sorted(hist):
                    print(f'      {bucket:5.1f}m : {"#" * hist[bucket]} ({hist[bucket]})')
        if args.csv:
            with open(args.csv, 'w') as f:
                f.write('angle_deg,range_m,quality\n')
                for a, r, q in rev:
                    f.write(f'{a:.5f},{"inf" if math.isinf(r) else f"{r:.5f}"},{q}\n')
            print(f'      wrote {args.csv}')

    # ---- global statistics -------------------------------------------------
    all_pts = []
    last_interval = None
    for pk in packets:
        if not pk.checksum_ok:
            continue
        pts, interval = decode_packet(pk, auto_layout, args.scale,
                                      correct=not args.no_correct)
        if interval is None:
            interval = last_interval
        else:
            last_interval = interval
        all_pts.extend(pts)
    if all_pts:
        vals = [r for _a, r, _q in all_pts if not math.isinf(r)]
        print(f'\n== overall ==')
        print(f'  points={len(all_pts)} valid={len(vals)} '
              f'({100.0 * len(vals) / len(all_pts):.1f}%)')
        if vals:
            vals.sort()
            print(f'  range min={vals[0]:.3f} p10={vals[len(vals)//10]:.3f} '
                  f'median={vals[len(vals)//2]:.3f} p90={vals[9*len(vals)//10]:.3f} '
                  f'max={vals[-1]:.3f}  (scale={args.scale})')
        if args.histogram and vals:
            hist = Counter(round(r, 1) for r in vals)
            print('  histogram:')
            for bucket in sorted(hist):
                print(f'    {bucket:5.1f}m : {"#" * hist[bucket]} ({hist[bucket]})')

    # ---- angular structure -------------------------------------------------
    print('\n== angular structure ==')
    angs = sorted(a for a, _r, _q in all_pts)
    if angs:
        gaps = [angs[i + 1] - angs[i] for i in range(len(angs) - 1)]
        if gaps:
            gaps_sorted = sorted(gaps)
            print(f'  angle step: min={gaps_sorted[0]:.4f} '
                  f'median={gaps_sorted[len(gaps_sorted)//2]:.4f} '
                  f'max={gaps_sorted[-1]:.4f} deg')


if __name__ == '__main__':
    main()

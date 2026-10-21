#!/usr/bin/env python3
"""
lidar_profile.py -- deep analysis of a captured YDLIDAR (S4B) stream.

Uses the *verified* framing (header = 10 bytes, sample = [quality, dist_lo,
dist_hi], validated 100% against the vendor checksum) and reports:

  * raw distance value statistics (min/max/mode/top-N) -- the raw values are
    what the device actually sent, independent of any unit assumption,
  * a full revolution of points, rendered as an ASCII polar plot and as a
    table, so that shape problems (V shapes, multiple echoes, gaps) are
    visible,
  * range statistics for several candidate scale factors so that the correct
    unit can be chosen against the S4B spec (0.10 - 8.0 m).

Usage:
    python3 lidar_profile.py lidar_153600.bin [--scale 4000] [--plot]
"""

import argparse
import math
import struct
import sys
from collections import Counter

PH = 0x55AA
HEADER_LEN = 10


def parse(buf):
    """Yield dicts for every packet, with checksum validation."""
    i, n = 0, len(buf)
    while i < n - 1:
        if buf[i] == 0xAA and buf[i + 1] == 0x55:
            if i + HEADER_LEN > n:
                break
            ct, lsn = buf[i + 2], buf[i + 3]
            fsa, lsa, cs = struct.unpack('<HHH', buf[i + 4:i + 10])
            start = i + HEADER_LEN
            end = start + lsn * 3
            if end > n:
                break
            payload = buf[start:end]
            c = PH ^ fsa ^ (ct + (lsn << 8)) ^ lsa
            for k in range(0, len(payload), 3):
                c ^= payload[k]
                c ^= payload[k + 1] | (payload[k + 2] << 8)
            yield {
                'off': i, 'ct': ct, 'lsn': lsn, 'fsa': fsa, 'lsa': lsa,
                'cs': cs, 'ok': (c & 0xFFFF) == cs, 'payload': payload,
            }
            i = end
        else:
            i += 1


def angle_corr(dq2):
    d_mm = dq2 / 4.0
    if d_mm <= 0:
        return 0.0
    return math.atan(((21.8 * (155.3 - d_mm)) / 155.3) / d_mm) * 180.0 / math.pi


def decode(pk, scale, correct=True):
    lsn = pk['lsn']
    fsa = pk['fsa'] >> 1
    lsa = pk['lsa'] >> 1
    if lsn > 1:
        if lsa < fsa:
            interval = (360 * 64 + lsa - fsa) / (lsn - 1) if (
                fsa > 270 * 64 and lsa < 90 * 64) else None
        else:
            interval = (lsa - fsa) / (lsn - 1)
    else:
        interval = 0.0
    if interval is None:
        return [], None
    out = []
    p = pk['payload']
    for idx in range(lsn):
        q = p[idx * 3]
        dq2 = p[idx * 3 + 1] | (p[idx * 3 + 2] << 8)
        ang = (fsa + interval * idx) / 64.0
        if correct:
            ang += angle_corr(dq2)
        out.append((ang % 360.0, dq2, q))
    return out, interval / 64.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('file')
    ap.add_argument('--scale', type=float, default=4000.0)
    ap.add_argument('--no-correct', action='store_true')
    ap.add_argument('--plot', action='store_true')
    ap.add_argument('--revs', type=int, default=1)
    ap.add_argument('--raw-hist', action='store_true')
    args = ap.parse_args()

    buf = open(args.file, 'rb').read()
    packets = list(parse(buf))
    ok = [p for p in packets if p['ok']]
    print(f'file      : {args.file} ({len(buf)} bytes)')
    print(f'packets   : {len(packets)}  valid checksum: {len(ok)}')
    ct_hist = Counter(p['ct'] for p in packets)
    print(f'CT values : {dict(ct_hist)}')
    print(f'LSN values: {dict(Counter(p["lsn"] for p in packets))}')

    # ---- raw distance statistics (device truth, unit independent) ---------
    raws = []
    for pk in ok:
        p = pk['payload']
        for k in range(0, len(p), 3):
            raws.append(p[k + 1] | (p[k + 2] << 8))
    raws_sorted = sorted(raws)
    print(f'\n== raw distance values (n={len(raws)}) ==')
    print(f'  min    = {raws_sorted[0]}  (0x{raws_sorted[0]:04x})')
    print(f'  max    = {raws_sorted[-1]}  (0x{raws_sorted[-1]:04x})')
    q = lambda f: raws_sorted[int(f * (len(raws_sorted) - 1))]
    print(f'  p50={q(.5)}  p90={q(.9)}  p99={q(.99)}  p999={q(.999)}')
    top = Counter(raws).most_common(12)
    print('  most common raw values (these are usually the "no signal" '
          'sentinel and the dominant surfaces):')
    for v, c in top:
        print(f'    0x{v:04x} = {v:6d}   x{c:6d}   '
              f'/4000={v/4000:7.3f}m  /8000={v/8000:7.3f}m  /2000={v/2000:7.3f}m')
    if args.raw_hist:
        hist = Counter(v >> 8 for v in raws)
        print('  high byte histogram (0xNN -> count):')
        for k in sorted(hist):
            print(f'    0x{k:02x}xx : {hist[k]:6d}  '
                  f'({"#" * min(60, hist[k] // 200)})')

    # ---- scale comparison --------------------------------------------------
    print('\n== candidate scales ==')
    for scale in (2000.0, 4000.0, 8000.0):
        vals = [r / scale for r in raws]
        valid = [v for v in vals if 0.12 <= v <= 8.0]
        over8 = sum(1 for v in vals if v > 8.0)
        under = sum(1 for v in vals if 0 < v < 0.12)
        print(f'  /{int(scale):5d}: valid(0.12-8m)={len(valid):6d} '
              f'({100*len(valid)/len(vals):5.1f}%)  >8m={over8:6d}  '
              f'<0.12m={under:6d}  max={max(vals):.2f}m')

    # ---- revolutions -------------------------------------------------------
    revs = []
    cur = []
    last_interval = None
    ring_starts = 0
    for pk in ok:
        pts, interval = decode(pk, args.scale, not args.no_correct)
        if interval is None:
            interval = last_interval
        else:
            last_interval = interval
        if (pk['ct'] & 0x01) == 1:
            ring_starts += 1
            if cur:
                revs.append(cur)
            cur = []
        cur.extend(pts)
    if cur:
        revs.append(cur)
    print(f'\n== revolutions ==\n  ring-start packets: {ring_starts}   '
          f'assembled: {len(revs)}')

    for r, rev in enumerate(revs[:args.revs]):
        rev = sorted(rev)
        angs = [a for a, _d, _q in rev]
        print(f'\n-- revolution {r}: {len(rev)} points, '
              f'angle {angs[0]:.2f} .. {angs[-1]:.2f} deg')
        gaps = [angs[i + 1] - angs[i] for i in range(len(angs) - 1)]
        if gaps:
            gs = sorted(gaps)
            print(f'   angular step: min={gs[0]:.4f} med={gs[len(gs)//2]:.4f} '
                  f'max={gs[-1]:.4f} deg')
        valid = [(a, d, q) for a, d, q in rev if 0.12 <= d / args.scale <= 8.0]
        print(f'   valid points: {len(valid)}')
        if valid:
            rr = sorted(d / args.scale for _a, d, _q in valid)
            print(f'   range: min={rr[0]:.3f} med={rr[len(rr)//2]:.3f} '
                  f'max={rr[-1]:.3f} m')

        # ASCII polar plot (top half = front)
        if args.plot:
            W, H = 72, 24
            grid = [[' '] * W for _ in range(H)]
            maxr = max((d / args.scale for _a, d, _q in valid), default=1.0)
            for a, d, _q in valid:
                r = d / args.scale
                if r > maxr:
                    continue
                # angle 0 = up (front), clockwise to the right
                theta = math.radians(a)
                x = W / 2 + (r / maxr) * (W / 2 - 1) * math.sin(theta)
                y = H / 2 - (r / maxr) * (H / 2 - 1) * math.cos(theta)
                xi, yi = int(round(x)), int(round(y))
                if 0 <= xi < W and 0 <= yi < H:
                    grid[yi][xi] = '#' if grid[yi][xi] == ' ' else '+'
            print(f'   polar plot (0deg = up/front, max range {maxr:.2f}m):')
            for row in grid:
                print('   |' + ''.join(row) + '|')

        # table of the profile
        print('   profile (angle, raw, range):')
        step = max(1, len(rev) // 60)
        for a, d, q in rev[::step]:
            r = d / args.scale
            flag = '' if 0.12 <= r <= 8.0 else '  (invalid/sentinel)'
            print(f'     {a:8.3f} deg  raw=0x{d:04x} ({d:6d})  '
                  f'{r:7.3f} m  q={q:3d}{flag}')


if __name__ == '__main__':
    main()

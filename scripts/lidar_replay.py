#!/usr/bin/env python3
"""
lidar_replay.py -- replay a captured YDLIDAR stream through the *real*
parser used by the ROS 2 node and report/plot the result.

This is the offline regression test for the lidar pipeline: if the capture
contains a sane scene, the replay must produce sane ranges, a sane number of
points per revolution, and a sane angular step.

    python3 scripts/lidar_replay.py lidar_153600.bin
    python3 scripts/lidar_replay.py lidar_153600.bin --csv /tmp/scan.csv
    python3 scripts/lidar_replay.py lidar_153600.bin --scale 8000   # compare
"""

import argparse
import math
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(
    os.path.dirname(HERE), 'ros2_ws', 'src', 'lidar_scan_publisher'))

from lidar_scan_publisher.ydlidar_protocol import YdLidarParser  # noqa: E402


def ascii_plot(points, width=76, height=26):
    """Polar plot, 0 deg = up (front), clockwise to the right."""
    valid = [p for p in points if not math.isinf(p.rng)]
    if not valid:
        return '(no valid points)'
    maxr = max(p.rng for p in valid)
    grid = [[' '] * width for _ in range(height)]
    for p in valid:
        r = p.rng / maxr
        theta = math.radians(p.angle)
        x = width / 2 + r * (width / 2 - 1) * math.sin(theta)
        y = height / 2 - r * (height / 2 - 1) * math.cos(theta)
        xi, yi = int(round(x)), int(round(y))
        if 0 <= xi < width and 0 <= yi < height:
            grid[yi][xi] = '#' if grid[yi][xi] == ' ' else '+'
    out = []
    for row in grid:
        out.append('  |' + ''.join(row) + '|')
    return '\n'.join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('file')
    ap.add_argument('--scale', type=float, default=4000.0)
    ap.add_argument('--range-min', type=float, default=0.12)
    ap.add_argument('--range-max', type=float, default=8.0)
    ap.add_argument('--no-correct', action='store_true')
    ap.add_argument('--invert', action='store_true')
    ap.add_argument('--csv', help='write the first revolution as CSV')
    ap.add_argument('--plot', action='store_true')
    ap.add_argument('--all-revs', action='store_true')
    args = ap.parse_args()

    data = open(args.file, 'rb').read()
    parser = YdLidarParser(scale=args.scale, range_min=args.range_min,
                           range_max=args.range_max,
                           correct_angles=not args.no_correct,
                           invert=args.invert)
    revs = parser.feed(data)
    tail = parser.flush()
    if tail:
        revs.append(tail)

    st = parser.stats
    print(f'file      : {args.file} ({len(data)} bytes)')
    print(f'packets   : {st["packets"]}  bad checksum: {st["bad_checksum"]}  '
          f'bad header: {st["bad_header"]}')
    print(f'samples   : {st["samples"]}   revolutions: {len(revs)}  scale: /{args.scale:.0f}')

    sizes = [len(r) for r in revs]
    if sizes:
        print(f'points/rev: min={min(sizes)} max={max(sizes)} '
              f'median={sorted(sizes)[len(sizes)//2]}')

    revs_sorted = sorted(revs, key=len, reverse=True)
    chosen = revs_sorted if args.all_revs else revs_sorted[:1]
    for i, rev in enumerate(chosen):
        pts = sorted(rev, key=lambda p: p.angle)
        valid = [p for p in pts if not math.isinf(p.rng)]
        angs = [p.angle for p in pts]
        gaps = [angs[k + 1] - angs[k] for k in range(len(angs) - 1)]
        print(f'\n-- revolution {i}: {len(pts)} points, {len(valid)} valid, '
              f'angle {min(angs):.2f}..{max(angs):.2f} deg')
        if gaps:
            gs = sorted(gaps)
            print(f'   angular step: min={gs[0]:.4f} med={gs[len(gs)//2]:.4f} '
                  f'max={gs[-1]:.4f} deg')
        if valid:
            rr = sorted(p.rng for p in valid)
            print(f'   range: min={rr[0]:.3f} med={rr[len(rr)//2]:.3f} '
                  f'max={rr[-1]:.3f} m')
            hist = Counter(round(p.rng, 1) for p in valid)
            print('   histogram:')
            for bucket in sorted(hist):
                print(f'     {bucket:5.1f} m : {"#" * min(50, hist[bucket])} '
                      f'({hist[bucket]})')
        if args.plot:
            print(ascii_plot(pts))
        if args.csv and i == 0:
            with open(args.csv, 'w') as f:
                f.write('angle_deg,range_m,quality,raw\n')
                for p in pts:
                    r = 'inf' if math.isinf(p.rng) else f'{p.rng:.4f}'
                    f.write(f'{p.angle:.4f},{r},{int(p.quality)},{p.raw}\n')
            print(f'   wrote {args.csv}')


if __name__ == '__main__':
    main()

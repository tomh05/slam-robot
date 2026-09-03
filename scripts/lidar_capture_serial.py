#!/usr/bin/env python3
"""Capture raw bytes from an unknown serial lidar.

This is intentionally not ROS-specific. Use it before trying a ROS driver.

Examples:
  python3 -m pip install pyserial
  python3 scripts/lidar_capture_serial.py --list
  python3 scripts/lidar_capture_serial.py --port /dev/ttyUSB0 --baud 230400 --seconds 5 --out captures/lidar_230400.bin
  python3 scripts/lidar_capture_serial.py --port /dev/ttyUSB0 --scan-baud --seconds 3
"""

from __future__ import annotations

import argparse
import collections
import pathlib
import sys
import time

try:
    import serial
    import serial.tools.list_ports
except ImportError:  # pragma: no cover - dependency may not be installed yet
    print("pyserial is required. Install with: python3 -m pip install pyserial", file=sys.stderr)
    raise


DEFAULT_BAUDS = [
    8000,
    9600,
    19200,
    38400,
    57600,
    115200,
    128000,
    153600,
    158700,  # reported by MB_1R2T demo code / notebook notes
    230400,
    256000,
    460800,
    512000,
    921600,
]


def list_ports() -> None:
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("No serial ports found")
        return
    for p in ports:
        print(f"{p.device}\t{p.description}\tVID:PID={p.vid!s}:{p.pid!s}\tserial={p.serial_number}")


def capture(port: str, baud: int, seconds: float, out: pathlib.Path | None, quiet: bool = False) -> bytes:
    if not quiet:
        print(f"Opening {port} at {baud} baud for {seconds:.1f}s")
    data = bytearray()
    deadline = time.monotonic() + seconds
    with serial.Serial(port=port, baudrate=baud, timeout=0.05) as ser:
        # Clear stale bytes, then capture fresh data.
        ser.reset_input_buffer()
        while time.monotonic() < deadline:
            chunk = ser.read(4096)
            if chunk:
                data.extend(chunk)
    b = bytes(data)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b)
        if not quiet:
            print(f"Wrote {len(b)} bytes to {out}")
    return b


def hexdump(data: bytes, limit: int = 256) -> str:
    lines = []
    shown = data[:limit]
    for base in range(0, len(shown), 16):
        chunk = shown[base : base + 16]
        hx = " ".join(f"{x:02x}" for x in chunk)
        asc = "".join(chr(x) if 32 <= x < 127 else "." for x in chunk)
        lines.append(f"{base:08x}  {hx:<47}  |{asc}|")
    if len(data) > limit:
        lines.append(f"... {len(data) - limit} more bytes not shown")
    return "\n".join(lines)


def analyse(data: bytes) -> dict[str, object]:
    pairs = collections.Counter(zip(data, data[1:]))
    byte_counts = collections.Counter(data)
    return {
        "bytes": len(data),
        "aa55_count": pairs[(0xAA, 0x55)],
        "55aa_count": pairs[(0x55, 0xAA)],
        "a55a_count": pairs[(0xA5, 0x5A)],
        "zero_fraction": (byte_counts[0] / len(data)) if data else 0.0,
        "ff_fraction": (byte_counts[0xFF] / len(data)) if data else 0.0,
        "unique_bytes": len(byte_counts),
        "top_bytes": byte_counts.most_common(8),
    }


def print_analysis(data: bytes) -> None:
    stats = analyse(data)
    print("Analysis:")
    print(f"  bytes:       {stats['bytes']}")
    print(f"  AA 55:       {stats['aa55_count']}   (YDLIDAR scan packet header candidate)")
    print(f"  55 AA:       {stats['55aa_count']}")
    print(f"  A5 5A:       {stats['a55a_count']}   (YDLIDAR response sync candidate)")
    print(f"  unique:      {stats['unique_bytes']}")
    print(f"  zero frac:   {stats['zero_fraction']:.3f}")
    print(f"  FF frac:     {stats['ff_fraction']:.3f}")
    print(f"  top bytes:   {stats['top_bytes']}")
    if data:
        print("\nFirst bytes:")
        print(hexdump(data))


def scan_bauds(port: str, bauds: list[int], seconds: float) -> None:
    print(f"Scanning {port}; this will try {len(bauds)} baud rates")
    for baud in bauds:
        try:
            data = capture(port, baud, seconds, out=None, quiet=True)
            stats = analyse(data)
            print(
                f"{baud:>7}: bytes={stats['bytes']:<7} "
                f"AA55={stats['aa55_count']:<5} A55A={stats['a55a_count']:<5} "
                f"unique={stats['unique_bytes']:<3} zero={stats['zero_fraction']:.2f} ff={stats['ff_fraction']:.2f}"
            )
        except Exception as e:  # keep trying other rates
            print(f"{baud:>7}: ERROR {e}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="list serial ports and exit")
    parser.add_argument("--port", help="serial port, e.g. /dev/ttyUSB0 or /dev/serial/by-id/...")
    parser.add_argument("--baud", type=int, default=230400, help="baud rate for capture")
    parser.add_argument("--seconds", type=float, default=5.0, help="capture duration")
    parser.add_argument("--out", type=pathlib.Path, help="output binary capture path")
    parser.add_argument("--scan-baud", action="store_true", help="try common baud rates and print simple statistics")
    parser.add_argument("--bauds", type=str, help="comma-separated baud list for --scan-baud")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.list:
        list_ports()
        return 0
    if not args.port:
        print("--port is required unless using --list", file=sys.stderr)
        return 2
    if args.scan_baud:
        bauds = DEFAULT_BAUDS if not args.bauds else [int(x.strip()) for x in args.bauds.split(",") if x.strip()]
        scan_bauds(args.port, bauds, args.seconds)
        return 0
    data = capture(args.port, args.baud, args.seconds, args.out)
    print_analysis(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

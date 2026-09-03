#!/usr/bin/env python3
"""Watch Arduino Nano D7 / right encoder S1 activity.

This talks to the base-controller firmware over USB serial and repeatedly sends
`R`. With current firmware, the `R` response includes raw pin levels and edge
counters for LS1, LS2, RS1/D7, and RS2/D3.
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Optional, Tuple

try:
    import serial
except ImportError:  # pragma: no cover
    serial = None


DEFAULT_PORT = "/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0"


def write_line(ser, line: str) -> None:
    ser.write((line + "\n").encode("ascii"))
    ser.flush()


def parse_r_line(line: str) -> Optional[Tuple[int, int, int, int, int, Optional[int], Optional[int], Optional[int], Optional[int]]]:
    parts = line.split()
    if len(parts) < 6 or parts[0] != "R":
        return None
    try:
        millis = int(parts[1])
        ls1 = int(parts[2])
        ls2 = int(parts[3])
        rs1 = int(parts[4])
        rs2 = int(parts[5])
        if len(parts) >= 10:
            ls1_edges = int(parts[6])
            ls2_edges = int(parts[7])
            rs1_edges = int(parts[8])
            rs2_edges = int(parts[9])
        else:
            ls1_edges = ls2_edges = rs1_edges = rs2_edges = None
        return millis, ls1, ls2, rs1, rs2, ls1_edges, ls2_edges, rs1_edges, rs2_edges
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Watch D7/right-S1 signal activity from Arduino firmware")
    parser.add_argument("--port", default=DEFAULT_PORT, help=f"serial port, default: {DEFAULT_PORT}")
    parser.add_argument("--baud", type=int, default=115200, help="serial baud, default: 115200")
    parser.add_argument("--interval", type=float, default=0.1, help="seconds between R requests, default: 0.1")
    parser.add_argument("--duration", type=float, default=0.0, help="seconds to run; 0 means until Ctrl-C")
    args = parser.parse_args()

    if serial is None:
        print("ERROR: pyserial is not installed. On the Pi try: sudo apt install python3-serial", file=sys.stderr)
        return 2

    try:
        ser = serial.Serial(args.port, args.baud, timeout=0.05, write_timeout=0.5)
    except serial.SerialException as exc:
        print(f"ERROR: failed to open {args.port}: {exc}", file=sys.stderr)
        return 1

    with ser:
        print(f"Opened {args.port} at {args.baud}. Nano may reset; waiting briefly...")
        time.sleep(2.0)
        ser.reset_input_buffer()

        # Keep motor targets at zero and avoid Arduino command timeout side-effects.
        write_line(ser, "V 0 0")
        write_line(ser, "R")

        print("Watching RS1/D7. Rotate the right track slowly.")
        print("If D7 is receiving a signal, RS1/D7 edge count should increase and/or RS1 level should change.")
        print("Press Ctrl-C to stop.")

        start = time.monotonic()
        next_request = start
        next_zero = start + 0.2
        last_rs1_edges: Optional[int] = None
        last_rs1_level: Optional[int] = None
        latest_rs1_edges: Optional[int] = None
        latest_rs1_level: Optional[int] = None

        try:
            while True:
                now = time.monotonic()
                if args.duration > 0 and now - start >= args.duration:
                    break
                if now >= next_zero:
                    write_line(ser, "V 0 0")
                    next_zero = now + 0.2
                if now >= next_request:
                    write_line(ser, "R")
                    next_request = now + max(args.interval, 0.02)

                raw = ser.readline()
                if not raw:
                    continue
                line = raw.decode("ascii", errors="replace").strip()
                parsed = parse_r_line(line)
                if parsed is None:
                    if line and not line.startswith("E "):
                        print(line)
                    continue

                millis, ls1, ls2, rs1, rs2, ls1_edges, ls2_edges, rs1_edges, rs2_edges = parsed
                latest_rs1_level = rs1
                latest_rs1_edges = rs1_edges

                if rs1_edges is not None:
                    if last_rs1_edges is None:
                        delta = 0
                    else:
                        delta = rs1_edges - last_rs1_edges
                    last_rs1_edges = rs1_edges
                    print(
                        f"ms={millis:8d} RS1/D7={rs1} RS2/D3={rs2} "
                        f"RS1_edges={rs1_edges:6d} delta={delta:+4d} "
                        f"all_edges LS1={ls1_edges} LS2={ls2_edges} RS2={rs2_edges}"
                    )
                else:
                    changed = ""
                    if last_rs1_level is not None and rs1 != last_rs1_level:
                        changed = "  <-- D7 level changed"
                    last_rs1_level = rs1
                    print(f"ms={millis:8d} RS1/D7={rs1} RS2/D3={rs2}{changed}")

        except KeyboardInterrupt:
            print("\nStopping...")
        finally:
            if latest_rs1_edges is not None:
                print(f"Final RS1/D7 edge count: {latest_rs1_edges}")
            elif latest_rs1_level is not None:
                print(f"Final RS1/D7 level: {latest_rs1_level}")
            try:
                write_line(ser, "V 0 0")
                write_line(ser, "S")
            except serial.SerialException:
                pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

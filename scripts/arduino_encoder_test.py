#!/usr/bin/env python3
"""Small serial helper for Arduino Nano encoder bringup.

It keeps motor targets at zero, optionally zeros encoder counts, prints periodic
E status lines, and can request raw S1/S2 pin levels with the firmware's `R`
command.
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


DEFAULT_PORT = "/dev/arduino"


def parse_e_line(line: str) -> Optional[Tuple[int, int, int, int, int, int, int]]:
    parts = line.split()
    if len(parts) != 8 or parts[0] != "E":
        return None
    try:
        return tuple(int(p) for p in parts[1:8])  # type: ignore[return-value]
    except ValueError:
        return None


def write_line(ser, line: str) -> None:
    ser.write((line + "\n").encode("ascii"))
    ser.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description="Monitor Arduino encoder counts over USB serial")
    parser.add_argument("--port", default=DEFAULT_PORT, help=f"serial port, default: {DEFAULT_PORT}")
    parser.add_argument("--baud", type=int, default=115200, help="serial baud, default: 115200")
    parser.add_argument("--duration", type=float, default=0.0, help="seconds to run; 0 means until Ctrl-C")
    parser.add_argument("--print-hz", type=float, default=5.0, help="status print rate, default: 5 Hz")
    parser.add_argument("--raw-interval", type=float, default=1.0, help="seconds between raw pin requests; 0 disables")
    parser.add_argument("--zero-command-interval", type=float, default=0.2, help="seconds between safe V 0 0 commands; 0 disables")
    parser.add_argument("--no-zero", action="store_true", help="do not send Z to zero encoder counts at start")
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

        # Safe motor state. V 0 0 does not produce high-rate ACK spam.
        write_line(ser, "V 0 0")
        if not args.no_zero:
            write_line(ser, "Z")
        if args.raw_interval > 0:
            write_line(ser, "R")

        start = time.monotonic()
        next_print = start
        next_raw = start + max(args.raw_interval, 0.0)
        next_zero_command = start + max(args.zero_command_interval, 0.0)
        last_print_counts: Optional[Tuple[int, int]] = None
        latest_status: Optional[Tuple[int, int, int, int, int, int, int]] = None

        print("Spin one track/motor slowly. Both encoders now count in both directions:",
              "counts should increase when the motor is driven forward and decrease when driven backward.")
        print("Press Ctrl-C to stop. Motors are commanded to zero while this script runs.")

        try:
            while True:
                now = time.monotonic()
                if args.duration > 0 and now - start >= args.duration:
                    break

                if args.raw_interval > 0 and now >= next_raw:
                    write_line(ser, "R")
                    next_raw = now + args.raw_interval

                if args.zero_command_interval > 0 and now >= next_zero_command:
                    write_line(ser, "V 0 0")
                    next_zero_command = now + args.zero_command_interval

                raw = ser.readline()
                if raw:
                    line = raw.decode("ascii", errors="replace").strip()
                    if not line:
                        continue

                    parsed = parse_e_line(line)
                    if parsed is not None:
                        latest_status = parsed
                    elif line.startswith("R "):
                        parts = line.split()
                        if len(parts) >= 6:
                            message = (
                                f"raw pins: LS1={parts[2]} LS2={parts[3]} "
                                f"RS1={parts[4]} RS2={parts[5]}"
                            )
                            if len(parts) >= 10:
                                message += (
                                    f" edges: LS1={parts[6]} LS2={parts[7]} "
                                    f"RS1/D7={parts[8]} RS2/D3={parts[9]}"
                                )
                            print(message)
                        else:
                            print(line)
                    else:
                        print(line)

                if latest_status is not None and now >= next_print:
                    ms, left, right, left_tps, right_tps, left_pwm, right_pwm = latest_status
                    if last_print_counts is None:
                        dl = dr = 0
                    else:
                        dl = left - last_print_counts[0]
                        dr = right - last_print_counts[1]
                    last_print_counts = (left, right)
                    elapsed = now - start
                    print(
                        f"t={elapsed:6.2f}s arduino_ms={ms:10d} "
                        f"L={left:8d} dL={dl:+5d} tps={left_tps:+5d} "
                        f"R={right:8d} dR={dr:+5d} tps={right_tps:+5d} "
                        f"pwm=({left_pwm:+4d},{right_pwm:+4d})"
                    )
                    next_print = now + (1.0 / args.print_hz if args.print_hz > 0 else 0.2)

        except KeyboardInterrupt:
            print("\nStopping...")
        finally:
            if latest_status is not None:
                _ms, left, right, _left_tps, _right_tps, _left_pwm, _right_pwm = latest_status
                print(f"Final counts: L={left} R={right}")
            try:
                write_line(ser, "V 0 0")
                write_line(ser, "S")
            except serial.SerialException:
                pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

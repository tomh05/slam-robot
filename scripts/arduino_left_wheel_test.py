#!/usr/bin/env python3
"""Move only the left motor briefly and report encoder position changes."""
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
Status = Tuple[int, int, int, int, int, int, int]
def parse_status(line: str) -> Optional[Status]:
    parts = line.split()
    if len(parts) != 8 or parts[0] != "E":
        return None
    try:
        return tuple(int(value) for value in parts[1:8])  # type: ignore[return-value]
    except ValueError:
        return None
def write_line(ser, line: str) -> None:
    ser.write((line + "\n").encode("ascii"))
    ser.flush()
def read_status(ser, timeout: float) -> Optional[Status]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        raw = ser.readline()
        if raw:
            line = raw.decode("ascii", errors="replace").strip()
            status = parse_status(line)
            if status is not None:
                return status
    return None
def print_status(label: str, status: Status) -> None:
    millis, left, right, left_tps, right_tps, left_pwm, right_pwm = status
    print(
        f"{label}: millis={millis} left_position={left} "
        f"right_position={right} left_tps={left_tps} right_tps={right_tps} "
        f"pwm=({left_pwm}, {right_pwm})"
    )
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a short left-wheel encoder test over USB serial"
    )
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument(
        "--speed",
        type=int,
        default=20,
        help="left target speed in ticks/sec; default: 20",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=3.0,
        help="seconds to drive; default: 3",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="skip the move confirmation prompt",
    )
    args = parser.parse_args()
    if args.speed <= 0:
        parser.error("--speed must be greater than zero")
    if args.duration <= 0:
        parser.error("--duration must be greater than zero")
    if serial is None:
        print(
            "ERROR: pyserial is not installed. Install it with: "
            "sudo apt install python3-serial",
            file=sys.stderr,
        )
        return 2
    if not args.yes:
        print(
            f"This will move ONLY the left wheel at {args.speed} ticks/sec "
            f"for {args.duration:.1f} seconds."
        )
        try:
            input("Make sure the robot is safely supported, then press Enter to continue...")
        except EOFError:
            print("Cancelled.", file=sys.stderr)
            return 1
    ser = None
    try:
        ser = serial.Serial(args.port, args.baud, timeout=0.05, write_timeout=0.5)
        print(f"Opened {args.port} at {args.baud}; waiting for Nano reset...")
        time.sleep(2.0)
        ser.reset_input_buffer()
        # Stop any previous command before taking the baseline.
        write_line(ser, "S")
        write_line(ser, "Z")
        baseline = read_status(ser, timeout=2.0)
        if baseline is None:
            print("ERROR: no E status received after zeroing the encoder.", file=sys.stderr)
            return 1
        print_status("Baseline", baseline)
        print("Driving left wheel...")
        end_time = time.monotonic() + args.duration
        latest = baseline
        while time.monotonic() < end_time:
            # The firmware's command watchdog is 400 ms, so refresh V regularly.
            write_line(ser, f"V {args.speed} 0")
            status = read_status(ser, timeout=0.15)
            if status is not None:
                latest = status
        # Stop immediately and collect one final status report.
        write_line(ser, "V 0 0")
        write_line(ser, "S")
        final = read_status(ser, timeout=1.0) or latest
        print_status("Final", final)
        left_ticks = final[1] - baseline[1]
        right_ticks = final[2] - baseline[2]
        print(f"Position change: left={left_ticks:+d} ticks, right={right_ticks:+d} ticks")
        print(f"Encoder ticks reported: left={left_ticks:+d}, right={right_ticks:+d}")
        return 0
    except serial.SerialException as exc:
        print(f"ERROR: serial communication failed: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted; stopping motors.", file=sys.stderr)
        return 130
    finally:
        if ser is not None:
            try:
                write_line(ser, "V 0 0")
                write_line(ser, "S")
            except serial.SerialException:
                pass
            ser.close()
if __name__ == "__main__":
    raise SystemExit(main())

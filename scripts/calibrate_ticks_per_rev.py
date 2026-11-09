#!/usr/bin/env python3
"""Bench calibration helper: measure encoder ticks per wheel revolution.

Usage:
  1. Lift the robot (or otherwise allow tracks/wheels to spin freely).
  2. Run this script on the Pi connected to the Arduino over USB.
  3. It zeros encoder counts, then prompts you to rotate each output wheel
     by a known number of revolutions (by hand, slowly) in the forward direction.
  4. It reports ticks/rev for each side.

The Arduino firmware reports signed positions in the E line:
  E <millis> <left_position> <right_position> <left_tps> <right_tps> <left_pwm> <right_pwm>

Motors are commanded to zero (V 0 0) while running for safety.
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


def write_line(ser: serial.Serial, line: str) -> None:
    ser.write((line + "\n").encode("ascii"))
    ser.flush()


def read_latest_status(ser: serial.Serial, timeout_s: float = 0.3) -> Optional[Tuple[int, int, int, int, int, int, int]]:
    deadline = time.monotonic() + timeout_s
    latest = None
    while time.monotonic() < deadline:
        raw = ser.readline()
        if not raw:
            continue
        line = raw.decode("ascii", errors="replace").strip()
        parsed = parse_e_line(line)
        if parsed is not None:
            latest = parsed
    return latest


def wait_for_status(ser: serial.Serial, timeout_s: float = 5.0) -> Optional[Tuple[int, int, int, int, int, int, int]]:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        status = read_latest_status(ser, timeout_s=0.5)
        if status is not None:
            return status
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure encoder ticks per wheel revolution (bench test)")
    parser.add_argument("--port", default=DEFAULT_PORT, help=f"serial port (default: {DEFAULT_PORT})")
    parser.add_argument("--baud", type=int, default=115200, help="serial baud (default: 115200)")
    parser.add_argument("--revs", type=float, default=1.0, help="number of wheel revolutions to rotate (default: 1.0)")
    parser.add_argument("--wheel-radius-m", type=float, default=0.029, help="wheel radius in meters for ticks_per_meter calc (default: 0.029)")
    args = parser.parse_args()

    if serial is None:
        print("ERROR: pyserial is not installed. Try: sudo apt install python3-serial", file=sys.stderr)
        return 2

    try:
        ser = serial.Serial(args.port, args.baud, timeout=0.05, write_timeout=0.5)
    except serial.SerialException as exc:
        print(f"ERROR: failed to open {args.port}: {exc}", file=sys.stderr)
        return 1

    with ser:
        print(f"Opened {args.port} @ {args.baud}. Waiting for Arduino reset...")
        time.sleep(2.0)
        ser.reset_input_buffer()

        # Safety: keep motors at zero.
        write_line(ser, "V 0 0")

        status = wait_for_status(ser)
        if status is None:
            print("ERROR: no E status received from Arduino. Check port/firmware.", file=sys.stderr)
            return 1

        print("\nMotors are commanded to zero. Rotate wheels BY HAND (slowly, forward).")
        print(f"Target: {args.revs:g} revolution(s) per side.\n")

        def measure_side(side: str, index: int) -> Optional[int]:
            # Zero counts
            write_line(ser, "Z")
            time.sleep(0.2)
            ser.reset_input_buffer()
            write_line(ser, "V 0 0")
            status0 = wait_for_status(ser)
            if status0 is None:
                print(f"  ERROR: could not read status for {side} side.")
                return None
            _, l0, r0, *_ = status0
            start_pos = l0 if index == 0 else r0

            input(f"  [{side}] Rotate the {side} output wheel FORWARD {args.revs:g} rev(s), then press Enter... ")

            # Keep sending safe zero command while reading
            for _ in range(3):
                write_line(ser, "V 0 0")
                time.sleep(0.05)
            status1 = wait_for_status(ser, timeout_s=2.0)
            if status1 is None:
                print(f"  ERROR: could not read status after rotating {side} side.")
                return None
            _, l1, r1, *_ = status1
            end_pos = l1 if index == 0 else r1
            delta = end_pos - start_pos
            print(f"  [{side}] position: {start_pos} -> {end_pos}  (delta = {delta} ticks)")
            return delta

        left_ticks = measure_side("LEFT", 0)
        right_ticks = measure_side("RIGHT", 1)

        # Stop/cleanup
        try:
            write_line(ser, "V 0 0")
            write_line(ser, "S")
        except serial.SerialException:
            pass

        print("\n--- Results ---")
        circumference = 2.0 * 3.141592653589793 * args.wheel_radius_m
        if left_ticks is not None and args.revs != 0:
            tpr = left_ticks / args.revs
            tpm = tpr / circumference if circumference > 0 else 0.0
            print(f"LEFT:  ticks/rev = {tpr:.1f}   ticks/m = {tpm:.1f}  (wheel_radius_m={args.wheel_radius_m})")
        if right_ticks is not None and args.revs != 0:
            tpr = right_ticks / args.revs
            tpm = tpr / circumference if circumference > 0 else 0.0
            print(f"RIGHT: ticks/rev = {tpr:.1f}   ticks/m = {tpm:.1f}  (wheel_radius_m={args.wheel_radius_m})")

        print("\nUpdate ros2_ws/src/slam_robot_base/config/arduino_base.yaml with these values,")
        print("then restart arduino_base_node and re-test straight-line motion.")
        print("Note: rotate in the robot's FORWARD direction. If a delta is negative, check motor/encoder sign.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

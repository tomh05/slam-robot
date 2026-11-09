#!/usr/bin/env python3
"""Bench calibration helper: measure encoder ticks per wheel revolution.

Usage:
  1. Lift the robot (or otherwise allow tracks/wheels to spin freely).
  2. Run this script on the Pi connected to the Arduino over USB.
  3. It reads raw encoder edge counts, then prompts you to rotate each output
     wheel by a known number of revolutions (by hand, slowly) in the forward
     direction.
  4. It reports ticks/rev for each side.

Note: The Arduino firmware only accumulates signed E-line positions when motors
are actively commanded (to avoid counting passive motion). For hand-spun bench
tests we use the R (raw) diagnostic line's S1 edge counters instead:
  R <ms> <LS1> <LS2> <RS1> <RS2> <LS1_edges> <LS2_edges> <RS1_edges> <RS2_edges>
Edge counters count both transitions; ticks (x1, rising edges) are estimated as
edges/2. Rotate in the forward direction for consistency.

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


def parse_r_line(line: str) -> Optional[Tuple[int, int, int, int, int]]:
    """Parse R line: R ms LS1 LS2 RS1 RS2 LS1_edges LS2_edges RS1_edges RS2_edges"""
    parts = line.split()
    if len(parts) < 10 or parts[0] != "R":
        return None
    try:
        ms = int(parts[1])
        ls1_edges = int(parts[6])
        ls2_edges = int(parts[7])
        rs1_edges = int(parts[8])
        rs2_edges = int(parts[9])
        return ms, ls1_edges, ls2_edges, rs1_edges, rs2_edges
    except ValueError:
        return None


def write_line(ser: serial.Serial, line: str) -> None:
    ser.write((line + "\n").encode("ascii"))
    ser.flush()


def read_latest_edges(ser: serial.Serial, timeout_s: float = 1.0) -> Optional[Tuple[int, int, int, int, int]]:
    """Return latest (ms, ls1_edges, ls2_edges, rs1_edges, rs2_edges) from R lines."""
    deadline = time.monotonic() + timeout_s
    latest = None
    while time.monotonic() < deadline:
        write_line(ser, "R")
        time.sleep(0.05)
        # Drain a few lines to catch the response
        drain_until = time.monotonic() + 0.2
        while time.monotonic() < drain_until:
            raw = ser.readline()
            if not raw:
                continue
            line = raw.decode("ascii", errors="replace").strip()
            parsed = parse_r_line(line)
            if parsed is not None:
                latest = parsed
    return latest


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
        for _ in range(3):
            write_line(ser, "V 0 0")
            time.sleep(0.05)

        edges0 = read_latest_edges(ser, timeout_s=3.0)
        if edges0 is None:
            print("ERROR: no R (raw) response from Arduino. Check port/firmware (needs R command support).", file=sys.stderr)
            return 1

        print("\nMotors are commanded to zero. Rotate wheels BY HAND (slowly, forward).")
        print("Using R-line S1 edge counts (edges/2 ≈ ticks) because E positions don't update while stopped.")
        print(f"Target: {args.revs:g} revolution(s) per side.\n")

        def measure_side(side: str, edge_index: int) -> Optional[float]:
            # edge_index: 1 = ls1_edges, 3 = rs1_edges in (ms, ls1, ls2, rs1, rs2)
            baseline = read_latest_edges(ser, timeout_s=2.0)
            if baseline is None:
                print(f"  ERROR: could not read raw edges for {side} side.")
                return None
            start_edges = baseline[edge_index]
            start_other = baseline[3 if edge_index == 1 else 1]

            input(f"  [{side}] Rotate the {side} output wheel FORWARD {args.revs:g} rev(s), then press Enter... ")

            for _ in range(3):
                write_line(ser, "V 0 0")
                time.sleep(0.05)
            after = read_latest_edges(ser, timeout_s=2.0)
            if after is None:
                print(f"  ERROR: could not read raw edges after rotating {side} side.")
                return None
            end_edges = after[edge_index]
            end_other = after[3 if edge_index == 1 else 1]
            delta_edges = end_edges - start_edges
            other_delta = end_other - start_other
            ticks_est = delta_edges / 2.0
            print(
                f"  [{side}] S1 edges: {start_edges} -> {end_edges} (delta={delta_edges}, est. ticks={ticks_est:.1f})"
                f"  [other side moved {other_delta} edges; keep it still]"
            )
            return ticks_est

        left_ticks = measure_side("LEFT", 1)
        right_ticks = measure_side("RIGHT", 3)

        # Stop/cleanup
        try:
            write_line(ser, "V 0 0")
            write_line(ser, "S")
        except serial.SerialException:
            pass

        print("\n--- Results (estimated from S1 edges/2) ---")
        circumference = 2.0 * 3.141592653589793 * args.wheel_radius_m
        if left_ticks is not None and args.revs != 0:
            tpr = left_ticks / args.revs
            tpm = tpr / circumference if circumference > 0 else 0.0
            print(f"LEFT:  ticks/rev ≈ {tpr:.1f}   ticks/m ≈ {tpm:.1f}  (wheel_radius_m={args.wheel_radius_m})")
        if right_ticks is not None and args.revs != 0:
            tpr = right_ticks / args.revs
            tpm = tpr / circumference if circumference > 0 else 0.0
            print(f"RIGHT: ticks/rev ≈ {tpr:.1f}   ticks/m ≈ {tpm:.1f}  (wheel_radius_m={args.wheel_radius_m})")

        print("\nUpdate ros2_ws/src/slam_robot_base/config/arduino_base.yaml with these values")
        print("(use left/right_ticks_per_rev or left/right_ticks_per_meter), then restart")
        print("arduino_base_node and re-test straight-line motion.")
        print("Tip: rotate in the robot's FORWARD direction; do 5-10 revs for better accuracy.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

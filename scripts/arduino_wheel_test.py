#!/usr/bin/env python3
"""Interactive wheel test over USB serial."""
from __future__ import annotations
import argparse
import sys
import time
import select
import termios
import tty
from typing import Optional, Tuple
try:
    import serial
except ImportError:  # pragma: no cover
    serial = None

DEFAULT_PORT = "/dev/arduino"
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


def print_controls() -> None:
    print("\nControls:")
    print("  q - left wheel forward")
    print("  a - left wheel backward")
    print("  w - both wheels forward")
    print("  s - both wheels backward")
    print("  e - right wheel forward")
    print("  d - right wheel backward")
    print("  space/any other key or 'x' - stop")
    print("  Ctrl+C - exit")
    print("\nPress a key to command movement (looping, no auto-exit)...\n")


def get_key(timeout: float = 0.01) -> Optional[str]:
    if select.select([sys.stdin], [], [], timeout)[0]:
        ch = sys.stdin.read(1)
        if not ch:
            return None
        # Handle Ctrl+C
        if ch == '\x03':
            raise KeyboardInterrupt()
        if ch == '\x04':  # Ctrl+D
            raise EOFError()
        return ch.lower()
    return None


def drive_for_duration(ser, left_tps: int, right_tps: int, duration: float, speed_label: str = "") -> None:
    if speed_label:
        print(f"Driving {speed_label} (L:{left_tps}, R:{right_tps}) for {duration:.1f}s...")
    end_time = time.monotonic() + duration
    latest = None
    while time.monotonic() < end_time:
        # Refresh command regularly for watchdog
        write_line(ser, f"V {left_tps} {right_tps}")
        status = read_status(ser, timeout=0.05)
        if status is not None:
            latest = status
        # Check for keypress to interrupt/change command
        key = get_key(0.001)
        if key is not None and key != ' ':
            # If user presses a command key, we'll break and let main loop handle it
            # But we need to signal - easier to just break
            break
    # Stop
    write_line(ser, "V 0 0")
    write_line(ser, "S")
    time.sleep(0.05)
    final = read_status(ser, timeout=0.3) or latest
    if final is not None and speed_label:
        print_status("  Status", final)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Interactive wheel test over USB serial"
    )
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument(
        "--speed",
        type=int,
        default=20,
        help="target speed in ticks/sec; default: 20",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=1.0,
        help="seconds to drive per command; default: 1.0",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="skip the confirmation prompt",
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
            f"This will drive wheels at {args.speed} ticks/sec "
            f"for {args.duration:.1f} seconds per command."
        )
        try:
            input("Make sure the robot is safely supported, then press Enter to continue...")
        except EOFError:
            print("Cancelled.", file=sys.stderr)
            return 1

    ser = None
    old_settings = None
    try:
        ser = serial.Serial(args.port, args.baud, timeout=0.05, write_timeout=0.5)
        print(f"Opened {args.port} at {args.baud}; waiting for Nano reset...")
        time.sleep(2.0)
        ser.reset_input_buffer()
        # Stop any previous command
        write_line(ser, "S")
        write_line(ser, "Z")
        baseline = read_status(ser, timeout=2.0)
        if baseline is None:
            print("ERROR: no E status received after zeroing the encoder.", file=sys.stderr)
            return 1
        print_status("Baseline", baseline)

        # Set up raw terminal for key input
        try:
            old_settings = termios.tcgetattr(sys.stdin)
            tty.setraw(sys.stdin.fileno())
        except Exception:
            print("Warning: Could not set raw terminal mode. Falling back to line-based input.", file=sys.stderr)
            old_settings = None

        print_controls()

        try:
            while True:
                key = get_key(0.5)
                if key is None:
                    continue
                if key == 'q':
                    # left forward
                    drive_for_duration(ser, args.speed, 0, args.duration, "left wheel forward")
                elif key == 'a':
                    # left backward
                    drive_for_duration(ser, -args.speed, 0, args.duration, "left wheel backward")
                elif key == 'w':
                    # both forward
                    drive_for_duration(ser, args.speed, args.speed, args.duration, "both wheels forward")
                elif key == 's':
                    # both backward
                    drive_for_duration(ser, -args.speed, -args.speed, args.duration, "both wheels backward")
                elif key == 'e':
                    # right forward
                    drive_for_duration(ser, 0, args.speed, args.duration, "right wheel forward")
                elif key == 'd':
                    # right backward
                    drive_for_duration(ser, 0, -args.speed, args.duration, "right wheel backward")
                elif key == 'x' or key == ' ':
                    write_line(ser, "V 0 0")
                    write_line(ser, "S")
                    print("Stopped.")
                else:
                    # Unknown key, just show controls reminder
                    print_controls()
        except KeyboardInterrupt:
            print("\n\nInterrupted; stopping motors.")
            return 130
        except EOFError:
            print("\n\nEOF; stopping motors.")
            return 0

    except serial.SerialException as exc:
        print(f"ERROR: serial communication failed: {exc}", file=sys.stderr)
        return 1
    finally:
        if old_settings is not None:
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            except Exception:
                pass
        if ser is not None:
            try:
                write_line(ser, "V 0 0")
                write_line(ser, "S")
            except Exception:
                pass
            ser.close()


if __name__ == "__main__":
    raise SystemExit(main())

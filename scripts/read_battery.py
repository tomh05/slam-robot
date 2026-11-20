#!/usr/bin/env python3
"""
Read battery/supply voltage from the Arduino Nano base controller.

The Arduino firmware responds to 'B\n' with:
  B <millis> <source> <adc_raw> <v_supply_mV>
  source: 0=unknown, 1=battery, 2=dc_external

Usage:
  python3 scripts/read_battery.py [--port PORT] [--baud BAUD]
"""

import argparse
import sys
import time

try:
    import serial
except ImportError:
    print("Error: pyserial not installed. Install with: pip install pyserial", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description='Read battery status from Arduino')
    parser.add_argument('--port', default='/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0',
                        help='Serial port (default: /dev/serial/by-id/usb-1a86_USB_Serial-if00-port0)')
    parser.add_argument('--baud', type=int, default=115200, help='Baud rate (default: 115200)')
    parser.add_argument('--poll', action='store_true', help='Continuously poll every 2 seconds')
    args = parser.parse_args()

    try:
        ser = serial.Serial(args.port, args.baud, timeout=1.0, write_timeout=1.0)
    except serial.SerialException as e:
        print(f"Failed to open {args.port}: {e}", file=sys.stderr)
        sys.exit(1)

    # Give Arduino time to reset after serial open
    time.sleep(2.0)
    ser.reset_input_buffer()

    def read_battery():
        ser.write(b'B\n')
        ser.flush()
        line = ser.readline().decode('ascii', errors='replace').strip()
        if not line:
            return None
        if not line.startswith('B '):
            print(f"Unexpected response: {line}")
            return None
        parts = line.split()
        if len(parts) != 5:
            print(f"Bad B line field count: {line}")
            return None
        try:
            millis = int(parts[1])
            source = int(parts[2])
            adc_raw = int(parts[3])
            supply_mv = int(parts[4])
            return millis, source, adc_raw, supply_mv
        except ValueError:
            print(f"Bad B line values: {line}")
            return None

    source_names = {0: 'unknown', 1: 'battery (2S Li-ion)', 2: 'DC external'}

    try:
        while True:
            result = read_battery()
            if result:
                millis, source, adc_raw, supply_mv = result
                voltage_v = supply_mv / 1000.0
                print(f"Voltage: {voltage_v:.2f} V  |  ADC: {adc_raw}  |  Source: {source_names.get(source, 'invalid')}  |  Arduino ms: {millis}")
            else:
                print("No response (timeout or bad data)")

            if not args.poll:
                break
            time.sleep(2.0)
    except KeyboardInterrupt:
        pass
    finally:
        ser.close()


if __name__ == '__main__':
    main()
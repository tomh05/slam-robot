import time
import serial
import sys
while True:
    try:
        ser = serial.Serial('/dev/ttyUSB0', 153600, timeout=0.1)
        print(f"{time.time():.2f} Port opened successfully")
        ser.close()
    except serial.SerialException as e:
        print(f"{time.time():.2f} Port not available: {e}")
    time.sleep(0.5)

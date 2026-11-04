# Serial Port Setup (udev rules)

This robot uses two identical CH340 USB-serial adapters (same VID:PID), so `/dev/ttyUSB*` numbers can swap between boots/plugs. Use udev rules bound to physical USB ports for stable names.

## Current mapping (on the Pi)

As discovered via `dmesg` and `udevadm`:
- `ttyUSB0` on physical port `1-1.2:1.0` → Lidar
- `ttyUSB1` on physical port `1-1.4:1.0` → Arduino Nano

With the rule below, these are symlinked as:
- `/dev/lidar` → lidar
- `/dev/arduino` → Arduino Nano

## Create the udev rule

On the Raspberry Pi:
```bash
sudo tee /etc/udev/rules.d/99-robot-serial.rules > /dev/null << 'EOF'
SUBSYSTEM=="tty", KERNELS=="1-1.4:1.0", SYMLINK+="arduino", MODE="0666", GROUP="dialout"
SUBSYSTEM=="tty", KERNELS=="1-1.2:1.0", SYMLINK+="lidar", MODE="0666", GROUP="dialout"
EOF

sudo udevadm control --reload-rules && sudo udevadm trigger
```

Verify:
```bash
ls -la /dev/arduino /dev/lidar
```

## Re-identifying if ports change

If you replug devices to different USB ports/hubs:
1. Plug in both devices and check which is which:
```bash
ls /dev/ttyUSB*
sudo dmesg | grep -B1 -A6 'ttyUSB'
udevadm info -a -n /dev/ttyUSB0 | grep KERNELS | head -1
udevadm info -a -n /dev/ttyUSB1 | grep KERNELS | head -1
```
2. Unplug one device (e.g. lidar) and see which `ttyUSB*` remains to identify the other
3. Update the rule with the correct `KERNELS=="..."` for each physical port and reload udev

## Usage in this repo

- Arduino upload: `scripts/upload_arduino.sh` uses `-p /dev/arduino`
- Robot bringup: `scripts/start_robot_local.sh` defaults `LIDAR_PORT` to `/dev/lidar` (overridable via env var)
- Many other scripts/docs may still reference `/dev/ttyUSB0/1` - prefer the named symlinks above

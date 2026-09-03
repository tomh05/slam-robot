# Hardware Inventory Template

Fill this file in as parts are identified. Photos of labels, connectors, and wiring are very useful.

## 1. Raspberry Pi

- Model: Raspberry Pi 4 Model B Rev 1.5
- RAM: 2 GB class; OS reports 1.8 GiB usable
- Storage card size/type: 16 GB microSD; OS sees `mmcblk0` as 14.4G with 512M FAT boot partition and 13.9G ext4 root partition
- Power supply/regulator: unknown; currently powered sufficiently for Wi-Fi/SSH/ROS install
- OS image: Ubuntu Server 24.04.4 LTS arm64 Raspberry Pi preinstalled image; kernel `6.8.0-1047-raspi`
- Hostname: `slamrobot`
- SSH user: `ubuntu`
- Notes: current home-network IP is `192.168.1.46`; `slamrobot.local` works via Avahi after bootstrap; ROS 2 Jazzy minimal bootstrap completed; ROS_DOMAIN_ID=42

Useful commands after boot:

```bash
cat /proc/device-tree/model && echo
free -h
lsblk
uname -a
```

## 2. Lidar / laser range finder

- Manufacturer: unknown; commonly referenced as MB_1R2T / factory-test lidar
- Model: likely MB_1R2T or compatible
- Interface: direct UART serial output according to seller/community code
- Connector: 8P JST-PH / 2.0 mm pitch; screenshot labels power positive, serial output, power negative, speed control 0-5 V
- Supply voltage: 5 V according to seller
- Current requirement: unknown
- Serial baud rate: likely 158700 or 153600; test both
- Scan frequency: unknown; community code assumes roughly 0.2 s scan time initially
- Range min/max: community ROS 1 code uses 0.11 m to 8.0 m
- Existing labels/markings: main MCU reportedly STM32F302C8T6
- Linux device path: N/A until connected through USB-UART
- USB VID/PID: N/A until connected through USB-UART
- ROS 2 driver candidate: port MB_1R2T community parser to ROS 2; optionally test `YDLIDAR/ydlidar_ros2_driver`
- Notes: user has the lidar physically available and has a USB-to-TTL serial adapter for capture. No additional helpful labels/markings beyond previous notes. See [`lidar-module-notes.md`](lidar-module-notes.md) and [`lidar-mb-1r2t-ros2-port.md`](lidar-mb-1r2t-ros2-port.md)

Useful commands:

```bash
lsusb
ls -l /dev/serial/by-id/
dmesg | tail -100
```

Mounting:

- Frame name: `lidar_link`
- Position relative to `base_link`:
  - x forward, metres: 0.0 provisional; assume centred until mount is known
  - y left, metres: 0.0 provisional; assume centred until mount is known
  - z up, metres: provisional lidar scan plane height is 0.10 m above ground; relative-to-`base_link` value depends on final frame convention/model
- Orientation relative to `base_link`:
  - roll: 0.0 provisional
  - pitch: 0.0 provisional
  - yaw: 0.0 provisional

## 3. Chassis and tracks

- Chassis kit/model: tracked chassis from old AliExpress link <https://www.aliexpress.com/item/32800078967.html>
- Track layout: two tracks, left and right; each track has three wheels, only one driven.
- Driven wheel arrangement: left track rear wheel is driven; right track front wheel is driven.
- Track inner gap, m: 0.113 measured
- Track width, m: 0.042 measured
- Track separation, centre-to-centre, m: 0.155 measured and confirmed
- Overall outside track width, m: 0.197 measured/derived from 0.113 m inner gap + 2 * 0.042 m track width
- Overall robot footprint, m: 0.185 long x 0.204 wide measured
- Wheel diameter including track, m: 0.058 measured
- Effective drive sprocket/wheel radius, m: 0.029 measured initial value; calibrate by floor-distance roll test
- Track contact length, m: 0.127 measured as front-wheel-centre to back-wheel-centre distance
- Centre platform underside height above ground, m: 0.043 measured
- Assumed centre platform size, m: 0.170 long x 0.095 wide x 0.003 thick; not built yet
- Robot mass with battery, kg: unknown; use 0.6 kg as provisional planning figure until weighed
- Approx max safe speed, m/s: 0.2 m/s provisional conservative indoor limit
- Notes: geometric measurements were taken on the robot on 2026-07-30. Odometry still needs effective wheel radius/ticks-per-metre and effective skid-steer track separation calibration on the floor.

Coordinate convention:

- `base_link` x axis points forward.
- `base_link` y axis points left.
- `base_link` z axis points up.
- Origin should usually be near the centre of rotation on the floor projection.

## 4. Motors

Left motor:

- Manufacturer/model: unlabelled geared motor with hall sensors; likely same family as old 9 V motor notes/spec link <https://gitnova.com/#/Robot/Engine/9vMotor/9vmotor>
- Rated voltage: unknown; suspect 9 V, treat as provisional
- Stall/current rating: unknown; must measure/estimate before final driver/battery choice
- Gear ratio: unknown
- Wires/connectors: M+, M-, GND, VCC, S1, S2 confirmed by user
- Notes: left/right motors are identical; no useful labels visible

Right motor:

- Manufacturer/model: unlabelled geared motor with hall sensors; likely same family as old 9 V motor notes/spec link <https://gitnova.com/#/Robot/Engine/9vMotor/9vmotor>
- Rated voltage: unknown; suspect 9 V, treat as provisional
- Stall/current rating: unknown; must measure/estimate before final driver/battery choice
- Gear ratio: unknown
- Wires/connectors: M+, M-, GND, VCC, S1, S2 confirmed by user
- Notes: left/right motors are identical; no useful labels visible

## 5. Encoders

Left encoder:

- Type: hall-effect, single-channel tachometer (only S2 used for counting after 2026-07-30 decision)
- Voltage level: 5 V from Arduino Nano
- Pullups: Arduino internal `INPUT_PULLUP` enabled in firmware
- Counts per output shaft revolution after gearbox: ~224 counts/rev (both directions)
- Connected pins, matching discovered existing-board pinout:
  - S1: Arduino D4, retained for raw pin debugging only (not used for direction)
  - S2: Arduino D2 / INT0, counted channel
  - Vcc: Arduino 5 V
  - GND: Arduino GND
- Direction sign when track moves forward: provisional `-1` (encoder reports negative for forward motion)
- Notes: both S1 and S2 toggle when the motor is turned; direction is inferred from the commanded motor direction in the firmware, not from hardware.

Right encoder:

- Type: hall-effect, single-channel tachometer (hardware fault: only one signal wire produces pulses)
- Voltage level: 5 V from Arduino Nano
- Pullups: Arduino internal `INPUT_PULLUP` enabled in firmware
- Counts per output shaft revolution after gearbox: ~150 counts/rev (both directions)
- Connected pins, matching discovered existing-board pinout:
  - S1: Arduino D7, **the only live right encoder signal** (produces pulses)
  - S2: Arduino D3 / INT1, **dead** (no pulses from right encoder)
  - Vcc: Arduino 5 V
  - GND: Arduino GND
- Direction sign when track moves forward: provisional `+1` (encoder reports positive for forward motion, because firmware applies sign from commanded direction)
- Notes: the right encoder's S2/D3 channel is dead; only S1/D7 produces pulses. The firmware counts on D3/S2, so either (a) swap the right encoder wires at the Arduino so the live signal goes to D3, or (b) change the firmware to count on D7. Direction is inferred from the motor's commanded direction; true bidirectional hardware direction sensing is unavailable until the dead channel is repaired.
- Notes: user has access to a multimeter and logic analyser; measure S1/S2 voltage and pulse behaviour before finalising wiring/software

Safety warning:

- Raspberry Pi GPIO is **not 5 V tolerant**. Use level shifters or confirm encoder output is 3.3 V before connecting.

## 6. Motor driver

- Manufacturer/model: HW-354 dual motor controller, MX1508 based
- Logic voltage: likely compatible with Arduino 5 V logic, confirm during bench test
- Motor voltage range: usually 2-10 V; user is happy to treat as 9 V maximum for initial tests; do not connect 12 V directly
- Current rating continuous/peak: unknown, confirm module spec and temperature under load
- Control interface:
  - PWM + DIR: no separate DIR; use two MX1508 inputs per motor
  - IN1/IN2: yes, Motor A `INA`/`INB`, Motor B `INC`/`IND`
  - serial: no
  - I2C: no
  - CAN: no
  - USB: no
  - other:
- Encoder support built in?
- Brake/coast mode?
- Fault output?
- Enable pin?
- Datasheet URL/local copy:
- Board chip marking: likely MX1508; exact marking still worth photographing/checking
- Board pin labels: `INA`, `INB`, `INC`, `IND`, `GND`, `VCC`, motor outputs; no extra enable/fault pins per user
- Notes: pin labels confirmed by user; treat motor supply as 6-9 V for initial tests and monitor board temperature; see [`motor-control-arduino-nano-plan.md`](motor-control-arduino-nano-plan.md)

Wiring table:

| Function | Pi/MCU pin | Driver pin | Voltage | Notes |
|---|---|---|---|---|
| Left motor input A | Arduino D5 | HW-354 INA | 5 V logic PWM | decided |
| Left motor input B | Arduino D6 | HW-354 INB | 5 V logic PWM | decided |
| Right motor input A | Arduino D9 | HW-354 INC | 5 V logic PWM | decided |
| Right motor input B | Arduino D10 | HW-354 IND | 5 V logic PWM | decided |
| Enable | N/A | N/A | | MX1508 has no separate enable on this pinout |
| Fault | N/A | N/A | | no fault output known |
| Ground | Arduino GND | HW-354 GND | 0 V | shared with motor supply ground |

## 7. Arduino / microcontroller

- Board: Arduino Nano clone, mini USB, confirmed by user
- Variant/chip: likely classic ATmega328P Nano; no additional visible marking beyond CH340C reported yet
- USB serial chip: CH340C, confirmed visible marking
- Logic voltage: likely fixed 5 V, confirm before connecting to any 3.3 V-only devices
- Connected to Raspberry Pi by: USB serial; detected on Pi as QinHeng CH340 serial converter
- Linux device path: `/dev/ttyUSB0` at first connection
- Stable-ish path: `/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0` -> `../../ttyUSB0`
- USB VID/PID: `1a86:7523` QinHeng Electronics CH340 serial converter
- Kernel driver: `ch341`; dmesg says `ch341-uart converter now attached to ttyUSB0`
- Firmware path: `firmware/arduino_nano_base_controller/arduino_nano_base_controller.ino`
- Programming tool on Pi: `arduino-cli` 1.5.1 installed at `/usr/local/bin/arduino-cli`; Arduino AVR core installed for user `ubuntu`
- Arduino CLI FQBN: `arduino:avr:nano:cpu=atmega328old`
- Upload status: initial firmware uploaded successfully from Pi over `/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0`
- Bootloader note: default/new Nano bootloader FQBN `arduino:avr:nano` failed with `not in sync: resp=0x66`; old bootloader FQBN succeeded
- Serial test: 115200 baud; firmware printed `BOOT arduino_nano_base_controller`, periodic `E ...` status lines, and responded `OK stop` to `S` command. Firmware intentionally does not ACK every high-rate `V` velocity command to reduce serial chatter.
- Role: motor PWM, encoder counting, low-level PID, safety timeout
- Notes: programming from the Pi is confirmed practical. The by-id path is generic for CH340 and may not be unique if multiple identical CH340 adapters are connected; use a udev rule/by-path if needed. See [`motor-control-arduino-nano-plan.md`](motor-control-arduino-nano-plan.md)

## 8. Serial adapters

- Spare adapter description: MAX3232 RS232-TTL level converter
- USB-to-TTL UART? no, not by itself
- True RS232 level converter? yes
- Logic voltage: check board markings; MAX3232 can often run at 3.3 V or 5 V depending on board
- Intended use: unknown; possibly serial debugging, but not needed for Arduino USB serial
- Notes: RS232 side must not be connected directly to lidar TTL serial or Raspberry Pi GPIO. User also has a separate USB-to-TTL serial adapter, which should be used for initial lidar capture if its voltage tolerance is suitable.

## 9. Power system

- Battery type: none selected yet; likely LiPo for final robot
- Battery nominal voltage: undecided; user suspects 9 V or 12 V class, but HW-354/MX1508 must not receive 12 V directly; choose battery/regulator architecture later
- Battery capacity: undecided; needs sizing task based on motor current, Pi load, lidar load, and desired runtime
- Main fuse: not yet planned; add before battery-powered operation
- Motor power path: prototype likely mains/bench supply first; final path TBD
- Pi regulator model: none selected; currently powered by nonofficial USB-C mains adapter that is adequate for Pi-only setup
- Pi regulator output voltage/current: final battery regulator/BEC needed; target likely stable 5 V with sufficient current for Pi 4 plus peripherals
- Lidar power source: TBD; likely regulated 5 V, not yet wired
- Common ground plan: TBD; Arduino, motor driver logic, encoder ground, and motor supply ground will need a shared reference; protect Pi from motor noise
- Power switch: not yet planned
- Emergency stop switch: not yet planned; strongly recommended before free-driving/autonomous tests
- Battery monitor/ADC: not planned
- Notes: user has some USB power banks but expects only about 10 W at 5 V, likely insufficient for full robot. For prototyping, keep Pi on mains USB-C and use a controlled/separate motor supply until battery architecture is chosen. Need advice/task on LiPo nominal voltage, capacity, regulator/BEC, fuse, switch, and E-stop. A BEC is a battery eliminator circuit: a DC-DC regulator commonly used in RC systems to derive stable 5 V from a higher-voltage battery.

## 10. Optional/future sensors

### IMU

- Model:
- Interface:
- Voltage:
- ROS 2 driver:
- Frame name:
- Mounting pose:

### Camera

- Model:
- Interface:
- ROS 2 driver:
- Frame name:
- Mounting pose:

### Other

- Bumpers:
- LEDs:
- Speaker/buzzer:
- Buttons:

## 11. Calibration values

These values should eventually move into ROS YAML/Xacro config.

```yaml
track_separation_m: 0.155
effective_wheel_radius_m: 0.029
left_encoder_counts_per_rev: null
right_encoder_counts_per_rev: null
left_inverted: null
right_inverted: null
max_linear_velocity_mps: 0.2
max_angular_velocity_radps: 0.5
cmd_vel_timeout_s: 0.5
lidar_frame: lidar_link
base_frame: base_link
odom_frame: odom
map_frame: map
```

## 12. Test notes

Use this area to record observations from bringup.

### Date:

- Test:
- Result:
- Changes made:
- Follow-up:

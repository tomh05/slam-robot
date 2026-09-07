# Motor Encoder Bringup Test Plan

Goal: confirm the Arduino Nano pinout for both motor encoders, verify that `S1`/`S2`
produce pulses, and measure counts before powered motor testing.

## Known hardware fault

Manual testing on 2026-07-28 revealed that the **right encoder only produces pulses on one of its two signal wires** (S1 or S2, but not both). After swapping wires and confirming both Arduino pins D3 and D7 work when fed the live signal, it was determined that one right encoder channel is dead or disconnected at the sensor. The left encoder is fully functional with both channels.

Because the hardware fault is not trivial to repair (likely a damaged hall sensor or broken wire inside the motor assembly), the decision was made to **use both encoders as single-channel (x1) tachometers for distance measurement only**. Direction is inferred from the motor's commanded direction as set by the speed controller.

This means:
- Encoder counts are **always positive** in the hardware ISR (magnitude only).
- Direction is inferred from the commanded motor velocity (`target_tps` sign):
  the firmware negates the tick delta when the target velocity is negative, so the
  PID and reported tps have the correct sign.
- The direction-corrected deltas are accumulated into **signed positions**
  (`left_position` / `right_position`) which are reported in the `E` line to the Pi.
- The Pi receives correctly-signed positions and can integrate odometry with
  proper forward/backward distinction.
- Distance integration is correct under normal operation (no slip or unexpected reversal).
- The robot **cannot detect slip** or unexpected motor direction from encoders alone.

## 1. Safety / setup

For the first encoder-only tests:

- Do **not** connect the HW-354/MX1508 motor driver yet.
- Do **not** connect motor power to `M+`/`M-` yet.
- Power the Arduino Nano from the Pi/laptop over USB.
- Power each motor hall sensor from Arduino `5V` and `GND` only.
- Keep Raspberry Pi GPIO away from encoder signals; the encoder signals are assumed 5 V until measured.

The Arduino firmware keeps motor outputs low on boot and stops on timeout, but the cleanest encoder test is with motor power disconnected.

## 2. Encoder pinout from the existing board

Motor connector order, already captured from notes:

```text
M+
M-
GND
VCC
S1
S2
```

### Left motor / Motor A encoder

| Motor connector | Arduino Nano pin |
|---|---:|
| `GND` | `GND` |
| `VCC` | `5V` |
| `S1` | `D4` |
| `S2` | `D2` / `INT0` |

### Right motor / Motor B encoder

| Motor connector | Arduino Nano pin |
|---|---:|
| `GND` | `GND` |
| `VCC` | `5V` |
| `S1` | `D7` |
| `S2` | `D3` / `INT1` |

Leave `M+`/`M-` disconnected for manual-spin encoder tests.

## 3. Firmware to use

Use the **single-channel** firmware in:

```text
firmware/arduino_nano_base_controller/arduino_nano_base_controller.ino
```

Current encoder behaviour:

- **Left encoder**: `S2` is counted on `RISING` via INT0 on D2. The ISR always increments by +1.
- **Right encoder**: `S1` is counted on `RISING` via a pin-change interrupt (PCINT2 / PCINT23) on D7.
  The right encoder's `S2` channel (D3/INT1) is dead and not used for counting.
- The ISR always increments the count by +1 — there is no direction pin read.
- Direction is inferred in the control loop from the commanded target velocity sign:
  when `target_tps` is negative, the tick delta is negated, the PID and reported tps
  have the correct sign, and the signed position accumulator moves backward.
- The `E` status line reports **signed positions** (`left_position` / `right_position`),
  not raw always-positive counts, so the Pi can distinguish forward from backward.
- Counts can be zeroed with `Z`.
- Raw pin levels and edge counters can be requested with `R`.

Useful upload command on the Pi:

```bash
cd /home/ubuntu/slam-robot
arduino-cli compile --fqbn arduino:avr:nano:cpu=atmega328old firmware/arduino_nano_base_controller
arduino-cli upload -p /dev/serial/by-id/usb-1a86_USB_Serial-if00-port0 --fqbn arduino:avr:nano:cpu=atmega328old firmware/arduino_nano_base_controller
```

Before upload, ensure no ROS node or serial monitor is holding the port:

```bash
pgrep -af 'arduino_base_node|robot_state_publisher|smoke_publisher'
fuser -v /dev/ttyUSB0
```

## 4. Quick serial test

From the Pi:

```bash
cd /home/ubuntu/slam-robot
python3 scripts/arduino_encoder_test.py
```

The script:

- opens `/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0` at 115200 baud,
- sends `V 0 0` periodically so motor targets stay zero and the Arduino command timeout does not suppress measured `tps`,
- sends `Z` to zero counts,
- periodically requests raw pin levels with `R`,
- prints periodic `E` status lines.

Expected output when spinning the left track/motor slowly by hand:

```text
L=      12 dL=  +3 tps=  +15 R=       0 dR=  +0 tps=   +0 pwm=(  +0,  +0)
```

Expected output when spinning the right track/motor slowly by hand:

```text
L=       0 dL=  +0 tps=   +0 R=      11 dR=  +2 tps=  +10 pwm=(  +0,  +0)
```

Both sides should now show **incrementing counts when spun** (since `V 0 0` means
no direction is commanded, the firmware cannot infer sign). Direction inference
(positive vs negative position changes) can only be verified under actual motor
commands with `motors_enabled:=true` and non-zero `/cmd_vel`.

Initial result from 2026-07-28 (single-channel mode):

- Left encoder: counts increase when the motor is driven forward (positive tps),
  decrease when driven backward (negative tps). Approximately **224 counts/rev**.
- Right encoder: counts increase when the motor is driven forward (positive tps),
  decrease when driven backward (negative tps). Approximately **150 counts/rev**.
- The raw right `S2/D3` channel is dead; only `S1/D7` produces pulses. The firmware
  now counts on the live channel only, with direction inferred from the command.

## 5. Raw pin test

The helper script periodically prints raw pin levels like:

```text
raw pins: LS1=1 LS2=0 RS1=1 RS2=1
```

In single-channel mode, **the left encoder counts on S2/D2** (INT0) and **the
right encoder counts on S1/D7** (pin-change interrupt, since S2/D3 is dead).
`S1` levels for the left encoder (`LS1/D4`) and `S2` levels for the right
encoder (`RS2/D3`) are still reported for debugging but are not used for
counting.

For the left encoder, `LS2/D2` should toggle and drive counts. For the right
encoder, only `RS1/D7` produces pulses (the right `S2/D3` channel is known
dead). The firmware now counts rising edges on D7 via a pin-change interrupt,
so right counts should move.

If raw pins do not toggle:

- confirm encoder `VCC` and `GND` are correct;
- confirm the motor connector orientation really matches `M+ M- GND VCC S1 S2`;
- measure `S1`/`S2` with a multimeter or logic analyser while rotating;
- check whether the hall outputs need external pullups. The firmware enables Arduino `INPUT_PULLUP`, so open-collector outputs should usually work.

If counts alternate between +1 and -1 and do not accumulate:

- make sure the uploaded firmware is the version that uses `RISING`, not the older `CHANGE` interrupt mode.

## 6. Measurements to record

For each side, record in `docs/hardware-inventory-template.md` or a test log:

- Which physical motor is left/right.
- Which way the track was moved for "forward".
- Approximate counts per full output shaft/sprocket revolution in each direction.
  (Both directions should now produce the same magnitude of count change.)
- Which live pin is the live channel for each encoder:
  D2 (S2) for left via INT0, D7 (S1) for right via PCINT2.
- Any observed voltage levels from the logic analyser/multimeter.

Counts per revolution can be measured by:

1. Send `Z` or restart `scripts/arduino_encoder_test.py`.
2. Put a tape mark on the output sprocket/wheel.
3. Rotate exactly one output revolution by hand **in one direction only**.
4. Read the absolute count change (should be positive for forward).
5. Rotate one revolution in the opposite direction.
6. Read the absolute count change (should be negative for backward).
7. Both directions should produce the same **magnitude** of count change.


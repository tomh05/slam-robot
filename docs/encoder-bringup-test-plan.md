# Motor Encoder Bringup Test Plan

Goal: confirm the Arduino Nano pinout for both motor encoders, verify that `S1`/`S2`
produce pulses, and measure counts before powered motor testing.

## Known hardware fault

Manual testing on 2026-07-28 revealed that the **right encoder only produces pulses on one of its two signal wires** (S1 or S2, but not both). After swapping wires and confirming both Arduino pins D3 and D7 work when fed the live signal, it was determined that one right encoder channel is dead or disconnected at the sensor. The left encoder is fully functional with both channels.

Because the hardware fault is not trivial to repair (likely a damaged hall sensor or broken wire inside the motor assembly), the decision was made to **use both encoders as single-channel (x1) tachometers for distance measurement only**. Direction is inferred from the motor's commanded direction as set by the speed controller.

This means:
- Encoder counts are **always positive** in the hardware ISR.
- The firmware negates the tick delta when the previous PWM command was negative, so the PID and reported tps have the correct sign.
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

- `S2` is counted on `RISING` only (D2 for left, D3 for right).
- The ISR always increments the count by +1 — there is no direction pin read.
- Direction is inferred in the control loop: when the previous PWM command was
  negative, the tick delta is negated before computing measured tps.
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

Both sides should now show **positive and negative counts** depending on the
commanded direction, because the firmware applies sign from the PWM command.
(When motors are stopped with `V 0 0`, direction is undefined but ticks should
be near zero.)

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

In single-channel mode, **only S2 is used for counting** (D2 left, D3 right).
`S1` levels are still reported for debugging but are not used for direction.

For the left encoder, `LS2/D2` should toggle and drive counts. For the right
encoder, only `RS1/D7` produces pulses (the right `S2/D3` channel is known
 dead). The firmware counts rising edges on whichever S2 pin is wired, but
 for the right side the live signal is on D7, not D3.

> **Note:** the current firmware ISR is attached to D3 for the right encoder.
> If right encoder counts do not move, the right encoder signal wires may need
> to be swapped at the Arduino (move the live wire to D3) or the firmware pin
> mapping changed to count on D7 instead.

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
- Which S2 pin (D2 or D3) is the live channel for each encoder.
- Any observed voltage levels from the logic analyser/multimeter.

Counts per revolution can be measured by:

1. Send `Z` or restart `scripts/arduino_encoder_test.py`.
2. Put a tape mark on the output sprocket/wheel.
3. Rotate exactly one output revolution by hand.
4. Read the absolute count change.
5. Repeat a few times in both directions.


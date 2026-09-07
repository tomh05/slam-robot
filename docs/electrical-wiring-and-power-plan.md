# Electrical Wiring and Initial Power Plan

## 1. Newly confirmed hardware details

### Raspberry Pi

- Raspberry Pi 4 Model B
- 2 GB RAM

### Arduino Nano

- Arduino Nano clone
- CH340C USB-serial chip
- Mini USB connector
- Likely classic 5 V ATmega328P Nano form factor, but confirm board voltage markings before wiring.

### Motor driver

- HW-354 dual motor controller
- Driver chip/module type: MX1508
- Terminals/pins:

| Pin | Meaning |
|---|---|
| `VCC` | Motor driver power input, usually 2 V to 10 V |
| `GND` | Ground |
| `INA`, `INB` | Motor A control inputs |
| `INC`, `IND` | Motor B control inputs |
| `OUT1`, `OUT2` | Motor A output terminals |
| `OUT3`, `OUT4` | Motor B output terminals |

### Motor wiring

Motor connector pins from left to right:

```text
M+
M-
GND
VCC
S1
S2
```

Interpretation:

| Pin | Meaning |
|---|---|
| `M+` | Motor power terminal positive/side A |
| `M-` | Motor power terminal negative/side B |
| `GND` | Hall sensor ground |
| `VCC` | Hall sensor power, likely 5 V |
| `S1` | Hall/encoder signal 1 |
| `S2` | Hall/encoder signal 2 |

### Serial adapter

- Adapter chip: MAX3232.
- Important: MAX3232 is an RS-232 level converter, not a USB-to-TTL serial adapter by itself.
- It converts TTL UART levels to/from true RS-232 voltage levels.
- Do **not** connect the RS-232 side to the lidar TTL serial output or Raspberry Pi GPIO.

## 2. Important power warning: do not use 12 V on HW-354/MX1508

The HW-354/MX1508 motor driver VCC is usually specified around **2 V to 10 V**.

Therefore:

- Do **not** connect 12 V directly to the HW-354 motor `VCC` input.
- If the motors are the likely 9 V geared motors from the old notes, start with a current-limited bench supply around **6 V to 9 V**.
- Use 12 V only if a separate buck converter/regulator steps it down to a safe motor-driver voltage, and if the motors can tolerate the chosen voltage.

Recommended first powered tests:

```text
Bench supply: 6 V, current limit low, e.g. 0.5-1 A initially
Robot tracks: lifted off the table
Motor PWM: low duty cycle only
```

Then increase current limit and voltage only after confirming wiring and direction.

## 3. Recommended initial power architecture

For bench testing:

```text
Laptop / USB charger / Pi USB power
  -> Raspberry Pi 5 V USB-C

Raspberry Pi USB port
  -> Arduino Nano mini USB

Bench supply 6-9 V
  -> HW-354 VCC/GND motor power

Arduino 5 V
  -> motor hall sensor VCC
Arduino GND
  -> motor hall sensor GND
  -> HW-354 GND
```

Important grounding rule:

- Arduino GND, HW-354 GND, and motor hall sensor GND must be common.
- Raspberry Pi will usually share ground with Arduino through USB.
- Avoid powering high-current motors from the Pi or Arduino 5 V pins.

For eventual battery operation:

```text
Battery, maybe 2S Li-ion/LiPo or similar
  -> motor driver VCC, if within 2-10 V and motor-safe
  -> buck converter 5 V, sufficient current for Raspberry Pi
  -> optional fused branches
```

If using a 12 V battery later:

```text
12 V battery
  -> buck converter to 6-9 V for HW-354/motors
  -> separate buck converter to stable 5.1 V for Raspberry Pi
```

## 4. MX1508 control pattern

The MX1508 controls each motor with two input pins.

Typical behaviour:

| IN1 | IN2 | Motor behaviour |
|---|---|---|
| LOW | LOW | Coast/stop |
| PWM/HIGH | LOW | One direction |
| LOW | PWM/HIGH | Opposite direction |
| HIGH | HIGH | Brake, depending on board/chip behaviour |

For speed control, apply PWM to one input while holding the other LOW.

Example for Motor A:

```text
Forward:  INA = PWM, INB = LOW
Reverse:  INA = LOW, INB = PWM
Stop:     INA = LOW, INB = LOW
```

Motor direction may be reversed in real wiring. Fix in firmware/config rather than rewiring if convenient.

## 5. Arduino Nano pin allocation

Updated to match the discovered existing-board encoder pinout.

### Motor driver pins

Use PWM-capable pins for MX1508 inputs:

| Function | Arduino Nano pin | Notes |
|---|---:|---|
| Motor A `INA` | D5 | PWM |
| Motor A `INB` | D6 | PWM |
| Motor B `INC` | D9 | PWM |
| Motor B `IND` | D10 | PWM |

### Encoder/hall pins

Use external interrupt pins for the counted channel on each motor. The second
channel (`S1`) is **not read for direction** because the right encoder has a
hardware fault (only one signal wire produces pulses). Direction is inferred
from the motor's commanded direction in the firmware.

| Function | Arduino Nano pin | Notes |
|---|---:|---|
| Left/Motor A encoder `S1` | D4 | retained for debugging only |
| Left/Motor A encoder `S2` | D2 | external interrupt INT0, counted channel |
| Right/Motor B encoder `S1` | D7 | live right encoder signal, counted via PCINT2 pin-change interrupt |
| Right/Motor B encoder `S2` | D3 | dead channel, debug only |

The ISR counts every rising edge as +1 (magnitude only). The firmware negates
the tick delta when the commanded target velocity is negative, so the PID and
reported tps have the correct sign. Direction-corrected deltas are accumulated
into signed `left_position`/`right_position` values, reported in the E line.

The left encoder `S2` (D2/INT0) is the live left channel and uses the external
interrupt. The right encoder `S2` (D3/INT1) is dead; the live right signal is
on `S1` (D7), which is counted via a pin-change interrupt (PCINT2/PCINT23).

### Serial

| Function | Connection |
|---|---|
| Pi to Arduino | USB cable to Nano mini USB |
| Baud | Start with 115200 |

Avoid using Arduino D0/D1 for external wiring because they are shared with USB serial.

## 6. Proposed wiring table

### Left motor, mapped to Motor A

| Motor connector | Connect to |
|---|---|
| `M+` | HW-354 `OUT1` |
| `M-` | HW-354 `OUT2` |
| `GND` | Arduino `GND` |
| `VCC` | Arduino `5V` |
| `S1` | Arduino `D4` |
| `S2` | Arduino `D2` |

### Right motor, mapped to Motor B

| Motor connector | Connect to |
|---|---|
| `M+` | HW-354 `OUT3` |
| `M-` | HW-354 `OUT4` |
| `GND` | Arduino `GND` |
| `VCC` | Arduino `5V` |
| `S1` | Arduino `D7` |
| `S2` | Arduino `D3` |

### HW-354 to Arduino

| HW-354 pin | Arduino Nano pin |
|---|---:|
| `INA` | D5 |
| `INB` | D6 |
| `INC` | D9 |
| `IND` | D10 |
| `GND` | GND |

### HW-354 power

| HW-354 pin | Connect to |
|---|---|
| `VCC` | Bench supply +, initially 6-9 V, not 12 V direct |
| `GND` | Bench supply -, Arduino GND |

## 7. First electrical test sequence

1. Do not connect motors yet.
2. Power Arduino over USB.
3. Upload firmware that sets all motor driver pins LOW.
4. Verify Arduino serial works.
5. Connect HW-354 control pins and shared GND only.
6. Connect bench supply to HW-354 VCC/GND with current limit.
7. Connect one motor to OUT1/OUT2.
8. Command very low PWM briefly.
9. Confirm direction and stop behaviour.
10. Connect hall sensor VCC/GND/S1/S2.
11. Spin motor slowly and confirm encoder counts.
12. Repeat for the second motor.
13. Only then put tracks on the floor.

## 8. Open power questions

- What battery will be used eventually?
- What motor voltage is best: 6 V, 7.4 V, 9 V?
- What is the stall current of each motor?
- Is HW-354/MX1508 current capacity sufficient for the tracked chassis under load?
- What 5 V regulator will power the Raspberry Pi from battery?
- Should there be a physical emergency stop or motor power switch? Recommended: yes.

# Mains / Bench Power Notes for Prototyping

Date recorded: 2026-07-30.

During prototyping it is useful to run the robot from mains power instead of the LiPo battery. The safest and most flexible way is to use a current-limited bench DC power supply as a battery substitute.

## Recommended supply

Preferred purchase/use:

```text
Adjustable bench DC power supply
Output range: about 0-30 V
Current range: preferably 0-10 A
Must have adjustable current limiting
```

A 0-30 V / 5 A unit is usable, especially when the Raspberry Pi is powered separately, but 10 A gives more margin for motor surge and future tests.

Recommended settings:

| Test stage | Voltage | Current limit | Notes |
|---|---:|---:|---|
| First motor bring-up | 6 V | 0.5-1 A | Tracks lifted, low PWM only |
| Normal tethered testing | 7.4-8.0 V | 3-5 A | Similar to a 2S LiPo under load |
| Fully charged 2S emulation | 8.4 V max | 5-8 A | Do not exceed HW-354/MX1508 voltage rating |

Do **not** use 12 V directly with the HW-354/MX1508 motor driver.

## Why not a simple 9 V wall adapter?

A regulated 9 V supply can work, but it is not the best default choice:

- The HW-354/MX1508 motor driver should be treated as a roughly 2-10 V device.
- 9 V leaves little headroom below the likely 10 V maximum.
- Cheap wall adapters may be poorly regulated or noisy.
- The intended battery is 2S LiPo: 7.4 V nominal, 8.4 V full, so 7.4-8.4 V is a better emulation range.

If using a fixed mains adapter instead of a bench supply, prefer:

```text
Regulated desktop DC supply, not an unregulated wall wart
Output: 7.5 V or 8.4 V DC
Current: at least 6 A, preferably 8-10 A
Connector: XT60 pigtail/adapter into the robot power input
```

Avoid generic 9 V wall warts unless the output is verified with a multimeter and the supply is known to be regulated.

## Safest early prototyping setup

For early motor tests, power the Pi separately and use the bench supply only for the motor branch:

```text
Official / good Raspberry Pi USB-C mains PSU
  -> Raspberry Pi 4

Raspberry Pi USB port
  -> Arduino Nano mini USB

Bench PSU set to 6-8 V, current-limited
  -> HW-354/MX1508 VCC and GND

Common ground:
  Pi/Arduino GND
  Bench PSU negative
  HW-354 GND
  Motor encoder GND
```

This keeps the Pi stable while allowing motor-current limiting. The motors must not be powered from the Pi or Arduino 5 V rail.

## Battery substitute through the robot power input

Once the robot has its final fused/switchable battery wiring, the bench supply can feed the same input as the battery:

```text
Bench PSU, 7.4-8.4 V
  -> XT60 adapter/pigtail
  -> main fuse
  -> main switch
  -> robot power distribution
      -> HW-354/MX1508 motor driver
      -> 5 V buck regulator
          -> Raspberry Pi USB-C
```

Good default setting:

```text
Voltage: 7.8 V
Current limit: 5 A to start
```

Raise the current limit only after measuring current draw and confirming wiring/regulator temperature.

## Battery vs mains source selection

The simplest and safest source-selection method is a single robot power connector:

```text
Robot XT60 input accepts either:
  1. 2S LiPo battery
  2. Bench PSU / mains adapter via XT60 pigtail
```

Physically plug in one source or the other. This avoids accidentally paralleling the LiPo and mains supply.

If a switch is used, it should be:

```text
DC-rated break-before-make ON-OFF-ON selector switch
Rated at least 10 A at 12 V DC, preferably higher
```

Positive-side switching example:

```text
Battery + ---- fuse ----\
                         selector switch ---- robot +
Mains PSU + ------------/

Battery -, PSU -, and robot GND are common only when that source is in use.
```

Important safety rules:

- Never directly connect LiPo positive and mains/bench PSU positive together.
- Do not backfeed the battery from the bench PSU.
- Do not use a bench PSU as a LiPo charger.
- Keep the main fuse close to the battery positive terminal.
- Keep a motor-enable/e-stop switch in the motor branch if practical.

# Battery and Power Research / Recommendation

This note collects the current power recommendation for the small tracked SLAM robot.

## Current robot constraints

Known project hardware:

- Raspberry Pi 4 Model B, 2 GB.
- Arduino Nano clone for low-level motor/encoder control.
- HW-354 / MX1508 dual DC motor driver.
- Two tracked drive motors with encoders.
- Likely 5 V serial 2D lidar module.
- Robot is small: about 20 cm long, central chassis about 10 cm wide.

Important constraint from the current motor driver:

- MX1508/HW-354 boards are commonly specified for roughly **2-10 V motor supply**.
- Therefore **do not connect a 12 V / 3S LiPo directly to the HW-354**.

Web references checked:

- MX1508 examples/spec summaries list module supply around 2-10 V and about 1.5 A continuous per channel, with 2-2.5 A peak depending on source:
  - <https://components101.com/modules/mx1508-dc-motor-driver-pinout-features-datasheet>
  - <https://www.datasheethub.com/mx1508-mini-dual-channel-1-5a-dc-motor-driver-module/>
- Raspberry Pi 4 official-type supply is 5.1 V / 3 A, 15.3 W:
  - <https://www.adafruit.com/product/4298>
- Typical lithium-polymer cell voltage: 3.7 V nominal, 4.2 V full, around 3.0 V minimum; therefore 2S is 7.4 V nominal and 8.4 V full:
  - <https://learn.adafruit.com/li-ion-and-lipoly-batteries/voltages>
- RC LiPo packs often lack protection circuitry and need appropriate charging/low-voltage handling:
  - <https://learn.adafruit.com/li-ion-and-lipoly-batteries/rc-type-batteries>
- Example compact buck regulator: Pololu 5 V, 5 A D24V50F5, input up to 38 V, around 0.7 in x 0.8 in, typical efficiency 85-95%:
  - <https://www.pololu.com/product/2851>

## Recommended topology

Use one 2S lithium battery and split it into motor and logic rails.

```text
2S battery, 7.4 V nominal / 8.4 V full
  -> main fuse
  -> main power switch
  -> power distribution
      -> motor branch / e-stop -> HW-354 VCC/GND -> motors
      -> 5.1 V buck/UBEC -> Raspberry Pi 4 USB-C
                           -> lidar 5 V if needed
                           -> Arduino Nano, usually through Pi USB
```

Grounds must be common:

```text
Battery -
Buck converter GND
Raspberry Pi GND
Arduino GND
HW-354 GND
Lidar GND
```

The Pi and motor driver should not share the same unregulated supply rail. The motors can use the raw 2S battery voltage; the Pi needs a separate regulated 5 V / 5.1 V rail.

For mains/tethered prototyping, see [`mains-bench-power-notes.md`](mains-bench-power-notes.md). Short version: use a current-limited 0-30 V bench supply, preferably 10 A, set to 6 V for first lifted-track tests and 7.4-8.4 V for 2S battery emulation. A regulated 7.5 V or 8.4 V desktop supply rated 6-10 A is an acceptable fixed alternative. Avoid generic 9 V wall warts and never connect a bench supply directly in parallel with the LiPo.

## Battery recommendation

First choice:

```text
2S LiPo, 7.4 V nominal, 2200 mAh, 20C or higher, XT30 or XT60 connector
```

Why:

- 8.4 V full is within the current motor driver's likely 10 V maximum.
- 7.4 V nominal should be reasonable for motors believed to be in the 6-9 V class.
- RC LiPo packs can supply motor surge current easily.
- 2200 mAh is a good compromise between runtime and size.

If space is tight:

```text
2S LiPo, 1500 mAh
```

If runtime matters more and it physically fits:

```text
2S LiPo, 3000 mAh
```

Do not use a 3S / 11.1 V nominal / 12.6 V full LiPo with the current HW-354 unless you add a separate high-current buck converter for the motor branch or replace the motor driver.

## Runtime estimate

Battery energy:

```text
Wh = nominal_voltage * Ah
```

Approximate capacities:

| Pack | Energy | Usable estimate at 80% |
|---|---:|---:|
| 2S 1500 mAh | 7.4 V * 1.5 Ah = 11.1 Wh | ~8.9 Wh |
| 2S 2200 mAh | 7.4 V * 2.2 Ah = 16.3 Wh | ~13.0 Wh |
| 2S 3000 mAh | 7.4 V * 3.0 Ah = 22.2 Wh | ~17.8 Wh |

Likely average robot power is unknown until measured. A plausible small tracked ROS robot range is:

- Pi 4 + Wi-Fi + ROS 2: ~3-7 W typical, with 15 W supply sizing.
- Lidar: maybe ~1-3 W, depending on module.
- Arduino/logic: small.
- Motors: highly variable; maybe ~5-20+ W total while driving, higher on carpet/turning/stall.

Estimated runtime for a 2S 2200 mAh pack:

| Average draw | Runtime using ~13 Wh usable |
|---:|---:|
| 12 W | ~65 min |
| 15 W | ~52 min |
| 20 W | ~39 min |
| 25 W | ~31 min |

So a 2S 2200 mAh pack is a credible first choice for the requested 30-60 minute target, assuming the motor current is not excessive.

## Regulator recommendation

Use a high-quality buck regulator/UBEC for the Raspberry Pi rail:

```text
Input: accepts 2S battery range, at least 6-9 V input
Output: 5.0-5.1 V
Current rating: at least 4 A, preferably 5 A
```

Good example class:

- Pololu 5 V, 5 A D24V50F5: <https://www.pololu.com/product/2851>
- Or an adjustable 5 A buck converter set to about 5.1 V.
- Or a good RC-style 5 V / 5.1 V UBEC rated 5 A.

Notes:

- The official Pi 4 supply is 5.1 V / 3 A. Use a 5 A-capable regulator for margin.
- Keep the buck-to-Pi cable short and thick enough. Voltage drop in thin USB leads can cause Pi undervoltage warnings.
- If using a fixed 5.0 V regulator, wire it carefully with short leads. 5.1 V is preferable because it gives margin for cable/drop losses.

## Protection and switching

Minimum recommended parts:

- Main fuse close to the battery positive terminal.
- Main power switch.
- Separate motor-enable/e-stop switch if possible.
- 2S low-voltage alarm on the LiPo balance connector.
- Proper 2S LiPo balance charger.
- 470-1000 uF electrolytic capacitor, rated 16 V or higher, across HW-354 VCC/GND near the motor driver.

Suggested starting fuse values:

- Whole robot: 5-7.5 A blade fuse to start; raise only if nuisance trips are measured and wiring supports it.
- Logic branch: optional separate 3-5 A fuse.
- Motor branch: optional separate 5 A fuse.

A useful safety arrangement is:

```text
Main switch controls everything.
Motor e-stop cuts only motor power, leaving Pi alive for logs/SSH.
Arduino firmware still enforces command timeout and stop-on-boot.
```

## Shopping list

Recommended first shopping list:

1. 2S 7.4 V LiPo battery, 2200 mAh, 20C+, XT30 or XT60.
2. Proper 2S/3S LiPo balance charger.
3. LiPo-safe charging bag.
4. 2S low-voltage alarm.
5. 5.1 V or 5.0 V 5 A buck regulator/UBEC for Pi.
6. USB-C power pigtail or short high-quality USB-C cable for Pi power.
7. XT30/XT60 pigtails/connectors matching the battery.
8. Inline blade fuse holder plus 5 A and 7.5 A fuses.
9. DC-rated main switch.
10. Optional separate motor arm/e-stop switch.
11. 470-1000 uF, 16 V or higher electrolytic capacitor.
12. 20-22 AWG silicone wire, heat shrink, small terminal blocks or distribution board.

Optional but useful:

- Inline RC watt meter for measuring current and runtime.
- INA219/INA226 voltage/current sensor for later ROS battery monitoring.
- Spare stronger motor driver if HW-354 overheats or current-limits.

## Alternatives considered

### 3S / 12 V battery

Not recommended with the current motor driver. A 3S LiPo is 12.6 V full, which exceeds the likely HW-354/MX1508 rating. Use 3S only if replacing the motor driver or adding a high-current buck converter for motors.

### USB power bank for the Pi plus separate motor battery

Good for bench/debugging and electrically simple, but bulkier and not as neat as one 2S battery with a buck converter.

### 2S Li-ion 18650 pack with BMS

Potentially good for longer runtime and safer handling, but the pack must support the motor surge current. A 2S1P 18650 pack may not tolerate tracked-robot motor peaks; 2S2P is better but larger. Use only protected/BMS packs or properly built packs.

## Tests before finalising

Before buying a much bigger battery or redesigning power, measure current:

1. Pi + lidar idle/load current from the 5 V rail.
2. Motor current with tracks lifted.
3. Motor current driving on the floor.
4. Motor current turning in place on the expected surface.
5. Motor driver temperature after several minutes.

If each motor often exceeds about 1-1.5 A continuous or the HW-354 gets hot, upgrade the motor driver before increasing battery size or voltage.

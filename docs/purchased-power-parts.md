# Purchased Power Parts

Date recorded: 2026-07-30.

These are the power-related parts purchased for the SLAM robot battery-power build.

## Purchased items

| Category | Store | Listing / item | Variant selected | Qty | Price paid | Status/date | Ref. number |
|---|---|---|---|---:|---:|---|---|
| 5 V buck regulator | DIYUSER Official Store | Mini560 5A DC-DC Mini560 PRO Step-Down Stabilized Voltage Supply Module 6-30V To 3.3V 5V 9V 12V | **Mini560-5V** | 1 | £1.06 | Verifying payment, Jul 30 2026 | 3075672636394785 |
| Raspberry Pi USB-C power pigtail | Wodexiaodian Store | 5V 3A Single USB C to 2 Pin Bare Wire Open End 24AWG USB Type C Male Pigtail Cable Cord DIY for USB C Equipment Installed 0.3/1M | **0.3M** | 1 | £0.92 | Verifying payment, Jul 30 2026 | 3075672636414785 |
| Main battery | YOWOO POWER Official Store | HRB 1PCS 3000mah 3300mah Lipo 2S 3S 4S 6S 5S Battery 7.4V 11.1V 14.8V 22.2V 18.5V Lipo 50C 60C XT60 T for RC Car Drone Airplane | **7.4V 3000mah XT60, China Mainland** | 1 | £15.13 | Verifying payment, Jul 30 2026 | 3075672636434785 |
| JST-XH connectors | Stand Seen Store | 5Sets JST XH2.54 XH 2.54mm Wire Cable Connector 2/3/4/5/6/7/8 Pin Male and Female Plug Socket 10cm 20cm Wire Length 26AWG | **Length 10CM, 4P** | 1 set | £1.50 | Verifying payment, Jul 30 2026 | 3075672636294785 |
| LiPo safe bag | Skyrc Global Store | Lipo Guard Safety Bag Fireproof Explosion-Proof Portable Lipo Safety Bag 215*115*155mm for RC FPV Racing Drone Car Battery Safe | **1pcs type2** | 1 | £2.60 | Verifying payment, Jul 30 2026 | 3075672636454785 |
| Inline fuse holder | DQLZV Official Store | Medium 32V Car Waterproof Fuse Holder Socket 18/16/14/12/10AWG Auto Motorcycle Motorbike Blade Fuse 3A 5A 7.5A 10A 15A 20A 25A | **Red, 14AWG, 10A** | 1 | £1.16 | Verifying payment, Jul 30 2026 | 3075672636314785 |
| XT60 pigtails | NUODA Official Store | OMCH XT60 12/14AWG XT90 10AWG Male Female Plug Battery Connector With Silicone Wire Cable For RC Airplane Lipo Battery Drone Car | **XT60 Male and Female, 10cm, XT60 - 12AWG Wire** | 1 | £2.33 | Verifying payment, Jul 30 2026 | 3075672636334785 |
| Battery voltage alarm/checker | Shop1105228120 Store | BX100 1-8S Lipo Battery Voltage Tester / Low Voltage Buzzer Alarm / Battery Voltage Checker with Dual Speakers For RC Lipo Battery | **1Pcs black BX100** | 1 | £1.61 | Verifying payment, Jul 30 2026 | 3075672636354785 |
| Balance charger | Mitoot Official Store | IMAX B6 80W Lipo Charger T/Tamiya/XT60 Plug For NiMh Li-ion Ni-Cd Lipo Battery Balance Discharger + 12V 5A Adapter For RC Charger | **B6 XT60 T and adapter, UK Plug** | 1 | £26.89 | Verifying payment, Jul 30 2026 | not provided |

Total recorded spend: **£53.20**.

## Assessment

Overall this is a good set of purchases for the planned 2S battery power architecture:

```text
2S 7.4 V / 3000 mAh LiPo
  -> inline fuse
  -> main switch / distribution, still needed
      -> HW-354/MX1508 motor driver directly
      -> Mini560 5 V buck -> USB-C pigtail -> Raspberry Pi 4
```

Positive checks:

- Battery variant is correct: **2S 7.4 V 3000 mAh XT60**.
- Regulator variant is correct: **Mini560-5V**, not 3.3 V / 9 V / 12 V.
- Charger is a better B6-style charger rather than the very cheap B3-only charger.
- LiPo safe bag and BX100 alarm were purchased.
- XT60 pigtails are **12 AWG**, which is more than adequate for this small robot.
- Fuse holder is **14 AWG**, suitable for the expected current range.

## Caveats / things to check when parts arrive

### USB-C pigtail is 24 AWG and advertised 3 A

The USB-C pigtail is short, 0.3 m, which helps. However, 24 AWG is thin for Raspberry Pi 4 peak current. It may work, but it is a possible source of voltage drop.

When testing:

1. Set/verify the Mini560 output at about **5.1 V if adjustable**, or confirm it is close to 5.0 V if fixed.
2. Measure voltage at the Pi end of the USB-C pigtail under load.
3. Watch for Pi undervoltage warnings:

```bash
vcgencmd get_throttled
```

If undervoltage appears, replace the pigtail with a shorter/thicker USB-C lead or wire 5 V into a better USB-C breakout/pigtail.

### Fuse is 10 A

The selected fuse holder variant includes a **10 A** fuse. That is not dangerous if the wiring can handle it, but it is higher than ideal for first bring-up.

Recommendation for first tests:

- Prefer **5 A or 7.5 A blade fuse** in the holder if available.
- Use the 10 A fuse only after measuring current and confirming there are no nuisance trips.

### Mini560 thermal/current reality

Mini560 modules are tiny. Even if advertised as 5 A, continuous current can be thermally limited.

Test before relying on it:

1. Power Pi only from the Mini560.
2. Let it run ROS/lidar/Wi-Fi for 10-20 minutes.
3. Check for Pi undervoltage.
4. Check regulator temperature carefully.

## Still needed / not yet purchased

These were in the recommended list but are not in the purchased list above:

1. **Main power switch**, DC-rated, between fuse and power distribution.
2. **Optional motor emergency stop / motor-enable switch**, ideally normally-closed, in series with motor-driver VCC only.
3. **1000 uF electrolytic capacitor**, 16 V or 25 V, across HW-354 VCC/GND.
4. **Extra red/black wire**, preferably 18-20 AWG silicone wire.
5. **Heat-shrink tubing**.
6. **Small terminal block / distribution block**.
7. **5 A and/or 7.5 A blade fuses** if the ordered fuse holder only comes with 10 A.

## Arrival checklist

When the parts arrive:

1. Photograph each part and label/variant.
2. Measure battery voltage before charging.
3. Charge the LiPo in the safe bag using balance mode.
4. Confirm the BX100 reads both cell voltages.
5. Verify Mini560 output with a multimeter before connecting the Pi.
6. Verify USB-C pigtail polarity before connecting the Pi.
7. First power the Pi without motor driver connected.
8. Then test motor branch with tracks lifted and ideally current-limited if possible.

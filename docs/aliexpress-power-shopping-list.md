# AliExpress Power Shopping List

Date checked: 2026-07-30.

Prices below are AliExpress search-result prices in GBP at time of checking. Final price, shipping, tax, stock, and exact SKU variant can change. Always select the exact variant noted, not just the cheapest variant on a multi-option listing.

Selection criteria used:

- Prefer low cost, but not the no-name/zero-sales option for safety-critical parts.
- Prefer listings with many sales and ~4.8+ rating where available.
- For the battery: use **2S / 7.4 V nominal / 8.4 V full**, not 3S.
- For the Raspberry Pi regulator: must accept a 2S LiPo input range, including around 6.6-8.4 V. Avoid regulators advertised only as 12 V/24 V input unless their detailed spec confirms low-voltage operation.

## Recommended basket

### 1. Main battery

Recommended listing:

- **HRB 1PCS 3000mah 3300mah Lipo 2S 3S 4S 6S 5S Battery 7.4V... 50C 60C XT60/T**
- Search result: ~£21.73, 456 sold, 5.0 rating.
- URL: <https://www.aliexpress.com/item/1005007309974197.html>
- Select variant: **2S 7.4 V, 3000 mAh, XT60**, preferably 50C/60C.

Why this one:

- HRB is a more recognisable RC battery brand than many generic listings.
- 2S voltage is appropriate for the HW-354/MX1508 motor driver.
- 3000 mAh gives better chance of 45-60 minute runtime.

Avoid:

- 3S / 11.1 V / 12.6 V full packs with the current HW-354.
- 5C FPV goggle packs for the robot drive battery; those are lower-discharge packs.
- LiHV 7.6 V nominal packs unless you have a LiHV-capable charger and intentionally choose LiHV.

Budget alternative:

- **7.4V Lipo Battery 2S 1500mah/2200mah/3000mah... Dean T/XT60...**
- Search result: ~£8.32 minimum, 297 sold, 4.8 rating.
- URL: <https://www.aliexpress.com/item/1005004588343407.html>
- Caveat: the shown minimum price may be a smaller-capacity variant, so check the final price for **2S 3000 mAh XT60**. More generic, so less preferred.

### 2. Charger

Safer/better recommendation:

- **IMAX B6 80W Lipo Charger T/Tamiya/XT60 Plug... + 12V 5A Adapter**
- Search result: ~£26.84, 600+ sold, 4.8 rating.
- URL: <https://www.aliexpress.com/item/1005004771454637.html>
- Select variant: **charger + power adapter + UK plug**, and ideally XT60 lead included.

Why:

- Adjustable charge current, balance charging, and supports more battery types/cell counts.
- Better for a 3000 mAh pack than a very small 10 W B3 charger.

Low-cost alternative:

- **Imax B3 Pro / B3 2S 3S 7.4V 11.1V LiPo charger**
- Example URL: <https://www.aliexpress.com/item/1005009675482885.html>
- Search result: ~£7.13, 47 sold, 4.7 rating.
- Select variant: **UK plug, 2S/3S LiPo balance charger**.
- Caveat: slow for a 3000 mAh pack and less flexible. It charges only through the balance connector.

Do not use a random DC adapter directly on a LiPo pack.

### 3. LiPo safe bag

Recommended low-cost listing:

- **Lipo Guard Safety Bag Fireproof Explosion-Proof Portable... 215x115x155mm**
- Search result: ~£2.59, 10,000+ sold, 4.9 rating.
- URL: <https://www.aliexpress.com/item/1005004478094343.html>

Better/branded alternative:

- **Zeee Lipo Battery Safe Bag 215x145x165mm Fireproof...**
- Search result: ~£11.16, 1,000+ sold, 4.8 rating.
- URL: <https://www.aliexpress.com/item/1005007354717056.html>

### 4. Low-voltage alarm / cell checker

Recommended listing:

- **BX100 1-8S Lipo Battery Voltage Tester / Low Voltage Buzzer Alarm**
- Search result: ~£1.64, 3,000+ sold, 4.9 rating.
- URL: <https://www.aliexpress.com/item/1005006863873350.html>

Use:

- Plug into the LiPo balance connector.
- Configure/observe low-voltage warning.
- Stop around 6.6-6.8 V pack voltage for 2S during early testing.

### 5. 5 V regulator for Raspberry Pi

Preferred cheap module class:

- **Mini560 / Mini560 PRO 5A DC-DC step-down module, 6-30 V input, 5 V output**
- Example listing: <https://www.aliexpress.com/item/1005006700113120.html>
- Search result: ~£1.06 minimum, 317 sold, 5.0 rating.
- Select variant: **5 V output**, not 3.3/9/12 V.

Higher-sales pack/listing:

- **Mini560 5A DC-DC Mini560 PRO Step-Down 6-30V to 3.3V/5V/9V/12V**
- URL: <https://www.aliexpress.com/item/1005006537133858.html>
- Search result: ~£7.10, 1,000+ sold, 4.8 rating.
- Caveat: may be a multipack; select the correct count and **5 V** variant.

RC UBEC alternative:

- **5V 3A/5A/7A/15A External UBEC Voltage Regulator, supports 2S-12S**
- URL: <https://www.aliexpress.com/item/1005006049299888.html>
- Search result: ~£3.59 minimum, 1,000+ sold, 4.7 rating.
- Select variant: **5 V, at least 5 A**, preferably 7 A if small price difference.

Avoid for this robot unless detailed specs confirm it works down to 6-7 V input:

- Modules advertised only as **12V/24V to 5V** or **8-36V input**. A 2S LiPo can be below 8 V under load, so these may brown out near the end of discharge.

### 6. USB-C power pigtail for Raspberry Pi

Recommended listing:

- **DIY USB C to 2 Pin Bare Wire Open End Power Cable, 5V USB Type C Male Plug**
- Search result: ~£1.16, 2,000+ sold, 4.9 rating.
- URL: <https://www.aliexpress.com/item/1005010487402203.html>

Notes:

- Use a short cable.
- Prefer thicker wire if variant options exist.
- Wire regulator +5 V to USB-C red/+ and regulator GND to black/-.
- Verify polarity and voltage with a multimeter before plugging into the Pi.

Alternative:

- **USB C to 2 Pin Bare Wire Open End Power Cord, 90 Degree**
- URL: <https://www.aliexpress.com/item/1005010089226136.html>
- Search result: ~£2.12, 5,000+ sold, 4.9 rating.

### 7. XT60 pigtails / connectors

Recommended listing:

- **OMCH XT60 12/14AWG XT90... Male Female Plug Battery Connector With Silicone Wire**
- Search result: ~£2.37, 3,000+ sold, 4.9 rating.
- URL: <https://www.aliexpress.com/item/1005009609084487.html>
- Select variant: **XT60 male + female with 14 AWG silicone wire**, or a small pack of pairs.

Alternative:

- **1-10Pcs XT60 Plug Male Female Connector with 14AWG Silicone Wire**
- URL: <https://www.aliexpress.com/item/1005009156026988.html>
- Search result: ~£6.12, 900+ sold, 4.6 rating.

### 8. Inline fuse holder and fuses

Recommended fuse holder:

- **Medium 32V Car Waterproof Fuse Holder... 18/16/14/12/10AWG... 3A 5A 7.5A 10A...**
- Search result: ~£1.46, 1,000+ sold, 4.8 rating.
- URL: <https://www.aliexpress.com/item/1005005325398100.html>
- Select variant: medium/standard blade type, 14 AWG or 12 AWG, with 5 A or 7.5 A fuse if possible.

Fuse assortment:

- **20pcs Standard Blade Fuse Kit 1A 2A 3A 4A 5A 7.5A 10A...**
- Search result: ~£1.42, 1,000+ sold, 4.9 rating.
- URL: <https://www.aliexpress.com/item/1005011692733520.html>

Start with:

- Whole robot: 5 A or 7.5 A fuse.
- Increase only if measurements justify it and wiring is sized appropriately.

### 9. Main power switch

Recommended listing:

- **KCD1 10A 12V/220V Rocker Switch LED Dot Light Car Boat Round ON/OFF SPST**
- Search result: ~£1.48, 1,000+ sold, 4.9 rating.
- URL: <https://www.aliexpress.com/item/1005005797777120.html>

Note:

- Put the main switch after the fuse.
- If using a lit switch, check whether the LED needs a separate ground pin.

### 10. Optional motor emergency stop / motor-enable switch

Recommended listing:

- **22mm LA36M Emergency Stop Switch Lockable Push Button 12v 24v 220v 10A 1NC/2NC**
- Search result: ~£2.30, 700+ sold, 4.8 rating.
- URL: <https://www.aliexpress.com/item/1005008518428843.html>
- Select variant: **normally closed (NC)** contact if available, so pressing the button opens/cuts motor power.

Alternative:

- **22mm Emergency Stop Red Mushroom Push Button XB2... Self-locking Latching 600V 10A**
- URL: <https://www.aliexpress.com/item/1005006825289029.html>
- Search result: ~£2.49, 473 sold, 4.6 rating.

Recommended wiring:

```text
Battery + -> fuse -> main switch -> split
  -> Pi regulator
  -> e-stop / motor-enable switch -> HW-354 motor VCC
```

This lets the e-stop cut motors while leaving the Pi alive.

### 11. Motor driver bulk capacitor

Recommended listing:

- **10pcs-20pcs 16V1000UF 1000UF 16V low ESR aluminum electrolytic capacitor**
- Search result: ~£0.81, 310 sold, 4.9 rating.
- URL: <https://www.aliexpress.com/item/1005003012636265.html>

Alternative higher-sales listing:

- **10V 16V 25V 35V... Low ESR Aluminum Capacitor 100UF...1000UF...**
- URL: <https://www.aliexpress.com/item/1005006186858370.html>
- Search result: ~£1.35, 10,000+ sold, 4.9 rating.
- Select variant: **1000 uF, 16 V or 25 V**.

Install across HW-354 VCC/GND near the motor driver. Observe polarity.

### 12. Wire

Recommended listing:

- **2 meter Silicone Wire 8/10/12/14/16/18/20/22AWG... 1m red + 1m black**
- Search result: ~£3.18, 10,000+ sold, 4.8 rating.
- URL: <https://www.aliexpress.com/item/1005007468075329.html>
- Select variant: **20 AWG or 18 AWG red+black**.

Recommendation:

- Use 18 AWG if the size/price difference is small for the battery/motor branch.
- 20-22 AWG is fine for logic/signal/light branches.

### 13. Heat-shrink tubing

Recommended listing:

- **Heat Shrink Tube Kit Thermoresistant Tubing...**
- Search result: ~£1.34, 50,000+ sold, 4.8 rating.
- URL: <https://www.aliexpress.com/item/1005008146302901.html>

Alternative:

- **580/560Pcs Heat Shrink Tubing Kit EVA material in 6 colors / 11 sizes**
- URL: <https://www.aliexpress.com/item/1005007129319686.html>
- Search result: ~£3.11, 10,000+ sold, 4.9 rating.

### 14. Small power distribution / terminal block

Recommended simple terminal block:

- **25A 600V Dual Row Barrier Screw Terminal Block Wire Connector TB Series**
- Search result: ~£1.11, 800+ sold, 4.9 rating.
- URL: <https://www.aliexpress.com/item/1005010304971671.html>
- Select variant: small position count, e.g. 3-6 positions.

Alternative, more robust but physically larger:

- **PinXin 12V-48V 250A Bus Bar Terminal Battery Power Distribution Block With Cover**
- URL: <https://www.aliexpress.com/item/1005008678562439.html>
- Search result: ~£5.91, 700+ sold, 4.9 rating.
- Probably overkill for this small robot, but electrically neat.

## Optional debugging part

### Smoke stopper / short-circuit protection plug

Useful for first power-up, but not a substitute for the permanent fuse:

- **JHEMCU Amass Smoke Stopper 1-6S 30V XT30 XT60 Fuse Installation Test Safety Plug**
- Search result: ~£2.75, 700+ sold, 4.8 rating.
- URL: <https://www.aliexpress.com/item/1005007532924287.html>

Use between battery and robot on the first power-up to catch shorts.

## Expected low-cost basket total

Approximate, using recommended low-cost choices and excluding optional e-stop/smoke stopper:

| Item | Approx. price |
|---|---:|
| HRB 2S 3000 mAh LiPo | £21.73 |
| B6-style charger | £26.84 |
| LiPo safe bag | £2.59 |
| Low-voltage alarm | £1.64 |
| 5 V regulator | £1-£7 depending variant |
| USB-C pigtail | £1.16 |
| XT60 pigtails | £2.37 |
| Fuse holder | £1.46 |
| Fuse assortment | £1.42 |
| Main switch | £1.48 |
| Capacitors | £0.81-£1.35 |
| Wire | £3.18 |
| Heat shrink | £1.34 |
| Terminal block | £1.11 |

Estimated total with B6 charger: roughly **£68-£75** before shipping/tax changes.

With the cheap B3 charger instead of B6: roughly **£48-£55**, but charging is slower and less flexible.

## Final pre-order checks

Before ordering, verify on each product page:

1. Battery variant is **2S 7.4 V 3000 mAh XT60**, not 3S/4S or different connector.
2. Battery physical dimensions fit the robot. Target: ideally under ~110-120 mm long, under ~45-50 mm wide, under ~25 mm high.
3. Charger has **UK plug** or an acceptable adapter and supports **2S LiPo balance charging**.
4. Regulator is **5 V output** and input works from a 2S LiPo, including around 6.6-8.4 V.
5. USB-C pigtail has thick enough wire and is for power, not data-only odd wiring.
6. Fuse holder/fuses match the selected blade fuse size.
7. Switches are DC-current suitable for the robot's expected current.

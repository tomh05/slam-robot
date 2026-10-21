# YDLIDAR S4B — protocol findings, root cause of the "wrong distance" bug, and next steps

**Session date:** 2025-10-23
**Status:** root cause of the broken ranges **found and fixed** (off-by-one in the
sample offset).  The rewrite is done and verified offline against a saved
capture, but **not yet verified on the robot** (the robot was offline at the end
of this session).

---

## 1. TL;DR for the next session

| Question | Answer | Confidence |
|---|---|---|
| Packet header | `AA 55` (PH = 0x55AA) | certain (checksum) |
| Header length | **10 bytes** (`AA 55 CT LSN FSA(2) LSA(2) CS(2)`) | certain (checksum) |
| Sample block starts at | **header + 10** (was `header + 9` → the bug) | certain (checksum) |
| Bytes per sample | **3** = `[quality][dist_lo][dist_hi]` (intensity FIRST) | certain (checksum) |
| Distance word | `(dist_lo \| dist_hi<<8) & 0xfffc`, little endian | certain (checksum) |
| Distance scale | `range_m = distance_q2 / 4000.0` (1 count = 0.25 mm) | high (SDK + spec + min-range argument, **still needs a tape-measure check**) |
| Angle | `(FSA>>1)/64 + i*interval`, `interval = (LSA-FSA)/(LSN-1)` (with the SDK wrap rule) | certain (SDK) |
| 2nd order angle correction | `atan(21.8*(155.3-d_mm)/(155.3*d_mm)) * 180/π`, with **`d_mm = distance_q2/4.0`** | certain (SDK) |
| Revolution boundary | packets with `CT & 0x01 == 1` (ring start); they carry `LSN = 1` | certain (SDK + data) |
| Revolution size | **546 samples**, step ≈ 0.6595°, scan period ≈ 0.1365 s (7.33 Hz), 4 kHz sample rate | measured |
| Rotation direction | reported angle **increases** CCW in the angle-value domain; the physical spin direction still needs a left/right test | partially |

---

## 2. The root cause (why the distances were nonsense)

The old parser read the sample block at `header + 9` instead of `header + 10`.
The S4B header is 10 bytes long (`AA 55 CT LSN FSA(2) LSA(2) CS(2)`); the
vendor SDK constant is `PackagePaidBytes = 10`
(`lidar-resources/YDLidar-SDK-master/core/common/ydlidar_protocol.h:143`).

Consequences of that single byte of misalignment — with the true stream

```
[q0][lo0][hi0][q1][lo1][hi1][q2][lo2][hi2] ...
```

the old parser produced (starting one byte early):

```
node sample 0 = [CS_hi][q0][lo0]  -> "distance" = q0 | lo0<<8
node sample 1 = [q0][lo0][hi0]    -> "distance" = lo0 | hi0<<8   (the TRUE
                                                                value of the
                                                                previous sample)
node sample 2 = [lo0][hi0][q1]    -> "distance" = hi0 | q1<<8
```

i.e. **one sample in three was right (but belonged to the previous sample) and
two out of three were garbage**.  Because the garbage value is dominated by
`lo<<8` or `hi<<8`, the reported range was up to 256× too large and jumped
around by 256-count steps, wrapping at 65535.  That is exactly the reported
symptom set:

* *"a few cm in the real world is reported as a few meters"* → the `lo<<8`
  garbage gives 11–16 m for a 30 cm target,
* *"the reported distance increases quickly and wraps round from low to high"*
  → the reported value is `256 × (low byte of the true distance)`, so it jumps
  by ~1 m every 4 mm of real movement and wraps when the low byte wraps,
* *"multiple echoes of the same object"* → three different (wrong) ranges are
  reported for every real sample,
* *"V shaped walls"* → a mixture of correct and garbage ranges at neighbouring
  angles,
* *"angle jitter"* → partly this, partly the wrong `d_mm` in the angle
  correction and partly the sign-flipped angle step.

**How it was found:** the YDLIDAR SDK computes a packet checksum.  Re-implementing
it and brute-forcing every plausible framing over the saved capture
(`lidar_153600.bin`, 1111 packets) gives an unambiguous answer:

```
header=10  sample_bytes=3  layout=A   checksum ok 200/200 (100.0%)   <-- correct
header=10  sample_bytes=3  layout=B   checksum ok   1/200 (  0.5%)
header= 9  sample_bytes=3  layout=A   checksum ok   0/200 (  0.0%)
header= 9  sample_bytes=3  layout=B   checksum ok   0/200 (  0.0%)
header= 9  sample_bytes=2  layout=T   checksum ok   0/200 (  0.0%)
header=10  sample_bytes=2  layout=T   checksum ok   0/200 (  0.0%)
header=10  sample_bytes=4  layout=A4  checksum ok   0/200 (  0.0%)
```

`layout A` = `[quality][dist_lo][dist_hi]`, `layout B` = `[dist_lo][dist_hi][quality]`,
`T` = 2-byte samples (no intensity), `A4` = 4-byte samples.

The same tool now reports **1111/1111 packets with a valid checksum** on the
whole capture, i.e. the framing is proven, not guessed.

### The other bugs that were in the old node

1. `samp_start = i + 9` → must be `i + 10` (the bug above).
2. The second order angle correction used `distance_q2` (raw counts) where the
   SDK uses `distance_q2 / 4.0` (millimetres).  At 0.3 m that is a 3° error.
3. The angle step was negated (`step = -raw_step`) "because the motor spins
   clockwise".  The SDK does **not** negate by default (`m_Inverted` is an
   option).  Negating the step while the revolution boundary is detected from
   the ring-start bit makes the angle sequence jump backwards mid-scan, which
   chopped the scan at arbitrary places → "multiple echoes".
4. No checksum validation at all, so byte-corrupted packets were used.
5. The revolution was assembled by "angle jumped by more than 180°" instead of
   using the ring-start packets the device explicitly provides.
6. `LaserScan` requires a **uniform** angle grid.  The old node published
   irregular angles but declared a uniform `angle_increment`; RViz then
   rendered nonsense.  The new node resamples onto a uniform grid, like the
   vendor ROS driver does
   (`lidar-resources/ydlidar_ros_driver-master/src/ydlidar_ros_driver.cpp:200-220`).
7. `range_max` was 16 m; the S4B spec is 0.10–8.0 m.

---

## 3. The verified protocol (with sources)

```
offset 0 : AA 55          header
offset 2 : CT             bit0 = 1 -> ring start (revolution boundary)
offset 3 : LSN            samples in this packet (40 normally, 1 for ring start)
offset 4 : FSA  (LE u16)  first sample angle, bit0 = check bit (must be 1)
offset 6 : LSA  (LE u16)  last  sample angle, bit0 = check bit (must be 1)
offset 8 : CS   (LE u16)  checksum
offset 10: LSN * 3 bytes of samples:
                [quality][dist_lo][dist_hi]
```

Angle: `angle_units = (FSA>>1) + i * interval`, `angle_deg = angle_units/64`
(1/64 degree units).  The interval is `(LSA-FSA)/(LSN-1)`; when `LSA < FSA`
the SDK uses `(23040 + LSA - FSA)/(LSN-1)` **only** if
`FSA > 270*64 and LSA < 90*64`, otherwise it re-uses the previous packet's
interval (`YDLidar-SDK/src/ydlidar_driver.cpp:960-1020`).
The first packet of every revolution hits exactly this wrap case
(FSA ≈ 349°, LSA ≈ 15°) — a naive `(LSA-FSA)/(LSN-1)` yields a bogus
−8.57°/sample step there, which is another source of "jitter" if not handled.

Distance: `distance_q2 = (dist_lo | dist_hi<<8) & 0xfffc`, then
`range_m = distance_q2 / 4000.0` for `TYPE_TRIANGLE` lidars
(`YDLidar-SDK/src/CYdLidar.cpp:582-590`).  The 0.25 mm unit is confirmed by
the independent kaiaai/LDS implementation of the X4 (same family):
`float point_distance_mm = node.distance_q2 * 0.25f;`
(`/tmp/LDS/src/LDS_YDLIDAR_X4.cpp`, cloned from https://github.com/kaiaai/LDS).

Second order angle correction (both the SDK and kaiaai/LDS):
`corr_deg = atan( (21.8*(155.3 - d_mm)/155.3) / d_mm ) * 180/π` with
`d_mm = distance_q2/4.0`; the SDK stores it in 1/64 degree units.

### "No signal" sentinel values seen in the capture

| raw | count | /4000 | /8000 | meaning |
|---|---|---|---|---|
| `0xFA00` (64000) | 10206 | 16.000 m | 8.000 m | no return (sentinel) |
| `0xFED8` (65240) | 10180 | 16.310 m | 8.155 m | no return (sentinel) |
| `0xFD48` (64840) | 2605 | 16.210 m | 8.105 m | no return (sentinel) |
| `0xFD49` (64841) | 475 | 16.210 m | 8.105 m | no return (sentinel) |

All *real* returns in the capture are below 12000 (3.0 m).  The sentinels are
firmware constants and are simply filtered out by `range_max`.

### Why `/4000` and not `/8000` (the distance scale)

* The vendor SDK uses `/4000` for every `TYPE_TRIANGLE` lidar, and the S4B is
  `TYPE_TRIANGLE` (`lidar-resources/ydlidar_ros_driver-master/details.md`,
  "LidarType Table").
* kaiaai/LDS: `distance_q2 * 0.25f` = millimetres for the X4 (same protocol).
* **Physical argument:** the S4B's minimum range is 0.10 m.  The smallest raw
  value in the whole capture is **460** → 460/4000 = **0.115 m** (just above
  the 0.10 m limit, exactly what a real device does).  With `/8000` it would
  be 0.057 m — *below* the sensor's own minimum range, i.e. physically
  impossible.

**Still to do:** confirm with a tape measure (see the action list).

---

## 4. What is in the repo now

### New/changed source

| File | Purpose |
|---|---|
| `ros2_ws/src/lidar_scan_publisher/lidar_scan_publisher/ydlidar_protocol.py` | **new** — ROS-free, unit-testable YDLIDAR decoder (checksum, framing, angle maths, revolution assembly) |
| `ros2_ws/src/lidar_scan_publisher/lidar_scan_publisher/node.py` | **rewritten** — thin ROS wrapper: serial → parser → uniform-grid `LaserScan` |
| `ros2_ws/src/lidar_scan_publisher/package.xml` | added `<exec_depend>python3-serial</exec_depend>` |
| `scripts/lidar_debug.py` | **new** — packet inspector: framing brute force + checksum validation + packet dump + CSV export |
| `scripts/lidar_profile.py` | **new** — revolution assembly, raw-value statistics, ASCII polar plot |
| `scripts/lidar_replay.py` | **new** — replays a capture through the *real* parser (offline regression test) |
| `scripts/lidar_capture_serial.py` | existing capture helper |

### Tools and what they show

```bash
# 1. capture (on the robot)
python3 scripts/lidar_capture_serial.py --port /dev/ttyUSB0 --baud 153600 --seconds 5

# 2. prove the framing (works on a .bin file, no robot needed)
python3 scripts/lidar_debug.py --file lidar_153600.bin --packets 5

# 3. revolution profile + polar plot
python3 scripts/lidar_profile.py lidar_153600.bin --plot

# 4. replay through the real parser (regression test)
python3 scripts/lidar_replay.py lidar_153600.bin --csv /tmp/scan.csv
```

Current offline result on `lidar_153600.bin`:

```
packets   : 1111  bad checksum: 0  bad header: 0
samples   : 40113   revolutions: 75  scale: /4000
points/rev: min=63 max=546 median=545
-- revolution 0: 546 points, 213 valid, angle 0.41..359.09 deg
   angular step: min=0.0029 med=0.6585 max=2.6250 deg
   range: min=0.120 med=0.765 max=3.007 m
```

546 samples/revolution and 0.6595°/sample ⇒ 4 kHz sample rate and
4000/546 = **7.33 Hz** rotation, which matches the CT byte of the ring-start
packets (`CT = 0x93` → `(0x93 & 0xFE) >> 1 = 73` → 7.3 Hz, exactly the SDK's
`scan_frequence` encoding).

---

## 5. Action list for the next session (in priority order)

1. **Flash the new node and look at RViz.**
   ```bash
   scp -r ros2_ws/src/lidar_scan_publisher ubuntu@slamrobot.local:~/slam-robot/ros2_ws/src/
   ssh ubuntu@slamrobot.local 'cd ~/slam-robot/ros2_ws && source /opt/ros/jazzy/setup.bash && source install/setup.bash && colcon build --packages-select lidar_scan_publisher'
   ssh ubuntu@slamrobot.local 'cd ~/slam-robot/ros2_ws && source /opt/ros/jazzy/setup.bash && source install/setup.bash && ros2 run tf2_ros static_transform_publisher --frame-id base_link --child-frame-id laser --z 0.1 &'
   ssh ubuntu@slamrobot.local 'cd ~/slam-robot/ros2_ws && source /opt/ros/jazzy/setup.bash && source install/setup.bash && ros2 run lidar_scan_publisher lidar_scan_publisher --port /dev/ttyUSB0 --frame-id laser'
   ```
   RViz: Fixed Frame `base_link`, LaserScan topic `/scan`.
2. **Confirm the distance scale empirically** (the only remaining doubt):
   put a sheet of paper at a *measured* 0.30 m, 0.50 m, 1.00 m and 2.00 m from
   the sensor and record
   `python3 scripts/lidar_debug.py --port /dev/ttyUSB0 --packets 20` (or
   `lidar_profile.py`) → the raw value should be `8000 × distance_m`
   (i.e. 2400 / 4000 / 8000 / 16000).  If the raw values are instead
   `16000 × distance_m`, the device is a 16 m variant and `/8000` is right.
3. **Decide the rotation direction**: put an obstacle on the robot's left and
   watch which way it moves in RViz; if it is mirrored, start the node with
   `--invert` (or add a 180° yaw to the static transform instead — do not do
   both).
4. **Re-check the "V shape"**: with the framing fixed the wall should be
   straight.  If a residual curvature remains, check the mounting tilt
   (`--z`, and a pitch in the static transform) and try
   `--no-correct` to see how much the 2nd order correction contributes.
5. **Multiple echoes**: they were caused by the off-by-one; verify that they
   are gone.  If not, check that the revolution boundary is the ring-start
   packet (CT bit 0) and that no packets are being lost by the serial reader
   (the capture showed occasional 2.6° gaps, i.e. dropped packets — consider
   a bigger read buffer / `serial.read()` size and a lower `timer` period).
6. **Optional: connect TX and use the vendor driver.**  Now that the framing
   is understood, wiring lidar RX ← Pi TX (3.3 V level!) would let the
   official `ydlidar_ros2_driver` work and would be a good cross-check of the
   ranges (the SDK is the reference implementation).  Until then the custom
   node is fine.
7. **Optional: adopt kaiaai.**  See section 6.

---

## 6. External references found this session

* **https://github.com/kaiaai/kaiaai** — a ROS 2 framework for DIY LiDAR
  robots (`kaia` CLI, one workspace for many robots, SLAM/Nav2 bringup,
  telemetry, Gazebo).  Its LiDAR driver library is
  **https://github.com/kaiaai/LDS** — an independent, from-scratch
  implementation of the YDLIDAR protocol for ESP32/Arduino (X4, X2/X2L, X3,
  SCL, RPLIDAR A1, Neato XV11, Xiaomi LDS, Delta-2A/B/G, LD14P, Camsense …).
  Very useful as a *reference implementation* (it confirmed the 0.25 mm
  distance unit and the angle maths) and as a possible future base for the
  robot stack.  The `kaiaai` repo itself has no lidar-debug tool; the debug
  value is in `LDS`.
* **https://discuss.ardupilot.org/t/15-360-degree-xv-proximity-lidar/104887/21**
  — despite the title this thread is about the **Xiaomi Roborock XV-11** lidar
  (a camera/photodiode based 6.5 m proximity scanner), *not* YDLIDAR.  The
  transferable ideas are: (a) write your own small decoder for the exact
  device instead of fighting a vendor driver, (b) the ESP32 "blackpill"
  + PWM motor control recipe for cheap lidars, (c) the MAVLink
  `OBSTACLE_DISTANCE` message for feeding a lidar into ArduPilot.  It does not
  help with the YDLIDAR protocol itself.
* Local resources: `lidar-resources/YDLidar-SDK-master` (the reference
  implementation, `src/ydlidar_driver.cpp` = framing + checksum,
  `src/CYdLidar.cpp` = distance scale + scan assembly) and
  `lidar-resources/ydlidar_ros_driver-master` (ROS driver: how a `LaserScan`
  is filled from the points).

---

## 7. Quick reference: the vendor checksum

From `YDLIDAR-SDK/src/ydlidar_driver.cpp` (triangle lidar **with** intensity,
3-byte samples):

```python
c  = 0x55AA
c ^= FSA_raw            # 16 bit word *including* the check bit
c ^= (CT + LSN * 256)
c ^= LSA_raw            # 16 bit word including the check bit
for each sample:
    c ^= quality_byte
    c ^= (dist_lo | dist_hi << 8)
assert (c & 0xFFFF) == CS
```

For a 2-byte-sample (no intensity) lidar the sample loop is just
`c ^= (lo | hi << 8)`; for a 4-byte TOF sample it is
`c ^= quality_word; c ^= distance_word`.

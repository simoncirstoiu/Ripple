# Ripple
Motion detection from your existing Zigbee devices.


## In one sentence

Ripple turns ordinary Zigbee devices into a room motion sensor. 
A person who moves between two devices changes the strength of the radio signal (RSSI) that one device receives from the other. 
Ripple firmware measures that change inside the device firmware.
It detects movement and keeps the room ON for `off_s` after the last movement, and reports it to Home Assistant. 
It needs no camera, no PIR, no mmWave and no extra hardware, except your existing Zigbee devices.

## Tested and supported hardware

- Chip: **Telink TLSR8258**. It has a 32-bit MCU (the firmware runs it at 24 MHz), no FPU, little RAM and an IEEE 802.15.4 radio at 2.4 GHz.
- Switches:

  | Gangs | Model | Board |
  |---|---|---|
  | 1 | Tuya TS0001 `_TZ3000_0t4zjtia` | `SWITCH_TUYA_0T4ZJTIA_TS0001` |
  | 2 | Tuya TS0002 `_TZ3000_ptjcjise` | `SWITCH_INDUAL_TOUCH_TS0002` |
  | 3 | Tuya TS0003 `_TZ3000_jfh4mdia` | `SWITCH_BSEED_JFH4MDIA_TS0003` |

- Each device keeps it's original functions stays and acts as a normal Zigbee 3.0 router. Relays, buttons, bindings, OTA and ZHA all work as before.
- Home Assistant side: the Ripple integration on top of ZHA. It needs nothing else, not even HACS.

## The physics perspective:

- **Wavelength.**
- λ = c / f = 3·10⁸ / 2.44·10⁹ ≈ **12.3 cm**.
- **What a body does.**
- A human body is mostly water, so at 2.4 GHz it absorbs and scatters the signal, and a body inside the radio path attenuates the link by several dB.
- **Where a line can see you.**
- Most of the energy travels inside the first Fresnel zone, an ellipsoid around the straight line between the two switches.
- Its radius is r = √(λ·d₁·d₂ / d).
- At the middle of a 5 m link that is **about 0.4 m**.
- The strongest effect is inside this ellipsoid, outside it, a moving person changes only the weaker reflected paths, so the effect is smaller and depends on the room.
- **Multipath.**
- Indoors, the receiver sees the sum of many reflected copies of the signal.
- A person who moves anywhere near the link changes that sum, this is what makes moving people visible, and it is also why the signal fluctuates even in an empty room at a high sensitivity.
- **Reciprocity.**
- The links A→B and B→A share the same propagation, so a body affects both directions alike.
- Noise at each receiver is independent: in a zone (the OR of its lines) the second direction lowers misses, but adds its own chance of a false ON, both directions see the same place, so they add little coverage.
- **Physical limits:**
  - one RSSI step is 1 dB;
  - a person who is perfectly still changes almost nothing, so the line is held ON by a hold timer after the last change, not measured continuously;
  - geometry and line sensitivity is the user's choice of which lines form each zone, more lines that cross a room give better coverage.

## How it works

### 1. Lines and beacons
- A **line** is one sender heard by one receiver.
- Each switch keeps up to **10 lines** (`SENSE_LINES`).
- Each switch sends short **sensing beacons**:
  - 2 to 10 per second, 5 by default, set from Home Assistant Ripple Addon;
  - an 802.15.4 broadcast with a 13-byte payload, about 1 ms on air, so about 0.5% of the channel per switch at 5 beacons per second (configurable between 0(off) and 10 beacons per second.;
  - addressed to a foreign PAN ID (`0x5E55`), so every other Zigbee device that is not flashed drops it at the MAC layer, so it is never relayed or ACKed and never touches a routing table;
  - it carries the sender's relay state, so the receiver knows when the sender switched a light.
- The receiver also uses every normal Zigbee frame from the same sender.
- **Beacons stop by themselves**
- During an OTA, for 60 s after boot, while a bound On/Off command is being delivered, and when the stack has fewer than 8 free buffers.

**The device main/primary function always comes first, so Ripple will prioritize the original device main functions.**

### 2. Per-line detection (integer math only)

1. **Sampling.** 
- Above 12.5 frames/s, only one frame in m is kept, with m = ⌈rate / 12.5⌉. 
- Fast senders are capped at 12.5 kept frames/s, so the work per line is bounded. 
- Slow senders give fewer frames and react later.
2. **Reference.** 
- The reference is the **median of the 5 kept frames before the current one**. 
- A median ignores single spikes and follows the slow drift of the room, it is a robust form of background subtraction.
3. **Deviation.** 
- dev = |x − median|, in dB.
4. **Weight.** 
- Each kept frame weighs w = min(dev / thr, 3), this is a capped (winsorised) score: the deviation in units of the threshold, capped at 3, so one large spike counts no more than three small ones. 
- Three bitmaps hold the hits w ≥ 1, ≥ 2 and ≥ 3 of the last 16 kept frames.
5. **Rule.** 
- The line turns ON when the weighted sum of those 16 frames stays at least **M** for D = 10 ms × (100 − s). 
- This is a weighted M-of-N rule over a sliding window of 16 kept frames, a finite-memory relative of CUSUM. 
- It is cheap, needs no floating point, and every step of s gives a different result.
6. **OFF.** 
- The line turns OFF `off_s` seconds after its last hit. 
- The default is 30 s, and from Ripple HA Addon you can adjust it per room/line.
7. **Light switching is not motion.** 
- A relay changes the RF itself. 
- Samples are skipped for 1.5 s after any relay edge, of the receiver or of the sender, and a learned offset is removed while the relay is ON.

### 3. One knob per line: sensitivity s = 0..100
- One table (`motion_tab`) gives the threshold and M for each s:
- s 100..50: threshold 1 dB, M rises from 1 to 8;
- s 49..1: M stays 8, and the threshold rises from 1.25 dB to 10 dB.
- The default is s = 50, the middle of the scale.
- **Calibrate.** 
- One command from HA records the empty room for a while. 
- For each line it builds a 16-bin histogram of 1 dB and picks the most sensitive `s` that never fired during the capture, minus a safety margin.
- **24 h self-tuning.** 
- It moves `s` by at most one coarse level per day, and by at most ±2 levels in total from the anchor set by the user or by Calibrate.
- It uses only frames in which the line and its zones are OFF.
- It makes `s` less sensitive only when even the quietest hour of the day is more than twice as noisy as the anchor day. 
- It makes `s` more sensitive only when the whole day is less than half as noisy.
- A person who is present for a few hours therefore cannot move it.
- Caveat: "OFF" is the detector's own judgement, a person whom no line sees, in every hour of the day, would count as empty, the quietest-hour rule and the ±2 bound limit that case.

### 4. Zones and reporting
- A **zone** is a set of lines that the user picks. 
- Each line can belong to up to 8 zones.
- A zone is ON when one or multiple of its lines detects (adjustable from Ripple HA Addon), so the integration can also require "all" lines, or "k of n" lines, per room, in order for the zone virtual motion sensor to be triggered.
- The switch reports **zone_state (`0xff43`)** and **per-line state (`0xff46`)** together, in one ZCL Report on the manufacturer cluster `0xfc57` (manufacturer `0x1141`). 
- The report asks for an APS ACK, with up to 2 re-sends 5 s apart if the ACK is missing.
- Reports are sent on a change, plus one heartbeat every 30 min. Diagnostics and the Live stream are sent only on request.
- **Everything is tuned from Home Assistant, with no OTA:** sources, zones, s, off_s, beacon rate, calibration and self-tuning on/off.

### 5. Home Assistant Ripple Addon
- The integration finds the supported devices at runtime, nothing is hardcoded for a specific HA setup.
- It creates room occupancy and motion entities and per-line entities.
- Its panel offers rooms, lines, a sensitivity slider, Calibrate and a Live view with real-time timestamps.

## Costs and limits:
- **Network:** 
- about 0.5% airtime per switch at 5 beacons/s. 
- Beacons are never relayed. 
- HA traffic is sent on a change, plus one heartbeat every 30 min.

- **Switch:**
  - no heap: fixed arrays for 10 lines;
  - a stack check and a reserve of 8 stack buffers;
  - a compact attribute table.
- **Scale:** 
- 0 to 100 switches per house, 10 lines and 8 zones per switch.
- **Limits:**
  - a line sees only near its own path, so a room needs lines that cross it;
  - a still person is held by the timers, not measured;
  - noisy or busy links need their own s, or a Calibrate;
  - a link with a gap of more than 4 s between frames restarts detection on that line;
  - a line counts only if its level is at least −90 dBm;
  - a switch sends no beacons during its own OTA and for 60 s after it.

## Why I build it.
- Because.

## Related work
- Ripple builds on **RSS-based device-free passive localisation**, also known as radio tomographic imaging (Youssef et al.; Patwari & Wilson), and on background subtraction of RSS.
- Commercial systems use the same principle on other radios, for example Philips Hue MotionAware (Zigbee lights) and ESPectre (Wi-Fi CSI on ESP32).
- What is different in Ripple:
  - it runs **inside the Zigbee device firmware**, on the TLSR8258, with no hub-side model;
  - it uses only RSSI, with integer math;
  - any Zigbee device on the network that transmits can be a sender; our our firmware also send adjustable beacons.

---

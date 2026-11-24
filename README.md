# Ripple for Home Assistant

Motion detection from your existing Zigbee devices.

https://github.com/user-attachments/assets/bd2e8076-61fb-47bc-91c2-4b365c0fa2b7

Ripple turns mains powered Zigbee devices into room presence sensors.

Devices that run the Ripple firmware measure the radio links between them, and a person moving through a room changes those links.

This integration finds the devices in ZHA or Zigbee2MQTT, groups them into rooms by area, and lets you tune, calibrate and flash them from Home Assistant.

## Tested hardware

- Chip: **Telink TLSR8258**. It has a 32-bit MCU (the firmware runs it at 24 MHz), no FPU, little RAM and an IEEE 802.15.4 radio at 2.4 GHz.
- Switches:

  | Gangs | Model | Board |
  |---|---|---|
  | 1 | Tuya TS0001 `_TZ3000_0t4zjtia` | `SWITCH_TUYA_0T4ZJTIA_TS0001` |
  | 2 | Tuya TS0002 `_TZ3000_ptjcjise` | `SWITCH_INDUAL_TOUCH_TS0002` |
  | 3 | Tuya TS0003 `_TZ3000_jfh4mdia` | `SWITCH_BSEED_JFH4MDIA_TS0003` |

- Each device keeps its original functions and stays a normal Zigbee 3.0 router. Relays, buttons, bindings and OTA work as before, in ZHA or Zigbee2MQTT.
- Home Assistant side: the Ripple integration, on top of ZHA or Zigbee2MQTT. It needs nothing else.

## Supported hardware

Every Zigbee router board with a Telink TLSR8258 in the board table can be flashed with Ripple: 123 boards. Boards that are Zigbee end devices are not supported, because the firmware is a router build.

The status comes from the device database the board table is built from: fully supported, mostly supported or in progress. Only the boards in Tested hardware run Ripple in daily use.

<details>
<summary>All 123 supported boards</summary>

| Device | Zigbee model | Manufacturer name | Type | Status |
|---|---|---|---|---|
| Aubess 4-gang | `TS0004` | `_TZ3000_mmkbptmx` | module | fully supported |
| Aubess TMZ02 | `TS0002` | `_TZ3000_lmlsduws` | module | fully supported |
| AVATTO ZWSM16-3 🅰 | `TS0003` | `_TZ3000_hbic3ka3` | module | fully supported |
| AVATTO ZWSM16-3 🅱 | `TS0003` | `_TZ3000_iv4eq7eh` | module | fully supported |
| AVATTO ZWSM16-4 🅰 | `TS0004` | `_TZ3000_5ajpkyq6` | module | fully supported |
| AVATTO ZWSM16-4 🅱 | `TS0004` | `_TZ3000_3n2minvf` | module | fully supported |
| BSEED 1-gang touch switch 🅰 | `TS0001` | `_TZ3000_9akmi5ly` | switch | fully supported |
| BSEED 1-gang touch switch 🅰 | `TS0001` | `_TZ3000_wijoqjk1` | switch | fully supported |
| BSEED Echo Click / Scale 3-gang | `TS0726` | `_TZ3002_iedhxgyi` | switch | fully supported |
| BSEED Echo Click / Scale 4-gang | `TS0726` | `_TZ3002_pzao9ls1` | switch | fully supported |
| BSEED Melody 1-gang touch switch L+N | `TS0001` | `_TZ3000_ysdv91bk` | switch | fully supported |
| BSEED Melody 2-gang touch switch L+N | `TS0002` | `_TZ3000_mklgayek` | switch | fully supported |
| BSEED Melody 3-gang touch switch L+N | `TS0003` | `_TZ3000_7aqaupa9` | switch | fully supported |
| BSEED outlet | `TS011F` | `_TZ3000_o1jzcxou` | outlet | fully supported |
| BSEED-type 3-gang touch switch (jfh4mdia) (tested) | `TS0003` | `_TZ3000_jfh4mdia` | switch | fully supported |
| EKAZA EKAC-T3092Z | `TS0002` | `_TZ3000_hznzbl0x` | module | fully supported |
| Farylink FS-02HZ / (Nous L13Z clone) | `TS0002` | `_TZ3000_ruxexjfz` | module | fully supported |
| Girier 1-gang curtains | `TS130F` | `_TZ3210_dwytrmda` | module | fully supported |
| Girier 1-gang dry-contact | `TS0001` | `_TZ3210_tqlv4ug4` | module | fully supported |
| Girier 2-gang curtains | `TS130F` | `_TZ3000_j1xl73iw` | module | fully supported |
| Girier JR-ZDS01 🅱 | `TS0001` | `_TZ3000_zw7yf6yk` | module | fully supported |
| Girier JR-ZDS01 🅲 | `TS0001` | `_TZ3000_6axxqqi2` | module | fully supported |
| Girier 🅰 3-gang | `TS0003` | `_TZ3000_odzoiovu` | module | fully supported |
| Girier 🅱 1-gang | `TS0001` | `_TZ3210_9hbau615` | module | fully supported |
| GoSmart IP-2101SZ / EMOS H5101 | `TS0001` | `_TZ3000_hyziup76` | module | fully supported |
| GoSmart IP-2102SZ / EMOS H5102 | `TS0002` | `_TZ3000_wxtmgjbd` | module | fully supported |
| Hommyn RLZBN02 | `TS0002` | `_TZ3000_5gey1ohx` | module | fully supported |
| iHseno 1-gang | `TS0001` | `_TZ3000_pgq7ormg` | module | fully supported |
| iHseno 1-gang 🅰 | `TS0001` | `_TZ3000_kycczpw8` | module | fully supported |
| iHseno 1-gang 🅱 | `TS0001` | `_TZ3000_rmjr4ufz` | module | fully supported |
| iHseno 2-gang | `TS0002` | `_TZ3000_eei0ubpy` | module | fully supported |
| iHseno 3-gang | `TS0003` | `_TZ3000_mhhxxjrs` | module | fully supported |
| iHseno 4-gang | `TS0004` | `_TZ3000_knoj8lpk` | module | fully supported |
| Indual MT-2G-Z 2-gang touch switch (tested) | `TS0002` | `_TZ3000_ptjcjise` | switch | fully supported |
| MHCOZY TYWB 4ch-RF / ZG-005(-RF) 🅰 | `TS0004` | `_TZ3000_imaccztn` | board | fully supported |
| Milfra 1-gang switch | `TS0001` | `_TZ3000_gsqxcwqr` | switch | fully supported |
| Milfra 2-gang switch | `TS0002` | `_TZ3210_mrigi9ij` | switch | fully supported |
| Milfra 3-gang switch | `TS0003` | `_TZ3000_ybjqjsuz` | switch | fully supported |
| Milfra 3-gang switch | `TS0003` | `_TZ3210_ybjqjsuz` | switch | fully supported |
| Milfra 4-gang switch | `TS0004` | `_TZ3210_03vs3ks5` | switch | fully supported |
| Moes ZM4LT2 | `TS0002` | `_TZ3000_criiahcg` | module | fully supported |
| Moes ZM4LT4 | `TS0004` | `_TZ3000_tyg4yiat` | module | fully supported |
| Nous B1Z | `TS0001` | `_TZ3000_ctftgjwb` | module | fully supported |
| NovaDigital MS105-ZB | `TS0001` | `_TZ3000_c8wtsv3p` | module | fully supported |
| NovaDigital ZTS-3W | `TS0003` | `_TZ3000_785olaiq` | switch | fully supported |
| QS-Zigbee-S10-3C | `TS0003` | `_TZ3000_ly9apzky` | module | fully supported |
| Scimagic ZG-001 1ch-RF | `TS0001` | `_TZ3000_g8n1n7lg` | board | fully supported |
| T-LED 1-gang | `TS0001` | `_TZ3000_npzfdcof` | module | fully supported |
| Tuya 1-gang | `TS011F` | `_TZ3000_i9oy2rdq` | module | fully supported |
| Tuya 1-gang switch | `TS0001` | `_TZ3000_ehgouyvu` | switch | fully supported |
| Tuya 1-gang touch switch (0t4zjtia) (tested) | `TS0001` | `_TZ3000_0t4zjtia` | switch | fully supported |
| Tuya 2-gang | `TS0002` | `_TZ3000_n1j44rth` | module | fully supported |
| Tuya 2-gang | `TS0002` | `_TZ3000_01gpyda5` | module | fully supported |
| Tuya 2-gang touch switch | `TS0002` | `_TZ3000_jjdkhueq` | switch | fully supported |
| Tuya 3-gang | `TS0003` | `_TZ3000_uwhjgngj` | module | fully supported |
| Tuya 3-gang switch | `TS0003` | `_TZ3000_aa5t61rh` | switch | fully supported |
| Tuya 3-gang switch | `TS0003` | `_TZ3000_zcbpj2t6` | switch | fully supported |
| Tuya 4-gang | `TS0004` | `_TZ3000_ltt60asa` | module | fully supported |
| Tuya 4-gang switch | `TS0004` | `_TZ3000_vit9k2nb` | switch | fully supported |
| Tuya common 1-gang | `TS0001` | `_TZ3000_khmapq4n` | module | fully supported |
| Tuya common 2-gang | `TS0002` | `_TZ3000_zbfya6h0` | module | fully supported |
| Tuya common 3-gang | `TS0003` | `_TZ3000_pf7swkqp` | module | fully supported |
| Tuya common 4-gang | `TS0004` | `_TZ3000_liygxtcq` | module | fully supported |
| Tuya default 1-gang 🅰 | `['TS0001', 'TS000F']` | `_TZ3000_skueekg3` | module | fully supported |
| Tuya default 1-gang 🅰 / Girier JR-ZDS01 🅰 / Zbeacon TS0001 | `['TS0001', 'TS000F']` | `_TZ3000_skueekg3` | module | fully supported |
| Tuya default 1-gang 🅱 | `TS0001` | `_TZ3000_skueekg3` | module | fully supported |
| Tuya default 1-gang 🅲 | `TS0001` | `_TZ3000_skueekg3` | module | fully supported |
| Tuya QS-Zigbee-S04-2C | `TS0002` | `_TZ3000_fisb3ajo` | module | fully supported |
| Tuya QS-Zigbee-S10-C04 curtains | `TS130F` | `_TZ3210_ol1uhvza` | module | fully supported |
| Tuya YNTDQ 1-gang | `TS0001` | `_TZ3000_olo5jhjk` | module | fully supported |
| Tuya ZTU 1-gang | `TS0001` | `_TZ3000_gjrubzje` | module | fully supported |
| Tuya/OXT 1-gang | `TS0001` | `_TZ3000_tqlv4ug4` | module | fully supported |
| Tuya/OXT 2-gang | `TS0002` | `_TZ3000_bvrlqyj7` | module | fully supported |
| Tuya/OXT 3-gang | `TS0003` | `_TZ3210_aksyshpw` | module | fully supported |
| UNSH FS-02HW / (Nous L13Z clone) | `TS0002` | `_TZ3000_ruxexjfz` | module | fully supported |
| ZTU dev board 2 | `-` | `-` | board | fully supported |
| AVATTO 1-gang dry-contact | `TS0001` | `_TZ3000_gzggw2ia` | module | mostly supported |
| AVATTO ZTS02RD-US-W1 | `TS0001` | `_TZ3000_w1tcofu8` | switch | mostly supported |
| AVATTO ZTS02RD-US-W2 | `TS0002` | `_TZ3000_ogpla3lh` | switch | mostly supported |
| AVATTO ZTS02RD-US-W3 | `TS0003` | `_TZ3000_avky2mvc` | switch | mostly supported |
| AVATTO ZTS02RD-US-W4 | `TS0004` | `_TZ3000_eeswvvtm` | switch | mostly supported |
| BSEED dim-backlight 1-gang touch switch | `TS0001` | `_TZ3000_blhvsaqf` | switch | mostly supported |
| BSEED dim-backlight 2-gang touch switch | `TS0002` | `_TZ3000_l9brjwau` | switch | mostly supported |
| BSEED dim-backlight 3-gang touch switch | `TS0003` | `_TZ3000_qkixdnon` | switch | mostly supported |
| homeetec 1-gang touch | `TS0001` | `_TZ3000_bmqxalil` | switch | mostly supported |
| homeetec 2-gang touch | `TS0002` | `_TZ3000_in5qxhtt` | switch | mostly supported |
| homeetec 3-gang touch | `TS0003` | `_TZ3000_pv4puuxi` | switch | mostly supported |
| MHCOZY TYWB 4ch-RF / ZG-005(-RF) 🅳 | `TS0004` | `_TZ3210_imaccztn` | board | mostly supported |
| Moes ZM-104B-M | `TS0002` | `_TZ3000_qaa59zqd` | module | mostly supported |
| NOVATO ZRM01 | `TS000F` | `_TZ3000_hdc8bbha` | module | mostly supported |
| NOVATO ZRM02 / Tuya QS-Zigbee-S10-2C | `TS000F` | `_TZ3000_m8f3z8ju` | module | mostly supported |
| Tuya 1-gang switch | `TS0001` | `_TZ3000_u6ocpapf` | switch | mostly supported |
| Tuya 3-gang touch switch | `TS0003` | `_TZ3000_nrdwow8a` | switch | mostly supported |
| Tuya 4-gang switch | `TS0004` | `_TZ3000_gbdxbmwz` | switch | mostly supported |
| Tuya common 1-gang | `TS0001` | `_TZ3000_rfexs4vs` | module | mostly supported |
| Tuya common 4-gang | `TS0004` | `_TZ3000_2wp3tnwa` | module | mostly supported |
| Zbeacon 2-gang | `TS0002` | `Zbeacon` | module | mostly supported |
| Aubess PM plug | `TS011F` | `_TZ3000_gvn91tmx` | plug | in progress |
| BSEED 2-gang touch switch | `TS0002` | `_TZ3000_cauq1okq` | switch | in progress |
| BSEED 2-gang touch switch | `TS0002` | `_TZ3000_w5xztuy7` | switch | in progress |
| BSEED Melody 4-gang touch switch L+N | `TS0004` | `_TZ3000_s6ma1nh4` | switch | in progress |
| BSEED PM outlet 🅰 | `TS011F` | `_TZ3000_b28wrpvx` | outlet | in progress |
| BSEED PM outlet 🅱 | `TS011F` | `_TZ3000_ko6v90pg` | outlet | in progress |
| BSEED PM outlet 🅲 | `TS011F` | `_TZ3000_4ux0ondb` | outlet | in progress |
| BSEED/Boruidapls PM Outlet | `TS011F` | `_TZ3210_zifx0xoj` | outlet | in progress |
| Farylink FS-02Z | `TS0001` | `_TZ3000_fdxihpp7` | module | in progress |
| Girier 🅰 1-gang | `TS0001` | `-` | module | in progress |
| Girier 🅰 2-gang | `TS0002` | `-` | module | in progress |
| Girier 🅱 2-gang | `TS0002` | `-` | module | in progress |
| LoraTap 1-gang curtains switch | `TS130F` | `_TZ3000_qa8s8vca` | switch | in progress |
| LVGESS 1-gang PM | `TS0001` | `_TZ3000_q8r0bbvy` | module | in progress |
| MakeGood MG-GPO01 double socket | `TS011F` | `_TZ3210_bep7ccew` | outlet | in progress |
| Moes PM wall socket | `TS011F` | `_TZ3000_ss98ec5d` | outlet | in progress |
| Moes SR-ZS | `TS0726` | `_TZ3002_vaq2bfcu` | switch | in progress |
| Moes ZM4LT1 | `TS0001` | `_TZ3000_afgzktgb` | module | in progress |
| Moes ZM4LT3 | `TS0003` | `_TZ3000_mzcp0of6` | module | in progress |
| PSMART T441/T451 TL | `TS0001` | `_TZ3000_l67wb0p1` | switch | in progress |
| PSMART T442/T452 TL | `TS0002` | `_TZ3000_cmgs1zkr` | switch | in progress |
| Tuya 1-gang switch | `TS0001` | `_TZ3000_b7s7xsow` | switch | in progress |
| Tuya 2-gang switch | `TS0002` | `_TZ3000_aa5t61rh` | switch | in progress |
| Tuya 2-gang switch | `TS0002` | `-` | switch | in progress |
| Tuya 3-gang switch | `TS0003` | `-` | switch | in progress |
| Tuya PM wall socket | `TS011F` | `_TZ3210_vddauzhn` | outlet | in progress |

</details>

## Requirements

- Home Assistant 2025.1 or newer, with one of:
  - Zigbee Home Automation (ZHA), with a `custom_quirks_path` set in the `zha:` section of `configuration.yaml`;
  - Zigbee2MQTT 2.x with the MQTT integration, and `advanced.enable_external_js` on in Zigbee2MQTT.
- Mains powered devices with the Telink TLSR8258 chip, or devices already on Ripple firmware 5.0.3 or newer.

Battery devices are not supported.

## Install

These steps are for a first install.

### 1. Back up

Make a full backup of Home Assistant.
On Zigbee2MQTT, also back up its data folder, the one with `configuration.yaml`, `database.db` and `state.json`.

### 2. Prepare ZHA or Zigbee2MQTT

On ZHA, Ripple gives ZHA its quirk as a file, `ripple_quirks.py`, and ZHA loads it from a quirks folder.
Add this to `configuration.yaml` in Home Assistant, if it is not there already:

```yaml
zha:
  custom_quirks_path: /config/custom_zha_quirks/
```

If you already have a `custom_quirks_path`, keep it: Ripple writes its file there.
Ripple creates the folder if it is missing.

On Zigbee2MQTT, leave `advanced.enable_external_js` on (the default).
If you use the external converter of the tuya-zigbee-switch project, remove it: both describe the same device models.

### 3. Install Ripple

Use one of the two ways below. The Marketplace is the recommended one: it installs the latest release and tells you when a new one is out.

#### From the Marketplace (recommended)

The Marketplace is in Home Assistant 2026.11 and newer.
Ripple is not in the default catalog, so it is added from its GitHub link.

1. Open Settings, Marketplace.
2. In the upper-right corner, choose "Add from link".
3. Enter `https://github.com/simoncirstoiu/Ripple`, then click Add.
   If the Marketplace asks for the type, choose Integration.
   If no GitHub account is connected yet, the Marketplace asks you to connect one first.
4. Open Ripple in the Marketplace and click Download.
5. Restart Home Assistant.

Updates show up in the Marketplace and in Settings, Updates.

#### Manual install

Download the source archive (zip or tar.gz) of the latest release from the Releases page of this repository, and unpack it.
Only the `custom_components/ripple_presence` folder goes into Home Assistant.

Copy `custom_components/ripple_presence` to `/config/custom_components/ripple_presence`.
Create `/config/custom_components` if it does not exist.
Any way of reaching `/config` works: the Samba share, the SSH add-on (where `/config` is `/homeassistant`), or a file editor add-on.

Restart Home Assistant.

To update, replace the folder with the one from the new release and restart Home Assistant.

### 4. Set up

1. Go to Settings, Devices and services, Add integration, and pick Ripple.
   When both ZHA and MQTT are set up, Ripple asks which one runs your devices.
   For Zigbee2MQTT it asks for the base topic (default `zigbee2mqtt`).
2. Keep "Allow writes to devices" off for the first start.
3. Add to "Protected devices" anything Ripple must never read, write or flash.
4. On ZHA, restart Home Assistant once more, so ZHA loads the Ripple quirk.
   Until then, Settings, Repairs shows that a restart is needed.
   On Zigbee2MQTT, Ripple saves its external converter `ripple.js` in `external_converters/` in the data folder by itself.
   If Zigbee2MQTT refuses it, Settings, Repairs says so.
5. Open Ripple in the sidebar and check the rooms and devices it found.

When the rooms and links look right, turn on "Allow writes to devices".

## The Ripple panel

- **Rooms**: live presence, room settings, calibration, and every device in the room with its links.
- **Devices**: the Zigbee devices running Ripple firmware, with status, firmware version, rooms and links.
- **Bindings**: what each button controls and what controls it; add or remove one binding at a time.
- **Firmware**: flash the Ripple firmware onto supported devices.

Each room also gets an Occupancy `binary_sensor` on a device named "Ripple - <room>".

Use it in your automations like any motion sensor.

## Flashing firmware

The firmware is one binary for the TLSR8258 chip, shipped with the integration as `firmware/Ripple-v5.0.6.bin`.

A newer `Ripple-vX.Y.Z.bin` placed in `/config/ripple/firmware` is used instead.

When you press Install on a device, Ripple:

1. reads the manufacturer and model that ZHA or Zigbee2MQTT reports and finds the board in the board table;
2. builds the OTA image for that device and keeps it in a cache, so identical devices reuse it;
3. sends it through the OTA of ZHA or Zigbee2MQTT;
4. waits for the device to come back (a converted device rejoins, permit join stays open while it does);
5. writes the board configuration (buttons, relays, LEDs) and checks it after the restart.

If the detected board is wrong, choose Custom and pick the board yourself from the table.

Only one install runs at a time.

Do not cut the power during a flash.

## Board table

`boards.json` lists the TLSR8258 boards Ripple knows, with their pins and the names the devices report.

You can add or override boards in `/config/ripple/boards.json`; Ripple reads it again when it changes, no restart needed.

Only router (mains powered) boards can be flashed.

Boards marked `tested` run Ripple in daily use: Tuya TS0001 `_TZ3000_0t4zjtia`, TS0002 `_TZ3000_ptjcjise` and TS0003 `_TZ3000_jfh4mdia`.

When a device fits more than one board, Ripple picks the tested one.

## Writes and safety

With writes off, Ripple only reads: it discovers devices, reads the devices one at a time, and shows motion.

Your changes are saved and listed under Repairs as "changes not sent".

With writes on, Ripple sends only what differs from the device.

Every write goes through one guarded path that refuses protected devices and devices without Ripple firmware.

## Firmware versions

Ripple configures devices on firmware 5.0.3, 5.0.4, 5.0.5 and 5.0.6.

Older Ripple firmware is shown with "update firmware" and left untouched.

A device with newer firmware than the integration knows is shown with "update integration" and also left untouched.

## In one sentence

- Ripple turns ordinary Zigbee devices into a room motion sensor. 
- A person who moves between two devices changes the strength of the radio signal (RSSI) that one device receives from the other. 
- Ripple firmware measures that change inside the device firmware.
- It detects movement and keeps the room ON for `off_s` after the last movement, and reports it to Home Assistant. 
- **It needs no camera, no PIR, no mmWave and no extra hardware, except your existing Zigbee devices.**

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
  - 2 to 10 per second, 5 by default, set from the Ripple integration;
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
  - The default is 30 s, and from the Ripple integration you can adjust it per room/line.
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
- **24 h self-tuning** (off by default since firmware 5.0.6, turn it on per switch from Home Assistant).
  - It moves `s` by at most one coarse level per day, and by at most ±2 levels in total from the anchor set by the user or by Calibrate.
  - It uses only frames in which the line and its zones are OFF.
  - It makes `s` less sensitive only when even the quietest hour of the day is more than twice as noisy as the anchor day. 
  - It makes `s` more sensitive only when the whole day is less than half as noisy.
  - A person who is present for a few hours therefore cannot move it.
  - Caveat: "OFF" is the detector's own judgement, a person whom no line sees, in every hour of the day, would count as empty, the quietest-hour rule and the ±2 bound limit that case.

### 4. Zones and reporting
  - A **zone** is a set of lines that the user picks. 
  - Each line can belong to up to 8 zones.
  - A zone is ON when one or multiple of its lines detects (adjustable from the Ripple integration), so the integration can also require "all" lines, or "k of n" lines, per room, in order for the zone virtual motion sensor to be triggered.
  - The switch reports **zone_state (`0xff43`)** and **per-line state (`0xff46`)** together, in one ZCL Report on the manufacturer cluster `0xfc57` (manufacturer `0x1141`). 
  - The report asks for an APS ACK, with up to 2 re-sends 5 s apart if the ACK is missing.
  - Reports are sent on a change, plus one heartbeat every 30 min. Diagnostics and the Live stream are sent only on request.
- **Everything is tuned from Home Assistant, with no OTA:** sources, zones, s, off_s, beacon rate, calibration and self-tuning on/off.

### 5. Home Assistant integration
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

## Why I built it
- Because.

## Related work
- Ripple builds on **RSS-based device-free passive localisation**, also known as radio tomographic imaging (Youssef et al.; Patwari & Wilson), and on background subtraction of RSS.
- Commercial systems use the same principle on other radios, for example Philips Hue MotionAware (Zigbee lights) and ESPectre (Wi-Fi CSI on ESP32).
- What is different in Ripple:
  - it runs **inside the Zigbee device firmware**, on the TLSR8258, with no hub-side model;
  - it uses only RSSI, with integer math;
  - any Zigbee device on the network that transmits can be a sender; our firmware also send adjustable beacons.

---

## Thanks

Ripple builds on published research.

These papers inspired it, and the ones we did not follow still helped us rule ideas out.

- Mrazovac, Bjelica, Kukolj, Todorović, Samardžija, "A Human Detection Method for Residential Smart Energy Systems Based on Zigbee RSSI Changes", IEEE Transactions on Consumer Electronics 58(3), 2012.
- Page, "Continuous Inspection Schemes", Biometrika, 1954.
- Basseville, Nikiforov, "Detection of Abrupt Changes: Theory and Application", 1993.
- Patwari et al., "Breathfinding", IEEE Journal of Selected Topics in Signal Processing: <https://span.ece.utah.edu/uploads/jstsp-patwari_r2_f.pdf>
- Patwari et al., "BreathTaking": <https://arxiv.org/abs/1109.3898>
- Edelstein, Rabbat, background subtraction for online baseline RSS: <https://arxiv.org/abs/1207.1137>
- Zhao, Patwari et al., "KRTI", IPSN 2013: <https://users.cs.utah.edu/~jeffp/papers/RTI+KD-ipsn13.pdf>
- Bocca et al., "RTI Goes Wild", IEEE Transactions on Mobile Computing, 2015: <https://alippi.faculty.polimi.it/articoli/RTI.pdf>
- Kaltiokallio et al., three-state RSS model: <https://arxiv.org/abs/1402.7019>
- Kaltiokallio, Bocca, Patwari, "A Multi-Scale Spatial Model for RSS-based Device-Free Localization": <https://arxiv.org/abs/1302.5914>
- Yigitler, Jäntti, Kaltiokallio, Patwari, "Detector Based Radio Tomographic Imaging": <https://arxiv.org/abs/1604.03083>
- Zheng, Men, "Through-Wall Tracking with Radio Tomography Networks Using Foreground Detection", IEEE WCNC 2012: <https://span.ece.utah.edu/uploads/zheng-wcnc2012-RT-nets-foreground-detection.pdf>
- Hillyard, Patwari, "Never Use Labels: Signal Strength-Based Bayesian Device-Free Localization in Changing Environments": <https://arxiv.org/abs/1812.11836>
- Ma, Muthukrishnan, Sandler, "Frugal Streaming for Estimating Quantiles": <https://arxiv.org/abs/1407.1121>
- Wang, Liu, Xu, Bu, An, "Multichannel RSS-based Device-Free Localization with Wireless Sensor Network": <https://arxiv.org/abs/1403.1170>
- Banerjee, Maas, Bocca, Patwari, Kasera, "Through Wall People Localization Exploiting Radio Windows": <https://arxiv.org/abs/1307.7233>
- Ibrahim, Gomaa, Youssef, "RadioGrapher": <https://arxiv.org/abs/1909.03551>
- Piccardi, "Background subtraction techniques: a review", IEEE SMC 2004.
- Boano et al., "Hot Packets", ExtremeCom 2013: <https://www.carloalbertoboano.com/documents/boano13extreme.pdf>
- Chelloug, temperature and humidity effects on RSSI: <https://arxiv.org/abs/1501.01073>
- Kim, Alexopoulos, Tsui, Wilson, "A Distribution-Free Tabular CUSUM Chart for Autocorrelated Data".
- Human body shadowing and channel modelling at 2.4 GHz: <https://arxiv.org/abs/1509.08071>

## Development

Run the tests in Docker:

```bash
docker build -t ripple-test tests
docker run --rm -v $PWD:/work -w /work ripple-test python -m pytest -q -p no:cacheprovider
```

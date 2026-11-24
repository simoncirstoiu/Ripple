"""Ripple v5 Zigbee interface: cluster 0xfc57 on endpoint 1, manufacturer code 0x1141 (firmware 5.0.3, 5.0.4, 5.0.5)."""
from __future__ import annotations

CLUSTER = 0xFC57
OCCUPANCY = 0x0406
ENDPOINT = 1
MANUF = 0x1141
# Firmware older than 5.0.3 is shown but never configured: its formats differ.
MIN_FW = 0x1103339C
LEGACY_MIN_FW = 0x11033342
# SENSE_API 3 = 5.0.3, 5 = 5.0.4 (new 100-row scale), 6 = 5.0.5 (adds the per-line state 0xff46).
# A mixed fleet keeps each switch on its own scale.
SENSE_API = 6
SUPPORTED_API = (3, 5, 6)
LINES_ON_API = 6

A_RAW_ENABLED = 0xFF31
A_BEACON_HZ = 0xFF39
A_CALIBRATE = 0xFF41
A_DETECT = 0xFF42
A_ZONE_STATE = 0xFF43
A_LINES_ON = 0xFF46  # bit i = line i of sources detects, reported together with 0xff43
A_SOURCES = 0xFF47
A_TUNE = 0xFF48
A_NODE_DIAG = 0xFF4B
A_LINK_A = 0xFF4C
A_LINK_B = 0xFF4D
A_LIVE = 0xFF4E
A_SENSE_API = 0xFF49
A_HOST_API = 0xFF4A
A_SELF_TUNE = 0xFF4F  # 1 (default): the 24 h self-tuning may move s, 0: it only measures
A_OCCUPANCY = 0x0000

CMD_SOURCES = 0x00
CMD_TUNE = 0x01
CMD_LIVE = 0x02
CMD_CAPTURE = 0x03

# Live: one record per sample of a streamed line, reported as 0xff4e.
# v2: q = 128 x hits of 16 / M; v3: q = 128 x weighted sum / M.
# v4: record bit 0x20 is the line's vote in its zones.
LIVE_VERSION = 4
LIVE_VERSIONS = (2, 3, 4)
LIVE_TMIN_MIN_MS = 100
LIVE_DURATION_MAX = 3600
LIVE_FRAMES_MAX = 30
LIVE_RECORDS_PER_FRAME = 10
LIVE_Q_THRESHOLD = 128

MAX_LINES = 10
MAX_ZONES = 8
NWK_MAX = 0xFFF7
BEACON_MIN, BEACON_MAX, BEACON_DEFAULT = 2, 10, 5
TUNE_VERSION = 5
TUNE_LEN = 40

# Per-line sensitivity s: 0 = parked (measured, never votes), 100 = most sensitive
S_MAX = 100
SENS_DEFAULT = 50  # the middle of the scale
SENS_DEFAULT_BY_API = {3: 89, 5: 50}
# 5.0.0 / 5.0.1 ladder byte -> s, as 5.0.3 converts it
LEGACY_S = {0x02: 89, 0x03: 89, 0x04: 86, 0x42: 85, 0x43: 83, 0x48: 82, 0x4C: 80, 0x50: 79, 0x58: 77, 0x24: 74}
# step 1-10 of the old settings format -> s on the 5.0.3 scale (the same conversion through its ladder byte)
STEP_S = {10: 89, 9: 89, 8: 86, 7: 85, 6: 83, 5: 82, 4: 80, 3: 79, 2: 77, 1: 74}
# s on the 5.0.3 scale -> s on the 5.0.4 scale, as the firmware converts it
S_FROM_3 = (0,) + (1,) * 63 + (6, 6, 12, 17, 17, 23, 28, 28, 34, 34, 34, 34, 34, 39, 39, 39,
                                39, 45, 45, 45, 45, 45, 45, 45, 45, 50, 57, 57, 64, 64, 71, 78, 78, 85, 92, 92, 100)
# 5.0.3 motion rule: a frame hits when |x - median of the 5 previous frames| >= thr dB.
# The line is ON while hits of the last 16 frames >= M.
# s 100..1 -> step 0..64 of (thr dB, M); each step raises thr or M.
MOTION_TAB = ((1, 1), (1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (2, 8),
              (2, 9), (2, 10), (2, 11), (2, 12), (3, 12), (3, 13), (3, 14), (4, 14), (4, 15),
              (4, 16)) + tuple((db, 16) for db in range(5, 51))
MOTION_PARKED_S = 70
# 5.0.4 scale: s 100..1 -> row 0..99 of (thr in 0.25 dB, M); a frame weighs min(dev x 4 / thr, 3).
# The line fires when the weighted sum of the last 16 frames holds >= M for 10 ms x (100 - s).
MOTION_TAB_5 = tuple((4, m) for m in (1,) * 8 + (2,) * 7 + (3,) * 7 + (4,) * 7 + (5,) * 7 + (6,) * 7 + (7,) * 7) + tuple(
    (q, 8) for q in (4, 5, 5, 6, 7, 8, 8, 9, 10, 11, 11, 12, 13, 14, 14, 15, 16, 16, 17, 18, 19, 19, 20, 21, 22, 22, 23,
                     24, 25, 25, 26, 27, 28, 28, 29, 30, 30, 31, 32, 33, 33, 34, 35, 36, 36, 37, 38, 39, 39, 40))

STATUS = {
    0x00: ('success', 'success'),
    0x7E: ('not_authorized', 'the device refused the command because Ripple had not declared its API (host_api) in the last 10 minutes'),
    0x80: ('malformed', 'the device refused a malformed command (wrong length)'),
    0x81: ('unsupported_command', 'the device does not support this command'),
    0x83: ('unsupported_manufacturer', 'the device refused the manufacturer code'),
    0x86: ('unsupported_attribute', 'the device does not have this attribute'),
    0x87: ('invalid_value', 'the device refused the value'),
    0x88: ('read_only', 'the attribute is read-only on the device'),
    0x93: ('not_ready', 'the device is not ready yet (just started) or a calibration is running, try again in a few seconds'),
}

LINK_BITS = (('on', 0x01), ('usable', 0x02), ('calibrated', 0x04), ('peer_known', 0x08), ('peer_on', 0x10),
             ('alive', 0x20), ('gate_fresh', 0x40), ('parked', 0x80))

# (name, offset, wide, signed, lo, hi, default, unit)
TUNE_FIELDS = (
    ('h', 1, False, False, 16, 255, 96, 'U'),
    ('heff_min', 2, False, False, 16, 255, 48, 'U'),
    ('dcap_db', 3, False, False, 1, 15, 4, 'dB'),
    ('confirm', 4, False, False, 0, 255, 0x13, 'hi nibble prev dB, lo nibble jump dB'),
    ('gate_range_q', 5, False, False, 0, 120, 8, '0.25 dB'),
    ('gate_frames', 6, False, False, 5, 8, 8, ''),
    ('gate_age_ds', 7, False, False, 5, 255, 30, '100 ms'),
    ('gate_gap_ds', 8, False, False, 5, 255, 40, '100 ms'),
    ('core_pct', 9, False, False, 1, 50, 3, '%'),
    ('core_max_bins', 10, False, False, 0, 16, 3, '0.5 fr/s'),  # Calibrate floor, 0 = off (5.0.5); 1-16 before
    ('off_s', 11, False, False, 1, 255, 30, 's'),
    ('blk_s', 12, False, False, 2, 25, 10, 's'),
    ('blk_thr_q', 13, False, False, 1, 40, 4, '0.25 dB'),
    ('hist_cap', 14, False, False, 16, 255, 127, ''),
    ('core_min_n', 15, False, False, 1, 255, 100, ''),
    ('learn_period_s', 16, False, False, 10, 255, 60, 's'),
    ('learn_every_s', 17, False, False, 1, 60, 1, 's'),
    ('b_minc', 18, False, False, 0, 255, 48, ''),
    ('rate_state_d', 19, False, False, 5, 100, 20, '0.1 fr/s'),
    ('rate_nostate_d', 20, False, False, 5, 100, 30, '0.1 fr/s'),
    ('level_min', 21, False, True, -100, -40, -88, 'dBm'),
    ('relay_skip_ds', 22, False, False, 0, 50, 15, '100 ms'),
    ('report_repeats', 23, False, False, 0, 5, 2, ''),
    ('exit_s', 24, False, False, 0, 255, 0, 's'),
    ('cal_margin', 25, False, False, 0, 34, 0, 'levels, 0 = by capture length'),  # a pad byte on 5.0.3
    ('alive_s', 26, True, False, 2, 300, 60, 's'),
    ('heartbeat_min', 28, True, False, 1, 1440, 30, 'min'),
    ('report_repeat_ms', 30, True, False, 500, 30000, 5000, 'ms'),
    ('flat_s', 32, True, False, 0, 3600, 300, 's, 0 = off'),
    ('cal_s', 34, True, False, 60, 1800, 300, 's'),
    ('quiet_q', 36, False, False, 0, 40, 4, '0.25 dB'),
    ('unl_dmin', 37, False, False, 1, 4, 2, 'dB'),
    ('off_res_db', 38, False, False, 1, 8, 4, 'dB'),
    ('off_max_db', 39, False, False, 1, 15, 8, 'dB'),
)
TUNE_DEFAULTS = {**{f[0]: f[6] for f in TUNE_FIELDS}, 'level_min': -90}
TUNE_DEFAULTS_BY_API = {5: TUNE_DEFAULTS, 3: {**TUNE_DEFAULTS, 'level_min': -88}}


def tune_defaults(api):
    return TUNE_DEFAULTS_BY_API[api_of(api)]


def status_name(code):
    return STATUS.get(code, (f'status_0x{code:02x}', ''))[0]


def status_text(code):
    return STATUS.get(code, ('', f'the device answered with ZCL status 0x{code:02x}'))[1]


def check_beacon_hz(v):
    v = int(v)
    if v != 0 and not BEACON_MIN <= v <= BEACON_MAX:
        raise ValueError(f'beacons per second must be 0 (off) or {BEACON_MIN}..{BEACON_MAX}')
    return v


def check_s(s):
    if isinstance(s, bool) or not isinstance(s, int) or not 0 <= s <= S_MAX:
        raise ValueError(f'sensitivity must be a whole number from 0 to {S_MAX}')
    return s


def s_from_legacy(byte):
    return LEGACY_S.get(byte, SENS_DEFAULT_BY_API[3])


def api_of(sense_api):
    """The scale a device runs: 5 for 5.0.4 and 5.0.5, else 3 (5.0.3, or not read yet)."""
    return 5 if sense_api in (5, 6) else 3


def has_lines_on(sense_api):
    """The device has the per-line state 0xff46 (5.0.5)."""
    return isinstance(sense_api, int) and sense_api >= LINES_ON_API


def lines_on_bits(value, n):
    """0xff46 as one bool per line of sources, in their order; None when not known."""
    return None if value is None else [bool(int(value) >> i & 1) for i in range(n)]


def sens_default(api):
    return SENS_DEFAULT_BY_API[api_of(api)]


def s_to_api(s, from_api, to_api):
    """s of one scale on another: 5.0.3 -> 5.0.4 as the firmware converts it; never back."""
    if api_of(from_api) == 3 and api_of(to_api) == 5:
        return SENS_DEFAULT if not 0 <= s <= S_MAX else S_FROM_3[s]
    return s


def sources_from_legacy(b):
    """sources of a 5.0.0 / 5.0.1 device with each ladder byte replaced by its s, for display and adoption only."""
    b = bytearray(b or b'')
    for i in range(3, len(b) - len(b) % 4, 4):
        b[i] = s_from_legacy(b[i])
    return bytes(b)


def motion_params(s, api=3):
    """(thr dB, M) of s 0-100 on the 5.0.3 scale (s 0 = parked, measured at s 70); on the 5.0.4 scale (thr in 0.25 dB, M),
    s 0 measured at the default 50."""
    tab = MOTION_TAB_5 if api_of(api) == 5 else MOTION_TAB
    s = int(s) or (SENS_DEFAULT if api_of(api) == 5 else MOTION_PARKED_S)
    i = 0 if s >= S_MAX else ((S_MAX - s) * (len(tab) - 1) + (S_MAX - 1) // 2) // (S_MAX - 1)
    return tab[i]


def weight(dev_db, thr_q4):
    """Weight of a stored frame, min(dev x 4 / thr, 3), dev in whole dB, thr in 0.25 dB."""
    return min(3, int(dev_db) * 4 // thr_q4)


def meter_s(dev_db):
    """Live meter: the lowest s at which this deviation, held 3 stored frames, fires (3 x w >= M); 100 when nowhere.
    A 30 dB loss reads 1, 3 dB 50, 1 dB 79, 0 dB 100."""
    for s in range(1, S_MAX + 1):
        q, m = motion_params(s, 5)
        if 3 * weight(dev_db, q) >= m:
            return s
    return S_MAX


def encode_sources(lines):
    """lines: [(nwk, zones, s)]; refuses what the firmware would refuse (status 0x87)."""
    if len(lines) > MAX_LINES:
        raise ValueError(f'a device takes at most {MAX_LINES} lines')
    seen = set()
    out = bytearray()
    for nwk, zones, sens in lines:
        if nwk is None or not 0 <= int(nwk) <= NWK_MAX:
            raise ValueError(f'invalid sender address {nwk!r}')
        check_s(sens)
        if nwk in seen:
            raise ValueError(f'sender 0x{nwk:04x} is twice on the same device')
        seen.add(nwk)
        out += int(nwk).to_bytes(2, 'little') + bytes([zones & 0xFF, sens & 0xFF])
    return bytes(out)


def decode_sources(b):
    if b is None:
        return None
    b = bytes(b)
    return [{'nwk': int.from_bytes(b[i:i + 2], 'little'), 'zones': b[i + 2], 'sens': b[i + 3]}
            for i in range(0, len(b) - len(b) % 4, 4)]


def decode_tune(b):
    b = bytes(b or b'')
    if len(b) != TUNE_LEN:
        return None
    out = {'version': b[0]}
    for name, off, wide, signed, *_ in TUNE_FIELDS:
        v = int.from_bytes(b[off:off + 2], 'little') if wide else b[off]
        out[name] = v - 256 if signed and v > 127 else v
    return out


def validate_tune(values, api=5):
    """Same checks as the firmware; returns a list of errors (empty = valid).
    On 5.0.3 byte 25 is a pad byte that must be 0."""
    errs = []
    if api_of(api) == 3 and values.get('cal_margin'):
        errs.append('cal_margin: this device runs firmware 5.0.3, which has no calibration margin (must be 0)')
    if values.get('core_max_bins') == 0 and not (isinstance(api, int) and api >= LINES_ON_API):
        errs.append('core_max_bins: 0 (floor off) needs firmware 5.0.5; this device takes 1..16')
    for name, _, wide, _, lo, hi, *_ in TUNE_FIELDS:
        v = values.get(name)
        if not isinstance(v, int) or isinstance(v, bool):
            errs.append(f'{name}: a whole number is required')
        elif not lo <= v <= hi:
            errs.append(f'{name}: must be {lo}..{hi}')
        elif wide and v > 0x7FFF:
            errs.append(f'{name}: must be at most 32767')
    if errs:
        return errs
    if values['core_min_n'] >= values['hist_cap']:
        errs.append('core_min_n must be smaller than hist_cap')
    if values['gate_age_ds'] > values['gate_gap_ds']:
        errs.append('gate_age_ds must not exceed gate_gap_ds')
    if values['rate_state_d'] > values['rate_nostate_d']:
        errs.append('rate_state_d must not exceed rate_nostate_d')
    if values['confirm'] >> 4 == 0:
        errs.append('confirm: the high nibble must not be 0')
    return errs


def encode_tune(values, api=5):
    values = {'cal_margin': 0, **values}
    errs = validate_tune(values, api)
    if errs:
        raise ValueError('; '.join(errs))
    b = bytearray(TUNE_LEN)
    b[0] = TUNE_VERSION
    for name, off, wide, signed, *_ in TUNE_FIELDS:
        v = values[name]
        if wide:
            b[off:off + 2] = v.to_bytes(2, 'little')
        else:
            b[off] = v & 0xFF
    return bytes(b)


def _u16(b, i):
    return int.from_bytes(b[i:i + 2], 'little')


def decode_node_diag(b):
    """Data of 0xff4b without its length byte (17 B)."""
    b = bytes(b or b'')
    if len(b) < 17:
        return None
    f = b[3]
    return {'lines': b[0], 'usable': b[1], 'zone_state': b[2], 'flags': f, 'uncalibrated': bool(f & 0x01),
            'calibrating': bool(f & 0x02), 'relay_on': bool(f & 0x80), 'last_on_line': None if b[4] == 0xFF else b[4],
            'last_on_s': b[5], 'stack_used': _u16(b, 6), 'calibrate_remaining': _u16(b, 8), 'tune_version': b[10],
            'dropped': _u16(b, 11), 'beacons_skipped': _u16(b, 13), 'zcl_init_overflow': b[15],
            'last_on_gate_ds': None if b[16] == 0xFF else b[16]}


def decode_link_diag(b, api=3):
    """Data of 0xff4c or 0xff4d without its length byte: 5 entries of 9 B (8 B before 5.0.2), unused slots are zeros.
    From 5.0.4 byte 2 is the weighted sum and byte 4 the threshold in 0.25 dB."""
    b = bytes(b or b'')
    q4 = api_of(api) == 5
    size = 9 if len(b) % 9 == 0 and len(b) % 8 else 8
    out = []
    for k in range(len(b) // size):
        e = b[k * size:k * size + size]
        st = e[3]
        out.append({'level_dbm': e[0] - 256 if e[0] > 127 else e[0], 'rate_d': e[1], 'status': st,
                    **{n: bool(st & m) for n, m in LINK_BITS}, 'flat_age_4s': e[6],
                    'gate_age_ds': None if e[7] == 255 else e[7],
                    # 5.0.3: hits of the last 16 stored frames, thr dB and M of the line's s
                    'hits': e[2] if size == 9 else None,
                    'thr_db': (e[4] / 4 if q4 else e[4]) if size == 9 else None,
                    'm': e[5] if size == 9 else None,
                    'capture_width': e[8] >> 4 if size == 9 else None, 'b_cal': e[8] & 0x0F if size == 9 else None})
    return out


def encode_live(duration_s, tmin_ms, lines):
    """Command 0x02: duration_s u16 (0 = stop), tmin u8 in 10 ms, then (NWK u16, candidate s 1-100 or 0) per line."""
    duration_s = int(duration_s)
    if not 0 <= duration_s <= LIVE_DURATION_MAX:
        raise ValueError(f'Live lasts 0..{LIVE_DURATION_MAX} s')
    tmin = max(LIVE_TMIN_MIN_MS, int(tmin_ms)) // 10
    if duration_s and not lines:
        raise ValueError('Live needs at least one line')
    if len(lines) > MAX_LINES:
        raise ValueError(f'a device has at most {MAX_LINES} lines')
    out = bytearray(duration_s.to_bytes(2, 'little') + bytes([min(255, tmin)]))
    for nwk, cand in lines:
        if cand:
            check_s(cand)
        out += int(nwk).to_bytes(2, 'little') + bytes([cand or 0])
    return bytes(out)


def encode_capture(nwks):
    """Command 0x03: NWK u16 per line of the receiver to capture; empty = every line."""
    if len(nwks) > MAX_LINES:
        raise ValueError(f'a device has at most {MAX_LINES} lines')
    seen = set()
    out = bytearray()
    for nwk in nwks:
        if nwk is None or not 0 <= int(nwk) <= NWK_MAX:
            raise ValueError(f'invalid sender address {nwk!r}')
        if nwk in seen:
            raise ValueError(f'sender 0x{nwk:04x} is listed twice')
        seen.add(nwk)
        out += int(nwk).to_bytes(2, 'little')
    return bytes(out)


def decode_live(b):
    """Data of 0xff4e without its length byte: header 8 B, n records of 5 B, then info entries of 6 B."""
    b = bytes(b or b'')
    if len(b) < 8 or b[0] not in LIVE_VERSIONS:
        return None
    n_rec, n_info = b[3] & 0x0F, b[3] >> 4
    if len(b) < 8 + n_rec * 5 + n_info * 6:
        return None
    first_ms = int.from_bytes(b[4:8], 'little')
    recs, info = [], []
    for k in range(n_rec):
        r = b[8 + k * 5:13 + k * 5]
        v4 = b[0] >= 4
        recs.append({'idx': r[0] & 0x0F, 'on': bool(r[0] & 0x10), 'gate': None if v4 else bool(r[0] & 0x20),
                     'vote': bool(r[0] & 0x20) if v4 else None, 'usable': bool(r[0] & 0x40),
                     'preview': bool(r[0] & 0x80), 'ms': first_ms + r[1] * 10,
                     'q': r[2], 'q2': r[3], 'd': r[4]})
    o = 8 + n_rec * 5
    for k in range(n_info):
        e = b[o + k * 6:o + k * 6 + 6]
        age = _u16(e, 4)
        info.append({'idx': e[0], 'state': e[1], 'm': _u16(e, 2), 'since_on_s': None if age == 0xFFFF else age})
    return {'version': b[0], 'seq': b[1], 'dropped': b[2], 'first_ms': first_ms, 'records': recs, 'info': info}

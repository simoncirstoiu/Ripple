"""Firmware attribute map: one table per sensing firmware profile (v5: cluster 0xfc57, manufacturer 0x1141)."""
from . import v5

U8, U16, U32, OCT, CHR, BMP8, BMP16 = 0x20, 0x21, 0x23, 0x41, 0x42, 0x18, 0x19
SW_BUILD_ID = 0x4000
RIPPLE_MARKER = 'ripple'
ZONE_ROOM = 0x01


def _a(key, attr, typ, access='r', cluster=v5.CLUSTER, **kw):
    return dict(key=key, id=attr, type=typ, access=access, cluster=cluster, **kw)


# Tune fields shown in other units: UI value * scale = firmware value.
_TUNE_UNITS = {'0.25 dB': ('dB', 4), '100 ms': ('s', 10), '0.1 fr/s': ('/s', 10), 's, 0 = off': ('s', 1),
               'U': ('', 1), 'bins': ('', 1), '0.5 fr/s': ('fr/s', 2)}
# Fields whose meaning changed get a new key, so an old saved value is never sent with the new meaning.
TUNE_KEYS = {'core_max_bins': 'cal_min_rate'}
# off_s and cal_s have their own controls.
TUNE_OWN = {'off_s': 'off_s', 'cal_s': 'cal_s'}
# Unused by firmware 5.0.3 and later; kept in the 40 B tune as the device stores them, no control in the UI.
TUNE_UNUSED = ('h', 'heff_min', 'dcap_db', 'confirm', 'gate_range_q', 'gate_frames', 'core_min_n', 'learn_period_s',
               'learn_every_s', 'exit_s', 'flat_s', 'unl_dmin')


# Plain meaning of each tune value; entity names are in strings.json.
TUNE_HELP = {
    'gate_age_ds': 'How long one such movement stays valid. At most "Forget recent packets after a silence of".',
    'gate_gap_ds': 'If no packet arrives for this long, the movement check starts over.',
    'core_pct': 'A signal level seen in at least this share of the empty-room packets counts as normal empty.',
    'cal_min_rate': 'Minimum capture rate for Calibrate to set a line above sensitivity 49: a line that stored fewer '
                    'packets per second during the capture stays at 49 at most. 0 = no floor. Firmware 5.0.5; '
                    '5.0.4 does not read it; on 5.0.3 it is the old empty-room width limit (value x 2 = 1 dB steps).',
    'cal_margin': 'Calibrate puts the slider this many levels below the most sensitive point the empty room allows. '
                  '0 = chosen by the calibration length (longer is safer). Not on firmware 5.0.3.',
    'blk_s': 'Length of the averaging block used for the average, the packet rate and the "did it move" check.',
    'blk_thr_q': 'A change of the block average this large counts as movement.',
    'hist_cap': 'Memory of the calibration. When a level reaches this count, every count is halved.',
    'b_minc': 'Scale of the noise allowance computed from the calibration. Higher ignores more of the line\'s own noise, '
              'so it is less sensitive.',
    'rate_state_d': 'Fewest packets per second for a line to vote, when the sender relay state is known.',
    'rate_nostate_d': 'Same, when the sender relay state is unknown. At least the value above.',
    'level_min': 'A line weaker than this does not vote.',
    'relay_skip_ds': 'Packets are ignored for this long around a relay toggle, on this device or on the sender.',
    'report_repeats': 'Re-sends of a presence change if Home Assistant does not confirm it.',
    'alive_s': 'A line not heard for this long stops voting. A sender relay state is trusted for this long.',
    'heartbeat_min': 'Sends the presence state again at least this often, even with no change.',
    'report_repeat_ms': 'Wait between those re-sends.',
    'quiet_q': 'The relay effect is learned only from a calm block (range up to this much).',
    'off_res_db': 'A larger correction is refused as "someone moved".',
    'off_max_db': 'Largest relay effect that can be learned.',
}
# Sections of the fine tuning card.
TUNE_SECTIONS = {
    'gate': ('gate_age_ds', 'gate_gap_ds'),
    'learning': ('core_pct', 'cal_min_rate', 'blk_s', 'blk_thr_q', 'hist_cap', 'b_minc', 'cal_margin'),
    'voting': ('rate_state_d', 'rate_nostate_d', 'level_min', 'alive_s'),
    'relays': ('relay_skip_ds', 'quiet_q', 'off_res_db', 'off_max_db'),
    'reporting': ('report_repeats', 'report_repeat_ms', 'heartbeat_min'),
}
TUNE_SECTION = {k: sec for sec, keys in TUNE_SECTIONS.items() for k in keys}


def _adv(name, off, wide, signed, lo, hi, default, unit):
    ui, scale = _TUNE_UNITS.get(unit, (unit, 1))
    key = TUNE_KEYS.get(name, name)
    return _a(key, v5.A_TUNE, OCT, 'rw', min=lo / scale, max=hi / scale, step=1 / scale, unit=ui,
              default=default / scale, scale=scale, group='tune', field=name, help=TUNE_HELP[key],
              section=TUNE_SECTION[key])


V5_ADVANCED = [_adv(*f) for f in v5.TUNE_FIELDS if f[0] not in TUNE_OWN and f[0] not in TUNE_UNUSED]


def tune_value(a, tune):
    """Firmware value of one advanced setting, read from a decoded tune."""
    return tune[a['field']]


def firmware_name(a):
    """Name of the value in the firmware tune, for the people who read the firmware code."""
    return a['field']


def _tune_put(t, a, v):
    t[a['field']] = v

V5_STATUS = [
    _a('occupancy', v5.A_OCCUPANCY, BMP8, cluster=v5.OCCUPANCY), _a('cal_left', v5.A_CALIBRATE, U16, 'rw'),
    _a('node_diag', v5.A_NODE_DIAG, OCT), _a('link_a', v5.A_LINK_A, OCT), _a('link_b', v5.A_LINK_B, OCT),
    _a('raw_enabled', v5.A_RAW_ENABLED, U8, 'rw'), _a('sense_api', v5.A_SENSE_API, U8),
    _a('lines_on', v5.A_LINES_ON, BMP16, min_api=v5.LINES_ON_API),  # 5.0.5+, read after sense_api
]

# Values the room/device settings produce (see derive_v5); sources and tune are sent as commands.
V5_DERIVED = [
    _a('detect', v5.A_DETECT, U8, 'rw'), _a('beacon_hz', v5.A_BEACON_HZ, U8, 'rw'),
    _a('self_tune', v5.A_SELF_TUNE, U8, 'rw'),  # 5.0.4+
    _a('sources', v5.A_SOURCES, OCT, cmd=v5.CMD_SOURCES), _a('tune', v5.A_TUNE, OCT, cmd=v5.CMD_TUNE),
]

SWITCH_DEFAULTS = dict(off_s=30, beacon_hz=v5.BEACON_DEFAULT, detect=True, cal_s=300)


def decode_tune(b):
    t = v5.decode_tune(b)
    return t if t and t['version'] == v5.TUNE_VERSION else None


def tune_with(base, settings, api=v5.SENSE_API):
    """Tune values from the device tune with the device settings applied; raises ValueError like the firmware."""
    t = {k: base[k] for k in v5.TUNE_DEFAULTS}
    for field, key in TUNE_OWN.items():
        if settings.get(key) is not None:
            t[field] = int(settings[key])
    for a in V5_ADVANCED:
        v = (settings.get('advanced') or {}).get(a['key'])
        if v is not None:
            _tune_put(t, a, int(round(float(v) * a['scale'])))
    # Default level_min moved from -88 to -90 in 5.0.4; replace the old default unless the user set it.
    if (v5.api_of(api) == 5 and t['level_min'] == v5.TUNE_DEFAULTS_BY_API[3]['level_min']
            and (settings.get('advanced') or {}).get('level_min') is None):
        t['level_min'] = v5.TUNE_DEFAULTS['level_min']
    errs = v5.validate_tune(t, api)
    if errs:
        raise ValueError('; '.join(errs))
    return t


def derive_v5(settings, lines, cfg):
    """Firmware values for one device from its settings, its lines [(nwk, zones, sens)] and the tune it holds."""
    out = {}
    if 'detect' in settings:
        out['detect'] = 1 if settings['detect'] else 0
    if 'beacon_hz' in settings:
        out['beacon_hz'] = v5.check_beacon_hz(settings['beacon_hz'])
    if settings.get('self_tune') is not None and v5.api_of(cfg.get('sense_api')) == 5:
        out['self_tune'] = 1 if settings['self_tune'] else 0
    out['sources'] = v5.encode_sources(lines)
    base = decode_tune(cfg.get('tune'))
    if base:
        api = cfg.get('sense_api')
        out['tune'] = v5.encode_tune(tune_with(base, settings, api), api)
    return out


def settings_from_device_v5(cfg):
    """Inverse of derive_v5 for adoption; None until detect, beacon_hz and tune were read."""
    t = decode_tune(cfg.get('tune'))
    if t is None or cfg.get('detect') is None or cfg.get('beacon_hz') is None:
        return None
    out = {'off_s': t['off_s'], 'cal_s': t['cal_s'], 'beacon_hz': cfg['beacon_hz'], 'detect': bool(cfg['detect']),
           'advanced': {}}
    if cfg.get('self_tune') is not None:
        out['self_tune'] = bool(cfg['self_tune'])
    for a in V5_ADVANCED:
        if tune_value(a, t) != tune_value(a, v5.tune_defaults(cfg.get('sense_api'))):
            out['advanced'][a['key']] = tune_value(a, t) / a['scale']
    return out


def decode_flags(v, api=3):
    """node_diag flags: bit0 a line is not calibrated, bit1 calibrating.
    Since 5.0.4 a line works without calibration, so bit0 is ignored there."""
    v = v or 0
    return {'needs_calibration': bool(v & 1) and v5.api_of(api) == 3, 'calibrating': bool(v & 2), 'refused': False,
            'table_truncated': False}


V5 = dict(
    id='v5', label='Ripple v5 (per-line detector)',
    status=V5_STATUS, derived=V5_DERIVED, advanced=V5_ADVANCED,
    include_slots=v5.MAX_LINES, calibrate=v5.A_CALIBRATE, cal_min=60, cal_max=1800,
    derive=derive_v5, adopt=settings_from_device_v5,
    decoders={'sources': v5.decode_sources, 'tune': decode_tune, 'node_diag': v5.decode_node_diag,
              'link_a': v5.decode_link_diag, 'link_b': v5.decode_link_diag, 'flags': decode_flags},
)

PROFILES = {p['id']: p for p in (V5,)}


def all_attrs(profile):
    return profile['status'] + profile['derived'] + profile['advanced']


def attr_by_key(profile, key):
    for a in all_attrs(profile):
        if a['key'] == key:
            return a
    raise KeyError(key)


def encode_check(typ, value):
    """Range check before a write; raises ValueError."""
    limits = {U8: 0xFF, U16: 0xFFFF, U32: 0xFFFFFFFF}
    if typ not in limits or not 0 <= int(value) <= limits[typ]:
        raise ValueError(f'value {value} does not fit type 0x{typ:02x}')
    return int(value)

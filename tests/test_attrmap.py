import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from custom_components.ripple_presence import attrmap as am  # noqa: E402
from custom_components.ripple_presence import v5  # noqa: E402

TUNE = v5.encode_tune(v5.TUNE_DEFAULTS)
CFG = {'tune': TUNE, 'detect': 0, 'beacon_hz': 5, 'sources': b''}


def test_advanced_tune_fields_no_hold_cal():
    keys = [a['key'] for a in am.V5_ADVANCED]
    assert len(keys) == len(v5.TUNE_FIELDS) - 2 - len(am.TUNE_UNUSED) and not {'exit_s', 'cal_s', 'off_s'} & set(keys)
    assert not set(am.TUNE_UNUSED) & set(keys)
    assert not {'h', 'heff_min', 'dcap_db', 'confirm', 'gate_range_q', 'gate_frames', 'unl_dmin'} & set(keys)
    assert all(a['id'] == v5.A_TUNE for a in am.V5_ADVANCED)


def test_scaled_ranges_exactly_fw_ranges():
    by = {a['key']: a for a in am.V5_ADVANCED}
    assert (by['quiet_q']['min'], by['quiet_q']['max'], by['quiet_q']['unit']) == (0, 10, 'dB')
    assert (by['gate_age_ds']['min'], by['gate_age_ds']['max'], by['gate_age_ds']['unit']) == (0.5, 25.5, 's')
    assert (by['rate_state_d']['min'], by['rate_state_d']['max'], by['rate_state_d']['step']) == (0.5, 10, 0.1)
    assert (by['level_min']['min'], by['level_min']['max'], by['level_min']['default']) == (-100, -40, -88)


def test_derive_maps_settings_attributes():
    out = am.derive_v5({'detect': True, 'beacon_hz': 0, 'off_s': 45, 'cal_s': 900, 'advanced': {'quiet_q': 1.5}},
                       [(0x1234, 1, 89)], CFG)
    assert (out['detect'], out['beacon_hz']) == (1, 0)
    assert out['sources'] == bytes([0x34, 0x12, 0x01, 89])
    t = v5.decode_tune(out['tune'])
    assert (t['off_s'], t['cal_s'], t['quiet_q'], t['exit_s'], t['version']) == (45, 900, 6, 0, 5)


def test_derive_no_tune_read_sends_no_tune():
    assert 'tune' not in am.derive_v5({}, [], {})


def test_adopt_is_inverse_of_derive():
    cfg = dict(CFG, tune=am.derive_v5({'off_s': 20, 'advanced': {'level_min': -80}}, [], CFG)['tune'])
    s = am.settings_from_device_v5(cfg)
    assert v5.decode_tune(cfg['tune'])['off_s'] == 20
    assert s == {'off_s': 20, 'cal_s': 300, 'beacon_hz': 5, 'detect': False, 'advanced': {'level_min': -80}}
    assert am.settings_from_device_v5({'tune': TUNE}) is None


def test_tune_fields_unused_503_kept_switch():
    t = dict(v5.decode_tune(TUNE), confirm=0x25, gate_frames=5, exit_s=9)
    out = am.derive_v5({'off_s': 40, 'advanced': {'level_min': -80}}, [], dict(CFG, tune=v5.encode_tune(t)))
    d = v5.decode_tune(out['tune'])
    assert (d['confirm'], d['gate_frames'], d['exit_s'], d['off_s'], d['level_min']) == (0x25, 5, 9, 40, -80)


def test_every_advanced_setting_has_plain():
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, '..', 'custom_components', 'ripple_presence', 'strings.json')) as f:
        names = json.load(f)['entity']['number']
    for a in am.V5_ADVANCED:
        name = names[f"adv_{a['key']}"]['name']
        assert a['help'] and a['field'] not in name and '_' not in name


def test_tune_cross_checks_refused():
    with pytest.raises(ValueError):
        am.tune_with(v5.decode_tune(TUNE), {'advanced': {'gate_age_ds': 5}})
    with pytest.raises(ValueError):
        am.tune_with(v5.decode_tune(TUNE), {'off_s': 256})
    with pytest.raises(ValueError):
        am.tune_with(v5.decode_tune(TUNE), {'advanced': {'rate_state_d': 4}})


def test_wrong_tune_version_is_not_used():
    bad = bytes([4]) + TUNE[1:]
    assert am.decode_tune(bad) is None


def test_flags_from_node_diag():
    assert am.decode_flags(0x83) == {'needs_calibration': True, 'calibrating': True, 'refused': False,
                                     'table_truncated': False}
    assert am.decode_flags(None)['calibrating'] is False


def test_encode_check():
    assert am.encode_check(am.U16, 1) == 1
    with pytest.raises(ValueError):
        am.encode_check(am.U8, 256)
    with pytest.raises(ValueError):
        am.encode_check(am.OCT, 1)


def test_every_fw_setting_has_place_ui():
    """Every tune value read by firmware 5.0.3 has a control; the ones it no longer reads have none."""
    owned = set(am.TUNE_OWN)
    fields = {a['field'] for a in am.V5_ADVANCED}
    assert {f[0] for f in v5.TUNE_FIELDS} == owned | fields | set(am.TUNE_UNUSED)
    assert not fields & set(am.TUNE_UNUSED)
    assert all(a['section'] in am.TUNE_SECTIONS for a in am.V5_ADVANCED)
    keys = [k for ks in am.TUNE_SECTIONS.values() for k in ks]
    assert sorted(keys) == sorted(a['key'] for a in am.V5_ADVANCED)


def test_panel_names_match_entity_names():
    import re
    base = os.path.join(os.path.dirname(__file__), '..', 'custom_components', 'ripple_presence')
    names = json.load(open(os.path.join(base, 'strings.json')))['entity']['number']
    js = open(os.path.join(base, 'frontend', 'ripple-panel.js')).read()
    for a in am.V5_ADVANCED:
        m = re.search(rf"\['{a['key']}', '((?:[^'\\]|\\.)*)', '", js)
        assert m and m.group(1) == names[f"adv_{a['key']}"]['name'], a['key']


def test_level_min_moves_to_new_default_after_ota():
    base = v5.decode_tune(v5.encode_tune(v5.tune_defaults(3), 3))
    assert base['level_min'] == -88
    assert am.tune_with(base, {}, 5)['level_min'] == -90
    assert am.tune_with(base, {}, 3)['level_min'] == -88
    assert am.tune_with(base, {'advanced': {'level_min': -88}}, 5)['level_min'] == -88


def test_core_max_bins_cal_floor_fr_s():
    # 5.0.5: the byte is the minimum capture rate in 0.5 fr/s; a new key, so no value of the old meaning is sent
    a = am.attr_by_key(am.V5, 'cal_min_rate')
    assert (a['field'], a['scale'], a['min'], a['max'], a['step'], a['default'], a['unit']) == (
        'core_max_bins', 2, 0, 8, 0.5, 1.5, 'fr/s')
    assert 'core_max_bins' not in [x['key'] for x in am.V5_ADVANCED]
    assert am.firmware_name(a) == 'core_max_bins'
    t = am.tune_with(v5.tune_defaults(6), {'advanced': {'cal_min_rate': 0}}, 6)
    assert t['core_max_bins'] == 0
    with pytest.raises(ValueError):
        am.tune_with(v5.tune_defaults(5), {'advanced': {'cal_min_rate': 0}}, 5)


def test_lines_on_is_read_only_from_api_6():
    a = am.attr_by_key(am.V5, 'lines_on')
    assert (a['id'], a['type'], a['access'], a['min_api']) == (v5.A_LINES_ON, am.BMP16, 'r', 6)

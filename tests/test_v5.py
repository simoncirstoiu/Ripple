import pytest

from custom_components.ripple_presence import v5

DEFAULT_TUNE_HEX = ('05 60 30 04 13 08 08 1E 28 03 03 1E 0A 04 7F 64 3C 01 30 14 1E A8 0F 02 00 00 3C 00 1E 00 88 13 '
                    '2C 01 2C 01 04 02 04 08')
# 5.0.4 (tune_defaults): level_min -90 (byte 21), cal_margin 0 in the old pad byte 25
DEFAULT_TUNE_107_HEX = DEFAULT_TUNE_HEX.replace(' 1E A8 0F ', ' 1E A6 0F ')


def test_default_tune_matches_fw_octet():
    assert v5.encode_tune(v5.tune_defaults(3), 3) == bytes.fromhex(DEFAULT_TUNE_HEX)
    assert v5.encode_tune(v5.TUNE_DEFAULTS) == bytes.fromhex(DEFAULT_TUNE_107_HEX)


def test_cal_margin_only_on_504():
    t = {**v5.TUNE_DEFAULTS, 'cal_margin': 5}
    assert v5.encode_tune(t)[25] == 5
    with pytest.raises(ValueError):
        v5.encode_tune(t, 3)
    with pytest.raises(ValueError):
        v5.encode_tune({**t, 'cal_margin': 35})


def test_scale_meter_and_conversion_match_firmware():
    assert [v5.meter_s(d) for d in (30, 3, 2, 1, 0)] == [1, 50, 58, 79, 100]
    assert v5.motion_params(100, 5) == (4, 1) and v5.motion_params(50, 5) == (4, 8) and v5.motion_params(1, 5) == (40, 8)
    assert v5.s_to_api(89, 3, 5) == 50 and v5.s_to_api(70, 3, 5) == 28 and v5.s_to_api(0, 3, 5) == 0
    assert v5.s_to_api(50, 5, 5) == 50
    rows = [v5.motion_params(s, 5) for s in range(100, 0, -1)]
    assert all(a[0] <= b[0] and a[1] <= b[1] for a, b in zip(rows, rows[1:]))  # thr and M never fall as s falls


def test_tune_round_trip_and_signed_level():
    t = v5.decode_tune(bytes.fromhex(DEFAULT_TUNE_HEX))
    assert t['version'] == 5 and t['level_min'] == -88 and t['cal_s'] == 300 and t['report_repeat_ms'] == 5000
    assert v5.encode_tune({k: t[k] for k in v5.TUNE_DEFAULTS}) == bytes.fromhex(DEFAULT_TUNE_HEX)
    assert v5.decode_tune(b'\x05' * 39) is None


@pytest.mark.parametrize('change, error', [
    ({'h': 15}, 'h: must be 16..255'),
    ({'level_min': -39}, 'level_min: must be -100..-40'),
    ({'cal_s': 1801}, 'cal_s: must be 60..1800'),
    ({'core_min_n': 127}, 'core_min_n must be smaller than hist_cap'),
    ({'gate_age_ds': 41}, 'gate_age_ds must not exceed gate_gap_ds'),
    ({'rate_state_d': 31}, 'rate_state_d must not exceed rate_nostate_d'),
    ({'confirm': 0x0F}, 'confirm: the high nibble must not be 0'),
    ({'alive_s': 1.5}, 'alive_s: a whole number is required'),
])
def test_tune_checks_match_firmware(change, error):
    assert error in v5.validate_tune({**v5.TUNE_DEFAULTS, **change})
    with pytest.raises(ValueError):
        v5.encode_tune({**v5.TUNE_DEFAULTS, **change})


def test_tune_pad_byte_and_version():
    b = v5.encode_tune(v5.TUNE_DEFAULTS)
    assert len(b) == 40 and b[0] == 5 and b[25] == 0


def test_sources_layout():
    assert v5.encode_sources([(0x1A02, 0b101, 0x03), (0x0000, 0, 0x24)]) == bytes([0x02, 0x1A, 0x05, 0x03, 0, 0, 0, 0x24])
    assert v5.encode_sources([]) == b''
    assert v5.decode_sources(bytes([0x02, 0x1A, 0x05, 0x03])) == [{'nwk': 0x1A02, 'zones': 5, 'sens': 3}]


@pytest.mark.parametrize('lines', [
    [(i, 1, 3) for i in range(11)],
    [(0xFFF8, 1, 3)],
    [(1, 1, 101)],
    [(1, 1, 255)],
    [(1, 1, True)],
    [(1, 1, 3), (1, 2, 3)],
    [(None, 1, 3)],
])
def test_sources_refused_like_firmware(lines):
    with pytest.raises(ValueError):
        v5.encode_sources(lines)


def test_sens_s():
    assert v5.SENS_DEFAULT == 50 and v5.SENS_DEFAULT_BY_API[3] == 89 and v5.check_s(0) == 0 and v5.check_s(100) == 100
    for bad in (-1, 101, 7.5, None, True):
        with pytest.raises(ValueError):
            v5.check_s(bad)
    assert v5.encode_sources([(1, 0, 0), (2, 1, 100)]) == bytes([1, 0, 0, 0, 2, 0, 1, 100])


def test_legacy_ladder_bytes_map_like_firmware():
    """sens_from_legacy of 5.0.3: the 5.0.x ladder bytes keep the (thr, M) they ran on 5.0.2."""
    assert [v5.s_from_legacy(b) for b in (0x02, 0x03, 0x04, 0x42, 0x43, 0x48, 0x4C, 0x50, 0x58, 0x24)] == \
        [89, 89, 86, 85, 83, 82, 80, 79, 77, 74]
    assert v5.s_from_legacy(0x05) == v5.s_from_legacy(0x00) == v5.s_from_legacy(0xFF) == 89
    assert v5.STEP_S[9] == 89 and v5.STEP_S[1] == 74
    raw = bytes([0x02, 0x1A, 0x01, 0x03, 0x03, 0x1A, 0x00, 0x24])
    assert v5.decode_sources(v5.sources_from_legacy(raw)) == [{'nwk': 0x1A02, 'zones': 1, 'sens': 89},
                                                              {'nwk': 0x1A03, 'zones': 0, 'sens': 74}]


@pytest.mark.parametrize('s, params', [
    # (thr dB, M) printed by the 5.0.3 firmware for every s
    (100, (1, 1)), (99, (1, 2)), (90, (1, 7)), (89, (1, 8)), (88, (2, 8)), (70, (5, 16)), (50, (18, 16)),
    (30, (31, 16)), (2, (49, 16)), (1, (50, 16)), (0, (5, 16)),
])
def test_motion_params_match_firmware(s, params):
    assert v5.motion_params(s) == params


def test_motion_chain_is_monotone():
    """65 points, each step down raises thr or M and never lowers either."""
    assert len(v5.MOTION_TAB) == 65 and v5.MOTION_TAB[0] == (1, 1) and v5.MOTION_TAB[-1] == (50, 16)
    for (d0, m0), (d1, m1) in zip(v5.MOTION_TAB, v5.MOTION_TAB[1:]):
        assert d1 >= d0 and m1 >= m0 and (d1, m1) != (d0, m0)
    ps = [v5.motion_params(s) for s in range(100, 0, -1)]
    assert all(b[0] >= a[0] and b[1] >= a[1] for a, b in zip(ps, ps[1:]))
    assert v5.motion_params(0) == v5.motion_params(v5.MOTION_PARKED_S)


def test_node_diag():
    b = bytes([3, 2, 0b101, 0x83, 1, 40, 0x10, 0x02, 0x2C, 0x01, 5, 0xFF, 0xFF, 7, 0, 0, 12])
    d = v5.decode_node_diag(b)
    assert d['lines'] == 3 and d['usable'] == 2 and d['zone_state'] == 5
    assert d['uncalibrated'] and d['calibrating'] and d['relay_on']
    assert d['last_on_line'] == 1 and d['stack_used'] == 0x0210 and d['calibrate_remaining'] == 300
    assert d['tune_version'] == 5 and d['dropped'] == 0xFFFF and d['beacons_skipped'] == 7 and d['last_on_gate_ds'] == 12
    assert v5.decode_node_diag(b[:10]) is None


def test_link_diag():
    entry = bytes([(-71) & 0xFF, 55, 9, 0x01 | 0x02 | 0x04 | 0x20 | 0x80, 3, 8, 2, 255, 0x23])
    d = v5.decode_link_diag(entry + bytes(36))
    assert len(d) == 5 and d[0]['level_dbm'] == -71 and d[0]['rate_d'] == 55
    assert d[0]['on'] and d[0]['usable'] and d[0]['calibrated'] and d[0]['alive'] and d[0]['parked']
    assert not d[0]['peer_known'] and d[0]['gate_age_ds'] is None
    assert d[0]['hits'] == 9 and d[0]['thr_db'] == 3 and d[0]['m'] == 8 and d[0]['flat_age_4s'] == 2
    assert d[0]['capture_width'] == 2 and d[0]['b_cal'] == 3
    assert d[1]['status'] == 0


def test_link_diag_5_0_1_has_8_bytes_per_line():
    entry = bytes([(-60) & 0xFF, 40, 5, 0x27, 4, 30, 0, 12])
    d = v5.decode_link_diag(entry * 2 + bytes(24))
    assert len(d) == 5 and d[1]['level_dbm'] == -60 and d[1]['hits'] is None and d[1]['b_cal'] is None


def test_capture_layout():
    assert v5.CMD_CAPTURE == 0x03
    assert v5.encode_capture([0x1444]) == bytes([0x44, 0x14])
    assert v5.encode_capture([0x1A02, 0x0000]) == bytes([0x02, 0x1A, 0, 0])
    assert v5.encode_capture([]) == b''


@pytest.mark.parametrize('nwks', [[0x1444, 0x1444], [0xFFF8], [None], [-1], list(range(11))])
def test_capture_refused_like_firmware(nwks):
    with pytest.raises(ValueError):
        v5.encode_capture(nwks)


def test_status_names():
    assert v5.status_name(0x93) == 'not_ready' and v5.status_name(0x7E) == 'not_authorized'
    assert v5.status_name(0x87) == 'invalid_value' and v5.status_name(0x80) == 'malformed'
    assert v5.status_name(0x86) == 'unsupported_attribute' and v5.status_name(0x88) == 'read_only'
    assert v5.status_name(0x81) == 'unsupported_command' and v5.status_name(0x55) == 'status_0x55'


def test_beacon_hz():
    assert v5.check_beacon_hz(0) == 0 and v5.check_beacon_hz(10) == 10
    for bad in (1, 11, -1):
        with pytest.raises(ValueError):
            v5.check_beacon_hz(bad)


def test_meter_vector_matches_fw_ci():
    """unit.c prints METER d=0..40 s=... ; the integration's meter_s must give the same 41 values."""
    fw = ('100 79 58 50 48 47 44 43 42 39 38 36 33 32 31 28 27 25 23 21 20 17 16 14 12 10 9 6 5 4 '
          '1 1 1 1 1 1 1 1 1 1 1')
    assert [v5.meter_s(d) for d in range(41)] == [int(x) for x in fw.split()]


def test_505_api_6_supported_504_scale():
    # SENSE_API 6: Ripple declares 6, still speaks 3 and 5 (mixed fleets during the OTA)
    assert v5.SENSE_API == 6 and v5.SUPPORTED_API == (3, 5, 6)
    assert [v5.api_of(a) for a in (None, 2, 3, 5, 6)] == [3, 3, 3, 5, 5]
    assert [v5.has_lines_on(a) for a in (None, 3, 5, 6)] == [False, False, False, True]
    assert v5.A_LINES_ON == 0xFF46 and v5.LIVE_VERSIONS == (2, 3, 4)
    # the default tune of 5.0.5 is the one of 5.0.4: core_max_bins 3 = 1.5 fr/s
    assert v5.encode_tune(v5.tune_defaults(6), 6) == bytes.fromhex(DEFAULT_TUNE_107_HEX)


def test_lines_on_bits_follow_sources_order():
    assert v5.lines_on_bits(0b101, 3) == [True, False, True]
    assert v5.lines_on_bits(0, 2) == [False, False]
    assert v5.lines_on_bits(None, 2) is None


def test_cal_floor_0_only_on_505():
    t = {**v5.tune_defaults(6), 'core_max_bins': 0}
    assert v5.validate_tune(t, 6) == []
    assert v5.validate_tune(t, 5) and v5.validate_tune(t, 3)
    assert v5.validate_tune({**t, 'core_max_bins': 17}, 6)

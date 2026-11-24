import asyncio
import json
import os
import re
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, '..'))
from custom_components.ripple_presence import v5  # noqa: E402
from tests.fake_core import FixtureCore  # noqa: E402
from custom_components.ripple_presence.engine import Engine  # noqa: E402
from custom_components.ripple_presence.store import Store  # noqa: E402
from custom_components.ripple_presence.zigbee import NotRipple, Outdated, Refused, Zigbee, WritesDisabled  # noqa: E402

FX = os.path.join(HERE, 'fixtures')


def load(name):
    with open(os.path.join(FX, name)) as f:
        return json.load(f)


async def make(name, allow_writes=False, protected=(), patch=None, core_patch=None, store=None):
    fx = load(name)
    if patch:
        patch(fx)
    core = FixtureCore(fx)
    if core_patch:
        core_patch(core)
    core.connected.set()
    z = Zigbee(core, allow_writes=allow_writes, protected=protected, spacing_s=0)
    e = Engine(core, z, store or Store(tempfile.mkdtemp()), {'poll_interval_s': 60})
    await e.refresh(wait_probe=True)
    return e, core


def by_name(e, name):
    return next(d for d in e.devices.values() if d['name'] == name)


def cmds(core, cmd=None):
    return [w for w in core.writes if 'command' in w and (cmd is None or w['command'] == cmd)]


def attr_writes(core):
    """Attribute writes other than host_api, which goes before every batch of commands."""
    return [(w['attr'], w['value']) for w in core.writes if 'attr' in w and w['attr'] != v5.A_HOST_API]


class DiscoveryTests(unittest.TestCase):
    def test_v5_switches_found_no_radio_traffic(self):
        reads = []

        def spy(core):
            orig = core.zcl_read

            async def zcl_read(*a):
                reads.append(a)
                return await orig(*a)
            core.zcl_read = zcl_read
        e, _ = asyncio.run(make('synthetic.json', core_patch=spy))
        kinds = {d['name']: d['kind'] for d in e.devices.values()}
        self.assertEqual(kinds['Kitchen switch'], 'ripple')
        self.assertEqual(kinds['Office switch'], 'needs_firmware')
        self.assertEqual(kinds['Tuya relay'], 'other')
        self.assertEqual(kinds['Coffee machine plug'], 'other')
        office = by_name(e, 'Office switch')['ieee']
        self.assertFalse([r for r in reads if r[0] == office])

    def test_offline_switch_is_listed_no_reads(self):
        e, _ = asyncio.run(make('synthetic.json'))
        g = by_name(e, 'Garage switch')
        self.assertEqual((g['probe'], g['kind']), ('offline', 'ripple'))
        self.assertIsNone(e.store.switch(g['ieee']))

    def test_rooms_come_from_areas_ripple(self):
        e, _ = asyncio.run(make('synthetic.json'))
        names = sorted(r['name'] for r in e.rooms())
        self.assertEqual(names, ['Garage', 'Hallway', 'Kitchen', 'Living room'])

    def test_custom_room_switch_from_other_area(self):
        async def go():
            e, _ = await make('synthetic.json')
            sw = [by_name(e, 'Stairs switch')['ieee'], by_name(e, 'Living room switch')['ieee']]
            r = e.create_room('Open space', sw)
            return e, r
        e, r = asyncio.run(go())
        self.assertIn('Open space', [x['name'] for x in e.rooms()])
        self.assertEqual(len(e.room(r['id'])['members']), 2)

    def test_adopts_settings_from_the_device(self):
        e, _ = asyncio.run(make('synthetic.json'))
        sw = e.store.switch(by_name(e, 'Hallway switch')['ieee'])
        names = sorted(e.devices[s]['name'] for s in sw['sources'])
        self.assertEqual(names, ['Front door sensor', 'Stairs switch'])
        self.assertEqual(sw['settings'], {'off_s': 30, 'cal_s': 300, 'beacon_hz': 5, 'detect': False, 'advanced': {}})
        self.assertEqual(sorted(sw['sens'].values()), [70, 70])

    def test_new_device_starts_with_detect_and_self_tune_off(self):
        def on(fx):
            for st in fx['state'].values():
                st['sense_api'], st['detect'], st['self_tune'] = 5, 1, 1
        async def go():
            e, core = await make('synthetic.json', allow_writes=True, patch=on)
            return e, core, by_name(e, 'Hallway switch')['ieee']
        e, core, hall = asyncio.run(go())
        self.assertFalse(e.store.switch(hall)['settings']['detect'])
        self.assertFalse(e.store.switch(hall)['settings']['self_tune'])
        written = [(w['attr'], w['value']) for w in core.writes if w.get('ieee') == hall and 'attr' in w]
        self.assertIn((v5.A_DETECT, 0), written)
        self.assertIn((v5.A_SELF_TUNE, 0), written)

    def test_known_device_keeps_its_settings(self):
        store = Store(tempfile.mkdtemp())
        async def first():
            e, _ = await make('synthetic.json', store=store)
            hall = by_name(e, 'Hallway switch')['ieee']
            await e.set_switch_settings(hall, {'detect': True})
            return hall
        hall = asyncio.run(first())
        def on(fx):
            for st in fx['state'].values():
                st['detect'] = 1
        async def again():
            e, core = await make('synthetic.json', allow_writes=True, patch=on, store=store)
            return e, core
        e, core = asyncio.run(again())
        self.assertTrue(e.store.switch(hall)['settings']['detect'])
        self.assertNotIn((v5.A_DETECT, 0), [(w['attr'], w['value']) for w in core.writes if w.get('ieee') == hall and 'attr' in w])

    def test_candidates_put_heard_devices_first(self):
        e, _ = asyncio.run(make('synthetic.json'))
        c = e.candidates(by_name(e, 'Kitchen switch')['ieee'])
        self.assertTrue(c[0]['heard'])
        self.assertNotIn(by_name(e, 'Kitchen switch')['ieee'], [x['ieee'] for x in c])

    def test_any_zigbee_device_can_be_a_sender(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            kitchen = by_name(e, 'Kitchen switch')['ieee']
            names = {x['name'] for x in e.candidates(kitchen)}
            self.assertTrue({'Tuya relay', 'Coffee machine plug', 'Smoke alarm'} <= names)
            relay = by_name(e, 'Tuya relay')['ieee']
            await e.add_line(kitchen, relay)
            return e, kitchen, relay
        e, kitchen, relay = asyncio.run(go())
        self.assertIn(relay, e.store.switch(kitchen)['sources'])
        self.assertIn(relay, [l['ieee'] for l in e.links(kitchen)])

    def test_panel_sender_list_comes_from_candidates(self):
        js = open(os.path.join(HERE, '..', 'custom_components', 'ripple_presence', 'frontend', 'ripple-panel.js')).read()
        body = js[js.index('  addLineDlg(r) {'):js.index('  addRoomDlg() {')]
        self.assertIn("this.ws('candidates', { ieee: want })", body)
        self.assertIn("const rx = h('select', {}, r.members.map(", body)

    def test_empty_zigbee_network(self):
        e, _ = asyncio.run(make('empty.json'))
        self.assertEqual(e.rooms(), [])
        self.assertEqual(e.status['ripple_count'], 0)

    def test_no_zha(self):
        e, _ = asyncio.run(make('no_zha.json'))
        self.assertFalse(e.status['zha'])
        self.assertEqual(e.devices, {})

    def test_non_v5_device_is_never_contacted(self):
        e, core = asyncio.run(make('synthetic.json'))
        office = by_name(e, 'Office switch')['ieee']
        with self.assertRaises(NotRipple):
            asyncio.run(e.zb.read_attr(office, v5.A_NODE_DIAG, 0x41))


class LinkTests(unittest.TestCase):
    def test_link_rows_show_v5_diagnostics(self):
        e, _ = asyncio.run(make('synthetic.json'))
        rows = e.links(by_name(e, 'Stairs switch')['ieee'])
        self.assertEqual([r['state'] for r in rows], ['calibrated', 'calibrated', 'blind'])
        self.assertEqual([r['sens'] for r in rows], [70, 70, 20])
        self.assertTrue(all(r['level'] < 0 and r['rate'] > 0 and 'alive' in r['bits'] for r in rows))

    def test_link_rows_carry_detector_parameters(self):
        e, _ = asyncio.run(make('synthetic.json'))
        for r in e.links(by_name(e, 'Stairs switch')['ieee']):
            det = r['det']
            self.assertEqual(set(det), {'api', 's', 'rate_d', 'thr_db', 'm', 'off_s', 'decim'})
            self.assertEqual((det['api'], det['thr_db'], det['m']), (3, *v5.motion_params(r['sens'])))
            self.assertEqual((det['s'], det['off_s']), (r['sens'], 30))

    def test_device_page_lists_lines_listens(self):
        js = open(os.path.join(HERE, '..', 'custom_components', 'ripple_presence', 'frontend', 'ripple-panel.js')).read()
        page = js[js.index('  devicePage(d) {'):js.index("'Listens to nobody.'")]
        self.assertIn("const lines = (d.links || []).map(", page)
        self.assertNotIn("'sends'", page)

    def test_panel_motion_table_matches_fw_table(self):
        js = open(os.path.join(HERE, '..', 'custom_components', 'ripple_presence', 'frontend', 'ripple-panel.js')).read()
        body = re.search(r'const MOTION_TAB = \[(.*?)\];', js, re.S).group(1)
        rows = tuple(tuple(int(x) for x in r.split(',')) for r in re.findall(r'\[([\d, ]+)\]', body))
        self.assertEqual(rows, v5.MOTION_TAB)
        self.assertIn(f'const MOTION_PARKED_S = {v5.MOTION_PARKED_S};', js)
        body5 = re.search(r'const MOTION_TAB_5 = \[(.*?)\];', js, re.S).group(1)
        rows5 = tuple(tuple(int(x) for x in r.split(',')) for r in re.findall(r'\[([\d, ]+)\]', body5))
        self.assertEqual(rows5, v5.MOTION_TAB_5)

    def test_uncald_switch_needs_cal(self):
        e, _ = asyncio.run(make('synthetic.json'))
        w = by_name(e, 'Kitchen worktop switch')
        self.assertEqual({r['state'] for r in e.links(w['ieee'])}, {'not_learned'})
        room = next(r for r in e.rooms() if r['name'] == 'Kitchen')
        self.assertTrue(room['needs_calibration'])


class WriteTests(unittest.TestCase):
    def test_values_not_read_yet_are_not_pending(self):
        e, _ = asyncio.run(make('synthetic.json'))
        ieee = by_name(e, 'Hallway switch')['ieee']
        e.devices[ieee]['config'] = {}
        self.assertEqual(e.pending(ieee), [])

    def test_adoption_leaves_nothing_pending(self):
        e, _ = asyncio.run(make('synthetic.json'))
        for d in e.ripple_devices():
            self.assertEqual(e.pending(d['ieee']), [], d['name'])

    def test_new_source_appended_no_moving_others(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            hall = by_name(e, 'Hallway switch')['ieee']
            before = e.devices[hall]['config']['sources']
            await e.add_source(hall, by_name(e, 'Smoke alarm')['ieee'])
            return e, core, before
        e, core, before = asyncio.run(go())
        sent = cmds(core, v5.CMD_SOURCES)
        nwk = by_name(e, 'Smoke alarm')['nwk']
        self.assertEqual([w['payload'] for w in sent], [before + nwk.to_bytes(2, 'little') + bytes([0x01, v5.SENS_DEFAULT_BY_API[3]])])
        self.assertEqual(sent[0]['manuf'], v5.MANUF)

    def test_source_without_nwk_is_kept_on_switch(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            hall, smoke = by_name(e, 'Hallway switch')['ieee'], by_name(e, 'Smoke alarm')['ieee']
            await e.add_source(hall, smoke)
            on_switch = e.devices[hall]['config']['sources']
            n = len(cmds(core, v5.CMD_SOURCES))
            e.devices[smoke]['nwk'] = None
            await e.calibrate([hall], 120)
            await e._safe_apply(hall)
            return e, core, hall, smoke, on_switch, n
        e, core, hall, smoke, on_switch, n = asyncio.run(go())
        self.assertEqual(len(cmds(core, v5.CMD_SOURCES)), n)
        self.assertEqual(e.devices[hall]['config']['sources'], on_switch)
        self.assertEqual(e.unresolved_sources(hall), [smoke])
        self.assertIn(smoke, e.store.switch(hall)['sources'])

    def test_settings_saved_when_read_only(self):
        async def go():
            e, core = await make('synthetic.json')
            ieee = by_name(e, 'Hallway switch')['ieee']
            res = await e.set_switch_settings(ieee, {'off_s': 20})
            return e, core, ieee, res
        e, core, ieee, res = asyncio.run(go())
        self.assertEqual(core.writes, [])
        self.assertEqual(e.store.switch(ieee)['settings']['off_s'], 20)
        self.assertFalse(res['written'])
        self.assertEqual([p['key'] for p in e.pending(ieee)], ['tune'])

    def test_off_tune_off_s_sent_command_0x01(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            ieee = by_name(e, 'Hallway switch')['ieee']
            await e.set_switch_settings(ieee, {'off_s': 45})
            return e, core, ieee
        e, core, ieee = asyncio.run(go())
        sent = cmds(core)
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]['command'], v5.CMD_TUNE)
        self.assertEqual(v5.decode_tune(sent[0]['payload'])['off_s'], 45)
        self.assertEqual(attr_writes(core), [])
        self.assertEqual(e.pending(ieee), [])

    def test_hold_and_beacon_ranges(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            ieee = by_name(e, 'Hallway switch')['ieee']
            for bad in ({'hold_s': 256}, {'off_s': 0}, {'off_s': 256}, {'beacon_hz': 1}, {'beacon_hz': 11}, {'cal_s': 1801}, {'sensitivity': 5}):
                with self.assertRaises(ValueError):
                    await e.set_switch_settings(ieee, bad)
            await e.set_switch_settings(ieee, {'beacon_hz': 0})
            return core
        core = asyncio.run(go())
        self.assertEqual(attr_writes(core), [(v5.A_BEACON_HZ, 0)])

    def test_detect_is_written_to_0xff42(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            await e.set_switch_settings(by_name(e, 'Hallway switch')['ieee'], {'detect': True})
            return core
        core = asyncio.run(go())
        self.assertEqual(attr_writes(core), [(v5.A_DETECT, 1)])
        self.assertEqual(core.writes[0]['manuf'], v5.MANUF)

    def test_sens_per_line(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            hall = by_name(e, 'Hallway switch')['ieee']
            sw = e.store.switch(hall)
            await e.set_sources(hall, sw['sources'], {sw['sources'][1]: 30})
            with self.assertRaises(ValueError):
                await e.set_sources(hall, sw['sources'], {sw['sources'][0]: 101})
            return e, core, hall
        e, core, hall = asyncio.run(go())
        lines = v5.decode_sources(cmds(core, v5.CMD_SOURCES)[0]['payload'])
        self.assertEqual([(l['zones'], l['sens']) for l in lines], [(0x01, 70), (0x01, 30)])
        self.assertEqual(e.links(hall)[1]['sens'], 30)

    def test_line_s_0_sent_never_detects(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            hall = by_name(e, 'Hallway switch')['ieee']
            sw = e.store.switch(hall)
            await e.set_sources(hall, sw['sources'], {sw['sources'][0]: 0})
            core.report(hall, v5.CLUSTER, v5.A_ZONE_STATE, 1)
            with patch('custom_components.ripple_presence.engine.DIAG_FRESH_S', 0):
                await e._read_lines(e.devices[hall])
                return e, core, e.links(hall)
        e, core, links = asyncio.run(go())
        self.assertEqual(v5.decode_sources(cmds(core, v5.CMD_SOURCES)[0]['payload'])[0]['sens'], 0)
        self.assertEqual((links[0]['sens'], links[0]['detecting']), (0, False))
        self.assertTrue(links[1]['detecting'])

    def test_commands_come_after_host_api(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            hall = by_name(e, 'Hallway switch')['ieee']
            await e.set_switch_settings(hall, {'off_s': 45})
            return core, hall
        core, hall = asyncio.run(go())
        seq = [w.get('attr', w.get('command')) for w in core.writes if w['ieee'] == hall]
        self.assertEqual(seq, [v5.A_HOST_API, v5.CMD_TUNE])
        self.assertEqual(core.switches[hall].host_api, v5.SENSE_API)

    def test_add_source_only_to_that_switch(self):
        async def go():
            e, core = await make('synthetic.json')
            a, b = by_name(e, 'Kitchen switch')['ieee'], by_name(e, 'Kitchen worktop switch')['ieee']
            before = list(e.store.switch(b)['sources'])
            await e.add_source(a, by_name(e, 'TV plug')['ieee'])
            return e, a, b, before
        e, a, b, before = asyncio.run(go())
        self.assertIn(by_name(e, 'TV plug')['ieee'], e.store.switch(a)['sources'])
        self.assertEqual(e.store.switch(a)['sens'][by_name(e, 'TV plug')['ieee']], v5.SENS_DEFAULT_BY_API[3])
        self.assertEqual(e.store.switch(b)['sources'], before)

    def test_at_most_ten_lines(self):
        async def go():
            e, _ = await make('synthetic.json')
            hall = by_name(e, 'Hallway switch')['ieee']
            others = [d['ieee'] for d in e.devices.values() if d['ieee'] != hall]
            with self.assertRaises(ValueError):
                await e.set_sources(hall, others[:11])
        asyncio.run(go())

    def test_sender_nwk_change_sends_sources(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            stairs = by_name(e, 'Stairs switch')['ieee']
            core.set_nwk(stairs, 0x7777)
            await e._check_nwk()
            await e._probe_task
            return e, core
        e, core = asyncio.run(go())
        sent = {w['ieee']: v5.decode_sources(w['payload']) for w in cmds(core, v5.CMD_SOURCES)}
        hall = by_name(e, 'Hallway switch')['ieee']
        self.assertIn(0x7777, [l['nwk'] for l in sent[hall]])
        self.assertEqual(e.pending(hall), [])

    def test_fw_refusal_is_reported(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            hall = by_name(e, 'Hallway switch')['ieee']
            core.not_ready.add(hall)
            with self.assertRaises(Refused) as cm:
                await e.add_source(hall, by_name(e, 'Smoke alarm')['ieee'])
            return cm.exception
        err = asyncio.run(go())
        self.assertEqual(err.code, 'not_ready')

    def test_advanced_tune_checks_match_firmware(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            hall = by_name(e, 'Hallway switch')['ieee']
            for bad in ({'hist_cap': 16}, {'quiet_q': 0.3}, {'rate_state_d': 3.1}, {'h': 96}, {'flat_s': 300},
                        {'gate_range_q': 3.0}, {'exit_s': 5}):
                with self.assertRaises(ValueError):
                    await e.set_switch_settings(hall, {'advanced': bad})
            await e.set_switch_settings(hall, {'advanced': {'quiet_q': 3.0, 'level_min': -80}})
            return core
        core = asyncio.run(go())
        t = v5.decode_tune(cmds(core, v5.CMD_TUNE)[0]['payload'])
        self.assertEqual((t['quiet_q'], t['level_min'], t['version']), (12, -80, 5))

    def test_cal_refused_when_read_only(self):
        async def go():
            e, _ = await make('synthetic.json')
            rid = e.rooms()[0]['id']
            with self.assertRaises(WritesDisabled):
                await e.calibrate_room(rid, 300)
        asyncio.run(go())

    def test_cal_sends_cal_s_then_starts(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            rid = next(r['id'] for r in e.rooms() if r['name'] == 'Hallway')
            with self.assertRaises(ValueError):
                await e.calibrate_room(rid, 30)
            with self.assertRaises(ValueError):
                await e.calibrate_room(rid, 1801)
            await e.calibrate_room(rid, 600)
            return e, core, rid
        e, core, rid = asyncio.run(go())
        hall = by_name(e, 'Hallway switch')['ieee']
        seq = [('cmd', v5.decode_tune(w['payload'])['cal_s']) if 'command' in w else ('attr', w['attr'], w['value'])
               for w in core.writes if w['ieee'] == hall]
        self.assertEqual(seq, [('attr', v5.A_HOST_API, v5.SENSE_API), ('cmd', 600), ('attr', v5.A_CALIBRATE, 1)])
        self.assertEqual(e.store.room_meta(rid)['cal_s'], 600)
        self.assertTrue(e.room(rid)['calibrating'])


class LineCalibrationTests(unittest.TestCase):
    def test_line_capture_sends_cal_s_then(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            hall, stairs = by_name(e, 'Hallway switch')['ieee'], by_name(e, 'Stairs switch')['ieee']
            res = await e.calibrate_line(hall, stairs, 600)
            return e, core, hall, res
        e, core, hall, res = asyncio.run(go())
        seq = [('cmd', w['command'], w['payload']) if 'command' in w else ('attr', w['attr'], w['value'])
               for w in core.writes if w['ieee'] == hall]
        self.assertEqual(seq, [('attr', v5.A_HOST_API, v5.SENSE_API), ('cmd', v5.CMD_TUNE, seq[1][2]),
                               ('cmd', v5.CMD_CAPTURE, (5188).to_bytes(2, 'little'))])
        self.assertEqual(v5.decode_tune(seq[1][2])['cal_s'], 600)
        self.assertEqual(res, {'written': [hall]})
        self.assertEqual(e.store.switch(hall)['settings']['cal_s'], 600)
        self.assertTrue(e.room('area:hallway')['calibrating'])

    def test_switch_view_says_what_calibrating(self):
        """The panel banner needs the seconds left, their age and the lines being captured."""
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            hall, stairs = by_name(e, 'Hallway switch')['ieee'], by_name(e, 'Stairs switch')['ieee']
            await e.calibrate_line(hall, stairs, 120)
            line = e.device_summary(e.devices[hall])
            await e.calibrate([hall], 90)
            return line, e.device_summary(e.devices[hall]), stairs
        line, room, stairs = asyncio.run(go())
        self.assertEqual((line['cal_left'], line['cal_txs']), (120, [stairs]))
        self.assertEqual((room['cal_left'], room['cal_txs']), (90, None))
        self.assertLess(time.time() - room['cal_left_at'], 5)

    def test_only_the_captured_line_becomes_cald(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            rx, tx = by_name(e, 'Kitchen worktop switch')['ieee'], by_name(e, 'Kitchen switch')['ieee']
            await e.calibrate_line(rx, tx, 60)
            core.switches[rx].advance(60)
            return core.switches[rx]
        sw = asyncio.run(go())
        self.assertEqual(sw.calibrated, {4369})

    def test_line_capture_refused_while_capture(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            hall = by_name(e, 'Hallway switch')['ieee']
            await e.calibrate_line(hall, by_name(e, 'Stairs switch')['ieee'], 300)
            with self.assertRaises(Refused) as cm:
                await e.calibrate_line(hall, by_name(e, 'Front door sensor')['ieee'], 300)
            return cm.exception
        err = asyncio.run(go())
        self.assertEqual(err.code, 'not_ready')

    def test_line_capture_refused_before_any(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            hall = by_name(e, 'Hallway switch')['ieee']
            with self.assertRaises(KeyError):
                await e.calibrate_line(hall, by_name(e, 'Smoke alarm')['ieee'], 300)
            with self.assertRaises(ValueError):
                await e.calibrate_line(hall, by_name(e, 'Stairs switch')['ieee'], 59)
            ro, ro_core = await make('synthetic.json')
            with self.assertRaises(WritesDisabled):
                await ro.calibrate_line(hall, by_name(ro, 'Stairs switch')['ieee'], 300)
            return core.writes + ro_core.writes
        self.assertEqual(asyncio.run(go()), [])

    def test_room_capture_covers_every_line_every(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            await e.calibrate_room('area:hallway', 300)
            return e, core
        e, core = asyncio.run(go())
        members = e.room('area:hallway')['members']
        self.assertEqual(sorted(w['ieee'] for w in core.writes if w.get('attr') == v5.A_CALIBRATE), sorted(members))
        self.assertFalse(cmds(core, v5.CMD_CAPTURE))


class ReportTests(unittest.TestCase):
    def test_zone_occupancy_reports_drive_motion(self):
        async def go():
            e, core = await make('synthetic.json')
            hall = by_name(e, 'Hallway switch')['ieee']
            core.report(hall, v5.CLUSTER, v5.A_ZONE_STATE, 1)
            on = e.room('area:hallway')['occupied']
            await e.set_room_settings('area:hallway', {'off_s': 0})
            core.report(hall, v5.OCCUPANCY, v5.A_OCCUPANCY, 0)
            off = e.room('area:hallway')['occupied']
            return on, off, e.devices[hall]['live']
        on, off, live = asyncio.run(go())
        self.assertTrue(on)
        self.assertFalse(off)
        self.assertTrue(live['event_seen'])

    def test_views_do_not_depend_on_the_clock(self):
        """rooms() and switch_view() carry absolute times, so the same state built later is the same JSON."""
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            hall = by_name(e, 'Hallway switch')['ieee']
            await e.calibrate([hall], 120)
            core.report(hall, v5.CLUSTER, v5.A_ZONE_STATE, 1)
            core.report(hall, v5.CLUSTER, v5.A_ZONE_STATE, 0)

            def build():
                return json.dumps({'rooms': e.rooms(), 'sw': [e.switch_view(i) for i in e.devices if e.store.switch(i)]},
                                  sort_keys=True, default=str)
            first = build()
            # the build must hold the time-dependent fields, or the comparison proves nothing
            assert e.room('area:hallway')['hold_until'] is not None
            assert e.switch_view(hall).get('cal_left_at') is not None
            t = time.time() + 5
            with patch('custom_components.ripple_presence.engine.now', lambda: t):
                later = build()
            return first, later
        first, later = asyncio.run(go())
        self.assertEqual(first, later)

    def test_room_holds_own_off_s_after_last(self):
        async def go():
            e, core = await make('synthetic.json')
            hall = by_name(e, 'Hallway switch')['ieee']
            default = e.room_settings('area:hallway')['off_s']
            core.report(hall, v5.CLUSTER, v5.A_ZONE_STATE, 1)
            core.report(hall, v5.CLUSTER, v5.A_ZONE_STATE, 0)
            held = e.room('area:hallway')
            held['t'] = time.time()
            await e.set_room_settings('area:hallway', {'off_s': 1})
            await asyncio.sleep(1.2)
            return default, held, e.room('area:hallway'), e.store.switch(hall)['settings']['off_s'], core.writes
        default, held, after, sw_off, writes = asyncio.run(go())
        self.assertEqual(default, 10)
        self.assertTrue(held['occupied'])
        self.assertGreater(held['hold_until'] - held['t'], 9)
        self.assertFalse(after['occupied'])
        self.assertEqual(sw_off, 30)
        self.assertEqual(writes, [])

    def test_room_off_s_range(self):
        async def go():
            e, _ = await make('synthetic.json')
            out = []
            for bad in (-1, 3601, 'x'):
                try:
                    await e.set_room_settings('area:hallway', {'off_s': bad})
                    out.append(None)
                except ValueError as err:
                    out.append(str(err))
            await e.set_room_settings('area:hallway', {'off_s': 3600})
            return out, e.room_settings('area:hallway')['off_s'], e.room('area:hallway')['settings']['off_s']
        out, saved, shown = asyncio.run(go())
        self.assertTrue(all(out))
        self.assertEqual((saved, shown), (3600, 3600))

    def test_zone_change_reads_which_lines_detect(self):
        async def go():
            e, core = await make('synthetic.json')
            hall = by_name(e, 'Hallway switch')['ieee']
            e._spawn = lambda coro: asyncio.ensure_future(coro)
            core.report(hall, v5.CLUSTER, v5.A_ZONE_STATE, 1)
            await asyncio.sleep(1.7)
            on_links, room = e.links(hall), e.room('area:hallway')
            core.report(hall, v5.CLUSTER, v5.A_ZONE_STATE, 0)
            await asyncio.sleep(1.7)
            return e, hall, on_links, room
        e, hall, on_links, room = asyncio.run(go())
        detecting = [l['name'] for l in on_links if l['detecting']]
        self.assertTrue(detecting)
        self.assertEqual([l['name'] for l in on_links if l['last_on']], detecting[:1])
        self.assertEqual({x['sender'] for x in room['detected_by'] if x['switch'] == 'Hallway switch'}, set(detecting))
        self.assertFalse(any(l['detecting'] for l in e.links(hall)))
        self.assertIsNotNone(e.devices[hall]['live']['lines_at'])

    def test_zone_off_clears_the_lines_at_once(self):
        async def go():
            e, core = await make('synthetic.json')
            hall = by_name(e, 'Hallway switch')['ieee']
            e._spawn = lambda coro: asyncio.ensure_future(coro)
            core.report(hall, v5.CLUSTER, v5.A_ZONE_STATE, 1)
            await asyncio.sleep(1.4)
            on = [l['name'] for l in e.links(hall) if l['detecting']]
            core.report(hall, v5.CLUSTER, v5.A_ZONE_STATE, 0)
            off = [l['name'] for l in e.links(hall) if l['detecting']]
            room = e.room('area:hallway')
            await asyncio.sleep(1.4)
            return on, off, room
        on, off, room = asyncio.run(go())
        self.assertTrue(on)
        self.assertEqual(off, [])
        self.assertFalse([x for x in room['detected_by'] if x['switch'] == 'Hallway switch'])

    def test_read_older_switch_diag_not_claim(self):
        async def go():
            e, core = await make('synthetic.json')
            hall = by_name(e, 'Hallway switch')['ieee']
            e._spawn = lambda coro: asyncio.ensure_future(coro)
            core.report(hall, v5.CLUSTER, v5.A_ZONE_STATE, 1)
            await e._read_lines(e.devices[hall])
            stale = [l['name'] for l in e.links(hall) if l['detecting']]
            await asyncio.sleep(1.4)
            return stale, [l['name'] for l in e.links(hall) if l['detecting']]
        stale, fresh = asyncio.run(go())
        self.assertEqual(stale, [])
        self.assertTrue(fresh)

    def test_zone_change_during_read_read_again(self):
        async def go():
            e, core = await make('synthetic.json')
            hall = by_name(e, 'Hallway switch')['ieee']
            e._spawn = lambda coro: asyncio.ensure_future(coro)
            reads = []
            orig = e._read_lines

            async def counted(d, with_node=True):
                reads.append(d["ieee"])
                await orig(d, with_node)
            e._read_lines = counted
            with patch('custom_components.ripple_presence.engine.DIAG_FRESH_S', 0.2):
                core.report(hall, v5.CLUSTER, v5.A_ZONE_STATE, 1)
                await asyncio.sleep(0.1)
                core.report(hall, v5.CLUSTER, v5.A_ZONE_STATE, 0)
                await asyncio.sleep(0.6)
            return reads, e
        reads, e = asyncio.run(go())
        self.assertEqual(len(reads), 2)
        self.assertFalse(e._snapping)

    def test_parked_line_sent_no_zones_never(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            hall = by_name(e, 'Hallway switch')['ieee']
            sw = e.store.switch(hall)
            await e.set_sources(hall, sw['sources'], parked=[sw['sources'][0]])
            core.report(hall, v5.CLUSTER, v5.A_ZONE_STATE, 1)
            await e._read_lines(e.devices[hall])
            return e, core, hall
        e, core, hall = asyncio.run(go())
        lines = v5.decode_sources(cmds(core, v5.CMD_SOURCES)[0]['payload'])
        self.assertEqual([l['zones'] for l in lines], [0x00, 0x01])
        links = e.links(hall)
        self.assertTrue(links[0]['parked'])
        self.assertFalse(links[0]['detecting'])
        self.assertEqual(e.store.switch(hall)['parked'], [links[0]['ieee']])

    def test_sole_voter_detects_once_zone_change(self):
        """Before link_diag is fresh, the only line that votes for a zone that came on is detecting at once."""
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            hall = by_name(e, 'Hallway switch')['ieee']
            sw = e.store.switch(hall)
            await e.set_sources(hall, sw['sources'], parked=[sw['sources'][0]])
            with patch('custom_components.ripple_presence.engine.DIAG_FRESH_S', 30):
                e._spawn = lambda coro: coro.close()
                core.report(hall, v5.CLUSTER, v5.A_ZONE_STATE, 1)
                one = [l['detecting'] for l in e.links(hall)]
                await e.set_sources(hall, sw['sources'], parked=[])
                core.report(hall, v5.CLUSTER, v5.A_ZONE_STATE, 0)
                core.report(hall, v5.CLUSTER, v5.A_ZONE_STATE, 1)
                two = [l['detecting'] for l in e.links(hall)]
                core.report(hall, v5.CLUSTER, v5.A_ZONE_STATE, 0)
                off = [l['detecting'] for l in e.links(hall)]
            return one, two, off
        one, two, off = asyncio.run(go())
        self.assertEqual(one, [False, True])
        self.assertEqual(two, [False, False])
        self.assertEqual(off, [False, False])

    def test_raw_stream_is_a_guarded_write(self):
        async def go():
            e, core = await make('synthetic.json')
            hall = by_name(e, 'Hallway switch')['ieee']
            with self.assertRaises(WritesDisabled):
                await e.set_raw_stream(hall, True)
            e2, core2 = await make('synthetic.json', allow_writes=True)
            await e2.set_raw_stream(hall, True)
            return core2, hall, e2
        core2, hall, e2 = asyncio.run(go())
        self.assertEqual(core2.switches[hall].raw_enabled, 1)
        self.assertEqual(e2.switch_view(hall)['raw_enabled'], 1)

    def test_poll_reads_node_diag_and_cal_left(self):
        async def go():
            e, core = await make('synthetic.json')
            hall = by_name(e, 'Hallway switch')
            core.switches[hall['ieee']].cal_left = 120
            await e.poll_device(hall)
            return hall['live']
        live = asyncio.run(go())
        self.assertEqual(live['cal_left'], 120)
        self.assertEqual(live['flags'] & 2, 2)

    def test_quiet_switch_rereads_lines_once_they(self):
        """A switch that never detects still gets fresh link_diag (level, rate) for the panel gauge."""
        async def go():
            e, core = await make('synthetic.json')
            hall = by_name(e, 'Hallway switch')
            reads = []
            orig = e._read_lines

            async def counted(d, with_node=True):
                reads.append(d['ieee'])
                await orig(d, with_node)
            e._read_lines = counted
            hall['live']['lines_at'] = 0
            await e.poll_device(hall)
            n1 = len(reads)
            await e.poll_device(hall)
            return n1, len(reads)
        n1, n2 = asyncio.run(go())
        self.assertEqual((n1, n2), (1, 1))

    def test_panel_gauge_needs_no_link_diag_read(self):
        js = open(os.path.join(HERE, '..', 'custom_components', 'ripple_presence', 'frontend', 'ripple-panel.js')).read()
        body = js[js.index('  _simStep(k, rx, r) {'):js.index('  _tick() {')]
        self.assertLess(body.index('sense_api >= 5'), body.index('if (!det) return;'))

    def test_poll_clears_room_rereads_lines(self):
        async def go():
            e, core = await make('synthetic.json')
            hall = by_name(e, 'Hallway switch')
            core.switches[hall['ieee']].detect = 1
            core.switches[hall['ieee']].zone_state = 1
            await e.poll_device(hall)
            before = [l['detecting'] for l in e.links(hall['ieee'])]
            core.switches[hall['ieee']].zone_state = 0
            await e.poll_device(hall)
            return before, [l['detecting'] for l in e.links(hall['ieee'])], hall['live']['motion']
        before, after, motion = asyncio.run(go())
        self.assertTrue(any(before))
        self.assertFalse(any(after))
        self.assertFalse(motion)


def drop_diag(core):
    orig = core.zcl_read

    async def zcl_read(ieee, cluster, attrs, manuf):
        ok, fail = await orig(ieee, cluster, attrs, manuf)
        for a in (v5.A_NODE_DIAG, v5.A_LINK_A, v5.A_LINK_B):
            if a in ok:
                fail[a] = 0x86
                del ok[a]
        return ok, fail
    core.zcl_read = zcl_read


class ConcurrencyTests(unittest.TestCase):
    def test_refresh_during_probe_promotes(self):
        async def go():
            core = FixtureCore(load('synthetic.json'))
            core.connected.set()
            z = Zigbee(core, spacing_s=0.002)
            e = Engine(core, z, Store(tempfile.mkdtemp()), {})
            await e.refresh()
            await asyncio.sleep(0.01)
            await e.refresh()
            for _ in range(500):
                await asyncio.sleep(0.01)
                if not e.status['probing'] and not (e._probe_task and not e._probe_task.done()):
                    break
            return e
        e = asyncio.run(go())
        self.assertEqual(e.status['ripple_count'], 6)
        self.assertTrue(all(d['probe'] for d in e.devices.values() if d['kind'] == 'ripple'))


class AdoptionTests(unittest.TestCase):
    def test_missing_diagnostics_not_block(self):
        e, _ = asyncio.run(make('synthetic.json', core_patch=drop_diag))
        self.assertEqual(len([d for d in e.devices.values() if d['kind'] == 'ripple' and e.store.switch(d['ieee'])]), 5)

    def test_failed_adoption_is_retried(self):
        async def go():
            e, core = await make('synthetic.json')
            hall = by_name(e, 'Hallway switch')['ieee']
            del e.store.data['switches'][hall]
            await e.retry_adoption()
            return e, hall
        e, hall = asyncio.run(go())
        self.assertIsNotNone(e.store.switch(hall))

    def test_unreachable_switch_backed_off(self):
        async def go():
            fx = load('synthetic.json')
            hall = next(d['ieee'] for d in fx['zha_devices'] if d['user_given_name'] == 'Hallway switch')
            e, core = await make('synthetic.json', core_patch=lambda c: c.unreachable.add(hall))
            first = (e.devices[hall]['kind'], e.store.switch(hall), hall in e.zb.backoff)
            core.unreachable.clear()
            e.zb.backoff.clear()
            await e.retry_adoption()
            return first, e.store.switch(hall)
        first, later = asyncio.run(go())
        self.assertEqual(first, ('ripple', None, True))
        self.assertIsNotNone(later)

    def test_switch_migrated_from_v4_keeps_lines(self):
        async def go():
            fx = load('synthetic.json')
            ieee = {d['user_given_name']: d['ieee'] for d in fx['zha_devices'] if d.get('user_given_name')}
            store = Store(tempfile.mkdtemp())
            store.data['switches'][ieee['Hallway switch']] = {
                'settings': {}, 'sources': [ieee['Smoke alarm']], 'sens': {ieee['Smoke alarm']: 70}, 'migrated': True}
            e, core = await make('synthetic.json', store=store)
            return e, ieee
        e, ieee = asyncio.run(go())
        sw = e.store.switch(ieee['Hallway switch'])
        self.assertNotIn('migrated', sw)
        self.assertEqual(sw['sources'], [ieee['Smoke alarm']])
        self.assertEqual(sw['settings']['beacon_hz'], 5)
        self.assertEqual([p['key'] for p in e.pending(ieee['Hallway switch'])], ['sources'])


class IdentityTests(unittest.TestCase):
    def test_marker_in_sw_build_id_wins(self):
        from custom_components.ripple_presence.engine import is_ripple_firmware
        self.assertTrue(is_ripple_firmware({'kind': 'needs_firmware', 'sw_build_id': 'ripple.v5'}))
        self.assertFalse(is_ripple_firmware({'kind': 'other', 'sw_build_id': '1.0.4'}))
        self.assertTrue(is_ripple_firmware({'kind': 'ripple', 'sw_build_id': None}))

    def test_cached_marker_is_used(self):
        def mark(fx):
            office = next(d for d in fx['zha_devices'] if d['user_given_name'] == 'Office switch')
            office['sw_build_id'] = 'ripple.v4'
        e, _ = asyncio.run(make('synthetic.json', patch=mark))
        from custom_components.ripple_presence.engine import is_ripple_firmware
        self.assertTrue(is_ripple_firmware(by_name(e, 'Office switch')))

    def test_old_firmware_with_quirk_cluster_needs_update(self):
        def old(fx):
            hall = next(d for d in fx['zha_devices'] if d['user_given_name'] == 'Hallway switch')
            hall['fw'] = 0x11033341
        e, _ = asyncio.run(make('synthetic.json', patch=old))
        self.assertEqual(by_name(e, 'Hallway switch')['kind'], 'needs_firmware')


    def test_ripple_fw_no_quirk_is_flagged(self):
        def bare(fx):
            hall = next(d for d in fx['zha_devices'] if d['user_given_name'] == 'Hallway switch')
            hall['sense'], hall['unquirked'] = False, True
        e, _ = asyncio.run(make('synthetic.json', patch=bare))
        hall = by_name(e, 'Hallway switch')
        self.assertEqual((hall['kind'], hall['probe'], hall['unquirked']), ('needs_firmware', 'no_quirk', True))

class HoldReadsTests(unittest.TestCase):
    def test_background_reads_wait_for_release(self):
        async def go():
            core = FixtureCore(load('synthetic.json'))
            core.connected.set()
            reads = []
            orig = core.zcl_read

            async def zcl_read(*a):
                reads.append(a)
                return await orig(*a)
            core.zcl_read = zcl_read
            z = Zigbee(core, spacing_s=0)
            e = Engine(core, z, Store(tempfile.mkdtemp()), {})
            e.hold_reads()
            await e.refresh()
            await asyncio.sleep(0.05)
            held = len(reads)
            discovered = len(e.devices)
            e.release_reads()
            for _ in range(200):
                await asyncio.sleep(0.02)
                if e._probe_task.done():
                    break
            return held, discovered, len(reads), e.status['ripple_count']
        held, discovered, after, n = asyncio.run(go())
        self.assertEqual(held, 0)
        self.assertGreater(discovered, 0)
        self.assertGreater(after, 0)
        self.assertEqual(n, 6)


class StoreTests(unittest.TestCase):
    def test_v4_settings_become_lines_v2(self):
        from custom_components.ripple_presence.store import migrate
        v4 = {'version': 1, 'switches': {'a': {'settings': {'sensitivity': 7, 'hold_s': 30}, 'sources': ['b', 'c']}},
              'rooms': [{'id': 'r1', 'name': 'Open', 'members': ['a']}], 'hidden_areas': ['area:x'],
              'room_meta': {'r1': {'cal_s': 3600}}, 'probe': {'a': {}}}
        out = migrate(1, v4)
        d3 = v5.SENS_DEFAULT_BY_API[3]
        self.assertEqual(out['switches']['a'], {'settings': {}, 'sources': ['b', 'c'], 'sens': {'b': d3, 'c': d3},
                                                'migrated': True})
        self.assertEqual((out['rooms'], out['hidden_areas'], out['room_meta']), (v4['rooms'], ['area:x'], {'r1': {'cal_s': 1800}}))
        self.assertEqual((out['probe'], out['version']), ({}, 5))
        with self.assertLogs('ripple.store', 'WARNING'):
            self.assertEqual(migrate(2, {'zones': {}, 'lines': {}})['switches'], {})

    def test_json_store_migrates_on_load(self):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, 'ripple.json'), 'w') as f:
            json.dump({'version': 1, 'switches': {'a': {'settings': {}, 'sources': ['b']}}, 'rooms': []}, f)
        self.assertEqual(Store(d).switch('a')['sens'], {'b': v5.SENS_DEFAULT_BY_API[3]})

    def test_steps_of_1_0_x_become_s(self):
        from custom_components.ripple_presence.store import migrate
        v3 = {'version': 3, 'switches': {'a': {'settings': {'hold_s': 5}, 'sources': ['b', 'c', 'd'],
                                               'sens': {'b': 9, 'c': 10, 'd': 1}, 'parked': ['d']}},
              'rooms': [{'id': 'r1', 'name': 'Open', 'members': ['a']}], 'room_meta': {}, 'probe': {}}
        out = migrate(3, v3)
        steps = {'b': v5.STEP_S[9], 'c': v5.STEP_S[10], 'd': v5.STEP_S[1]}
        self.assertEqual(out['switches']['a'], {'settings': {}, 'sources': ['b', 'c', 'd'], 'sens': steps, 'parked': ['d']})
        self.assertEqual((out['version'], out['rooms']), (5, v3['rooms']))
        d = tempfile.mkdtemp()
        with open(os.path.join(d, 'ripple.json'), 'w') as f:
            json.dump(v3, f)
        self.assertEqual(Store(d).switch('a')['sens'], steps)

    def test_502_store_keeps_s_and_drops_the_hold(self):
        from custom_components.ripple_presence.store import migrate
        v4 = {'version': 4, 'switches': {'a': {'settings': {'hold_s': 5, 'off_s': 12}, 'sources': ['b', 'c'],
                                               'sens': {'b': 70, 'c': 93}, 'parked': []}},
              'rooms': [], 'room_meta': {}, 'probe': {}, 'bindings': {}}
        out = migrate(4, v4)
        self.assertEqual(out['switches']['a'], {'settings': {'off_s': 12}, 'sources': ['b', 'c'],
                                                'sens': {'b': 70, 'c': 93}, 'parked': []})
        self.assertEqual(out['version'], 5)


def legacy(fx, name='Hallway switch', fw=0x1103339A):
    """A switch still on 5.0.1: ladder bytes in sources, 8 B link_diag, no sense_api."""
    dev = next(d for d in fx['zha_devices'] if d['user_given_name'] == name)
    dev['fw'] = fw
    st = fx['state'][dev['ieee']]
    raw = bytearray(bytes.fromhex(st['sources']))
    for i in range(3, len(raw), 4):
        raw[i] = {70: 0x03, 20: 0x42, 75: 0x02, 10: 0x48}[raw[i]]
    st['sources'], st['sense_api'] = raw.hex(), None
    return dev['ieee']


class ApiTests(unittest.TestCase):
    """Firmware 5.0.2 / 5.0.3: Ripple configures only switches whose API it speaks (SENSE_API 3)."""

    def test_5_0_1_switch_is_shown_but_never_written(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True, patch=legacy)
            hall = by_name(e, 'Hallway switch')['ieee']
            sw = e.store.switch(hall)
            with self.assertRaises(Outdated):
                await e.set_sources(hall, sw['sources'], {sw['sources'][0]: 40})
            with self.assertRaises(Outdated):
                await e.set_raw_stream(hall, True)
            return e, core, hall
        e, core, hall = asyncio.run(go())
        self.assertEqual(by_name(e, 'Hallway switch')['kind'], 'ripple')
        old = v5.s_from_legacy(0x03)
        self.assertEqual(sorted(e.store.switch(hall)['sens'].values()), sorted([40, old]))
        self.assertEqual([l['sens'] for l in e.links(hall)], [40, old])
        self.assertEqual(e.switch_view(hall)['api'], 'update_firmware')
        self.assertEqual([w for w in core.writes if w['ieee'] == hall], [])

    def test_5_0_1_lines_keep_meaning_adoption(self):
        e, _ = asyncio.run(make('synthetic.json', patch=legacy))
        stairs = e.store.switch(by_name(e, 'Stairs switch')['ieee'])
        hall = e.store.switch(by_name(e, 'Hallway switch')['ieee'])
        L = v5.s_from_legacy
        self.assertEqual(sorted(hall['sens'].values()), [L(0x03)] * 2)
        self.assertEqual(sorted(stairs['sens'].values()), [20, 70, 70])

    def test_switch_is_read_and_written_after_ota(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True, patch=legacy)
            hall = by_name(e, 'Hallway switch')['ieee']
            sw = core.switches[hall]
            sw.sources = v5.sources_from_legacy(sw.sources)
            sw.sense_api = 3
            await e._read_api(e.devices[hall])
            await e.add_source(hall, by_name(e, 'Smoke alarm')['ieee'])
            return e, core, hall
        e, core, hall = asyncio.run(go())
        self.assertEqual(e.switch_view(hall)['api'], 'ok')
        sent = v5.decode_sources(cmds(core, v5.CMD_SOURCES)[0]['payload'])
        self.assertEqual([l['sens'] for l in sent], [v5.s_from_legacy(0x03)] * 3)

    def test_after_ota_504_stored_s_follow_new(self):
        """5.0.3 -> 5.0.4 (SENSE_API 5): the switch converts its NV s (sens_from_v8), the store does the same once."""
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            stairs = by_name(e, 'Stairs switch')['ieee']
            before = dict(e.store.switch(stairs)['sens'])
            sw = core.switches[stairs]
            sw.sources = v5.encode_sources([(l['nwk'], l['zones'], v5.s_to_api(l['sens'], 3, 5))
                                            for l in v5.decode_sources(sw.sources)])
            sw.sense_api = 5
            await e.read_config(stairs)
            await e.add_source(stairs, by_name(e, 'Smoke alarm')['ieee'])
            return e, core, stairs, before
        e, core, stairs, before = asyncio.run(go())
        sw = e.store.switch(stairs)
        self.assertEqual(sw['sens_api'], 5)
        self.assertEqual({k: sw['sens'][k] for k in before}, {k: v5.s_to_api(v, 3, 5) for k, v in before.items()})
        self.assertEqual(e.switch_view(stairs)['api'], 'ok')
        sent = v5.decode_sources(cmds(core, v5.CMD_SOURCES)[-1]['payload'])
        self.assertEqual(sent[-1]['sens'], v5.SENS_DEFAULT)
        self.assertEqual(sorted(l['sens'] for l in sent[:-1]), sorted(v5.s_to_api(v, 3, 5) for v in before.values()))

    def test_504_s_moved_switch_taken_never(self):
        """Calibrate / the 24 h self-tuning move s on the switch; Ripple takes it before any sources write."""
        def build5(fx):
            for st in fx['state'].values():
                st['sense_api'] = 5
        async def go():
            e, core = await make('synthetic.json', allow_writes=True, patch=build5)
            stairs = by_name(e, 'Stairs switch')['ieee']
            sw = core.switches[stairs]
            lines = v5.decode_sources(sw.sources)
            moved = [(l['nwk'], l['zones'], 57 if i == 0 else l['sens']) for i, l in enumerate(lines)]
            sw.sources = v5.encode_sources(moved)  # the switch moved the first line to s 57 by itself
            await e.add_source(stairs, by_name(e, 'Smoke alarm')['ieee'])
            return e, core, stairs, lines
        e, core, stairs, lines = asyncio.run(go())
        sent = v5.decode_sources(cmds(core, v5.CMD_SOURCES)[-1]['payload'])
        self.assertEqual(sent[0]['sens'], 57)
        self.assertEqual([l['sens'] for l in sent[1:len(lines)]], [l['sens'] for l in lines[1:]])
        self.assertEqual(sent[-1]['sens'], v5.SENS_DEFAULT)

    def test_504_self_tuning_switch_writes_0xff4f(self):
        def build5(fx):
            for st in fx['state'].values():
                st['sense_api'] = 5
        async def go():
            e, core = await make('synthetic.json', allow_writes=True, patch=build5)
            stairs = by_name(e, 'Stairs switch')['ieee']
            self_tune_before = e.devices[stairs]['config'].get('self_tune')
            await e.set_switch_settings(stairs, {'self_tune': True})
            return core, stairs, self_tune_before
        core, stairs, before = asyncio.run(go())
        self.assertEqual(before, 0)
        self.assertIn((v5.A_SELF_TUNE, 1), [(w['attr'], w['value']) for w in core.writes if w.get('ieee') == stairs and 'attr' in w])
        e, _ = asyncio.run(make('synthetic.json'))
        with self.assertRaises(ValueError):
            e.validate_settings(by_name(e, 'Stairs switch')['ieee'], {'self_tune': True})

    def test_504_votes_no_a_cal(self):
        def build5(fx):
            for st in fx['state'].values():
                st['sense_api'] = 5
        e, _ = asyncio.run(make('synthetic.json', patch=build5))
        w = by_name(e, 'Kitchen worktop switch')
        self.assertTrue(all(r['state'] in ('usable', 'calibrated', 'below_level_min', 'blind') for r in e.links(w['ieee'])))
        self.assertNotIn('not_learned', {r['state'] for r in e.links(w['ieee'])})
        room = next(r for r in e.rooms() if r['name'] == 'Kitchen')
        self.assertFalse(room['needs_calibration'])

    def test_newer_api_asks_for_an_integration_update(self):
        def newer(fx):
            hall = next(d['ieee'] for d in fx['zha_devices'] if d['user_given_name'] == 'Hallway switch')
            fx['state'][hall]['sense_api'] = v5.SENSE_API + 1

        async def go():
            e, core = await make('synthetic.json', allow_writes=True, patch=newer)
            hall = by_name(e, 'Hallway switch')['ieee']
            with self.assertRaises(Outdated):
                await e.set_switch_settings(hall, {'off_s': 9})
            return e, core, hall
        e, core, hall = asyncio.run(go())
        self.assertEqual(e.switch_view(hall)['api'], 'update_integration')
        self.assertEqual([w for w in core.writes if w['ieee'] == hall], [])

    def test_sense_api_0_while_booting_falls_back(self):
        from custom_components.ripple_presence.engine import api_state
        self.assertEqual(api_state({'config': {'sense_api': 0}, 'fw': 0x1103339C}), 'ok')
        self.assertEqual(api_state({'config': {}, 'fw': 0x1103339B}), 'update_firmware')
        self.assertEqual(api_state({'config': {'sense_api': 2}, 'fw': 0x1103339C}), 'update_firmware')
        self.assertEqual(api_state({'config': {'sense_api': 3}, 'fw': 0x1103339B}), 'ok')


def _fleet(apis, lines_on=None):
    """Patch: sense_api per switch name (others keep the fixture's), lines_on (0xff46) per switch name."""
    def p(fx):
        by = {d.get('user_given_name'): d['ieee'] for d in fx['zha_devices']}
        for name, api in apis.items():
            fx['state'][by[name]]['sense_api'] = api
        for name, v in (lines_on or {}).items():
            fx['state'][by[name]]['lines_on'] = v
    return p


def _spy_reads(core):
    orig, core.read_log = core.zcl_read, []

    async def zcl_read(ieee, cluster, attrs, manuf):
        core.read_log += [(ieee, a) for a in attrs]
        return await orig(ieee, cluster, attrs, manuf)
    core.zcl_read = zcl_read


class Firmware505Tests(unittest.TestCase):
    """Firmware 5.0.5, SENSE_API 6: per-line state 0xff46, Live v4, Calibrate floor."""

    def test_api_6_is_accepted_and_configured(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True, patch=_fleet({'Stairs switch': 6}))
            stairs = by_name(e, 'Stairs switch')['ieee']
            await e.set_switch_settings(stairs, {'off_s': 9})
            return e, core, stairs
        e, core, stairs = asyncio.run(go())
        self.assertEqual(e.switch_view(stairs)['api'], 'ok')
        self.assertIn((v5.A_HOST_API, 6), [(w['attr'], w['value']) for w in core.writes if w['ieee'] == stairs and 'attr' in w])
        self.assertEqual(v5.decode_tune(cmds(core, v5.CMD_TUNE)[-1]['payload'])['off_s'], 9)
        self.assertEqual(v5.api_of(6), 5)  # same scale as 5.0.4: s default 50, MOTION_TAB_5
        self.assertEqual(v5.sens_default(6), v5.SENS_DEFAULT)

    def test_mixed_fleet_3_5_6_configured_each(self):
        apis = {'Hallway switch': 3, 'Kitchen switch': 5, 'Stairs switch': 6}
        e, _ = asyncio.run(make('synthetic.json', patch=_fleet(apis)))
        for name in apis:
            self.assertEqual(e.switch_view(by_name(e, name)['ieee'])['api'], 'ok', name)
        self.assertEqual(e.line_states(by_name(e, 'Kitchen switch')['ieee']), {})
        self.assertEqual(e.line_states(by_name(e, 'Hallway switch')['ieee']), {})

    def test_api_5_switch_unchanged_never_asked(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True, patch=_fleet({'Stairs switch': 5}),
                                 core_patch=_spy_reads)
            stairs = by_name(e, 'Stairs switch')['ieee']
            await e.add_source(stairs, by_name(e, 'Smoke alarm')['ieee'])
            return e, core, stairs
        e, core, stairs = asyncio.run(go())
        self.assertEqual(e.switch_view(stairs)['api'], 'ok')
        self.assertNotIn(v5.A_LINES_ON, [a for _, a in core.read_log])
        self.assertNotIn('lines_on', e.devices[stairs]['config'])
        self.assertEqual(e.line_states(stairs), {})
        self.assertEqual(v5.decode_sources(cmds(core, v5.CMD_SOURCES)[-1]['payload'])[-1]['sens'], v5.SENS_DEFAULT)

    def test_lines_read_start_follows_report(self):
        async def go():
            e, core = await make('synthetic.json', patch=_fleet({'Stairs switch': 6}, {'Stairs switch': 0b101}))
            stairs = by_name(e, 'Stairs switch')['ieee']
            first = e.line_states(stairs)
            core.report(stairs, v5.CLUSTER, v5.A_LINES_ON, 0b010)
            return e, stairs, first
        e, stairs, first = asyncio.run(go())
        hall, living, tv = (by_name(e, n)['ieee'] for n in ('Hallway switch', 'Living room switch', 'TV plug'))
        self.assertEqual(first, {hall: True, living: False, tv: True})
        self.assertEqual(e.line_states(stairs), {hall: False, living: True, tv: False})
        self.assertEqual({l['ieee']: l['detecting'] for l in e.links(stairs)}, {hall: False, living: True, tv: False})

    def test_lines_read_again_when_sources_change(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True,
                                 patch=_fleet({'Stairs switch': 6}, {'Stairs switch': 0b101}), core_patch=_spy_reads)
            stairs = by_name(e, 'Stairs switch')['ieee']
            n = sum(1 for i, a in core.read_log if i == stairs and a == v5.A_LINES_ON)
            await e.remove_source(stairs, by_name(e, 'Hallway switch')['ieee'])
            return e, core, stairs, n
        e, core, stairs, n = asyncio.run(go())
        living, tv = (by_name(e, n_)['ieee'] for n_ in ('Living room switch', 'TV plug'))
        self.assertEqual(sum(1 for i, a in core.read_log if i == stairs and a == v5.A_LINES_ON), n + 1)
        self.assertEqual(e.line_states(stairs), {living: False, tv: True})

    def test_line_states_unknown_until_sources(self):
        e, _ = asyncio.run(make('synthetic.json', patch=_fleet({'Stairs switch': 6})))
        stairs = by_name(e, 'Stairs switch')['ieee']
        e.devices[stairs]['config'].pop('sources')
        self.assertIsNone(e.line_states(stairs))
        e.devices[stairs]['config']['sense_api'] = None
        self.assertIsNone(e.line_states(stairs))

    def test_cal_floor_fr_s_0_505(self):
        async def go(api, rate):
            e, core = await make('synthetic.json', allow_writes=True, patch=_fleet({'Stairs switch': api}))
            stairs = by_name(e, 'Stairs switch')['ieee']
            await e.set_switch_settings(stairs, {'advanced': {'cal_min_rate': rate}})
            return v5.decode_tune(cmds(core, v5.CMD_TUNE)[-1]['payload'])['core_max_bins']
        self.assertEqual(asyncio.run(go(6, 0)), 0)
        self.assertEqual(asyncio.run(go(6, 2.5)), 5)
        self.assertEqual(asyncio.run(go(5, 1)), 2)
        with self.assertRaises(ValueError):
            asyncio.run(go(5, 0))
        with self.assertRaises(ValueError):
            asyncio.run(go(6, 8.5))
        with self.assertRaises(ValueError):
            asyncio.run(go(6, 1.25))


class RoomTriggerTests(unittest.TestCase):
    """The room turns on only when x of its y lines detect (any / all / custom)."""
    HALL = 'area:hallway'  # Hallway switch (5.0.4, one line: its motion) + Stairs switch (5.0.5, three lines from 0xff46)

    @staticmethod
    async def _hall(lines_on=0b101, writes=False):
        e, core = await make('synthetic.json', allow_writes=writes,
                             patch=_fleet({'Hallway switch': 5, 'Stairs switch': 6}, {'Stairs switch': lines_on}))
        return e, core, by_name(e, 'Hallway switch')['ieee'], by_name(e, 'Stairs switch')['ieee']

    def test_any_is_the_default(self):
        async def go():
            e, core, hall, stairs = await self._hall(lines_on=0)
            t0 = e.room(self.HALL)
            core.report(hall, v5.CLUSTER, v5.A_ZONE_STATE, 1)
            on = e.room(self.HALL)
            core.report(hall, v5.CLUSTER, v5.A_ZONE_STATE, 0)
            held = e.room(self.HALL)
            return e, t0, on, held, core.writes
        e, t0, on, held, writes = asyncio.run(go())
        self.assertEqual(e.room_settings(self.HALL)['trigger_mode'], 'any')
        self.assertEqual((t0['trigger']['mode'], t0['trigger']['threshold'], t0['trigger']['total']), ('any', 1, 4))
        self.assertTrue(on['occupied'])
        self.assertEqual(on['trigger']['active'], 1)
        self.assertTrue(held['occupied'])
        self.assertIsNotNone(held['hold_until'])
        self.assertEqual(writes, [])

    def test_mixed_fleet_counts_504_switch_line(self):
        e, core, hall, stairs = asyncio.run(self._hall())
        lines = e.room_lines(e.room(self.HALL)['members'])
        hall_lines = [x for x in lines if x[0] == hall]
        self.assertEqual(hall_lines, [(hall, None, False)])
        self.assertEqual(sorted(on for rx, tx, on in lines if rx == stairs), [False, True, True])

    def test_all_needs_every_line_and_holds_after_drop(self):
        async def go():
            e, core, hall, stairs = await self._hall()
            await e.set_room_settings(self.HALL, {'trigger_mode': 'all', 'off_s': 1})
            core.report(hall, v5.CLUSTER, v5.A_ZONE_STATE, 1)
            three = e.room(self.HALL)
            core.report(stairs, v5.CLUSTER, v5.A_LINES_ON, 0b111)
            four = e.room(self.HALL)
            core.report(stairs, v5.CLUSTER, v5.A_LINES_ON, 0b011)
            held = e.room(self.HALL)
            await asyncio.sleep(1.2)
            return three, four, held, e.room(self.HALL), core.writes
        three, four, held, after, writes = asyncio.run(go())
        self.assertEqual((three['trigger']['active'], three['trigger']['threshold']), (3, 4))
        self.assertFalse(three['occupied'])
        self.assertTrue(four['occupied'])
        self.assertTrue(held['occupied'])
        self.assertIsNotNone(held['hold_until'])
        self.assertFalse(after['occupied'])
        self.assertEqual(writes, [])

    def test_all_ignores_505_switch_no_sources(self):
        """The switch with no Ripple sender has no line, so `all` turns on when every real line detects."""
        async def go():
            e, core, hall, stairs = await self._hall(lines_on=0)
            e.devices[hall]['config']['sources'] = v5.encode_sources([])
            e.devices[hall]['config'].update(sense_api=6, lines_on=0)
            await e.set_room_settings(self.HALL, {'trigger_mode': 'all'})
            before = e.room(self.HALL)
            core.report(stairs, v5.CLUSTER, v5.A_LINES_ON, 0b111)
            return e, hall, before, e.room(self.HALL)
        e, hall, before, after = asyncio.run(go())
        self.assertEqual([x for x in e.room_lines(e.room(self.HALL)['members']) if x[0] == hall], [])
        self.assertEqual((before['trigger']['total'], before['trigger']['threshold']), (3, 3))
        self.assertFalse(before['occupied'])
        self.assertTrue(after['occupied'])
        self.assertEqual(after['trigger']['active'], 3)

    def test_custom_k_clamp_when_lines_go_away(self):
        async def go():
            e, core, hall, stairs = await self._hall(lines_on=0b011, writes=True)
            await e.set_room_settings(self.HALL, {'trigger_mode': 'custom', 'trigger_k': 3})
            core.report(hall, v5.CLUSTER, v5.A_ZONE_STATE, 1)
            three = e.room(self.HALL)
            await e.set_room_settings(self.HALL, {'trigger_k': 4})
            short = e.room(self.HALL)
            await e.remove_source(stairs, by_name(e, 'TV plug')['ieee'])
            fewer = e.room(self.HALL)
            return e, three, short, fewer
        e, three, short, fewer = asyncio.run(go())
        self.assertTrue(three['occupied'])
        self.assertEqual(three['trigger']['threshold'], 3)
        self.assertEqual((short['moving'], short['trigger']['active']), ([], 3))
        self.assertIsNotNone(short['hold_until'])  # below the new threshold: only the off_s hold keeps it on
        self.assertEqual(fewer['trigger']['total'], 3)
        self.assertEqual((fewer['trigger']['k'], fewer['trigger']['threshold'], fewer['trigger']['clamped']), (4, 3, True))
        self.assertEqual(e.room_settings(self.HALL)['trigger_k'], 4)

    def test_parked_silent_lines_not_counted(self):
        async def go():
            e, core, hall, stairs = await self._hall(writes=True)
            srcs = e.store.switch(stairs)['sources']
            await e.set_sources(stairs, srcs, sens={srcs[2]: 0}, parked=[srcs[1]])
            return e, stairs, srcs
        e, stairs, srcs = asyncio.run(go())
        self.assertEqual([tx for _, tx, _ in e.room_lines([stairs])], [srcs[0]])

    def test_threshold_met_turns_room_on(self):
        async def go():
            e, core, hall, stairs = await self._hall(lines_on=0)
            await e.set_room_settings(self.HALL, {'trigger_mode': 'custom', 'trigger_k': 2})
            core.report(stairs, v5.CLUSTER, v5.A_LINES_ON, 0b011)  # Occupancy of the switch not reported yet
            custom = e.room(self.HALL)
            await e.set_room_settings(self.HALL, {'trigger_mode': 'all'})
            core.report(stairs, v5.CLUSTER, v5.A_LINES_ON, 0b111)
            core.report(hall, v5.CLUSTER, v5.A_ZONE_STATE, 1)
            all_ = e.room(self.HALL)
            return e, stairs, hall, custom, all_
        e, stairs, hall, custom, all_ = asyncio.run(go())
        self.assertFalse(e.devices[stairs]['live'].get('motion'))
        self.assertTrue(custom['occupied'])
        self.assertIsNone(custom['hold_until'])
        self.assertEqual(custom['moving'], [stairs])
        self.assertIsNotNone(custom['since'])
        self.assertTrue(all_['occupied'])
        self.assertEqual(sorted(all_['moving']), sorted([hall, stairs]))

    def test_occupancy_flipping_later_has_no_glitch(self):
        async def go():
            e, core, hall, stairs = await self._hall(lines_on=0)
            await e.set_room_settings(self.HALL, {'trigger_mode': 'custom', 'trigger_k': 2})
            seen = []
            e.listeners.append(lambda: seen.append(e.room(self.HALL)['occupied']))
            core.report(stairs, v5.CLUSTER, v5.A_LINES_ON, 0b011)
            core.report(stairs, v5.OCCUPANCY, v5.A_OCCUPANCY, 1)
            core.report(stairs, v5.CLUSTER, v5.A_ZONE_STATE, 1)
            return seen, e.room(self.HALL)
        seen, after = asyncio.run(go())
        self.assertTrue(seen)
        self.assertNotIn(False, seen)
        self.assertTrue(after['occupied'])

    def test_hold_starts_when_504_switch_goes_off(self):
        t = [1000.0]
        async def go():
            with patch('custom_components.ripple_presence.engine.now', lambda: t[0]):
                e, core, hall, stairs = await self._hall(lines_on=0b001)
                await e.set_room_settings(self.HALL, {'trigger_mode': 'custom', 'trigger_k': 2, 'off_s': 30})
                core.report(hall, v5.OCCUPANCY, v5.A_OCCUPANCY, 1)
                on = e.room(self.HALL)
                t[0] = 1010.0
                core.report(hall, v5.OCCUPANCY, v5.A_OCCUPANCY, 0)
                t[0] = 1025.0  # read later: the hold still counts from the drop
                held = e.room(self.HALL)
                return on, held
        on, held = asyncio.run(go())
        self.assertTrue(on['occupied'])
        self.assertTrue(held['occupied'])
        self.assertEqual(held['hold_until'], 1040.0)

    def test_hold_starts_when_threshold_raised(self):
        t = [2000.0]
        async def go():
            with patch('custom_components.ripple_presence.engine.now', lambda: t[0]):
                e, core, hall, stairs = await self._hall(lines_on=0b011)
                await e.set_room_settings(self.HALL, {'trigger_mode': 'custom', 'trigger_k': 2, 'off_s': 30})
                on = e.room(self.HALL)
                t[0] = 2005.0
                await e.set_room_settings(self.HALL, {'trigger_k': 3})
                t[0] = 2020.0
                held = e.room(self.HALL)
                # from 'any' with a switch in motion straight to 'all': the hold starts at the change too
                core.report(hall, v5.CLUSTER, v5.A_ZONE_STATE, 1)
                await e.set_room_settings(self.HALL, {'trigger_mode': 'any'})
                t[0] = 2100.0
                await e.set_room_settings(self.HALL, {'trigger_mode': 'all'})
                t[0] = 2110.0
                from_any = e.room(self.HALL)
                return on, held, from_any
        on, held, from_any = asyncio.run(go())
        self.assertTrue(on['occupied'])
        self.assertEqual(held['hold_until'], 2035.0)
        self.assertTrue(held['occupied'])
        self.assertEqual((from_any['trigger']['active'], from_any['trigger']['threshold']), (3, 4))
        self.assertEqual(from_any['hold_until'], 2130.0)

    def test_bad_values_are_refused(self):
        async def go():
            e, core, hall, stairs = await self._hall()
            errs = []
            for bad in ({'trigger_mode': 'most'}, {'trigger_k': 0}, {'trigger_k': 'x'}):
                try:
                    await e.set_room_settings(self.HALL, bad)
                except ValueError as err:
                    errs.append(str(err))
            return e, errs
        e, errs = asyncio.run(go())
        self.assertEqual(len(errs), 3)
        self.assertEqual(e.room_settings(self.HALL)['trigger_mode'], 'any')


if __name__ == '__main__':
    unittest.main()

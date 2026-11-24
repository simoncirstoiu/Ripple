import asyncio
import os
import sys
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, '..'))
sys.path.insert(0, HERE)
from custom_components.ripple_presence import v5  # noqa: E402
from custom_components.ripple_presence.live import LiveBudget  # noqa: E402
from test_engine import make  # noqa: E402


class CodecTests(unittest.TestCase):
    def test_encode_live(self):
        p = v5.encode_live(60, 100, [(0x1234, 0x03), (0x5678, 0)])
        self.assertEqual(p.hex(), '3c000a341203785600')

    def test_encode_live_refuses_tmin_below_100(self):
        self.assertEqual(v5.encode_live(10, 20, [(1, 0)])[2], 10)

    def test_encode_live_refuses_bad_values(self):
        with self.assertRaises(ValueError):
            v5.encode_live(3601, 100, [(1, 0)])
        with self.assertRaises(ValueError):
            v5.encode_live(10, 100, [])

    def test_decode_live(self):
        fr = bytes([2, 7, 2, 2 | 1 << 4]) + (1000).to_bytes(4, 'little') + bytes([0x31, 0, 100, 90, 4, 0x01, 10, 130, 120, 6]) \
            + bytes([1, 0x27]) + (8).to_bytes(2, 'little') + (0xFFFF).to_bytes(2, 'little')
        f = v5.decode_live(fr)
        self.assertEqual((f['seq'], f['dropped']), (7, 2))
        self.assertEqual([r['ms'] for r in f['records']], [1000, 1100])
        self.assertTrue(f['records'][0]['on'] and f['records'][0]['gate'])
        self.assertEqual((f['records'][0]['q'], f['records'][0]['q2'], f['records'][0]['d']), (100, 90, 4))
        self.assertEqual(f['info'][0], {'idx': 1, 'state': 0x27, 'm': 8, 'since_on_s': None})

    def test_decode_live_v4_reads_the_vote_bit(self):
        # 5.0.5: bit 0x20 of a record is the line's vote in its zones (LV_VOTE), no longer the gate bit
        fr = bytes([4, 1, 0, 3]) + (500).to_bytes(4, 'little') + bytes([0x30 | 2, 0, 140, 140, 5, 0x10 | 1, 5, 130, 130, 4,
                                                                         0x40, 9, 3, 3, 0])
        f = v5.decode_live(fr)
        self.assertEqual(f['version'], 4)
        self.assertEqual([(r['idx'], r['on'], r['vote'], r['gate']) for r in f['records']],
                         [(2, True, True, None), (1, True, False, None), (0, False, False, None)])
        self.assertTrue(f['records'][2]['usable'])

    def test_decode_live_v3_has_gate_bit_but_no_vote(self):
        fr = bytes([3, 1, 0, 1]) + bytes(4) + bytes([0x30, 0, 140, 140, 5])
        r = v5.decode_live(fr)['records'][0]
        self.assertEqual((r['gate'], r['vote']), (True, None))

    def test_decode_live_refuses_short_or_unknown(self):
        self.assertIsNone(v5.decode_live(b'\x05' + bytes(7)))
        self.assertEqual(v5.decode_live(b'\x04' + bytes(7))['version'], 4)  # Live v4 of 5.0.5
        self.assertEqual(v5.decode_live(b'\x03' + bytes(7))['version'], 3)  # Live v3 of 5.0.4
        self.assertIsNone(v5.decode_live(bytes([2, 0, 0, 3]) + bytes(4)))
        self.assertIsNone(v5.decode_live(bytes([1, 0, 0, 0]) + bytes(4)))  # Live v1 of 5.0.2


class SessionTests(unittest.TestCase):
    def _room_with_lines(self, e):
        return next(r for r in e.rooms() if e.live.room_lines(r['id']))

    def _save_during_live(self, delta):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            r = self._room_with_lines(e)
            rx, tx = e.live.room_lines(r['id'])[0]
            await e.live.start(r['id'], 60)
            sens = e.store.switch(rx)['sens'][tx]
            n = len(core.writes)
            await e.save_line(rx, tx, sens - delta if sens + delta > v5.S_MAX else sens + delta)
            return [w.get('command', w.get('attr')) for w in core.writes[n:] if w['ieee'] == rx]
        return asyncio.run(go())

    def test_saving_same_value_during_live_writes(self):
        self.assertEqual([x for x in self._save_during_live(0) if x != v5.A_HOST_API], [])

    def test_saving_new_value_during_live_writes(self):
        sent = [x for x in self._save_during_live(1) if x in (v5.CMD_SOURCES, v5.CMD_LIVE)]
        self.assertEqual(sent, [v5.CMD_SOURCES, v5.CMD_LIVE])

    def test_start_sends_only_to_room_receivers(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            r = self._room_with_lines(e)
            await e.live.start(r['id'], 60)
            return e, core, r
        e, core, r = asyncio.run(go())
        sent = {w['ieee'] for w in core.writes if w.get('command') == v5.CMD_LIVE}
        receivers = {rx for rx, _ in e.live.room_lines(r['id'])}
        self.assertTrue(sent)
        self.assertLessEqual(sent, receivers)

    def test_stop_sends_zero_duration(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            r = self._room_with_lines(e)
            await e.live.start(r['id'], 60)
            n = len(core.writes)
            await e.live.stop(r['id'])
            return core.writes[n:], e
        new, e = asyncio.run(go())
        stops = [w for w in new if w.get('command') == v5.CMD_LIVE]
        self.assertTrue(stops)
        self.assertTrue(all(w['payload'][:2] == b'\x00\x00' for w in stops))
        self.assertEqual(e.live.sessions, {})

    def test_candidate_goes_only_to_its_line(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            r = self._room_with_lines(e)
            rx, tx = e.live.room_lines(r['id'])[0]
            await e.live.start(r['id'], 60)
            n = len(core.writes)
            await e.live.set_candidate(r['id'], rx, tx, 45)
            with self.assertRaises(ValueError):
                await e.live.set_candidate(r['id'], rx, tx, 101)
            return core.writes[n:], e, rx, tx
        new, e, rx, tx = asyncio.run(go())
        w = [x for x in new if x.get('command') == v5.CMD_LIVE]
        self.assertEqual({x['ieee'] for x in w}, {rx})
        p = w[-1]['payload']
        lines = {int.from_bytes(p[i:i + 2], 'little'): p[i + 2] for i in range(3, len(p), 3)}
        self.assertEqual(lines[e.devices[tx]['nwk']], 45)
        self.assertEqual(sorted(set(lines.values())), [0, 45])

    def test_live_line_streams_line(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            r = self._room_with_lines(e)
            rx, tx = e.live.room_lines(r['id'])[0]
            view = await e.live.start(r['id'], 60, [[rx, tx]])
            with self.assertRaises(KeyError):
                await e.live.start(r['id'], 60, [['aa', 'bb']])
            return e, core, r, rx, tx, view
        e, core, r, rx, tx, view = asyncio.run(go())
        w = [x for x in core.writes if x.get('command') == v5.CMD_LIVE]
        self.assertEqual({x['ieee'] for x in w}, {rx})
        p = w[-1]['payload']
        self.assertEqual([int.from_bytes(p[i:i + 2], 'little') for i in range(3, len(p), 3)], [e.devices[tx]['nwk']])
        self.assertEqual(view[r['id']]['lines'], [{'rx': rx, 'tx': tx}])

    def test_budget_refuses_too_many_frames(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            r = self._room_with_lines(e)
            e.live.frames_per_s = lambda plan: 31.0
            await e.live.start(r['id'], 60)
        with self.assertRaises(LiveBudget):
            asyncio.run(go())

    def test_frame_maps_records_to_lines(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            r = self._room_with_lines(e)
            rx, tx = e.live.room_lines(r['id'])[0]
            got = []
            e.live.listeners.append(got.append)
            srcs = v5.decode_sources(e.devices[rx]['config'].get('sources')) or []
            idx = [l['nwk'] for l in srcs].index(e.devices[tx]['nwk'])
            fr = bytes([2, 1, 0, 1]) + (5000).to_bytes(4, 'little') + bytes([idx | 0x10, 0, 140, 140, 5])
            e.live.on_frame(rx, fr)
            return got, tx
        got, tx = asyncio.run(go())
        ev = [g for g in got if g['type'] == 'live'][0]
        self.assertEqual(ev['records'][0]['tx'], tx)
        self.assertTrue(ev['records'][0]['on'])
        self.assertIsNotNone(ev['records'][0]['last_on'])

    def test_live_v4_frame_carries_vote_each_line(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            r = self._room_with_lines(e)
            rx, tx = e.live.room_lines(r['id'])[0]
            got = []
            e.live.listeners.append(got.append)
            srcs = v5.decode_sources(e.devices[rx]['config'].get('sources')) or []
            idx = [l['nwk'] for l in srcs].index(e.devices[tx]['nwk'])
            for vote in (0x20, 0):
                fr = bytes([4, 1, 0, 1]) + (5000).to_bytes(4, 'little') + bytes([idx | 0x10 | vote, 0, 140, 140, 5])
                e.live.on_frame(rx, fr)
            return got
        got = asyncio.run(go())
        recs = [g['records'][0] for g in got if g['type'] == 'live']
        self.assertEqual([(r['on'], r['vote'], r['gate']) for r in recs], [(True, True, None), (True, False, None)])

    def test_live_start_follows_clusters_replaced(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            gen = {'n': 0}
            calls = []
            core.clusters = lambda ieee: (gen['n'],)
            sub = core.subscribe
            core.subscribe = lambda ieee, cb: calls.append(ieee) or sub(ieee, cb)
            e._subscribe()
            rx = e.live.room_lines(self._room_with_lines(e)['id'])[0][0]
            calls.clear()
            e._subscribe()
            unchanged = list(calls)
            gen['n'] = 1
            await e.live.start(self._room_with_lines(e)['id'], 60)
            return unchanged, calls, rx, len(core.subs[rx])
        unchanged, calls, rx, n = asyncio.run(go())
        self.assertEqual(unchanged, [])
        self.assertIn(rx, calls)
        self.assertEqual(n, 1)


if __name__ == '__main__':
    unittest.main()

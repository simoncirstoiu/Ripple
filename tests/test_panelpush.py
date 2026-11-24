import asyncio
import json
import os
import sys
import unittest
from unittest.mock import patch

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, '..'))
sys.path.insert(0, HERE)
from custom_components.ripple_presence import v5  # noqa: E402
from custom_components.ripple_presence.panelpush import PanelPush, build_views, _dump  # noqa: E402
from test_engine import by_name, make  # noqa: E402


def ready(e):
    return [d['ieee'] for d in e.ripple_devices() if e.store.switch(d['ieee'])]


def views_of(e):
    return build_views(e, e.zb.allow_writes, 'entry', ready(e))


class Sink:
    def __init__(self):
        self.msgs = []

    def __call__(self, m):
        self.msgs.append(json.loads(json.dumps(m)))  # what goes over the socket must be plain JSON


async def pushed(e):
    loop = asyncio.get_running_loop()
    p = PanelPush(lambda: views_of(e), loop)
    e.listeners.append(p.changed)
    s = Sink()
    unsub = p.subscribe(s)
    return p, s, unsub


async def settle():
    for _ in range(3):
        await asyncio.sleep(0.07)


class Client:
    """Applies snapshots and deltas the way the panel does."""
    def __init__(self):
        self.rev = None
        self.st = None

    def apply(self, m):
        m = json.loads(json.dumps(m))  # what goes over the socket is a copy
        if m['type'] == 'snapshot':
            if self.rev is not None and m['rev'] < self.rev:
                return
            self.rev = m['rev']
            self.st = {k: m[k] for k in ('meta', 'others', 'zha')}
            self.st['rooms'] = {r['id']: r for r in m['rooms']}
            self.st['order'] = [r['id'] for r in m['rooms']]
            self.st['switches'] = {v['ieee']: v for v in m['switches']}
            return
        if m['type'] != 'delta' or self.st is None or m['rev'] <= self.rev:
            return
        self.rev = m['rev']
        for ieee, ch in m.get('switches', {}).items():
            cur = dict(self.st['switches'].get(ieee, {}))
            for f in ch.get('_drop', []):
                cur.pop(f, None)
            cur.update({f: v for f, v in ch.items() if f != '_drop'})
            self.st['switches'][ieee] = cur
        for ieee in m.get('gone', []):
            self.st['switches'].pop(ieee, None)
        self.st['rooms'].update(m.get('rooms', {}))
        for rid in m.get('rooms_gone', []):
            self.st['rooms'].pop(rid, None)
        if 'room_order' in m:
            self.st['order'] = m['room_order']
        for k in ('meta', 'others', 'zha'):
            if k in m:
                self.st[k] = m[k]

    def same_as(self, views):
        return (_dump({k: self.st[k] for k in ('meta', 'others', 'zha')}) == _dump({k: views[k] for k in ('meta', 'others', 'zha')})
                and self.st['order'] == [r['id'] for r in views['rooms']]
                and _dump([self.st['rooms'][r] for r in self.st['order']]) == _dump(views['rooms'])
                and _dump(self.st['switches']) == _dump(views['switches']))


class PanelPushTests(unittest.TestCase):
    def test_snapshot_inside_window_then_revert(self):
        """A value goes A->B, the panel loads a snapshot (B), the value goes back to A before the flush: the
        panel must end on A, not stay on B."""
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            loop = asyncio.get_running_loop()
            p = PanelPush(lambda: views_of(e), loop)
            c = Client()
            p.subscribe(c.apply)
            await settle()
            e.status['probing'] = True
            p.changed()
            c.apply(p.snapshot()[1])  # the panel's _load() inside the window
            e.status['probing'] = False
            p.changed()
            await settle()
            return c.same_as(views_of(e)), c.st['meta']['status']['probing']
        same, probing = asyncio.run(go())
        self.assertFalse(probing)
        self.assertTrue(same)

    def test_snapshot_first_then_nothing_without_change(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            p, s, _ = await pushed(e)
            p.changed()
            await settle()
            return s.msgs
        msgs = asyncio.run(go())
        self.assertEqual([m['type'] for m in msgs], ['snapshot'])
        self.assertTrue(msgs[0]['switches'] and msgs[0]['rooms'])

    def test_switch_changed_sends_changed_keys(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            hall = by_name(e, 'Hallway switch')['ieee']
            p, s, _ = await pushed(e)
            await e.set_switch_settings(hall, {'off_s': 45})
            await settle()
            return hall, s.msgs, p
        hall, msgs, p = asyncio.run(go())
        deltas = [m for m in msgs if m['type'] == 'delta']
        self.assertTrue(deltas)
        for d in deltas:
            self.assertEqual(set(d.get('switches', {})), {hall})
            self.assertNotIn('zha', d)
            self.assertLess(len(d['switches'][hall]), len(msgs[0]['switches'][0]))
        self.assertEqual([d['rev'] for d in deltas], sorted({d['rev'] for d in deltas}))
        self.assertEqual(p.rev, deltas[-1]['rev'])

    def test_zone_report_delta_is_small(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            hall = by_name(e, 'Hallway switch')['ieee']
            p, s, _ = await pushed(e)
            core.report(hall, v5.CLUSTER, v5.A_ZONE_STATE, 1)
            await settle()
            return s.msgs
        msgs = asyncio.run(go())
        deltas = [m for m in msgs if m['type'] == 'delta']
        self.assertTrue(deltas)
        for d in deltas:
            self.assertLess(len(_dump(d)), 5000)
            self.assertNotIn('zha', d)

    def test_rooms_go_per_id_removed_named(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            sw = [by_name(e, 'Stairs switch')['ieee']]
            p, s, _ = await pushed(e)
            r = e.create_room('Open space', sw)
            await settle()
            e.delete_room(r['id'])
            await settle()
            return r['id'], s.msgs
        rid, msgs = asyncio.run(go())
        deltas = [m for m in msgs if m['type'] == 'delta']
        self.assertTrue(any(rid in d.get('rooms', {}) for d in deltas))
        self.assertTrue(any(rid in d.get('rooms_gone', []) for d in deltas))
        for d in deltas:
            self.assertLessEqual(len(d.get('rooms', {})), 3)

    def test_unsubscribe_and_close(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            p, s, unsub = await pushed(e)
            s2 = Sink()
            p.subscribe(s2)
            unsub()
            hall = by_name(e, 'Hallway switch')['ieee']
            await e.set_switch_settings(hall, {'off_s': 50})
            await settle()
            n1 = len(s.msgs)
            p.close()
            return n1, s.msgs, s2.msgs, p
        n1, m1, m2, p = asyncio.run(go())
        self.assertEqual(n1, 1)
        self.assertEqual(len(m1), 1)
        self.assertEqual(m2[-1], {'type': 'closed'})
        self.assertEqual(p._conns, {})

    def test_every_operation_changes_views_calls(self):
        """Coverage: if what the panel would show moved, the engine must have announced it."""
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            hall = by_name(e, 'Hallway switch')['ieee']
            sw = e.store.switch(hall)
            src = sw['sources'][0]
            room = next(r for r in e.rooms() if hall in r['members'])
            calls = []
            e.listeners.append(lambda: calls.append(1))
            ops = [
                ('settings', lambda: e.set_switch_settings(hall, {'off_s': 33})),
                ('save_line', lambda: e.save_line(hall, src, 41)),
                ('room_settings', lambda: e.set_room_settings(room['id'], {'off_s': 20})),
                ('zone_on', lambda: asyncio.sleep(0, core.report(hall, v5.CLUSTER, v5.A_ZONE_STATE, 1))),
                ('read_lines', lambda: e._read_lines(e.devices[hall])),
                ('poll', lambda: e.poll_device(e.devices[hall])),
                ('read_config', lambda: e.read_config(hall)),
                ('calibrate', lambda: e.calibrate([hall], 120)),
                ('live_start', lambda: e.live.start(room['id'], 60)),
                ('live_stop', lambda: e.live.stop(room['id'])),
                ('zone_off', lambda: asyncio.sleep(0, core.report(hall, v5.CLUSTER, v5.A_ZONE_STATE, 0))),
                ('refresh', lambda: e.refresh()),
            ]
            missed = []
            for name, op in ops:
                before = _dump(views_of(e))
                calls.clear()
                try:
                    await op()
                except Exception as err:  # an op the fixture cannot do still must not change silently
                    if _dump(views_of(e)) != before and not calls:
                        missed.append((name, repr(err)))
                    continue
                await asyncio.sleep(0)
                if _dump(views_of(e)) != before and not calls:
                    missed.append(name)
            return missed
        with patch('custom_components.ripple_presence.engine.DIAG_FRESH_S', 0):
            self.assertEqual(asyncio.run(go()), [])

    def test_views_are_plain_json(self):
        async def go():
            e, core = await make('synthetic.json', allow_writes=True)
            return views_of(e)
        v = asyncio.run(go())
        json.dumps(v)  # no default=str: a non-JSON value must fail here
        self.assertTrue(all('left' not in s for s in v['meta']['live'].values()))


if __name__ == '__main__':
    unittest.main()

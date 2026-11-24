import asyncio
import unittest

from custom_components.ripple_presence import zigbee as zb
from custom_components.ripple_presence.bindings import parse_binds

from .test_zigbee import FakeCore

SRC, DST = '00:11:22:33:44:55:66:77', '88:99:aa:bb:cc:dd:ee:ff'
RESP = {'replies': [[0, 2, 0, [
    {'SrcEndpoint': 1, 'ClusterId': 6, 'DstAddress': {'addrmode': 3, 'nwk': None, 'ieee': [0xff, 0xee, 0xdd, 0xcc, 0xbb, 0xaa, 0x99, 0x88], 'endpoint': 4}},
    {'SrcEndpoint': 2, 'ClusterId': 6, 'DstAddress': {'addrmode': 1, 'nwk': 5, 'ieee': None, 'endpoint': None}}]]]}


class ParseTests(unittest.TestCase):
    def test_parse_device_and_group_bindings(self):
        b = parse_binds(RESP)
        self.assertEqual(b[0], {'src_ep': 1, 'cluster': 6, 'dst_ieee': DST, 'dst_ep': 4, 'group': None})
        self.assertEqual(b[1]['group'], 5)


class GuardTests(unittest.TestCase):
    def _z(self, **kw):
        core = FakeCore()
        z = zb.Zigbee(core, spacing_s=0, **kw)
        asyncio.run(z.detect())
        return z, core

    def test_bind_refused_when_read_only(self):
        z, core = self._z()
        with self.assertRaises(zb.WritesDisabled):
            asyncio.run(z.bind(SRC, 1, DST, 4, 6))

    def test_bind_refused_when_target_protected(self):
        z, core = self._z(allow_writes=True, protected=[DST])
        with self.assertRaises(zb.Protected):
            asyncio.run(z.bind(SRC, 1, DST, 4, 6))

    def test_unbind_always_targets_endpoint(self):
        z, core = self._z(allow_writes=True)
        core.binds = {'replies': [[0, 3, 0, RESP['replies'][0][3] + [
            {'SrcEndpoint': 1, 'ClusterId': 8, 'DstAddress': {'addrmode': 3, 'ieee': DST, 'endpoint': 4}},
            {'SrcEndpoint': 1, 'ClusterId': 6, 'DstAddress': {'addrmode': 3, 'ieee': DST, 'endpoint': 5}}]]]}
        asyncio.run(z.unbind(SRC, 1, DST, 6))
        sent = [(m['src_ep'], m['cluster'], m['dst'], m['dst_ep']) for m in core.sent if m['type'] == 'zdo_unbind']
        self.assertEqual(sent, [(1, 6, DST, 4), (1, 6, DST, 5)])

    def test_unbind_no_target_is_refused(self):
        z, core = self._z(allow_writes=True)
        with self.assertRaises(ValueError):
            asyncio.run(z.unbind(SRC, None, DST, 6))


class CacheTests(unittest.TestCase):
    """A removed binding leaves the view at once, even when the read-back right after the write fails."""

    class _Zb:
        def __init__(self, resp):
            self.resp = resp

        async def unbind(self, *a):
            return None

        async def bind(self, *a):
            return None

        async def read_binds(self, ieee):
            if self.resp is None:
                raise TimeoutError('no answer')
            return self.resp

    class _Engine:
        devices = {SRC: {'ieee': SRC, 'name': 'Stairs', 'kind': 'ripple', 'model': 'TS0003-BSD-T'}}

    def _b(self, resp):
        from custom_components.ripple_presence.bindings import Bindings
        b = Bindings(self._Engine(), self._Zb(resp))
        b.cache[SRC] = {'at': 1, 'binds': parse_binds(RESP), 'error': None}
        return b

    def test_remove_drops_binding_when_read_back(self):
        b = self._b(None)
        asyncio.run(b.remove(SRC, 1, DST))
        self.assertFalse(any(x['dst_ieee'] == DST for x in b.cache[SRC]['binds']))
        self.assertTrue(b.cache[SRC]['error'])

    def test_empty_read_back_error_not_empty(self):
        b = self._b({'replies': []})
        asyncio.run(b.read(SRC))
        self.assertTrue(b.cache[SRC]['error'])
        self.assertEqual(len(b.cache[SRC]['binds']), 2)

    def test_add_shows_binding_when_read_back(self):
        b = self._b(None)
        asyncio.run(b.add(SRC, 3, DST, 5))
        self.assertTrue(any(x['src_ep'] == 3 and x['dst_ep'] == 5 for x in b.cache[SRC]['binds']))


class PersistTests(unittest.TestCase):
    """The binding tables live in the store, so they survive a restart and need no new read."""

    def test_cache_survives_a_store_reload(self):
        import tempfile
        from custom_components.ripple_presence.bindings import Bindings
        from custom_components.ripple_presence.store import Store
        d = tempfile.mkdtemp()
        zb_ = CacheTests._Zb(RESP)
        asyncio.run(Bindings(CacheTests._Engine(), zb_, Store(d)).read(SRC))
        calls = []

        class Never(CacheTests._Zb):
            async def read_binds(self, ieee):
                calls.append(ieee)
                raise AssertionError('no read expected')
        b2 = Bindings(CacheTests._Engine(), Never(None), Store(d))
        view = b2.view()
        self.assertEqual([r['dst_ieee'] for r in view[SRC]['controls']], [DST])
        self.assertTrue(view[SRC]['at'])
        self.assertEqual(calls, [])

    def test_store_no_bindings_key_loads(self):
        import json, os, tempfile
        from custom_components.ripple_presence.bindings import Bindings
        from custom_components.ripple_presence.store import Store
        d = tempfile.mkdtemp()
        with open(os.path.join(d, 'ripple.json'), 'w') as f:
            json.dump({'version': 4, 'switches': {}, 'rooms': [], 'room_meta': {}, 'probe': {}}, f)
        self.assertEqual(Bindings(CacheTests._Engine(), CacheTests._Zb(RESP), Store(d)).view(), {})


class OurFirmwareTests(unittest.TestCase):
    """Only our firmware (v4 production or v5) holds bindings; other devices are targets and never read."""

    def test_identity_rule(self):
        from custom_components.ripple_presence.engine import is_our_firmware
        self.assertTrue(is_our_firmware({'kind': 'ripple', 'model': 'TS0002-IND-T'}))
        self.assertTrue(is_our_firmware({'kind': 'needs_firmware', 'model': 'TS0003-BSD-T', 'fw': 0x1103300A, 'manuf_id': 0x1141}))
        self.assertTrue(is_our_firmware({'kind': 'other', 'model': 'x', 'sw_build_id': 'ripple.v5'}))
        self.assertFalse(is_our_firmware({'kind': 'other', 'model': 'TS0004', 'manuf_id': 0x1002}))
        self.assertFalse(is_our_firmware({'kind': 'other', 'model': 'TRADFRI bulb', 'manuf_id': 0x117C}))
        self.assertFalse(is_our_firmware({'kind': 'other', 'model': 'TS0002-ABC-T', 'manuf_id': 0x1002}))

    def test_backend_refuses_source_without_our_firmware(self):
        from custom_components.ripple_presence.bindings import Bindings
        from custom_components.ripple_presence.zigbee import NotRipple
        calls = []

        class Zb(CacheTests._Zb):
            async def read_binds(self, ieee):
                calls.append(ieee)
                return RESP

            async def bind(self, *a):
                calls.append(a)

        class Eng:
            devices = {SRC: {'ieee': SRC, 'name': 'Bulb', 'kind': 'other', 'model': 'TRADFRI bulb', 'manuf_id': 0x117C},
                       DST: {'ieee': DST, 'name': 'Hall', 'kind': 'needs_firmware', 'model': 'TS0001-XYZ-T', 'manuf_id': 0x1141}}
        b = Bindings(Eng(), Zb(RESP))
        for coro in (b.read(SRC), b.add(SRC, 1, DST, 2), b.remove(SRC, 1, DST)):
            with self.assertRaises(NotRipple):
                asyncio.run(coro)
        self.assertEqual(calls, [])
        asyncio.run(b.read(DST))
        self.assertEqual(calls, [DST])

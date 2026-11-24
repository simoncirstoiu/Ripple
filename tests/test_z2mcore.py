import asyncio
import json
import os
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from custom_components.ripple_presence import v5  # noqa: E402
from custom_components.ripple_presence.z2mcore import Z2MCore, from_z2m, to_z2m  # noqa: E402

IEEE = 'a4:c1:38:9e:f5:5b:ea:e9'
DEVICES = [
    {'ieee_address': '0x00124b0000000001', 'type': 'Coordinator', 'friendly_name': 'Coordinator', 'endpoints': {}},
    {'ieee_address': to_z2m(IEEE), 'type': 'Router', 'friendly_name': 'Hol', 'network_address': 12171,
     'manufacturer': 'unknown', 'model_id': 'TS0002-IND-T', 'software_build_id': 'Ripple-5.0.5',
     'definition': {'vendor': 'Ripple', 'model': 'TS0002-IND-T'},
     'endpoints': {'1': {'name': 'switch_left', 'clusters': {'input': ['genBasic', 'genOnOff', 'rippleSense'], 'output': []}},
                   '3': {'name': 'relay_left', 'clusters': {'input': ['genOnOff'], 'output': []}}}},
]


def msg(topic, payload, retain=False):
    return SimpleNamespace(topic=topic, payload=json.dumps(payload), retain=retain)


class FakeZ2M:
    """Answers the converter's requests the way the Ripple converter does."""

    def __init__(self, core):
        self.core, self.sent, self.attrs, self.fail = core, [], {}, None
        self.saved = None

    async def publish(self, topic, payload):
        self.sent.append((topic, payload))
        loop = asyncio.get_running_loop()
        if topic.endswith('/set'):
            req = payload['ripple']
            rep = {'id': req['id'], 'ok': True}
            if self.fail is not None:
                rep = {'id': req['id'], 'ok': False, **self.fail}
            elif req['op'] == 'read':
                rep['attrs'] = {str(a): self.attrs[a] for a in req['attrs'] if a in self.attrs}
            elif req['op'] == 'binds':
                rep['entries'] = [{'src_ep': 1, 'cluster': 6, 'mode': 3, 'dst': '0xa4c138b5f0000001', 'group': None, 'dst_ep': 4},
                                  {'src_ep': 2, 'cluster': 6, 'mode': 1, 'dst': None, 'group': 5, 'dst_ep': None}]
            loop.call_soon(self.core._on_message, msg('zigbee2mqtt/Hol', {'state_left': 'ON', 'ripple_reply': rep}))
        elif topic.endswith('/bridge/request/converter/save'):
            self.saved = payload
            loop.call_soon(self.core._on_message, msg('zigbee2mqtt/bridge/response/converter/save',
                                                      {'status': 'ok', 'data': {}, 'transaction': payload['transaction']}))


def run(coro_fn):
    async def go():
        hass = SimpleNamespace(loop=asyncio.get_running_loop(), async_create_task=asyncio.ensure_future)
        core = Z2MCore(hass)
        fake = FakeZ2M(core)
        core._publish = fake.publish
        core._on_message(msg('zigbee2mqtt/bridge/devices', DEVICES, retain=True))
        return await coro_fn(core, fake)
    return asyncio.run(go())


class AddressTests(unittest.TestCase):
    def test_round_trip(self):
        self.assertEqual(to_z2m(IEEE), '0xa4c1389ef55beae9')
        self.assertEqual(from_z2m('0xa4c1389ef55beae9'), IEEE)
        self.assertEqual(from_z2m('0x1'), '00:00:00:00:00:00:00:01')


class RequestTests(unittest.TestCase):
    def test_read_bytes_and_missing(self):
        async def go(core, fake):
            fake.attrs = {v5.A_ZONE_STATE: 1, 0xff30: {'hex': '0102'}}
            return await core.zcl_read(IEEE, v5.CLUSTER, [v5.A_ZONE_STATE, 0xff30, 0xff99], v5.MANUF)
        ok, fail = run(go)
        self.assertEqual(ok, {v5.A_ZONE_STATE: 1, 0xff30: b'\x01\x02'})
        self.assertEqual(fail, {0xff99: 0x86})

    def test_request_carries_manufacturer_and_endpoint(self):
        async def go(core, fake):
            await core.zcl_write(IEEE, v5.CLUSTER, v5.A_HOST_API, 6, v5.MANUF)
            return fake.sent[-1]
        topic, payload = run(go)
        self.assertEqual(topic, 'zigbee2mqtt/Hol/set')
        req = payload['ripple']
        self.assertEqual((req['op'], req['ep'], req['cluster'], req['manuf'], req['attrs']),
                         ('write', 1, v5.CLUSTER, v5.MANUF, {str(v5.A_HOST_API): 6}))

    def test_refused_write_returns_status(self):
        async def go(core, fake):
            fake.fail = {'status': 0x7e, 'error': 'Status NOT_AUTHORIZED'}
            return await core.zcl_write(IEEE, v5.CLUSTER, v5.A_TUNE, b'\x00', v5.MANUF)
        self.assertEqual(run(go), 0x7e)

    def test_command_payload_as_hex(self):
        async def go(core, fake):
            st = await core.zcl_command(IEEE, v5.CLUSTER, v5.CMD_SOURCES, b'\x01\x02', v5.MANUF)
            return st, fake.sent[-1][1]['ripple']
        st, req = run(go)
        self.assertEqual(st, 0)
        self.assertEqual(req['payload'], {'hex': '0102'})

    def test_network_failure_raises(self):
        async def go(core, fake):
            fake.fail = {'status': None, 'error': 'Delivery failed'}
            return await core.zcl_read(IEEE, v5.CLUSTER, [v5.A_ZONE_STATE], v5.MANUF)
        with self.assertRaises(Exception) as cm:
            run(go)
        self.assertIn('Delivery failed', str(cm.exception))

    def test_binds_shape(self):
        async def go(core, fake):
            return await core.zdo_binds(IEEE)
        st, total, _, entries = run(go)['replies'][0]
        self.assertEqual((st, total), (0, 2))
        self.assertEqual(entries[0]['DstAddress'], {'addrmode': 3, 'ieee': 'a4:c1:38:b5:f0:00:00:01', 'endpoint': 4})
        self.assertEqual(entries[1]['DstAddress'], {'addrmode': 1, 'nwk': 5})

    def test_unknown_device(self):
        async def go(core, fake):
            return await core.zcl_read('00:00:00:00:00:00:00:99', v5.CLUSTER, [1], v5.MANUF)
        with self.assertRaises(Exception):
            run(go)


class ReportTests(unittest.TestCase):
    def test_reports_once_per_sequence(self):
        async def go(core, fake):
            got = []
            core.subscribe(IEEE, lambda i, c, a, v: got.append((i, c, a, v)))
            rep = {'b': 7, 'n': 1, 'ep': 1, 'cluster': v5.CLUSTER, 'attrs': {str(v5.A_ZONE_STATE): 3, '65328': {'hex': 'ff'}}}
            core._on_message(msg('zigbee2mqtt/Hol', {'ripple': rep}))
            core._on_message(msg('zigbee2mqtt/Hol', {'ripple': rep, 'linkquality': 90}))
            core._on_message(msg('zigbee2mqtt/Hol', {'ripple': {**rep, 'n': 2, 'attrs': {'0': 1}, 'cluster': 0x0406}}))
            return got
        self.assertEqual(run(go), [(IEEE, v5.CLUSTER, v5.A_ZONE_STATE, 3), (IEEE, v5.CLUSTER, 0xff30, b'\xff'), (IEEE, 0x0406, 0, 1)])

    def test_retained_first_report_ignored(self):
        async def go(core, fake):
            got = []
            core.subscribe(IEEE, lambda i, c, a, v: got.append(a))
            rep = {'b': 7, 'n': 9, 'ep': 1, 'cluster': v5.CLUSTER, 'attrs': {'1': 1}}
            core._on_message(msg('zigbee2mqtt/Hol', {'ripple': rep}, retain=True))
            return got
        self.assertEqual(run(go), [])

    def test_other_endpoint_ignored(self):
        async def go(core, fake):
            got = []
            core.subscribe(IEEE, lambda i, c, a, v: got.append(a))
            core._on_message(msg('zigbee2mqtt/Hol', {'ripple': {'b': 1, 'n': 1, 'ep': 3, 'cluster': 6, 'attrs': {'0': 1}}}))
            return got
        self.assertEqual(run(go), [])


class ConverterTests(unittest.TestCase):
    def test_saved_when_missing_or_changed(self):
        async def go(core, fake):
            first = await core.ensure_converter('ripple.js', 'code-1')
            core._on_message(msg('zigbee2mqtt/bridge/converters', [{'name': 'ripple.js', 'code': 'code-1'}], retain=True))
            second = await core.ensure_converter('ripple.js', 'code-1')
            third = await core.ensure_converter('ripple.js', 'code-2')
            return first, second, third, fake.saved
        first, second, third, saved = run(go)
        self.assertEqual((first, second, third), (True, False, True))
        self.assertEqual((saved['name'], saved['code']), ('ripple.js', 'code-2'))

    def test_error_kept(self):
        async def go(core, fake):
            async def refuse(topic, payload):
                asyncio.get_running_loop().call_soon(core._on_message, msg(
                    'zigbee2mqtt/bridge/response/converter/save',
                    {'status': 'error', 'error': 'external JS is disabled', 'transaction': payload['transaction']}))
            core._publish = refuse
            await core.ensure_converter('ripple.js', 'x')
            return core.converter_error
        self.assertIn('external JS is disabled', run(go))


if __name__ == '__main__':
    unittest.main()

import asyncio
import json
import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from custom_components.ripple_presence import flasher as fl  # noqa: E402
from custom_components.ripple_presence.flasher import FlashError, Z2MFlasher  # noqa: E402
from custom_components.ripple_presence.z2mcore import FLASH_KEY, Z2MCore, _short, safe_info, to_z2m  # noqa: E402

IEEE = 'a4:c1:38:9e:f5:5b:ea:e9'
DEVICES = [{'ieee_address': to_z2m(IEEE), 'type': 'Router', 'friendly_name': 'Hol', 'model_id': 'TS0002',
            'endpoints': {'1': {'clusters': {'input': ['genBasic', 'genOnOff'], 'output': ['genOta']}}}}]


def msg(topic, payload, retain=False):
    return SimpleNamespace(topic=topic, payload=json.dumps(payload), retain=retain)


class FakeBroker:
    """Answers the generic converters and the bridge requests the way Zigbee2MQTT does."""

    def __init__(self, core):
        self.core, self.sent = core, []
        self.values = {'genOta': {'manufacturerId': 4417, 'imageTypeId': 54179}, 'genBasic': {'modelId': 'TS0002'}}
        self.silent = False
        self.ota_error = None

    def later(self, topic, payload):
        asyncio.get_running_loop().call_soon(self.core._on_message, msg(topic, payload))

    async def publish(self, topic, payload):
        self.sent.append((topic, payload))
        if topic == 'zigbee2mqtt/Hol/set' and 'read' in payload and not self.silent:
            r = payload['read']
            vals = self.values.get(r['cluster'], {})
            self.later('zigbee2mqtt/Hol', {'state_left': 'ON', r['state_property']: {a: vals[a] for a in r['attributes'] if a in vals}})
        elif topic.startswith('zigbee2mqtt/bridge/request/'):
            path = topic[len('zigbee2mqtt/bridge/request/'):]
            tid = payload['transaction']
            if path == 'device/ota_update/update':
                for p in (10.0, 55.5):
                    self.later('zigbee2mqtt/Hol', {'update': {'state': 'updating', 'progress': p, 'remaining': 30}})
                if self.ota_error:
                    rep = {'status': 'error', 'error': self.ota_error, 'data': {}, 'transaction': tid}
                else:
                    rep = {'status': 'ok', 'data': {'id': payload['id']}, 'transaction': tid}
            else:
                rep = {'status': 'ok', 'data': {}, 'transaction': tid}
            self.later(f'zigbee2mqtt/bridge/response/{path}', rep)


def run(coro_fn):
    async def go():
        hass = SimpleNamespace(loop=asyncio.get_running_loop(), async_create_task=asyncio.ensure_future)
        core = Z2MCore(hass)
        broker = FakeBroker(core)
        core._publish = broker.publish
        core._on_message(msg('zigbee2mqtt/bridge/devices', DEVICES, retain=True))
        return await coro_fn(core, broker)
    return asyncio.run(go())


class CoreFlashTests(unittest.TestCase):
    def test_plain_read_comes_back_in_the_state(self):
        async def go(core, broker):
            got = await core.plain_read(IEEE, 'genOta', ['manufacturerId', 'imageTypeId'], options={'direction': 1})
            self.assertEqual(got, {'manufacturerId': 4417, 'imageTypeId': 54179})
            topic, payload = broker.sent[-1]
            self.assertEqual(topic, 'zigbee2mqtt/Hol/set')
            self.assertEqual(payload['read']['options'], {'direction': 1})
            self.assertEqual(payload['read']['state_property'], FLASH_KEY)
            self.assertNotIn(FLASH_KEY, core._states[IEEE])
            self.assertEqual(core._states[IEEE]['state_left'], 'ON')
        run(go)

    def test_plain_read_times_out_without_answer(self):
        async def go(core, broker):
            broker.silent = True
            with self.assertRaises(asyncio.TimeoutError):
                await core.plain_read(IEEE, 'genBasic', ['modelId'], timeout=0.05)
            self.assertEqual(core._state_waits.get(IEEE), [])
        run(go)

    def test_plain_write_payload(self):
        async def go(core, broker):
            await core.plain_write(IEEE, 'genBasic', 0xff00, 'x;TS0002-IND-T;', 0x44)
            self.assertEqual(broker.sent[-1], ('zigbee2mqtt/Hol/set', {'write': {
                'cluster': 'genBasic', 'payload': {'65280': {'value': 'x;TS0002-IND-T;', 'type': 0x44}}}}))
        run(go)

    def test_ota_install_sends_hex_and_reports_progress(self):
        async def go(core, broker):
            seen = []
            await core.ota_install(IEEE, b'\x1e\xf1\xee\x0b', progress=seen.append)
            topic, payload = broker.sent[-1]
            self.assertEqual(topic, 'zigbee2mqtt/bridge/request/device/ota_update/update')
            self.assertEqual(payload['id'], '0xa4c1389ef55beae9')
            self.assertEqual(payload['hex']['data'], '1ef1ee0b')
            await asyncio.sleep(0)
            self.assertEqual(seen, [10.0, 55.5])
            self.assertEqual(core._ota_progress, {})
        run(go)

    def test_ota_error_raises(self):
        async def go(core, broker):
            broker.ota_error = 'Device did not respond to OTA request'
            with self.assertRaises(Exception) as cm:
                await core.ota_install(IEEE, b'\x00')
            self.assertIn('did not respond', str(cm.exception))
        run(go)

    def test_permit_join_is_capped(self):
        async def go(core, broker):
            await core.permit_join(600)
            self.assertEqual(broker.sent[-1][0], 'zigbee2mqtt/bridge/request/permit_join')
            self.assertEqual(broker.sent[-1][1]['time'], 254)
        run(go)

    def test_reinterview_and_shown_model(self):
        async def go(core, broker):
            await core.reinterview(IEEE)
            self.assertEqual(broker.sent[-1][0], 'zigbee2mqtt/bridge/request/device/interview')
            self.assertEqual(broker.sent[-1][1]['id'], '0xa4c1389ef55beae9')
            self.assertEqual(core.shown_model(IEEE), 'TS0002')
        run(go)


class SafetyTests(unittest.TestCase):
    def test_bridge_info_drops_the_network_key(self):
        info = {'version': '2.6.0', 'network': {'channel': 25, 'pan_id': 1, 'extended_pan_id': 'x'},
                'config': {'advanced': {'network_key': [1, 2, 3], 'enable_external_js': True},
                           'mqtt': {'password': 'secret'}}}
        got = safe_info(info)
        self.assertEqual(got['network'], {'channel': 25})
        self.assertEqual(got['config'], {'advanced': {'enable_external_js': True, 'log_level': None}})
        self.assertNotIn('secret', json.dumps(got))
        self.assertNotIn('network_key', json.dumps(got))

    def test_log_hides_the_image(self):
        got = _short({'id': '0x1', 'hex': {'data': 'ab' * 1000, 'file_name': 'f'}})
        self.assertEqual(got['hex']['data'], '<1000 bytes>')
        self.assertEqual(_short({'a': 1}), {'a': 1})


class FakeCore:
    def __init__(self):
        self.model = 'TS0002'
        self.shown = 'TS0002'
        self.ota = {'manufacturerId': 4417, 'imageTypeId': 54179}
        self.calls = []
        self.answering = True

    async def plain_read(self, ieee, cluster, attrs, options=None, timeout=20):
        self.calls.append(('read', cluster))
        if not self.answering:
            raise asyncio.TimeoutError()
        if cluster == 'genOta':
            return dict(self.ota)
        return {'modelId': self.model}

    async def plain_write(self, ieee, cluster, attr, value, data_type):
        self.calls.append(('write', cluster, attr, value, data_type))
        self.model = value.split(';')[1]

    async def permit_join(self, seconds):
        self.calls.append(('permit', seconds))

    async def ota_install(self, ieee, image, progress=None):
        self.calls.append(('ota', len(image)))
        progress(42.0)
        self.model = 'TS0012-CUSTOM'

    async def reinterview(self, ieee):
        self.calls.append(('interview',))
        self.shown = self.model

    def shown_model(self, ieee):
        return self.shown


class Files:
    def latest(self):
        return {'name': 'Ripple-v5.0.5.bin', 'version': '5.0.5'}

    def image(self, name, manufacturer_id, image_type):
        self.asked = (manufacturer_id, image_type)
        return b'\x00' * 64, False


def make(core):
    async def executor(fn, *a):
        return fn(*a)
    hass = SimpleNamespace(async_add_executor_job=executor,
                           async_create_background_task=lambda coro, name: asyncio.ensure_future(coro))
    zb = SimpleNamespace(allow_writes=True, protected=set())
    files = Files()
    return Z2MFlasher(hass, core, files, None, zb), files


BOARD = {'key': 'SWITCH_INDUAL_TOUCH_TS0002', 'how': 'stock', 'config_str': 'ptjcjise;TS0002-IND-T;LD4i;',
         'device_type': 'router', 'stock_manufacturer_id': 4417, 'stock_image_type': 54179}


@mock.patch.object(fl, 'POLL_S', 0)
class Z2MFlasherTests(unittest.IsolatedAsyncioTestCase):
    async def test_full_install_on_a_stock_device(self):
        core = FakeCore()
        f, files = make(core)
        await f._install(IEEE, BOARD)
        self.assertEqual(files.asked, (4417, 54179))
        kinds = [c[0] for c in core.calls]
        self.assertIn('ota', kinds)
        self.assertIn('permit', kinds)
        self.assertIn(('write', 'genBasic', 0xff00, BOARD['config_str'], 0x44), core.calls)
        self.assertEqual(kinds[-1], 'interview')
        self.assertEqual(f.jobs[IEEE]['state'], 'rebuilding')
        self.assertEqual(f.jobs[IEEE]['version'], '5.0.5')

    async def test_query_falls_back_to_the_stock_ids(self):
        core = FakeCore()
        core.ota = {}
        f, _ = make(core)
        f._board = BOARD
        q = await f._ask_query(IEEE)
        self.assertEqual((q.manufacturer_code, q.image_type), (4417, 54179))

    async def test_query_without_ids_fails(self):
        core = FakeCore()
        core.ota = {}
        f, _ = make(core)
        f._board = {**BOARD, 'how': 'flashed'}
        with self.assertRaises(FlashError):
            await f._ask_query(IEEE)

    async def test_query_ignores_wildcard_image_type(self):
        core = FakeCore()
        core.ota = {'manufacturerId': 4417, 'imageTypeId': 0xFFFF}
        f, _ = make(core)
        f._board = BOARD
        q = await f._ask_query(IEEE)
        self.assertEqual((q.manufacturer_code, q.image_type), (4417, 54179))

    async def test_query_wildcard_without_stock_ids_fails(self):
        core = FakeCore()
        core.ota = {'manufacturerId': 0xFFFF, 'imageTypeId': 54179}
        f, _ = make(core)
        f._board = {**BOARD, 'how': 'flashed'}
        with self.assertRaises(FlashError):
            await f._ask_query(IEEE)

    async def test_wildcard_device_installs_with_table_ids(self):
        core = FakeCore()
        core.ota = {'manufacturerId': 4417, 'imageTypeId': 0xFFFF}
        f, files = make(core)
        await f._install(IEEE, BOARD)
        self.assertEqual(files.asked, (4417, 54179))
        self.assertIn('ota', [c[0] for c in core.calls])

    async def test_query_prefers_the_device(self):
        core = FakeCore()
        core.ota = {'manufacturerId': 0x1141, 'imageTypeId': 47149}
        f, _ = make(core)
        f._board = BOARD
        q = await f._ask_query(IEEE)
        self.assertEqual(q.image_type, 47149)

    async def test_ota_error_becomes_flash_error(self):
        core = FakeCore()

        async def broken(ieee, image, progress=None):
            raise RuntimeError('Device did not respond to OTA request')
        core.ota_install = broken
        f, _ = make(core)
        with self.assertRaises(FlashError) as cm:
            await f._ota(IEEE, b'\x00')
        self.assertIn('did not respond', str(cm.exception))

    async def test_rebuild_hint_names_zigbee2mqtt(self):
        core = FakeCore()

        async def no_change(ieee):
            pass
        core.reinterview = no_change
        f, _ = make(core)
        f._reinterview = no_change
        with self.assertRaises(FlashError) as cm:
            await f._rebuild(IEEE, 'TS0002-IND-T')
        self.assertIn('Zigbee2MQTT', str(cm.exception))

    async def test_read_model_none_when_silent(self):
        core = FakeCore()
        core.answering = False
        f, _ = make(core)
        self.assertIsNone(await f._read_model(IEEE))


if __name__ == '__main__':
    unittest.main()

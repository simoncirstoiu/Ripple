"""Ripple on Zigbee2MQTT end to end: Home Assistant's MQTT integration, the Z2M backend and a simulated Zigbee2MQTT."""
import asyncio
import json
import os

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_mqtt_message

from custom_components.ripple_presence import v5
from custom_components.ripple_presence.const import DOMAIN
from custom_components.ripple_presence.z2mcore import to_z2m

from . import fake_core
from .conftest import FIXTURES

BASE = 'zigbee2mqtt'


def _out(v):
    return {'hex': bytes(v).hex()} if isinstance(v, (bytes, bytearray)) else v


def _in(v):
    return bytes.fromhex(v['hex']) if isinstance(v, dict) and 'hex' in v else v


class FakeZigbee2MQTT:
    """Plays Zigbee2MQTT and the Ripple converter on top of the simulated v5 switches."""

    def __init__(self, hass, fixture):
        self.hass = hass
        self.sim = fake_core.FixtureCore(fixture)
        self.names = {}
        self.devices = []
        self.saved = []
        self.sent = []
        self.seq = 0
        for d in fixture['zha_devices']:
            if d.get('device_type') == 'Coordinator':
                continue
            name = d.get('user_given_name') or d['name']
            self.names[name] = d['ieee']
            eps = {}
            for e in fixture['endpoints'].get(d['ieee'], []):
                cl = {'input': ['genBasic'] if e['ep'] == 1 else [], 'output': []}
                if e['onoff_in']:
                    cl['input'].append('genOnOff')
                if e['onoff_out']:
                    cl['output'].append('genOnOff')
                eps[str(e['ep'])] = {'name': None, 'clusters': cl}
            if d.get('sense'):
                eps.setdefault('1', {'name': None, 'clusters': {'input': ['genBasic'], 'output': []}})
                eps['1']['clusters']['input'].append('rippleSense')
            self.devices.append({
                'ieee_address': to_z2m(d['ieee']), 'type': d['device_type'], 'friendly_name': name,
                'network_address': d['nwk'], 'manufacturer': d['manufacturer'], 'model_id': d['model'],
                'software_build_id': d.get('sw_build_id'), 'endpoints': eps,
                'definition': {'vendor': 'Ripple', 'model': d['model']} if d.get('sense') else None,
                'fw': d.get('fw')})
        for ieee in self.sim.switches:
            self.sim.subscribe(ieee, self._report)

    def fire(self, topic, payload, retain=False):
        async_fire_mqtt_message(self.hass, topic, json.dumps(payload), retain=retain)

    def boot(self):
        self.fire(f'{BASE}/bridge/state', {'state': 'online'}, retain=True)
        self.fire(f'{BASE}/bridge/info', {'version': '2.6.0', 'config': {'advanced': {'network_key': [1, 2]}}}, retain=True)
        self.fire(f'{BASE}/bridge/converters', [], retain=True)
        self.fire(f'{BASE}/bridge/devices', [{k: v for k, v in d.items() if k != 'fw'} for d in self.devices], retain=True)
        for d in self.devices:
            if d['fw']:
                self.fire(f"{BASE}/{d['friendly_name']}", {'update': {'state': 'idle', 'installed_version': d['fw']}},
                          retain=True)

    def _name(self, ieee):
        return next(n for n, i in self.names.items() if i == ieee)

    def _report(self, ieee, cluster, attr, value):
        self.seq += 1
        self.fire(f'{BASE}/{self._name(ieee)}',
                  {'ripple': {'b': 1, 'n': self.seq, 'ep': 1, 'cluster': cluster, 'attrs': {str(attr): _out(value)}}})

    async def publish(self, topic, payload, *args):
        self.sent.append((topic, json.loads(payload)))
        self.hass.async_create_task(self._answer(topic, json.loads(payload)))

    async def _answer(self, topic, payload):
        if topic.startswith(f'{BASE}/bridge/request/'):
            path = topic[len(f'{BASE}/bridge/request/'):]
            if path == 'converter/save':
                self.saved.append(payload['name'])
            self.fire(f'{BASE}/bridge/response/{path}', {'status': 'ok', 'data': {}, 'transaction': payload['transaction']})
            return
        name = topic[len(BASE) + 1:-len('/set')] if topic.endswith('/set') else None
        req = payload.get('ripple') if name else None
        if not isinstance(req, dict):
            return
        ieee = self.names[name]
        rep = {'id': req['id'], 'ok': True}
        try:
            if req['op'] == 'read':
                ok, fail = await self.sim.zcl_read(ieee, req['cluster'], req['attrs'], req.get('manuf'))
                rep['attrs'] = {str(a): _out(v) for a, v in ok.items()}
            elif req['op'] == 'write':
                for a, v in req['attrs'].items():
                    st = await self.sim.zcl_write(ieee, req['cluster'], int(a), _in(v), req.get('manuf'))
                    if st:
                        rep = {'id': req['id'], 'ok': False, 'status': st, 'error': 'refused'}
            elif req['op'] == 'command':
                st = await self.sim.zcl_command(ieee, req['cluster'], req['cmd'], _in(req['payload']), req.get('manuf'))
                if st:
                    rep = {'id': req['id'], 'ok': False, 'status': st, 'error': 'refused'}
            elif req['op'] == 'binds':
                rep['entries'] = []
            else:
                rep['ok'] = True
        except Exception as e:  # noqa: BLE001
            rep = {'id': req['id'], 'ok': False, 'error': str(e)}
        self.fire(f'{BASE}/{name}', {'ripple_reply': rep})


@pytest.fixture
async def z2m(hass, mqtt_mock):
    with open(os.path.join(FIXTURES, 'synthetic.json')) as f:
        fake = FakeZigbee2MQTT(hass, json.load(f))
    mqtt_mock.async_publish.side_effect = fake.publish
    return fake


async def _setup(hass, z2m, allow_writes=False):
    entry = MockConfigEntry(domain=DOMAIN, title='Ripple', data={'stack': 'z2m', 'base_topic': BASE},
                            options={'allow_writes': allow_writes, 'protected_devices': [], 'poll_interval_s': 60,
                                     'resync_minutes': 60})
    entry.add_to_hass(hass)
    setup = hass.async_create_task(hass.config_entries.async_setup(entry.entry_id))
    await asyncio.sleep(0.05)
    z2m.boot()
    assert await setup
    rt = entry.runtime_data
    for _ in range(300):
        await asyncio.sleep(0.02)
        if not rt.engine.status.get('probing') and rt.engine.status.get('discovered_at') and rt.ready_switches():
            break
    await hass.async_block_till_done()
    return entry, rt


async def test_ripple_runs_on_zigbee2mqtt(hass, z2m):
    entry, rt = await _setup(hass, z2m)
    assert rt.stack == 'z2m'
    assert z2m.saved == ['ripple.js']
    sense = {d['ieee'] for d in z2m.sim.fx['zha_devices'] if d.get('sense')}
    assert {d['ieee'] for d in rt.engine.ripple_devices()} == sense
    assert rt.ready_switches()
    reads = [p['ripple'] for t, p in z2m.sent if t.endswith('/set') and 'ripple' in p]
    assert reads and all(r['manuf'] in (v5.MANUF, None) for r in reads)
    assert not [w for w in z2m.sim.writes if 'attr' in w], 'read-only by default'
    diag_stack = rt.core.bridge
    assert 'network_key' not in json.dumps(diag_stack)
    await hass.config_entries.async_unload(entry.entry_id)


async def test_reports_reach_the_engine(hass, z2m):
    entry, rt = await _setup(hass, z2m)
    ieee = next(iter(rt.ready_switches()))
    sw = z2m.sim.switches[ieee]
    sw.detect = 1
    z2m.sim.report(ieee, v5.CLUSTER, v5.A_ZONE_STATE, 1)
    await asyncio.sleep(0.1)
    await hass.async_block_till_done()
    assert rt.engine.devices[ieee]['live']['zone_state'] == 1
    await hass.config_entries.async_unload(entry.entry_id)


async def test_three_element_identifiers_dont_break_discovery(hass, z2m):
    """#88: another integration registers a 3-element identifier; Ripple still finds the switches."""
    from homeassistant.helpers import device_registry as dr
    other = MockConfigEntry(domain='other')
    other.add_to_hass(hass)
    dr.async_get(hass).async_get_or_create(config_entry_id=other.entry_id, identifiers={('other', 'bridge', 'x')}, name='Odd')
    entry, rt = await _setup(hass, z2m)
    sense = {d['ieee'] for d in z2m.sim.fx['zha_devices'] if d.get('sense')}
    assert {d['ieee'] for d in rt.engine.ripple_devices()} == sense
    assert not rt.engine.status.get('error')
    await hass.config_entries.async_unload(entry.entry_id)

import asyncio
import json
import os
from functools import partial
from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ripple_presence.const import DOMAIN
from custom_components.ripple_presence import zigbee as zb
from custom_components.ripple_presence import v5
from custom_components.ripple_presence.attrmap import V5_ADVANCED

from . import fake_core
from .conftest import FIXTURES

FAST = partial(zb.Zigbee, spacing_s=0)
_FX = {}


def _entry(hass, allow_writes=False):
    entry = MockConfigEntry(domain=DOMAIN, title='Ripple', data={},
                            options={'allow_writes': allow_writes, 'protected_devices': [], 'poll_interval_s': 60, 'resync_minutes': 60})
    entry.add_to_hass(hass)
    return entry


async def _setup(hass, fixture='synthetic.json', allow_writes=False, entry=None):
    _FX['path'] = os.path.join(FIXTURES, fixture)
    entry = entry or _entry(hass, allow_writes)
    with patch('custom_components.ripple_presence.runtime.Zigbee', FAST):
        assert await hass.config_entries.async_setup(entry.entry_id)
        rt = entry.runtime_data
        for _ in range(200):
            await asyncio.sleep(0.02)
            if not rt.engine.status.get('probing') and rt.engine.status.get('discovered_at') and rt.ready_switches():
                break
        await asyncio.sleep(0.7)
        await hass.async_block_till_done()
    return entry, rt


def _eid(hass, platform, unique_id):
    return er.async_get(hass).async_get_entity_id(platform, DOMAIN, unique_id)


def _fake_core(hass):
    with open(_FX['path']) as f:
        return fake_core.FixtureCore(json.load(f), simulate=True)


@pytest.fixture(autouse=True)
def _core():
    with patch('custom_components.ripple_presence.runtime.HassCore', _fake_core):
        yield
    _FX.clear()


async def test_config_flow_aborts_no_zigbee(hass):
    res = await hass.config_entries.flow.async_init(DOMAIN, context={'source': config_entries.SOURCE_USER})
    assert res['type'] == 'abort' and res['reason'] == 'no_zigbee'


async def test_config_flow_z2m_only(hass):
    MockConfigEntry(domain='mqtt', data={}).add_to_hass(hass)
    res = await hass.config_entries.flow.async_init(DOMAIN, context={'source': config_entries.SOURCE_USER})
    assert res['type'] == 'form' and res['step_id'] == 'z2m'
    res = await hass.config_entries.flow.async_configure(res['flow_id'], {'base_topic': ' z2m/ '})
    assert res['type'] == 'form' and res['step_id'] == 'settings'
    with patch('custom_components.ripple_presence.async_setup_entry', return_value=True):
        res = await hass.config_entries.flow.async_configure(res['flow_id'], {'allow_writes': False})
    assert res['type'] == 'create_entry'
    assert res['data'] == {'stack': 'z2m', 'base_topic': 'z2m'}


async def test_config_flow_both_stacks_asks(hass):
    MockConfigEntry(domain='zha', data={}).add_to_hass(hass)
    MockConfigEntry(domain='mqtt', data={}).add_to_hass(hass)
    res = await hass.config_entries.flow.async_init(DOMAIN, context={'source': config_entries.SOURCE_USER})
    assert res['type'] == 'form' and res['step_id'] == 'user'
    res = await hass.config_entries.flow.async_configure(res['flow_id'], {'stack': 'zha'})
    assert res['type'] == 'form' and res['step_id'] == 'settings'


async def test_config_flow_creates_read_only_entry(hass):
    MockConfigEntry(domain='zha', data={}).add_to_hass(hass)
    res = await hass.config_entries.flow.async_init(DOMAIN, context={'source': config_entries.SOURCE_USER})
    assert res['type'] == 'form'
    with patch('custom_components.ripple_presence.async_setup_entry', return_value=True):
        res = await hass.config_entries.flow.async_configure(res['flow_id'], {'allow_writes': False, 'protected_devices': []})
    assert res['type'] == 'create_entry'
    assert res['options']['allow_writes'] is False


async def test_entities_attach_switch_room_devices(hass):
    entry, rt = await _setup(hass)
    hall = next(d['ieee'] for d in rt.engine.devices.values() if d['name'] == 'Hallway switch')
    assert _eid(hass, 'number', f'ripple_presence_{hall}_off_s')
    assert not _eid(hass, 'number', f'ripple_presence_{hall}_hold_s')
    assert not _eid(hass, 'number', f'ripple_presence_{hall}_sensitivity')
    assert not _eid(hass, 'button', f'ripple_presence_{hall}_calibrate')
    assert _eid(hass, 'button', 'ripple_presence_room_area:hallway_calibrate')
    occ = _eid(hass, 'binary_sensor', 'ripple_presence_room_area:hallway_occupancy')
    assert occ and hass.states.get(occ).attributes['device_class'] == 'motion'
    from homeassistant.helpers import device_registry as dr
    room_dev = dr.async_get(hass).async_get(er.async_get(hass).async_get(occ).device_id)
    assert room_dev.name == 'Ripple - Hallway'
    assert hass.states.get(occ).attributes['friendly_name'] == 'Ripple - Hallway Motion'
    adv = _eid(hass, 'number', f'ripple_presence_{hall}_adv_quiet_q')
    assert er.async_get(hass).async_get(adv).disabled_by is not None
    assert not _eid(hass, 'number', f'ripple_presence_{hall}_adv_dcap_db')
    assert not _eid(hass, 'number', f'ripple_presence_{hall}_adv_h')


async def test_number_change_saved_when_read_only(hass):
    entry, rt = await _setup(hass)
    hall = next(d['ieee'] for d in rt.engine.devices.values() if d['name'] == 'Hallway switch')
    eid = _eid(hass, 'number', f'ripple_presence_{hall}_off_s')
    await hass.services.async_call('number', 'set_value', {'entity_id': eid, 'value': 45}, blocking=True)
    await asyncio.sleep(0.7)
    await hass.async_block_till_done()
    assert rt.core.writes == []
    assert hass.states.get(eid).state == '45'
    assert ir.async_get(hass).async_get_issue(DOMAIN, 'read_only_pending')


async def test_number_change_written_when_allowed(hass):
    entry, rt = await _setup(hass, allow_writes=True)
    hall = next(d['ieee'] for d in rt.engine.devices.values() if d['name'] == 'Hallway switch')
    eid = _eid(hass, 'number', f'ripple_presence_{hall}_off_s')
    await hass.services.async_call('number', 'set_value', {'entity_id': eid, 'value': 45}, blocking=True)
    from custom_components.ripple_presence import v5
    assert [(w['command'], v5.decode_tune(w['payload'])['off_s']) for w in rt.core.writes if 'command' in w] == [(v5.CMD_TUNE, 45)]
    assert [w['attr'] for w in rt.core.writes if 'attr' in w] == [v5.A_HOST_API]


async def test_cal_button_refused_when_read_only(hass):
    entry, rt = await _setup(hass)
    eid = _eid(hass, 'button', 'ripple_presence_room_area:hallway_calibrate')
    from homeassistant.exceptions import HomeAssistantError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call('button', 'press', {'entity_id': eid}, blocking=True)
    assert rt.core.writes == []


async def test_options_flow_links_change_switch(hass):
    entry, rt = await _setup(hass)
    e = rt.engine
    a = next(d['ieee'] for d in e.devices.values() if d['name'] == 'Kitchen switch')
    b = next(d['ieee'] for d in e.devices.values() if d['name'] == 'Kitchen worktop switch')
    tv = next(d['ieee'] for d in e.devices.values() if d['name'] == 'TV plug')
    before = list(e.store.switch(b)['sources'])
    res = await hass.config_entries.options.async_init(entry.entry_id)
    res = await hass.config_entries.options.async_configure(res['flow_id'], {'next_step_id': 'links'})
    res = await hass.config_entries.options.async_configure(res['flow_id'], {'switch': a})
    assert res['step_id'] == 'links_edit'
    res = await hass.config_entries.options.async_configure(res['flow_id'], {'sources': e.store.switch(a)['sources'] + [tv]})
    assert res['type'] == 'create_entry'
    assert tv in e.store.switch(a)['sources'] and e.store.switch(b)['sources'] == before


async def test_panel_and_websocket_state(hass, hass_ws_client):
    entry, rt = await _setup(hass)
    assert 'ripple' in hass.data['frontend_panels']
    client = await hass_ws_client(hass)
    await client.send_json({'id': 1, 'type': 'ripple_presence/state'})
    msg = await client.receive_json()
    assert msg['success'] and {r['name'] for r in msg['result']['rooms']} == {'Garage', 'Hallway', 'Kitchen', 'Living room'}


async def test_no_zigbee_devices(hass):
    entry, rt = await _setup(hass, fixture='empty.json')
    assert rt.engine.status['ripple_count'] == 0
    assert not [e for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)]


async def test_reload_keeps_entities_available(hass):
    entry, rt = await _setup(hass)
    with patch('custom_components.ripple_presence.runtime.Zigbee', FAST):
        await rt.store._ha.async_save(rt.store.data)
        assert await hass.config_entries.async_reload(entry.entry_id)
        rt = entry.runtime_data
        for _ in range(200):
            await asyncio.sleep(0.02)
            if rt.ready_switches() and all(rt.engine.devices[s]['config_at'] for s in rt.ready_switches()):
                break
        await asyncio.sleep(0.7)
        await hass.async_block_till_done()
    hall = next(d['ieee'] for d in rt.engine.devices.values() if d['name'] == 'Hallway switch')
    assert hass.states.get(_eid(hass, 'number', f'ripple_presence_{hall}_off_s')).state != 'unavailable'
    assert rt.engine.pending(hall) == []


async def test_zha_entry_wins_over_other_device(hass):
    from homeassistant.helpers import device_registry as dr
    from custom_components.ripple_presence.hacore import zha_registry_entries
    ieee = '00:11:22:33:44:55:66:77'
    other, zha = MockConfigEntry(domain='other'), MockConfigEntry(domain='zha')
    other.add_to_hass(hass)
    zha.add_to_hass(hass)
    reg = dr.async_get(hass)
    reg.async_get_or_create(config_entry_id=other.entry_id, identifiers={('other', 'x')}, connections={('zigbee', ieee)}, name='Other')
    reg.async_get_or_create(config_entry_id=zha.entry_id, identifiers={('zha', ieee)}, connections={('zigbee', ieee)}, name='Zha', sw_version='0x11033341')
    assert zha_registry_entries(hass)[ieee].sw_version == '0x11033341'


def _zha_device(hass, ieee, name):
    from homeassistant.helpers import device_registry as dr
    zha = MockConfigEntry(domain='zha')
    zha.add_to_hass(hass)
    return dr.async_get(hass).async_get_or_create(config_entry_id=zha.entry_id, identifiers={('zha', ieee)},
                                                 connections={('zigbee', ieee)}, name='model name').id, zha


async def test_switch_entities_join_the_zha_device(hass):
    from homeassistant.helpers import device_registry as dr
    ieee = '0c:43:14:ff:fe:10:20:03'
    st = MockConfigEntry(domain='smartthings')
    st.add_to_hass(hass)
    dr.async_get(hass).async_get_or_create(config_entry_id=st.entry_id, identifiers={('smartthings', 'x')},
                                           connections={('zigbee', ieee)}, name='Hallway (SmartThings)')
    dev_id, _ = _zha_device(hass, ieee, 'Hallway switch')
    entry, rt = await _setup(hass)
    eid = _eid(hass, 'number', f'ripple_presence_{ieee}_off_s')
    assert er.async_get(hass).async_get(eid).device_id == dev_id
    ours = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert not [d for d in ours if any(i[0] == 'zha' for i in d.identifiers)]


async def test_zha_entry_is_the_one_owned_by_zha(hass):
    from homeassistant.helpers import device_registry as dr
    from custom_components.ripple_presence.hacore import zha_registry_entries
    ieee = '00:11:22:33:44:55:66:88'
    dev_id, _ = _zha_device(hass, ieee, 'x')
    dr.async_get(hass).async_update_device(dev_id, name_by_user='Hall')
    stray = MockConfigEntry(domain=DOMAIN)
    stray.add_to_hass(hass)
    try:
        dr.async_get(hass).async_get_or_create(config_entry_id=stray.entry_id, identifiers={('zha', ieee)})
    except Exception:
        pass
    assert zha_registry_entries(hass)[ieee].name_by_user == 'Hall'


async def test_zha_devices_mark_our_firmware(hass, hass_ws_client):
    entry, rt = await _setup(hass)
    client = await hass_ws_client(hass)
    await client.send_json({'id': 1, 'type': 'ripple_presence/zha_devices'})
    ours = {d['name']: d['ours'] for d in (await client.receive_json())['result']}
    assert ours['Stairs switch'] and ours['Office switch']
    assert not ours['Tuya relay'] and not ours['TV plug'] and not ours['Front door sensor']
    plug = next(d['ieee'] for d in rt.engine.devices.values() if d['name'] == 'TV plug')
    await client.send_json({'id': 2, 'type': 'ripple_presence/bindings/read', 'ieee': plug})
    assert (await client.receive_json())['error']['code'] == 'invalid'


async def test_bindings_cache_survives_a_restart(hass, hass_ws_client, hass_storage):
    entry, rt = await _setup(hass)
    stairs = next(d['ieee'] for d in rt.engine.devices.values() if d['name'] == 'Stairs switch')
    await rt.bindings.read(stairs)
    await rt.store._ha.async_save(rt.store.data)
    assert hass_storage['ripple_presence']['data']['bindings'][stairs]['binds']
    with patch('custom_components.ripple_presence.runtime.Zigbee', FAST):
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
    rt = entry.runtime_data
    reads = []
    orig = rt.zb.read_binds

    async def spy(ieee):
        reads.append(ieee)
        return await orig(ieee)
    rt.zb.read_binds = spy
    client = await hass_ws_client(hass)
    await client.send_json({'id': 1, 'type': 'ripple_presence/bindings'})
    view = (await client.receive_json())['result']
    assert view[stairs]['at'] and view[stairs]['controls']
    assert reads == []


async def test_bindings_read_and_guarded_writes(hass, hass_ws_client):
    entry, rt = await _setup(hass)
    e = rt.engine
    stairs = next(d['ieee'] for d in e.devices.values() if d['name'] == 'Stairs switch')
    living = next(d['ieee'] for d in e.devices.values() if d['name'] == 'Living room switch')
    client = await hass_ws_client(hass)
    await client.send_json({'id': 1, 'type': 'ripple_presence/bindings/read', 'ieee': stairs})
    assert (await client.receive_json())['success']
    await client.send_json({'id': 2, 'type': 'ripple_presence/bindings'})
    view = (await client.receive_json())['result']
    assert [(b['src_ep'], b['dst_ieee'], b['dst_ep']) for b in view[stairs]['controls']] == [(2, living, 4)]
    assert view[living]['controlled_by'][0]['src_ieee'] == stairs
    await client.send_json({'id': 3, 'type': 'ripple_presence/bindings/add', 'src': stairs, 'src_ep': 3, 'dst': living, 'dst_ep': 5})
    res = await client.receive_json()
    assert not res['success'] and res['error']['code'] == 'writes_disabled'
    assert rt.core.writes == []


async def test_devices_and_fw_lists(hass, hass_ws_client):
    entry, rt = await _setup(hass)
    client = await hass_ws_client(hass)
    await client.send_json({'id': 1, 'type': 'ripple_presence/devices'})
    devs = (await client.receive_json())['result']
    assert {d['name'] for d in devs} == {'Kitchen switch', 'Kitchen worktop switch', 'Hallway switch', 'Stairs switch',
                                         'Living room switch', 'Garage switch'}
    await client.send_json({'id': 2, 'type': 'ripple_presence/firmware'})
    fw = (await client.receive_json())['result']
    assert any(f['latest'] != f['installed'] for f in fw)


async def test_v4_zone_device_removed_every_start(hass):
    """An old zone device that kept its entity is removed at every start."""
    from homeassistant.helpers import device_registry as dr
    entry = MockConfigEntry(domain=DOMAIN, title='Ripple', data={'stray_cleanup_done': True},
                            options={'allow_writes': False, 'protected_devices': [], 'poll_interval_s': 60, 'resync_minutes': 60})
    entry.add_to_hass(hass)
    reg, ents = dr.async_get(hass), er.async_get(hass)
    zone = reg.async_get_or_create(config_entry_id=entry.entry_id, identifiers={(DOMAIN, 'zone_0000000001')}, name='Office', model='Zone')
    old = ents.async_get_or_create('binary_sensor', DOMAIN, 'ripple_presence_zone_0000000001_occupancy', config_entry=entry, device_id=zone.id)
    empty = reg.async_get_or_create(config_entry_id=entry.entry_id, identifiers={(DOMAIN, 'room_gone')}, name='empty')
    entry, rt = await _setup(hass, entry=entry)
    assert reg.async_get(zone.id) is None
    assert ents.async_get(old.entity_id) is None
    assert reg.async_get(empty.id) is None
    assert not [d for d in dr.async_entries_for_config_entry(reg, entry.entry_id)
                if not er.async_entries_for_device(ents, d.id, include_disabled_entities=True)]


async def test_cleanup_keeps_zha_and_shared_devices(hass):
    from homeassistant.helpers import device_registry as dr
    ieee = '0c:43:14:ff:fe:10:20:04'
    zha_id, zha = _zha_device(hass, ieee, 'Other switch')
    other = MockConfigEntry(domain='other')
    other.add_to_hass(hass)
    entry = _entry(hass)
    reg = dr.async_get(hass)
    reg.async_update_device(zha_id, add_config_entry_id=entry.entry_id)
    mixed = reg.async_get_or_create(config_entry_id=entry.entry_id, identifiers={(DOMAIN, 'zone_mixed'), ('other', 'x')}, name='mixed')
    shared = reg.async_get_or_create(config_entry_id=entry.entry_id, identifiers={(DOMAIN, 'zone_shared')}, name='shared')
    reg.async_update_device(shared.id, add_config_entry_id=other.entry_id)
    entry, rt = await _setup(hass, entry=entry)
    for dev_id in (zha_id, mixed.id, shared.id):
        assert reg.async_get(dev_id) is not None
    from custom_components.ripple_presence import async_remove_config_entry_device as remove
    for dev_id in (zha_id, mixed.id, shared.id):
        assert await remove(hass, entry, reg.async_get(dev_id)) is False


async def test_ui_delete_refuses_live_room_switch(hass, hass_ws_client):
    from homeassistant.helpers import device_registry as dr
    from homeassistant.setup import async_setup_component
    from custom_components.ripple_presence import async_remove_config_entry_device as remove
    entry, rt = await _setup(hass)
    reg = dr.async_get(hass)
    hall = next(d['ieee'] for d in rt.engine.devices.values() if d['name'] == 'Hallway switch')
    room = reg.async_get_device(identifiers={(DOMAIN, 'room_area:hallway')})
    switch = reg.async_get_device(identifiers={(DOMAIN, hall)})
    assert room is not None and switch is not None
    assert await remove(hass, entry, room) is False
    assert await remove(hass, entry, switch) is False
    left = reg.async_get_or_create(config_entry_id=entry.entry_id, identifiers={(DOMAIN, 'zone_left')}, name='left')
    assert await remove(hass, entry, left) is True
    assert await async_setup_component(hass, 'config', {})
    client = await hass_ws_client(hass)
    await client.send_json({'id': 1, 'type': 'config/device_registry/remove_config_entry', 'device_id': room.id,
                            'config_entry_id': entry.entry_id})
    assert not (await client.receive_json())['success']
    await client.send_json({'id': 2, 'type': 'config/device_registry/remove_config_entry', 'device_id': left.id,
                            'config_entry_id': entry.entry_id})
    assert (await client.receive_json())['success']
    assert reg.async_get(left.id) is None and reg.async_get(room.id) is not None


async def test_startup_never_detaches_from_real_zha(hass):
    """A ZHA device still carrying Ripple's entry keeps it; only orphan Ripple-only devices go."""
    from homeassistant.helpers import device_registry as dr
    ieee = '0c:43:14:ff:fe:10:20:03'
    dev_id, zha = _zha_device(hass, ieee, 'Hallway switch')
    entry = _entry(hass)
    reg = dr.async_get(hass)
    reg.async_update_device(dev_id, add_config_entry_id=entry.entry_id)
    stray = reg.async_get_or_create(config_entry_id=entry.entry_id, identifiers={(DOMAIN, 'legacy')}, name='stray')
    kept = reg.async_get_or_create(config_entry_id=entry.entry_id, identifiers={(DOMAIN, 'room_area:hallway')}, name='room')
    er.async_get(hass).async_get_or_create('binary_sensor', DOMAIN, 'ripple_presence_room_area:hallway_occupancy',
                                           config_entry=entry, device_id=kept.id)
    entry, rt = await _setup(hass, entry=entry)
    dev = reg.async_get(dev_id)
    assert dev is not None and {zha.entry_id, entry.entry_id} <= set(dev.config_entries)
    assert reg.async_get(stray.id) is None
    assert reg.async_get(kept.id) is not None
    eid = _eid(hass, 'number', f'ripple_presence_{ieee}_off_s')
    assert er.async_get(hass).async_get(eid).device_id == dev_id
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    dev = reg.async_get(dev_id)
    assert dev is not None and entry.entry_id in dev.config_entries
    assert er.async_get(hass).async_get(eid).device_id == dev_id


async def test_zha_occupancy_ripple_switch_goes(hass):
    """On v5 switches Ripple motion replaces ZHA's Occupancy; a live one or another device's stays."""
    ents = er.async_get(hass)
    dev_id, zha = _zha_device(hass, '0c:43:14:ff:fe:10:20:03', 'Hallway switch')
    orphan = ents.async_get_or_create('binary_sensor', 'zha', '0c:43:14:ff:fe:10:20:03-1-1030',
                                      config_entry=zha, device_id=dev_id).entity_id
    live = ents.async_get_or_create('binary_sensor', 'zha', '0c:43:14:ff:fe:10:20:04-1-1030',
                                    config_entry=zha).entity_id
    other = ents.async_get_or_create('binary_sensor', 'zha', '00:11:22:33:44:55:66:88-1-1030',
                                     config_entry=zha).entity_id
    hass.states.async_set(live, 'off')
    entry, rt = await _setup(hass)
    stairs = next(d['ieee'] for d in rt.engine.ripple_devices() if d['ieee'].endswith(':04'))
    assert stairs == '0c:43:14:ff:fe:10:20:04'
    assert ents.async_get(orphan) is None
    assert ents.async_get(live) is not None
    assert ents.async_get(other) is not None


async def test_first_reads_wait_for_zha_then_settle(hass):
    from custom_components.ripple_presence import hacore
    core = hacore.HassCore(hass)
    assert core.zha_ready() is False
    ready, sleeps = {'v': False}, []

    async def fake_sleep(s):
        sleeps.append(s)
        if len(sleeps) == 2:
            ready['v'] = True
    with patch.object(hacore.HassCore, 'zha_ready', lambda self: ready['v']), patch.object(hacore.asyncio, 'sleep', fake_sleep):
        await core.wait_ready(60)
        assert sleeps == [5, 5, 60]
        sleeps.clear()
        await core.wait_ready(60)
        assert sleeps == []


async def test_runtime_holds_reads_until_core_ready(hass):
    fx = fake_core
    gate = asyncio.Event()

    class GatedCore(fx.FixtureCore):
        async def wait_ready(self, delay_s):
            await gate.wait()
    _FX['path'] = os.path.join(FIXTURES, 'synthetic.json')
    entry = _entry(hass)
    with patch.object(fx, 'FixtureCore', GatedCore), patch('custom_components.ripple_presence.runtime.Zigbee', FAST):
        assert await hass.config_entries.async_setup(entry.entry_id)
        rt = entry.runtime_data
        await asyncio.sleep(0.3)
        assert rt.engine.status.get('discovered_at')
        assert rt.zb.stats['reads'] == 0 and not rt.ready_switches()
        gate.set()
        for _ in range(200):
            await asyncio.sleep(0.02)
            if rt.ready_switches() and not rt.engine.status.get('probing'):
                break
        await hass.async_block_till_done()
    assert rt.zb.stats['reads'] > 0 and rt.ready_switches()


async def test_v4_entities_non_v5_switch_entities(hass):
    entry = _entry(hass)
    reg = er.async_get(hass)
    hall, office = '0c:43:14:ff:fe:10:20:03', '0c:43:14:ff:fe:10:20:06'
    old = [reg.async_get_or_create('number', DOMAIN, f'ripple_presence_{hall}_sensitivity', config_entry=entry),
           reg.async_get_or_create('sensor', DOMAIN, f'ripple_presence_{hall}_need', config_entry=entry),
           reg.async_get_or_create('number', DOMAIN, f'ripple_presence_{hall}_adv_thr_min', config_entry=entry),
           reg.async_get_or_create('number', DOMAIN, 'ripple_presence_room_area:hallway_sensitivity', config_entry=entry),
           reg.async_get_or_create('button', DOMAIN, f'ripple_presence_{office}_calibrate', config_entry=entry),
           reg.async_get_or_create('button', DOMAIN, f'ripple_presence_{hall}_calibrate', config_entry=entry)]
    keep = [reg.async_get_or_create('switch', DOMAIN, f'ripple_presence_{hall}_detect', config_entry=entry),
            reg.async_get_or_create('binary_sensor', DOMAIN, 'ripple_presence_room_area:hallway_occupancy', config_entry=entry),
            reg.async_get_or_create('button', DOMAIN, 'ripple_presence_room_area:hallway_calibrate', config_entry=entry)]
    entry, rt = await _setup(hass, entry=entry)
    assert [reg.async_get(e.entity_id) for e in old] == [None] * len(old)
    assert all(reg.async_get(e.entity_id) for e in keep)


async def test_v4_storage_is_migrated(hass, hass_storage):
    hall, smoke = '0c:43:14:ff:fe:10:20:03', '0c:43:14:ff:fe:10:20:0d'
    hass_storage['ripple_presence'] = {'version': 1, 'minor_version': 1, 'key': 'ripple_presence', 'data': {
        'version': 1, 'switches': {hall: {'settings': {'sensitivity': 3, 'hold_s': 30}, 'sources': [smoke]}},
        'rooms': [{'id': 'r1234abcd', 'name': 'Open space', 'members': [hall]}], 'room_meta': {}, 'probe': {},
        'hidden_areas': ['area:kitchen']}}
    entry, rt = await _setup(hass)
    sw = rt.store.switch(hall)
    assert sw['sources'] == [smoke] and sw['sens'] == {smoke: v5.SENS_DEFAULT_BY_API[3]} and 'migrated' not in sw
    assert 'hold_s' not in sw['settings'] and 'sensitivity' not in sw['settings']
    names = {r['name'] for r in rt.engine.rooms()}
    assert 'Open space' in names and 'Kitchen' not in names


async def test_pr3_storage_is_discarded(hass, hass_storage):
    hass_storage['ripple_presence'] = {'version': 2, 'minor_version': 1, 'key': 'ripple_presence',
                                       'data': {'zones': {'z1': {}}, 'lines': {}, 'bits': {}, 'applied': {}}}
    entry, rt = await _setup(hass)
    assert 'zones' not in rt.store.data and rt.store.data['version'] == 5


async def test_1_0_x_storage_keeps_lines_with_s(hass, hass_storage):
    hall, smoke, door = '0c:43:14:ff:fe:10:20:03', '0c:43:14:ff:fe:10:20:0d', '0c:43:14:ff:fe:10:20:0c'
    hass_storage['ripple_presence'] = {'version': 3, 'minor_version': 1, 'key': 'ripple_presence', 'data': {
        'version': 3, 'switches': {hall: {'settings': {'hold_s': 7}, 'sources': [smoke, door],
                                          'sens': {smoke: 9, door: 4}, 'parked': [door]}},
        'rooms': [], 'room_meta': {}, 'probe': {}}}
    entry, rt = await _setup(hass)
    sw = rt.store.switch(hall)
    assert sw['sens'] == {smoke: v5.STEP_S[9], door: v5.STEP_S[4]} and sw['parked'] == [door] and 'hold_s' not in sw['settings']


async def test_websocket_sets_sens_of_one_line(hass, hass_ws_client):
    entry, rt = await _setup(hass)
    e = rt.engine
    hall = next(d['ieee'] for d in e.devices.values() if d['name'] == 'Hallway switch')
    src = list(e.store.switch(hall)['sources'])
    client = await hass_ws_client(hass)
    await client.send_json({'id': 1, 'type': 'ripple_presence/switch/sources', 'ieee': hall, 'sources': src,
                            'sens': {src[0]: 35}})
    assert (await client.receive_json())['success']
    assert e.store.switch(hall)['sens'] == {src[0]: 35, src[1]: 70}
    await client.send_json({'id': 2, 'type': 'ripple_presence/room', 'room_id': 'area:hallway'})
    room = (await client.receive_json())['result']
    assert [l['sens'] for l in room['switches'][0]['links']] == [35, 70]
    assert 'sensitivity' not in room['settings']


async def test_websocket_parks_line_shows_fine(hass, hass_ws_client):
    from homeassistant.helpers import entity_registry as er
    entry, rt = await _setup(hass)
    e = rt.engine
    hall = next(d['ieee'] for d in e.devices.values() if d['name'] == 'Hallway switch')
    src = list(e.store.switch(hall)['sources'])
    client = await hass_ws_client(hass)
    await client.send_json({'id': 1, 'type': 'ripple_presence/switch/sources', 'ieee': hall, 'sources': src,
                            'parked': [src[1]]})
    assert (await client.receive_json())['success']
    await client.send_json({'id': 2, 'type': 'ripple_presence/room', 'room_id': 'area:hallway'})
    res = (await client.receive_json())['result']
    sw = res['switches'][0]
    assert [l['parked'] for l in sw['links']] == [False, True]
    assert 'detected_by' in res['room'] and 'detected_by' in sw
    assert len(sw['advanced']) == len(V5_ADVANCED) and all(a['section'] and a['help'] for a in sw['advanced'])
    await client.send_json({'id': 3, 'type': 'ripple_presence/switch/raw', 'ieee': hall, 'enabled': True})
    assert (await client.receive_json())['error']['code'] == 'writes_disabled'
    reg = er.async_get(hass)
    eid = reg.async_get_entity_id('switch', 'ripple_presence', f'ripple_presence_{hall}_raw_stream')
    assert eid and reg.async_get(eid).disabled_by is not None


async def test_diagnostics_are_json(hass):
    import json
    from custom_components.ripple_presence.diagnostics import async_get_config_entry_diagnostics
    entry, rt = await _setup(hass)
    hall = next(d['ieee'] for d in rt.engine.devices.values() if d['name'] == 'Hallway switch')
    await rt.engine.set_switch_settings(hall, {'off_s': 9})
    diag = await async_get_config_entry_diagnostics(hass, entry)
    json.dumps(diag)
    sw = next(s for s in diag['switches'] if s['ieee'] == hall)
    assert len(sw['advanced']) == len(V5_ADVANCED) and sw['diag'] and sw['stack_used'] == 2860


async def test_fw_install_shows_device_ends_refresh(hass, hass_ws_client):
    FixtureCore = fake_core.FixtureCore
    hall = '0c:43:14:ff:fe:10:20:03'
    with patch.object(FixtureCore, 'ieee_of_entity', create=True, new=lambda self, eid: hall if eid == 'update.hall' else None):
        entry, rt = await _setup(hass)
        refreshes = []
        orig = rt.engine.refresh

        async def counted(*a, **k):
            refreshes.append(1)
            return await orig(*a, **k)
        rt.engine.refresh = counted
        hass.states.async_set('update.hall', 'on', {'in_progress': True, 'update_percentage': 22.81,
                                                    'installed_version': '0x1103339a', 'latest_version': '0x1103339b'})
        await hass.async_block_till_done()
        client = await hass_ws_client(hass)
        await client.send_json({'id': 1, 'type': 'ripple_presence/devices'})
        row = next(d for d in (await client.receive_json())['result'] if d['ieee'] == hall)
        assert row['update']['in_progress'] and row['update']['percentage'] == 22.81
        hass.states.async_set('update.other', 'on', {'in_progress': True})
        hass.states.async_set('update.hall', 'off', {'in_progress': False, 'installed_version': '0x1103339b',
                                                     'latest_version': '0x1103339b'})
        await hass.async_block_till_done()
        await asyncio.sleep(0.1)
        assert not (rt.engine.devices[hall].get('update') or {}).get('in_progress') and refreshes


async def test_websocket_cals_one_line(hass, hass_ws_client):
    from custom_components.ripple_presence import v5
    entry, rt = await _setup(hass, allow_writes=True)
    e = rt.engine
    hall = next(d['ieee'] for d in e.devices.values() if d['name'] == 'Hallway switch')
    smoke = next(d['ieee'] for d in e.devices.values() if d['name'] == 'Smoke alarm')
    src = list(e.store.switch(hall)['sources'])
    client = await hass_ws_client(hass)
    await client.send_json({'id': 1, 'type': 'ripple_presence/line/calibrate', 'rx': hall, 'tx': smoke, 'seconds': 300})
    assert (await client.receive_json())['error']['code'] == 'not_found'
    await client.send_json({'id': 2, 'type': 'ripple_presence/line/calibrate', 'rx': hall, 'tx': src[1], 'seconds': 300})
    assert (await client.receive_json())['result'] == {'written': [hall]}
    nwk = e.devices[src[1]]['nwk']
    assert [w['payload'] for w in rt.core.writes if w.get('command') == v5.CMD_CAPTURE] == [nwk.to_bytes(2, 'little')]
    await client.send_json({'id': 3, 'type': 'ripple_presence/line/calibrate', 'rx': hall, 'tx': src[0], 'seconds': 300})
    err = (await client.receive_json())['error']
    assert err['code'] == 'invalid' and '0x93' in err['message']


async def test_websocket_line_cal_refused_when_read(hass, hass_ws_client):
    entry, rt = await _setup(hass)
    hall = next(d['ieee'] for d in rt.engine.devices.values() if d['name'] == 'Hallway switch')
    src = rt.engine.store.switch(hall)['sources'][0]
    client = await hass_ws_client(hass)
    await client.send_json({'id': 1, 'type': 'ripple_presence/line/calibrate', 'rx': hall, 'tx': src, 'seconds': 300})
    assert (await client.receive_json())['error']['code'] == 'writes_disabled'
    assert rt.core.writes == []


async def test_websocket_cal_takes_rooms_only(hass, hass_ws_client):
    from custom_components.ripple_presence import v5
    entry, rt = await _setup(hass, allow_writes=True)
    hall = next(d['ieee'] for d in rt.engine.devices.values() if d['name'] == 'Hallway switch')
    client = await hass_ws_client(hass)
    await client.send_json({'id': 1, 'type': 'ripple_presence/calibrate', 'ieee': hall, 'seconds': 300})
    assert (await client.receive_json())['error']['code'] == 'invalid_format'
    assert rt.core.writes == []
    await client.send_json({'id': 2, 'type': 'ripple_presence/calibrate', 'room_id': 'area:hallway', 'seconds': 300})
    members = rt.engine.room('area:hallway')['members']
    assert sorted((await client.receive_json())['result']['written']) == sorted(members)
    assert sorted(w['ieee'] for w in rt.core.writes if w.get('attr') == v5.A_CALIBRATE) == sorted(members)


async def test_gone_rooms_and_switches_leave_ha(hass):
    from homeassistant.helpers import device_registry as dr
    entry, rt = await _setup(hass)
    ents, reg = er.async_get(hass), dr.async_get(hass)
    area = next(d['area_id'] for d in rt.engine.ripple_devices() if d['area_id'])
    room = rt.engine.create_room('Office', [rt.engine.ripple_devices()[0]['ieee']])
    await asyncio.sleep(1.2)
    await hass.async_block_till_done()
    occ = f'{DOMAIN}_room_{room["id"]}_occupancy'
    assert _eid(hass, 'binary_sensor', occ)
    old = reg.async_get_or_create(config_entry_id=entry.entry_id, identifiers={(DOMAIN, 'room_r0ld0000')}, name='Office')
    ents.async_get_or_create('binary_sensor', DOMAIN, f'{DOMAIN}_room_r0ld0000_occupancy', config_entry=entry, device_id=old.id)
    ents.async_get_or_create('number', DOMAIN, f'{DOMAIN}_room_r0ld0000_off_s', config_entry=entry, device_id=old.id)
    gone_sw = f'{DOMAIN}_aa:bb:cc:dd:ee:ff:00:11_active_links'
    ents.async_get_or_create('sensor', DOMAIN, gone_sw, config_entry=entry)
    rt.engine.delete_room(room['id'])
    await asyncio.sleep(1.2)
    await hass.async_block_till_done()
    assert not _eid(hass, 'binary_sensor', occ)
    assert reg.async_get_device(identifiers={(DOMAIN, f'room_{room["id"]}')}) is None
    assert reg.async_get(old.id) is None
    assert not _eid(hass, 'binary_sensor', f'{DOMAIN}_room_r0ld0000_occupancy')
    assert not _eid(hass, 'number', f'{DOMAIN}_room_r0ld0000_off_s')
    assert not _eid(hass, 'sensor', gone_sw)
    assert _eid(hass, 'binary_sensor', f'{DOMAIN}_room_area:{area}_occupancy')
    assert all(_eid(hass, 'sensor', f'{DOMAIN}_{s}_active_links') for s in rt.ready_switches())


async def test_area_room_kept_while_switch_may_v5(hass):
    entry, rt = await _setup(hass)
    d = next(d for d in rt.engine.ripple_devices() if d['area_id'])
    rid = f'area:{d["area_id"]}'
    assert not rt._room_gone(rid, {rid})
    assert rt._room_gone('r0ld0000', set())
    d['kind'], d['fw'] = 'needs_firmware', None
    assert not rt._room_gone(rid, set())
    rt.store.data.setdefault('hidden_areas', []).append(rid)
    assert rt._room_gone(rid, set())


async def _settle(hass):
    await asyncio.sleep(1.2)
    await hass.async_block_till_done()


def _fw505_fixture(tmp_path):
    """Stairs switch on 5.0.5 (SENSE_API 6) with its first line detecting, Kitchen switch on 5.0.4."""
    import json
    fx = json.load(open(os.path.join(FIXTURES, 'synthetic.json')))
    by = {d.get('user_given_name'): d['ieee'] for d in fx['zha_devices']}
    fx['state'][by['Stairs switch']].update(sense_api=6, lines_on=0b001)
    fx['state'][by['Kitchen switch']]['sense_api'] = 5
    path = tmp_path / 'fw505.json'
    path.write_text(json.dumps(fx))
    return str(path), by


async def test_505_motion_sensor_per_line_created(hass, tmp_path):
    path, by = _fw505_fixture(tmp_path)
    entry, rt = await _setup(hass, path, allow_writes=True)
    rt.core.simulate = False
    stairs, hall, living, tv = (by[n] for n in ('Stairs switch', 'Hallway switch', 'Living room switch', 'TV plug'))
    uid = lambda tx: f'{DOMAIN}_{stairs}_line_{tx}'
    await _settle(hass)
    eids = {tx: _eid(hass, 'binary_sensor', uid(tx)) for tx in (hall, living, tv)}
    assert all(eids.values()), eids
    assert [hass.states.get(eids[tx]).state for tx in (hall, living, tv)] == ['on', 'off', 'off']
    st = hass.states.get(eids[hall])
    assert st.attributes['device_class'] == 'motion' and st.attributes['sender'] == 'Hallway switch'
    assert st.attributes['friendly_name'].endswith('Motion from Hallway switch')
    # API 5 (firmware 5.0.4): no per-line sensors
    ents = er.async_get(hass)
    assert not [e for e in er.async_entries_for_config_entry(ents, entry.entry_id)
                if e.unique_id.startswith(f"{DOMAIN}_{by['Kitchen switch']}_line_")]
    # the report of 0xff46 (with zone_state, one Report) moves the states
    rt.core.report(stairs, v5.CLUSTER, v5.A_LINES_ON, 0b110)
    await _settle(hass)
    assert [hass.states.get(eids[tx]).state for tx in (hall, living, tv)] == ['off', 'on', 'on']
    # a line leaves sources: its sensor goes; it comes back: a new one
    await rt.engine.remove_source(stairs, hall)
    rt._on_change()
    await _settle(hass)
    assert not _eid(hass, 'binary_sensor', uid(hall))
    assert _eid(hass, 'binary_sensor', uid(living)) and _eid(hass, 'binary_sensor', uid(tv))
    assert [hass.states.get(eids[tx]).state for tx in (living, tv)] == ['on', 'on']
    await rt.engine.add_source(stairs, hall)
    rt._on_change()
    await _settle(hass)
    assert _eid(hass, 'binary_sensor', uid(hall))


async def test_line_sensors_survive_stale_entity(hass, tmp_path):
    path, by = _fw505_fixture(tmp_path)
    entry = _entry(hass)
    ents = er.async_get(hass)
    stairs, kitchen = by['Stairs switch'], by['Kitchen switch']
    keep = ents.async_get_or_create('binary_sensor', DOMAIN, f"{DOMAIN}_{stairs}_line_{by['Hallway switch']}", config_entry=entry)
    bad = ents.async_get_or_create('binary_sensor', DOMAIN, f'{DOMAIN}_{stairs}_line_x', config_entry=entry)
    old_fw = ents.async_get_or_create('binary_sensor', DOMAIN, f"{DOMAIN}_{kitchen}_line_{by['Hallway switch']}",
                                      config_entry=entry)
    await _setup(hass, path, entry=entry)
    await _settle(hass)
    assert ents.async_get(keep.entity_id) is not None
    assert ents.async_get(bad.entity_id) is None
    assert ents.async_get(old_fw.entity_id) is None  # Kitchen switch runs 5.0.4: no 0xff46


async def test_room_trigger_select_and_number(hass, tmp_path):
    """Per room, a select any/all/custom and the number of lines for custom; the motion sensor shows the count."""
    path, by = _fw505_fixture(tmp_path)
    entry, rt = await _setup(hass, path)
    rt.core.simulate = False
    await _settle(hass)
    sel = _eid(hass, 'select', 'ripple_presence_room_area:hallway_trigger_mode')
    num = _eid(hass, 'number', 'ripple_presence_room_area:hallway_trigger_k')
    occ = _eid(hass, 'binary_sensor', 'ripple_presence_room_area:hallway_occupancy')
    assert sel and num and occ
    st = hass.states.get(sel)
    assert st.state == 'any' and st.attributes['options'] == ['any', 'all', 'custom']
    a = hass.states.get(occ).attributes
    assert (a['trigger_mode'], a['threshold'], a['active_lines'], a['total_lines']) == ('any', 1, 1, 4)
    await hass.services.async_call('select', 'select_option', {'entity_id': sel, 'option': 'all'}, blocking=True)
    await _settle(hass)
    assert hass.states.get(sel).state == 'all'
    assert hass.states.get(occ).attributes['threshold'] == 4
    await hass.services.async_call('number', 'set_value', {'entity_id': num, 'value': 2}, blocking=True)
    await _settle(hass)
    assert hass.states.get(sel).state == 'custom'
    assert float(hass.states.get(num).state) == 2 and hass.states.get(num).attributes['max'] == 4
    assert rt.engine.room_settings('area:hallway')['trigger_k'] == 2
    assert rt.core.writes == []


async def test_fw_every_router_listed_and_any_board(hass, hass_ws_client):
    entry, rt = await _setup(hass, allow_writes=True)
    started = []

    class FakeFlasher:
        def start(self, ieee, board):
            started.append((ieee, board))

        def view(self):
            return {}
    rt.flasher = FakeFlasher()
    client = await hass_ws_client(hass)
    await client.send_json({'id': 1, 'type': 'ripple_presence/firmware/overview'})
    res = (await client.receive_json())['result']
    ieees = {d['ieee'] for d in res['devices']}
    bulb, door = '0c:43:14:ff:fe:10:20:0b', '0c:43:14:ff:fe:10:20:0c'
    assert bulb in ieees and door not in ieees and '00:00:00:00:00:00:00:01' not in ieees
    assert all(b['flashable'] for b in res['table']) and res['table']
    key = res['table'][0]['key']
    await client.send_json({'id': 2, 'type': 'ripple_presence/firmware/install', 'ieee': bulb, 'board': key, 'custom': True})
    assert (await client.receive_json())['success']
    assert started[0][0] == bulb and started[0][1]['key'] == key and started[0][1]['how'] == 'stock'
    await client.send_json({'id': 3, 'type': 'ripple_presence/firmware/install', 'ieee': door, 'board': key})
    assert not (await client.receive_json())['success']

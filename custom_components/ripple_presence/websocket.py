"""Websocket commands used by the Ripple sidebar panel."""
from __future__ import annotations

import time

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, SIGNAL_UPDATE
from .engine import is_our_firmware, is_ripple_firmware
from .flasher import FlashError
from .live import LiveBudget
from .panelpush import build_views, zha_list
from .zigbee import WritesDisabled, ZigbeeError


def _with_entity(hass, rooms):
    """Adds the entity id of each room's motion sensor, for the HA more-info dialog."""
    reg = er.async_get(hass)
    for r in rooms:
        r['entity_id'] = reg.async_get_entity_id('binary_sensor', DOMAIN, f"{DOMAIN}_room_{r['id']}_occupancy")
    return rooms


def _rt(hass):
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    return entries[0].runtime_data if entries else None


@callback
def async_register_commands(hass: HomeAssistant):
    for fn in (ws_state, ws_room, ws_candidates, ws_room_settings, ws_switch_settings, ws_sources, ws_calibrate,
               ws_room_save, ws_room_delete, ws_devices, ws_endpoints, ws_firmware, ws_bindings, ws_bindings_read,
               ws_bind_add, ws_bind_remove, ws_reset_advanced, ws_raw_stream, ws_subscribe, ws_live_start, ws_live_stop,
               ws_live_candidate, ws_line_save, ws_line_add, ws_line_remove, ws_line_calibrate, ws_zha_devices, ws_history,
               ws_panel_subscribe, ws_panel_snapshot, ws_boards, ws_board_match, ws_fw_overview, ws_fw_install):
        websocket_api.async_register_command(hass, fn)


async def _guard(connection, msg, coro):
    try:
        connection.send_result(msg['id'], await coro)
    except WritesDisabled as e:
        connection.send_error(msg['id'], 'writes_disabled', str(e))
    except LiveBudget as e:
        connection.send_error(msg['id'], 'live_budget', str(e))
    except (ZigbeeError, ValueError) as e:
        connection.send_error(msg['id'], 'invalid', str(e))
    except KeyError as e:
        connection.send_error(msg['id'], 'not_found', str(e))


def _no_entry(connection, msg):
    connection.send_error(msg['id'], 'not_loaded', 'Ripple is not set up')


@websocket_api.websocket_command({vol.Required('type'): 'ripple_presence/state'})
@callback
def ws_state(hass, connection, msg):
    rt = _rt(hass)
    if not rt:
        return _no_entry(connection, msg)
    e = rt.engine
    connection.send_result(msg['id'], {
        'allow_writes': rt.zb.allow_writes, 'status': e.status, 'entry_id': rt.entry.entry_id, 'now': time.time(),
        'rooms': _with_entity(hass, e.rooms()), 'switches': [e.switch_view(s) for s in rt.ready_switches()], 'live': e.live.view(),
        'others': [e.device_summary(d) for d in e.devices.values() if d['kind'] in ('needs_firmware', 'candidate')]})


@websocket_api.websocket_command({vol.Required('type'): 'ripple_presence/room', vol.Required('room_id'): str})
@callback
def ws_room(hass, connection, msg):
    rt = _rt(hass)
    if not rt:
        return _no_entry(connection, msg)
    e = rt.engine
    try:
        r = e.room(msg['room_id'])
    except KeyError as err:
        return connection.send_error(msg['id'], 'not_found', str(err))
    connection.send_result(msg['id'], {'room': r, 'settings': e.room_settings(r['id']),
                                       'switches': [e.switch_view(m) for m in r['members'] if e.profile(m)]})


@websocket_api.websocket_command({vol.Required('type'): 'ripple_presence/candidates', vol.Required('ieee'): str})
@callback
def ws_candidates(hass, connection, msg):
    rt = _rt(hass)
    if not rt:
        return _no_entry(connection, msg)
    connection.send_result(msg['id'], rt.engine.candidates(msg['ieee']))


@websocket_api.websocket_command({vol.Required('type'): 'ripple_presence/room/settings', vol.Required('room_id'): str,
                                  vol.Required('changes'): dict})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_room_settings(hass, connection, msg):
    rt = _rt(hass)
    await _guard(connection, msg, rt.engine.set_room_settings(msg['room_id'], msg['changes']))


@websocket_api.websocket_command({vol.Required('type'): 'ripple_presence/switch/settings', vol.Required('ieee'): str,
                                  vol.Required('changes'): dict})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_switch_settings(hass, connection, msg):
    rt = _rt(hass)
    await _guard(connection, msg, rt.engine.set_switch_settings(msg['ieee'], msg['changes']))


@websocket_api.websocket_command({vol.Required('type'): 'ripple_presence/switch/sources', vol.Required('ieee'): str,
                                  vol.Required('sources'): [str], vol.Optional('sens'): {str: int},
                                  vol.Optional('parked'): [str]})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_sources(hass, connection, msg):
    rt = _rt(hass)
    await _guard(connection, msg, rt.engine.set_sources(msg['ieee'], msg['sources'], msg.get('sens'), msg.get('parked')))


@websocket_api.websocket_command({vol.Required('type'): 'ripple_presence/switch/reset_advanced', vol.Required('ieee'): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_reset_advanced(hass, connection, msg):
    rt = _rt(hass)
    await _guard(connection, msg, rt.engine.reset_advanced(msg['ieee']))


@websocket_api.websocket_command({vol.Required('type'): 'ripple_presence/switch/raw', vol.Required('ieee'): str,
                                  vol.Required('enabled'): bool})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_raw_stream(hass, connection, msg):
    rt = _rt(hass)
    await _guard(connection, msg, rt.engine.set_raw_stream(msg['ieee'], msg['enabled']))


@websocket_api.websocket_command({vol.Required('type'): 'ripple_presence/calibrate', vol.Required('room_id'): str,
                                  vol.Required('seconds'): int})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_calibrate(hass, connection, msg):
    await _guard(connection, msg, _rt(hass).engine.calibrate_room(msg['room_id'], msg['seconds']))


@websocket_api.websocket_command({vol.Required('type'): 'ripple_presence/room/save', vol.Optional('room_id'): str,
                                  vol.Required('name'): str, vol.Required('members'): [str]})
@websocket_api.require_admin
@callback
def ws_room_save(hass, connection, msg):
    e = _rt(hass).engine
    try:
        r = e.update_room(msg['room_id'], msg['name'], msg['members']) if msg.get('room_id') else e.create_room(msg['name'], msg['members'])
        connection.send_result(msg['id'], r)
    except (ValueError, KeyError) as err:
        connection.send_error(msg['id'], 'invalid', str(err))


@websocket_api.websocket_command({vol.Required('type'): 'ripple_presence/room/delete', vol.Required('room_id'): str})
@websocket_api.require_admin
@callback
def ws_room_delete(hass, connection, msg):
    _rt(hass).engine.delete_room(msg['room_id'])
    connection.send_result(msg['id'], {'ok': True})


def _coordinator(e):
    return next((d['ieee'] for d in e.devices.values() if d['kind'] == 'coordinator'), None)


@websocket_api.websocket_command({vol.Required('type'): 'ripple_presence/devices'})
@callback
def ws_devices(hass, connection, msg):
    rt = _rt(hass)
    if not rt:
        return _no_entry(connection, msg)
    e = rt.engine
    connection.send_result(msg['id'], [e.device_summary(d) for d in e.devices.values() if is_ripple_firmware(d)])


@websocket_api.websocket_command({vol.Required('type'): 'ripple_presence/endpoints', vol.Required('ieee'): str})
@websocket_api.async_response
async def ws_endpoints(hass, connection, msg):
    rt = _rt(hass)
    await _guard(connection, msg, rt.core.call({'type': 'ripple/endpoints', 'ieee': msg['ieee']}))


@websocket_api.websocket_command({vol.Required('type'): 'ripple_presence/firmware'})
@websocket_api.async_response
async def ws_firmware(hass, connection, msg):
    rt = _rt(hass)
    await _guard(connection, msg, rt.core.call({'type': 'ripple/firmware'}))


@websocket_api.websocket_command({vol.Required('type'): 'ripple_presence/bindings'})
@callback
def ws_bindings(hass, connection, msg):
    rt = _rt(hass)
    if not rt:
        return _no_entry(connection, msg)
    connection.send_result(msg['id'], rt.bindings.view(_coordinator(rt.engine)))


@websocket_api.websocket_command({vol.Required('type'): 'ripple_presence/bindings/read', vol.Required('ieee'): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_bindings_read(hass, connection, msg):
    rt = _rt(hass)
    await _guard(connection, msg, rt.bindings.read(msg['ieee']))


@websocket_api.websocket_command({vol.Required('type'): 'ripple_presence/bindings/add', vol.Required('src'): str,
                                  vol.Required('src_ep'): int, vol.Required('dst'): str, vol.Required('dst_ep'): int})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_bind_add(hass, connection, msg):
    rt = _rt(hass)
    await _guard(connection, msg, rt.bindings.add(msg['src'], msg['src_ep'], msg['dst'], msg['dst_ep']))


@websocket_api.websocket_command({vol.Required('type'): 'ripple_presence/bindings/remove', vol.Required('src'): str,
                                  vol.Required('src_ep'): int, vol.Required('dst'): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_bind_remove(hass, connection, msg):
    rt = _rt(hass)
    await _guard(connection, msg, rt.bindings.remove(msg['src'], msg['src_ep'], msg['dst']))


def panel_views(rt):
    """Everything the panel shows, as PanelPush builds it for snapshots and deltas."""
    reg = er.async_get(rt.hass)
    return build_views(rt.engine, rt.zb.allow_writes, rt.entry.entry_id, rt.ready_switches(),
                       lambda rid: reg.async_get_entity_id('binary_sensor', DOMAIN, f"{DOMAIN}_room_{rid}_occupancy"))


def _zha_list(rt):
    return zha_list(rt.engine)


@websocket_api.websocket_command({vol.Required('type'): 'ripple_presence/panel/subscribe'})
@callback
def ws_panel_subscribe(hass, connection, msg):
    """Snapshot first, then deltas ({'type': 'delta', 'rev': n, ...}), Live frames, and 'closed' on unload."""
    rt = _rt(hass)
    if not rt:
        return _no_entry(connection, msg)
    connection.send_result(msg['id'])

    @callback
    def send(ev):
        connection.send_message(websocket_api.event_message(msg['id'], ev))
    unsub_push = rt.push.subscribe(send)
    rt.engine.live.listeners.append(send)

    @callback
    def unsub():
        unsub_push()
        if send in rt.engine.live.listeners:
            rt.engine.live.listeners.remove(send)
    connection.subscriptions[msg['id']] = unsub


@websocket_api.websocket_command({vol.Required('type'): 'ripple_presence/panel/snapshot'})
@callback
def ws_panel_snapshot(hass, connection, msg):
    """The same snapshot the subscription starts with, read-only, with its rev."""
    rt = _rt(hass)
    if not rt:
        return _no_entry(connection, msg)
    connection.send_result(msg['id'], rt.push.snapshot()[1])


@websocket_api.websocket_command({vol.Required('type'): 'ripple_presence/subscribe'})
@callback
def ws_subscribe(hass, connection, msg):
    """Pushes {'type': 'changed'} when Ripple's state changes and every Live frame as it arrives; no polling."""
    rt = _rt(hass)
    if not rt:
        return _no_entry(connection, msg)

    @callback
    def changed():
        connection.send_message(websocket_api.event_message(msg['id'], {'type': 'changed'}))

    @callback
    def live(ev):
        connection.send_message(websocket_api.event_message(msg['id'], ev))
    unsub_changed = async_dispatcher_connect(hass, SIGNAL_UPDATE, changed)
    rt.engine.live.listeners.append(live)

    @callback
    def unsub():
        unsub_changed()
        if live in rt.engine.live.listeners:
            rt.engine.live.listeners.remove(live)
    connection.subscriptions[msg['id']] = unsub
    connection.send_result(msg['id'])


@websocket_api.websocket_command({vol.Required('type'): 'ripple_presence/live/start', vol.Required('room_id'): str,
                                  vol.Required('seconds'): int,
                                  vol.Optional('lines'): [vol.All([str], vol.Length(min=2, max=2))]})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_live_start(hass, connection, msg):
    await _guard(connection, msg, _rt(hass).engine.live.start(msg['room_id'], msg['seconds'], msg.get('lines')))


@websocket_api.websocket_command({vol.Required('type'): 'ripple_presence/live/stop', vol.Required('room_id'): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_live_stop(hass, connection, msg):
    await _guard(connection, msg, _rt(hass).engine.live.stop(msg['room_id']))


@websocket_api.websocket_command({vol.Required('type'): 'ripple_presence/live/candidate', vol.Required('room_id'): str,
                                  vol.Required('rx'): str, vol.Required('tx'): str, vol.Required('step'): vol.Any(None, int)})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_live_candidate(hass, connection, msg):
    await _guard(connection, msg, _rt(hass).engine.live.set_candidate(msg['room_id'], msg['rx'], msg['tx'], msg['step']))


@websocket_api.websocket_command({vol.Required('type'): 'ripple_presence/line/save', vol.Required('rx'): str,
                                  vol.Required('tx'): str, vol.Required('sens'): int})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_line_save(hass, connection, msg):
    await _guard(connection, msg, _rt(hass).engine.save_line(msg['rx'], msg['tx'], msg['sens']))


@websocket_api.websocket_command({vol.Required('type'): 'ripple_presence/line/add', vol.Required('rx'): str,
                                  vol.Required('tx'): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_line_add(hass, connection, msg):
    await _guard(connection, msg, _rt(hass).engine.add_line(msg['rx'], msg['tx']))


@websocket_api.websocket_command({vol.Required('type'): 'ripple_presence/line/remove', vol.Required('rx'): str,
                                  vol.Required('tx'): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_line_remove(hass, connection, msg):
    await _guard(connection, msg, _rt(hass).engine.remove_line(msg['rx'], msg['tx']))


@websocket_api.websocket_command({vol.Required('type'): 'ripple_presence/line/calibrate', vol.Required('rx'): str,
                                  vol.Required('tx'): str, vol.Required('seconds'): int})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_line_calibrate(hass, connection, msg):
    await _guard(connection, msg, _rt(hass).engine.calibrate_line(msg['rx'], msg['tx'], msg['seconds']))


@websocket_api.websocket_command({vol.Required('type'): 'ripple_presence/zha_devices'})
@callback
def ws_zha_devices(hass, connection, msg):
    """Every Zigbee device a binding can target (not the coordinator, not a protected device)."""
    rt = _rt(hass)
    if not rt:
        return _no_entry(connection, msg)
    connection.send_result(msg['id'], _zha_list(rt))


@websocket_api.websocket_command({vol.Required('type'): 'ripple_presence/history', vol.Required('room_id'): str,
                                  vol.Optional('since'): vol.Coerce(float), vol.Optional('until'): vol.Coerce(float),
                                  vol.Optional('limit', default=500): vol.All(int, vol.Range(min=1, max=5000))})
@callback
def ws_history(hass, connection, msg):
    """Detections of the lines of a room for the last 7 days, newest first."""
    rt = _rt(hass)
    if not rt:
        return _no_entry(connection, msg)
    e = rt.engine
    try:
        r = e.room(msg['room_id'])
    except KeyError as err:
        return connection.send_error(msg['id'], 'not_found', str(err))
    lines = {(rx, tx) for rx in r['members'] for tx in (e.store.switch(rx) or {}).get('sources', [])}
    connection.send_result(msg['id'], {'events': e.history.query(lines, msg.get('since'), msg.get('until'),
                                                                   msg['limit'])})


@websocket_api.websocket_command({vol.Required('type'): 'ripple_presence/boards'})
@websocket_api.async_response
async def ws_boards(hass, connection, msg):
    """The board table: bundled plus the user's file, with any errors in that file."""
    rt = _rt(hass)
    if not rt:
        return _no_entry(connection, msg)
    connection.send_result(msg['id'], await hass.async_add_executor_job(rt.boards.all))


@websocket_api.websocket_command({vol.Required('type'): 'ripple_presence/board_match', vol.Required('ieee'): str})
@websocket_api.async_response
async def ws_board_match(hass, connection, msg):
    """Boards from the table that fit what the Zigbee integration reports for this device; more than one means the user picks."""
    rt = _rt(hass)
    if not rt:
        return _no_entry(connection, msg)
    d = next((x for x in await rt.core.call({'type': 'zha/devices'}) if x['ieee'].lower() == msg['ieee'].lower()), None)
    if d is None:
        return connection.send_error(msg['id'], 'not_found', msg['ieee'])
    boards = await hass.async_add_executor_job(rt.boards.match, d.get('manufacturer'), d.get('model'))
    connection.send_result(msg['id'], {'ieee': d['ieee'], 'manufacturer': d.get('manufacturer'),
                                       'model': d.get('model'), 'boards': boards})


BLANK = ('unknown', 'TS0012-CUSTOM')


def _fw_candidates(rt, table, d):
    """Boards for this device: matched by the reported names, or any board if it runs Ripple with no config yet."""
    if (d.get('manufacturer'), d.get('model')) == BLANK:
        return [dict(b, how='blank') for b in table['boards']]
    return rt.boards.match(d.get('manufacturer'), d.get('model'))


def _fw_how(d):
    """How a board the user picks by hand is installed on this device.
    Like the boards it already fits; without any, from what the device runs now."""
    hows = {b.get('how') for b in d['boards']}
    if hows:
        return 'blank' if 'blank' in hows else 'stock' if 'stock' in hows else 'flashed'
    if (d.get('manufacturer'), d.get('model')) == BLANK:
        return 'blank'
    return 'flashed' if d.get('ripple') else 'stock'


async def _fw_devices(hass, rt):
    table = await hass.async_add_executor_job(rt.boards.all)
    out = []
    for d in await rt.core.call({'type': 'zha/devices'}):
        if d.get('device_type') == 'Coordinator':
            continue
        boards = await hass.async_add_executor_job(_fw_candidates, rt, table, d)
        if not boards and d.get('device_type') != 'Router':
            continue
        out.append({'ieee': d['ieee'], 'name': d.get('user_given_name') or d.get('name'), 'area_id': d.get('area_id'),
                    'manufacturer': d.get('manufacturer'), 'model': d.get('model'), 'available': d.get('available'),
                    'device_type': d.get('device_type'), 'ripple': is_our_firmware(d),
                    'protected': d['ieee'].lower() in rt.zb.protected, 'boards': boards})
    return out


@websocket_api.websocket_command({vol.Required('type'): 'ripple_presence/firmware/overview'})
@websocket_api.async_response
async def ws_fw_overview(hass, connection, msg):
    """The Firmware tab: the universal binaries, the devices the board table recognises, the running installs."""
    rt = _rt(hass)
    if not rt:
        return _no_entry(connection, msg)
    table = await hass.async_add_executor_job(rt.boards.all)
    connection.send_result(msg['id'], {
        'table': [b for b in table['boards'] if b['flashable']], 'dir': rt.fw_files.dir, 'binaries': await hass.async_add_executor_job(rt.fw_files.binaries),
        'devices': await _fw_devices(hass, rt), 'jobs': rt.flasher.view() if rt.flasher else {},
        'allow_writes': rt.zb.allow_writes, 'available': rt.flasher is not None})


@websocket_api.websocket_command({vol.Required('type'): 'ripple_presence/firmware/install', vol.Required('ieee'): str,
                                  vol.Required('board'): str, vol.Optional('custom', default=False): bool})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_fw_install(hass, connection, msg):
    """Starts the install; the board is taken again from the table, never from the panel.
    Any router device may get any flashable board the user picks."""
    rt = _rt(hass)
    if not rt:
        return _no_entry(connection, msg)
    if rt.flasher is None:
        return connection.send_error(msg['id'], 'unavailable', 'no Zigbee radio in this mode')
    d = next((x for x in await _fw_devices(hass, rt) if x['ieee'].lower() == msg['ieee'].lower()), None)
    if d is None:
        return connection.send_error(msg['id'], 'not_found', f"{msg['ieee']}: not a router device")
    board = next((b for b in d['boards'] if b['key'] == msg['board']), None)
    if board is None:
        if d.get('device_type') != 'Router':
            return connection.send_error(msg['id'], 'refused', 'a board picked by hand needs a Zigbee router device')
        table = await hass.async_add_executor_job(rt.boards.all)
        board = next((dict(b, how=_fw_how(d)) for b in table['boards'] if b['key'] == msg['board']), None)
    if board is None:
        return connection.send_error(msg['id'], 'invalid', f"board {msg['board']} does not fit this device")
    try:
        rt.flasher.start(d['ieee'], board)
    except (FlashError, ValueError) as e:
        return connection.send_error(msg['id'], 'refused', str(e))
    connection.send_result(msg['id'], {'ok': True, 'jobs': rt.flasher.view()})

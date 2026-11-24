"""Runtime of one Ripple config entry: engine, transport, entity bookkeeping, repairs."""
from __future__ import annotations

import logging
import re

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .attrmap import V5_ADVANCED
from .const import (CONF_ALLOW_WRITES, CONF_BASE_TOPIC, CONF_POLL, CONF_PROTECTED, CONF_RESYNC, CONF_STACK, DEFAULTS, DOMAIN,
                    Z2M_BASE_DEFAULT,
                    SIGNAL_UPDATE)
from . import quirk
from .bindings import Bindings
from .boards import Boards
from .flasher import Flasher, FirmwareFiles, Z2MFlasher
from .engine import Engine
from .hacore import HassCore, update_info
from .z2m import converter as z2m_converter
from .z2mcore import Z2MCore, from_z2m
from .history import HaHistory
from .panelpush import PanelPush
from .store import HaStore
from .zigbee import Zigbee

_LOGGER = logging.getLogger(__name__)
SWITCH_KEYS = {'motion', 'raw_stream', 'off_s', 'beacon_hz', 'cal_s', 'detect', 'calibration', 'cal_left',
               'active_links', 'pending', 'stack_used'} | {f'adv_{a["key"]}' for a in V5_ADVANCED}
ROOM_KEYS = {'occupancy', 'calibrate', 'off_s', 'beacon_hz', 'cal_s', 'detect', 'trigger_mode', 'trigger_k'}
OCCUPANCY_CLUSTER = 0x0406
_SWITCH_UID = re.compile(rf'^{DOMAIN}_([0-9a-f]{{2}}(?::[0-9a-f]{{2}}){{7}})_(.+)$')
# 5.0.5: one motion sensor per line, key line_<sender ieee>
_LINE_KEY = re.compile(r'^line_([0-9a-f]{2}(?::[0-9a-f]{2}){7})$')


@callback
def _is_update_entity(data):
    return str(data.get('entity_id', '')).startswith('update.')


def protected_ieees(hass, device_ids):
    reg = dr.async_get(hass)
    out = []
    for did in device_ids or []:
        d = reg.async_get(did)
        for kind, value in (d.connections if d else ()):
            if kind == dr.CONNECTION_ZIGBEE:
                out.append(value)
        for dom, ident in (d.identifiers if d else ()):
            if dom == 'mqtt' and str(ident).startswith('zigbee2mqtt_0x'):
                out.append(from_z2m(str(ident)[12:]))
    return out


def ripple_only(d, entry_id):
    """True when every identifier of the device is Ripple's and only this entry owns it."""
    owner = {d.config_entry_id} if hasattr(d, 'config_entry_id') else set(d.config_entries)
    return bool(d.identifiers) and all(dom == DOMAIN for dom, _ in d.identifiers) and owner == {entry_id}


class RippleRuntime:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.quirk = None
        self.hass, self.entry = hass, entry
        self.options = {**DEFAULTS, **entry.options}
        self.stack = entry.data.get(CONF_STACK) or 'zha'
        if self.stack == 'z2m':
            self.core = Z2MCore(hass, entry.data.get(CONF_BASE_TOPIC) or Z2M_BASE_DEFAULT)
        else:
            self.core = HassCore(hass)
        self.dev_mode = getattr(self.core, 'standalone', False)
        self.zb = Zigbee(self.core, allow_writes=self.options[CONF_ALLOW_WRITES],
                         protected=protected_ieees(hass, self.options[CONF_PROTECTED]))
        self.store = HaStore(hass)
        self.engine = Engine(self.core, self.zb, self.store,
                             {'poll_interval_s': self.options[CONF_POLL], 'resync_minutes': self.options[CONF_RESYNC]})
        self.engine.history = HaHistory(hass)
        self.engine.listeners.append(self._on_change)
        self.push = PanelPush(self._panel_views, hass.loop)
        self.engine.listeners.append(self.push.changed)
        self.bindings = Bindings(self.engine, self.zb, self.store)
        self.boards = Boards(hass.config.config_dir)
        self.fw_files = FirmwareFiles(hass.config.config_dir)
        if self.dev_mode:
            self.flasher = None
        elif self.stack == 'z2m':
            self.flasher = Z2MFlasher(hass, self.core, self.fw_files, self.boards, self.zb)
        else:
            self.flasher = Flasher(hass, self.core._zigpy, self.fw_files, self.boards, self.zb,
                                   reinterview=self.core.reinterview)
        self.known_switches, self.known_rooms = set(), set()
        self.adders = []
        self.known_lines, self.line_adders = set(), []
        self._update = Debouncer(hass, _LOGGER, cooldown=0.5, immediate=True, function=self._push)
        self._rescan = Debouncer(hass, _LOGGER, cooldown=10, immediate=False, function=self.engine.refresh)

    def _drop_stray_devices(self):
        """On every start removes v4 zone devices and Ripple-only devices left without entities.
        ZHA devices and devices shared with another integration are never touched."""
        reg, ents = dr.async_get(self.hass), er.async_get(self.hass)
        for d in list(dr.async_entries_for_config_entry(reg, self.entry.entry_id)):
            if not ripple_only(d, self.entry.entry_id):
                continue
            zone = all(str(i).startswith('zone_') for _, i in d.identifiers)
            if zone or not er.async_entries_for_device(ents, d.id, include_disabled_entities=True):
                reg.async_remove_device(d.id)

    def _drop_stale_entities(self):
        """Removes Ripple entities whose key Ripple no longer makes, such as the old per-room sensitivity."""
        ents = er.async_get(self.hass)
        for e in er.async_entries_for_config_entry(ents, self.entry.entry_id):
            uid = str(e.unique_id)
            if uid.startswith(f'{DOMAIN}_room_'):
                keep = any(uid.endswith(f'_{k}') for k in ROOM_KEYS)
            else:
                m = _SWITCH_UID.match(uid)
                keep = bool(m) and (m.group(2) in SWITCH_KEYS or bool(_LINE_KEY.match(m.group(2))))
            if not keep:
                ents.async_remove(e.entity_id)

    def _gone_switches(self):
        """Removes switch entities of devices that ZHA knows and that are surely not v5 (older firmware, coordinator)."""
        if self.engine.status.get('error') or not self.engine.devices:
            return
        ents = er.async_get(self.hass)
        for e in er.async_entries_for_config_entry(ents, self.entry.entry_id):
            m = _SWITCH_UID.match(str(e.unique_id))
            d = self.engine.devices.get(m.group(1)) if m else None
            gone = m and d is None
            if gone or (d and d['kind'] in ('needs_firmware', 'other', 'coordinator') and not d.get('unquirked')
                        and not (d['sense'] and d['fw'] is None)):
                ents.async_remove(e.entity_id)
                self.known_switches.discard(m.group(1))
                self.known_lines = {k for k in self.known_lines if k[0] != m.group(1)}

    def _line_sets(self):
        """Lines with a motion sensor, per device whose lines are known: the senders in the device's sources (5.0.5)."""
        out = {}
        for ieee in self.ready_switches():
            st = self.engine.line_states(ieee)
            if st is not None:
                out[ieee] = set(st)
        return out

    def _gone_lines(self, sets):
        """Removes the motion sensor of every line no longer in its device's sources (created and removed with them)."""
        if self.engine.status.get('error'):
            return
        ents = er.async_get(self.hass)
        for e in er.async_entries_for_config_entry(ents, self.entry.entry_id):
            m = _SWITCH_UID.match(str(e.unique_id))
            line = m and _LINE_KEY.match(m.group(2))
            if line and m.group(1) in sets and line.group(1) not in sets[m.group(1)]:
                ents.async_remove(e.entity_id)
                self.known_lines.discard((m.group(1), line.group(1)))

    def _drop_zha_occupancy(self):
        """Removes the ZHA Occupancy entity of v5 devices once ZHA no longer makes it."""
        ents = er.async_get(self.hass)
        for d in self.engine.ripple_devices():
            eid = ents.async_get_entity_id('binary_sensor', 'zha', f"{d['ieee']}-1-{OCCUPANCY_CLUSTER}")
            st = self.hass.states.get(eid) if eid else None
            if eid and (st is None or st.attributes.get('restored')):
                ents.async_remove(eid)

    def _room_gone(self, rid, live):
        """A room is gone when Ripple no longer lists it and no device of its area may still turn out to be v5."""
        if rid in live:
            return False
        if not rid.startswith('area:') or rid in self.store.data.get('hidden_areas', []):
            return True
        return not any(d.get('area_id') == rid[5:] and (d.get('unquirked') or (d['sense'] and d['fw'] is None))
                       for d in self.engine.devices.values())

    def _gone_rooms(self):
        """Removes the entities and the device of every room that no longer exists in Ripple."""
        st = self.engine.status
        if st.get('error') or not st.get('zha') or not st.get('discovered_at'):
            return
        live = {r['id'] for r in self.engine.rooms()}
        ents, reg, pre = er.async_get(self.hass), dr.async_get(self.hass), f'{DOMAIN}_room_'
        for e in er.async_entries_for_config_entry(ents, self.entry.entry_id):
            uid = str(e.unique_id)
            key = next((k for k in ROOM_KEYS if uid.startswith(pre) and uid.endswith(f'_{k}')), None)
            rid = uid[len(pre):-len(key) - 1] if key else None
            if rid and self._room_gone(rid, live):
                ents.async_remove(e.entity_id)
                self.known_rooms.discard(rid)
        for d in list(dr.async_entries_for_config_entry(reg, self.entry.entry_id)):
            rids = [i[5:] for dom, i in d.identifiers if dom == DOMAIN and str(i).startswith('room_')]
            if rids and ripple_only(d, self.entry.entry_id) and all(self._room_gone(r, live) for r in rids):
                reg.async_remove_device(d.id)
                self.known_rooms.difference_update(rids)

    async def async_start(self):
        self._drop_stale_entities()
        self._drop_stray_devices()
        await self.store.async_load()
        await self.engine.history.async_load()
        spawn = lambda coro: self.entry.async_create_background_task(self.hass, coro, f'{DOMAIN} task')
        wait = getattr(self.core, 'wait_ready', None)
        if wait:
            self.engine.hold_reads()
            spawn(self._release_reads(wait))
        await self.engine.start(spawn=spawn)
        if hasattr(self.core, 'run'):
            spawn(self.core.run())
        else:
            spawn(self.engine.refresh())
        self.entry.async_on_unload(self.hass.bus.async_listen(dr.EVENT_DEVICE_REGISTRY_UPDATED, self._on_registry))
        if hasattr(self.core, 'ieee_of_entity'):
            self.entry.async_on_unload(self.hass.bus.async_listen(
                EVENT_STATE_CHANGED, self._on_update_state, event_filter=_is_update_entity))

    async def _release_reads(self, wait):
        await wait(self.options[CONF_POLL])
        if self.stack == 'z2m':
            await self._z2m_converter()
            self.core.on_connect.append(self._z2m_converter)
        self.engine.release_reads()
        await self.engine.refresh()

    async def _z2m_converter(self):
        """Keeps the Ripple external converter in Zigbee2MQTT in step with the board table."""
        rows = self.boards.all()['boards']
        src, _ = await self.hass.async_add_executor_job(z2m_converter.render, rows)
        await self.core.ensure_converter(z2m_converter.FILE_NAME, src)
        self._repairs()

    @callback
    def _on_update_state(self, event):
        ieee = self.core.ieee_of_entity(event.data['entity_id'])
        if ieee:
            self.engine.set_update(ieee, update_info(event.data.get('new_state')))

    @callback
    def _on_registry(self, event):
        self.hass.async_create_task(self._rescan.async_call())

    def _panel_views(self):
        from .websocket import panel_views
        return panel_views(self)

    def stop(self):
        if self.flasher:
            self.flasher.cancel_all()
        self.push.close()
        self.engine.stop()
        self.core.close()
        self._update.async_shutdown()
        self._rescan.async_shutdown()

    @callback
    def _on_change(self):
        self.hass.async_create_task(self._update.async_call())

    @callback
    def register_adder(self, add):
        """Platforms register here; they get what is already known, then every new device or room."""
        self.adders.append(add)
        rooms = [r for r in self.engine.rooms() if r['id'] in self.known_rooms]
        if self.known_switches or rooms:
            add(sorted(self.known_switches), rooms)

    @callback
    def register_line_adder(self, add):
        """The binary_sensor platform registers here; it gets every known line, then every new one."""
        self.line_adders.append(add)
        if self.known_lines:
            add(sorted(self.known_lines))

    def ready_switches(self):
        return [d['ieee'] for d in self.engine.ripple_devices() if self.store.switch(d['ieee'])]

    async def _push(self):
        new_sw = [s for s in self.ready_switches() if s not in self.known_switches]
        new_rooms = [r for r in self.engine.rooms() if r['id'] not in self.known_rooms]
        self._gone_switches()
        self._drop_zha_occupancy()
        self._gone_rooms()
        if new_sw or new_rooms:
            self.known_switches.update(new_sw)
            self.known_rooms.update(r['id'] for r in new_rooms)
            for add in self.adders:
                add(new_sw, new_rooms)
        sets = self._line_sets()
        self._gone_lines(sets)
        new_lines = sorted((rx, tx) for rx, txs in sets.items() for tx in txs if (rx, tx) not in self.known_lines)
        if new_lines and self.line_adders:
            self.known_lines.update(new_lines)
            for add in self.line_adders:
                add(new_lines)
        async_dispatcher_send(self.hass, SIGNAL_UPDATE)
        self._repairs()

    def _repairs(self):
        pending = sum(1 for s in self.ready_switches() if self.engine.pending(s))
        if not self.zb.allow_writes and pending:
            ir.async_create_issue(self.hass, DOMAIN, 'read_only_pending', is_fixable=False,
                                  severity=ir.IssueSeverity.WARNING, translation_key='read_only_pending',
                                  translation_placeholders={'count': str(pending)})
        else:
            ir.async_delete_issue(self.hass, DOMAIN, 'read_only_pending')
        err = getattr(self.core, 'converter_error', None)
        if err:
            ir.async_create_issue(self.hass, DOMAIN, 'z2m_converter', is_fixable=False,
                                  severity=ir.IssueSeverity.ERROR, translation_key='z2m_converter',
                                  translation_placeholders={'error': err})
        else:
            ir.async_delete_issue(self.hass, DOMAIN, 'z2m_converter')
        q = self.quirk
        if q and q.error == 'no_custom_quirks_path':
            ir.async_create_issue(self.hass, DOMAIN, 'quirk_no_path', is_fixable=False,
                                  severity=ir.IssueSeverity.ERROR, translation_key='quirk_no_path')
        else:
            ir.async_delete_issue(self.hass, DOMAIN, 'quirk_no_path')
        if q and q.changed:
            ir.async_create_issue(self.hass, DOMAIN, 'quirk_restart', is_fixable=False,
                                  severity=ir.IssueSeverity.WARNING, translation_key='quirk_restart',
                                  translation_placeholders={'file': f'{q.path}/{quirk.QUIRK_FILE}'})
        else:
            ir.async_delete_issue(self.hass, DOMAIN, 'quirk_restart')
        dupes = (q.duplicates if q else []) or []
        if dupes:
            ir.async_create_issue(self.hass, DOMAIN, 'quirk_duplicate', is_fixable=False,
                                  severity=ir.IssueSeverity.WARNING, translation_key='quirk_duplicate',
                                  translation_placeholders={'files': ', '.join(dupes)})
        else:
            ir.async_delete_issue(self.hass, DOMAIN, 'quirk_duplicate')
        unq = sorted(d['name'] or d['ieee'] for d in self.engine.devices.values() if d.get('unquirked'))
        if unq:
            key = 'quirk_broken' if quirk.ERROR else 'quirk_not_applied'
            ir.async_create_issue(self.hass, DOMAIN, 'quirk_not_applied', is_fixable=False,
                                  severity=ir.IssueSeverity.WARNING, translation_key=key,
                                  translation_placeholders={'count': str(len(unq)), 'names': ', '.join(unq)})
        else:
            ir.async_delete_issue(self.hass, DOMAIN, 'quirk_not_applied')

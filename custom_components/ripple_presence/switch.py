"""Detection on/off per device and per room; raw signal stream and boolean detector constants (disabled by default)."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory

from .entity import RoomEntityBase, SwitchEntityBase


async def async_setup_entry(hass, entry, async_add_entities):
    rt = entry.runtime_data

    def add(switches, rooms):
        ents = [SwitchDetect(rt, s) for s in switches] + [RawStream(rt, s) for s in switches]
        ents += [SelfTune(rt, s) for s in switches]
        ents += [RoomDetect(rt, r) for r in rooms]
        for s in switches:
            prof = rt.engine.profile(s)
            ents += [AdvancedSwitch(rt, s, a) for a in (prof['advanced'] if prof else []) if a.get('kind') == 'bool']
        async_add_entities(ents)
    rt.register_adder(add)


class SwitchDetect(SwitchEntityBase, SwitchEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, rt, ieee):
        super().__init__(rt, ieee, 'detect')

    @property
    def is_on(self):
        return self.settings.get('detect')

    async def async_turn_on(self, **kw):
        await self._run(self.engine.set_switch_settings(self.ieee, {'detect': True}))

    async def async_turn_off(self, **kw):
        await self._run(self.engine.set_switch_settings(self.ieee, {'detect': False}))


class SelfTune(SwitchEntityBase, SwitchEntity):
    """Firmware 5.0.4: the 24 h self-tuning may move each line's s (on, default) or only measures (off)."""
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, rt, ieee):
        super().__init__(rt, ieee, 'self_tune')

    @property
    def available(self):
        d = self.dev or {}
        return super().available and (d.get('config') or {}).get('sense_api') == 5

    @property
    def is_on(self):
        v = self.settings.get('self_tune')
        if v is None:
            v = ((self.dev or {}).get('config') or {}).get('self_tune')
        return None if v is None else bool(v)

    async def async_turn_on(self, **kw):
        await self._run(self.engine.set_switch_settings(self.ieee, {'self_tune': True}))

    async def async_turn_off(self, **kw):
        await self._run(self.engine.set_switch_settings(self.ieee, {'self_tune': False}))


class RoomDetect(RoomEntityBase, SwitchEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, rt, room):
        super().__init__(rt, room, 'detect')

    @property
    def is_on(self):
        v = self.engine.room_settings(self.rid).get('detect') if self.room else None
        return None if v in (None, 'mixed') else v

    async def async_turn_on(self, **kw):
        await self._run(self.engine.set_room_settings(self.rid, {'detect': True}))

    async def async_turn_off(self, **kw):
        await self._run(self.engine.set_room_settings(self.rid, {'detect': False}))


class AdvancedSwitch(SwitchEntityBase, SwitchEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(self, rt, ieee, attr):
        super().__init__(rt, ieee, f'adv_{attr["key"]}')
        self.attr = attr

    @property
    def is_on(self):
        return bool((self.settings.get('advanced') or {}).get(self.attr['key'], self.attr['default']))

    async def async_turn_on(self, **kw):
        await self._run(self.engine.set_switch_settings(self.ieee, {'advanced': {self.attr['key']: 1}}))

    async def async_turn_off(self, **kw):
        await self._run(self.engine.set_switch_settings(self.ieee, {'advanced': {self.attr['key']: 0}}))


class RawStream(SwitchEntityBase, SwitchEntity):
    """0xff31, diagnostics only: the device sends its raw signal samples to HA and turns this off at every restart."""
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, rt, ieee):
        super().__init__(rt, ieee, 'raw_stream')

    @property
    def is_on(self):
        v = (self.dev or {}).get('config', {}).get('raw_enabled')
        return None if v is None else bool(v)

    async def async_turn_on(self, **kw):
        await self._run(self.engine.set_raw_stream(self.ieee, True))

    async def async_turn_off(self, **kw):
        await self._run(self.engine.set_raw_stream(self.ieee, False))

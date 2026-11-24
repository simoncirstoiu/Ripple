"""Device and room settings, plus the firmware's detector constants (disabled by default)."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfTime

from . import attrmap as am
from .const import ROOM_NUMBERS, SWITCH_NUMBERS
from .entity import RoomEntityBase, SwitchEntityBase

UNITS = {'s': UnitOfTime.SECONDS, 'min': UnitOfTime.MINUTES}


async def async_setup_entry(hass, entry, async_add_entities):
    rt = entry.runtime_data

    def add(switches, rooms):
        ents = []
        for s in switches:
            ents += [SwitchNumber(rt, s, *spec) for spec in SWITCH_NUMBERS]
            prof = rt.engine.profile(s)
            ents += [AdvancedNumber(rt, s, a) for a in (prof['advanced'] if prof else []) if a.get('kind') != 'bool']
        for r in rooms:
            ents += [RoomNumber(rt, r, *spec) for spec in ROOM_NUMBERS] + [RoomTriggerK(rt, r)]
        async_add_entities(ents)
    rt.register_adder(add)


class _Spec:
    def _apply_spec(self, lo, hi, step, unit, mode):
        self._attr_native_min_value, self._attr_native_max_value, self._attr_native_step = lo, hi, step
        self._attr_native_unit_of_measurement = UNITS.get(unit, unit)
        self._attr_mode = NumberMode.SLIDER if mode == 'slider' else NumberMode.BOX
        self._attr_entity_category = EntityCategory.CONFIG


class SwitchNumber(SwitchEntityBase, _Spec, NumberEntity):
    def __init__(self, rt, ieee, key, lo, hi, step, unit, mode):
        super().__init__(rt, ieee, key)
        self._apply_spec(lo, hi, step, unit, mode)

    @property
    def native_value(self):
        v = self.settings.get(self.key, 300 if self.key == 'cal_s' else None)
        return None if v is None else v

    async def async_set_native_value(self, value):
        await self._run(self.engine.set_switch_settings(self.ieee, {self.key: int(value)}))


class RoomNumber(RoomEntityBase, _Spec, NumberEntity):
    def __init__(self, rt, room, key, lo, hi, step, unit, mode):
        super().__init__(rt, room, key)
        self._apply_spec(lo, hi, step, unit, mode)

    @property
    def native_value(self):
        if not self.room:
            return None
        v = self.engine.room_settings(self.rid).get(self.key)
        return None if v in (None, 'mixed') else v

    @property
    def extra_state_attributes(self):
        if not self.room:
            return None
        return {'mixed': self.engine.room_settings(self.rid).get(self.key) == 'mixed'}

    async def async_set_native_value(self, value):
        await self._run(self.engine.set_room_settings(self.rid, {self.key: int(value)}))


class RoomTriggerK(RoomEntityBase, NumberEntity):
    """k of the custom room trigger: lines that must detect at once, 1..the room's line count."""
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 1
    _attr_native_step = 1

    def __init__(self, rt, room):
        super().__init__(rt, room, 'trigger_k')

    @property
    def native_max_value(self):
        r = self.room
        return max(1, r['trigger']['total']) if r else 1

    @property
    def native_value(self):
        r = self.room
        return r['trigger']['threshold'] if r and r['trigger']['mode'] == 'custom' else None

    @property
    def extra_state_attributes(self):
        r = self.room
        return {'saved': r['trigger']['k'], 'clamped': r['trigger']['clamped']} if r else None

    async def async_set_native_value(self, value):
        await self._run(self.engine.set_room_settings(self.rid, {'trigger_mode': 'custom', 'trigger_k': int(value)}))


class AdvancedNumber(SwitchEntityBase, NumberEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False
    _attr_mode = NumberMode.BOX

    def __init__(self, rt, ieee, attr):
        super().__init__(rt, ieee, f'adv_{attr["key"]}')
        self.attr = attr
        self._attr_native_min_value, self._attr_native_max_value = attr['min'], attr['max']
        self._attr_native_step = attr['step']
        self._attr_native_unit_of_measurement = UNITS.get(attr['unit'], attr['unit'] or None)

    @property
    def native_value(self):
        return (self.settings.get('advanced') or {}).get(self.attr['key'], self.attr['default'])

    @property
    def extra_state_attributes(self):
        cur = (self.dev or {}).get('config', {}).get(self.attr['key'])
        return {'default': self.attr['default'], 'on_device': None if cur is None else cur / self.attr['scale'],
                'meaning': self.attr['help'], 'firmware_name': am.firmware_name(self.attr)}

    async def async_set_native_value(self, value):
        await self._run(self.engine.set_switch_settings(self.ieee, {'advanced': {self.attr['key']: value}}))

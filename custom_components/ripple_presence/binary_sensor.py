"""Motion per room (device "Ripple - <room>"), per device and, on firmware 5.0.5, per line."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from .entity import RoomEntityBase, SwitchEntityBase


async def async_setup_entry(hass, entry, async_add_entities):
    rt = entry.runtime_data

    def add(switches, rooms):
        async_add_entities([SwitchMotion(rt, s) for s in switches] + [RoomOccupancy(rt, r) for r in rooms])
    rt.register_adder(add)
    rt.register_line_adder(lambda lines: async_add_entities([LineMotion(rt, rx, tx) for rx, tx in lines]))


class RoomOccupancy(RoomEntityBase, BinarySensorEntity):
    """The room's motion sensor; its unique id keeps the key 'occupancy' so existing automations keep their entity."""
    _attr_device_class = BinarySensorDeviceClass.MOTION

    def __init__(self, rt, room):
        super().__init__(rt, room, 'occupancy')

    @property
    def is_on(self):
        r = self.room
        return r['occupied'] if r else None

    @property
    def extra_state_attributes(self):
        r = self.room or {}
        names = {d['ieee']: d['name'] for d in self.engine.devices.values()}
        return {'switches': [names.get(m, m) for m in r.get('members', [])],
                'motion_from': [names.get(m, m) for m in r.get('moving', [])],
                'detected_by': [f"{x['sender']} → {x['switch']}" for x in r.get('detected_by', [])],
                **({'trigger_mode': r['trigger']['mode'], 'threshold': r['trigger']['threshold'],
                    'active_lines': r['trigger']['active'], 'total_lines': r['trigger']['total']} if r.get('trigger') else {})}


class SwitchMotion(SwitchEntityBase, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.MOTION

    def __init__(self, rt, ieee):
        super().__init__(rt, ieee, 'motion')

    @property
    def is_on(self):
        return self.dev['live'].get('motion') if self.dev else None

    @property
    def extra_state_attributes(self):
        if not self.dev or not self.engine.profile(self.ieee):
            return {}
        links = self.engine.links(self.ieee)
        return {'detected_by': [l['name'] for l in links if l['detecting'] and not l['parked']],
                'last_line_on': next((l['name'] for l in links if l['last_on']), None)}


class LineMotion(SwitchEntityBase, BinarySensorEntity):
    """Motion on one line of the device (0xff46, firmware 5.0.5+), on the receiver's device."""
    _attr_device_class = BinarySensorDeviceClass.MOTION

    def __init__(self, rt, ieee, tx):
        super().__init__(rt, ieee, f'line_{tx}')
        self._attr_translation_key = None
        self.tx = tx

    @property
    def name(self):
        x = self.engine.devices.get(self.tx)
        return f"Motion from {x['name'] if x else self.tx}"

    @property
    def _state(self):
        return (self.engine.line_states(self.ieee) or {}).get(self.tx, 'gone')

    @property
    def available(self):
        return super().available and self._state != 'gone'

    @property
    def is_on(self):
        st = self._state
        return None if st == 'gone' else st

    @property
    def extra_state_attributes(self):
        x = self.engine.devices.get(self.tx) or {}
        return {'sender': x.get('name', self.tx), 'sender_ieee': self.tx}

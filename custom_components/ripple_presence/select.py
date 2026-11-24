"""Room trigger: how many lines of the room must detect before its motion turns on."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory

from .const import TRIGGER_MODES
from .entity import RoomEntityBase


async def async_setup_entry(hass, entry, async_add_entities):
    rt = entry.runtime_data

    def add(switches, rooms):
        async_add_entities([RoomTriggerMode(rt, r) for r in rooms])
    rt.register_adder(add)


class RoomTriggerMode(RoomEntityBase, SelectEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = list(TRIGGER_MODES)

    def __init__(self, rt, room):
        super().__init__(rt, room, 'trigger_mode')

    @property
    def current_option(self):
        r = self.room
        return r['trigger']['mode'] if r else None

    async def async_select_option(self, option):
        await self._run(self.engine.set_room_settings(self.rid, {'trigger_mode': option}))

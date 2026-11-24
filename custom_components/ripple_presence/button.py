"""Calibrate a whole room."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory

from .entity import RoomEntityBase


async def async_setup_entry(hass, entry, async_add_entities):
    rt = entry.runtime_data

    def add(switches, rooms):
        async_add_entities([RoomCalibrate(rt, r) for r in rooms])
    rt.register_adder(add)


class RoomCalibrate(RoomEntityBase, ButtonEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, rt, room):
        super().__init__(rt, room, 'calibrate')

    async def async_press(self):
        await self._run(self.engine.calibrate_room(self.rid, self.engine.room_settings(self.rid)['cal_s']), strict=True)

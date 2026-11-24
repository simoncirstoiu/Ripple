"""Base entities: switch entities join the existing ZHA device, room entities get a Ripple service device."""
from __future__ import annotations

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, SIGNAL_UPDATE
from .hacore import zha_registry_entries
from .zigbee import WritesDisabled, ZigbeeError


class RippleEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, rt, key):
        self.rt, self.engine, self.key = rt, rt.engine, key
        self._attr_translation_key = key

    async def async_added_to_hass(self):
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL_UPDATE, self._updated))

    @callback
    def _updated(self):
        self.async_write_ha_state()

    async def _run(self, coro, strict=False):
        """Turns Ripple errors into errors HA shows next to the control.
        Settings are kept when writes are off; actions (strict) report it."""
        try:
            res = await coro
        except WritesDisabled as e:
            if strict:
                raise HomeAssistantError(str(e), translation_domain=DOMAIN, translation_key='writes_disabled') from e
            return None
        except (ZigbeeError, ValueError, KeyError) as e:
            raise HomeAssistantError(str(e)) from e
        self.rt._on_change()
        return res


class SwitchEntityBase(RippleEntity):
    def __init__(self, rt, ieee, key):
        super().__init__(rt, key)
        self.ieee = ieee
        self._attr_unique_id = f'{DOMAIN}_{ieee}_{key}'
        zha_dev = zha_registry_entries(rt.hass).get(ieee.lower())
        if zha_dev is not None:
            self.device_entry = zha_dev
        elif rt.dev_mode:
            d = rt.engine.devices.get(ieee) or {}
            self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, ieee)}, name=d.get('name'), model=d.get('model'),
                                                manufacturer=d.get('manufacturer'), sw_version=d.get('sw_version'),
                                                suggested_area=d.get('area'))

    @property
    def dev(self):
        return self.engine.devices.get(self.ieee)

    @property
    def settings(self):
        return (self.rt.store.switch(self.ieee) or {}).get('settings', {})

    @property
    def available(self):
        d = self.dev
        return bool(d and d['kind'] == 'ripple')


class RoomEntityBase(RippleEntity):
    def __init__(self, rt, room, key):
        super().__init__(rt, key)
        self.rid = room['id']
        self._attr_unique_id = f'{DOMAIN}_room_{self.rid}_{key}'
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f'room_{self.rid}')}, name=f"Ripple - {room['name']}", manufacturer='Ripple', model='Room',
            entry_type=DeviceEntryType.SERVICE, suggested_area=room['name'] if room['kind'] == 'area' else None)

    @property
    def room(self):
        try:
            return self.engine.room(self.rid)
        except KeyError:
            return None

    @property
    def available(self):
        return self.room is not None

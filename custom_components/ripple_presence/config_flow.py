"""Config flow (writes off by default) and options flow: settings, links of a device, extra rooms."""
from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector as sel

from .const import (CONF_ALLOW_WRITES, CONF_BASE_TOPIC, CONF_POLL, CONF_PROTECTED, CONF_RESYNC, CONF_STACK, DEFAULTS,
                    DOMAIN, Z2M_BASE_DEFAULT)

NEW_ROOM = '__new__'


def _settings_schema(o, stack='zha'):
    return vol.Schema({
        vol.Required(CONF_ALLOW_WRITES, default=o[CONF_ALLOW_WRITES]): sel.BooleanSelector(),
        vol.Optional(CONF_PROTECTED, default=o[CONF_PROTECTED]): sel.DeviceSelector(
            sel.DeviceSelectorConfig(integration='mqtt' if stack == 'z2m' else 'zha', multiple=True)),
        vol.Required(CONF_POLL, default=o[CONF_POLL]): sel.NumberSelector(sel.NumberSelectorConfig(
            min=10, max=3600, step=1, unit_of_measurement='s', mode=sel.NumberSelectorMode.BOX)),
        vol.Required(CONF_RESYNC, default=o[CONF_RESYNC]): sel.NumberSelector(sel.NumberSelectorConfig(
            min=5, max=1440, step=1, unit_of_measurement='min', mode=sel.NumberSelectorMode.BOX)),
    })


def _clean(user_input):
    out = dict(user_input)
    for k in (CONF_POLL, CONF_RESYNC):
        if k in out:
            out[k] = int(out[k])
    return out


class RippleConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._data = {}

    def _stacks(self):
        out = []
        if self.hass.config_entries.async_entries('zha'):
            out.append('zha')
        if self.hass.config_entries.async_entries('mqtt'):
            out.append('z2m')
        return out

    async def async_step_user(self, user_input=None):
        stacks = self._stacks()
        if not stacks:
            return self.async_abort(reason='no_zigbee')
        if user_input is not None:
            return await self._after_stack(user_input[CONF_STACK])
        if len(stacks) == 1:
            return await self._after_stack(stacks[0])
        schema = vol.Schema({vol.Required(CONF_STACK, default=stacks[0]): sel.SelectSelector(
            sel.SelectSelectorConfig(options=stacks, translation_key=CONF_STACK))})
        return self.async_show_form(step_id='user', data_schema=schema)

    async def _after_stack(self, stack):
        self._data = {CONF_STACK: stack}
        if stack == 'z2m':
            return await self.async_step_z2m()
        return await self.async_step_settings()

    async def async_step_z2m(self, user_input=None):
        if user_input is not None:
            self._data[CONF_BASE_TOPIC] = user_input[CONF_BASE_TOPIC].strip().strip('/') or Z2M_BASE_DEFAULT
            return await self.async_step_settings()
        schema = vol.Schema({vol.Required(CONF_BASE_TOPIC, default=Z2M_BASE_DEFAULT): sel.TextSelector()})
        return self.async_show_form(step_id='z2m', data_schema=schema)

    async def async_step_settings(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title='Ripple', data=self._data, options={**DEFAULTS, **_clean(user_input)})
        full = _settings_schema(DEFAULTS, self._data.get(CONF_STACK, 'zha')).schema
        schema = vol.Schema({k: v for k, v in full.items() if k in (CONF_ALLOW_WRITES, CONF_PROTECTED)})
        return self.async_show_form(step_id='settings', data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return RippleOptionsFlow()


class RippleOptionsFlow(OptionsFlow):
    def __init__(self):
        self._switch = None
        self._room = None

    @property
    def _engine(self):
        return self.config_entry.runtime_data.engine

    def _keep(self):
        return self.async_create_entry(data=dict(self.config_entry.options))

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(step_id='init', menu_options=['settings', 'links', 'rooms'])

    async def async_step_settings(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(data={**DEFAULTS, **_clean(user_input)})
        return self.async_show_form(step_id='settings', data_schema=_settings_schema(
            {**DEFAULTS, **self.config_entry.options}, self.config_entry.data.get(CONF_STACK, 'zha')))

    def _switch_options(self):
        e = self._engine
        return [sel.SelectOptionDict(value=d['ieee'], label=f"{d['name']}" + (f" ({d['area']})" if d['area'] else ''))
                for d in sorted(e.ripple_devices(), key=lambda d: d['name'] or '') if e.store.switch(d['ieee'])]

    async def async_step_links(self, user_input=None):
        opts = self._switch_options()
        if not opts:
            return self.async_abort(reason='no_switches')
        if user_input is not None:
            self._switch = user_input['switch']
            return await self.async_step_links_edit()
        return self.async_show_form(step_id='links', data_schema=vol.Schema({
            vol.Required('switch'): sel.SelectSelector(sel.SelectSelectorConfig(options=opts, mode=sel.SelectSelectorMode.DROPDOWN))}))

    async def async_step_links_edit(self, user_input=None):
        e, ieee = self._engine, self._switch
        errors = {}
        if user_input is not None:
            try:
                await e.set_sources(ieee, user_input.get('sources', []))
                return self._keep()
            except ValueError:
                errors['sources'] = 'too_many'
        cands = e.candidates(ieee)
        options = [sel.SelectOptionDict(value=c['ieee'], label=c['name'] + (' (heard by this device)' if c['heard'] else '')
                                        + (f", {c['area']}" if c['area'] else '')) for c in cands]
        current = (e.store.switch(ieee) or {}).get('sources', [])
        dev = e.devices[ieee]
        return self.async_show_form(
            step_id='links_edit', errors=errors,
            description_placeholders={'switch': dev['name'], 'max': str(e.profile(ieee)['include_slots'])},
            data_schema=vol.Schema({vol.Optional('sources', default=current): sel.SelectSelector(
                sel.SelectSelectorConfig(options=options, multiple=True, mode=sel.SelectSelectorMode.DROPDOWN))}))

    async def async_step_rooms(self, user_input=None):
        custom = self._engine.store.data['rooms']
        options = [sel.SelectOptionDict(value=NEW_ROOM, label='New room')] + [
            sel.SelectOptionDict(value=r['id'], label=r['name']) for r in custom]
        if user_input is not None:
            self._room = None if user_input['room'] == NEW_ROOM else user_input['room']
            return await self.async_step_room_edit()
        return self.async_show_form(step_id='rooms', data_schema=vol.Schema({
            vol.Required('room', default=NEW_ROOM): sel.SelectSelector(sel.SelectSelectorConfig(options=options, mode=sel.SelectSelectorMode.LIST))}))

    async def async_step_room_edit(self, user_input=None):
        e = self._engine
        room = next((r for r in e.store.data['rooms'] if r['id'] == self._room), None)
        errors = {}
        if user_input is not None:
            try:
                if room and user_input.get('remove'):
                    e.delete_room(room['id'])
                elif room:
                    e.update_room(room['id'], user_input['name'], user_input.get('switches', []))
                else:
                    e.create_room(user_input['name'], user_input.get('switches', []))
                return self._keep()
            except ValueError:
                errors['name'] = 'name_required'
        schema = {vol.Required('name', default=room['name'] if room else ''): sel.TextSelector(),
                  vol.Optional('switches', default=room['members'] if room else []): sel.SelectSelector(
                      sel.SelectSelectorConfig(options=self._switch_options(), multiple=True, mode=sel.SelectSelectorMode.LIST))}
        if room:
            schema[vol.Optional('remove', default=False)] = sel.BooleanSelector()
        return self.async_show_form(step_id='room_edit', data_schema=vol.Schema(schema), errors=errors)

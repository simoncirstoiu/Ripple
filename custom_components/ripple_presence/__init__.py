"""Ripple: room presence from the radio links between Zigbee devices with the Ripple sensing firmware."""
from __future__ import annotations

from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from . import quirk
from .const import DEFAULTS, DOMAIN, PANEL_URL, STATIC_URL, VERSION, idents
from .runtime import RippleRuntime, ripple_only
from .websocket import async_register_commands

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.NUMBER, Platform.SELECT, Platform.SENSOR, Platform.SWITCH]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config) -> bool:
    async_register_commands(hass)
    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_URL, str(Path(__file__).parent / 'frontend'), cache_headers=False)])
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    rt = RippleRuntime(hass, entry)
    entry.runtime_data = rt
    if rt.stack == 'zha':
        rt.quirk = await quirk.async_install(hass, VERSION)
    await rt.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await panel_custom.async_register_panel(
        hass, frontend_url_path=PANEL_URL, webcomponent_name='ripple-panel', sidebar_title='Ripple',
        sidebar_icon='mdi:access-point-network', module_url=f'{STATIC_URL}/ripple-panel.js?v={VERSION}',
        require_admin=True, config={})
    entry.async_on_unload(entry.add_update_listener(_options_changed))
    return True


async def _options_changed(hass: HomeAssistant, entry: ConfigEntry) -> None:
    if {**DEFAULTS, **entry.options} != entry.runtime_data.options:
        await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_config_entry_device(hass: HomeAssistant, entry: ConfigEntry, device) -> bool:
    """Lets the UI delete Ripple-only leftovers; live devices and rooms refuse."""
    if not ripple_only(device, entry.entry_id):
        return False
    rt = getattr(entry, 'runtime_data', None)
    if rt is None:
        return all(str(i).startswith('zone_') for _, i in idents(device))
    live = {f'room_{r["id"]}' for r in rt.engine.rooms()}
    live |= {i for i, d in rt.engine.devices.items() if d.get('kind') == 'ripple'}
    return not any(i in live for _, i in idents(device))


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        entry.runtime_data.stop()
        frontend.async_remove_panel(hass, PANEL_URL)
    return ok

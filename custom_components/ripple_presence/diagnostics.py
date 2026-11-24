"""Config entry diagnostics."""
from __future__ import annotations

from homeassistant.components.diagnostics import async_redact_data

from . import attrmap as am
from . import v5
from .z2m.converter import FILE_NAME

REDACT = {'protected_devices'}


async def async_get_config_entry_diagnostics(hass, entry):
    rt = entry.runtime_data
    e = rt.engine
    return {
        'options': async_redact_data(dict(entry.options), REDACT),
        'status': e.status,
        'panel_push': {**rt.push.stats, 'rev': rt.push.rev, 'panels': len(rt.push._conns)},
        'zigbee': {'stats': rt.zb.stats, 'recent_writes': rt.zb.write_log[-50:]},
        'stack': _stack(rt),
        'profiles': {p['id']: [f'>= 0x{v5.MIN_FW:08x}'] for p in am.PROFILES.values()},
        'rooms': e.rooms(),
        'switches': [e.device_detail(s) for s in rt.ready_switches()],
        'others': [e.device_summary(d) for d in e.devices.values() if d['kind'] not in ('ripple', 'coordinator')],
        'store': {k: v for k, v in e.store.data.items() if k != 'probe'},
    }


def _stack(rt):
    core = rt.core
    if getattr(rt, 'stack', 'zha') != 'z2m':
        return {'name': 'ZHA'}
    return {'name': 'Zigbee2MQTT', 'base_topic': core.base, 'bridge': core.bridge,
            'converter_saved': bool(core.converters) and FILE_NAME in core.converters,
            'converter_error': core.converter_error, 'last_error': core.last_error, 'devices': len(core._devs)}

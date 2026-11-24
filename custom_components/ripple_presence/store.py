"""Ripple's own settings: a JSON file (tests) or Home Assistant's storage helper (HaStore)."""
import copy
import json
import logging
import os
import tempfile

from .v5 import SENS_DEFAULT_BY_API, STEP_S, sens_default

# stores written before 5.0.4 hold s on the 5.0.3 scale; a device record without sens_api is on it
S_DEFAULT = SENS_DEFAULT_BY_API[3]

log = logging.getLogger('ripple.store')
STORE_VERSION = 5
# bindings: the last binding table read from each device, kept across restarts (ieee -> at, binds, error)
EMPTY = {'version': STORE_VERSION, 'switches': {}, 'rooms': [], 'room_meta': {}, 'probe': {}, 'bindings': {}}


# Settings that firmware 5.0.3 no longer has: the exit hold (exit_s) is read by no code since the motion rule
DROPPED_SETTINGS = ('hold_s',)


def migrate(old_version, data):
    """Format 1: rooms kept, links become lines at the default s. Format 2 is discarded.
    Format 3 (steps 1-10): every step becomes its s. Format 4: s kept as the device keeps it across the OTA to 5.0.3.
    Settings that 5.0.3 no longer has are dropped."""
    if old_version in (3, 4) and isinstance(data, dict):
        out = {**copy.deepcopy(EMPTY), **copy.deepcopy(data), 'version': STORE_VERSION}
        for sw in out['switches'].values():
            if old_version == 3:
                sw['sens'] = {k: STEP_S.get(v, S_DEFAULT) for k, v in (sw.get('sens') or {}).items()}
            for k in DROPPED_SETTINGS:
                (sw.get('settings') or {}).pop(k, None)
        return out
    if old_version != 1 or not isinstance(data, dict):
        log.warning('Ripple settings format %s is not supported; starting empty', old_version)
        return copy.deepcopy(EMPTY)
    out = copy.deepcopy(EMPTY)
    for k in ('rooms', 'hidden_areas'):
        if k in data:
            out[k] = copy.deepcopy(data[k])
    for rid, meta in (data.get('room_meta') or {}).items():
        out['room_meta'][rid] = {**meta, **({'cal_s': max(60, min(1800, int(meta['cal_s'])))} if 'cal_s' in meta else {})}
    for ieee, sw in (data.get('switches') or {}).items():
        src = list(dict.fromkeys(sw.get('sources') or []))
        out['switches'][ieee] = {'settings': {}, 'sources': src, 'sens': {s: S_DEFAULT for s in src}, 'migrated': True}
    return out


class Store:
    def __init__(self, data_dir):
        os.makedirs(data_dir, exist_ok=True)
        self.path = os.path.join(data_dir, 'ripple.json')
        try:
            with open(self.path) as f:
                loaded = json.load(f)
            if loaded.get('version', 1) != STORE_VERSION:
                loaded = migrate(loaded.get('version', 1), loaded)
            self.data = {**copy.deepcopy(EMPTY), **loaded}
        except (OSError, ValueError):
            self.data = copy.deepcopy(EMPTY)

    def save(self):
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self.path), prefix='.ripple-')
        with os.fdopen(fd, 'w') as f:
            json.dump(self.data, f, indent=1, sort_keys=True)
        os.replace(tmp, self.path)

    def switch(self, ieee):
        return self.data['switches'].get(ieee)

    def put_switch(self, ieee, settings, sources, sens=None, parked=(), sens_api=3):
        """sens_api: the scale the s values are on (3 = 5.0.3, 5 = 5.0.4)."""
        sources = list(sources)
        self.data['switches'][ieee] = {'settings': settings, 'sources': sources,
                                       'sens': {s: (sens or {}).get(s, sens_default(sens_api)) for s in sources},
                                       'parked': [s for s in sources if s in set(parked)], 'sens_api': sens_api}
        self.save()
        return self.data['switches'][ieee]

    def room_meta(self, rid):
        return self.data['room_meta'].setdefault(rid, {})

    def export(self):
        return copy.deepcopy(self.data)

    def import_(self, data):
        if not isinstance(data, dict) or not isinstance(data.get('switches', {}), dict):
            raise ValueError('not a Ripple settings file')
        self.data = {**copy.deepcopy(EMPTY), **{k: v for k, v in data.items() if k in EMPTY}}
        self.save()


class HaStore(Store):
    """Same data, kept in .storage/ripple through Home Assistant's Store with delayed saves."""

    def __init__(self, hass, key='ripple_presence'):
        from homeassistant.helpers.storage import Store as HassStorage

        class _Storage(HassStorage):
            async def _async_migrate_func(self, old_major_version, old_minor_version, old_data):
                return migrate(old_major_version, old_data)
        self._ha = _Storage(hass, STORE_VERSION, key)
        self.data = copy.deepcopy(EMPTY)

    async def async_load(self):
        loaded = await self._ha.async_load()
        if loaded:
            self.data = {**copy.deepcopy(EMPTY), **loaded}

    def save(self):
        self._ha.async_delay_save(lambda: self.data, 2)

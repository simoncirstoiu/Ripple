"""Diagnostic sensors of each Ripple device."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory, UnitOfInformation, UnitOfTime

from . import attrmap as am
from .entity import SwitchEntityBase

CAL_STATES = ['calibrated', 'needs_calibration', 'calibrating', 'refused']


async def async_setup_entry(hass, entry, async_add_entities):
    rt = entry.runtime_data

    def add(switches, rooms):
        ents = []
        for s in switches:
            ents += [Calibration(rt, s), CalLeft(rt, s), Links(rt, s), Pending(rt, s), Counter(rt, s, 'stack_used')]
        async_add_entities(ents)
    rt.register_adder(add)


class _Diag(SwitchEntityBase, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC


class Calibration(_Diag):
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = CAL_STATES

    def __init__(self, rt, ieee):
        super().__init__(rt, ieee, 'calibration')

    @property
    def native_value(self):
        f = (self.dev or {}).get('live', {}).get('flags')
        if f is None:
            return None
        f = am.decode_flags(f, ((self.dev or {}).get('config') or {}).get('sense_api'))
        return 'calibrating' if f['calibrating'] else 'refused' if f['refused'] else (
            'needs_calibration' if f['needs_calibration'] else 'calibrated')


class CalLeft(_Diag):
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS

    def __init__(self, rt, ieee):
        super().__init__(rt, ieee, 'cal_left')

    @property
    def native_value(self):
        return (self.dev or {}).get('live', {}).get('cal_left')


def _node(ent):
    d = ent.dev or {}
    prof = ent.engine.profile(ent.ieee)
    raw = d.get('live', {}).get('node_diag') or d.get('config', {}).get('node_diag')
    return prof['decoders']['node_diag'](raw) if prof and raw else None


class Links(_Diag):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, rt, ieee):
        super().__init__(rt, ieee, 'active_links')

    @property
    def native_value(self):
        n = _node(self)
        return n['usable'] if n else None

    @property
    def extra_state_attributes(self):
        names = (('name', 'name'), ('state', 'state'), ('sens', 'sensitivity'), ('level', 'signal_dbm'),
                 ('rate', 'packets_per_s'), ('evidence_pct', 'evidence_pct'))
        return {'links': [{n: l[k] for k, n in names} for l in self.engine.links(self.ieee)]}


class Pending(_Diag):
    def __init__(self, rt, ieee):
        super().__init__(rt, ieee, 'pending')

    @property
    def native_value(self):
        return len(self.engine.pending(self.ieee))

    @property
    def extra_state_attributes(self):
        return {'changes': [p['key'] for p in self.engine.pending(self.ieee)]}


class Counter(_Diag):
    _attr_entity_registry_enabled_default = False

    def __init__(self, rt, ieee, key):
        super().__init__(rt, ieee, key)
        if key == 'stack_used':
            self._attr_device_class = SensorDeviceClass.DATA_SIZE
            self._attr_native_unit_of_measurement = UnitOfInformation.BYTES
        else:
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self):
        return (self.dev or {}).get('config', {}).get(self.key)

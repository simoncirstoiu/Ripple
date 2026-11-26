"""Constants for Ripple."""
DOMAIN = 'ripple_presence'
VERSION = '1.0.41'
CONF_ALLOW_WRITES = 'allow_writes'
CONF_PROTECTED = 'protected_devices'
CONF_POLL = 'poll_interval_s'
CONF_RESYNC = 'resync_minutes'
CONF_STACK = 'stack'
CONF_BASE_TOPIC = 'base_topic'
STACKS = ('zha', 'z2m')
Z2M_BASE_DEFAULT = 'zigbee2mqtt'
DEFAULTS = {CONF_ALLOW_WRITES: False, CONF_PROTECTED: [], CONF_POLL: 60, CONF_RESYNC: 60}
SIGNAL_UPDATE = f'{DOMAIN}_update'
PANEL_URL = 'ripple'
STATIC_URL = '/ripple_static'
SWITCH_NUMBERS = [
    ('off_s', 1, 255, 1, 's', 'box'),
    ('beacon_hz', 0, 10, 1, None, 'slider'),
    ('cal_s', 60, 1800, 1, 's', 'box'),
]
ROOM_OFF_DEFAULT = 10
ROOM_OFF_MAX = 3600
# lines that must detect before a room turns on: any = 1, all = every line, custom = k
TRIGGER_MODES = ('any', 'all', 'custom')
TRIGGER_DEFAULT = 'any'
TRIGGER_K_MAX = 100
# the room's off_s is its own hold after the last device went off, not the devices' line hold
ROOM_NUMBERS = [('off_s', 0, ROOM_OFF_MAX, 1, 's', 'box')] + SWITCH_NUMBERS[1:]


def idents(d):
    """(domain, id) of every identifier of a device entry. Some integrations register identifiers
    with more than two elements, so they are never unpacked as pairs."""
    for t in (d.identifiers if d else ()):
        if len(t) >= 2:
            yield t[0], t[1]

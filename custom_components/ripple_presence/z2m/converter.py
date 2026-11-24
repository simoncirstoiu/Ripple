"""Builds the Zigbee2MQTT external converter for the router boards in the board table."""
from __future__ import annotations

import hashlib
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATE = 'converter.js.jinja'
FILE_NAME = 'ripple.js'


def _names(prefix, count, three=('left', 'middle', 'right'), start=0):
    if count == 1:
        return [prefix]
    if count == 2:
        return [f'{prefix}_left', f'{prefix}_right']
    if count == 3:
        return [f'{prefix}_{x}' for x in three]
    return [f'{prefix}_{i + start}' for i in range(count)]


def device(config_str, models=(), description=None):
    """One converter entry from a config string, with the endpoint names tuya-zigbee-switch gives them."""
    _, model, *tokens = str(config_str).rstrip(';').split(';')
    n = {'R': 0, 'S': 0, 'X': 0, 'C': 0, 'I': 0}
    led = battery = False
    for tok in tokens:
        if tok in ('SLP', 'M') or not tok:
            continue
        if tok[:2] == 'BT':
            battery = True
        if tok[0] in n:
            n[tok[0]] += 1
        if tok[0] == 'L':
            led = True
    relays = _names('relay', n['R'])
    return {
        'zb_models': list(dict.fromkeys([model, *models])),
        'model': model,
        'description': description or model,
        'switchNames': _names('switch', n['S']),
        'relayNames': relays,
        'relayIndicatorNames': relays[:n['I']],
        'coverSwitchNames': _names('cover_switch', n['X'], start=1),
        'coverNames': _names('cover', n['C']),
        'has_dedicated_net_led': led,
        'has_battery_cluster': battery,
    }


def devices(boards):
    """Entries for the flashable boards, one per model; a model claimed by an earlier entry is not repeated."""
    out, seen = [], set()
    for b in sorted(boards, key=lambda b: (not b.get('user'), not b.get('tested'), b.get('key', ''))):
        if not b.get('flashable'):
            continue
        cfg = str(b.get('config_str', ''))
        parts = cfg.split(';')
        if len(parts) < 3 or not parts[1]:
            continue
        old = b.get('old_zb_models') or []
        d = device(cfg, old if isinstance(old, list) else [old], b.get('human_name'))
        d['zb_models'] = [m for m in d['zb_models'] if m not in seen]
        if parts[1] not in d['zb_models']:
            continue
        seen.update(d['zb_models'])
        out.append(d)
    return out


def render(boards):
    """(source, sha1) of the converter for these boards."""
    env = Environment(loader=FileSystemLoader(str(Path(__file__).parent)), autoescape=False,
                      trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True)
    src = env.get_template(TEMPLATE).render(devices=devices(boards), z2m_v1=False)
    return src, hashlib.sha1(src.encode()).hexdigest()

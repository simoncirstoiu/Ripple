"""Board table: which config string a device with the supported chip needs, found from what ZHA reports."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

BUNDLED = Path(__file__).with_name('boards.json')
USER_FILE = ('ripple', 'boards.json')
KINDS = {'S': 'switches', 'R': 'relays', 'L': 'leds', 'I': 'indicator', 'B': 'button', 'X': 'covers',
         'C': 'cover_switches', 'BT': 'battery'}


def _list(v):
    return [x for x in (v if isinstance(v, list) else [v]) if x]


def summary(config_str):
    """Counts what a config string declares (devices, relays, leds ...), from its tokens after name and model."""
    out = {k: 0 for k in KINDS.values()}
    for tok in str(config_str).split(';')[2:]:
        if tok.startswith('BT'):
            out['battery'] += 1
        elif tok[:1] in KINDS and not tok.startswith(('SLP', 'LP')):
            out[KINDS[tok[:1]]] += 1
    return out


def flashable(board):
    """(ok, reason): the firmware is a Zigbee router build, so only router boards get it."""
    dt = board.get('device_type')
    if dt == 'router':
        return True, None
    return False, f'device_type {dt!r}: only router boards are supported' if dt else 'device_type missing'


def _row(key, b, **extra):
    ok, why = flashable(b)
    return {'key': key, **b, 'summary': summary(b.get('config_str', '')), 'flashable': ok, 'not_flashable': why, **extra}


def check_config(config_str):
    """Raises ValueError if the string cannot be a device config (the firmware reads at most 127 chars)."""
    s = str(config_str)
    parts = s.split(';')
    if not s.endswith(';') or len(parts) < 3 or not parts[0] or not parts[1]:
        raise ValueError('config must be "manufacturer;model;tokens...;" and end with ";"')
    if len(s.encode()) > 127:
        raise ValueError('config is longer than 127 bytes')
    if len(parts[1].encode()) > 31 or len(parts[0].encode()) > 31:
        raise ValueError('manufacturer and model are at most 31 bytes')


class Boards:
    """Bundled table plus the user's file in HA config, re-read when that file changes.
    Reads files: call all() and match() from an executor, not the event loop."""

    def __init__(self, config_dir):
        self.user_path = os.path.join(config_dir, *USER_FILE)
        self._mtime = ()
        self._table = {}
        self._errors = []

    def _load(self):
        errors = []
        table = {}
        try:
            table.update(json.loads(BUNDLED.read_text(encoding='utf-8')).get('boards', {}))
        except (OSError, ValueError) as e:
            errors.append(f'bundled table: {e}')
        try:
            mtime = os.path.getmtime(self.user_path)
        except OSError:
            mtime = None
        if mtime is not None:
            try:
                with open(self.user_path, encoding='utf-8') as f:
                    user = json.load(f).get('boards', {})
                for key, b in user.items():
                    if b is None:
                        table.pop(key, None)
                        continue
                    try:
                        check_config(b.get('config_str', ''))
                    except ValueError as e:
                        errors.append(f'{key}: {e}')
                        continue
                    table[key] = {**b, 'user': True}
            except (OSError, ValueError, AttributeError) as e:
                errors.append(f'{self.user_path}: {e}')
        self._table, self._errors, self._mtime = table, errors, mtime
        for e in errors:
            _LOGGER.warning('Ripple board table: %s', e)

    def _fresh(self):
        try:
            mtime = os.path.getmtime(self.user_path)
        except OSError:
            mtime = None
        if mtime != self._mtime:
            self._load()

    def all(self):
        self._fresh()
        return {'boards': [_row(k, b) for k, b in sorted(self._table.items())],
                'user_file': self.user_path, 'errors': list(self._errors)}

    def match(self, manufacturer, model):
        """Boards that fit what ZHA reports: the stock (before flash) names, or the names from the config (after)."""
        self._fresh()
        out = []
        for key, b in self._table.items():
            cfg = str(b.get('config_str', '')).split(';')
            stock = (manufacturer in _list(b.get('stock_manufacturer_name')) + _list(b.get('old_manufacturer_names'))
                     and model in _list(b.get('stock_model_name')) + _list(b.get('old_zb_models')))
            ours = len(cfg) > 1 and manufacturer == cfg[0] and model == cfg[1]
            if stock or ours:
                out.append(_row(key, b, how='stock' if stock else 'flashed'))
        return sorted(out, key=lambda b: (not b.get('tested'), b['key']))

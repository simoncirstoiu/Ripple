"""Writes zha_quirk.py into ZHA's custom_quirks_path as ripple_quirks.py.
ZHA loads it itself at start; Ripple never touches ZHA's quirk registry."""
from __future__ import annotations

import ast
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

_LOGGER = logging.getLogger(__name__)
SOURCE = Path(__file__).with_name('zha_quirk.py')
QUIRK_FILE = 'ripple_quirks.py'
QUIRK_ATTR = '_quirk_registry_entry'
HEADER = ('# Ripple {version}: the Ripple ZHA quirk, loaded by ZHA from its custom_quirks_path.\n'
          '# Written by the Ripple integration at every start; local edits are overwritten.\n\n')
FOOTER = '\n\n# ZHA registers custom quirks at import.\nfor _builder in build_quirks():\n    _builder.add_to_registry()\n'

ERROR: str | None = None


@dataclass
class Result:
    path: str | None = None
    changed: bool = False
    error: str | None = None
    duplicates: list[str] = field(default_factory=list)


def _configs(text):
    """CONFIGS of zha_quirk.py, read from its source without importing it."""
    for node in ast.parse(text).body:
        if isinstance(node, ast.Assign) and any(getattr(t, 'id', None) == 'CONFIGS' for t in node.targets):
            return [c.value for c in node.value.elts]
    return []


def _read_models():
    try:
        return frozenset(tuple(c.split(';')[:2]) for c in _configs(SOURCE.read_text()))
    except (OSError, SyntaxError):
        return frozenset()


# Read once at import, which HA runs in its executor: models() is called from the event loop for every device.
_MODELS = _read_models()


def models():
    """(manufacturer, model) pairs the quirk applies to."""
    return _MODELS


def render(version):
    return HEADER.format(version=version) + SOURCE.read_text() + FOOTER


def _install(path, version):
    """Writes ripple_quirks.py when its content differs; returns (changed, other files for the same models)."""
    os.makedirs(path, exist_ok=True)
    target = Path(path) / QUIRK_FILE
    text = render(version)
    try:
        changed = target.read_text() != text
    except OSError:
        changed = True
    if changed:
        tmp = target.with_suffix('.tmp')
        tmp.write_text(text)
        os.replace(tmp, target)
    ours = {m for _, m in models()}
    dupes = []
    for f in sorted(Path(path).glob('*.py')):
        if f.name == QUIRK_FILE:
            continue
        try:
            body = f.read_text(errors='ignore')
        except OSError:
            continue
        if any(m in body for m in ours):
            dupes.append(str(f))
    return changed, dupes


async def _custom_quirks_path(hass):
    """zha: custom_quirks_path from configuration.yaml (ZHA reads it only from there)."""
    from homeassistant.config import async_hass_config_yaml
    conf = await async_hass_config_yaml(hass)
    return ((conf or {}).get('zha') or {}).get('custom_quirks_path')


async def async_install(hass, version) -> Result:
    global ERROR
    res = Result()
    try:
        res.path = await _custom_quirks_path(hass)
    except Exception as err:  # noqa: BLE001
        ERROR = res.error = f'configuration.yaml could not be read: {err}'
        return res
    if not res.path:
        ERROR = res.error = 'no_custom_quirks_path'
        return res
    try:
        res.changed, res.duplicates = await hass.async_add_executor_job(_install, res.path, version)
        ERROR = None
    except Exception as err:  # noqa: BLE001
        ERROR = res.error = repr(err)
        _LOGGER.exception('Ripple quirk file not written')
        return res
    if res.changed:
        _LOGGER.warning('Ripple quirk written to %s; ZHA loads it at the next Home Assistant start',
                        os.path.join(res.path, QUIRK_FILE))
    return res

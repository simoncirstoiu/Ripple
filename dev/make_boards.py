"""Builds boards.json (the bundled board table) from a device_db.yaml, keeping only chips the firmware supports."""
import importlib.util
import json
import os
import re
import sys

import yaml

_spec = importlib.util.spec_from_file_location('boards', os.path.join(
    os.path.dirname(__file__), '..', 'custom_components', 'ripple_presence', 'boards.py'))
boards_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(boards_mod)

CHIPS = {'TLSR8258'}
FIELDS = ('human_name', 'category', 'power', 'neutral', 'output', 'device_type', 'mcu', 'stock_manufacturer_name',
          'stock_model_name', 'old_manufacturer_names', 'old_zb_models', 'stock_manufacturer_id', 'stock_image_type',
          'config_str', 'alt_config_str', 'status', 'tested')


def main(src, dst):
    db = yaml.safe_load(open(src))
    boards = {}
    for key, v in sorted(db.items()):
        if not isinstance(v, dict) or v.get('mcu') not in CHIPS or not v.get('config_str'):
            continue
        try:
            boards_mod.check_config(v['config_str'])
        except ValueError as e:
            print(f'skip {key}: {e}')
            continue
        boards[key] = {f: v.get(f) for f in FIELDS if v.get(f) is not None}
        if 'human_name' in boards[key]:
            boards[key]['human_name'] = re.sub(r'\s*<br\s*/?>\s*', ' / ', boards[key]['human_name'])
    out = {'version': 1, 'boards': boards}
    with open(dst, 'w') as f:
        json.dump(out, f, indent=1, ensure_ascii=False, sort_keys=True)
        f.write('\n')
    print(f'{len(boards)} boards -> {dst}')


if __name__ == '__main__':
    main(*sys.argv[1:3])

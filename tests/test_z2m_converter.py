"""Zigbee2MQTT external converter generated from the board table."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from custom_components.ripple_presence import boards  # noqa: E402
from custom_components.ripple_presence.z2m import converter  # noqa: E402

HERE = os.path.dirname(__file__)


class ConverterTests(unittest.TestCase):
    def setUp(self):
        self.rows = boards.Boards(tempfile.mkdtemp()).all()['boards']

    def test_config_string_names_endpoints(self):
        d = converter.device('ptjcjise;TS0002-IND-T;LD4i;SC3u;RC2;SB7u;RB4;M;', ['TS0002-OLD'], 'Indual')
        self.assertEqual(d['zb_models'], ['TS0002-IND-T', 'TS0002-OLD'])
        self.assertEqual(d['switchNames'], ['switch_left', 'switch_right'])
        self.assertEqual(d['relayNames'], ['relay_left', 'relay_right'])
        self.assertTrue(d['has_dedicated_net_led'])
        self.assertFalse(d['has_battery_cluster'])

    def test_one_definition_per_model(self):
        devs = converter.devices(self.rows)
        models = [m for d in devs for m in d['zb_models']]
        self.assertEqual(len(models), len(set(models)))
        flashable = {r['config_str'].split(';')[1] for r in self.rows if r['flashable']}
        self.assertEqual(flashable - set(models), set())

    def test_tested_board_claims_shared_model(self):
        devs = converter.devices(self.rows)
        owner = next(d for d in devs if 'TS0002-IND-T' in d['zb_models'])
        self.assertEqual(owner['description'], 'Indual MT-2G-Z 2-gang touch switch')

    def test_render_is_stable_and_carries_ripple(self):
        src, sha = converter.render(self.rows)
        self.assertEqual(converter.render(self.rows), (src, sha))
        self.assertIn('deviceAddCustomCluster("rippleSense", rippleCluster)', src)
        self.assertIn('module.exports = definitions;', src)

    @unittest.skipUnless(shutil.which('node') and os.environ.get('ZHC_DIR'), 'node or ZHC_DIR missing')
    def test_node_against_herdsman_converters(self):
        src, _ = converter.render(self.rows)
        path = os.path.join(tempfile.mkdtemp(), 'ripple.cjs')
        with open(path, 'w') as f:
            f.write(src)
        res = subprocess.run(['node', os.path.join(HERE, 'z2m_converter.mjs'), path],
                             capture_output=True, text=True, check=False, timeout=120)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)


if __name__ == '__main__':
    unittest.main()

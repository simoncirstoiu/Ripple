"""Board table: bundled boards.json, the user's file over it, matching by what ZHA reports."""
import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from custom_components.ripple_presence import boards  # noqa: E402


class BoardTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.b = boards.Boards(self.dir)

    def write_user(self, data):
        os.makedirs(os.path.join(self.dir, 'ripple'), exist_ok=True)
        path = os.path.join(self.dir, 'ripple', 'boards.json')
        with open(path, 'w') as f:
            json.dump({'boards': data}, f)
        t = time.time() + len(data) + 1
        os.utime(path, (t, t))

    def test_bundled_table_supported_chip_valid(self):
        rows = self.b.all()['boards']
        self.assertGreater(len(rows), 100)
        for r in rows:
            self.assertEqual(r['mcu'], 'TLSR8258', r['key'])
            boards.check_config(r['config_str'])
        self.assertEqual(self.b.all()['errors'], [])

    def test_stock_names_match_before_flash(self):
        m = self.b.match('_TZ3000_ptjcjise', 'TS0002')
        self.assertEqual([x['key'] for x in m], ['SWITCH_INDUAL_TOUCH_TS0002'])
        self.assertEqual(m[0]['how'], 'stock')
        self.assertEqual(m[0]['summary']['switches'], 2)
        self.assertEqual(m[0]['summary']['relays'], 2)

    def test_config_names_match_after_flash(self):
        m = self.b.match('ptjcjise', 'TS0002-IND-T')
        self.assertEqual([(x['key'], x['how']) for x in m], [('SWITCH_INDUAL_TOUCH_TS0002', 'flashed')])

    def test_tested_boards_match_before_and_after_flash(self):
        for stock, flashed, key, relays in (
                (('_TZ3000_0t4zjtia', 'TS0001'), ('0t4zjtia', 'TS0001-0T4-T'), 'SWITCH_TUYA_0T4ZJTIA_TS0001', 1),
                (('_TZ3000_ptjcjise', 'TS0002'), ('ptjcjise', 'TS0002-IND-T'), 'SWITCH_INDUAL_TOUCH_TS0002', 2),
                (('_TZ3000_jfh4mdia', 'TS0003'), ('jfh4mdia', 'TS0003-BSD-T'), 'SWITCH_BSEED_JFH4MDIA_TS0003', 3)):
            for names, how in ((stock, 'stock'), (flashed, 'flashed')):
                m = self.b.match(*names)
                self.assertEqual([(x['key'], x['how']) for x in m], [(key, how)])
                self.assertTrue(m[0]['tested'] and m[0]['flashable'])
                self.assertEqual(m[0]['summary']['relays'], relays)

    def test_tested_board_listed_first(self):
        self.write_user({'A_FIRST_UNTESTED': {'config_str': 'x;TS0003-X;SC3u;RC2;M;', 'device_type': 'router',
                                              'stock_manufacturer_name': '_TZ3000_jfh4mdia', 'stock_model_name': 'TS0003'}})
        self.assertEqual([x['key'] for x in self.b.match('_TZ3000_jfh4mdia', 'TS0003')],
                         ['SWITCH_BSEED_JFH4MDIA_TS0003', 'A_FIRST_UNTESTED'])

    def test_same_stock_names_match_both_boards(self):
        self.assertGreater(len(self.b.match('_TZ3210_imaccztn', 'TS0004')), 1)

    def test_only_router_boards_are_flashable(self):
        rows = {r['key']: r for r in self.b.all()['boards']}
        self.assertTrue(rows['SWITCH_INDUAL_TOUCH_TS0002']['flashable'])
        ends = [r for r in rows.values() if r.get('device_type') == 'end_device']
        self.assertTrue(ends)
        for r in ends:
            self.assertFalse(r['flashable'], r['key'])
            self.assertIn('router', r['not_flashable'])
        self.assertEqual(boards.flashable({}), (False, 'device_type missing'))

    def test_unknown_device_matches_nothing(self):
        self.assertEqual(self.b.match('_TZ3000_nothing', 'TS9999'), [])

    def test_user_file_applies_without_restart(self):
        self.assertEqual(self.b.match('_TZ9999_newboard', 'TS0001'), [])
        self.write_user({
            'MY_NEW_BOARD': {'human_name': 'New 1-gang', 'mcu': 'TLSR8258', 'stock_manufacturer_name': '_TZ9999_newboard',
                             'stock_model_name': 'TS0001', 'config_str': 'newboard;TS0001-NEW;SC2u;RC3;M;'},
            'SWITCH_INDUAL_TOUCH_TS0002': None,
        })
        m = self.b.match('_TZ9999_newboard', 'TS0001')
        self.assertEqual([x['key'] for x in m], ['MY_NEW_BOARD'])
        self.assertTrue(m[0]['user'])
        self.assertEqual(self.b.match('_TZ3000_ptjcjise', 'TS0002'), [])

    def test_bad_user_rows_reported_skipped(self):
        self.write_user({'BAD': {'stock_manufacturer_name': 'x', 'stock_model_name': 'y', 'config_str': 'no-semicolon'},
                         'LONG': {'config_str': 'a;b;' + 'SC2u;' * 30}})
        out = self.b.all()
        self.assertEqual(len(out['errors']), 2)
        self.assertNotIn('BAD', [r['key'] for r in out['boards']])

    def test_broken_user_file_keeps_bundled_table(self):
        os.makedirs(os.path.join(self.dir, 'ripple'))
        with open(os.path.join(self.dir, 'ripple', 'boards.json'), 'w') as f:
            f.write('{not json')
        out = self.b.all()
        self.assertEqual(len(out['errors']), 1)
        self.assertGreater(len(out['boards']), 100)


if __name__ == '__main__':
    unittest.main()

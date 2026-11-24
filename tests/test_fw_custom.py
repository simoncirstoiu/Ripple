import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from custom_components.ripple_presence.websocket import _fw_how  # noqa: E402


class FwCustomHow(unittest.TestCase):
    def test_blank_device_gets_config_only(self):
        self.assertEqual(_fw_how({'boards': [{'how': 'blank'}, {'how': 'blank'}]}), 'blank')

    def test_stock_device_flashed_permit_join(self):
        self.assertEqual(_fw_how({'boards': [{'how': 'stock'}, {'how': 'flashed'}]}), 'stock')

    def test_ripple_device_is_reflashed(self):
        self.assertEqual(_fw_how({'boards': [{'how': 'flashed'}]}), 'flashed')

    def test_unmatched_stock_device_is_converted(self):
        self.assertEqual(_fw_how({'boards': [], 'manufacturer': '_TZ3000_new', 'model': 'TS0003'}), 'stock')

    def test_unmatched_ripple_device_is_reflashed(self):
        d = {'boards': [], 'manufacturer': 'abc', 'model': 'TS0003-ABC-T', 'ripple': True}
        self.assertEqual(_fw_how(d), 'flashed')

    def test_unmatched_blank_device_gets_config_only(self):
        self.assertEqual(_fw_how({'boards': [], 'manufacturer': 'unknown', 'model': 'TS0012-CUSTOM'}), 'blank')


if __name__ == '__main__':
    unittest.main()

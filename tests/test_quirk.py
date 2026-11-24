"""The quirk as a file: Ripple writes ripple_quirks.py into ZHA's custom_quirks_path and never touches ZHA."""
import asyncio
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from custom_components.ripple_presence import quirk  # noqa: E402


def fake_hass(path):
    async def job(f, *a):
        return f(*a)
    return SimpleNamespace(async_add_executor_job=job, path=path)


class QuirkFileTests(unittest.TestCase):
    def run_install(self, path, version='9.9.9'):
        old = quirk._custom_quirks_path

        async def cqp(hass):
            return hass.path
        quirk._custom_quirks_path = cqp
        try:
            return asyncio.run(quirk.async_install(fake_hass(path), version))
        finally:
            quirk._custom_quirks_path = old

    def test_writes_file_only_on_change(self):
        d = tempfile.mkdtemp()
        r1 = self.run_install(d)
        f = os.path.join(d, quirk.QUIRK_FILE)
        self.assertTrue(r1.changed and r1.error is None and os.path.exists(f))
        body = open(f).read()
        self.assertIn('Ripple 9.9.9', body)
        self.assertTrue(body.rstrip().endswith('_builder.add_to_registry()'))
        self.assertIn(open(quirk.SOURCE).read(), body)
        self.assertFalse(self.run_install(d).changed)
        self.assertTrue(self.run_install(d, '9.9.10').changed)

    def test_no_custom_quirks_path_reported(self):
        r = self.run_install(None)
        self.assertEqual(r.error, 'no_custom_quirks_path')

    def test_another_quirk_file_same_models(self):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, 'switch_quirk.py'), 'w') as f:
            f.write('CONFIGS = ["ptjcjise;TS0002-IND-T;"]\n')
        with open(os.path.join(d, 'other.py'), 'w') as f:
            f.write('# unrelated\n')
        r = self.run_install(d)
        self.assertEqual(r.duplicates, [os.path.join(d, 'switch_quirk.py')])

    def test_models_come_from_the_configs(self):
        m = quirk.models()
        self.assertIn(('ptjcjise', 'TS0002-IND-T'), m)
        self.assertIn(('jfh4mdia', 'TS0003-BSD-T'), m)
        self.assertNotIn('custom_components.ripple_presence.zha_quirk', sys.modules)

    def test_models_not_read_disk_after_import(self):
        """models() is called from the event loop for every device: the file is read once, at import."""
        from pathlib import Path
        from unittest.mock import patch
        with patch.object(Path, 'read_text', side_effect=AssertionError('read in the event loop')):
            m = quirk.models()
        self.assertIn(('ptjcjise', 'TS0002-IND-T'), m)

    def test_the_written_file_compiles(self):
        compile(quirk.render('1'), quirk.QUIRK_FILE, 'exec')


    def test_v5_switches_keep_occupancy_reports(self):
        src = open(os.path.join(os.path.dirname(quirk.SOURCE), 'zha_quirk.py')).read()
        v5 = src[src.index('.replaces(RippleSenseCluster'):src.index('out.append(_quirk(config).firmware_version_filter(max_version')]
        self.assertIn('.adds(OccupancySensing, endpoint_id=1)', v5)
        self.assertIn('.prevent_default_entity_creation(endpoint_id=1, cluster_id=OccupancySensing.cluster_id)', v5)


if __name__ == '__main__':
    unittest.main()

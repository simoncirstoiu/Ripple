import asyncio
import os
import sys
import unittest
from types import SimpleNamespace

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, '..'))

from custom_components.ripple_presence import v5  # noqa: E402
from custom_components.ripple_presence.hacore import sense_info, zcl_write  # noqa: E402


def dev(manuf, quirked, api=True, fw=None):
    attrs = {v5.A_ZONE_STATE: None, **({v5.A_HOST_API: None} if api else {})} if quirked else {}
    cmds = {v5.CMD_SOURCES: None} if quirked else {}
    cl = SimpleNamespace(attributes=attrs, server_commands=cmds)
    ep = SimpleNamespace(in_clusters={v5.CLUSTER: cl}, out_clusters={})
    ota = SimpleNamespace(out_clusters={0x0019: {0x0002: fw}}) if fw else SimpleNamespace()
    return SimpleNamespace(manufacturer_id=manuf, endpoints={0: SimpleNamespace(), v5.ENDPOINT: ep, **({2: ota} if fw else {})})


class SenseInfoTests(unittest.TestCase):
    def test_foreign_fc57_not_unquirked_ripple(self):
        for manuf in (0x117C, 0x1286, None):
            self.assertEqual(sense_info(dev(manuf, False))[2], False)

    def test_ripple_no_quirk_is_flagged(self):
        has, _, unquirked = sense_info(dev(v5.MANUF, False))
        self.assertEqual((has, unquirked), (False, True))

    def test_ripple_with_quirk_is_sensing(self):
        has, _, unquirked = sense_info(dev(v5.MANUF, True))
        self.assertEqual((has, unquirked), (True, False))

    def test_502_under_quirk_no_host_api_flagged(self):
        self.assertEqual(sense_info(dev(v5.MANUF, True, api=False, fw=v5.MIN_FW)), (True, v5.MIN_FW, True))
        self.assertEqual(sense_info(dev(v5.MANUF, True, api=False, fw=0x1103339A))[2], False)


class WriteRecordTests(unittest.TestCase):
    """zigpy answers a write with one record per attribute; none at all is not a success."""

    def run_write(self, res):
        class Cl:
            async def write_attributes(self, attrs, **kw):
                return res
        return asyncio.run(zcl_write(Cl(), v5.A_HOST_API, 2, v5.MANUF))

    def test_records(self):
        ok = SimpleNamespace(status=0, attrid=v5.A_HOST_API)
        bad = SimpleNamespace(status=0x87, attrid=v5.A_HOST_API)
        self.assertEqual(self.run_write([[ok]]), 0)
        self.assertEqual(self.run_write([[bad]]), 0x87)
        self.assertIsNone(self.run_write([[]]))
        self.assertIsNone(self.run_write([]))
        self.assertIsNone(self.run_write(None))


if __name__ == '__main__':
    unittest.main()


class UpdateInfoTests(unittest.TestCase):
    def test_progress_from_update_attributes(self):
        from custom_components.ripple_presence.hacore import update_info
        st = lambda attrs: SimpleNamespace(entity_id='update.x', state='on', attributes=attrs)
        self.assertEqual(update_info(st({'in_progress': True, 'update_percentage': 22.81}))['percentage'], 22.81)
        self.assertEqual(update_info(st({'in_progress': 40}))['percentage'], 40)
        u = update_info(st({'in_progress': False, 'installed_version': 'a', 'latest_version': 'b'}))
        self.assertEqual((u['in_progress'], u['percentage'], u['installed'], u['latest']), (False, None, 'a', 'b'))
        self.assertIsNone(update_info(None))

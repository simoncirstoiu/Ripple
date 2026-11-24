import binascii
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from custom_components.ripple_presence import flasher  # noqa: E402


def fake_bin(size=1000):
    return bytes((i * 7) & 0xFF for i in range(size))


class FlasherFiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bundled = os.path.join(self.tmp.name, 'bundled')
        os.makedirs(self.bundled)
        self.files = flasher.FirmwareFiles(self.tmp.name, bundled_dir=self.bundled)

    def tearDown(self):
        self.tmp.cleanup()

    def test_version_from_name(self):
        self.assertEqual(flasher.bin_version('Ripple-v5.0.5.bin'), (5, 0, 5))
        self.assertIsNone(flasher.bin_version('Ripple-1-v5.0.5.bin'))
        self.assertIsNone(flasher.bin_version('Ripple-v5.0.5.zigbee'))

    def test_latest_is_highest_version(self):
        for n in ('Ripple-v5.0.5.bin', 'Ripple-v5.0.10.bin', 'Ripple-v4.9.9.bin', 'other.bin'):
            self.files.save(n, fake_bin()) if flasher.bin_version(n) else None
        self.assertEqual(self.files.latest()['name'], 'Ripple-v5.0.10.bin')
        self.assertEqual(len(self.files.binaries()), 3)

    def test_bundled_binary_is_used(self):
        with open(os.path.join(self.bundled, 'Ripple-v5.0.5.bin'), 'wb') as f:
            f.write(fake_bin())
        b = self.files.latest()
        self.assertEqual((b['name'], b['source']), ('Ripple-v5.0.5.bin', 'bundled'))
        self.files.image('Ripple-v5.0.5.bin', 0x1141, 47149)
        self.assertTrue(os.listdir(self.files.cache))

    def test_user_binary_wins(self):
        with open(os.path.join(self.bundled, 'Ripple-v5.0.5.bin'), 'wb') as f:
            f.write(fake_bin())
        self.files.save('Ripple-v5.0.5.bin', fake_bin(2000))
        self.assertEqual(self.files.latest()['source'], 'user')
        self.assertEqual(len(self.files.binaries()), 1)
        self.files.save('Ripple-v5.0.4.bin', fake_bin())
        self.assertEqual(self.files.latest()['version'], '5.0.5')

    def test_replaced_binary_is_not_served_from_cache(self):
        self.files.save('Ripple-v5.0.5.bin', fake_bin(1000))
        a, _ = self.files.image('Ripple-v5.0.5.bin', 0x1141, 47149)
        self.files.save('Ripple-v5.0.5.bin', fake_bin(2000))
        b, cached = self.files.image('Ripple-v5.0.5.bin', 0x1141, 47149)
        self.assertFalse(cached)
        self.assertNotEqual(a, b)

    def test_integration_ships_a_binary(self):
        names = os.listdir(flasher.BUNDLED_DIR)
        self.assertTrue(any(flasher.bin_version(n) for n in names), names)

    def test_bad_name_refused(self):
        with self.assertRaises(ValueError):
            self.files.save('firmware.bin', fake_bin())

    def test_prepare_bin_adds_length_magic_crc(self):
        img = flasher.prepare_bin(fake_bin(1000))
        self.assertEqual(len(img) % 16, 4)
        self.assertEqual(img[6:8], flasher.TELINK_OTA_MAGIC)
        self.assertEqual(int.from_bytes(img[0x18:0x1C], 'little'), len(img))
        crc = binascii.crc32(img[:-4]) ^ 0xFFFFFFFF
        self.assertEqual(int.from_bytes(img[-4:], 'little'), crc)
        self.assertEqual(flasher.prepare_bin(img), img)

    def test_ota_header_matches_device(self):
        ota = flasher.make_ota(fake_bin(), 0x1002, 54179)
        magic, _, hlen, _, manuf, itype, ver, _, _, total = flasher.OTA_HDR.unpack_from(ota)
        self.assertEqual((magic, hlen, manuf, itype, ver), (0x0BEEF11E, 56, 0x1002, 54179, 0xFFFFFFFF))
        self.assertEqual(total, len(ota))

    def test_image_is_cached(self):
        self.files.save('Ripple-v5.0.5.bin', fake_bin())
        a, cached_a = self.files.image('Ripple-v5.0.5.bin', 0x1141, 47149)
        b, cached_b = self.files.image('Ripple-v5.0.5.bin', 0x1141, 47149)
        self.assertEqual((cached_a, cached_b), (False, True))
        self.assertEqual(a, b)
        c, cached_c = self.files.image('Ripple-v5.0.5.bin', 0x1002, 54179)
        self.assertFalse(cached_c)
        self.assertNotEqual(a[:20], c[:20])

    def test_zigpy_parses_the_image(self):
        try:
            from zigpy.ota.image import parse_ota_image
        except ImportError:
            self.skipTest('zigpy not installed')
        ota = flasher.make_ota(fake_bin(), 0x1141, 47149)
        img, rest = parse_ota_image(ota)
        self.assertEqual(rest, b'')
        self.assertEqual((img.header.manufacturer_id, img.header.image_type), (0x1141, 47149))


class Dev:
    def __init__(self, model):
        self.model = model


class FlasherRebuild(unittest.IsolatedAsyncioTestCase):
    def make(self, after, reinterview=True, fail=False):
        devs = {'a': Dev('TS0012-CUSTOM')}
        calls = []

        async def reinterview_fn(ieee):
            calls.append(ieee)
            if fail:
                raise RuntimeError('no answer')
            devs[ieee] = Dev(after)

        f = flasher.Flasher(None, devs.get, None, None, None, reinterview=reinterview_fn if reinterview else None)
        return f, calls

    def setUp(self):
        self.poll = flasher.POLL_S
        flasher.POLL_S = 0

    def tearDown(self):
        flasher.POLL_S = self.poll

    async def test_new_model_after_reinterview(self):
        f, calls = self.make('TS0002-IND-T')
        await f._rebuild('a', 'TS0002-IND-T')
        self.assertEqual(calls, ['a'])

    async def test_retries_then_fails_with_hint(self):
        f, calls = self.make('TS0012-CUSTOM')
        with self.assertRaises(flasher.FlashError) as e:
            await f._rebuild('a', 'TS0002-IND-T')
        self.assertEqual(len(calls), flasher.REINTERVIEW_TRIES)
        self.assertIn('Reconfigure', str(e.exception))

    async def test_reinterview_error_is_reported(self):
        f, _ = self.make('x', fail=True)
        with self.assertRaises(flasher.FlashError) as e:
            await f._rebuild('a', 'TS0002-IND-T')
        self.assertIn('no answer', str(e.exception))

    async def test_without_reinterview(self):
        f, _ = self.make('x', reinterview=False)
        with self.assertRaises(flasher.FlashError):
            await f._rebuild('a', 'TS0002-IND-T')


if __name__ == '__main__':
    unittest.main()

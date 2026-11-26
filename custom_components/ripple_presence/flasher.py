"""Firmware install: the universal Ripple binary, an OTA image made on the spot for the device, then the board config."""
from __future__ import annotations

import asyncio
import binascii
import logging
import os
import re
import struct
import time
from types import SimpleNamespace

from .boards import check_config, flashable

_LOGGER = logging.getLogger(__name__)

ZIGBEE_OTA_MAGIC = 0x0BEEF11E
TELINK_OTA_MAGIC = b'\x5d\x02'
OTA_HDR = struct.Struct('<I5HIH32sI')
SUB_HDR = struct.Struct('<HI')
HEADER_STRING = b'Telink OTA Image'
FILE_VERSION = 0xFFFFFFFF
MAX_IMAGE_TYPE = 0xFFBF  # higher values are ZCL wildcards / security credentials
BIN_RE = re.compile(r'^Ripple-v(\d+)\.(\d+)\.(\d+)\.bin$')
FW_DIR = ('ripple', 'firmware')
CACHE_SUBDIR = 'cache'
BUNDLED_DIR = os.path.join(os.path.dirname(__file__), 'firmware')
BASIC = 0x0000
OTA = 0x0019
ATTR_MODEL = 0x0005
ATTR_CONFIG = 0xff00
LONG_STRING = 0x44
QUERY_WAIT_S = 90
REJOIN_MAX_S = 30 * 60
PERMIT_EVERY_S = 20
PERMIT_DURATION_S = 60
ANSWER_WAIT_S = 10 * 60
POLL_S = 5
REINTERVIEW_TRIES = 3
QUERY_READ_S = 20


def bin_version(name):
    """(5, 0, 5) from 'Ripple-v5.0.5.bin', None for any other name."""
    m = BIN_RE.match(name)
    return tuple(int(x) for x in m.groups()) if m else None


def prepare_bin(data):
    """The Telink part of make_ota.py: pad to 16, length, magic and CRC, unless the binary already has them."""
    data = bytes(data)
    if data[6:8] == TELINK_OTA_MAGIC:
        return data
    pad = 16 - len(data) % 16
    if pad < 16:
        data += b'\xff' * pad
    img = bytearray(data)
    img[0x18:0x1C] = (len(img) + 4).to_bytes(4, 'little')
    img[6:8] = TELINK_OTA_MAGIC
    img += (binascii.crc32(img) ^ 0xFFFFFFFF).to_bytes(4, 'little')
    return bytes(img)


def make_ota(data, manufacturer_id, image_type, file_version=FILE_VERSION):
    """Zigbee OTA file: the header the device asked for (its manufacturer and image type) around the binary."""
    img = prepare_bin(data)
    total = OTA_HDR.size + SUB_HDR.size + len(img)
    hdr = OTA_HDR.pack(ZIGBEE_OTA_MAGIC, 0x100, 56, 0, manufacturer_id, image_type, file_version, 2,
                       HEADER_STRING.ljust(32, b'\x00'), total)
    return hdr + SUB_HDR.pack(0, len(img)) + img


class FirmwareFiles:
    """Universal binaries: the one shipped with the integration, plus the user's in <config>/ripple/firmware.
    The user's file wins over a bundled one with the same version.
    Blocking: call from an executor."""

    def __init__(self, config_dir, bundled_dir=BUNDLED_DIR):
        self.dir = os.path.join(config_dir, *FW_DIR)
        self.bundled_dir = bundled_dir
        self.cache = os.path.join(self.dir, CACHE_SUBDIR)

    @staticmethod
    def _list(folder):
        try:
            names = os.listdir(folder)
        except OSError:
            return []
        return [n for n in names if bin_version(n)]

    def binaries(self):
        found = {}
        for folder, source in ((self.bundled_dir, 'bundled'), (self.dir, 'user')):
            for n in self._list(folder):
                found[bin_version(n)] = {'name': n, 'version': '.'.join(map(str, bin_version(n))), 'source': source,
                                         'path': os.path.join(folder, n)}
        return [found[v] for v in sorted(found, reverse=True)]

    def latest(self):
        b = self.binaries()
        return b[0] if b else None

    def _path(self, name):
        for b in self.binaries():
            if b['name'] == name:
                return b['path']
        raise FileNotFoundError(name)

    def save(self, name, data):
        if not bin_version(name):
            raise ValueError(f'{name}: name must be Ripple-v<x.y.z>.bin')
        os.makedirs(self.dir, exist_ok=True)
        tmp = os.path.join(self.dir, f'.{name}.part')
        with open(tmp, 'wb') as f:
            f.write(data)
        os.replace(tmp, os.path.join(self.dir, name))

    def image(self, name, manufacturer_id, image_type):
        """The OTA image for this binary and this device header, built once and then read from the cache.
        The cache key holds the binary's CRC, so a replaced file never reuses an old image."""
        with open(self._path(name), 'rb') as f:
            data = f.read()
        path = os.path.join(self.cache, f'{name[:-4]}-{binascii.crc32(data):08x}-{manufacturer_id:04x}-{image_type:04x}.zigbee')
        try:
            with open(path, 'rb') as f:
                return f.read(), True
        except OSError:
            pass
        ota = make_ota(data, manufacturer_id, image_type)
        os.makedirs(self.cache, exist_ok=True)
        tmp = path + '.part'
        with open(tmp, 'wb') as f:
            f.write(ota)
        os.replace(tmp, path)
        return ota, False


class FlashError(Exception):
    pass


class Flasher:
    """One install at a time (parallel OTAs have blocked the stick); the others wait in a queue."""

    stack_name = 'ZHA'
    rebuild_hint = 'press Reconfigure on the device page in ZHA'

    def __init__(self, hass, zigpy_device, files, boards, zb, notify=None, reinterview=None):
        self.hass = hass
        self._dev = zigpy_device
        self._reinterview = reinterview
        self.files = files
        self.boards = boards
        self.zb = zb
        self.notify = notify or (lambda: None)
        self.jobs = {}
        self._lock = asyncio.Lock()
        self._tasks = {}

    def view(self):
        return {ieee: dict(j) for ieee, j in self.jobs.items()}

    def _set(self, ieee, **kw):
        self.jobs[ieee] = {**self.jobs.get(ieee, {}), **kw, 'ts': time.time()}
        self.notify()

    def check(self, ieee, board):
        """Raises FlashError if Ripple must not install on this device with this board."""
        if not self.zb.allow_writes:
            raise FlashError('writes are off in the Ripple settings')
        if ieee.lower() in self.zb.protected:
            raise FlashError(f'{ieee} is in protected_devices')
        ok, why = flashable(board)
        if not ok:
            raise FlashError(why)
        check_config(board.get('config_str', ''))

    def start(self, ieee, board):
        ieee = ieee.lower()
        self.check(ieee, board)
        t = self._tasks.get(ieee)
        if t and not t.done():
            raise FlashError(f'{ieee}: an install is already running')
        self._set(ieee, state='queued', board=board['key'], progress=None, error=None, started=time.time())
        self._tasks[ieee] = self.hass.async_create_background_task(self._run(ieee, board), f'ripple_flash_{ieee}')

    def cancel_all(self):
        for t in self._tasks.values():
            t.cancel()

    async def _run(self, ieee, board):
        try:
            async with self._lock:
                await self._install(ieee, board)
            self._set(ieee, state='done', progress=100, error=None)
        except asyncio.CancelledError:
            self._set(ieee, state='error', error='cancelled')
            raise
        except Exception as e:  # noqa: BLE001
            _LOGGER.warning('Ripple firmware install on %s failed: %s', ieee, e)
            self._set(ieee, state='error', error=str(e) or type(e).__name__)

    def _ota_cluster(self, dev):
        for ep_id, ep in dev.endpoints.items():
            if ep_id == 0:
                continue
            for clusters in (ep.out_clusters, ep.in_clusters):
                if OTA in clusters:
                    return clusters[OTA]
        raise FlashError('the device has no OTA cluster')

    def _query(self, dev):
        for ep_id, ep in dev.endpoints.items():
            if ep_id == 0:
                continue
            for clusters in (ep.out_clusters, ep.in_clusters):
                c = clusters.get(OTA)
                if c is not None and getattr(c, 'last_query_cmd', None) is not None:
                    return c.last_query_cmd
        return None

    async def _ask_query(self, ieee):
        """The device's own manufacturer code and image type, from its last OTA query, else asked for now."""
        dev = self._dev(ieee)
        q = self._query(dev)
        if q is not None:
            return q
        from zigpy.zcl.clusters.general import Ota
        await self._ota_cluster(dev).image_notify(payload_type=Ota.ImageNotifyCommand.PayloadType.QueryJitter,
                                                  query_jitter=100)
        end = time.monotonic() + QUERY_WAIT_S
        while time.monotonic() < end:
            await asyncio.sleep(1)
            q = self._query(self._dev(ieee))
            if q is not None:
                return q
        raise FlashError('the device did not ask for an OTA image')

    async def _install(self, ieee, board):
        self._board = board
        if board.get('how') != 'blank':
            await self._flash(ieee, permit=board.get('how') == 'stock')
        self._set(ieee, state='configuring')
        await self._write_config(ieee, board['config_str'])
        self._set(ieee, state='verifying')
        model = board['config_str'].split(';')[1]
        await self._wait_model(ieee, model)
        self._set(ieee, state='rebuilding')
        await self._rebuild(ieee, model)

    async def _flash(self, ieee, permit):
        self._set(ieee, state='preparing')
        fw = await self.hass.async_add_executor_job(self.files.latest)
        if fw is None:
            raise FlashError(f'no Ripple-v<x.y.z>.bin in the integration or in {self.files.dir}')
        q = await self._ask_query(ieee)
        data, cached = await self.hass.async_add_executor_job(self.files.image, fw['name'], q.manufacturer_code,
                                                              q.image_type)
        _LOGGER.info('Ripple firmware %s for %s: manufacturer 0x%04x, image type 0x%04x (%s)', fw['version'], ieee,
                     q.manufacturer_code, q.image_type, 'cache' if cached else 'built')
        self._set(ieee, state='flashing', progress=0, version=fw['version'])
        await self._ota(ieee, data)
        self._set(ieee, state='rejoining', progress=None)
        await self._wait_answer(ieee, permit=permit)

    async def _ota(self, ieee, data):
        from zigpy.ota import OtaImageWithMetadata
        from zigpy.ota.image import parse_ota_image
        from zigpy.ota.providers import BaseOtaImageMetadata
        from zigpy.zcl import foundation
        image, _ = parse_ota_image(data)
        h = image.header
        meta = BaseOtaImageMetadata(file_version=h.file_version, manufacturer_id=h.manufacturer_id,
                                    image_type=h.image_type, file_size=len(data), source='Ripple')

        def progress(current, total, pct):
            self._set(ieee, progress=round(pct, 1))

        status = await self._dev(ieee).update_firmware(OtaImageWithMetadata(metadata=meta, firmware=image),
                                                       progress_callback=progress, force=True)
        if status != foundation.Status.SUCCESS:
            raise FlashError(f'OTA ended with {status!r}')

    async def _read_model(self, ieee):
        try:
            dev = self._dev(ieee)
            basic = dev.endpoints[1].in_clusters[BASIC]
            ok, _ = await asyncio.wait_for(basic.read_attributes([ATTR_MODEL], allow_cache=False), 15)
            return ok.get(ATTR_MODEL)
        except Exception:  # noqa: BLE001
            return None

    async def _permit(self):
        try:
            await self.hass.services.async_call('zha', 'permit', {'duration': PERMIT_DURATION_S}, blocking=True)
        except Exception as e:  # noqa: BLE001
            _LOGGER.warning('Ripple: permit join failed: %s', e)

    async def _wait_answer(self, ieee, permit):
        """After the OTA the device reboots; a converted one rejoins, so permit-join stays open until it answers."""
        end = time.monotonic() + (REJOIN_MAX_S if permit else ANSWER_WAIT_S)
        next_permit = 0
        while time.monotonic() < end:
            if permit and time.monotonic() >= next_permit:
                await self._permit()
                next_permit = time.monotonic() + PERMIT_EVERY_S
            if await self._read_model(ieee) is not None:
                return
            await asyncio.sleep(POLL_S)
        raise FlashError('the device did not come back after the OTA')

    async def _write_config(self, ieee, config_str):
        from zigpy import types as t
        from zigpy.zcl import foundation
        basic = self._dev(ieee).endpoints[1].in_clusters[BASIC]
        attr = foundation.Attribute(ATTR_CONFIG, foundation.TypeValue(LONG_STRING, t.LongCharacterString(config_str)))
        try:
            rsp = await asyncio.wait_for(basic.write_attributes_raw([attr]), 30)
        except (asyncio.TimeoutError, TimeoutError):
            # The device reboots right after saving; the model check below is the real proof.
            _LOGGER.info('Ripple: no answer to the config write on %s, checking the model', ieee)
            return
        recs = getattr(rsp, 'status_records', None)
        if recs is None:
            recs = [rsp] if hasattr(rsp, 'status') else []
        bad = [r for r in recs if getattr(r, 'status', foundation.Status.SUCCESS) != foundation.Status.SUCCESS]
        if bad:
            raise FlashError(f'writing the board config failed: {bad[0].status!r}')

    async def _rebuild(self, ieee, model):
        """The new config changes the endpoints; the Zigbee integration only sees them after a re-interview."""
        hint = self.rebuild_hint
        if self._reinterview is None:
            raise FlashError(f'the device runs the new config, but {self.stack_name} cannot re-read it here: {hint}')
        last = None
        for _ in range(REINTERVIEW_TRIES):
            try:
                await self._reinterview(ieee)
            except Exception as e:  # noqa: BLE001
                last = e
                _LOGGER.info('Ripple: re-interview of %s failed: %s', ieee, e)
            if self._shown_model(ieee) == model:
                return
            await asyncio.sleep(POLL_S)
        why = f' ({last})' if last else ''
        raise FlashError(f'the device runs the new config, but {self.stack_name} still shows the old one{why}: {hint}')

    def _shown_model(self, ieee):
        return getattr(self._dev(ieee), 'model', None)

    async def _wait_model(self, ieee, model):
        """The firmware saves the config and reboots; done when the device reports the board's model."""
        end = time.monotonic() + ANSWER_WAIT_S
        seen = None
        while time.monotonic() < end:
            await asyncio.sleep(POLL_S)
            seen = await self._read_model(ieee)
            if seen == model:
                return
        raise FlashError(f'after the config the device reports model {seen!r}, not {model!r}')


class Z2MFlasher(Flasher):
    """The same install through Zigbee2MQTT: its OTA takes the image as hex, reads and writes go through
    the generic converters, so stock devices work too."""

    stack_name = 'Zigbee2MQTT'
    rebuild_hint = 'press Interview on the device page in Zigbee2MQTT'

    def __init__(self, hass, core, files, boards, zb, notify=None):
        super().__init__(hass, None, files, boards, zb, notify=notify, reinterview=core.reinterview)
        self.core = core

    def _shown_model(self, ieee):
        return self.core.shown_model(ieee)

    async def _ask_query(self, ieee):
        """The OTA client attributes of the device; for a stock board the table's ids if the device does not say."""
        try:
            got = await self.core.plain_read(ieee, 'genOta', ['manufacturerId', 'imageTypeId'],
                                             options={'direction': 1}, timeout=QUERY_READ_S)
        except Exception as e:  # noqa: BLE001
            _LOGGER.info('Ripple: reading the OTA ids of %s failed: %s', ieee, e)
            got = {}
        manuf, itype = got.get('manufacturerId'), got.get('imageTypeId')
        # Some stock firmwares answer the wildcard 0xFFFF; Zigbee2MQTT refuses an image type above 0xFFBF.
        if isinstance(manuf, int) and isinstance(itype, int) and 0 <= manuf < 0xFFFF and 0 <= itype <= MAX_IMAGE_TYPE:
            return SimpleNamespace(manufacturer_code=manuf, image_type=itype)
        if got:
            _LOGGER.info('Ripple: %s reports OTA ids %s / %s, not usable', ieee, manuf, itype)
        b = getattr(self, '_board', None) or {}
        if b.get('how') == 'stock' and isinstance(b.get('stock_manufacturer_id'), int) \
                and isinstance(b.get('stock_image_type'), int):
            return SimpleNamespace(manufacturer_code=b['stock_manufacturer_id'], image_type=b['stock_image_type'])
        raise FlashError('the device did not report a valid OTA manufacturer code and image type')

    async def _ota(self, ieee, data):
        try:
            await self.core.ota_install(ieee, data, progress=lambda pct: self._set(ieee, progress=round(pct, 1)))
        except asyncio.TimeoutError as e:
            raise FlashError('Zigbee2MQTT did not finish the OTA in time') from e
        except Exception as e:  # noqa: BLE001
            raise FlashError(f'OTA failed: {e}') from e

    async def _read_model(self, ieee):
        try:
            got = await self.core.plain_read(ieee, 'genBasic', ['modelId'], timeout=QUERY_READ_S)
        except Exception:  # noqa: BLE001
            return None
        return got.get('modelId')

    async def _permit(self):
        try:
            await self.core.permit_join(PERMIT_DURATION_S)
        except Exception as e:  # noqa: BLE001
            _LOGGER.warning('Ripple: permit join failed: %s', e)

    async def _write_config(self, ieee, config_str):
        # Zigbee2MQTT does not report the write; the model check after it is the proof.
        await self.core.plain_write(ieee, 'genBasic', ATTR_CONFIG, config_str, LONG_STRING)

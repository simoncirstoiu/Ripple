"""Attribute transport: cluster 0xfc57 (manufacturer 0x1141) and Occupancy 0x0406 on endpoint 1, and the single guarded write path."""
import asyncio
import logging
import time

from . import v5
from .attrmap import encode_check

log = logging.getLogger('ripple.zigbee')
BACKOFF_MIN_S, BACKOFF_MAX_S = 15, 900
# host_api counts 600 s on the device; a batch of commands within this window declares it once
API_BATCH_S = 60
_BUSY_HINTS = ('DELIVERY', 'ROUTE', 'NO_ACK', 'TIMEOUT', 'TIMED OUT', 'NOT_JOINED', 'NETWORK_BUSY')


class ZigbeeError(Exception):
    pass


class WritesDisabled(ZigbeeError):
    pass


class Protected(ZigbeeError):
    pass


class NotRipple(ZigbeeError):
    """The device is not a Ripple v5 device, so Ripple never reads or writes its sensing clusters."""


class Unsupported(ZigbeeError):
    pass


class Outdated(ZigbeeError):
    """The device speaks another sensing API than this integration: update the firmware or the integration first."""


class DeviceError(ZigbeeError):
    pass


class Refused(DeviceError):
    """The device answered with a ZCL status other than success."""

    def __init__(self, what, status):
        self.status = status
        self.code = v5.status_name(status)
        super().__init__(f'{what}: {v5.status_text(status)} (0x{status:02x})')


class Busy(DeviceError):
    """No answer at the network level (route, delivery, timeout); the device is backed off."""


def _is_busy(e):
    if isinstance(e, (asyncio.TimeoutError, TimeoutError)) or 'Delivery' in type(e).__name__:
        return True
    return any(h in str(e).upper() for h in _BUSY_HINTS)


def _wrap(e):
    return (Busy if _is_busy(e) else DeviceError)(str(e) or type(e).__name__)


class Zigbee:
    def __init__(self, core, allow_writes=False, protected=(), spacing_s=0.15, is_v5=None):
        self.core = core
        self.allow_writes = bool(allow_writes)
        self.protected = {p.strip().lower() for p in protected if p and p.strip()}
        self.spacing_s = spacing_s
        self.is_v5 = is_v5 or (lambda ieee: False)
        self.outdated = lambda ieee: None
        self._api_at = {}
        self.has_zha = False
        self._lock = asyncio.Lock()
        self.stats = {'reads': 0, 'writes': 0, 'commands': 0, 'errors': 0}
        self.backoff = {}
        self.write_log = []

    async def detect(self):
        up = getattr(self.core, 'backend_up', None)
        if up:
            self.has_zha = bool(await up())
            return {'zha': self.has_zha}
        services = await self.core.call({'type': 'get_services'})
        self.has_zha = bool(services.get('zha'))
        return {'zha': self.has_zha}

    def _log(self, ieee, op, detail):
        self.write_log.append({'ieee': ieee, op: detail, 'ok': True})
        del self.write_log[:-200]
        log.info('%s %s %s', op, ieee, detail)

    def _check_device(self, ieee):
        if ieee.lower() in self.protected:
            raise Protected(f'{ieee} is in protected_devices')

    def check_target(self, ieee):
        """Every sensing request goes through here: protected and non-v5 devices are never contacted."""
        self._check_device(ieee)
        if not self.is_v5(ieee):
            raise NotRipple(f'{ieee} is not a Ripple v5 device')

    async def _serial(self, coro_fn):
        async with self._lock:
            try:
                return await coro_fn()
            finally:
                if self.spacing_s:
                    await asyncio.sleep(self.spacing_s)

    def _check_backoff(self, ieee):
        b = self.backoff.get(ieee)
        if b and time.monotonic() < b[0]:
            raise Busy(f'{ieee} did not answer, next read in {int(b[0] - time.monotonic()) + 1} s')

    def _backoff_fail(self, ieee, err):
        delay = min(BACKOFF_MAX_S, self.backoff[ieee][1] * 2) if ieee in self.backoff else BACKOFF_MIN_S
        self.backoff[ieee] = (time.monotonic() + delay, delay)
        log.debug('%s unreachable (%s), backing off %d s', ieee, err, delay)

    async def read_attr(self, ieee, attr, typ, cluster=v5.CLUSTER):
        """One attribute; 0xfc57 with manufacturer 0x1141, Occupancy without; octet strings without length byte."""
        self.check_target(ieee)
        self._check_backoff(ieee)
        return await self._serial(lambda: self._read_guarded(ieee, attr, cluster))

    async def _read_guarded(self, ieee, attr, cluster):
        """Runs under the network-wide lock; a device in backoff gets no traffic."""
        self._check_backoff(ieee)
        try:
            v = await self._read_once(ieee, attr, cluster)
        except Busy as e:
            self._backoff_fail(ieee, e)
            raise
        except DeviceError:
            self.backoff.pop(ieee, None)
            raise
        self.backoff.pop(ieee, None)
        return v

    async def _read_once(self, ieee, attr, cluster):
        self.stats['reads'] += 1
        manuf = v5.MANUF if cluster == v5.CLUSTER else None
        try:
            ok, fail = await self.core.zcl_read(ieee, cluster, [attr], manuf)
            if attr in ok and ok[attr] is not None:
                return ok[attr]
            st = fail.get(attr)
            if st == 0x86:
                raise Unsupported(f'0x{attr:04x} is not supported by the device')
            if st is not None:
                raise Refused(f'read 0x{attr:04x}', st)
            raise DeviceError(f'no answer for 0x{attr:04x}')
        except ZigbeeError:
            self.stats['errors'] += 1
            raise
        except Exception as e:
            self.stats['errors'] += 1
            raise _wrap(e) from e

    def _check_write(self, ieee):
        self.check_target(ieee)
        if not self.allow_writes:
            raise WritesDisabled('writes are off in the Ripple settings')
        why = self.outdated(ieee)
        if why:
            raise Outdated(why)

    async def write_attr(self, ieee, attr, typ, value):
        """The only attribute path that changes a device; refused unless allow_writes is on."""
        self.check_target(ieee)
        value = encode_check(typ, value)
        self._check_write(ieee)

        async def go():
            self.stats['writes'] += 1
            try:
                status = await self.core.zcl_write(ieee, v5.CLUSTER, attr, value, v5.MANUF)
            except Exception as e:
                self.stats['errors'] += 1
                raise _wrap(e) from e
            self._check_status(ieee, f'write 0x{attr:04x}', {'attr': attr, 'value': value}, status)
        log.info('write %s 0x%04x = %s', ieee, attr, value)
        return await self._serial(go)

    def _check_status(self, ieee, what, rec, status):
        """None means zigpy returned no record for the write: counted as a failure, never as success."""
        self.write_log.append({'ieee': ieee, **rec, 'ok': status == 0})
        del self.write_log[:-200]
        if status is None:
            self.stats['errors'] += 1
            raise DeviceError(f'{what}: the device confirmed nothing')
        if status:
            self.stats['errors'] += 1
            raise Refused(what, status)

    async def _declare_api(self, ieee):
        """Writes host_api = SENSE_API and reads it back once; the device then takes commands for 600 s."""
        self.stats['writes'] += 1
        try:
            status = await self.core.zcl_write(ieee, v5.CLUSTER, v5.A_HOST_API, v5.SENSE_API, v5.MANUF)
        except Exception as e:
            self.stats['errors'] += 1
            raise _wrap(e) from e
        self._check_status(ieee, 'write host_api 0xff4a', {'attr': v5.A_HOST_API, 'value': v5.SENSE_API}, status)
        self.stats['reads'] += 1
        try:
            ok, fail = await self.core.zcl_read(ieee, v5.CLUSTER, [v5.A_HOST_API], v5.MANUF)
        except Exception as e:
            self.stats['errors'] += 1
            raise _wrap(e) from e
        if ok.get(v5.A_HOST_API) != v5.SENSE_API:
            self.stats['errors'] += 1
            raise DeviceError(f'host_api reads {ok.get(v5.A_HOST_API, fail.get(v5.A_HOST_API))!r} '
                              f'after writing {v5.SENSE_API}: the device does not take commands from this integration')
        self._api_at[ieee] = time.monotonic()

    async def command(self, ieee, cmd, payload):
        """Manufacturer command on 0xfc57, after host_api; 0x7E rewrites host_api and retries once."""
        self._check_write(ieee)
        payload = bytes(payload)

        async def send():
            self.stats['commands'] += 1
            try:
                return await self.core.zcl_command(ieee, v5.CLUSTER, cmd, payload, v5.MANUF)
            except Exception as e:
                self.stats['errors'] += 1
                raise _wrap(e) from e

        async def go():
            if time.monotonic() - self._api_at.get(ieee, -API_BATCH_S) >= API_BATCH_S:
                await self._declare_api(ieee)
            status = await send()
            if status == 0x7E:
                log.info('command %s 0x%02x not authorized, declaring host_api again', ieee, cmd)
                self._api_at.pop(ieee, None)
                await self._declare_api(ieee)
                status = await send()
            if status == 0x7E:
                self._api_at.pop(ieee, None)
            self._check_status(ieee, f'command 0x{cmd:02x}', {'command': cmd, 'payload': payload.hex()}, status)
        log.info('command %s 0x%02x %s', ieee, cmd, payload.hex())
        return await self._serial(go)

    async def read_binds(self, ieee):
        """Binding table through ZDO Mgmt_Bind_req (read-only)."""
        self._check_device(ieee)

        async def go():
            self.stats['reads'] += 1
            return await self.core.zdo_binds(ieee)
        return await self._serial(go)

    def _check_bind(self, src, src_ep, dst, cluster, dst_ep=0):
        for v, n in ((src_ep, 'source endpoint'), (cluster, 'cluster'), (dst_ep, 'target endpoint')):
            if not isinstance(v, int) or not 0 <= v <= 0xFFFF:
                raise ValueError(f'{n} is required')
        if not src or not dst:
            raise ValueError('source and target devices are required')
        self._check_device(src)
        self._check_device(dst)
        if not self.allow_writes:
            raise WritesDisabled('allow_writes is off in the Ripple settings')

    async def bind(self, src, src_ep, dst, dst_ep, cluster):
        """One binding, one endpoint and one cluster; never the bulk device bind."""
        self._check_bind(src, src_ep, dst, cluster, dst_ep)

        async def go():
            self.stats['writes'] += 1
            await self.core.zdo_bind(src, src_ep, cluster, dst, dst_ep)
            self._log(src, 'bind', f'ep{src_ep} 0x{cluster:04x} -> {dst} ep{dst_ep}')
        return await self._serial(go)

    async def unbind(self, src, src_ep, dst, cluster):
        """Removes the bindings of one source endpoint and cluster to one device, nothing else."""
        self._check_bind(src, src_ep, dst, cluster)
        from .bindings import parse_binds
        table = parse_binds(await self.read_binds(src))
        eps = sorted({b['dst_ep'] for b in table
                      if b['src_ep'] == src_ep and b['cluster'] == cluster and b['dst_ieee'] == dst.lower()})

        async def go():
            for ep in eps:
                self.stats['writes'] += 1
                await self.core.zdo_unbind(src, src_ep, cluster, dst, ep)
                self._log(src, 'unbind', f'ep{src_ep} 0x{cluster:04x} -> {dst} ep{ep}')
        await self._serial(go)
        return eps

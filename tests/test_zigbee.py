import asyncio
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from custom_components.ripple_presence import v5  # noqa: E402
from custom_components.ripple_presence import zigbee as zb  # noqa: E402
from custom_components.ripple_presence.attrmap import U8, U16, OCT  # noqa: E402

IEEE = '00:11:22:33:44:55:66:77'
OTHER = '00:11:22:33:44:55:66:88'


class FakeCore:
    """Records every request; zcl_* answer like zigpy (values without length byte, failures as status)."""

    def __init__(self, values=None, write_status=0, cmd_status=0, fail=None):
        self.sent = []
        self.binds = {'replies': []}
        self.values = values or {}
        self.write_status, self.cmd_status = write_status, cmd_status
        self.fail = fail

    async def call(self, msg):
        self.sent.append(msg)
        t = msg['type']
        if t == 'get_services':
            return {'zha': {'permit': {}}}
        raise AssertionError(t)

    async def zdo_binds(self, ieee):
        self.sent.append({'type': 'zdo_binds', 'ieee': ieee})
        return self.binds

    async def zdo_bind(self, ieee, src_ep, cluster, dst, dst_ep):
        self.sent.append({'type': 'zdo_bind', 'ieee': ieee, 'src_ep': src_ep, 'cluster': cluster, 'dst': dst, 'dst_ep': dst_ep})

    async def zdo_unbind(self, ieee, src_ep, cluster, dst, dst_ep):
        self.sent.append({'type': 'zdo_unbind', 'ieee': ieee, 'src_ep': src_ep, 'cluster': cluster, 'dst': dst, 'dst_ep': dst_ep})

    async def zcl_read(self, ieee, cluster, attrs, manuf):
        self.sent.append({'type': 'read', 'ieee': ieee, 'cluster': cluster, 'attrs': attrs, 'manuf': manuf})
        if self.fail:
            raise self.fail
        ok = {a: self.values[(cluster, a)] for a in attrs if (cluster, a) in self.values}
        return ok, {a: 0x86 for a in attrs if a not in ok}

    async def zcl_write(self, ieee, cluster, attr, value, manuf):
        self.sent.append({'type': 'write', 'ieee': ieee, 'cluster': cluster, 'attr': attr, 'value': value, 'manuf': manuf})
        if self.fail:
            raise self.fail
        if attr == v5.A_HOST_API and self.write_status == 0 and not getattr(self, 'ignore_api', False):
            self.values[(cluster, attr)] = value
        return self.write_status

    async def zcl_command(self, ieee, cluster, cmd, payload, manuf):
        self.sent.append({'type': 'command', 'ieee': ieee, 'cluster': cluster, 'cmd': cmd, 'payload': payload, 'manuf': manuf})
        if isinstance(self.cmd_status, list):
            return self.cmd_status.pop(0)
        return self.cmd_status


def run(c):
    return asyncio.run(c)


def z_for(core, **kw):
    kw.setdefault('is_v5', lambda ieee: ieee == IEEE)
    return zb.Zigbee(core, spacing_s=0, **kw)


def radio(core):
    return [m for m in core.sent if m['type'] in ('read', 'write', 'command')]


class GuardTests(unittest.TestCase):
    def test_write_refused_when_disabled(self):
        core = FakeCore()
        z = z_for(core, allow_writes=False)
        with self.assertRaises(zb.WritesDisabled):
            run(z.write_attr(IEEE, v5.A_DETECT, U8, 1))
        with self.assertRaises(zb.WritesDisabled):
            run(z.command(IEEE, v5.CMD_SOURCES, b''))
        self.assertEqual(radio(core), [])

    def test_write_refused_for_protected_device(self):
        core = FakeCore()
        z = z_for(core, allow_writes=True, protected=[IEEE])
        with self.assertRaises(zb.Protected):
            run(z.write_attr(IEEE, v5.A_DETECT, U8, 1))
        self.assertEqual(radio(core), [])

    def test_read_refused_for_protected_device(self):
        core = FakeCore(values={(v5.CLUSTER, v5.A_DETECT): 1})
        z = z_for(core, protected=[IEEE])
        with self.assertRaises(zb.Protected):
            run(z.read_attr(IEEE, v5.A_DETECT, U8))
        self.assertEqual(radio(core), [])

    def test_non_v5_device_is_never_contacted(self):
        core = FakeCore(values={(v5.CLUSTER, v5.A_DETECT): 1})
        z = z_for(core, allow_writes=True)
        for call in (z.read_attr(OTHER, v5.A_DETECT, U8), z.write_attr(OTHER, v5.A_DETECT, U8, 1),
                     z.command(OTHER, v5.CMD_TUNE, bytes(40))):
            with self.assertRaises(zb.NotRipple):
                run(call)
        self.assertEqual(radio(core), [])

    def test_write_out_of_range_refused(self):
        core = FakeCore()
        z = z_for(core, allow_writes=True)
        with self.assertRaises(ValueError):
            run(z.write_attr(IEEE, v5.A_BEACON_HZ, U8, 300))
        self.assertEqual(radio(core), [])


class TransportTests(unittest.TestCase):
    def test_sensing_read_carries_manufacturer(self):
        core = FakeCore(values={(v5.CLUSTER, v5.A_NODE_DIAG): b'\x01\x02'})
        self.assertEqual(run(z_for(core).read_attr(IEEE, v5.A_NODE_DIAG, OCT)), b'\x01\x02')
        self.assertEqual(radio(core)[0]['manuf'], v5.MANUF)

    def test_occupancy_read_no_manufacturer_code(self):
        core = FakeCore(values={(v5.OCCUPANCY, v5.A_OCCUPANCY): 1})
        self.assertEqual(run(z_for(core).read_attr(IEEE, v5.A_OCCUPANCY, 0x18, v5.OCCUPANCY)), 1)
        self.assertEqual((radio(core)[0]['cluster'], radio(core)[0]['manuf']), (v5.OCCUPANCY, None))

    def test_unsupported_attribute(self):
        with self.assertRaises(zb.Unsupported):
            run(z_for(FakeCore()).read_attr(IEEE, 0xff4e, U8))

    def test_write_status_is_refused(self):
        core = FakeCore(write_status=0x87)
        z = z_for(core, allow_writes=True)
        with self.assertRaises(zb.Refused) as cm:
            run(z.write_attr(IEEE, v5.A_CALIBRATE, U16, 1))
        self.assertEqual(cm.exception.code, 'invalid_value')
        w = radio(core)[0]
        self.assertEqual((w['cluster'], w['attr'], w['value'], w['manuf']), (v5.CLUSTER, v5.A_CALIBRATE, 1, v5.MANUF))
        self.assertFalse(z.write_log[-1]['ok'])

    def test_command_goes_cluster_manufacturer(self):
        core = FakeCore()
        z = z_for(core, allow_writes=True)
        payload = v5.encode_sources([(0x1234, 1, 70)])
        run(z.command(IEEE, v5.CMD_SOURCES, payload))
        c = radio(core)[-1]
        self.assertEqual((c['cluster'], c['cmd'], c['payload'], c['manuf']), (v5.CLUSTER, 0, payload, v5.MANUF))
        self.assertEqual(z.stats['commands'], 1)

    def test_command_not_ready(self):
        z = z_for(FakeCore(cmd_status=0x93), allow_writes=True)
        with self.assertRaises(zb.Refused) as cm:
            run(z.command(IEEE, v5.CMD_TUNE, bytes(40)))
        self.assertEqual(cm.exception.code, 'not_ready')

    def test_write_without_record_is_a_failure(self):
        core = FakeCore(write_status=None)
        z = z_for(core, allow_writes=True)
        with self.assertRaises(zb.DeviceError):
            run(z.write_attr(IEEE, v5.A_DETECT, U8, 1))
        self.assertFalse(z.write_log[-1]['ok'])


class HostApiTests(unittest.TestCase):
    """Firmware 5.0.2 takes commands only within 600 s of a host_api write."""

    def kinds(self, core):
        return [(m['type'], m.get('attr', m.get('attrs', m.get('cmd')))) for m in radio(core)]

    def test_host_api_is_read_back_before_a_batch(self):
        core = FakeCore()
        z = z_for(core, allow_writes=True)
        run(z.command(IEEE, v5.CMD_TUNE, bytes(40)))
        run(z.command(IEEE, v5.CMD_SOURCES, b''))
        self.assertEqual(self.kinds(core), [('write', v5.A_HOST_API), ('read', [v5.A_HOST_API]), ('command', v5.CMD_TUNE),
                                            ('command', v5.CMD_SOURCES)])
        w = radio(core)[0]
        self.assertEqual((w['value'], w['manuf']), (v5.SENSE_API, v5.MANUF))

    def test_not_authorized_declares_again(self):
        core = FakeCore(cmd_status=[0x7E, 0])
        z = z_for(core, allow_writes=True)
        run(z.command(IEEE, v5.CMD_SOURCES, b''))
        self.assertEqual([k for k in self.kinds(core) if k[0] != 'read'],
                         [('write', v5.A_HOST_API), ('command', 0), ('write', v5.A_HOST_API), ('command', 0)])

    def test_not_authorized_twice_is_refused(self):
        core = FakeCore(cmd_status=[0x7E, 0x7E])
        z = z_for(core, allow_writes=True)
        with self.assertRaises(zb.Refused) as cm:
            run(z.command(IEEE, v5.CMD_SOURCES, b''))
        self.assertEqual(cm.exception.code, 'not_authorized')
        self.assertEqual(sum(1 for m in radio(core) if m['type'] == 'command'), 2)
        self.assertNotIn(IEEE, z._api_at)

    def test_host_api_write_without_record_sends_nothing(self):
        core = FakeCore(write_status=None)
        z = z_for(core, allow_writes=True)
        with self.assertRaises(zb.DeviceError):
            run(z.command(IEEE, v5.CMD_SOURCES, b''))
        self.assertEqual(self.kinds(core), [('write', v5.A_HOST_API)])

    def test_host_api_not_kept_sends_no_command(self):
        core = FakeCore()
        core.ignore_api = True
        z = z_for(core, allow_writes=True)
        with self.assertRaises(zb.DeviceError):
            run(z.command(IEEE, v5.CMD_SOURCES, b''))
        self.assertNotIn('command', [m['type'] for m in radio(core)])

    def test_outdated_switch_gets_no_write_at_all(self):
        core = FakeCore()
        z = z_for(core, allow_writes=True)
        z.outdated = lambda ieee: 'update its firmware'
        for call in (z.command(IEEE, v5.CMD_SOURCES, b''), z.write_attr(IEEE, v5.A_DETECT, U8, 1)):
            with self.assertRaises(zb.Outdated):
                run(call)
        self.assertEqual(radio(core), [])

    def test_bindings_need_only_zha(self):
        core = FakeCore()
        z = z_for(core, allow_writes=True)
        self.assertEqual(run(z.detect()), {'zha': True})
        run(z.bind(IEEE, 1, OTHER, 4, 6))
        self.assertEqual(core.sent[-1]['type'], 'zdo_bind')


class BackoffTests(unittest.TestCase):
    def test_delivery_failure_backs_off_without_traffic(self):
        core = FakeCore(fail=asyncio.TimeoutError())
        z = z_for(core)
        with self.assertRaises(zb.Busy):
            run(z.read_attr(IEEE, v5.A_DETECT, U8))
        n = len(radio(core))
        with self.assertRaises(zb.Busy):
            run(z.read_attr(IEEE, v5.A_DETECT, U8))
        self.assertEqual(len(radio(core)), n)

    def test_unsupported_attribute_is_not_busy(self):
        z = z_for(FakeCore())
        with self.assertRaises(zb.Unsupported):
            run(z.read_attr(IEEE, v5.A_DETECT, U8))
        self.assertNotIn(IEEE, z.backoff)

    def test_backoff_grows_per_device_clears(self):
        core = FakeCore(fail=RuntimeError('MAC NO_ACK'), values={(v5.CLUSTER, v5.A_DETECT): 1})
        z = z_for(core)
        with self.assertRaises(zb.Busy):
            run(z.read_attr(IEEE, v5.A_DETECT, U8))
        first = z.backoff[IEEE][1]
        z.backoff[IEEE] = (time.monotonic() - 1, first)
        with self.assertRaises(zb.Busy):
            run(z.read_attr(IEEE, v5.A_DETECT, U8))
        self.assertEqual(z.backoff[IEEE][1], first * 2)
        core.fail = None
        z.backoff[IEEE] = (time.monotonic() - 1, z.backoff[IEEE][1])
        self.assertEqual(run(z.read_attr(IEEE, v5.A_DETECT, U8)), 1)
        self.assertNotIn(IEEE, z.backoff)

    def test_write_delivery_failure_is_busy(self):
        z = z_for(FakeCore(fail=asyncio.TimeoutError()), allow_writes=True)
        with self.assertRaises(zb.Busy):
            run(z.write_attr(IEEE, v5.A_DETECT, U8, 1))


class SingleFlightTests(unittest.TestCase):
    def test_one_read_in_flight_across_devices(self):
        state = {'now': 0, 'max': 0}

        class Slow(FakeCore):
            async def zcl_read(self, ieee, cluster, attrs, manuf):
                state['now'] += 1
                state['max'] = max(state['max'], state['now'])
                await asyncio.sleep(0.01)
                state['now'] -= 1
                return {attrs[0]: 1}, {}
        z = zb.Zigbee(Slow(), spacing_s=0, is_v5=lambda ieee: True)

        async def go():
            await asyncio.gather(*[z.read_attr(i, v5.A_DETECT, U8) for i in (IEEE, OTHER, IEEE)])
        run(go())
        self.assertEqual(state['max'], 1)


if __name__ == '__main__':
    unittest.main()

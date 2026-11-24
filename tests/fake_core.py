"""Fixture-backed stand-in for Home Assistant, used by the tests."""
import asyncio
import time
import random

from custom_components.ripple_presence import v5


class CoreError(Exception):
    def __init__(self, code, message):
        super().__init__(f'{code}: {message}')
        self.code = code


class FakeSwitch:
    """Firmware behaviour of one v5 switch (5.0.3, 5.0.4 or 5.0.5 by sense_api), as far as Ripple can observe it."""

    def __init__(self, st=None):
        st = st or {}
        self.detect = st.get('detect', 0)
        self.beacon_hz = st.get('beacon_hz', v5.BEACON_DEFAULT)
        self.cal_left = st.get('cal_left', 0)
        self.zone_state = st.get('zone_state', 0)
        self.sources = bytes.fromhex(st.get('sources', ''))
        self.capture = {l['nwk'] for l in self.lines()}
        api = st.get('sense_api', 3)
        self.tune = bytes.fromhex(st['tune']) if st.get('tune') else v5.encode_tune(v5.tune_defaults(api), api)
        self.calibrated = set(st.get('calibrated', []))
        self.stack_used = st.get('stack_used', 0)
        self.beacons_skipped = st.get('beacons_skipped', 0)
        self.link = st.get('link', {})
        self.raw_enabled = 0
        self.sense_api = st.get('sense_api', 3)  # the fleet runs 5.0.3; a state with sense_api 5 is 5.0.4
        self.host_api = 0
        self.host_api_until = 0.0
        self.self_tune = st.get('self_tune', 0)
        self.lines_on = st.get('lines_on')  # 5.0.5; None = from zone_state and the lines' zones

    def lines_on_now(self):
        """0xff46: bit i = line i of sources detects."""
        if self.lines_on is not None:
            return self.lines_on
        return sum(1 << i for i, l in enumerate(self.lines())
                   if self.detect and self.zone_state & l['zones'] and l['sens'] and self.votes(l))

    def lines(self):
        return v5.decode_sources(self.sources)

    def votes(self, l):
        """5.0.3 votes only on a calibrated line; 5.0.4 without a capture too."""
        return l['nwk'] in self.calibrated or v5.api_of(self.sense_api) == 5

    def node_diag(self):
        lines = self.lines()
        cal = sum(1 for l in lines if l['nwk'] in self.calibrated)
        flags = (1 if cal < len(lines) else 0) | (2 if self.cal_left else 0)
        b = bytearray(17)
        on = [i for i, l in enumerate(lines) if self.zone_state & l['zones'] and self.votes(l)]
        b[0], b[1], b[2], b[3], b[4] = len(lines), cal, self.zone_state if self.detect else 0, flags, on[0] if on else 0xFF
        b[6:8] = self.stack_used.to_bytes(2, 'little')
        b[8:10] = self.cal_left.to_bytes(2, 'little')
        b[10] = v5.TUNE_VERSION
        b[13:15] = self.beacons_skipped.to_bytes(2, 'little')
        b[16] = 0xFF
        return bytes(b)

    def link_diag(self, part):
        lines = self.lines()
        out = bytearray()
        for k in range(5):
            i = part * 5 + k
            if i >= len(lines):
                out += bytes(9)
                continue
            l = lines[i]
            x = self.link.get(f'0x{l["nwk"]:04x}', {})
            cal, vote = l['nwk'] in self.calibrated, self.votes(l)
            st = 0x20 | (0x04 if cal else 0) | (0x02 if vote and x.get('usable', True) else 0) | (0 if l['zones'] else 0x80)
            if self.zone_state & l['zones'] and vote:
                st |= 0x01
            thr, m = v5.motion_params(l['sens'], self.sense_api)
            out += bytes([x.get('level', -70) & 0xFF, x.get('rate', 50), x.get('hits', 0), st, thr, m, 0, 12,
                          (x.get('width', 1) << 4) | x.get('b_cal', 1)])
        return bytes(out)

    def read(self, attr):
        return {v5.A_BEACON_HZ: self.beacon_hz, v5.A_CALIBRATE: self.cal_left, v5.A_DETECT: self.detect,
                v5.A_ZONE_STATE: self.zone_state if self.detect else 0, v5.A_SOURCES: self.sources,
                v5.A_TUNE: self.tune, v5.A_NODE_DIAG: self.node_diag(), v5.A_LINK_A: self.link_diag(0),
                v5.A_LINK_B: self.link_diag(1), v5.A_RAW_ENABLED: self.raw_enabled,
                v5.A_SENSE_API: self.sense_api, v5.A_HOST_API: self.api(),
                **({v5.A_SELF_TUNE: self.self_tune} if v5.api_of(self.sense_api) == 5 else {}),
                **({v5.A_LINES_ON: self.lines_on_now()} if v5.has_lines_on(self.sense_api) else {})}.get(attr)

    def api(self):
        if self.host_api and time.monotonic() >= self.host_api_until:
            self.host_api = 0
        return self.host_api

    def write(self, attr, value):
        if attr == v5.A_DETECT:
            self.detect = 1 if value else 0
        elif attr == v5.A_SELF_TUNE and v5.api_of(self.sense_api) == 5:
            self.self_tune = value if value in (0, 1) else self.self_tune
        elif attr == v5.A_RAW_ENABLED:
            self.raw_enabled = 1 if value else 0
        elif attr == v5.A_HOST_API:
            self.host_api, self.host_api_until = value & 0xFF, time.monotonic() + 600
        elif attr == v5.A_BEACON_HZ:
            self.beacon_hz = 0 if not value else max(v5.BEACON_MIN, min(v5.BEACON_MAX, value))
        elif attr == v5.A_CALIBRATE:
            self.cal_left = v5.decode_tune(self.tune)['cal_s'] if value else 0
            self.capture = {l['nwk'] for l in self.lines()}
        elif attr in (v5.A_ZONE_STATE, v5.A_SOURCES, v5.A_TUNE, v5.A_NODE_DIAG, v5.A_LINK_A, v5.A_LINK_B, v5.A_SENSE_API) or (
                attr == v5.A_LINES_ON and v5.has_lines_on(self.sense_api)):
            return 0x88
        else:
            return 0x86
        return 0

    def command(self, cmd, p):
        if self.sense_api and self.api() < self.sense_api:
            return 0x7E
        if cmd == v5.CMD_SOURCES:
            if len(p) % 4:
                return 0x80
            try:
                v5.encode_sources([(l['nwk'], l['zones'], l['sens']) for l in v5.decode_sources(p)])
            except ValueError:
                return 0x87
            keep = {l['nwk'] for l in self.lines()} & {l['nwk'] for l in v5.decode_sources(p)}
            self.calibrated &= keep
            if self.lines_on is not None:  # a kept line keeps its state at its new index
                on = {l['nwk'] for i, l in enumerate(self.lines()) if self.lines_on >> i & 1}
                self.lines_on = sum(1 << i for i, l in enumerate(v5.decode_sources(p)) if l['nwk'] in on)
            self.sources = bytes(p)
            return 0
        if cmd == v5.CMD_TUNE:
            if len(p) != v5.TUNE_LEN:
                return 0x80
            t = v5.decode_tune(p)
            if t['version'] != v5.TUNE_VERSION or v5.validate_tune(t, self.sense_api):
                return 0x87
            self.tune = bytes(p)
            return 0
        if cmd == v5.CMD_LIVE:
            if len(p) < 3 or (len(p) - 3) % 3:
                return 0x80
            dur = int.from_bytes(p[:2], 'little')
            nwks = [l['nwk'] for l in self.lines()]
            want = [(int.from_bytes(p[i:i + 2], 'little'), p[i + 2]) for i in range(3, len(p), 3)]
            if any(n not in nwks for n, _ in want):
                return 0x87
            self.live = {'end': time.time() + dur, 'lines': {nwks.index(n): c for n, c in want}, 'seq': 0} if dur else None
            return 0
        if cmd == v5.CMD_CAPTURE:
            if len(p) % 2:
                return 0x80
            if self.cal_left:
                return 0x93
            nwks = [l['nwk'] for l in self.lines()]
            want = [int.from_bytes(p[i:i + 2], 'little') for i in range(0, len(p), 2)]
            if any(n not in nwks for n in want) or len(set(want)) != len(want) or not (want or nwks):
                return 0x87
            self.capture = set(want or nwks)
            self.cal_left = v5.decode_tune(self.tune)['cal_s']
            return 0
        return 0x81

    def live_frame(self):
        """One simulated Live frame (0xff4e data): a record per streamed line, like a beacon of each sender."""
        lv = getattr(self, 'live', None)
        if not lv or time.time() >= lv['end']:
            self.live = None
            return None
        recs = b''
        ver = {5: 3, 6: 4}.get(self.sense_api, 2)
        lines = self.lines()
        for i, cand in lv['lines'].items():
            q = lv.setdefault('q', {}).get(i, 0)
            q = max(0, min(255, q + random.randint(-40, 45))) if random.random() < 0.9 else 0
            lv['q'][i] = q
            q2 = max(0, min(255, q + (25 if cand else 0)))
            on = q >= 128
            # v4: 0x20 = the line votes in its zones; v2/v3: the gate bit
            b20 = on and i < len(lines) and lines[i]['zones'] and lines[i]['sens'] if ver >= 4 else True
            recs += bytes([i | (0x10 if on else 0) | (0x20 if b20 else 0) | 0x40 | (0x80 if cand else 0), 0, q, q2,
                           random.randint(0, 9)])
        n = len(lv['lines'])
        ms = int(time.time() * 1000) & 0xFFFFFFFF
        lv['seq'] = (lv['seq'] + 1) & 0xFF
        return bytes([ver, lv['seq'], 0, n]) + ms.to_bytes(4, 'little') + recs

    def advance(self, seconds):
        if self.cal_left:
            self.cal_left = max(0, self.cal_left - seconds)
            if not self.cal_left:
                self.calibrated |= self.capture & {l['nwk'] for l in self.lines()}


class FixtureCore:
    """Answers the calls Ripple makes from a recorded or synthetic fixture; v5 switches are simulated."""
    standalone = True

    def __init__(self, fixture, simulate=False):
        self.fx = fixture
        self.simulate = simulate
        self.connected = asyncio.Event()
        self.on_connect = []
        self.version = fixture.get('meta', {}).get('ha_version', 'fixture')
        self.last_error = None
        state = fixture.get('state', {})
        self.switches = {d['ieee']: FakeSwitch(state.get(d['ieee'])) for d in fixture.get('zha_devices', [])
                         if d.get('sense')}
        self.writes = []
        self.subs = {}
        self.unreachable = set()
        self.not_ready = set()

    def close(self):
        pass

    async def run(self):
        self.connected.set()
        for cb in self.on_connect:
            asyncio.create_task(cb())
        k = 0
        while True:
            await asyncio.sleep(0.2)
            k += 1
            if self.simulate:
                for ieee, sw in self.switches.items():
                    f = sw.live_frame() if hasattr(sw, 'live_frame') else None
                    if f:
                        self.report(ieee, v5.CLUSTER, v5.A_LIVE, f)
                if k % 15 == 0:
                    self._tick()

    def _tick(self):
        for sw in self.switches.values():
            sw.advance(3)
        capable = [i for i, sw in self.switches.items() if sw.detect and sw.lines()]
        if not capable:
            return
        ieee = random.choice(capable)
        sw = self.switches[ieee]
        on = 0 if sw.zone_state else (1 if random.random() < 0.5 else 0)
        self.report(ieee, v5.CLUSTER, v5.A_ZONE_STATE, on)
        if v5.has_lines_on(sw.sense_api):
            sw.lines_on = None
            self.report(ieee, v5.CLUSTER, v5.A_LINES_ON, sw.lines_on_now())
        self.report(ieee, v5.OCCUPANCY, v5.A_OCCUPANCY, on)

    def report(self, ieee, cluster, attr, value):
        sw = self.switches.get(ieee)
        if sw and cluster == v5.CLUSTER and attr == v5.A_ZONE_STATE:
            sw.zone_state = value
        if sw and cluster == v5.CLUSTER and attr == v5.A_LINES_ON:
            sw.lines_on = value
        for cb in list(self.subs.get(ieee, [])):
            cb(ieee, cluster, attr, value)

    def subscribe(self, ieee, cb):
        self.subs.setdefault(ieee, []).append(cb)
        return lambda: self.subs.get(ieee, []).remove(cb) if cb in self.subs.get(ieee, []) else None

    def set_nwk(self, ieee, nwk):
        next(d for d in self.fx['zha_devices'] if d['ieee'] == ieee)['nwk'] = nwk

    def _switch(self, ieee):
        if ieee in self.unreachable:
            raise asyncio.TimeoutError(f'{ieee} did not answer')
        sw = self.switches.get(ieee)
        if sw is None:
            raise CoreError('not_found', f'{ieee} has no cluster 0xfc57 on endpoint 1')
        return sw

    async def zcl_read(self, ieee, cluster, attrs, manuf):
        await asyncio.sleep(0)
        sw = self._switch(ieee)
        ok, fail = {}, {}
        for a in attrs:
            if cluster == v5.OCCUPANCY:
                v = (1 if sw.zone_state and sw.detect else 0) if a == v5.A_OCCUPANCY and manuf is None else None
            else:
                v = sw.read(a) if manuf == v5.MANUF else None
            if v is None:
                fail[a] = 0x86
            else:
                ok[a] = v
        return ok, fail

    async def zcl_write(self, ieee, cluster, attr, value, manuf):
        await asyncio.sleep(0)
        sw = self._switch(ieee)
        self.writes.append({'ieee': ieee, 'cluster': cluster, 'attr': attr, 'value': value, 'manuf': manuf})
        return sw.write(attr, value)

    async def zcl_command(self, ieee, cluster, cmd, payload, manuf):
        await asyncio.sleep(0)
        sw = self._switch(ieee)
        self.writes.append({'ieee': ieee, 'cluster': cluster, 'command': cmd, 'payload': bytes(payload), 'manuf': manuf})
        if ieee in self.not_ready:
            return 0x93
        return sw.command(cmd, bytes(payload))

    async def zdo_binds(self, ieee):
        await asyncio.sleep(0)
        if ieee in self.unreachable:
            raise asyncio.TimeoutError(f'{ieee} did not answer')
        return self.fx.get('binds', {}).get(ieee, {'replies': []})

    async def zdo_bind(self, ieee, src_ep, cluster, dst, dst_ep):
        await asyncio.sleep(0)
        self.writes.append({'zdo': 'bind', 'ieee': ieee, 'src_ep': src_ep, 'cluster': cluster, 'dst': dst, 'dst_ep': dst_ep})

    async def zdo_unbind(self, ieee, src_ep, cluster, dst, dst_ep):
        await asyncio.sleep(0)
        self.writes.append({'zdo': 'unbind', 'ieee': ieee, 'src_ep': src_ep, 'cluster': cluster, 'dst': dst, 'dst_ep': dst_ep})

    async def call(self, msg, timeout=30):
        await asyncio.sleep(0)
        t = msg['type']
        fx = self.fx
        if t == 'get_services':
            return {d: {s: {} for s in names} for d, names in fx.get('services', {}).items()}
        if t == 'zha/devices':
            if 'zha' not in fx.get('services', {}):
                raise CoreError('unknown_command', 'Unknown command.')
            return [dict(d) for d in fx.get('zha_devices', [])]
        if t == 'config/area_registry/list':
            return fx.get('areas', [])
        if t == 'config/device_registry/list':
            return fx.get('device_registry', [])
        if t == 'ripple/endpoints':
            return fx.get('endpoints', {}).get(msg['ieee'], [])
        if t == 'ripple/firmware':
            return fx.get('firmware', [])
        if t in ('subscribe_events', 'call_service'):
            return None
        raise CoreError('unknown_command', t)

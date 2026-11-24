"""Discovery, rooms, per-device settings, sync to devices, live status."""
import asyncio
import logging
import re
import time
import uuid

from . import attrmap as am
from . import v5
from .const import ROOM_OFF_DEFAULT, ROOM_OFF_MAX, TRIGGER_DEFAULT, TRIGGER_K_MAX, TRIGGER_MODES
from .history import History
from .live import Live
from .zigbee import Busy, DeviceError, Outdated, Unsupported, WritesDisabled, ZigbeeError

log = logging.getLogger('ripple.engine')
RIPPLE_MODEL = re.compile(r'^TS\d{4}-[A-Za-z0-9]+-[A-Za-z0-9]+$')


# the device refreshes node_diag and link_diag once a second
DIAG_FRESH_S = 1.1


def now():
    return time.time()


LINES_READ_S = 60  # link_diag of a quiet device is re-read this often, so a line's level and rate never go stale
S_READ_S = 600  # 5.0.4: how often sources is re-read, so s moved by the 24 h self-tuning reaches Ripple


def dev_api(d):
    """Scale and formats the device runs: 5 from firmware 5.0.4, 3 for 5.0.3 or not read yet."""
    return v5.api_of((d.get('config') or {}).get('sense_api'))


def api_state(d):
    """'ok', 'update_firmware' or 'update_integration', from SENSE_API or else from the OTA file version."""
    api = (d.get('config') or {}).get('sense_api')
    if api:
        return 'ok' if api in v5.SUPPORTED_API else 'update_integration' if api > v5.SENSE_API else 'update_firmware'
    fw = d.get('fw')
    return 'update_firmware' if fw is not None and fw < v5.MIN_FW else 'ok'


OUTDATED = {'update_firmware': 'this device runs Ripple firmware older than 5.0.3: update its firmware first, '
                               'Ripple changes nothing on it until then',
            'update_integration': 'this device runs a newer Ripple firmware than this integration knows: update the integration first, '
                            'Ripple changes nothing on it until then'}


def is_ripple_firmware(d):
    """The Ripple marker in Basic sw_build_id wins, else the detection result."""
    build = str(d.get('sw_build_id') or '').strip().lower()
    if build.startswith(am.RIPPLE_MARKER):
        return True
    return d.get('kind') == 'ripple'


def is_our_firmware(d):
    """Any build of the device firmware, older v4 builds included.
    Matches the Ripple marker, or a TS000N-XXX-T model id with Telink manufacturer code 0x1141."""
    if is_ripple_firmware(d):
        return True
    return bool(RIPPLE_MODEL.match(d.get('model') or '')) and d.get('manuf_id') in (None, v5.MANUF)


class Engine:
    def __init__(self, core, zigbee, store, opts):
        self.core, self.zb, self.store, self.opts = core, zigbee, store, opts
        self.devices = {}
        self.areas = {}
        self.status = {'zha': None, 'ripple_count': 0, 'discovered_at': None,
                       'error': None, 'probing': False}
        self.listeners = []
        self._busy = set()
        self._probe_task = None
        self._probe_again = False
        self._spawn = asyncio.create_task
        self._ready = None
        self._subs = {}
        self._snapping = set()
        self._snap_again = set()
        self._was_detecting = {}
        self._hold_timers = {}  # room id -> timer that clears the room when its off_s ends
        self._trig = {}  # room id -> {'met': threshold reached, 'off_at': when the count dropped below it}
        self.line_last = {}  # (rx, tx) -> ts of the last time the line was seen detecting
        self.live = Live(self)
        self.history = History()
        zigbee.is_v5 = lambda ieee: (self.devices.get(ieee) or {}).get('kind') == 'ripple'
        zigbee.outdated = lambda ieee: OUTDATED.get(api_state(self.devices.get(ieee) or {}))

    # ---------- lifecycle ----------

    def hold_reads(self):
        """Background reads wait for release_reads(); user actions are not held."""
        self._ready = asyncio.Event()

    def release_reads(self):
        if self._ready is not None:
            self._ready.set()

    async def _wait_ready(self):
        if self._ready is not None:
            await self._ready.wait()

    async def start(self, spawn=asyncio.create_task):
        self.core.on_connect.append(self.refresh)
        self._spawn = spawn
        spawn(self._poll_loop())
        spawn(self._reconcile_loop())

    def _changed(self):
        for cb in self.listeners:
            try:
                cb()
            except Exception:
                log.exception('listener')

    async def refresh(self, wait_probe=False):
        try:
            found = await self.zb.detect()
            self.status.update(zha=found['zha'], error=None)
        except Exception as e:
            self.status['error'] = f'Cannot reach Home Assistant: {e}'
            return
        if not self.status['zha']:
            self.devices = {}
            self.status['ripple_count'] = 0
            self._changed()
            return
        try:
            zdevs = await self.core.call({'type': 'zha/devices'})
            areas = await self.core.call({'type': 'config/area_registry/list'})
            reg = await self.core.call({'type': 'config/device_registry/list'})
        except Exception as e:
            self.status['error'] = f"{getattr(self.core, 'stack_name', 'ZHA')} did not answer: {e}"
            return
        self.areas = {a['area_id']: a['name'] for a in areas or []}
        reg = {r['id']: r for r in reg or []}
        old, new = self.devices, {}
        for z in zdevs or []:
            r = reg.get(z.get('device_reg_id')) or {}
            prev = old.get(z['ieee'], {})
            area_id = z.get('area_id') or r.get('area_id')
            new[z['ieee']] = {
                'ieee': z['ieee'], 'nwk': z.get('nwk'), 'name': z.get('user_given_name') or r.get('name_by_user') or z.get('name'),
                'model': z.get('model'), 'manufacturer': z.get('manufacturer'), 'area_id': area_id,
                'area': self.areas.get(area_id), 'available': bool(z.get('available')),
                'device_type': z.get('device_type'), 'lqi': z.get('lqi'), 'rssi': z.get('rssi'),
                'last_seen': z.get('last_seen'), 'sw_version': r.get('sw_version'), 'reg_id': z.get('device_reg_id'),
                'neighbors': [n.get('ieee') for n in z.get('neighbors') or [] if n.get('ieee')],
                'has_onoff': bool(z.get('has_onoff')), 'sense': bool(z.get('sense')), 'fw': z.get('fw'),
                'unquirked': bool(z.get('unquirked')), 'manuf_id': z.get('manuf_id'), 'update': z.get('update'),
                'kind': prev.get('kind', 'other'), 'probe': prev.get('probe'), 'profile': prev.get('profile'),
                'live': prev.get('live', {}), 'config': prev.get('config', {}), 'config_at': prev.get('config_at'),
                'error': prev.get('error'), 'sw_build_id': z.get('sw_build_id') or prev.get('sw_build_id'),
            }
        self.devices = new
        for d in new.values():
            if d['device_type'] == 'Coordinator':
                d['kind'] = 'coordinator'
            elif d['ieee'].lower() in self.zb.protected:
                d['kind'] = 'protected'
            elif d['device_type'] == 'Router' and self._is_candidate(d):
                self._probe(d)
            else:
                d['kind'] = 'other'
        self._subscribe()
        self.status['discovered_at'] = now()
        self._count()
        if wait_probe:
            await self._probe_all()
        elif self._probe_task and not self._probe_task.done():
            self._probe_again = True
        else:
            self._probe_task = self._spawn(self._probe_all())
        self._changed()

    @staticmethod
    def _is_candidate(d):
        return bool(RIPPLE_MODEL.match(d.get('model') or '') or d['sense'])

    def _subscribe(self):
        """Zone and occupancy reports of every v5 device go to _on_report."""
        want = {d['ieee'] for d in self.devices.values() if d['kind'] == 'ripple'}
        for ieee in [i for i in self._subs if i not in want]:
            self._subs.pop(ieee)[1]()
        sub = getattr(self.core, 'subscribe', None)
        if not sub:
            return
        clusters = getattr(self.core, 'clusters', lambda ieee: ())
        for ieee in want:
            key, old = clusters(ieee), self._subs.get(ieee)
            if old and len(old[0]) == len(key) and all(a is b for a, b in zip(old[0], key)):
                continue
            # ZHA can replace the zigpy clusters (rejoin, re-quirk, reload); the old ones never get a report again.
            if old:
                old[1]()
                log.info('reports of %s subscribed again: ZHA replaced its clusters', ieee)
            try:
                self._subs[ieee] = (key, sub(ieee, self._on_report))
            except Exception as e:
                self._subs.pop(ieee, None)
                log.warning('no reports from %s: %s', ieee, e)

    def stop(self):
        self.live.stop_all()
        for _, u in self._subs.values():
            u()
        self._subs.clear()

    def _count(self):
        self.status['ripple_count'] = sum(1 for d in self.devices.values() if d['kind'] == 'ripple')

    def _current(self, ieee):
        """A refresh replaces the device dicts; always work on the live one."""
        return self.devices.get(ieee)

    async def _probe_all(self):
        await self._wait_ready()
        self.status['probing'] = True
        try:
            while True:
                self._probe_again = False
                for ieee in list(self.devices):
                    d = self._current(ieee)
                    if d and d['kind'] in ('candidate', 'ripple', 'needs_firmware'):
                        self._probe(d)
                if not self._probe_again:
                    break
            await self._after_probe()
        finally:
            self.status['probing'] = False


    async def _after_probe(self):
        self._count()
        for ieee in list(self.devices):
            d = self._current(ieee)
            if not d or d['kind'] != 'ripple' or not d['available']:
                continue
            if self._needs_adoption(ieee):
                await self._adopt(d)
            elif not d['config_at']:
                await self.read_config(ieee)
        self._changed()
        if self.zb.allow_writes:
            for d in list(self.devices.values()):
                if (d['kind'] == 'ripple' and d['available'] and d['config_at'] and api_state(d) == 'ok'
                        and self.pending(d['ieee'])):
                    await self._safe_apply(d['ieee'])

    def _probe(self, d):
        """v5 detection from ZHA's memory, no radio traffic: the quirk's 0xfc57 on ep1 and OTA version >= 5.0.0.
        Builds below 5.0.3 are shown and read, but api_state keeps every write away from them."""
        fw = d.get('fw')
        if d['sense'] and fw is not None and fw >= v5.LEGACY_MIN_FW:
            d['kind'], d['profile'], d['probe'], d['error'] = 'ripple', 'v5', 'ok', None
        elif d.get('unquirked'):
            d['kind'], d['profile'], d['probe'] = 'needs_firmware', None, 'no_quirk'
        else:
            d['kind'], d['profile'], d['probe'] = 'needs_firmware', None, 'no_sensing'
        if not d['available']:
            d['probe'] = 'offline'

    def _needs_adoption(self, ieee):
        sw = self.store.switch(ieee)
        return sw is None or bool(sw.get('migrated'))

    def profile(self, ieee):
        return am.PROFILES.get((self.devices.get(ieee) or {}).get('profile') or '')

    # ---------- reading devices ----------

    async def read_config(self, ieee, groups=('status', 'derived', 'advanced')):
        d, prof = self.devices[ieee], self.profile(ieee)
        if not prof or ieee in self._busy:
            return
        self._busy.add(ieee)
        self._changed()
        misses = 0
        try:
            for g in groups:
                for a in prof[g]:
                    if a.get('field') or (a.get('min_api') and not (isinstance(d['config'].get('sense_api'), int)
                                                                    and d['config']['sense_api'] >= a['min_api'])):
                        continue
                    try:
                        v = await self.zb.read_attr(ieee, a['id'], a['type'], a['cluster'])
                        if a['key'] == 'sources' and api_state(d) == 'update_firmware':
                            v = v5.sources_from_legacy(v)
                        d['config'][a['key']] = v
                        misses = 0
                    except Unsupported:
                        continue
                    except Busy as e:
                        d['error'] = f'No answer yet, will retry: {e}'
                        return
                    except DeviceError as e:
                        if g == 'status':
                            continue
                        misses += 1
                        if misses >= 3:
                            d['error'] = f'Device stopped answering: {e}'
                            return
            d['config_at'] = now()
            d['error'] = None
            self._update_live_from_config(d)
        finally:
            self._busy.discard(ieee)
            self._changed()

    def _sync_sens_api(self, d, sw=None):
        """Keeps the stored s on the scale the device runs.
        After an update from 5.0.3 the device converts its own s, and the store does the same once."""
        sw = sw or self.store.switch(d['ieee'])
        if not sw or (d.get('config') or {}).get('sense_api') not in v5.SUPPORTED_API:
            return
        api, was = dev_api(d), sw.get('sens_api', 3)
        if api == was:
            if api == 5:
                self._follow_switch_s(d, sw)
            return
        if api == 5:
            sw['sens'] = {k: v5.s_to_api(v, was, api) for k, v in (sw.get('sens') or {}).items()}
        else:
            log.warning('%s runs 5.0.3 again: its s values are kept as they are', d['name'])
        sw['sens_api'] = api
        self.store.save()

    def _follow_switch_s(self, d, sw):
        """The device moves s itself (Calibrate, self-tuning), so a line it changed takes the device's value.
        A change made here and not sent yet is kept."""
        prof = self.profile(d['ieee'])
        lines = (prof['decoders']['sources'](d['config'].get('sources')) or []) if prof else []
        if not lines:
            return
        nwk_to_ieee = {x['nwk']: x['ieee'] for x in self.devices.values() if x.get('nwk') is not None}
        sent, changed = sw.setdefault('sens_sent', {}), False
        for l in lines:
            src = nwk_to_ieee.get(l['nwk'])
            if src not in (sw.get('sens') or {}) or not 0 <= l['sens'] <= v5.S_MAX:
                continue
            if src not in sent:
                sent[src] = l['sens']
                changed = True
            elif l['sens'] != sent[src] and sw['sens'][src] == sent[src]:
                log.info('%s: s of the line from %s moved on the device %s -> %s', d['name'], src, sent[src], l['sens'])
                sw['sens'][src] = sent[src] = l['sens']
                changed = True
        if changed:
            self.store.save()

    def _update_live_from_config(self, d):
        c, live = d['config'], d['live']
        self._sync_sens_api(d)
        if 'occupancy' in c and 'motion_at' not in live:
            self._set_motion(d, c['occupancy'] & am.ZONE_ROOM)
        if 'node_diag' in c:
            self._set_node_diag(d, c['node_diag'])
        if 'cal_left' in c:
            live['cal_left'], live['cal_left_at'] = c['cal_left'], now()
        tune = am.decode_tune(c.get('tune'))
        for a in self.profile(d['ieee'])['advanced'] if tune else []:
            c[a['key']] = am.tune_value(a, tune)
        live['read_at'] = now()

    def _set_node_diag(self, d, raw):
        live = d['live']
        live['node_diag'] = raw
        n = v5.decode_node_diag(raw)
        if n:
            live['flags'] = n['flags']
            d['config']['stack_used'] = n['stack_used']
            d['config']['beacons_skipped'] = n['beacons_skipped']
            self._set_motion(d, n['zone_state'] & am.ZONE_ROOM)

    async def _read_api(self, d):
        """SENSE_API of an outdated device; after an OTA to 5.0.3 it reads 3 and the lines are read again."""
        try:
            v = await self.zb.read_attr(d['ieee'], v5.A_SENSE_API, am.U8)
        except ZigbeeError:
            return
        was = api_state(d)
        d['config']['sense_api'] = v
        if was != 'ok' and api_state(d) == 'ok':
            await self.read_config(d['ieee'], ('derived',))
            await self._read_lines_on(d)

    async def _read_lines_on(self, d):
        """Reads the per-line state 0xff46 (firmware 5.0.5); its bits follow the order of sources."""
        if not v5.has_lines_on(d['config'].get('sense_api')):
            return
        try:
            d['config']['lines_on'] = await self.zb.read_attr(d['ieee'], v5.A_LINES_ON, am.BMP16)
        except ZigbeeError as e:
            log.info('%s: per-line state not read: %s', d['name'], e)
            return
        self._changed()

    def line_states(self, ieee):
        """{sender ieee: detecting or None} for the device's sources, {} without 0xff46.
        None while sense_api or sources are not read."""
        d = self.devices.get(ieee)
        if not d or d['kind'] != 'ripple':
            return None
        api, cfg = d['config'].get('sense_api'), d['config']
        if api not in v5.SUPPORTED_API:
            return None
        if not v5.has_lines_on(api):
            return {}
        lines = v5.decode_sources(cfg.get('sources'))
        if lines is None:
            return None
        bits = v5.lines_on_bits(cfg.get('lines_on'), len(lines))
        nwk_to_ieee = {x['nwk']: x['ieee'] for x in self.devices.values() if x.get('nwk') is not None}
        return {nwk_to_ieee[l['nwk']]: None if bits is None else bits[i]
                for i, l in enumerate(lines) if l['nwk'] in nwk_to_ieee}

    async def _adopt(self, d):
        await self.read_config(d['ieee'])
        prof, c = self.profile(d['ieee']), d['config']
        settings = prof['adopt'](c)
        if settings is None:
            return
        nwk_to_ieee = {x['nwk']: x['ieee'] for x in self.devices.values() if x.get('nwk') is not None}
        lines = [l for l in prof['decoders']['sources'](c.get('sources')) or [] if l['nwk'] in nwk_to_ieee]
        srcs = [nwk_to_ieee[l['nwk']] for l in lines]
        sens = {nwk_to_ieee[l['nwk']]: l['sens'] if 0 <= l['sens'] <= v5.S_MAX else v5.sens_default(dev_api(d)) for l in lines}
        parked = [nwk_to_ieee[l['nwk']] for l in lines if not l['zones']]
        old = self.store.switch(d['ieee'])
        if old is None:
            # a device Ripple has not seen before starts with detection and self-tuning off
            settings['detect'] = False
            if 'self_tune' in settings:
                settings['self_tune'] = False
        if old and old.get('migrated'):
            settings.update({k: v for k, v in old['settings'].items() if k != 'advanced'})
            srcs, sens, parked = old['sources'], old.get('sens', {}), old.get('parked', [])
        old_api = old.get('sens_api', 3) if old and old.get('migrated') else dev_api(d)
        sw = self.store.put_switch(d['ieee'], settings, srcs, sens, parked, old_api)
        self._sync_sens_api(d, sw)
        log.info('adopted %s: %d sources', d['name'], len(srcs))

    # ---------- desired state and writes ----------

    def lines(self, ieee):
        """(nwk, zones, s) per source; zones is the room bit, or 0 for a parked line that never votes."""
        sw = self.store.switch(ieee) or {'sources': []}
        parked = set(sw.get('parked', []))
        out = []
        for s in sw['sources']:
            x = self.devices.get(s)
            if x and x.get('nwk') is not None:
                zones = 0 if s in parked else am.ZONE_ROOM
                out.append((x['nwk'], zones, v5.check_s(sw.get('sens', {}).get(s, v5.sens_default(sw.get('sens_api'))))))
        return out

    def desired(self, ieee):
        sw, prof = self.store.switch(ieee), self.profile(ieee)
        if not sw or not prof:
            return {}
        lines = self._slot_layout(self.devices[ieee]['config'], self.lines(ieee))
        try:
            out = prof['derive'](sw['settings'], lines, self.devices[ieee]['config'])
        except ValueError as e:
            self.devices[ieee]['error'] = str(e)
            return {}
        if self.unresolved_sources(ieee):
            # a source whose NWK is not known right now would be left out of the list and erased from the device
            out.pop('sources', None)
        return out

    def unresolved_sources(self, ieee):
        sw = self.store.switch(ieee) or {'sources': []}
        return [s for s in sw['sources'] if (self.devices.get(s) or {}).get('nwk') is None]

    @staticmethod
    def _slot_layout(cfg, lines):
        """Keep each line at the position it already has on the device; new ones go after them."""
        have = [l['nwk'] for l in v5.decode_sources(cfg.get('sources')) or []]
        rank = {n: i for i, n in enumerate(have)}
        return sorted(lines, key=lambda l: rank.get(l[0], len(have)))

    def pending(self, ieee):
        d, prof = self.devices.get(ieee), self.profile(ieee)
        if not d or not prof:
            return []
        out = []
        for k, want in self.desired(ieee).items():
            have = d['config'].get(k)
            if have is not None and have != want:
                a = am.attr_by_key(prof, k)
                out.append({'key': k, 'id': a['id'], 'type': a['type'], 'cmd': a.get('cmd'), 'want': want,
                            'have': have})
        out.sort(key=lambda p: (p['cmd'] is None, p['cmd'] or 0, p['id']))
        return out

    async def apply_switch(self, ieee):
        if not self.zb.allow_writes:
            raise WritesDisabled('writes are off in the Ripple settings')
        d = self.devices[ieee]
        if not d['available']:
            raise DeviceError(f'{d["name"]} is offline')
        if OUTDATED.get(api_state(d)):
            raise Outdated(f'{d["name"]}: {OUTDATED[api_state(d)]}')
        if dev_api(d) == 5 and any(p['key'] == 'sources' for p in self.pending(ieee)):
            await self._read_s(d)  # never write back an s the device moved since the last read
        for p in self.pending(ieee):
            if p['cmd'] is not None:
                await self.zb.command(ieee, p['cmd'], p['want'])
            else:
                await self.zb.write_attr(ieee, p['id'], p['type'], p['want'])
            d['config'][p['key']] = p['want']
            if p['key'] == 'sources' and v5.has_lines_on(d['config'].get('sense_api')):
                d['config']['lines_on'] = None  # its bits follow sources: read again below
            sw = self.store.switch(ieee)
            if p['key'] == 'sources' and sw is not None and dev_api(d) == 5:
                nwk_to_ieee = {x['nwk']: x['ieee'] for x in self.devices.values() if x.get('nwk') is not None}
                sw['sens_sent'] = {nwk_to_ieee[l['nwk']]: l['sens'] for l in v5.decode_sources(p['want'])
                                   if l['nwk'] in nwk_to_ieee}
                self.store.save()
        if v5.has_lines_on(d['config'].get('sense_api')) and d['config'].get('lines_on', 0) is None:
            await self._read_lines_on(d)
        self._update_live_from_config(d)
        self._arm_room_holds()
        self._changed()
        return True

    async def _safe_apply(self, ieee):
        try:
            await self.apply_switch(ieee)
        except ZigbeeError as e:
            self.devices[ieee]['error'] = str(e)
            log.warning('apply %s: %s', ieee, e)

    async def _after_change(self, ieee):
        self._changed()
        written = False
        if self.zb.allow_writes and self.devices[ieee]['available']:
            await self.apply_switch(ieee)
            written = True
        self._changed()
        return {'written': written, 'pending': len(self.pending(ieee))}

    def _switch_or_fail(self, ieee):
        sw = self.store.switch(ieee)
        if sw is None or not self.profile(ieee):
            raise KeyError(f'{ieee} is not a Ripple device or was not read yet')
        return sw

    def validate_settings(self, ieee, changes):
        prof = self.profile(ieee)
        out = {}
        for k, v in changes.items():
            if k == 'off_s':
                out[k] = _int_in(v, 1, 255, k)
            elif k == 'beacon_hz':
                out[k] = v5.check_beacon_hz(_int_in(v, 0, v5.BEACON_MAX, k))
            elif k == 'detect':
                out[k] = bool(v)
            elif k == 'self_tune':
                if dev_api(self.devices[ieee]) != 5:
                    raise ValueError('the 24 h self-tuning needs Ripple firmware 5.0.4 on this device')
                out[k] = bool(v)
            elif k == 'cal_s':
                out[k] = _int_in(v, prof['cal_min'], prof['cal_max'], k)
            elif k == 'advanced':
                adv = {}
                for ak, av in (v or {}).items():
                    a = next((x for x in prof['advanced'] if x['key'] == ak), None)
                    if a is None:
                        raise ValueError(f'{ak} is not an advanced setting')
                    fv = float(av)
                    if not a['min'] <= fv <= a['max'] or abs(fv * a['scale'] - round(fv * a['scale'])) > 1e-6:
                        raise ValueError(f'{ak} must be between {a["min"]} and {a["max"]} in steps of {a["step"]}')
                    adv[ak] = fv
                out[k] = adv
            else:
                raise ValueError(f'unknown setting {k}')
        sw = self.store.switch(ieee) or {'settings': {}}
        base = am.decode_tune(self.devices[ieee]['config'].get('tune'))
        if base and ({'off_s', 'cal_s', 'advanced'} & set(out)):
            merged = {**sw['settings'], **{k: v for k, v in out.items() if k != 'advanced'},
                      'advanced': {**(sw['settings'].get('advanced') or {}), **out.get('advanced', {})}}
            am.tune_with(base, merged, self.devices[ieee]['config'].get('sense_api'))
        return out

    async def set_switch_settings(self, ieee, changes):
        sw = self._switch_or_fail(ieee)
        ch = self.validate_settings(ieee, changes)
        if 'advanced' in ch:
            sw['settings'].setdefault('advanced', {}).update(ch.pop('advanced'))
        sw['settings'].update(ch)
        self.store.save()
        return await self._after_change(ieee)

    async def reset_advanced(self, ieee):
        sw, prof = self._switch_or_fail(ieee), self.profile(ieee)
        tdef = v5.tune_defaults(dev_api(self.devices[ieee]))
        sw['settings']['advanced'] = {a['key']: tdef.get(a['field'], a['default'] * a['scale']) / a['scale']
                                      for a in prof['advanced']}
        self.store.save()
        return await self._after_change(ieee)

    async def add_source(self, ieee, src):
        sw, prof = self._switch_or_fail(ieee), self.profile(ieee)
        if src == ieee or src not in self.devices:
            raise ValueError('unknown source device')
        if src not in sw['sources']:
            if len(sw['sources']) >= prof['include_slots']:
                raise ValueError(f'a device listens to at most {prof["include_slots"]} devices')
            sw['sources'].append(src)
            sw.setdefault('sens', {})[src] = v5.sens_default(dev_api(self.devices[ieee]))
            self.store.save()
        return await self._after_change(ieee)

    async def set_sources(self, ieee, sources, sens=None, parked=None):
        """Lines of a device: the sources in order, each with a sensitivity s 0-100 and parked or voting."""
        sw, prof = self._switch_or_fail(ieee), self.profile(ieee)
        sources = list(dict.fromkeys(s for s in sources if s != ieee))
        if any(s not in self.devices for s in sources):
            raise ValueError('unknown source device')
        if len(sources) > prof['include_slots']:
            raise ValueError(f'a device listens to at most {prof["include_slots"]} devices')
        steps = {**sw.get('sens', {}), **{k: _int_in(v, 0, v5.S_MAX, 'sensitivity') for k, v in (sens or {}).items()}}
        sw['sources'] = sources
        sw['sens'] = {s: steps.get(s, v5.sens_default(dev_api(self.devices[ieee]))) for s in sources}
        park = set(sw.get('parked', []) if parked is None else parked)
        sw['parked'] = [s for s in sources if s in park]
        self.store.save()
        # Live is sent again only when the lines on the device change: a save of the same value writes nothing
        moved = any(p['key'] == 'sources' for p in self.pending(ieee))
        res = await self._after_change(ieee)
        if res.get('written') and moved:
            await self.live.after_sources(ieee)
        return res

    async def save_line(self, rx, tx, sens):
        """Saves the sensitivity of one line; the other lines of the receiver keep their saved values."""
        sw = self._switch_or_fail(rx)
        if tx not in sw['sources']:
            raise KeyError(f'{tx} is not a line of {rx}')
        return await self.set_sources(rx, sw['sources'], {tx: sens}, None)

    async def add_line(self, rx, tx):
        sw = self._switch_or_fail(rx)
        if tx in sw['sources']:
            raise ValueError('this line already exists')
        return await self.set_sources(rx, sw['sources'] + [tx], None, None)

    async def remove_line(self, rx, tx):
        sw = self._switch_or_fail(rx)
        return await self.set_sources(rx, [s for s in sw['sources'] if s != tx], None, None)

    async def remove_source(self, ieee, src):
        sw = self._switch_or_fail(ieee)
        sw['sources'] = [s for s in sw['sources'] if s != src]
        sw.get('sens', {}).pop(src, None)
        sw['parked'] = [s for s in sw.get('parked', []) if s != src]
        self.store.save()
        return await self._after_change(ieee)

    async def calibrate(self, members, seconds, txs=None):
        """Sends tune.cal_s = seconds with command 0x01, then starts the capture of every line with 0xff41 = 1.
        With txs (senders of lines of the single receiver in members), command 0x03 captures only those lines."""
        written = []
        for ieee in members:
            prof = self.profile(ieee)
            if not prof:
                continue
            if not prof['cal_min'] <= seconds <= prof['cal_max']:
                raise ValueError(f'calibration must last {prof["cal_min"]} to {prof["cal_max"]} s')
        capture = None if txs is None else v5.encode_capture([(self.devices.get(t) or {}).get('nwk') for t in txs])
        if not self.zb.allow_writes:
            raise WritesDisabled('writes are off in the Ripple settings')
        for ieee in members:
            d, prof = self.devices[ieee], self.profile(ieee)
            if not prof or not d['available']:
                continue
            sw = self.store.switch(ieee)
            if sw is not None and sw['settings'].get('cal_s') != seconds:
                sw['settings']['cal_s'] = seconds
                self.store.save()
            if d['config'].get('tune') is None:
                await self.read_config(ieee, ('derived',))
            if am.decode_tune(d['config'].get('tune')) is None:
                raise DeviceError(f'{d["name"]}: the tune of the device could not be read')
            await self.apply_switch(ieee)
            if capture is None:
                await self.zb.write_attr(ieee, prof['calibrate'], am.U16, 1)
            else:
                await self.zb.command(ieee, v5.CMD_CAPTURE, capture)
            d['live']['flags'] = (d['live'].get('flags') or 0) | 2
            d['live']['cal_left'] = seconds
            d['live']['cal_started'] = d['live']['cal_left_at'] = now()
            d['live']['cal_txs'] = None if txs is None else list(txs)
            written.append(ieee)
        self._changed()
        return {'written': written}

    async def calibrate_line(self, rx, tx, seconds):
        """Captures one line only (command 0x03): the other lines of the receiver keep their calibration and detect."""
        sw = self._switch_or_fail(rx)
        if tx not in sw['sources']:
            raise KeyError(f'{tx} is not a line of {rx}')
        return await self.calibrate([rx], int(seconds), [tx])

    async def calibrate_room(self, rid, seconds):
        seconds = int(seconds)
        room = self.room(rid)
        res = await self.calibrate(room['members'], seconds)
        self.store.room_meta(rid)['cal_s'] = seconds
        self.store.save()
        return res

    # ---------- rooms ----------

    def ripple_devices(self):
        return [d for d in self.devices.values() if d['kind'] == 'ripple']

    def rooms(self):
        out = []
        by_area = {}
        for d in self.ripple_devices():
            if d['area_id']:
                by_area.setdefault(d['area_id'], []).append(d['ieee'])
        hidden = set(self.store.data.get('hidden_areas', []))
        extra_areas = [k[5:] for k, m in self.store.data['room_meta'].items() if k.startswith('area:') and m.get('extra')]
        for aid in list(by_area) + [a for a in extra_areas if a not in by_area and a in self.areas]:
            rid = f'area:{aid}'
            if rid not in hidden:
                out.append(self._room_summary(rid, self.areas.get(aid, aid), 'area', self._area_members(rid, by_area.get(aid, []))))
        for r in self.store.data['rooms']:
            out.append(self._room_summary(r['id'], r['name'], 'custom',
                                          [m for m in r['members'] if m in self.devices]))
        out.sort(key=lambda r: r['name'].lower())
        return out

    def _area_members(self, rid, base):
        """An area room holds the area's devices, minus the ones removed in Ripple, plus the ones added in Ripple."""
        meta = self.store.room_meta(rid)
        removed = set(meta.get('removed', []))
        return [m for m in base if m not in removed] + [m for m in meta.get('extra', []) if m in self.devices and m not in base]

    def room_lines(self, members):
        """Usable lines of the room's devices as [(receiver, sender or None, on)].
        With 0xff46 each known, sent, unparked source voting in the room zone is a line.
        Without it a device counts as one line, unless it has 0xff46 and no source at all."""
        out = []
        for m in members:
            d = self.devices[m]
            states = self.line_states(m)
            if states == {} and self._no_sources(d):
                continue  # 5.0.5 device that listens to nobody: no line, and its own motion can never turn on
            if not states or any(v is None for v in states.values()):
                out.append((m, None, bool(d['live'].get('motion'))))
                continue
            sw = self.store.switch(m) or {}
            parked = set(sw.get('parked', []))
            fw = {l['nwk']: l for l in v5.decode_sources(d['config'].get('sources')) or []}
            for tx in sw.get('sources', []):
                x = self.devices.get(tx)
                l = fw.get(x['nwk']) if x else None
                if tx in states and l and tx not in parked and l.get('sens') and l.get('zones', 0) & am.ZONE_ROOM:
                    out.append((m, tx, bool(states[tx])))
        return out

    def _no_sources(self, d):
        """5.0.5 device whose sources are read and empty (no Ripple sender at all)."""
        api = d['config'].get('sense_api')
        return api in v5.SUPPORTED_API and v5.has_lines_on(api) and v5.decode_sources(d['config'].get('sources')) == []

    def room_trigger(self, rid, members, lines=None):
        """Mode, stored k, threshold, active and total lines of a room; any = 1, all = y, custom = k."""
        meta = self.store.room_meta(rid)
        mode = meta.get('trigger_mode', TRIGGER_DEFAULT)
        mode = mode if mode in TRIGGER_MODES else TRIGGER_DEFAULT
        k = meta.get('trigger_k')
        lines = self.room_lines(members) if lines is None else lines
        y, active = len(lines), sum(1 for *_, on in lines if on)
        want = 1 if mode == 'any' else y if mode == 'all' else (k or 1)
        threshold = max(1, min(want, y))
        return {'mode': mode, 'k': k, 'threshold': threshold, 'active': active, 'total': y,
                'clamped': mode == 'custom' and k is not None and k > threshold}

    def _room_summary(self, rid, name, kind, members):
        devs = [self.devices[m] for m in members]
        lines = self.room_lines(members)
        trig = self.room_trigger(rid, members, lines)
        moving = [d for d in devs if d['live'].get('motion')]
        if trig['threshold'] <= 1:
            # one line is enough: any device in motion, hold from its last OFF
            until = None if moving else self._room_hold_until(rid, devs)
            hold = until is not None and until > now()
            since = [d['live'].get('motion_at') for d in (moving or devs) if d['live'].get('motion_at')]
            occupied = bool(moving) or hold
            since = (min(since) if moving else max(since)) if since else None
            # kept so a later threshold above one line goes on from where this room is (on, or holding since its last OFF)
            offs = [d['live']['motion_off_at'] for d in devs if d['live'].get('motion_off_at')]
            self._trig[rid] = {'met': bool(moving), 'off_at': None if moving or not offs else max(offs),
                               'on_at': since if moving else None}
        else:
            # above one line the room follows the count of its lines, not the devices' own motion
            met = trig['active'] >= trig['threshold']
            st = self._trig.setdefault(rid, {'met': False, 'off_at': None, 'on_at': None})
            if met and not st['met']:
                st['on_at'] = now()
            if st['met'] and not met:
                st['off_at'] = now()  # the hold starts when the count drops below the threshold
            st['met'] = met
            active_rx = {rx for rx, _, on in lines if on}
            moving = [d for d in devs if d['ieee'] in active_rx] if met else []
            until = None if met or st['off_at'] is None else st['off_at'] + self.store.room_meta(rid).get('off_s', ROOM_OFF_DEFAULT)
            hold = until is not None and until > now()
            occupied = met or hold
            if met:
                ons = [d['live']['motion_at'] for d in moving if d['live'].get('motion') and d['live'].get('motion_at')]
                since = min(ons) if ons else st['on_at']
            else:
                offs = [d['live'].get('motion_at') for d in devs if d['live'].get('motion_at')]
                since = st['off_at'] if st['off_at'] is not None else (max(offs) if offs else None)
        flags = [am.decode_flags(d['live'].get('flags'), dev_api(d)) for d in devs]
        return {'id': rid, 'name': name, 'kind': kind, 'members': members,
                'occupied': occupied, 'hold_until': until if hold else None, 'since': since,
                'moving': [d['ieee'] for d in moving],
                'calibrating': any(f['calibrating'] for f in flags),
                'needs_calibration': any(f['needs_calibration'] or f['refused'] for f in flags),
                'offline': [d['ieee'] for d in devs if not d['available']],
                'pending': sum(1 for m in members if self.pending(m)),
                'cal_s': self.store.room_meta(rid).get('cal_s', 300),
                'settings': {'off_s': self.store.room_meta(rid).get('off_s', ROOM_OFF_DEFAULT),
                             'trigger_mode': trig['mode'], 'trigger_k': trig['k']},
                'trigger': trig,
                'detected_by': [x for m in members for x in self.detecting_lines(m)]}

    def room(self, rid):
        for r in self.rooms():
            if r['id'] == rid:
                return r
        raise KeyError(f'no room {rid}')

    def room_settings(self, rid):
        r = self.room(rid)
        meta = self.store.room_meta(rid)
        vals = {'cal_s': meta.get('cal_s', 300), 'off_s': meta.get('off_s', ROOM_OFF_DEFAULT),
                'trigger_mode': r['trigger']['mode'], 'trigger_k': r['trigger']['k']}
        for k in ('beacon_hz', 'detect'):
            seen = {(self.store.switch(m) or {}).get('settings', {}).get(k) for m in r['members']
                    if self.store.switch(m)}
            vals[k] = seen.pop() if len(seen) == 1 else ('mixed' if seen else None)
        return vals

    async def set_room_settings(self, rid, changes):
        r = self.room(rid)
        results = {}
        if 'cal_s' in changes:
            self.store.room_meta(rid)['cal_s'] = _int_in(changes.pop('cal_s'), 60, 1800, 'cal_s')
            self.store.save()
            self._changed()
        if 'trigger_mode' in changes and changes['trigger_mode'] not in TRIGGER_MODES:
            raise ValueError(f"trigger_mode must be one of {', '.join(TRIGGER_MODES)}")
        if changes.get('trigger_k') is not None:
            _int_in(changes['trigger_k'], 1, TRIGGER_K_MAX, 'trigger_k')
        room_keys = [k for k in ('off_s', 'trigger_mode', 'trigger_k') if k in changes]
        if room_keys:
            meta = self.store.room_meta(rid)
            if 'off_s' in changes:
                meta['off_s'] = _int_in(changes.pop('off_s'), 0, ROOM_OFF_MAX, 'off_s')
            if 'trigger_mode' in changes:
                meta['trigger_mode'] = changes.pop('trigger_mode')
            if 'trigger_k' in changes:
                k = changes.pop('trigger_k')
                meta['trigger_k'] = None if k is None else int(k)
            self.store.save()
            self._arm_room_holds()
            self._changed()
            results['room'] = {'written': True}
        if not changes:
            return results
        for m in r['members']:
            if self.store.switch(m):
                try:
                    results[m] = await self.set_switch_settings(m, changes)
                except ZigbeeError as e:
                    results[m] = {'written': False, 'error': str(e)}
        return results

    def create_room(self, name, members):
        name = (name or '').strip()
        if not name:
            raise ValueError('a room needs a name')
        r = {'id': 'r' + uuid.uuid4().hex[:8], 'name': name[:60], 'members': [m for m in members if m in self.devices]}
        self.store.data['rooms'].append(r)
        self.store.save()
        self._changed()
        return r

    def update_room(self, rid, name=None, members=None):
        if rid.startswith('area:'):
            if name is not None and name.strip() and name.strip() != self.areas.get(rid[5:]):
                raise ValueError('a room from a Home Assistant area takes the name of the area; rename the area in Home Assistant')
            if members is not None:
                base = [d['ieee'] for d in self.ripple_devices() if d['area_id'] == rid[5:]]
                want = [m for m in dict.fromkeys(members) if m in self.devices]
                meta = self.store.room_meta(rid)
                meta['removed'] = [m for m in base if m not in want]
                meta['extra'] = [m for m in want if m not in base]
                self.store.save()
                self._changed()
            return self.room(rid)
        r = next((x for x in self.store.data['rooms'] if x['id'] == rid), None)
        if r is None:
            raise KeyError(rid)
        if name is not None and name.strip():
            r['name'] = name.strip()[:60]
        if members is not None:
            r['members'] = [m for m in members if m in self.devices]
        self.store.save()
        self._changed()
        return r

    def delete_room(self, rid):
        if rid.startswith('area:'):
            self.store.data.setdefault('hidden_areas', []).append(rid)
        else:
            self.store.data['rooms'] = [x for x in self.store.data['rooms'] if x['id'] != rid]
        self.store.save()
        self._changed()

    # ---------- link sources ----------

    def heard_by(self, ieee):
        d = self.devices[ieee]
        heard = set(d['neighbors'])
        heard |= {x['ieee'] for x in self.devices.values() if ieee in x['neighbors']}
        nwk_to_ieee = {x['nwk']: x['ieee'] for x in self.devices.values()}
        for nwk, diag in self._link_diag(ieee).items():
            if diag['alive'] and nwk in nwk_to_ieee:
                heard.add(nwk_to_ieee[nwk])
        heard.discard(ieee)
        return heard

    def _link_diag(self, ieee):
        """link_diag entries by sender NWK; entries follow the order of the lines the device holds."""
        d, prof = self.devices[ieee], self.profile(ieee)
        if not prof:
            return {}
        lines = prof['decoders']['sources'](d['config'].get('sources')) or []
        diag = [e for key in ('link_a', 'link_b') for e in prof['decoders'][key](d['config'].get(key), dev_api(d)) or []]
        return {l['nwk']: e for l, e in zip(lines, diag)}

    def candidates(self, ieee):
        d, heard = self.devices[ieee], self.heard_by(ieee)
        sel = set((self.store.switch(ieee) or {}).get('sources', []))
        out = []
        for x in self.devices.values():
            if x['ieee'] == ieee:
                continue
            out.append({'ieee': x['ieee'], 'name': x['name'], 'area': x['area'], 'heard': x['ieee'] in heard,
                        'same_area': bool(d['area_id']) and x['area_id'] == d['area_id'], 'selected': x['ieee'] in sel,
                        'available': x['available'], 'kind': x['kind']})
        out.sort(key=lambda c: (not c['heard'], not c['same_area'], (c['name'] or '').lower()))
        return out

    def links(self, ieee):
        """Per source: what the device reports about its line (level, rate, S, status) next to what Ripple wants."""
        d, prof, sw = self.devices[ieee], self.profile(ieee), self.store.switch(ieee) or {'sources': []}
        by_nwk = self._link_diag(ieee)
        fw_lines = {l['nwk']: l for l in (prof['decoders']['sources'](d['config'].get('sources')) or [])} if prof else {}
        sent = set(fw_lines)
        api = dev_api(d)
        tune = {**v5.tune_defaults(api), **(am.decode_tune(d['config'].get('tune')) or {})}
        sole = self._sole_voters(d, fw_lines)
        exact = self.line_states(ieee) or {}  # the device's own per-line state
        out = []
        for s in sw['sources']:
            x = self.devices.get(s)
            nwk = x['nwk'] if x else None
            info = by_nwk.get(nwk, {})
            if not x or nwk not in sent:
                state = 'missing' if not x else 'not_sent'
            elif api == 5:  # a line votes without a capture; only its rate and level gate it
                state = ('calibrated' if info.get('calibrated') else 'usable') if info.get('usable') else (
                    'below_level_min' if info.get('level_dbm') is not None and info['level_dbm'] < tune['level_min']
                    else 'blind')
            else:
                state = 'not_learned' if not info.get('calibrated') else 'calibrated' if info.get('usable') else 'blind'
            out.append({'ieee': s, 'name': x['name'] if x else s, 'area': x['area'] if x else None, 'state': state,
                        'sens': sw.get('sens', {}).get(s, v5.sens_default(api)), 'level': info.get('level_dbm'),
                        'rate': None if info.get('rate_d') is None else info['rate_d'] / 10, 'hits': info.get('hits'),
                        'thr_db': info.get('thr_db'), 'm': info.get('m'), 'bits': [n for n, _ in v5.LINK_BITS if info.get(n)],
                        'parked': s in set(sw.get('parked', [])),
                        'detecting': exact[s] if exact.get(s) is not None else nwk in sole or (
                            _detecting(info, api) and (fw_lines.get(nwk) or {}).get('sens') != 0
                            and self._votes_now(d, fw_lines.get(nwk))),
                        'evidence_pct': _pct(info.get('hits'), info.get('m')),
                        'last_on': nwk is not None and nwk == self._last_on_nwk(ieee),
                        'last_detection': self._line_last(ieee, s),
                        'det': _det_params(info, fw_lines.get(nwk), tune, api)})
        return out

    @staticmethod
    def _sole_voters(d, fw_lines):
        """Before link_diag is fresh: a zone that came on was turned on by one of its voting lines (sens > 0).
        When only one line votes for it, that line is detecting now."""
        zs = d['live'].get('zone_state')
        if not zs or d['live'].get('lines_at', 0) - d['live'].get('zone_on_at', 0) >= DIAG_FRESH_S:
            return set()
        out = set()
        for b in range(8):
            if zs & (1 << b):
                voters = [n for n, l in fw_lines.items() if l.get('sens') and l.get('zones', 0) & (1 << b)]
                if len(voters) == 1:
                    out.add(voters[0])
        return out

    @staticmethod
    def _votes_now(d, line):
        """zone_state is current; link_diag is not: a line votes only if its zones are on now and it was read after they came on."""
        zs = d['live'].get('zone_state')
        if zs is None or not line:
            return True
        return bool(zs & line.get('zones', 0)) and d['live'].get('lines_at', 0) - d['live'].get('zone_on_at', 0) >= DIAG_FRESH_S

    def _line_last(self, rx, tx):
        ts = [t for t in (self.line_last.get((rx, tx)), self.live.last_on.get((rx, tx))) if t]
        return max(ts) if ts else None

    def _last_on_nwk(self, ieee):
        """Sender of the line that last turned on (node_diag byte 4 is its index in the device's line list)."""
        d, prof = self.devices[ieee], self.profile(ieee)
        if not prof:
            return None
        node = prof['decoders']['node_diag'](d['live'].get('node_diag') or d['config'].get('node_diag'))
        lines = prof['decoders']['sources'](d['config'].get('sources')) or []
        i = (node or {}).get('last_on_line')
        return lines[i]['nwk'] if i is not None and i < len(lines) else None

    def detecting_lines(self, ieee):
        """Lines of one device that currently detect, as {device, sender, last_on}, from the last link_diag read."""
        if not self.profile(ieee):
            return []
        d = self.devices[ieee]
        return [{'switch': d['name'], 'switch_ieee': ieee, 'sender': l['name'], 'sender_ieee': l['ieee'],
                 'last_on': l['last_on']} for l in self.links(ieee) if l['detecting'] and not l['parked']]

    async def _snapshot_lines(self, ieee):
        """After a zone change, reads node_diag and link_diag once the device has refreshed them, so the UI shows which lines detect.
        A zone change during a read queues one more read instead of being lost."""
        if ieee in self._snapping:
            self._snap_again.add(ieee)
            return
        self._snapping.add(ieee)
        try:
            while True:
                self._snap_again.discard(ieee)
                await asyncio.sleep(DIAG_FRESH_S)
                await self._read_lines(self.devices[ieee])
                if ieee not in self._snap_again:
                    break
        finally:
            self._snapping.discard(ieee)
            self._snap_again.discard(ieee)

    async def _read_lines(self, d, with_node=True):
        prof = self.profile(d['ieee'])
        if not prof:
            return
        node = prof['decoders']['node_diag'](d['live'].get('node_diag') or d['config'].get('node_diag'))
        keys = (['node_diag'] if with_node else []) + ['link_a'] + (['link_b'] if (node or {}).get('lines', 0) > 5 else [])
        started = now()
        for k in keys:
            a = am.attr_by_key(prof, k)
            try:
                v = await self.zb.read_attr(d['ieee'], a['id'], a['type'], a['cluster'])
            except ZigbeeError as e:
                log.debug('line read %s: %s', d['name'], e)
                self._changed()
                return
            d['config'][k] = v
            if k == 'node_diag':
                self._set_node_diag(d, v)
        d['live']['lines_at'] = started
        self._note_detections(d['ieee'])
        self._changed()

    def _note_detections(self, ieee):
        for l in self.links(ieee):
            key = (ieee, l['ieee'])
            if l['detecting'] and not self._was_detecting.get(key):
                self.line_last[key] = now()
            if not l['parked']:
                self.history.add(ieee, l['ieee'], l['detecting'], 'diag')
            self._was_detecting[key] = l['detecting']

    async def set_raw_stream(self, ieee, on):
        """0xff31: raw signal stream to HA for diagnostics; the device turns it off at every restart."""
        self._switch_or_fail(ieee)
        await self.zb.write_attr(ieee, v5.A_RAW_ENABLED, am.U8, 1 if on else 0)
        self.devices[ieee]['config']['raw_enabled'] = 1 if on else 0
        self._changed()
        return {'written': True}

    def set_update(self, ieee, info):
        """A firmware install moved (HA's update entity); when it ends, the device is read again from ZHA."""
        d = self.devices.get(ieee)
        if not d or d.get('update') == info:
            return
        was = (d.get('update') or {}).get('in_progress')
        d['update'] = info
        self._changed()
        if was and not (info or {}).get('in_progress'):
            self._spawn(self.refresh())

    # ---------- live status ----------

    def _set_motion(self, d, on):
        on = bool(on)
        if d['live'].get('motion') != on or 'motion_at' not in d['live']:
            if d['live'].get('motion') and not on:
                d['live']['motion_off_at'] = now()
            d['live']['motion'] = on
            d['live']['motion_at'] = now()
            self._arm_room_holds()
            self._changed()

    def _room_hold_until(self, rid, devs):
        """When the room goes off after its last device went off (the room's own off_s, not the device's)."""
        offs = [d['live']['motion_off_at'] for d in devs if d['live'].get('motion_off_at')]
        if not offs:
            return None
        return max(offs) + self.store.room_meta(rid).get('off_s', ROOM_OFF_DEFAULT)

    def _arm_room_holds(self):
        rooms = self.rooms()  # also notes when a room's line count drops below its threshold
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        for r in rooms:
            t = self._hold_timers.pop(r['id'], None)
            if t:
                t.cancel()
            if r['hold_until']:
                self._hold_timers[r['id']] = loop.call_later(max(0, r['hold_until'] - now()) + 0.05, self._changed)

    def _on_report(self, ieee, cluster, attr, value):
        """zone_state (0xff43, manufacturer 0x1141) and Occupancy (0x0406) reports; the room is zone bit 0."""
        d = self.devices.get(ieee)
        if not d or d['kind'] != 'ripple':
            return
        if (cluster, attr) == (v5.CLUSTER, v5.A_LIVE):
            if isinstance(value, (bytes, bytearray)):
                self.live.on_frame(ieee, value)
            return
        if not isinstance(value, int):
            return
        if (cluster, attr) == (v5.CLUSTER, v5.A_LINES_ON):
            # sent with zone_state in one Report; bit i = line i of sources
            d['live']['event_seen'] = True
            if d['config'].get('lines_on') != value:
                d['config']['lines_on'] = value
                self._arm_room_holds()
                self._changed()
            return
        if (cluster, attr) in ((v5.CLUSTER, v5.A_ZONE_STATE), (v5.OCCUPANCY, v5.A_OCCUPANCY)):
            d['live']['event_seen'] = True
            if cluster == v5.CLUSTER:
                old = d['live'].get('zone_state')
                changed = old != value
                d['live']['zone_state'] = value
                if value & ~(old or 0):
                    d['live']['zone_on_at'] = now()
            moved = d['live'].get('motion') != bool(value & am.ZONE_ROOM)
            self._set_motion(d, value & am.ZONE_ROOM)
            if cluster == v5.CLUSTER and changed:
                self._spawn(self._snapshot_lines(ieee))
                if not moved:
                    self._changed()

    async def _read_s(self, d):
        """5.0.4: re-reads sources and the self-tuning device, then takes the s the device moved itself."""
        prof = self.profile(d['ieee'])
        for k in ('sources', 'self_tune'):
            a = am.attr_by_key(prof, k)
            try:
                d['config'][k] = await self.zb.read_attr(d['ieee'], a['id'], a['type'], a['cluster'])
            except Unsupported:
                continue
        d['live']['s_read_at'] = now()
        self._update_live_from_config(d)

    async def poll_device(self, d):
        prof = self.profile(d['ieee'])
        was = d['live'].get('motion')
        cal_was = d['live'].get('cal_left')
        for k in ('node_diag', 'cal_left'):
            a = am.attr_by_key(prof, k)
            try:
                v = await self.zb.read_attr(d['ieee'], a['id'], a['type'], a['cluster'])
            except Unsupported:
                continue
            except ZigbeeError as e:
                d['live']['error'] = str(e)
                self._changed()
                return
            d['config'][k] = v
            if k == 'node_diag':
                self._set_node_diag(d, v)
            else:
                d['live'][k], d['live']['cal_left_at'] = v, now()
        d['live']['read_at'] = now()
        d['live'].pop('error', None)
        # the device moves s after a Calibrate and during self-tuning, so s is re-read
        if dev_api(d) == 5 and ((cal_was and not d['live'].get('cal_left'))
                                or now() - d['live'].get('s_read_at', 0) >= S_READ_S):
            try:
                await self._read_s(d)
            except ZigbeeError as e:
                d['live']['error'] = str(e)
        if d['live'].get('motion') or was or now() - d['live'].get('lines_at', 0) >= LINES_READ_S:
            await self._read_lines(d, with_node=False)
        self._changed()

    async def retry_adoption(self):
        for ieee in list(self.devices):
            d = self._current(ieee)
            if not d or d['kind'] != 'ripple' or not d['available'] or ieee in self._busy:
                continue
            if self._needs_adoption(ieee):
                await self._adopt(d)
            elif not d['config_at']:
                await self.read_config(ieee)

    async def _poll_loop(self):
        interval = max(10, int(self.opts.get('poll_interval_s', 60)))
        await self._wait_ready()
        while True:
            self._subscribe()
            await self._check_nwk()
            if not self.status.get('probing'):
                await self.retry_adoption()
            start = now()
            for d in list(self.ripple_devices()):
                if d['available'] and d['ieee'] not in self._busy:
                    await self.poll_device(d)
            fast = any(am.decode_flags(d['live'].get('flags'))['calibrating'] for d in self.ripple_devices())
            await asyncio.sleep(max(2, (10 if fast else interval) - (now() - start)))

    async def _check_nwk(self):
        """A sender that rejoined with a new NWK makes its lines pending; a refresh sends them again."""
        try:
            zdevs = await self.core.call({'type': 'zha/devices'})
        except Exception:
            return
        if any(z['ieee'] in self.devices and self.devices[z['ieee']].get('nwk') != z.get('nwk') for z in zdevs or []):
            log.info('a device changed its network address, refreshing')
            await self.refresh()

    async def _reconcile_loop(self):
        minutes = int(self.opts.get('resync_minutes', 60))
        while True:
            await asyncio.sleep(max(5, minutes) * 60)
            if not self.zb.allow_writes:
                continue
            for d in list(self.ripple_devices()):
                if d['available'] and api_state(d) != 'ok':
                    await self._read_api(d)
                if d['available'] and self.store.switch(d['ieee']) and api_state(d) == 'ok':
                    await self.read_config(d['ieee'], ('derived',))
                    if self.pending(d['ieee']):
                        await self._safe_apply(d['ieee'])

    # ---------- views for the API ----------

    def device_summary(self, d):
        rooms = [r['name'] for r in self.rooms() if d['ieee'] in r['members']]
        return {k: d.get(k) for k in ('ieee', 'nwk', 'name', 'model', 'manufacturer', 'area', 'area_id', 'available',
                                      'device_type', 'lqi', 'last_seen', 'sw_version', 'kind', 'probe', 'profile',
                                      'error', 'reg_id', 'has_onoff')} | {
            'links_count': len((self.store.switch(d['ieee']) or {}).get('sources', [])),
            'ripple_fw': is_ripple_firmware(d), 'sw_build_id': d.get('sw_build_id'),
            'api': api_state(d) if d['kind'] == 'ripple' else None, 'sense_api': d['config'].get('sense_api'),
            'update': d.get('update'),
            'rooms': rooms, 'motion': d['live'].get('motion'), 'motion_at': d['live'].get('motion_at'),
            'flags': None if d['live'].get('flags') is None else am.decode_flags(d['live']['flags']), 'cal_left': d['live'].get('cal_left'),
            'cal_left_at': d['live'].get('cal_left_at'),
            'cal_txs': d['live'].get('cal_txs'),
            'pending': len(self.pending(d['ieee'])) if d['kind'] == 'ripple' else 0}

    def switch_view(self, ieee):
        d, prof = self.devices[ieee], self.profile(ieee)
        sw = self.store.switch(ieee)
        view = self.device_summary(d)
        node = prof['decoders']['node_diag'](d['live'].get('node_diag') or d['config'].get('node_diag')) if prof else None
        cfg = d['config']
        adv = []
        tdef = v5.tune_defaults(dev_api(d))
        for a in (prof['advanced'] if prof else []):
            cur = cfg.get(a['key'])
            want = ((sw or {}).get('settings', {}).get('advanced') or {}).get(a['key'])
            adv.append({k: a.get(k) for k in ('key', 'min', 'max', 'step', 'unit', 'section', 'help')}
                       | {'default': tdef.get(a['field'], a['default'] * a['scale']) / a['scale']}
                       | {'device': None if cur is None else cur / a['scale'], 'value': want,
                          'firmware_name': am.firmware_name(a)})
        view.update(node=node, settings=(sw or {}).get('settings'), adopted=sw is not None,
                    advanced=adv, raw_enabled=cfg.get('raw_enabled'), lines_at=d['live'].get('lines_at'),
                    detected_by=self.detecting_lines(ieee),
                    links=self.links(ieee) if prof else [],
                    pending_list=[{k: v.hex() if isinstance(v, bytes) else v for k, v in p.items()} for p in self.pending(ieee)],
                    reading=ieee in self._busy, config_at=d['config_at'],
                    max_sources=prof['include_slots'] if prof else 0,
                    cal_range=[prof['cal_min'], prof['cal_max']] if prof else None)
        return view

    def device_detail(self, ieee):
        d, prof = self.devices[ieee], self.profile(ieee)
        view = self.switch_view(ieee)
        cfg = d['config']
        if prof:
            nwk_names = {x['nwk']: x['name'] for x in self.devices.values()}
            diag = [{'nwk': nwk, 'name': nwk_names.get(nwk, f'0x{nwk:04x}'), **e} for nwk, e in self._link_diag(ieee).items()]
            view.update(diag=diag, stack_used=cfg.get('stack_used'),
                        beacons_skipped=cfg.get('beacons_skipped'), profile_label=prof['label'])
        return view


def _det_params(info, fw_line, tune, api=3):
    """What the panel needs to replay the 5.0.3 motion rule of one line for every s.
    From 5.0.4 the panel reads the Live meter instead."""
    if not info.get('rate_d'):
        return None
    s = fw_line['sens'] if fw_line else v5.sens_default(api)
    thr, m = v5.motion_params(s, api)
    return {'api': api, 's': s, 'rate_d': info['rate_d'], 'thr_db': thr / 4 if api == 5 else thr, 'm': m,
            'off_s': tune['off_s'], 'decim': (info['rate_d'] + 124) // 125 if info['rate_d'] > 125 else 1}


def _detecting(info, api=3):
    """A line votes when it is on, usable, alive and not parked.
    On 5.0.3 it must also be calibrated."""
    keys = ('on', 'usable', 'alive') + (('calibrated',) if api == 3 else ())
    return all(info.get(k) for k in keys) and not info.get('parked')


def _pct(hits, m):
    return None if hits is None or not m else min(100, round(100 * hits / m))


def _int_in(v, lo, hi, name):
    try:
        iv = int(v)
    except (TypeError, ValueError):
        raise ValueError(f'{name} must be a whole number')
    if not lo <= iv <= hi:
        raise ValueError(f'{name} must be between {lo} and {hi}')
    return iv

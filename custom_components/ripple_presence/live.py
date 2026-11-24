"""Live: per-room sessions, command 0x02 per receiver, records from reports of 0xff4e."""
import asyncio
import logging
import time

from . import v5

log = logging.getLogger('ripple.live')


def now():
    return time.time()


class LiveBudget(ValueError):
    """The Live sessions together would send more frames than the coordinator should take."""


class Live:
    def __init__(self, engine):
        self.engine = engine
        self.sessions = {}      # room id -> {'end': ts, 'cand': {(rx, tx): s}, 'only': [(rx, tx)] or None}
        self.sent = {}          # receiver -> last payload sent
        self.lines = {}         # (rx, tx) -> last record
        self.last_on = {}       # (rx, tx) -> ts of the last turn ON seen
        self.m = {}             # (rx, tx) -> M of the line's s, announced by the device (Live v2)
        self.stats = {}         # receiver -> {'frames', 'dropped', 'lost', 'seq'}
        self.listeners = []
        self._timers = {}
        self._lock = asyncio.Lock()

    # ---------- what is live ----------

    def room_lines(self, rid):
        """Lines of a room: every line of every receiver in the room, as (rx, tx)."""
        e = self.engine
        out = []
        for rx in e.room(rid)['members']:
            sw = e.store.switch(rx)
            if sw and e.profile(rx):
                out += [(rx, tx) for tx in sw['sources']]
        return out

    def plan(self, sessions=None):
        """receiver -> {'end': ts, 'lines': {tx: s or None}} merged over the live rooms."""
        sessions = self.sessions if sessions is None else sessions
        out = {}
        for rid, s in sessions.items():
            try:
                lines = self.room_lines(rid)
            except KeyError:
                continue
            only = s.get('only')
            for rx, tx in lines:
                if only is not None and (rx, tx) not in only:
                    continue
                p = out.setdefault(rx, {'end': 0, 'lines': {}})
                p['end'] = max(p['end'], s['end'])
                cand = s['cand'].get((rx, tx))
                if cand is not None or tx not in p['lines']:
                    p['lines'][tx] = cand
        return out

    def tmin_ms(self, receivers):
        return max(v5.LIVE_TMIN_MIN_MS, 33 * receivers)

    def frames_per_s(self, plan):
        """Upper bound of the Live frames per second: a full buffer skips tmin."""
        tmin = self.tmin_ms(len(plan))
        total = 0.0
        for rx, p in plan.items():
            hz = max([self._beacon_hz(tx) for tx in p['lines']] or [v5.BEACON_DEFAULT])
            total += max(1000 / tmin, len(p['lines']) * hz / v5.LIVE_RECORDS_PER_FRAME)
        return total

    def _beacon_hz(self, ieee):
        sw = self.engine.store.switch(ieee) or {}
        hz = (sw.get('settings') or {}).get('beacon_hz')
        return hz if hz else v5.BEACON_DEFAULT

    def view(self):
        t = now()
        return {rid: {'end': s['end'], 'left': max(0, round(s['end'] - t)),
                      'cand': [{'rx': rx, 'tx': tx, 'step': st} for (rx, tx), st in s['cand'].items()],
                      'lines': None if s.get('only') is None else [{'rx': rx, 'tx': tx} for rx, tx in s['only']]}
                for rid, s in self.sessions.items()}

    # ---------- user actions ----------

    async def start(self, rid, seconds, lines=None):
        """Live Room (lines None) or Live of some lines of the room; a new start replaces the room's session."""
        seconds = int(seconds)
        if not 10 <= seconds <= v5.LIVE_DURATION_MAX:
            raise ValueError(f'Live lasts 10 to {v5.LIVE_DURATION_MAX} s')
        room = self.room_lines(rid)
        if not room:
            raise ValueError('this room has no lines to stream')
        only = None
        if lines is not None:
            only = [tuple(x) for x in lines]
            if not only or any(x not in room for x in only):
                raise KeyError('a line to stream is not a line of this room')
        sessions = {**self.sessions, rid: {'end': now() + seconds, 'cand': (self.sessions.get(rid) or {}).get('cand', {}),
                                           'only': only}}
        fps = self.frames_per_s(self.plan(sessions))
        if fps > v5.LIVE_FRAMES_MAX:
            raise LiveBudget(f'Live in these rooms would send about {fps:.0f} frames/s, '
                             f'above {v5.LIVE_FRAMES_MAX}; stop Live in another room first')
        self.sessions = sessions
        getattr(self.engine, '_subscribe', lambda: None)()
        self._arm(rid, seconds)
        await self.apply()
        return self.view()

    async def stop(self, rid):
        self.sessions.pop(rid, None)
        t = self._timers.pop(rid, None)
        if t:
            t.cancel()
        await self.apply()
        return self.view()

    async def set_candidate(self, rid, rx, tx, step):
        s = self.sessions.get(rid)
        if not s:
            raise ValueError('Live is not running in this room')
        if (rx, tx) not in self.room_lines(rid) or (s.get('only') is not None and (rx, tx) not in s['only']):
            raise KeyError(f'no live line {rx} <- {tx} in this room')
        if step is None:
            s['cand'].pop((rx, tx), None)
        else:
            s['cand'][(rx, tx)] = v5.check_s(int(step))
        await self.apply()
        return self.view()

    async def after_sources(self, rx):
        """A sources write stops Live on the device (line indices may move): send it again."""
        if any(rx in p for p in [self.plan()]):
            self.sent.pop(rx, None)
            await self.apply()

    def _arm(self, rid, seconds):
        old = self._timers.pop(rid, None)
        if old:
            old.cancel()

        async def expire():
            await asyncio.sleep(seconds)
            self._timers.pop(rid, None)
            if rid in self.sessions and self.sessions[rid]['end'] <= now() + 0.5:
                self.sessions.pop(rid, None)
                await self.apply()
                self._emit({'type': 'live_state', 'live': self.view()})
        self._timers[rid] = asyncio.ensure_future(expire())

    async def apply(self):
        """Sends command 0x02 to every receiver whose Live lines changed; 0 s stops the ones no longer live."""
        async with self._lock:
            e = self.engine
            plan = self.plan()
            tmin = self.tmin_ms(len(plan))
            t = now()
            for rx in sorted(set(plan) | set(self.sent)):
                p = plan.get(rx)
                if p:
                    sw = e.store.switch(rx) or {}
                    lines = []
                    for tx, step in p['lines'].items():
                        x = e.devices.get(tx)
                        if not x or x.get('nwk') is None:
                            continue
                        saved = (sw.get('sens') or {}).get(tx, v5.sens_default(sw.get('sens_api')))
                        lines.append((x['nwk'], step if step and step != saved else 0))
                    dur = max(1, min(v5.LIVE_DURATION_MAX, round(p['end'] - t)))
                    payload = v5.encode_live(dur, tmin, lines) if lines else v5.encode_live(0, tmin, [])
                else:
                    payload = v5.encode_live(0, tmin, [])
                if self.sent.get(rx) == payload[3:] and p:
                    continue
                if not p and rx not in self.sent:
                    continue
                d = e.devices.get(rx)
                if not d or not d['available']:
                    self.sent.pop(rx, None)
                    continue
                try:
                    await e.zb.command(rx, v5.CMD_LIVE, payload)
                except Exception as err:
                    log.warning('live %s: %s', d['name'], err)
                    d['live']['live_error'] = str(err)
                    self.sent.pop(rx, None)
                    continue
                d['live'].pop('live_error', None)
                if p:
                    self.sent[rx] = payload[3:]
                else:
                    self.sent.pop(rx, None)
                    for k in [k for k in self.lines if k[0] == rx]:
                        self.lines.pop(k, None)
            self._emit({'type': 'live_state', 'live': self.view()})

    # ---------- frames from the devices ----------

    def on_frame(self, rx, value):
        f = v5.decode_live(value)
        if f is None:
            return
        e = self.engine
        d = e.devices.get(rx)
        prof = e.profile(rx)
        if not d or not prof:
            return
        srcs = prof['decoders']['sources'](d['config'].get('sources')) or []
        nwk_to_ieee = {x['nwk']: x['ieee'] for x in e.devices.values() if x.get('nwk') is not None}
        tx_of = {i: nwk_to_ieee.get(l['nwk']) for i, l in enumerate(srcs)}
        st = self.stats.setdefault(rx, {'frames': 0, 'dropped': 0, 'lost': 0, 'seq': None})
        if st['seq'] is not None:
            st['lost'] += (f['seq'] - st['seq'] - 1) & 0xFF
        st['seq'] = f['seq']
        st['frames'] += 1
        st['dropped'] += f['dropped']
        t = now()
        moved = False
        info = []
        for i in f['info']:
            tx = tx_of.get(i['idx'])
            if not tx:
                continue
            self.m[(rx, tx)] = i['m']
            if i['since_on_s'] is not None:
                old = self.last_on.get((rx, tx))
                # the age comes in whole seconds: a jitter under 1 s is not a new turn on
                if old is None or abs(t - i['since_on_s'] - old) >= 1:
                    self.last_on[(rx, tx)] = t - i['since_on_s']
                    moved = True
            info.append({'tx': tx, 'm': i['m'], 'last_on': self.last_on.get((rx, tx))})
        recs = []
        for r in f['records']:
            tx = tx_of.get(r['idx'])
            if not tx:
                continue
            prev = self.lines.get((rx, tx))
            if r['on'] and not (prev or {}).get('on'):
                self.last_on[(rx, tx)] = t
                moved = True
            e.history.add(rx, tx, r['on'], 'live', t)
            self.lines[(rx, tx)] = r
            recs.append({'tx': tx, **{k: r[k] for k in ('on', 'gate', 'vote', 'usable', 'preview', 'ms', 'q', 'q2', 'd')},
                         'last_on': self.last_on.get((rx, tx))})
        self._emit({'type': 'live', 'rx': rx, 'seq': f['seq'], 'dropped': f['dropped'], 'lost': st['lost'],
                    'records': recs, 'info': info})
        if moved:   # last_on feeds the line's last detection in the device view
            e._changed()

    def _emit(self, ev):
        if ev.get('type') == 'live_state':
            self.engine._changed()  # the sessions are part of the panel's state too
        for cb in list(self.listeners):
            try:
                cb(ev)
            except Exception:
                log.exception('live listener')

    def stop_all(self):
        for t in self._timers.values():
            t.cancel()
        self._timers.clear()

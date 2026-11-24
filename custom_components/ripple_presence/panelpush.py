"""Pushes the panel state over the websocket: a snapshot on subscribe, then only what changed.
Changes inside the flush window are merged, so bursts do not spend the event loop on rebuilds.
Connections with the same delta share one encoded message."""
import json
import time

FLUSH_S = 0.05
LISTS = ('meta', 'others', 'zha')


def _dump(v):
    return json.dumps(v, sort_keys=True, separators=(',', ':'))


def _cache(views):
    return {'switches': {k: {f: _dump(x) for f, x in v.items()} for k, v in views['switches'].items()},
            'rooms': {r['id']: _dump(r) for r in views['rooms']},
            **{k: _dump(views[k]) for k in LISTS}}


def _delta(cache, views, new):
    """What differs between what a connection last received (cache) and the new views (new = _cache(views))."""
    out = {}
    sw = {}
    for ieee, keys in new['switches'].items():
        old = cache['switches'].get(ieee)
        if old is None:
            sw[ieee] = views['switches'][ieee]
            continue
        ch = {f: views['switches'][ieee][f] for f, s in keys.items() if old.get(f) != s}
        dropped = [f for f in old if f not in keys]
        if dropped:
            ch['_drop'] = dropped
        if ch:
            sw[ieee] = ch
    if sw:
        out['switches'] = sw
    gone = [k for k in cache['switches'] if k not in new['switches']]
    if gone:
        out['gone'] = gone
    rooms = {r['id']: r for r in views['rooms'] if cache['rooms'].get(r['id']) != new['rooms'][r['id']]}
    if rooms:
        out['rooms'] = rooms
    rgone = [k for k in cache['rooms'] if k not in new['rooms']]
    if rgone:
        out['rooms_gone'] = rgone
    if [r['id'] for r in views['rooms']] != list(cache['rooms']):
        out['room_order'] = [r['id'] for r in views['rooms']]
    for k in LISTS:
        if cache[k] != new[k]:
            out[k] = views[k]
    return out


def zha_list(e):
    """Every Zigbee device a binding can target (not the coordinator, not a protected device)."""
    from .engine import is_our_firmware
    out = [{k: d.get(k) for k in ('ieee', 'name', 'model', 'area', 'available', 'kind', 'reg_id')} | {'ours': is_our_firmware(d)}
           for d in e.devices.values() if d['kind'] not in ('coordinator', 'protected')]
    out.sort(key=lambda d: (d['name'] or '').lower())
    return out


def build_views(e, allow_writes, entry_id, ready, entity_of=lambda rid: None):
    """Everything the panel shows.
    Live sessions go without their countdown: the panel counts from 'end'."""
    live = {rid: {k: v for k, v in s.items() if k != 'left'} for rid, s in e.live.view().items()}
    rooms = e.rooms()
    for r in rooms:
        r['entity_id'] = entity_of(r['id'])
    return {
        'meta': {'allow_writes': allow_writes, 'status': e.status, 'entry_id': entry_id, 'live': live},
        'rooms': rooms,
        'switches': {s: e.switch_view(s) for s in ready},
        'others': [e.device_summary(d) for d in e.devices.values() if d['kind'] in ('needs_firmware', 'candidate')],
        'zha': zha_list(e),
    }


class PanelPush:
    def __init__(self, build, loop):
        """build() -> {'meta': {...}, 'rooms': [...], 'others': [...], 'zha': [...], 'devices': {ieee: view}}."""
        self._build = build
        self._loop = loop
        self._conns = {}
        self._next = 0
        self._handle = None
        self._last = 0.0
        self._window = FLUSH_S
        self.rev = 0
        self.stats = {'flushes': 0, 'sent': 0, 'bytes': 0, 'last_ms': 0.0, 'window_ms': FLUSH_S * 1000}

    def snapshot(self):
        """The full state with the current rev, from the same build the deltas come from.
        A pending flush goes out first, so no panel is left showing an intermediate value."""
        views = self.flush() if self._conns else self._build()
        return views, {'type': 'snapshot', 'rev': self.rev, 'now': time.time(), **views,
                       'switches': list(views['switches'].values())}

    def subscribe(self, send):
        """Sends the snapshot at once and returns the unsubscribe callback."""
        views, snap = self.snapshot()
        cid = self._next
        self._next += 1
        self._conns[cid] = (send, _cache(views))
        send(snap)

        def unsub():
            self._conns.pop(cid, None)
        return unsub

    def changed(self):
        if self._handle is not None or not self._conns:
            return
        wait = self._last + self._window - time.monotonic()
        self._handle = self._loop.call_later(wait, self.flush) if wait > 0 else self._loop.call_soon(self.flush)

    def flush(self):
        """Sends every connection what changed and returns the views it was built from."""
        if self._handle is not None:
            self._handle.cancel()
            self._handle = None
        self._last = time.monotonic()
        if not self._conns:
            return None
        t0 = time.perf_counter()
        views = self._build()
        new = _cache(views)
        outs, encoded = [], {}
        for cid, (send, cache) in list(self._conns.items()):
            delta = _delta(cache, views, new)
            if delta:
                self._conns[cid] = (send, new)
                outs.append((send, delta))
        if outs:
            self.rev += 1
            now = time.time()
            for send, delta in outs:
                key = _dump(delta)
                if key not in encoded:
                    encoded[key] = {'type': 'delta', 'rev': self.rev, 'now': now, **delta}
                    self.stats['bytes'] = len(key)
                self.stats['sent'] += 1
                try:
                    send(encoded[key])
                except Exception:  # a socket already gone; its unsubscribe drops it
                    pass
        ms = (time.perf_counter() - t0) * 1000
        self.stats['flushes'] += 1
        self.stats['last_ms'] = round(ms, 2)
        self._window = max(FLUSH_S, 2 * ms / 1000)
        self.stats['window_ms'] = round(self._window * 1000, 1)
        return views

    def close(self):
        """On unload: every panel gets 'closed' so it subscribes again to the new instance."""
        if self._handle is not None:
            self._handle.cancel()
            self._handle = None
        for send, _ in list(self._conns.values()):
            try:
                send({'type': 'closed'})
            except Exception:  # a socket already gone
                pass
        self._conns.clear()

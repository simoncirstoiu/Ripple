"""Detections of every line (on / off) for the last 7 days, from Live and from the link_diag reads."""
import time

KEEP_S = 7 * 24 * 3600
MAX_EVENTS = 50000


class History:
    """In memory; HaHistory keeps it in .storage across restarts."""

    def __init__(self):
        self.events = []  # [t, rx, tx, on, src] oldest first
        self._state = {}  # (rx, tx) -> last on value recorded

    def add(self, rx, tx, on, src, t=None):
        """Records a change of the line only; the same state seen again by the other source is skipped."""
        on = bool(on)
        prev = self._state.get((rx, tx))
        if prev == on or (prev is None and not on):
            self._state[(rx, tx)] = on
            return False
        self._state[(rx, tx)] = on
        self.events.append([round(t if t is not None else time.time(), 1), rx, tx, on, src])
        self._prune()
        self.save()
        return True

    def query(self, lines=None, since=None, until=None, limit=500):
        """Newest first; lines is a set of (rx, tx) or None for all."""
        since = since if since is not None else time.time() - KEEP_S
        out = []
        for t, rx, tx, on, src in reversed(self.events):
            if t < since or len(out) >= limit:
                break
            if until is not None and t > until:
                continue
            if lines is None or (rx, tx) in lines:
                out.append({'t': t, 'rx': rx, 'tx': tx, 'on': on, 'src': src})
        return out

    def _prune(self):
        cut = time.time() - KEEP_S
        i = 0
        while i < len(self.events) and self.events[i][0] < cut:
            i += 1
        drop = max(i, len(self.events) - MAX_EVENTS)
        if drop:
            del self.events[:drop]

    def _loaded(self, events):
        self.events = [e for e in events if isinstance(e, list) and len(e) == 5]
        self.events.sort(key=lambda e: e[0])
        self._prune()
        self._state = {}
        for _, rx, tx, on, _ in self.events:
            self._state[(rx, tx)] = on

    def save(self):
        pass


class HaHistory(History):
    def __init__(self, hass, key='ripple_presence.history'):
        from homeassistant.helpers.storage import Store as HassStorage
        super().__init__()
        self._ha = HassStorage(hass, 1, key)

    async def async_load(self):
        loaded = await self._ha.async_load()
        if isinstance(loaded, dict):
            self._loaded(loaded.get('events') or [])

    def save(self):
        self._ha.async_delay_save(lambda: {'events': self.events}, 30)

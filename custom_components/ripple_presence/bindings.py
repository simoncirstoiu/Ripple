"""Zigbee bindings of the devices: read with ZDO Mgmt_Bind_req, change only through the guarded write path."""
from __future__ import annotations

import time

ONOFF, LEVEL = 0x0006, 0x0008


def _ieee(v):
    """binds_get gives the IEEE as little-endian byte list over the websocket, or as an object in process."""
    if isinstance(v, (list, tuple)) and len(v) == 8:
        return ':'.join(f'{b:02x}' for b in reversed(v))
    return str(v).lower() if v is not None else None


def parse_binds(resp):
    out = []
    for reply in (resp or {}).get('replies') or []:
        entries = reply[3] if isinstance(reply, (list, tuple)) and len(reply) > 3 else []
        for e in entries or []:
            dst = e.get('DstAddress') or {}
            mode = dst.get('addrmode')
            out.append({'src_ep': int(e.get('SrcEndpoint')), 'cluster': int(e.get('ClusterId')),
                        'dst_ieee': _ieee(dst.get('ieee')) if mode == 3 else None,
                        'dst_ep': dst.get('endpoint') if mode == 3 else None,
                        'group': dst.get('nwk') if mode == 1 else None})
    return out


class Bindings:
    def __init__(self, engine, zb, store=None):
        self.engine, self.zb, self.store = engine, zb, store
        self._mem = {}

    @property
    def cache(self):
        """Last table read per device; kept in the store so it survives restarts."""
        if self.store is None:
            return self._mem
        return self.store.data.setdefault('bindings', {})

    def _save(self):
        if self.store is not None:
            self.store.save()

    def _check_source(self, ieee):
        """Only our firmware holds bindings; any other device is only ever a target and is never read."""
        from .engine import is_our_firmware
        from .zigbee import NotRipple
        d = self.engine.devices.get(ieee)
        if d is None or not is_our_firmware(d):
            raise NotRipple(f'{(d or {}).get("name") or ieee} does not run Ripple firmware: it cannot hold a binding')

    async def read(self, ieee):
        self._check_source(ieee)
        try:
            resp = await self.zb.read_binds(ieee)
            if not (resp or {}).get('replies'):
                raise ValueError('the device did not answer the binding read')
            self.cache[ieee] = {'at': time.time(), 'binds': parse_binds(resp), 'error': None}
        except Exception as e:
            self.cache[ieee] = {**self.cache.get(ieee, {'binds': []}), 'at': time.time(), 'error': str(e)}
        self._save()
        return self.cache[ieee]

    def view(self, coordinator_ieee=None, clusters=(ONOFF,)):
        names = {d['ieee']: d['name'] for d in self.engine.devices.values()}
        rows = []
        for src, c in self.cache.items():
            for b in c.get('binds', []):
                if b['cluster'] not in clusters or not b['dst_ieee'] or b['dst_ieee'] == coordinator_ieee:
                    continue
                rows.append({**b, 'src_ieee': src, 'src_name': names.get(src, src), 'dst_name': names.get(b['dst_ieee'], b['dst_ieee'])})
        out = {}
        for ieee, c in self.cache.items():
            out[ieee] = {'at': c.get('at'), 'error': c.get('error'),
                         'controls': [r for r in rows if r['src_ieee'] == ieee],
                         'controlled_by': [r for r in rows if r['dst_ieee'] == ieee]}
        for r in rows:
            out.setdefault(r['dst_ieee'], {'at': None, 'error': None, 'controls': [], 'controlled_by': []})
            if r not in out[r['dst_ieee']]['controlled_by']:
                out[r['dst_ieee']]['controlled_by'].append(r)
        return out

    async def add(self, src, src_ep, dst, dst_ep, cluster=ONOFF):
        self._check_source(src)
        await self.zb.bind(src, int(src_ep), dst, int(dst_ep), int(cluster))
        c = self.cache.setdefault(src, {'at': time.time(), 'binds': [], 'error': None})
        new = {'src_ep': int(src_ep), 'cluster': int(cluster), 'dst_ieee': dst, 'dst_ep': int(dst_ep), 'group': None}
        if new not in c['binds']:
            c['binds'].append(new)
        return await self.read(src)

    async def remove(self, src, src_ep, dst, cluster=ONOFF):
        self._check_source(src)
        await self.zb.unbind(src, int(src_ep), dst, int(cluster))
        c = self.cache.get(src)
        if c:
            c['binds'] = [b for b in c['binds'] if not (b['src_ep'] == int(src_ep) and b['cluster'] == int(cluster) and b['dst_ieee'] == dst)]
        return await self.read(src)

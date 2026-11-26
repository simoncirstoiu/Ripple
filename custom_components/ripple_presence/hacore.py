"""Adapter that answers Ripple's requests from inside Home Assistant (registries, ZHA objects, services, bus).
Only the zcl_* calls send radio traffic."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import idents
from . import quirk, v5

_LOGGER = logging.getLogger(__name__)
OTA, OTA_FILE_VERSION = 0x0019, 0x0002
BASIC, SW_BUILD_ID = 0x0000, 0x4000


class CoreError(Exception):
    def __init__(self, code, message):
        super().__init__(f'{code}: {message}')
        self.code = code


def _zha_gateway(hass):
    """ZHA's gateway object; internal API, so every access is guarded."""
    try:
        from homeassistant.components.zha.helpers import get_zha_gateway
        return get_zha_gateway(hass)
    except Exception as e:
        _LOGGER.debug('ZHA gateway not reachable: %s', e)
        return None


def _registry_entries(reg):
    items = list(reg.devices)
    if items and isinstance(items[0], str):
        items = [reg.async_get(i) for i in items]
    return items


def zha_registry_entries(hass):
    """IEEE -> the device entry owned by ZHA; other entries may share its identifier or connection."""
    zha_ids = {e.entry_id for e in hass.config_entries.async_entries('zha')}
    out = {}
    for d in _registry_entries(dr.async_get(hass)):
        owned = d.config_entry_id in zha_ids if hasattr(d, 'config_entry_id') else bool(zha_ids & set(d.config_entries))
        for domain, ident in idents(d):
            key = str(ident).lower()
            if domain == 'zha' and (owned or key not in out):
                out[key] = d
    return out


def update_info(st):
    """What an update entity says about a firmware install: running, how far, from and to which version."""
    if st is None:
        return None
    a = st.attributes
    prog = a.get('in_progress')
    pct = a.get('update_percentage')
    if pct is None and isinstance(prog, (int, float)) and not isinstance(prog, bool):
        pct = prog
    return {'entity': st.entity_id, 'state': st.state, 'in_progress': bool(prog), 'percentage': pct,
            'installed': a.get('installed_version'), 'latest': a.get('latest_version')}


def _update_entity(ents, device_id):
    return next((e for e in er.async_entries_for_device(ents, device_id) if e.domain == 'update'), None)


def fw_int(v):
    """OTA file version as int, from an int or a '0x11033399' string."""
    if v is None:
        return None
    if isinstance(v, int):
        return v
    try:
        return int(str(v).strip(), 16)
    except ValueError:
        return None


def sense_info(zigpy_dev, fallback_fw=None):
    """(quirk's 0xfc57 on ep1, OTA file version, 0xfc57 present but without the quirk) from zigpy's cache."""
    has = raw = old_quirk = False
    try:
        cl = zigpy_dev.endpoints[v5.ENDPOINT].in_clusters[v5.CLUSTER]
        raw = True
        attrs = getattr(cl, 'attributes', {})
        has = v5.A_ZONE_STATE in attrs and v5.CMD_SOURCES in getattr(cl, 'server_commands', {})
        old_quirk = has and v5.A_HOST_API not in attrs
    except (KeyError, AttributeError, TypeError):
        pass
    fw = None
    try:
        for eid, ep in zigpy_dev.endpoints.items():
            if eid and OTA in getattr(ep, 'out_clusters', {}):
                fw = ep.out_clusters[OTA].get(OTA_FILE_VERSION)
                break
    except Exception:
        fw = None
    # IKEA, SONOFF and others have their own 0xfc57: only our manufacturer code counts as an unquirked Ripple device.
    ours = getattr(zigpy_dev, 'manufacturer_id', None) == v5.MANUF
    fw = fw_int(fw) if fw is not None else fw_int(fallback_fw)
    # A 5.0.2 device under a quirk without host_api (0xff4a) cannot be configured: ZHA must load the bundled quirk.
    return has, fw, (raw and not has and ours) or (old_quirk and fw is not None and fw >= v5.MIN_FW)


def cached_build_id(zigpy_dev):
    """Basic sw_build_id from zigpy's cache, if ZHA ever read it; no radio traffic."""
    try:
        v = zigpy_dev.endpoints[v5.ENDPOINT].in_clusters[BASIC].get(SW_BUILD_ID)
    except Exception:
        return None
    return None if v is None else str(v)


def _norm(v):
    if isinstance(v, (bytes, bytearray)):
        return bytes(v)
    try:
        return int(v)
    except (TypeError, ValueError):
        return v


async def zcl_read(cluster, attrs, manuf, timeout=30):
    kw = {} if manuf is None else {'manufacturer': manuf}
    known, missing = [], {}
    for a in attrs:
        try:
            cluster.find_attribute(a, **({} if manuf is None else {'manufacturer_code': manuf}))
            known.append(a)
        except (KeyError, ValueError):
            # zigpy 2.3 raises for ids the quirk does not define; treat as unsupported, no radio.
            missing[a] = 0x86
    if not known:
        return {}, missing
    ok, fail = await asyncio.wait_for(cluster.read_attributes(known, allow_cache=False, only_cache=False, **kw), timeout)
    return {a: _norm(v) for a, v in ok.items()}, {**missing, **{a: int(s) for a, s in fail.items()}}


async def zcl_write(cluster, attr, value, manuf, timeout=30):
    kw = {} if manuf is None else {'manufacturer': manuf}
    res = await asyncio.wait_for(cluster.write_attributes({attr: value}, **kw), timeout)
    recs = res[0] if res and isinstance(res[0], list) else (res or [])
    # No record for the attribute is not a success: the caller treats None as a failed write.
    return max((int(r.status) for r in recs if getattr(r, 'attrid', None) in (attr, None)), default=None)


async def zcl_command(cluster, cmd, payload, manuf, timeout=30):
    import zigpy.types as t
    rsp = await asyncio.wait_for(
        cluster.command(cmd, t.SerializableBytes(bytes(payload)), manufacturer=manuf, expect_reply=True), timeout)
    status = getattr(rsp, 'status', None)
    if status is None and isinstance(rsp, (list, tuple)) and len(rsp) > 1:
        status = rsp[1]
    return int(status) if status is not None else 0


def subscribe_cluster(cluster, cb):
    """cb(cluster_id, attr_id, value) on every attribute report or update; returns the unsubscribe function."""
    cid = cluster.cluster_id
    if hasattr(cluster, 'on_event'):
        # zigpy 2.3: reports emit attribute_report; attribute_updated only when a quirk changes the value.
        unsubs = [cluster.on_event(name, lambda ev: cb(cid, ev.attribute_id, _norm(ev.value)))
                  for name in ('attribute_report', 'attribute_updated')]
        return lambda: [u() for u in unsubs]

    class _Listener:
        def attribute_updated(self, attrid, value, *_):
            cb(cid, attrid, _norm(value))
    lst = _Listener()
    cluster.add_listener(lst)
    return lambda: cluster.remove_listener(lst)


class HassCore:
    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self.connected = asyncio.Event()
        self.connected.set()
        self.on_connect = []
        self.version = HA_VERSION
        self.last_error = None
        self._unsubs = []

    def zha_ready(self):
        from homeassistant.config_entries import ConfigEntryState
        return _zha_gateway(self.hass) is not None and any(
            e.state is ConfigEntryState.LOADED for e in self.hass.config_entries.async_entries('zha'))

    async def wait_ready(self, delay_s):
        """Returns once HA runs and ZHA is loaded; after a cold start, waits delay_s more for routes to form."""
        waited = False
        while not (self.hass.state is CoreState.running and self.zha_ready()):
            waited = True
            await asyncio.sleep(5)
        if waited and delay_s:
            _LOGGER.debug('ZHA ready, first reads in %s s', delay_s)
            await asyncio.sleep(delay_s)

    def on_event(self, event_type, cb):
        @callback
        def _handle(ev):
            cb({'data': dict(ev.data)})
        self._unsubs.append(self.hass.bus.async_listen(event_type, _handle))

    def close(self):
        for u in self._unsubs:
            u()
        self._unsubs.clear()

    def _zdev(self, ieee):
        gw = _zha_gateway(self.hass)
        if gw is None:
            return None
        for k, d in getattr(gw, 'devices', {}).items():
            if str(k) == ieee:
                return d
        return None

    def _zigpy(self, ieee):
        zigpy_dev = getattr(self._zdev(ieee), 'device', None)
        if zigpy_dev is None:
            raise CoreError('not_found', f'ZHA device {ieee} not found')
        return zigpy_dev

    async def reinterview(self, ieee, timeout=180):
        """What ZHA's Reconfigure does: zigpy reads the endpoints again, then ZHA rebuilds the device."""
        gw = _zha_gateway(self.hass)
        fn = getattr(gw, 'async_reinterview_device', None)
        if fn is None:
            raise CoreError('unsupported', 'this ZHA version cannot re-interview a device')
        zdev = self._zdev(ieee)
        if zdev is None:
            raise CoreError('not_found', f'ZHA device {ieee} not found')
        await asyncio.wait_for(fn(zdev.ieee), timeout)

    async def zdo_binds(self, ieee, timeout=30):
        """Binding table through ZDO Mgmt_Bind_req, in the reply shape that bindings.parse_binds reads."""
        dev = self._zigpy(ieee)
        entries, idx, total = [], 0, 0
        for _ in range(16):
            rsp = await asyncio.wait_for(dev.zdo.Mgmt_Bind_req(idx), timeout)
            status, total, start, lst = int(rsp[0]), int(rsp[1]), int(rsp[2]), list(rsp[3] or [])
            if status:
                raise CoreError('refused', f'Mgmt_Bind_rsp status 0x{status:02x}')
            for b in lst:
                a = b.DstAddress
                mode = int(a.addrmode)
                entries.append({'SrcEndpoint': int(b.SrcEndpoint), 'ClusterId': int(b.ClusterId),
                                'DstAddress': {'addrmode': mode,
                                               'nwk': int(a.nwk) if mode == 1 else None,
                                               'ieee': str(a.ieee) if mode == 3 else None,
                                               'endpoint': int(a.endpoint) if mode == 3 else None}})
            idx = start + len(lst)
            if not lst or idx >= total:
                break
        return {'replies': [[0, total, 0, entries]]}

    async def _zdo_bind(self, cmd, ieee, src_ep, cluster, dst, dst_ep, timeout):
        import zigpy.types as t
        import zigpy.zdo.types as zdo_t
        dev = self._zigpy(ieee)
        addr = zdo_t.MultiAddress(addrmode=3, ieee=t.EUI64.convert(dst), endpoint=int(dst_ep))
        rsp = await asyncio.wait_for(getattr(dev.zdo, cmd)(dev.ieee, int(src_ep), int(cluster), addr), timeout)
        status = int(rsp[0]) if isinstance(rsp, (list, tuple)) and rsp else 0
        if status:
            raise CoreError('refused', f'{cmd} status 0x{status:02x}')

    async def zdo_bind(self, ieee, src_ep, cluster, dst, dst_ep, timeout=30):
        await self._zdo_bind('Bind_req', ieee, src_ep, cluster, dst, dst_ep, timeout)

    async def zdo_unbind(self, ieee, src_ep, cluster, dst, dst_ep, timeout=30):
        await self._zdo_bind('Unbind_req', ieee, src_ep, cluster, dst, dst_ep, timeout)

    def _cluster(self, ieee, cluster_id):
        zigpy_dev = self._zigpy(ieee)
        try:
            return zigpy_dev.endpoints[v5.ENDPOINT].in_clusters[cluster_id]
        except (KeyError, AttributeError) as e:
            raise CoreError('not_found', f'{ieee} has no cluster 0x{cluster_id:04x} on endpoint 1') from e

    async def zcl_read(self, ieee, cluster_id, attrs, manuf):
        return await zcl_read(self._cluster(ieee, cluster_id), attrs, manuf)

    async def zcl_write(self, ieee, cluster_id, attr, value, manuf):
        return await zcl_write(self._cluster(ieee, cluster_id), attr, value, manuf)

    async def zcl_command(self, ieee, cluster_id, cmd, payload, manuf):
        return await zcl_command(self._cluster(ieee, cluster_id), cmd, payload, manuf)

    def clusters(self, ieee):
        """The zigpy cluster objects 0xfc57 and 0x0406 that receive the reports now, None where missing."""
        out = []
        for cid in (v5.CLUSTER, v5.OCCUPANCY):
            try:
                out.append(self._cluster(ieee, cid))
            except CoreError:
                out.append(None)
        return tuple(out)

    def subscribe(self, ieee, cb):
        """cb(ieee, cluster_id, attr_id, value) for reports of 0xfc57 and 0x0406 on endpoint 1."""
        unsubs = []
        for cid in (v5.CLUSTER, v5.OCCUPANCY):
            try:
                unsubs.append(subscribe_cluster(self._cluster(ieee, cid), lambda c, a, v: cb(ieee, c, a, v)))
            except CoreError:
                continue

        def unsub():
            for u in unsubs:
                u()
        return unsub

    def _devices(self):
        gw = _zha_gateway(self.hass)
        if gw is None:
            return []
        ents = er.async_get(self.hass)
        zha_entries = zha_registry_entries(self.hass)
        topo = {}
        try:
            for ieee, neigh in gw.application_controller.topology.neighbors.items():
                topo[str(ieee)] = [str(n.ieee) for n in neigh]
        except Exception:
            pass
        out = []
        for k, d in getattr(gw, 'devices', {}).items():
            ieee = str(k)
            zdev = getattr(d, 'device', None)
            try:
                has_onoff = any(0x0006 in ep.in_clusters for eid, ep in zdev.endpoints.items() if eid)
            except Exception:
                has_onoff = False
            entry = zha_entries.get(ieee.lower())
            upd = _update_entity(ents, entry.id) if entry else None
            sense, fw, unquirked = sense_info(zdev, getattr(d, 'firmware_version', None) or (entry.sw_version if entry else None))
            # loaded before the bundled quirk was registered: no quirk at all on one of our models
            unquirked = unquirked or (bool(quirk.models()) and (getattr(zdev, 'manufacturer', None), getattr(zdev, 'model', None)) in quirk.models()
                                      and not hasattr(zdev, quirk.QUIRK_ATTR))
            dtype = getattr(d, 'device_type', None)
            if getattr(d, 'is_coordinator', False):
                dtype = 'Coordinator'
            out.append({
                'ieee': ieee, 'nwk': int(d.nwk) if getattr(d, 'nwk', None) is not None else None,
                'manufacturer': getattr(d, 'manufacturer', None), 'model': getattr(d, 'model', None),
                'name': getattr(d, 'name', ieee), 'user_given_name': entry.name_by_user if entry else None,
                'area_id': entry.area_id if entry else None, 'device_reg_id': entry.id if entry else None,
                'available': bool(getattr(d, 'available', False)), 'device_type': str(dtype) if dtype else None,
                'lqi': getattr(d, 'lqi', None), 'rssi': getattr(d, 'rssi', None),
                'last_seen': getattr(d, 'last_seen', None), 'neighbors': [{'ieee': n} for n in topo.get(ieee, [])],
                'has_onoff': has_onoff, 'sense': sense, 'fw': fw, 'unquirked': unquirked,
                'manuf_id': getattr(zdev, 'manufacturer_id', None),
                'sw_build_id': cached_build_id(zdev),
                'update': update_info(self.hass.states.get(upd.entity_id)) if upd else None,
            })
        return out

    def _endpoints(self, ieee):
        d = self._zdev(ieee)
        zdev = getattr(d, 'device', None)
        if zdev is None:
            return []
        entry = zha_registry_entries(self.hass).get(ieee.lower())
        names = {}
        if entry:
            for e in er.async_entries_for_device(er.async_get(self.hass), entry.id):
                parts = str(e.unique_id).split('-')
                if e.domain in ('switch', 'light') and len(parts) >= 2 and parts[1].isdigit():
                    st = self.hass.states.get(e.entity_id)
                    names[int(parts[1])] = {'name': (st.attributes.get('friendly_name') if st else None) or e.name or e.original_name,
                                            'entity_id': e.entity_id}
        out = []
        for eid, ep in zdev.endpoints.items():
            if not eid or eid == 242:
                continue
            out.append({'ep': eid, 'onoff_in': 0x0006 in ep.in_clusters, 'onoff_out': 0x0006 in ep.out_clusters,
                        **names.get(eid, {'name': None, 'entity_id': None})})
        return out

    def _firmware(self):
        ents = er.async_get(self.hass)
        out = []
        for ieee, entry in zha_registry_entries(self.hass).items():
            upd = _update_entity(ents, entry.id)
            st = self.hass.states.get(upd.entity_id) if upd else None
            image_type = None
            try:
                zdev = getattr(self._zdev(ieee), 'device', None)
                for eid, ep in zdev.endpoints.items():
                    if eid and 0x0019 in ep.out_clusters:
                        image_type = ep.out_clusters[0x0019]._attr_cache.get(0x0008)
                        break
            except Exception:
                pass
            out.append({'ieee': ieee, 'sw_version': entry.sw_version, 'image_type': image_type,
                        'update_entity': upd.entity_id if upd else None, 'state': st.state if st else None,
                        'installed': st.attributes.get('installed_version') if st else None,
                        'latest': st.attributes.get('latest_version') if st else None,
                        'in_progress': st.attributes.get('in_progress') if st else None})
        return out

    def ieee_of_entity(self, entity_id):
        """IEEE of the ZHA device that owns an entity, or None."""
        ent = er.async_get(self.hass).async_get(entity_id)
        dev = dr.async_get(self.hass).async_get(ent.device_id) if ent and ent.device_id else None
        return next((str(v).lower() for k, v in (dev.connections if dev else ()) if k == dr.CONNECTION_ZIGBEE), None)

    async def call(self, msg, timeout=30):
        t = msg['type']
        hass = self.hass
        if t == 'get_services':
            return hass.services.async_services()
        if t == 'zha/devices':
            return self._devices()
        if t == 'config/area_registry/list':
            return [{'area_id': a.id, 'name': a.name} for a in ar.async_get(hass).async_list_areas()]
        if t == 'config/device_registry/list':
            return [{'id': d.id, 'sw_version': d.sw_version, 'name_by_user': d.name_by_user, 'area_id': d.area_id,
                     'name': d.name} for d in _registry_entries(dr.async_get(hass))]
        if t == 'ripple/endpoints':
            return self._endpoints(msg['ieee'])
        if t == 'ripple/firmware':
            return self._firmware()
        if t == 'call_service':
            resp = await hass.services.async_call(msg['domain'], msg['service'], msg.get('service_data') or {},
                                                  blocking=True, return_response=bool(msg.get('return_response')))
            return {'response': resp}
        raise CoreError('unknown_command', t)

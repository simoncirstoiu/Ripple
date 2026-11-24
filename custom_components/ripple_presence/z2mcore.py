"""Adapter that answers Ripple's requests through Zigbee2MQTT, over Home Assistant's MQTT integration.
Same interface as HassCore; radio traffic goes through the Ripple external converter."""
from __future__ import annotations

import asyncio
import itertools
import json
import logging
import os

from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from . import v5
from .hacore import CoreError, _update_entity, update_info

_LOGGER = logging.getLogger(__name__)
DEFAULT_BASE = 'zigbee2mqtt'
SENSE_NAMES = ('rippleSense', str(v5.CLUSTER))
UNSUPPORTED = 0x86
FLASH_KEY = 'ripple_flash'
PERMIT_MAX_S = 254
OTA_TIMEOUT_S = 3600


def safe_info(info):
    """The parts of bridge/info worth keeping; its config holds the network key and passwords."""
    out = {k: info.get(k) for k in ('version', 'commit', 'zigbee_herdsman', 'zigbee_herdsman_converters',
                                    'coordinator', 'permit_join', 'restart_required')}
    net = info.get('network')
    if isinstance(net, dict):
        out['network'] = {'channel': net.get('channel')}
    adv = (info.get('config') or {}).get('advanced')
    if isinstance(adv, dict):
        out['config'] = {'advanced': {k: adv.get(k) for k in ('enable_external_js', 'log_level')}}
    return out


def _short(payload):
    """A firmware image is sent as hex; the log keeps only its size."""
    if isinstance(payload, dict) and isinstance(payload.get('hex'), dict):
        return {**payload, 'hex': {**payload['hex'], 'data': f"<{len(payload['hex'].get('data') or '') // 2} bytes>"}}
    return payload


def to_z2m(ieee):
    """a4:c1:38:... -> 0xa4c138..."""
    return '0x' + ieee.replace(':', '').lower()


def from_z2m(addr):
    """0xa4c138... -> a4:c1:38:..."""
    h = str(addr).lower().removeprefix('0x').rjust(16, '0')
    return ':'.join(h[i:i + 2] for i in range(0, 16, 2))


def _norm(v):
    if isinstance(v, dict) and isinstance(v.get('hex'), str):
        return bytes.fromhex(v['hex'])
    return v


def _out(v):
    if isinstance(v, (bytes, bytearray)):
        return {'hex': bytes(v).hex()}
    return v


def _sense_info(d, state):
    """(has the sensing cluster, firmware version, served by another converter) from bridge/devices and the state."""
    ep1 = (d.get('endpoints') or {}).get('1') or {}
    has = any(n in SENSE_NAMES for n in (ep1.get('clusters') or {}).get('input') or [])
    upd = state.get('update') if isinstance(state.get('update'), dict) else {}
    fw = upd.get('installed_version')
    ours = (d.get('definition') or {}).get('vendor') == 'Ripple'
    return has, fw if isinstance(fw, int) else None, has and not ours


class Z2MCore:
    stack = 'z2m'
    stack_name = 'Zigbee2MQTT'

    def __init__(self, hass: HomeAssistant, base=DEFAULT_BASE):
        self.hass = hass
        self.base = base.rstrip('/')
        self.connected = asyncio.Event()
        self.on_connect = []
        self.version = HA_VERSION
        self.last_error = None
        self.bridge = {'state': None, 'info': None}
        self._devs = {}
        self._names = {}
        self._states = {}
        self._avail = {}
        self._seen = {}
        self._listeners = {}
        self._pending = {}
        self._ids = itertools.count(1)
        self._prefix = os.urandom(3).hex()
        self._unsubs = []
        self._loaded = asyncio.Event()
        self.converters = None
        self.converter_error = None
        self._state_waits = {}
        self._ota_progress = {}

    # ---- MQTT plumbing
    async def start(self):
        from homeassistant.components import mqtt
        if not await mqtt.async_wait_for_mqtt_client(self.hass):
            self.last_error = 'MQTT is not set up in Home Assistant'
            raise CoreError('no_mqtt', self.last_error)
        self._unsubs.append(await mqtt.async_subscribe(self.hass, f'{self.base}/#', self._on_message, encoding='utf-8'))

    async def wait_ready(self, delay_s):
        """Waits until Zigbee2MQTT has published its device list."""
        try:
            await self.start()
            await asyncio.wait_for(self._loaded.wait(), timeout=max(delay_s, 30))
        except (CoreError, asyncio.TimeoutError) as e:
            self.last_error = self.last_error or f'Zigbee2MQTT did not publish {self.base}/bridge/devices'
            _LOGGER.warning('Zigbee2MQTT not ready: %s', e)
        self.connected.set()

    async def backend_up(self):
        return self._loaded.is_set() and self.bridge['state'] != 'offline'

    def close(self):
        for u in self._unsubs:
            u()
        self._unsubs.clear()
        for f in self._pending.values():
            if not f.done():
                f.cancel()
        self._pending.clear()

    async def _publish(self, topic, payload):
        from homeassistant.components import mqtt
        _LOGGER.debug('MQTT out %s %s', topic, _short(payload))
        await mqtt.async_publish(self.hass, topic, json.dumps(payload))

    @callback
    def _on_message(self, msg):
        topic = msg.topic[len(self.base) + 1:]
        try:
            data = json.loads(msg.payload) if msg.payload else None
        except ValueError:
            data = msg.payload
        if topic.startswith('bridge/'):
            self._on_bridge(topic[7:], data)
            return
        if topic.endswith('/availability'):
            name = topic[:-13]
            ieee = self._names.get(name)
            if ieee:
                st = data.get('state') if isinstance(data, dict) else data
                self._avail[ieee] = st == 'online'
            return
        ieee = self._names.get(topic)
        if ieee is None or not isinstance(data, dict):
            return
        skip = ('ripple', 'ripple_reply', FLASH_KEY)
        self._states[ieee] = {**self._states.get(ieee, {}), **{k: v for k, v in data.items() if k not in skip}}
        self._on_flash_state(ieee, data)
        if 'ripple_reply' in data or 'ripple' in data:
            _LOGGER.debug('MQTT in %s %s', msg.topic, {k: data.get(k) for k in ('ripple', 'ripple_reply')})
        self._on_reply(data.get('ripple_reply'))
        self._on_report(ieee, data.get('ripple'), msg.retain)

    def _on_bridge(self, what, data):
        if what == 'state':
            self.bridge['state'] = data.get('state') if isinstance(data, dict) else data
        elif what == 'info' and isinstance(data, dict):
            self.bridge['info'] = safe_info(data)
        elif what == 'converters' and isinstance(data, list):
            self.converters = {c.get('name'): c.get('code') for c in data if isinstance(c, dict)}
        elif what == 'devices' and isinstance(data, list):
            self._devs = {from_z2m(d['ieee_address']): d for d in data if d.get('ieee_address')}
            self._names = {d.get('friendly_name') or d['ieee_address']: i for i, d in self._devs.items()}
            self._names.update({d['ieee_address']: i for i, d in self._devs.items()})
            if self._loaded.is_set():
                for cb in list(self.on_connect):
                    self.hass.async_create_task(cb())
            self._loaded.set()
        elif what.startswith('response/'):
            _LOGGER.debug('MQTT in bridge/%s %s', what, data)
            if isinstance(data, dict):
                f = self._pending.pop(str(data.get('transaction')), None)
                if f and not f.done():
                    f.set_result(data)

    def _on_flash_state(self, ieee, data):
        if FLASH_KEY in data:
            for f in self._state_waits.pop(ieee, []):
                if not f.done():
                    f.set_result(data[FLASH_KEY])
        upd = data.get('update')
        cb = self._ota_progress.get(ieee)
        if cb and isinstance(upd, dict) and isinstance(upd.get('progress'), (int, float)):
            cb(float(upd['progress']))

    def _on_reply(self, rep):
        if not isinstance(rep, dict):
            return
        f = self._pending.pop(str(rep.get('id')), None)
        if f and not f.done():
            f.set_result(rep)

    def _on_report(self, ieee, rep, retained):
        """A converter report is new when its (boot, sequence) differs from the last one seen for the device."""
        if not isinstance(rep, dict) or rep.get('ep') != 1:
            return
        key = (rep.get('b'), rep.get('n'))
        last = self._seen.get(ieee)
        self._seen[ieee] = key
        if key == last or (last is None and retained):
            return
        for cb in list(self._listeners.get(ieee, ())):
            for a, v in (rep.get('attrs') or {}).items():
                try:
                    cb(ieee, int(rep['cluster']), int(a), _norm(v))
                except Exception:
                    _LOGGER.exception('report listener')

    def _topic(self, ieee):
        d = self._devs.get(ieee.lower())
        if d is None:
            raise CoreError('not_found', f'Zigbee2MQTT device {ieee} not found')
        return f'{self.base}/{d.get("friendly_name") or d["ieee_address"]}'

    async def _request(self, ieee, req, timeout=30):
        rid = f'{self._prefix}-{next(self._ids)}'
        fut = self.hass.loop.create_future()
        self._pending[rid] = fut
        try:
            await self._publish(f'{self._topic(ieee)}/set', {'ripple': {'id': rid, **req, 'timeout': timeout * 1000}})
            rep = await asyncio.wait_for(fut, timeout + 5)
        finally:
            self._pending.pop(rid, None)
        if rep.get('ok'):
            return rep
        status = rep.get('status')
        if isinstance(status, int):
            raise Refused(status, f'{req["op"]} status 0x{status:02x}: {rep.get("error")}')
        raise CoreError('failed', str(rep.get('error')))

    async def bridge_request(self, path, payload, timeout=30):
        """bridge/request/<path> with a transaction id; returns the bridge/response payload."""
        tid = f'{self._prefix}-{next(self._ids)}'
        fut = self.hass.loop.create_future()
        self._pending[tid] = fut
        try:
            await self._publish(f'{self.base}/bridge/request/{path}', {**payload, 'transaction': tid})
            rep = await asyncio.wait_for(fut, timeout)
        finally:
            self._pending.pop(tid, None)
        if rep.get('status') != 'ok':
            raise CoreError('failed', str(rep.get('error')))
        return rep.get('data')

    async def ensure_converter(self, name, code):
        """Saves the Ripple converter in Zigbee2MQTT unless the same code is already there; True when it was saved."""
        if self.converters is not None and self.converters.get(name) == code:
            self.converter_error = None
            return False
        try:
            await self.bridge_request('converter/save', {'name': name, 'code': code}, timeout=60)
        except (CoreError, asyncio.TimeoutError) as e:
            self.converter_error = str(e) or 'no answer from Zigbee2MQTT'
            _LOGGER.warning('Ripple converter not saved in Zigbee2MQTT: %s', self.converter_error)
            return False
        self.converter_error = None
        _LOGGER.info('Ripple converter saved in Zigbee2MQTT as %s', name)
        return True

    # ---- radio
    async def zcl_read(self, ieee, cluster_id, attrs, manuf):
        try:
            rep = await self._request(ieee, {'op': 'read', 'ep': 1, 'cluster': cluster_id, 'attrs': list(attrs), 'manuf': manuf})
        except CoreError as e:
            st = _status_of(e)
            if st is None:
                raise
            return {}, {a: st for a in attrs}
        got = {int(k): _norm(v) for k, v in (rep.get('attrs') or {}).items()}
        return {a: got[a] for a in attrs if a in got}, {a: UNSUPPORTED for a in attrs if a not in got}

    async def zcl_write(self, ieee, cluster_id, attr, value, manuf):
        try:
            await self._request(ieee, {'op': 'write', 'ep': 1, 'cluster': cluster_id, 'attrs': {str(attr): _out(value)}, 'manuf': manuf})
        except CoreError as e:
            st = _status_of(e)
            if st is None:
                raise
            return st
        return 0

    async def zcl_command(self, ieee, cluster_id, cmd, payload, manuf):
        try:
            await self._request(ieee, {'op': 'command', 'ep': 1, 'cluster': cluster_id, 'cmd': cmd,
                                       'payload': _out(bytes(payload)), 'manuf': manuf})
        except CoreError as e:
            st = _status_of(e)
            if st is None:
                raise
            return st
        return 0

    async def zdo_binds(self, ieee, timeout=30):
        """Binding table in the shape HassCore returns."""
        rep = await self._request(ieee, {'op': 'binds'}, timeout)
        entries = []
        for b in rep.get('entries') or []:
            if b.get('group') is not None:
                dst = {'addrmode': 1, 'nwk': int(b['group'])}
            else:
                dst = {'addrmode': 3, 'ieee': from_z2m(b['dst']), 'endpoint': b.get('dst_ep')}
            entries.append({'SrcEndpoint': b.get('src_ep'), 'ClusterId': b.get('cluster'), 'DstAddress': dst})
        return {'replies': [[0, len(entries), 0, entries]]}

    async def zdo_bind(self, ieee, src_ep, cluster, dst, dst_ep, timeout=30):
        await self._request(ieee, {'op': 'bind', 'src_ep': src_ep, 'cluster': cluster, 'dst': to_z2m(dst), 'dst_ep': dst_ep}, timeout)

    async def zdo_unbind(self, ieee, src_ep, cluster, dst, dst_ep, timeout=30):
        await self._request(ieee, {'op': 'unbind', 'src_ep': src_ep, 'cluster': cluster, 'dst': to_z2m(dst), 'dst_ep': dst_ep}, timeout)

    def subscribe(self, ieee, cb):
        """cb(ieee, cluster_id, attr_id, value) for reports of 0xfc57 and 0x0406 on endpoint 1."""
        ieee = ieee.lower()
        self._listeners.setdefault(ieee, []).append(cb)

        def unsub():
            lst = self._listeners.get(ieee, [])
            if cb in lst:
                lst.remove(cb)
        return unsub

    # ---- firmware install, through the generic converters every Zigbee2MQTT device has
    async def plain_read(self, ieee, cluster, attrs, options=None, timeout=20):
        """Attribute values by name; the result comes back in the device state under FLASH_KEY."""
        ieee = ieee.lower()
        fut = self.hass.loop.create_future()
        self._state_waits.setdefault(ieee, []).append(fut)
        req = {'cluster': cluster, 'attributes': list(attrs), 'state_property': FLASH_KEY}
        if options:
            req['options'] = options
        try:
            await self._publish(f'{self._topic(ieee)}/set', {'read': req})
            got = await asyncio.wait_for(fut, timeout)
        finally:
            lst = self._state_waits.get(ieee, [])
            if fut in lst:
                lst.remove(fut)
        return got if isinstance(got, dict) else {}

    async def plain_write(self, ieee, cluster, attr, value, data_type):
        """Fire and forget: Zigbee2MQTT does not report the outcome of a write over MQTT."""
        await self._publish(f'{self._topic(ieee)}/set',
                            {'write': {'cluster': cluster, 'payload': {str(attr): {'value': value, 'type': data_type}}}})

    async def permit_join(self, seconds):
        await self.bridge_request('permit_join', {'time': min(int(seconds), PERMIT_MAX_S)})

    async def ota_install(self, ieee, image, progress=None, timeout=OTA_TIMEOUT_S):
        """Installs an OTA file through Zigbee2MQTT's own OTA, which takes the image as hex."""
        ieee = ieee.lower()
        if progress:
            self._ota_progress[ieee] = progress
        try:
            return await self.bridge_request('device/ota_update/update',
                                             {'id': to_z2m(ieee), 'hex': {'data': image.hex(), 'file_name': 'ripple.ota'}},
                                             timeout=timeout)
        finally:
            self._ota_progress.pop(ieee, None)

    async def reinterview(self, ieee, timeout=180):
        await self.bridge_request('device/interview', {'id': to_z2m(ieee)}, timeout=timeout)

    def shown_model(self, ieee):
        return (self._devs.get(ieee.lower()) or {}).get('model_id')

    # ---- registries
    def _ha_device(self, ieee):
        ident = f'zigbee2mqtt_{to_z2m(ieee)}'
        return next((d for d in dr.async_get(self.hass).devices.values()
                     if any(dom == 'mqtt' and i == ident for dom, i in d.identifiers)), None)

    def _devices(self):
        out = []
        for ieee, d in self._devs.items():
            st = self._states.get(ieee, {})
            reg = self._ha_device(ieee)
            upd = _update_entity(er.async_get(self.hass), reg.id) if reg else None
            sense, fw, unquirked = _sense_info(d, st)
            name = d.get('friendly_name')
            has_onoff = any('genOnOff' in ((ep.get('clusters') or {}).get('input') or [])
                            for ep in (d.get('endpoints') or {}).values())
            out.append({
                'ieee': ieee, 'nwk': d.get('network_address'), 'manufacturer': d.get('manufacturer'),
                'model': d.get('model_id'), 'name': name or ieee,
                'user_given_name': name if name and name != d.get('ieee_address') else None,
                'area_id': reg.area_id if reg else None, 'device_reg_id': reg.id if reg else None,
                'available': self._avail.get(ieee, not d.get('disabled')), 'device_type': d.get('type'),
                'lqi': st.get('linkquality'), 'rssi': None, 'last_seen': st.get('last_seen'), 'neighbors': [],
                'has_onoff': has_onoff, 'sense': sense, 'fw': fw, 'unquirked': unquirked, 'manuf_id': None,
                'sw_build_id': d.get('software_build_id'),
                'update': update_info(self.hass.states.get(upd.entity_id)) if upd else None,
            })
        return out

    def _endpoints(self, ieee):
        d = self._devs.get(ieee.lower())
        if d is None:
            return []
        reg = self._ha_device(ieee)
        ents = er.async_entries_for_device(er.async_get(self.hass), reg.id) if reg else []
        out = []
        for eid, ep in sorted((d.get('endpoints') or {}).items(), key=lambda kv: int(kv[0])):
            eid = int(eid)
            if not eid or eid == 242:
                continue
            cl = ep.get('clusters') or {}
            label = ep.get('name')
            hit = next((e for e in ents if e.domain in ('switch', 'light') and label
                        and str(e.unique_id).endswith(f'_{label}_zigbee2mqtt')), None)
            st = self.hass.states.get(hit.entity_id) if hit else None
            out.append({'ep': eid, 'onoff_in': 'genOnOff' in (cl.get('input') or []),
                        'onoff_out': 'genOnOff' in (cl.get('output') or []),
                        'name': ((st.attributes.get('friendly_name') if st else None) or hit.name or hit.original_name) if hit else None,
                        'entity_id': hit.entity_id if hit else None})
        return out

    def _firmware(self):
        ents = er.async_get(self.hass)
        out = []
        for ieee in self._devs:
            reg = self._ha_device(ieee)
            upd = _update_entity(ents, reg.id) if reg else None
            st = self.hass.states.get(upd.entity_id) if upd else None
            out.append({'ieee': ieee, 'sw_version': reg.sw_version if reg else None, 'image_type': None,
                        'update_entity': upd.entity_id if upd else None, 'state': st.state if st else None,
                        'installed': st.attributes.get('installed_version') if st else None,
                        'latest': st.attributes.get('latest_version') if st else None,
                        'in_progress': st.attributes.get('in_progress') if st else None})
        return out

    def ieee_of_entity(self, entity_id):
        """IEEE of the Zigbee2MQTT device that owns an entity, or None."""
        ent = er.async_get(self.hass).async_get(entity_id)
        dev = dr.async_get(self.hass).async_get(ent.device_id) if ent and ent.device_id else None
        for dom, i in (dev.identifiers if dev else ()):
            if dom == 'mqtt' and str(i).startswith('zigbee2mqtt_0x'):
                ieee = from_z2m(str(i)[12:])
                return ieee if ieee in self._devs else None
        return None

    async def call(self, msg, timeout=30):
        t = msg['type']
        if t == 'get_services':
            return self.hass.services.async_services()
        if t == 'zha/devices':
            return self._devices()
        if t == 'config/area_registry/list':
            return [{'area_id': a.id, 'name': a.name} for a in ar.async_get(self.hass).async_list_areas()]
        if t == 'config/device_registry/list':
            return [{'id': d.id, 'sw_version': d.sw_version, 'name_by_user': d.name_by_user, 'area_id': d.area_id,
                     'name': d.name} for d in dr.async_get(self.hass).devices.values()]
        if t == 'ripple/endpoints':
            return self._endpoints(msg['ieee'])
        if t == 'ripple/firmware':
            return self._firmware()
        if t == 'call_service':
            resp = await self.hass.services.async_call(msg['domain'], msg['service'], msg.get('service_data') or {},
                                                       blocking=True, return_response=bool(msg.get('return_response')))
            return {'response': resp}
        raise CoreError('unknown_command', t)


class Refused(CoreError):
    """The device answered with a ZCL status other than success."""

    def __init__(self, status, message):
        super().__init__('refused', message)
        self.status = status


def _status_of(e):
    """ZCL status carried by a refused request, or None for network-level failures."""
    return getattr(e, 'status', None)

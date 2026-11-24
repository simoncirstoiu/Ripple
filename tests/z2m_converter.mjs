// Node check of the generated Zigbee2MQTT converter against zigbee-herdsman-converters (ZHC_DIR = its node_modules).
import { createRequire } from 'node:module';
import path from 'node:path';

const [file, zhcDir] = [process.argv[2], process.env.ZHC_DIR];
const require = createRequire(path.join(zhcDir, 'x.js'));
const zhc = require('zigbee-herdsman-converters');
const defs = createRequire(import.meta.url)(path.resolve(file));
const fails = [];
const eq = (what, got, want) => { if (JSON.stringify(got) !== JSON.stringify(want)) fails.push(`${what}: ${JSON.stringify(got)} != ${JSON.stringify(want)}`); };

for (const d of defs) zhc.addExternalDefinition(d);
const def = await zhc.findByDevice({ modelID: 'TS0002-IND-T', manufacturerName: 'ptjcjise', endpoints: [], type: 'Router' });
eq('definition for TS0002-IND-T', [def?.vendor, def?.model], ['Ripple', 'TS0002-IND-T']);
eq('one definition per model', defs.flatMap((d) => d.zigbeeModel).length, new Set(defs.flatMap((d) => d.zigbeeModel)).size);
const fz = def.fromZigbee.find((c) => c.cluster === 'rippleSense');
const occ = def.fromZigbee.find((c) => c.cluster === 'msOccupancySensing');
const tz = def.toZigbee.find((c) => c.key && c.key.includes('ripple'));

const calls = [];
const ep = (id) => ({
  ID: id,
  read: async (cl, attrs, o) => { calls.push(['read', cl, attrs, o.manufacturerCode]); return { 0xfff0: Buffer.from([1, 2]), 0xff40: 7 }; },
  write: async (cl, attrs, o) => { calls.push(['write', cl, attrs, o.manufacturerCode]); },
  command: async (cl, cmd, payload, o) => { calls.push(['command', cl, cmd, payload, o.manufacturerCode]); },
  bind: async (cl, dst) => { calls.push(['bind', cl, dst.ID ?? dst]); },
  unbind: async (cl, dst) => { calls.push(['unbind', cl, dst.ID ?? dst]); },
});
class Dev {
  static byIeeeAddr(ieee) { return ieee === '0xa4c138000000000b' ? other : undefined; }
  constructor(ieee) { this.ieeeAddr = ieee; this.customClusters = {}; this.eps = { 1: ep(1), 3: ep(3) }; }
  getEndpoint(id) { return this.eps[id]; }
  addCustomCluster(name, def) { this.customClusters[name] = def; }
  async bindingTable() { return [{ sourceEndpoint: 1, clusterId: 6, destAddrMode: 3, dest: '0xa4c138000000000b', destEndpoint: 3 }]; }
}
const dev = new Dev('0xa4c138000000000a');
const other = new Dev('0xa4c138000000000b');
let published;
const meta = { device: dev, publish: (p) => { published = p; } };
const run = async (req) => { published = undefined; await tz.convertSet(dev.getEndpoint(1), 'ripple', req, meta); return published.ripple_reply; };

let r = await run({ id: 1, op: 'read', ep: 1, cluster: 'rippleSense', attrs: [0xfff0, 0xff40] });
eq('read reply', [r.ok, r.attrs], [true, { 65520: { hex: '0102' }, 65344: 7 }]);
eq('read uses the Ripple manufacturer code', calls.at(-1)[3], 0x1141);
r = await run({ id: 2, op: 'write', ep: 1, cluster: 'rippleSense', attrs: { 0xff4a: 5, 0xff40: { hex: 'aabb' } } });
eq('write reply', r.ok, true);
eq('write payload', [calls.at(-1)[2].a_ff4a, Buffer.isBuffer(calls.at(-1)[2].a_ff40), calls.at(-1)[3]], [5, true, 0x1141]);
r = await run({ id: 3, op: 'command', ep: 1, cluster: 'rippleSense', cmd: 1, payload: { hex: '0102' } });
eq('command reply', r.ok, true);
r = await run({ id: 4, op: 'binds' });
eq('binds', r.entries, [{ src_ep: 1, cluster: 6, mode: 3, dst: '0xa4c138000000000b', group: null, dst_ep: 3 }]);
r = await run({ id: 5, op: 'bind', src_ep: 1, cluster: 6, dst: '0xa4c138000000000b', dst_ep: 3 });
eq('bind', [r.ok, calls.at(-1)], [true, ['bind', 6, 3]]);
r = await run({ id: 6, op: 'nope' });
eq('unknown op fails with a reply', [r.id, r.ok], [6, false]);

const rep = fz.convert(def, { endpoint: { ID: 1 }, cluster: 'rippleSense', device: dev, data: { 0xfff0: Buffer.from([9]) }, type: 'attributeReport' }, () => {}, {}, meta).ripple;
eq('report', [rep.ep, rep.cluster, rep.attrs], [1, 0xfc57, { 65520: { hex: '09' } }]);
const o = occ.convert(def, { endpoint: { ID: 1 }, cluster: 'msOccupancySensing', device: dev, data: { occupancy: 1 }, type: 'attributeReport' }, () => {}, {}, meta).ripple;
eq('occupancy report', [o.cluster, o.attrs], [0x0406, { 0: 1 }]);

console.log(fails.length ? fails.join('\n') : `z2m converter OK (${defs.length} definitions)`);
process.exit(fails.length ? 1 : 0);

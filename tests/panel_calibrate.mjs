// Node check of the calibration buttons: one per line and one per room on the room page, none on the device page.
import { readFileSync } from 'node:fs';
const src = readFileSync(new URL('../custom_components/ripple_presence/frontend/ripple-panel.js', import.meta.url), 'utf8');
const pick = (name) => src.match(new RegExp(`  ${name}\\([^)]*\\) \\{[\\s\\S]*?\\n  \\}`))[0];
const one = (name) => src.match(new RegExp(`  ${name}\\([^)]*\\) \\{.*\\}\\n`))[0];
const h = (tag, attrs, ...kids) => ({ tag, attrs: attrs || {}, kids: kids.flat(Infinity).filter((k) => k != null && k !== false) });
const names = ['lines', 'roomPage', 'linesTable', 'lineRow', 'histCard', 'memo', 'freshLine', 'calibrateRoom', 'calibrateLine', 'devicePage', 'tuneValues', 'lineLive', 'lineItem'];
const P = new Function('h', 'lineKey', 'reachOf', 'clock', 'S_MAX', 'TO_BACKEND', 'memoNode',
  `return class { ${names.map(pick).join(' ')} ${one('calSeconds')} }`)(h, (rx, tx) => `${rx}<${tx}`, () => null, () => 'never', 100, {}, (k, sig, build) => { memos.push([k, sig]); return build(); });
const memos = [];
const p = new P();
const sw = { hall: { ieee: 'hall', name: 'Hall', links: [{ ieee: 'stairs', sens: 70 }, { ieee: 'door', sens: 70 }] },
  stairs: { ieee: 'stairs', name: 'Stairs', links: [{ ieee: 'hall', sens: 70 }] } };
p.sw = (i) => sw[i];
p.devName = (i) => (sw[i] || {}).name || i;
p.devLink = (i) => i;
p._rooms = () => [room];
p.room = (id) => (id === room.id ? room : null);
p.loadHist = p.histRow = p.histDlg = p.moreInfo = () => null;
p.fwBadge = p.switchSettings = p.tunePanel = p.roomField = p.roomTriggerField = p.roomSaveBar = () => null;
p.S = { live: {}, lv: {}, lineEdit: {}, cal: {}, log: [], dedit: {}, open: {}, hist: {} };
p._st = { switches: Object.values(sw) };
const calls = [];
p._call = (type, data, ok) => { calls.push([type, data, ok]); return Promise.resolve(true); };
const room = { id: 'area:hall', name: 'Hall', members: ['hall', 'stairs'], cal_s: 600 };
const all = (n, out = []) => { if (n && typeof n === 'object') { if (n.tag) out.push(n); (n.kids || n).forEach?.((k) => all(k, out)); } return out; };
const text = (n) => (typeof n === 'string' ? n : (n.kids || []).map(text).join(''));
const buttons = (tree, label) => all(tree).filter((n) => n.tag === 'button' && text(n) === label);
const fails = [];
const eq = (what, got, want) => { if (JSON.stringify(got) !== JSON.stringify(want)) fails.push(`${what}: ${JSON.stringify(got)} != ${JSON.stringify(want)}`); };

const page = p.roomPage(room);
eq('one Calibrate room button', buttons(page, 'Calibrate room').length, 1);
eq('a Calibrate button per line of the room', buttons(page, 'Calibrate').length, 3);
buttons(page, 'Calibrate room')[0].attrs.onclick();
eq('room calibration with the room duration', calls.pop().slice(0, 2), ['calibrate', { room_id: 'area:hall', seconds: 600 }]);
p.S.cal['area:hall'] = 120;
buttons(page, 'Calibrate')[1].attrs.onclick();
eq('line calibration of hall <- door', calls.pop().slice(0, 2), ['line/calibrate', { rx: 'hall', tx: 'door', seconds: 120 }]);
for (const [v, want] of [[10, 60], [5000, 1800], [0, 300]]) {
  p.S.cal['area:hall'] = v;
  eq(`duration ${v} clamped`, p.calSeconds(room), want);
}
eq('no Calibrate room without lines', buttons(p.roomPage({ ...room, members: [] }), 'Calibrate room')[0].attrs.disabled, true);
const dev = all(p.devicePage({ ieee: 'hall', name: 'Hall', links: sw.hall.links, settings: { cal_s: 300 } }));
eq('no calibration button on the device page', dev.filter((n) => n.tag === 'button' && /calibrat/i.test(text(n))).length, 0);
eq('no calibration call from the device page', /_call\('calibrate'/.test(pick('devicePage')), false);
// memoized rows: an unchanged line is not rebuilt, and a kept row's button acts on the room as it is now
delete p.S.cal['area:hall'];
memos.length = 0;
const first = buttons(p.roomPage(room), 'Calibrate');
const rows = memos.filter(([k]) => !k.includes('|') && k.includes('<'));
eq('every line row is memoized by its line key', rows.map(([k]) => k).sort(), ['hall<door', 'hall<stairs', 'stairs<hall']);
eq('a row signature names its room', rows.every(([, sig]) => sig.includes('area:hall')), true);
const loaded = { ...room, cal_s: 900 };  // _load() brings new objects
p.room = (id) => (id === room.id ? loaded : null);
first[0].attrs.onclick();
eq('kept row calibrates with the current room duration', calls.pop().slice(0, 2), ['line/calibrate', { rx: 'hall', tx: 'stairs', seconds: 900 }]);
console.log(fails.length ? fails.join('\n') : 'panel calibration buttons OK');
process.exit(fails.length ? 1 : 0);

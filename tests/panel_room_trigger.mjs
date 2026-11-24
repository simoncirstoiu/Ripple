// Node check of the room trigger field: select any/all/custom, a number 1..N only for custom, clamp note, save bar.
import { readFileSync } from 'node:fs';
const src = readFileSync(new URL('../custom_components/ripple_presence/frontend/ripple-panel.js', import.meta.url), 'utf8');
const pick = (name) => src.match(new RegExp(`  ${name}\\([^)]*\\) \\{[\\s\\S]*?\\n  \\}`))[0];
const h = (tag, attrs, ...kids) => ({ tag, attrs: attrs || {}, kids: kids.flat(Infinity).filter((k) => k != null && k !== false) });
const P = new Function('h', `return class { ${pick('roomTriggerField')} ${pick('roomSaveBar')} }`)(h);
const p = new P();
p.S = { redit: {}, rmsg: {} };
p.render = () => {};
const all = (n, f, out = []) => { if (n && typeof n === 'object') { if (f(n)) out.push(n); (n.kids || []).forEach((k) => all(k, f, out)); } return out; };
const text = (n) => (typeof n === 'string' ? n : (n.kids || []).map(text).join(''));
const ok = (c, m) => { if (!c) { console.error('FAIL', m); process.exit(1); } };
const room = (trigger) => ({ id: 'r', settings: { off_s: 10, trigger_mode: trigger.mode, trigger_k: trigger.k }, trigger });

let r = room({ mode: 'any', k: null, threshold: 1, active: 1, total: 4, clamped: false });
let f = p.roomTriggerField(r);
let sel = all(f, (n) => n.tag === 'select')[0];
ok(sel && all(sel, (n) => n.tag === 'option').map((o) => o.attrs.value).join() === 'any,all,custom', 'three options');
ok(all(sel, (n) => n.tag === 'option' && n.attrs.selected)[0].attrs.value === 'any', 'any selected');
ok(!all(f, (n) => n.tag === 'input').length, 'no number for any');
ok(text(f).includes('1 of 4 lines detecting, the room needs 1'), 'status line');
ok(text(f).includes('older than 5.0.5 counts as one line'), 'help says how old switches count');
ok(p.roomSaveBar(r) === null, 'nothing to save');

sel.attrs.onchange({ target: { value: 'custom' } });
f = p.roomTriggerField(r);
const num = all(f, (n) => n.tag === 'input')[0];
ok(num && num.attrs.min === 1 && num.attrs.max === 4 && num.attrs.value === 2, 'number 1..N for custom, starts at 2');
ok(text(f).includes('of 4'), 'shows of N');
let bar = p.roomSaveBar(r);
ok(text(bar).includes('2 settings changed'), 'mode and k to save: ' + text(bar));

p.S.redit.r = { trigger_mode: 'custom', trigger_k: 7 };
ok(text(p.roomSaveBar(r)).includes('out of range: trigger_k (1-4)'), 'k above N refused');

p.S.redit = {};
r = room({ mode: 'custom', k: 4, threshold: 3, active: 3, total: 3, clamped: true });
f = p.roomTriggerField(r);
ok(text(f).includes('fewer lines than the 4 chosen, so it uses 3'), 'clamp shown');
ok(p.roomSaveBar(r) === null, 'a clamped k is not a change');
p.S.redit.r = { trigger_mode: 'all' };
bar = p.roomSaveBar(r);
ok(text(bar).includes('1 setting changed'), 'only the mode is sent for all: ' + text(bar));
console.log('room trigger panel: ok');

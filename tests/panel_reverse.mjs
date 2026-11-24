// Node check of the panel binding rules (revOf, dirTag) with v4-production-like switches and a plain device.
import { readFileSync } from 'node:fs';
const src = readFileSync(new URL('../custom_components/ripple_presence/frontend/ripple-panel.js', import.meta.url), 'utf8');
const pick = (name) => src.match(new RegExp(`  ${name}\\([^)]*\\) \\{[\\s\\S]*?\\n  \\}`))[0];
const P = new Function(`return class { ${pick('revOf')} ${pick('dirTag')} ${pick('readAt')} ${pick('allBinds')} ${pick('findB')} }`)();
const p = new P();
// main: 2-gang switch (buttons 1-2, relays 3-4); aux: 1-gang switch (button 1, relay 2); plug: not ours
const N = { main: 2, aux: 1, plug: 1 };
p.isOurs = (i) => i !== 'plug';
p.relays = (i) => N[i];
p.S = { eps: { main: [1], aux: [1], plug: [1] }, binds: {
  main: { at: 1, controls: [{ src_ep: 1, dst_ieee: 'aux', dst_ep: 2 }] },
  aux: { at: 1, controls: [{ src_ep: 1, dst_ieee: 'main', dst_ep: 3 }] } } };
const fwd = { src: 'main', sep: 1, dst: 'aux', dep: 2 }, back = { src: 'aux', sep: 1, dst: 'main', dep: 3 };
const fails = [];
const eq = (what, got, want) => { if (JSON.stringify(got) !== JSON.stringify(want)) fails.push(`${what}: ${JSON.stringify(got)} != ${JSON.stringify(want)}`); };
eq('reverse of main->aux', p.revOf(fwd), back);
eq('reverse of aux->main', p.revOf(back), fwd);
eq('main->aux both ways', p.dirTag(fwd), 'both ways');
eq('aux->main both ways', p.dirTag(back), 'both ways');
delete p.S.binds.aux.controls[0];
p.S.binds.aux.controls = [];
eq('reverse read and absent', p.dirTag(fwd), 'one way');
delete p.S.binds.aux;
eq('reverse source never read', p.dirTag(fwd), 'reverse not read');
eq('target without our firmware: no reverse', p.revOf({ src: 'main', sep: 1, dst: 'plug', dep: 1 }), null);
eq('target without our firmware: one way', p.dirTag({ src: 'main', sep: 1, dst: 'plug', dep: 1 }), 'one way');
console.log(fails.length ? fails.join('\n') : 'panel binding rules OK');
process.exit(fails.length ? 1 : 0);

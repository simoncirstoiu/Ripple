// Node check of the Live gauge of a 5.0.4+ switch: the switch sends d = 0 on every sample it does not store,
// so a 0 record must not empty the gauge; it shows the peak d of the last LIVE_PEAK_MS and falls back once quiet.
import { readFileSync } from 'node:fs';
const src = readFileSync(new URL('../custom_components/ripple_presence/frontend/ripple-panel.js', import.meta.url), 'utf8');
const pick = (name) => src.match(new RegExp(`  ${name}\\([^)]*\\) \\{[\\s\\S]*?\\n  \\}`))[0];
const top = (re, dflt) => (src.match(re) || [dflt])[0];
const lib = [top(/const S_MAX = .*\n/), top(/const LIVE_PEAK_MS = .*\n/, ''), top(/const SENS_DEFAULT = .*\n/), top(/const MOTION_TAB_5 = [\s\S]*?\];\n/),
  top(/function motionParams5\(s\) \{[\s\S]*?\n\}\n/),
  top(/function meterS\(dev\) \{[\s\S]*?\n\}\n/)].join('');
const P = new Function('lineKey', `${lib} return [class { ${pick('_simStep')} }, meterS];`)((rx, tx) => `${rx}<${tx}`);
const [C, meterS] = P;
const p = new C();
p.sw = () => ({ sense_api: 6, links: [{ ieee: 'tx' }] });
const fails = [];
const eq = (what, got, want) => { if (JSON.stringify(got) !== JSON.stringify(want)) fails.push(`${what}: ${JSON.stringify(got)} != ${JSON.stringify(want)}`); };
const k = 'rx<tx';
const step = (ms, d) => { p._simStep(k, 'rx', { tx: 'tx', ms, d }); return p._sim[k].meter; };
eq('quiet line: empty gauge', step(0, 0), null);
eq('a stored sample moves the gauge', step(100, 6), meterS(6));
eq('the unstored samples after it keep it', [200, 400, 800, 1099].map((t) => step(t, 0)), Array(4).fill(meterS(6)));
eq('a smaller stored sample inside the window keeps the peak', step(1000, 2), meterS(6));
eq('the peak leaves the window, the smaller one stays', step(1100, 0), meterS(2));
eq('a larger one takes over at once', step(1150, 9), meterS(9));
eq('quiet for a full window: empty again', step(2200, 0), null);
eq('a larger deviation reads a lower s (30 dB 1, 3 dB 50)', meterS(9) < meterS(2), true);
if (fails.length) { console.error(fails.join('\n')); process.exit(1); }
console.log('panel_live_gauge: ok');

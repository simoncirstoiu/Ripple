// Ripple sidebar panel, on live data from the integration.
const CSS = `
:host {
  display: block; min-height: 100vh;
  --bg: var(--primary-background-color, #fafafa); --card: var(--ha-card-background, var(--card-background-color, #fff));
  --text: var(--primary-text-color, #212121); --muted: var(--secondary-text-color, #727272); --line: var(--divider-color, rgba(0, 0, 0, .12));
  --primary: var(--primary-color, #009ac7); --on: var(--state-active-color, #ffc107); --ok: var(--success-color, #43a047);
  --warn: var(--error-color, #db4437); --chip: var(--secondary-background-color, #e5e5e5); --sim: var(--accent-color, #ff9800);
  font: 14px/1.45 var(--ha-font-family-body, Roboto, Noto, sans-serif); background: var(--bg); color: var(--text);
}
:host([dark]) { --nav-active: var(--primary); }
* { box-sizing: border-box; }
header { position: sticky; top: 0; z-index: 5; background: var(--app-header-background-color, var(--primary)); color: var(--app-header-text-color, #fff); border-bottom: var(--app-header-border-bottom, none); display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); align-items: center; gap: clamp(8px, 2vw, 24px); padding: 0 clamp(8px, 2vw, 16px); min-height: 56px; }
header h1 { font-size: 20px; font-weight: 400; margin: 0; display: flex; align-items: center; gap: 4px; }
header ha-menu-button { --mdc-icon-button-size: 40px; }
nav#nav { display: flex; gap: 4px; justify-self: center; overflow-x: auto; max-width: 100%; }
nav#nav button { white-space: nowrap; background: none; border: 0; color: inherit; opacity: .7; font: inherit; padding: 18px 12px; border-bottom: 2px solid transparent; cursor: pointer; }
nav#nav button.on { opacity: 1; color: var(--nav-active, var(--app-header-text-color)); border-bottom-color: currentColor; }
.mock { justify-self: end; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 100%; font-size: 12px; border: 1px dashed var(--accent-color); color: var(--accent-color); padding: 4px 8px; border-radius: 4px; }
main { max-width: 1280px; margin: 0 auto; padding: clamp(8px, 2vw, 16px); }
.card { container-type: inline-size; min-width: 0; background: var(--card); border-radius: var(--ha-card-border-radius, 12px); border: var(--ha-card-border-width, 1px) solid var(--ha-card-border-color, var(--line)); box-shadow: var(--ha-card-box-shadow, none); padding: 16px; margin-bottom: 16px; }
.card h2 { font-size: 18px; font-weight: 500; margin: 0 0 4px; }
.card .sub { color: var(--muted); margin: 0 0 12px; }
.row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.spacer { flex: 1; }
button.btn { font: inherit; font-weight: 500; border-radius: 18px; padding: 8px 16px; cursor: pointer; border: 1px solid var(--line); background: var(--card); color: var(--text); }
button.btn.pri { background: var(--primary); border-color: var(--primary); color: var(--text-primary-color); }
button.btn.live { background: var(--warn); border-color: var(--warn); color: var(--text-primary-color); }
button.btn:disabled { opacity: .4; cursor: default; }
button.link { background: none; border: 0; color: var(--primary); font: inherit; cursor: pointer; padding: 0; }
.chip { display: inline-flex; align-items: center; gap: 6px; background: var(--chip); border-radius: 16px; padding: 4px 6px 4px 12px; }
.chip button { background: none; border: 0; color: var(--muted); cursor: pointer; font-size: 16px; line-height: 1; }
.chip button.link { color: var(--primary); font-size: inherit; font-weight: 500; }
.state { display: inline-block; border-radius: 12px; padding: 2px 10px; font-size: 12px; font-weight: 500; }
.state.occ { background: color-mix(in srgb, var(--on) 20%, transparent); color: var(--on); }
.state.free { background: var(--chip); color: var(--muted); }
.state.det { background: color-mix(in srgb, var(--on) 20%, transparent); color: var(--on); }
.state.calm { background: var(--chip); color: var(--muted); }
.state.livetag { background: color-mix(in srgb, var(--warn) 20%, transparent); color: var(--warn); margin-right: 6px; }
.state.upd.busy { background: color-mix(in srgb, var(--primary) 18%, transparent); color: var(--primary); }
.state.upd { background: color-mix(in srgb, var(--warn) 18%, transparent); color: var(--warn); margin-left: 6px; }
.col { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
.col > .card { margin-bottom: 0; }
.state.novote { background: transparent; border: 1px dashed var(--muted); color: var(--muted); }
.rooms { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }
.rooms .card { cursor: pointer; margin: 0; }
table { width: 100%; border-collapse: collapse; }
th { text-align: left; font-weight: 500; color: var(--muted); font-size: 12px; padding: 6px 8px; border-bottom: 1px solid var(--line); }
td { padding: 10px 8px; border-bottom: 1px solid var(--line); vertical-align: middle; }
.linename b { font-weight: 500; }
button.devlink { font-weight: 500; }
.linename small { display: block; color: var(--muted); }
.gauge { position: relative; height: 14px; width: 100%; background: var(--chip); border-radius: 7px; overflow: visible; }
.gauge { background-image: repeating-linear-gradient(90deg, transparent 0 calc(10% - 1px), var(--line) calc(10% - 1px) 10%); }
.gauge .fill { position: absolute; right: 0; top: 0; bottom: 0; border-radius: 7px; background: var(--primary); transition: width .1s; }
.gauge .fill.over { background: var(--on); }
.gauge .mark { position: absolute; top: -4px; bottom: -4px; width: 2px; background: var(--text); }
.gauge .mark.pend { background: transparent; border-left: 2px dashed var(--text); width: 0; }
.gscale { display: flex; justify-content: space-between; font-size: 11px; color: var(--muted); }
.gauge.idle .fill { width: 0 !important; }
.gauge .marks { display: contents; }
.gnote { font-size: 12px; color: var(--muted); min-height: 32px; line-height: 16px; margin-top: 4px; }
.lrow { display: grid; grid-template-columns: minmax(120px, 1.3fr) minmax(84px, .6fr) minmax(140px, 1.4fr) minmax(190px, 1.6fr) minmax(80px, .7fr) max-content;
  grid-template-areas: "name state gauge sens last acts"; gap: 4px 12px; align-items: center; padding: 10px 8px; border-bottom: 1px solid var(--line); }
.lrow > * { min-width: 0; }
.lrow.lhead { padding: 6px 8px; color: var(--muted); font-size: 12px; font-weight: 500; }
.lrow.hit { background: color-mix(in srgb, var(--on) 12%, transparent); }
.lrow.mod { box-shadow: inset 3px 0 var(--primary); }
.c-name { grid-area: name; overflow-wrap: anywhere; } .c-state { grid-area: state; } .c-gauge { grid-area: gauge; }
.c-state .vote { display: block; color: var(--muted); font-size: 11px; }
.c-sens { grid-area: sens; } .c-last { grid-area: last; } .c-acts { grid-area: acts; }
@container (max-width: 760px) {
  .lrow.lhead { display: none; }
  .lrow { grid-template-columns: minmax(0, 1fr) auto; grid-template-areas: "name state" "gauge gauge" "sens sens" "last last" "acts acts"; }
  .c-acts { justify-content: flex-start; }
  .c-last::before { content: attr(data-label) ": "; color: var(--muted); }
}
.tscroll { overflow-x: auto; }
.tscroll table { min-width: 480px; }
.empty.left { text-align: left; padding: 8px 0; }
.gap-top { margin-top: 16px; }
input.num { width: 7ch; min-width: 64px; }
.pair { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 380px), 1fr)); gap: 16px; align-items: stretch; margin-bottom: 16px; }
.pair > .card { margin-bottom: 0; }
.pair.top { align-items: start; }
.field.inline { grid-template-columns: minmax(120px, 34%) minmax(0, 1fr) auto; align-items: center; }
.field.inline .name { display: flex; flex-direction: column; gap: 2px; }
.field.inline .help { grid-column: 2; }
.field.inline .ctl { grid-column: 3; grid-row: 1; flex-direction: row; align-items: center; gap: 6px; }
details.fw > summary { cursor: pointer; font-size: 18px; font-weight: 500; }
details.fw > summary small { font-size: 13px; font-weight: 400; color: var(--muted); margin-left: 8px; }
details.fw[open] > summary { margin-bottom: 4px; }
.pair .log { max-height: 260px; }
.acts-row { display: flex; gap: 6px; justify-content: flex-end; flex-wrap: wrap; }
.gnote.would { color: var(--on); font-weight: 500; }
.sens { display: flex; align-items: center; gap: 8px; }
.sens input[type=range] { flex: 1; min-width: 80px; }
.sens button.sensbox { flex: none; }
.sens button.sensbox { min-width: 52px; height: 34px; padding: 0 10px; border: 1px solid var(--line); border-radius: 8px; background: var(--input-fill-color, transparent); color: inherit; font: inherit; font-weight: 500; cursor: pointer; }
.sens button.sensbox:hover, .sens button.sensbox:focus-visible { border-color: var(--primary-color); outline: none; }
.sens button.sensbox.changed { border-color: var(--primary-color); color: var(--primary-color); }
dialog .sensrow { display: flex; align-items: center; justify-content: center; gap: 12px; margin: 16px 0 8px; }
dialog .sensrow .btn.step { width: 44px; height: 44px; padding: 0; font-size: 22px; }
dialog .sensrow input.sensnum { width: 96px; text-align: center; font-size: 24px; }
dialog .sensrng { display: flex; align-items: center; gap: 8px; color: var(--muted); }
dialog .sensrng input[type=range] { flex: 1; padding: 0; background: transparent !important; border: 0 !important; }
.sens output { width: 22px; text-align: right; font-weight: 500; }
.sens small { color: var(--muted); font-size: 11px; display: block; }
.savebar { position: sticky; bottom: 0; background: var(--card); border: 1px solid var(--primary); border-radius: 12px; padding: 12px 16px; display: flex; align-items: center; gap: 12px; margin-bottom: 16px; box-shadow: 0 -2px 12px color-mix(in srgb, var(--primary-background-color) 60%, transparent); }
.livebar { background: var(--warn); color: var(--text-primary-color); border-radius: 12px; padding: 10px 16px; display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-bottom: 16px; }
.calbar { background: var(--primary); color: var(--text-primary-color, #fff); border-radius: 12px; padding: 10px 16px; display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-bottom: 16px; }
.calbar .callist { display: flex; flex-direction: column; gap: 2px; }
.livebar button { background: var(--text-primary-color); color: var(--warn); border: 0; border-radius: 18px; padding: 6px 12px; font: inherit; cursor: pointer; }
.sim { border: 2px dashed var(--sim); }
.sim h2 { color: var(--sim); }
.field { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 4px 16px; padding: 12px 0; border-bottom: 1px solid var(--line); }
.field:last-child { border-bottom: 0; }
.field label { font-weight: 500; }
.field .help { grid-column: 1; color: var(--muted); font-size: 13px; }
.field .ctl { grid-column: 2; grid-row: 1 / span 2; display: flex; flex-direction: column; gap: 2px; align-items: flex-end; }
.field .ctl .in { display: flex; align-items: center; gap: 6px; }
.field input[type=number] { width: 8ch; min-width: 72px; font: inherit; padding: 6px 8px; border-radius: 6px; border: 1px solid var(--line); background: var(--card); color: var(--text); text-align: right; }
.field input.changed { border-color: var(--primary); box-shadow: 0 0 0 1px var(--primary); }
.field .def { font-size: 12px; color: var(--muted); }
.field .tech { font-size: 11px; color: var(--muted); font-family: ui-monospace, monospace; }
details.sec { border-top: 1px solid var(--line); }
details.sec summary { cursor: pointer; padding: 12px 0; font-weight: 500; font-size: 15px; }
details.sec summary small { font-weight: 400; color: var(--muted); margin-left: 8px; }
.tune { display: grid; grid-template-columns: minmax(130px, 200px) minmax(0, 1fr); gap: 24px; margin-top: 8px; }
.cats { display: flex; flex-direction: column; gap: 2px; border-right: 1px solid var(--line); padding-right: 12px; align-self: start; position: sticky; top: 8px; }
.cats button { display: flex; justify-content: space-between; align-items: center; text-align: left; background: none; border: 0; padding: 8px 10px; border-radius: 6px; color: var(--text); font: inherit; cursor: pointer; }
.cats button:hover { background: var(--chip); }
.cats button.on { background: var(--chip); font-weight: 600; box-shadow: inset 3px 0 0 var(--primary); }
.cats .n { background: var(--primary); color: var(--text-primary-color); border-radius: 10px; font-size: 11px; padding: 0 7px; }
.catbody h3 { margin: 0 0 4px; font-size: 16px; }
.catinfo { color: var(--muted); font-size: 13px; margin: 0 0 8px; }
.grp { font-size: 12px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; margin-top: 12px; }
details.adv { margin-top: 16px; border-top: 1px solid var(--line); }
details.adv > summary { cursor: pointer; padding: 12px 0 4px; font-weight: 500; }
details.adv > summary small { font-weight: 400; color: var(--primary); margin-left: 8px; }
details.more { margin-top: 4px; }
details.more summary { cursor: pointer; font-size: 12px; color: var(--primary); width: fit-content; }
details.more dl { display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: 4px 12px; margin: 6px 0 0; padding: 8px 10px; background: var(--chip); border-radius: 6px; }
details.more dt { font-weight: 500; color: var(--text); }
details.more dd { margin: 0; }
@container (max-width: 640px) {
  .field { grid-template-columns: minmax(0, 1fr); }
  .field .ctl { grid-column: 1; grid-row: auto; align-items: flex-start; }
  details.more dl { grid-template-columns: minmax(0, 1fr); }
  .tune { grid-template-columns: minmax(0, 1fr); }
}
@container (max-width: 420px) {
  .field.inline { grid-template-columns: minmax(0, 1fr) auto; }
  .field.inline .help { grid-column: 1 / span 2; grid-row: 2; }
  .field.inline .ctl { grid-column: 2; }
  .cats { flex-direction: row; overflow-x: auto; border-right: 0; border-bottom: 1px solid var(--line); padding: 0 0 8px; position: static; }
  .cats button { white-space: nowrap; }
}
.log { font-family: ui-monospace, monospace; font-size: 12px; max-height: 180px; overflow: auto; }
.log div { padding: 2px 0; }
.empty { color: var(--muted); padding: 16px 0; text-align: center; }
dialog { border: 0; border-radius: var(--ha-dialog-border-radius, 24px); padding: clamp(16px, 4vw, 24px); background: var(--card); color: var(--text); width: min(440px, calc(100vw - 32px)); box-shadow: var(--ha-card-box-shadow, 0 8px 32px rgba(0, 0, 0, .3)); }
dialog::backdrop { background: rgba(0,0,0,.4); }
dialog h3 { margin: 0 0 12px; font-weight: 500; }
dialog .acts { display: flex; justify-content: flex-end; gap: 8px; margin-top: 20px; }
dialog select, dialog input { font: inherit; padding: 8px; border-radius: 6px; border: 1px solid var(--line); background: var(--card); color: var(--text); width: 100%; }
dialog label { display: block; margin: 12px 0 4px; color: var(--muted); font-size: 13px; }
.crumb { color: var(--muted); margin-bottom: 8px; display: flex; align-items: center; gap: 4px; }
.bgroups { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 340px), 1fr)); gap: 20px 24px; margin-top: 8px; }
.bgh { color: var(--muted); font-size: 15px; font-weight: 500; margin: 0 0 8px 4px; }
.tiles { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.tile { display: flex; align-items: center; gap: 12px; min-width: 0; padding: 10px 12px; text-align: left; cursor: pointer; font: inherit; color: var(--text);
  background: var(--card); border: var(--ha-card-border-width, 1px) solid var(--ha-card-border-color, var(--line)); border-radius: var(--ha-card-border-radius, 12px); }
.tile:hover { background: color-mix(in srgb, var(--text) 5%, var(--card)); }
.tile:focus-visible { outline: 2px solid var(--primary); outline-offset: 1px; }
.tile .ti { flex: none; width: 24px; height: 24px; color: var(--muted); }
.tile .ti svg { width: 24px; height: 24px; fill: currentColor; display: block; }
.tile .tt { min-width: 0; display: flex; flex-direction: column; }
.tile .tn { font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tile .ts { color: var(--muted); font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tile.has .ti { color: var(--primary); }
dialog.wide { width: min(720px, calc(100vw - 32px)); max-height: calc(100vh - 48px); overflow: auto; }
tr.pickrow { cursor: pointer; }
tr.pickrow:hover { background: var(--secondary-background-color, rgba(127, 127, 127, .12)); }
p.fwwarn { color: var(--warn, var(--error-color)); }
input.bsearch { width: 100%; box-sizing: border-box; font: inherit; padding: 8px 12px; margin: 4px 0 12px; border: 1px solid var(--line); border-radius: 8px; background: var(--input-fill-color, transparent); color: inherit; }
@media (max-width: 600px) { .tiles { grid-template-columns: minmax(0, 1fr); } }
details.bdev { padding: 0; }
details.bdev > summary { cursor: pointer; padding: 14px 16px; display: flex; align-items: center; gap: 12px; }
details.bdev > summary .secondary { color: var(--muted); }
details.bdev .body { padding: 0 16px 16px; }
.btabs { display: flex; gap: 4px; margin: 12px 0 4px; border-bottom: 1px solid var(--line); overflow-x: auto; }
.btabs button { white-space: nowrap; background: none; border: 0; border-bottom: 2px solid transparent; color: inherit; font: inherit; font-size: 13px; padding: 10px 12px; min-height: 44px; cursor: pointer; opacity: .75; }
.btabs button.on { opacity: 1; font-weight: 600; border-bottom-color: var(--primary); }
dialog[tabindex]:focus { outline: none; }
.hpre .btn.on { background: var(--primary); border-color: var(--primary); color: var(--text-primary-color, #fff); font-weight: 600; }
.btabs button:disabled { opacity: .35; cursor: default; }
.btabs small { margin-left: 6px; color: var(--muted); }
.bgrp { font-size: 12px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; margin: 12px 0 4px; }
.bind { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px 12px; padding: 6px 0; min-height: 44px; border-bottom: 1px solid var(--line); }
.bind small { color: var(--muted); font-family: ui-monospace, monospace; font-size: 11px; margin-left: 4px; }
.bind .dir { display: inline-block; white-space: nowrap; margin-left: 8px; font-size: 11px; color: var(--muted); border: 1px solid var(--line); border-radius: 10px; padding: 1px 8px; }
.bform { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 180px), 1fr)); gap: 12px; align-items: end; margin-top: 16px; }
.bform label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--muted); }
.bform label.both { flex-direction: row; align-items: center; gap: 6px; min-height: 36px; font-size: 13px; color: var(--text); cursor: pointer; }
.bform label.both.off { color: var(--muted); cursor: default; }
.bform label.both input { width: 16px; height: 16px; margin: 0; accent-color: var(--primary); }
.brev { margin: 8px 0 0; font-size: 13px; color: var(--muted); }
.bform select { font: inherit; padding: 8px; border-radius: 6px; border: 1px solid var(--line); background: var(--card); color: var(--text); }
.bfoot { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-top: 12px; color: var(--muted); font-size: 13px; }
input[type=number], select, dialog input { background: var(--input-fill-color) !important; color: var(--text) !important; border: 0 !important; border-bottom: 1px solid var(--input-idle-line-color) !important; border-radius: 4px 4px 0 0 !important; }
input[type=number]:focus, select:focus, dialog input:focus { outline: none; border-bottom: 2px solid var(--primary-color) !important; }
select option { background: var(--card-background-color); color: var(--primary-text-color); }
input[type=range], input[type=checkbox] { accent-color: var(--primary-color); }
input.changed { border-bottom: 2px solid var(--primary-color) !important; box-shadow: none !important; }
@media (max-width: 600px) {
  header { grid-template-columns: minmax(0, 1fr); row-gap: 0; padding-top: 8px; }
  header h1 { justify-self: center; }
  .mock { display: none; }
  nav#nav { justify-self: center; }
  nav#nav button { padding: 12px 10px; }
}
.sent { display: block; }
.card.click { cursor: pointer; }
.card.click:hover { border-color: var(--primary); }
.hrow { display: grid; grid-template-columns: auto auto minmax(0, 1fr) auto; gap: 10px; padding: 2px 0; }
.hrow .hl { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hrow .hd, .hrow .hs { color: var(--muted); }
.hrow.on .hs { color: var(--primary); font-weight: 600; }
.hlog { max-height: 50vh; overflow: auto; margin-top: 8px; }
.hform input, .hform select { width: 100%; box-sizing: border-box; }
dialog .acts.hpre { justify-content: flex-start; flex-wrap: wrap; margin-top: 8px; }
@media (max-width: 600px) { .hrow { grid-template-columns: auto auto minmax(0, 1fr); } .hrow .hd { display: none; } }
.warnbox { border-color: var(--warning-color, #ffa600); }
`;

const TUNE = [
  ['gate', 'Movement check', [
    ['gate_age_ds', 'Movement stays valid for', 'How long a detected movement stays valid.', 0.5, 25.5, 0.1, 3, 's'],
    ['gate_gap_ds', 'Forget packets after a gap of', 'If no packet arrives for this long, the movement check starts over.', 0.5, 25.5, 0.1, 4, 's'],
  ]],
  ['learning', 'The empty room', [
    ['core_pct', 'Share for the empty-room level', 'A signal level seen in at least this share of empty-room packets is considered normal.', 1, 50, 1, 3, '%'],
    ['cal_min_rate', 'Calibrate: minimum capture rate above sensitivity 49', 'Calibrate sets a line above sensitivity 49 only if it stored at least this many packets per second during the capture; a slower line stays at 49 at most. 0 = no floor. Firmware 5.0.5 (5.0.4 does not read it; on 5.0.3 it is the old empty-room width limit, value x 2 = 1 dB steps).', 0, 8, 0.5, 1.5, 'fr/s'],
    ['blk_s', 'Averaging block length', 'The block used for the average, the packet rate and the "has it moved" check.', 2, 25, 1, 10, 's'],
    ['blk_thr_q', 'Block change counted as movement', 'A change of the block average this large counts as movement.', 0.25, 10, 0.25, 1, 'dB'],
    ['hist_cap', 'Calibration memory', 'During a calibration, when a level reaches this count, every count is halved.', 16, 255, 1, 127, ''],
    ['b_minc', 'Calibration noise allowance', 'Scale of the noise allowance computed at calibration. Higher ignores more of the line noise, so the line is less sensitive.', 0, 255, 1, 48, ''],
    ['cal_margin', 'Calibration margin', 'Calibrate puts the slider this many levels below the most sensitive point the empty room allows. 0 = chosen by the calibration length. Not on firmware 5.0.3.', 0, 34, 1, 0, 'levels'],
  ]],
  ['voting', 'When a line votes', [
    ['rate_state_d', 'Minimum packet rate, sender relay state known', 'The fewest packets per second for a line to vote.', 0.5, 10, 0.1, 2, 'packets/s'],
    ['rate_nostate_d', 'Minimum packet rate, sender relay state unknown', 'Same, when the sender relay state is unknown. At least the value above.', 0.5, 10, 0.1, 3, 'packets/s'],
    ['level_min', 'Weakest signal used', 'A line weaker than this does not vote.', -100, -40, 1, -90, 'dBm'],
    ['alive_s', 'A silent line stops voting after', 'A line not heard for this long no longer votes.', 2, 300, 1, 60, 's'],
  ]],
  ['relays', 'Relay effect', [
    ['relay_skip_ds', 'Ignore packets around a relay switch', 'Packets are ignored for this long around a relay switching, on this switch or on the sender.', 0, 5, 0.1, 1.5, 's'],
    ['quiet_q', 'Quiet block', 'The relay effect is learned only from a calm block (variation up to this much).', 0, 10, 0.25, 1, 'dB'],
    ['off_res_db', 'Largest learned correction', 'A larger correction is refused as "someone moved".', 1, 8, 1, 4, 'dB'],
    ['off_max_db', 'Largest relay effect', 'The largest relay effect that can be learned.', 1, 15, 1, 8, 'dB'],
  ]],
  ['reporting', 'Reporting to Home Assistant', [
    ['report_repeats', 'Resends of a change', 'How many times a presence change is resent if Home Assistant does not confirm it.', 0, 5, 1, 2, ''],
    ['report_repeat_ms', 'Pause between resends', 'The wait between resends.', 0.5, 30, 0.1, 5, 's'],
    ['heartbeat_min', 'Resend the state at least every', 'Sends the state again, even without a change.', 1, 1440, 1, 30, 'min'],
  ]],
];
const CAT = {
  gate: ['Movement check', 'A filter: a line detects only if the signal moved recently. It stops false detections when the signal level drifts slowly without anyone moving.'],
  learning: ['Empty room', 'A calibration records what the signal of each line looks like with the room empty, and the line compares against it from then on. The line never changes it by itself.'],
  voting: ['Voting', 'Which lines may vote for presence. Lines that are too weak, too slow or silent are left out of the vote.'],
  relays: ['Relays', 'When a relay switches, the radio signal changes a little. This is where you tune how that effect is ignored, so it is not taken for a person.'],
  reporting: ['Reporting', 'How the presence state reaches Home Assistant and how often it is resent.'],
};
// [essential, if raised, if lowered, when to change it]
const DETAIL = {
  gate_age_ds: [true, 'A detected movement stays valid longer, so detection continues more easily.', 'Detection needs more recent movement.',
    'When the room goes clear although you are in it and moving little.'],
  gate_gap_ds: [false, 'Tolerates longer gaps between packets.', 'After a short gap the check starts from zero.', 'Only on lines with rare or irregular packets.'],
  core_pct: [false, 'Only very frequent levels count as "empty room": the line is more sensitive.', 'More levels count as normal: the line is less sensitive.', 'Rarely.'],
  cal_min_rate: [false, 'More slow lines stay at sensitivity 49 after Calibrate: fewer false detections on them.', 'Calibrate may put slower lines above 49: more sensitive, more false detections.', 'When a slow line gives false detections after Calibrate: raise it.'],
  blk_s: [false, 'Smoother average, slower reaction to changes.', 'Faster reaction, noisier average.', 'Rarely.'],
  blk_thr_q: [false, 'A bigger change is needed for the block to count as "movement".', 'Small changes count as "movement" too.', 'Rarely.'],
  hist_cap: [false, 'A calibration keeps more detail.', 'A calibration halves its counts sooner.', 'Rarely.'],
  b_minc: [true, 'Ignores more noise: the line is less sensitive, with fewer false detections.', 'The line is more sensitive, but its noise counts more too.',
    'When a noisy line detects falsely even at low sensitivity.'],
  cal_margin: [false, 'After Calibrate the slider sits further from the false-detection edge: safer, a little less sensitive.', 'The slider sits closer to the edge: more sensitive, more risk of false detections.',
    'When a line still gives false detections right after Calibrate.'],
  rate_state_d: [false, 'Lines with few packets stop voting.', 'Slow lines vote too, and they are slower and less reliable.', 'Rarely.'],
  rate_nostate_d: [false, 'Same, when the sender relay state is unknown.', 'Same. Cannot be below the value above.', 'Rarely.'],
  level_min: [true, 'Towards -40: only strong lines vote.', 'Towards -100: weak lines vote too, and they are noisier.', 'When a weak line gives false detections.'],
  alive_s: [true, 'A silent line keeps voting for a while and can keep the room occupied.', 'A silent line leaves the vote quickly.', 'When the room stays occupied after a device stops sending.'],
  relay_skip_ds: [true, 'Ignores longer around a relay toggle: fewer false detections when the relay toggles, but a longer gap in detection.', 'The gap is shorter, but switching can cause a false detection.',
    'When a false detection appears right after you turn the light on or off.'],
  quiet_q: [false, 'The relay effect is learned from busier blocks too.', 'It is learned only from very calm blocks: safer, less often.', 'Rarely.'],
  off_res_db: [false, 'Larger corrections are accepted as relay effect.', 'Large corrections are treated as "someone moved".', 'Rarely.'],
  off_max_db: [false, 'A larger relay effect can be learned.', 'Large relay effects are no longer learned.', 'Rarely.'],
  report_repeats: [false, 'More certain that Home Assistant gets the change, with more radio traffic.', 'Less traffic, but a lost change arrives only at the next periodic resend.', 'When Home Assistant sometimes misses changes.'],
  report_repeat_ms: [false, 'Resends come less often.', 'Resends come more often.', 'Rarely.'],
  heartbeat_min: [true, 'Less traffic. A wrong state in Home Assistant is corrected later.', 'A wrong state is corrected sooner, with more traffic.', 'Rarely.'],
};
// Per-line sensitivity s 0-100 (firmware 5.0.3, v5.py MOTION_TAB): s -> (thr dB, M hits of the
// last 16 stored frames). A chain: s 100..1 is step 0..64, each step raises thr or M, so a lower s only removes hits.
const S_MAX = 100;
// the Live gauge of a 5.0.4+ device shows the peak meter deviation of the records of this last window (ms)
const LIVE_PEAK_MS = 1000;
const MOTION_TAB = [
  [1, 1], [1, 2], [1, 3], [1, 4], [1, 5], [1, 6], [1, 7], [1, 8], [2, 8], [2, 9], [2, 10], [2, 11], [2, 12], [3, 12],
  [3, 13], [3, 14], [4, 14], [4, 15], [4, 16], [5, 16], [6, 16], [7, 16], [8, 16], [9, 16], [10, 16], [11, 16],
  [12, 16], [13, 16], [14, 16], [15, 16], [16, 16], [17, 16], [18, 16], [19, 16], [20, 16], [21, 16], [22, 16],
  [23, 16], [24, 16], [25, 16], [26, 16], [27, 16], [28, 16], [29, 16], [30, 16], [31, 16], [32, 16], [33, 16],
  [34, 16], [35, 16], [36, 16], [37, 16], [38, 16], [39, 16], [40, 16], [41, 16], [42, 16], [43, 16], [44, 16],
  [45, 16], [46, 16], [47, 16], [48, 16], [49, 16], [50, 16]
];
const MOTION_PARKED_S = 70; // s 0 (parked) is measured at s 70 and never votes
function motionParams(s) {
  s = s || MOTION_PARKED_S;
  const n = MOTION_TAB.length;
  const i = s >= S_MAX ? 0 : Math.trunc(((S_MAX - s) * (n - 1) + Math.trunc((S_MAX - 1) / 2)) / (S_MAX - 1));
  return { db: MOTION_TAB[i][0], k: MOTION_TAB[i][1] };
}
const MP = Array.from({ length: S_MAX + 1 }, (_, s) => motionParams(s));
const popcount16 = (x) => { let c = 0; for (x &= 0xFFFF; x; x &= x - 1) c++; return c; };
// evidence of every s from the sim: e = s of the first one not reached, from 100 down, minus its fraction
function reachOf(S, H) {
  for (let k = S_MAX; k >= 1; k--) {
    const g = Math.min(1, S[k] / H[k]);
    if (g < 1) return { e: k - g, from: k < S_MAX ? k + 1 : null };
  }
  return { e: 0, from: 1 };
}
const SENS_DEFAULT = 50; // 5.0.4: the middle of the scale (5.0.3 started a line at 89)
// 5.0.4 scale (firmware SENSE_API 5, v5.py MOTION_TAB_5): s -> (thr in 0.25 dB, M); a stored frame weighs min(dev x 4 / thr, 3)
const MOTION_TAB_5 = [
  [4, 1], [4, 1], [4, 1], [4, 1], [4, 1], [4, 1], [4, 1], [4, 1], [4, 2], [4, 2], [4, 2], [4, 2], [4, 2], [4, 2], [4, 2],
  [4, 3], [4, 3], [4, 3], [4, 3], [4, 3], [4, 3], [4, 3], [4, 4], [4, 4], [4, 4], [4, 4], [4, 4], [4, 4], [4, 4], [4, 5],
  [4, 5], [4, 5], [4, 5], [4, 5], [4, 5], [4, 5], [4, 6], [4, 6], [4, 6], [4, 6], [4, 6], [4, 6], [4, 6], [4, 7], [4, 7],
  [4, 7], [4, 7], [4, 7], [4, 7], [4, 7], [4, 8], [5, 8], [5, 8], [6, 8], [7, 8], [8, 8], [8, 8], [9, 8], [10, 8], [11, 8],
  [11, 8], [12, 8], [13, 8], [14, 8], [14, 8], [15, 8], [16, 8], [16, 8], [17, 8], [18, 8], [19, 8], [19, 8], [20, 8], [21, 8],
  [22, 8], [22, 8], [23, 8], [24, 8], [25, 8], [25, 8], [26, 8], [27, 8], [28, 8], [28, 8], [29, 8], [30, 8], [30, 8], [31, 8],
  [32, 8], [33, 8], [33, 8], [34, 8], [35, 8], [36, 8], [36, 8], [37, 8], [38, 8], [39, 8], [39, 8], [40, 8]
];
function motionParams5(s) {
  s = s || SENS_DEFAULT;
  const n = MOTION_TAB_5.length;
  const i = s >= S_MAX ? 0 : Math.trunc(((S_MAX - s) * (n - 1) + Math.trunc((S_MAX - 1) / 2)) / (S_MAX - 1));
  return { q: MOTION_TAB_5[i][0], k: MOTION_TAB_5[i][1] };
}
// Live meter of 5.0.4: the lowest s at which this deviation, held 3 stored
// frames, fires (3 x w >= M); 100 when it fires nowhere. 30 dB reads 1, 3 dB 50, 1 dB 79, 0 dB 100.
const SLIDER_REST_MS = 150; // the thumb is at rest when it stayed on a value this long
const SLIDER_DRIFT = 3;      // at most this many steps of release drift are undone
function meterS(dev) {
  for (let s = 1; s <= S_MAX; s++) {
    const p = motionParams5(s);
    if (3 * Math.min(3, Math.trunc((dev * 4) / p.q)) >= p.k) return s;
  }
  return S_MAX;
}
const P_SWITCH = 'M7,2H17A2,2 0 0,1 19,4V20A2,2 0 0,1 17,22H7A2,2 0 0,1 5,20V4A2,2 0 0,1 7,2M7,4V20H17V4H7M9,6H15V12H9V6Z';
const P_DEVICE = 'M3,6H21V4H3C1.9,4 1,4.9 1,6V18A2,2 0 0,0 3,20H7V18H3V6M13,12H9V13.78C8.39,14.33 8,15.11 8,16C8,16.89 8.39,17.67 9,18.22V20H13V18.22C13.61,17.67 14,16.88 14,16C14,15.12 13.61,14.33 13,13.78V12M11,17.5A1.5,1.5 0 0,1 9.5,16A1.5,1.5 0 0,1 11,14.5A1.5,1.5 0 0,1 12.5,16A1.5,1.5 0 0,1 11,17.5M22,8H16A1,1 0 0,0 15,9V19A1,1 0 0,0 16,20H22A1,1 0 0,0 23,19V9A1,1 0 0,0 22,8M21,18H17V10H21V18Z';
const VOTE_TITLE = 'Live, firmware 5.0.5: whether this line counts in its zones now (a line with no zone or parked never votes).';
const API_LABEL = { update_firmware: 'update firmware', update_integration: 'update integration' };
const API_HELP = { update_firmware: 'Older than Ripple firmware 5.0.3: Ripple shows this device but changes nothing on it until the firmware is updated.',
  update_integration: 'Newer firmware than this integration knows: Ripple changes nothing on this device until the integration is updated.' };
const FIELD = {};
TUNE.forEach(([, , fs]) => fs.forEach((f) => { FIELD[f[0]] = f; }));
// display unit -> backend unit, for the one value whose unit differs
const TO_BACKEND = { report_repeat_ms: 1000 };

// Splits a text into sentences, one per line.
const SENT = /(?<=[.!?])\s+(?=[A-Z0-9"'(])/;
function h(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === 'key') e._key = v;
    else if (k.startsWith('on')) { (e._on ||= {})[k] = v; e[k] = v; }
    else if (k === 'class') e.className = v;
    else if (k === 'value') { e.value = v; e._val = String(v); }
    else if (k === 'props') Object.assign(e, v);
    else e.setAttribute(k, v === true ? '' : v);
  }
  const prose = tag === 'p' || tag === 'dd' || /\b(sub|help|catinfo|brev|gnote)\b/.test(e.className);
  kids.flat(Infinity).forEach((c) => {
    if (c == null || c === false) return;
    if (c.nodeType) { e.append(c); return; }
    const parts = prose ? String(c).split(SENT) : [String(c)];
    if (parts.length < 2) { e.append(String(c)); return; }
    parts.forEach((t) => { const sp = document.createElement('span'); sp.className = 'sent'; sp.textContent = t; e.append(sp); });
  });
  return e;
}

// A memoized element: a placeholder with its key, its signature (everything it shows) and how to build it.
// The signature is kept on the element on screen, written only once that element is fully patched, so a
// render that throws, or a value that could not be written, leaves no claim that the screen is up to date.
const memoNode = (key, sig, build) => { const c = document.createComment(''); c._key = key; c._sig = sig; c._build = build; return c; };
// Values morph left alone because their input has the focus; the elements around them are not up to date.
let skipped = 0;
// Builds the placeholders inside a new subtree before it goes on screen.
function realize(n) {
  if (n._build) {
    const el = realize(n._build());
    el._sig = n._sig;
    return el;
  }
  for (const c of [...n.childNodes]) if (c._build || c.firstChild) { const r = realize(c); if (r !== c) c.replaceWith(r); }
  return n;
}

// Patches the live DOM in place: only changed nodes, attributes and text are touched.
// Returns the node that is on screen afterwards.
function morph(a, b) {
  if (a === b) return a;
  if (b._build) {
    if (a._sig === b._sig) return a;
    const s0 = skipped;
    const el = morph(a, b._build());
    el._sig = skipped === s0 ? b._sig : null;  // a skipped focused value: rebuild on the next render
    return el;
  }
  // a node being patched no longer matches the signature it was built from; a patch that throws midway
  // must not leave it claiming so (the memo branch above writes the new one once the patch is complete)
  a._sig = null;
  if (a.nodeType !== b.nodeType || a.nodeName !== b.nodeName || a._keep) {
    if (a._keep) return a;
    const n = realize(b);
    a.replaceWith(n);
    return n;
  }
  if (a.nodeType !== 1) { if (a.data !== b.data) a.data = b.data; return a; }
  for (const { name } of [...a.attributes]) if (!b.hasAttribute(name)) a.removeAttribute(name);
  for (const { name, value } of [...b.attributes]) if (a.getAttribute(name) !== value) a.setAttribute(name, value);
  if (a.nodeName === 'DETAILS' && a.open !== b.open) a.open = b.open;
  for (const k of new Set([...Object.keys(a._on || {}), ...Object.keys(b._on || {})])) a[k] = b._on?.[k] || null;
  a._on = b._on;
  const focused = a === a.getRootNode().activeElement;
  if (b._val !== undefined && a.value !== b._val) { if (focused) skipped++; else a.value = b._val; }
  if (a.type === 'checkbox') a.checked = b.hasAttribute('checked');
  if (focused && a.nodeName === 'SELECT') { skipped++; return a; }
  patch(a, [...b.childNodes]);
  return a;
}
// Children with a key are matched by key (moved, kept or built), the others by order.
function patch(parent, nodes) {
  const old = [...parent.childNodes];
  const keyed = new Map();
  const free = [];
  for (const o of old) { if (o._key != null) keyed.set(o._key, o); else free.push(o); }
  let fi = 0;
  const kept = new Set();
  // 1. match the new children to the old ones
  const els = nodes.map((n) => {
    let a = n._key != null ? keyed.get(n._key) : free[fi++];
    if (a && kept.has(a)) a = null;
    const el = a ? morph(a, n) : realize(n);
    kept.add(el);
    return el;
  });
  // 2. remove the old children that are not kept, so the kept ones need no move
  for (const o of old) if (!kept.has(o) && o.parentNode === parent) o.remove();
  // 3. place in order, moving a node only when it is out of place. A node that holds the
  // focus or a pointer press is never moved (a move drops both): its siblings move instead.
  const active = parent.getRootNode().activeElement;
  const holds = (el) => el.nodeType === 1 && ((active && el.contains(active)) || el.matches(':active'));
  els.forEach((el, i) => {
    const at = parent.childNodes[i];
    if (at === el) return;
    if (el.parentNode === parent && parent.moveBefore) parent.moveBefore(el, at);
    else if (el.parentNode === parent && holds(el)) {
      while (parent.childNodes[i] !== el) parent.insertBefore(parent.childNodes[i], el.nextSibling);
    } else parent.insertBefore(el, at || null);
  });
}

// Dialog content: lists are flattened and empty items dropped (replaceChildren would print arrays as text).
const dlgSet = (d, ...kids) => d.replaceChildren(...kids.flat(Infinity).filter((k) => k != null && k !== false).map((k) => (k.nodeType ? realize(k) : k)));
const lineKey = (rx, tx) => `${rx}<${tx}`;
const clock = (ts) => (ts ? new Date(ts * 1000).toLocaleTimeString() : 'never');
// Time left until end (ms): 'm:ss' for Live, 'm:ss left' / 'finishing…' for a calibration.
const countdown = (end, fmt) => {
  const x = Math.max(0, Math.ceil((end - Date.now()) / 1000));
  const t = `${Math.floor(x / 60)}:${String(x % 60).padStart(2, '0')}`;
  return fmt === 'cal' ? (x > 0 ? `${t} left` : 'finishing…') : t;
};
const nowS = () => Date.now() / 1000;

// The unsubscribe of a subscription is only sent on the socket it was made on.
// Message ids start over on every new socket, so the old id sent there would cancel another subscription of this tab.
function dropOnSocket({ u, conn, sock }) {
  if (!conn.connected || conn.socket !== sock) return;
  try { Promise.resolve(u()).catch(() => {}); } catch (e) { /* the socket closed meanwhile */ }
}

class RipplePanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this.S = { open: {}, cat: {}, lineEdit: {}, redit: {}, rmsg: {}, dedit: {}, sedit: {}, smsg: {}, cal: {}, bopen: {}, bf: {}, bmsg: {},
      eps: {}, binds: {}, liveDefault: 300, live: {}, lv: {}, hist: {}, msg: null };
    this._st = null;
    this._zha = [];
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (hass && hass.themes) this.toggleAttribute('dark', !!hass.themes.darkMode);
    if (first) this._start();
    else if (this._watchConn()) this._resubscribe();
  }
  set narrow(v) { this._narrow = v; if (this._ready) this.render(); }
  set route(r) { this._route = r; if (this._ready) this.render(); }
  set panel(p) { this._panel = p; }

  get _base() { return `/${this._panel?.url_path || 'ripple'}`; }

  async _start() {
    const root = this.shadowRoot;
    root.innerHTML = '';
    root.append(h('style', {}, CSS));
    this._header = h('header', {});
    this._main = h('main', { id: 'app' });
    this._dlg = h('dialog', { id: 'dlg' });
    // bindings of one device: redrawn by render() while open, closed by Escape, Enter or Close
    this._bdlg = h('dialog', { id: 'bdlg', class: 'wide' });
    this._bdlg.addEventListener('close', () => { this.S.bmodal = null; });
    this._bdlg.addEventListener('keydown', (e) => {
      if (e.key !== 'Enter' || ['BUTTON', 'SELECT', 'INPUT', 'SUMMARY'].includes(e.target.nodeName)) return;
      e.preventDefault();
      this._bdlg.close();
    });
    root.append(this._header, this._main, this._dlg, this._bdlg);
    // a value skipped while its input had the focus is written by the first render after it loses it
    root.addEventListener('focusout', () => { if (this._ready) this._renderSoon(); });
    this._dlg.addEventListener('keydown', (e) => {
      if (e.key !== 'Enter' || e.target.nodeName === 'BUTTON') return;
      const btns = [...this._dlg.querySelectorAll('.acts button:not(:disabled)')];
      if (btns.length > 1) { e.preventDefault(); btns[btns.length - 1].click(); }
    });
    // the subscription's snapshot is the first state; an older backend without it is read with _load()
    this._watchConn();
    this._subscribe();
    this._timer = setInterval(() => this._tick(), 500);
    this._onVis ||= () => { if (!document.hidden && this._hiddenDirty) { this._hiddenDirty = false; this.render(); } };
    document.addEventListener('visibilitychange', this._onVis);
    this._ready = true;
    this.render();
  }

  disconnectedCallback() {
    clearInterval(this._timer);
    if (this._onVis) document.removeEventListener('visibilitychange', this._onVis);
    if (this._raf) cancelAnimationFrame(this._raf);
    if (this._rraf) cancelAnimationFrame(this._rraf);
    this._raf = this._rraf = null;
    clearTimeout(this._retry);
    this._gen = (this._gen || 0) + 1;
    this._watchConn(null);
    this._push = false;
    this._dropSub();
    this._ready = false;
    this._hass = null;
  }

  ws(type, data = {}) { return this._hass.callWS({ type: `ripple_presence/${type}`, ...data }); }

  // With the push subscription a read is one snapshot with its rev; one older than the deltas already brought is dropped.
  // Without it (an older backend) state and zha_devices are read as before.
  async _load() {
    if (this._push) {
      const snap = await this.ws('panel/snapshot');
      if (snap.rev >= (this._rev ?? -1)) this._applySnap(snap);
      return;
    }
    const [st, zha] = await Promise.all([this.ws('state'), this.ws('zha_devices')]);
    this._clock(st.now);
    this._st = st;
    this._zha = zha;
    this._liveState(st.live || {});
  }

  // browser clock minus HA clock, so absolute server timestamps turn into local ones
  _clock(now) { if (typeof now === 'number') this._skew = Date.now() / 1000 - now; }

  _applySnap(m) {
    this.S.msg = null;
    this._clock(m.now);
    this._rev = m.rev;
    this._st = { ...m.meta, rooms: m.rooms, switches: m.switches, others: m.others };
    this._zha = m.zha || [];
    this._liveState((m.meta && m.meta.live) || {});
  }

  _applyDelta(m) {
    if (!this._st || m.rev <= (this._rev ?? -1)) return;
    this._clock(m.now);
    this._rev = m.rev;
    const st = { ...this._st };
    if (m.switches || m.gone) {
      const gone = new Set(m.gone || []);
      const byId = new Map((st.switches || []).filter((x) => !gone.has(x.ieee)).map((x) => [x.ieee, x]));
      for (const [ieee, ch] of Object.entries(m.switches || {})) {
        const cur = { ...(byId.get(ieee) || {}), ...ch };
        (ch._drop || []).forEach((f) => delete cur[f]);
        delete cur._drop;
        byId.set(ieee, cur);
      }
      st.switches = [...byId.values()];
    }
    if (m.rooms || m.rooms_gone || m.room_order) {
      const gone = new Set(m.rooms_gone || []);
      const byId = new Map((st.rooms || []).filter((r) => !gone.has(r.id)).map((r) => [r.id, r]));
      for (const [id, r] of Object.entries(m.rooms || {})) byId.set(id, r);
      const order = m.room_order || [...byId.keys()];
      st.rooms = order.map((id) => byId.get(id)).filter(Boolean);
    }
    if (m.others) st.others = m.others;
    if (m.meta) {
      Object.assign(st, m.meta);
      this._liveState(m.meta.live || {});
    }
    if (m.zha) this._zha = m.zha;
    this._st = st;
  }

  _liveState(view) {
    const t = Date.now();
    this.S.live = Object.fromEntries(Object.entries(view).map(([rid, v]) => [rid, { end: v.end != null ? this.srvMs(v.end) : t + v.left * 1000,
      only: v.lines ? new Set(v.lines.map((x) => lineKey(x.rx, x.tx))) : null }]));
    this._pruneSim();
  }

  // Is the line (key rx<tx) streaming in a room that is live now?
  keyLive(k) {
    const rx = k.split('<')[0];
    return Object.entries(this.S.live).some(([rid, s]) => {
      const r = this.room(rid);
      return !!r && r.members.includes(rx) && (!s.only || s.only.has(k));
    });
  }

  _pruneSim() {
    for (const k of Object.keys(this._sim || {})) if (!this.keyLive(k)) delete this._sim[k];
    for (const k of Object.keys(this._peaks || {})) if (!this.keyLive(k)) delete this._peaks[k];
  }

  // Live Room streams every line of the room; Live of a line streams only that line
  lineLive(r, l) {
    const s = this.S.live[r.id];
    return !!s && (!s.only || s.only.has(lineKey(l.rx, l.tx)));
  }

  async liveLine(r, l) {
    const s = this.S.live[r.id];
    if (s && s.only && s.only.has(lineKey(l.rx, l.tx)) && s.only.size === 1) return this.stopLive(r.id);
    try {
      this._liveState(await this.ws('live/start', { room_id: r.id, seconds: this.S.liveDefault, lines: [[l.rx, l.tx]] }));
    } catch (e) { this._toast(`Live could not start: ${e.message || e}`); }
    this.render();
  }

  // A hand that lets go of the slider moves a step or two in the last instant: the value kept is the one the thumb
  // rested on (at least SLIDER_REST_MS still), not the one under the pointer at release
  sliderGrab(k, v) { (this._sl ||= {})[k] = { rest: v, last: v, t: performance.now() }; }

  sliderMove(k, v) {
    const s = (this._sl ||= {})[k] ||= { rest: v, last: v, t: performance.now() };
    const t = performance.now();
    if (v !== s.last) {
      if (t - s.t >= SLIDER_REST_MS) s.rest = s.last;
      s.last = v;
      s.t = t;
    }
  }

  // On release: the value to put back when the last move was release drift, otherwise null
  sliderDrop(k) {
    const s = this._sl && this._sl[k];
    if (this._sl) delete this._sl[k];
    if (s && s.last !== s.rest && performance.now() - s.t < SLIDER_REST_MS && Math.abs(s.last - s.rest) <= SLIDER_DRIFT) return s.rest;
    return null;
  }

  // Sensitivity of one line: typed, stepped with - and +, or slid; Live shows it while the dialog is open
  sensDlg(r, l) {
    const d = this._dlg;
    const k = lineKey(l.rx, l.tx);
    // Cancel puts back the row's own state as it was: a pending edit and its value, or none
    const hadEdit = k in this.S.lineEdit;
    const pending = this.S.lineEdit[k];
    const before = pending ?? l.sens;
    let v = before;
    let done = false;
    const num = h('input', { type: 'number', class: 'sensnum', min: 0, max: S_MAX, step: 1, value: v,
      oninput: (e) => { const n = Math.round(+e.target.value); if (e.target.value !== '' && Number.isFinite(n)) set(n, num); },
      onchange: () => { num.value = v; } });
    const rng = h('input', { type: 'range', min: 0, max: S_MAX, step: 1, value: v,
      onpointerdown: () => this.sliderGrab('dlg', v),
      oninput: (e) => { this.sliderMove('dlg', +e.target.value); set(+e.target.value, rng); },
      onchange: () => { const b = this.sliderDrop('dlg'); if (b != null) set(b); } });
    const minus = h('button', { class: 'btn step', title: 'One step less sensitive', onclick: () => set(v - 1) }, '−');
    const plus = h('button', { class: 'btn step', title: 'One step more sensitive', onclick: () => set(v + 1) }, '+');
    const note = h('p', { class: 'sub' });
    const save = h('button', { class: 'btn pri', onclick: () => { done = true; d.close(); this.saveLine(l, v); } }, 'Save');
    const set = (n, from) => {
      v = Math.min(S_MAX, Math.max(0, n));
      if (from !== num) num.value = v;
      if (from !== rng) rng.value = v;
      minus.disabled = v <= 0;
      plus.disabled = v >= S_MAX;
      // Save is the row's Save: it makes the value shown the saved one, also when that only drops the row's unsaved edit
      const f = this.freshLine(r.id, k) || { r, l };  // the device may change while the dialog is open
      const saved = f.l.sens;
      save.disabled = v === saved && !hadEdit;
      note.textContent = `${v === 0 ? '0 = off, the line does not vote.' : '100 = most sensitive, 0 = off.'} Saved on the device: ${saved}.`;
      if (from !== 'init') this.slide(f.r, f.l, v);
    };
    set(v, 'init');
    dlgSet(d, h('h3', {}, 'Sensitivity'),
      h('p', {}, `${this.devName(l.rx)} listens to ${this.devName(l.tx)}`),
      h('div', { class: 'sensrow' }, minus, num, plus),
      h('div', { class: 'sensrng' }, h('span', {}, '0'), rng, h('span', {}, '100')),
      note,
      h('div', { class: 'acts' },
        h('button', { class: 'btn', onclick: () => d.close() }, 'Cancel'),
        save));
    d.onclose = () => {
      d.onclose = null;
      if (done) return;
      if (hadEdit) this.S.lineEdit[k] = pending; else delete this.S.lineEdit[k];
      this.render();
      const f = this.freshLine(r.id, k);
      if (f && this.lineLive(f.r, f.l)) {
        clearTimeout(this._cand?.[k]);
        this._call('live/candidate', { room_id: f.r.id, rx: f.l.rx, tx: f.l.tx, step: hadEdit && pending !== f.l.sens && pending ? pending : null });
      }
    };
    d.showModal();
    num.focus();
    num.select();
  }

  // The library's own resubscribe after a reconnect has no error path.
  // A panel subscribing while Ripple is still starting would stay on stale state without a word.
  // So resubscribe is off and 'ready' starts over here.
  // true when the connection object changed
  _watchConn(conn = this._hass && this._hass.connection) {
    if (this._conn === conn) return false;
    if (this._conn) this._conn.removeEventListener('ready', this._onReady);
    this._conn = conn || null;
    this._onReady ||= () => { this._resubscribe(); };
    if (this._conn) this._conn.addEventListener('ready', this._onReady);
    return true;
  }

  _dropSub() {
    const s = this._unsub;
    this._unsub = null;
    if (s) dropOnSocket(s);
  }

  // a new backend instance or a new socket: its revs start over and its first message is a snapshot
  _resubscribe(delay = 0) {
    clearTimeout(this._retry);
    this._gen = (this._gen || 0) + 1;  // a subscribe still in flight belongs to the old round and is dropped
    this._dropSub();
    this._push = false;
    this._rev = null;
    this._retry = setTimeout(() => this._subscribe(), delay);
  }

  // Snapshot, then deltas and Live frames. 'closed' comes when the integration reloads: subscribe again.
  _subscribe(tries = 0) {
    if (!this._hass) return;
    const gen = this._gen;
    const stale = () => gen !== this._gen || !this._hass;
    const again = (e) => {
      if (stale()) return;
      if (tries === 0) { this.S.msg = `Ripple is not ready: ${e.message || e.code || e}`; this.render(); }
      // an HA restart with a slow ZHA can take minutes: after about 4 min say so, but keep trying every 10 s
      if (tries === 30) { this.S.msg = `Live updates are not available: ${e.message || e}`; this.render(); }
      this._retry = setTimeout(() => this._subscribe(tries + 1), Math.min(10000, 500 * 2 ** Math.min(tries, 5)));
    };
    const conn = this._hass.connection;
    // only the events of the current round: an older one may still deliver a snapshot or a 'closed'
    conn.subscribeMessage((ev) => { if (!stale()) this._event(ev); }, { type: 'ripple_presence/panel/subscribe' }, { resubscribe: false })
      .then((u) => {
        // the socket that carried the result: a subscribe queued while the socket was suspended is made on the next one
        const sock = conn.socket;
        if (stale()) { dropOnSocket({ u, conn, sock }); return; }
        this._unsub = { u, conn, sock };
        this._push = true;
        if (tries > 0) { this.S.msg = null; this.render(); }
      })
      .catch((e) => {
        if (!e || e.code !== 'unknown_command') return again(e);
        // unknown: an older Ripple without the push, or Ripple not loaded yet (then its other commands are unknown too)
        this.ws('state').then(() => { if (!stale()) this._subscribeOld(); }, () => again(e));
      });
  }

  _subscribeOld() {
    this._load().then(() => this.render()).catch((e) => { this.S.msg = `Ripple is not ready: ${e.message || e}`; this.render(); });
    const gen = this._gen;
    const stale = () => gen !== this._gen || !this._hass;
    const conn = this._hass.connection;
    conn.subscribeMessage((ev) => { if (!stale()) this._event(ev); }, { type: 'ripple_presence/subscribe' }, { resubscribe: false })
      .then((u) => {
        // the socket that carried the result: a subscribe queued while the socket was suspended is made on the next one
        const sock = conn.socket;
        if (stale()) { dropOnSocket({ u, conn, sock }); return; }
        this._unsub = { u, conn, sock };
      })
      .catch((e) => { this.S.msg = `Live updates are not available: ${e.message || e}`; });
  }

  // one render per frame for state that came over the socket
  _renderSoon() {
    if (this._rraf) return;
    this._rraf = requestAnimationFrame(() => { this._rraf = null; this.render(); });
  }

  _event(ev) {
    if (ev.type === 'snapshot') {
      this._applySnap(ev);
      this._renderSoon();
    } else if (ev.type === 'delta') {
      this._applyDelta(ev);
      this._renderSoon();
    } else if (ev.type === 'closed') {
      this._resubscribe(1000);
    } else if (ev.type === 'changed') {
      this._reloadSoon();
    } else if (ev.type === 'live_state') {
      this._liveState(ev.live || {});
      this.render();
    } else if (ev.type === 'live') {
      const recs = ev.records || [];
      (ev.info || []).forEach((i) => {
        const k = lineKey(ev.rx, i.tx);
        this.S.lv[k] = { ...(this.S.lv[k] || {}), last_on: i.last_on, m: i.m };
      });
      recs.forEach((r) => this._record(ev.rx, r, false));
      this._paintSoon([...recs, ...(ev.info || [])].map((r) => lineKey(ev.rx, r.tx)));
    }
  }

  // Lines whose live values changed are painted on the next frame, each in its own row only.
  // A line turning on or off also changes the room card, so that frame renders the page.
  _paintSoon(keys) {
    const d = (this._dirtyLines ||= new Set());
    keys.forEach((k) => d.add(k));
    if (!this._raf) this._raf = requestAnimationFrame(() => { this._raf = null; this._paintLines(); });
  }

  _paintLines() {
    const keys = this._dirtyLines || new Set();
    this._dirtyLines = new Set();
    if (!keys.size) return;
    const rid = this._curRoom;
    if (this._flip || !rid || !this._main || document.hidden) { this._flip = false; this.render(); return; }
    const rows = new Map();
    for (const e of this._main.querySelectorAll('.lrow')) if (e._key != null) rows.set(e._key, e);
    for (const k of keys) {
      const el = rows.get(k);
      const f = el && this.freshLine(rid, k);
      if (f) morph(el, this.lineItem(f.r, f.l));
    }
  }

  // at most one reload in flight and none starved by a stream of changes
  _reloadSoon() {
    if (this._loading) { this._dirty = true; return; }
    this._loading = true;
    this._dirty = false;
    this._load().then(() => this.render()).catch(() => {}).finally(() => {
      this._loading = false;
      if (this._dirty) this._reloadSoon();
    });
  }

  _record(rx, r, draw = true) {
    const k = lineKey(rx, r.tx);
    const prev = this.S.lv[k];
    this.S.lv[k] = { ...r, at: nowS(), m: prev && prev.m };
    this._simStep(k, rx, r);
    if (!!(prev && prev.on) !== !!r.on) this._flip = true;
    if (draw) this.render();
  }

  // replays the 5.0.3 motion rule (as the firmware does) for every s 1-100 on every packet:
  // d = med5 = |x - median of the 5 previous stored frames| (0 on a sample that is not stored), one stored frame
  // every decim samples; B = hits (med5 >= thr) of the last 16 stored frames, the line hits while popcount(B) >= M
  _simStep(k, rx, r) {
    const l = ((this.sw(rx) || {}).links || []).find((x) => x.ieee === r.tx);
    const det = l && l.det;
    // 5.0.4 sends the meter deviation itself: the gauge needs no link_diag read (a stale one left it blank)
    if ((det && det.api === 5) || (this.sw(rx) || {}).sense_api >= 5) {
      // the device sends the meter deviation, the gauge reads it on the real scale (s_live = meterS(d)).
      // d is 0 on every sample the device does not store (most of them), so the gauge shows the peak d of the
      // records of the last LIVE_PEAK_MS: a 0 record alone no longer empties it, and it falls back once quiet.
      const ms = r.ms ?? Date.now();
      const peaks = ((this._peaks ||= {})[k] || []).filter((p) => ms - p[0] < LIVE_PEAK_MS && p[0] <= ms);
      if (r.d > 0) peaks.push([ms, r.d]);
      this._peaks[k] = peaks;
      const d = peaks.reduce((a, p) => Math.max(a, p[1]), 0);
      ((this._sim ||= {})[k] = { meter: d > 0 ? meterS(d) : null });
      return;
    }
    if (!det) return;
    const sim = ((this._sim ||= {})[k] ||= { B: Array(S_MAX + 1).fill(0), S: Array(S_MAX + 1).fill(0),
      H: MP.map((p) => p.k), c: 0 });
    const d = r.d || 0;
    // a non-zero med5 is always a stored frame and re-aligns the decimation count
    const stored = d > 0 || sim.c + 1 >= (det.decim || 1);
    sim.c = stored ? 0 : sim.c + 1;
    for (let s = 1; s <= S_MAX; s++) {
      if (stored) sim.B[s] = ((sim.B[s] << 1) | (d >= MP[s].db ? 1 : 0)) & 0xFFFF;
      sim.S[s] = popcount16(sim.B[s]);
    }
    // the device's own count is exact: q = hits * 128 / M at the line's s, q' at the previewed candidate
    const sync = (s, q) => {
      if (q == null || !(s >= 1 && s <= S_MAX)) return;
      const n = Math.ceil((q * MP[s].k) / 128 - 1e-9);
      sim.S[s] = q >= 255 ? Math.max(sim.S[s], n) : n;
    };
    sync(l.sens, r.q);
    const cand = this.S.lineEdit[k];
    if (r.preview && cand) sync(cand, r.q2);
  }

  _tick() {
    let gone = false;
    for (const [rid, l] of Object.entries(this.S.live)) {
      if (Date.now() >= l.end) { delete this.S.live[rid]; gone = true; }
    }
    if (gone) this._pruneSim();
    const cal = this.calibrations();
    if (this._calN && !cal.length) this._reloadSoon();
    this._calN = cal.length;
    const calSig = cal.map((c) => c.ieee + c.lines.join()).join('|');
    if (gone || calSig !== this._calSig) { this._calSig = calSig; this.render(); } else this._countdowns();
    const rid = this._curRoom;
    if (rid && this.isConnected && Date.now() - ((this.S.hist[rid] || {}).at || 0) > 5000) this.loadHist(rid);
  }

  _countdowns() {
    if (!this.shadowRoot || document.hidden) return;
    for (const e of this.shadowRoot.querySelectorAll('[data-end]')) {
      const t = countdown(+e.dataset.end, e.dataset.fmt);
      if (e.textContent !== t) e.textContent = t;
    }
  }

  async loadHist(rid) {
    const cur = this.S.hist[rid] || {};
    this.S.hist[rid] = { ...cur, at: Date.now() };
    try {
      const { events } = await this.ws('history', { room_id: rid, limit: 40 });
      const same = JSON.stringify(events) === JSON.stringify(cur.events);
      this.S.hist[rid] = { at: Date.now(), events };
      if (!same && this._curRoom === rid) this.render();
    } catch (e) { /* older backend: no history command */ }
  }

  moreInfo(entityId) {
    if (entityId) this.dispatchEvent(new CustomEvent('hass-more-info', { detail: { entityId }, bubbles: true, composed: true }));
  }

  histRow(x) {
    const d = new Date(x.t * 1000);
    return h('div', { key: `${x.t}|${x.rx}|${x.tx}|${x.on}`, class: 'hrow' + (x.on ? ' on' : '') },
      h('span', { class: 'hd' }, d.toLocaleDateString(undefined, { day: '2-digit', month: '2-digit' })),
      h('span', { class: 'ht' }, d.toLocaleTimeString()),
      h('span', { class: 'hl' }, `${this.devName(x.rx)} ← ${this.devName(x.tx)}`),
      h('span', { class: 'hs' }, x.on ? 'detecting' : 'quiet'));
  }

  histDlg(r) {
    const d = this._dlg;
    const pad = (n) => String(n).padStart(2, '0');
    const loc = (t) => { const x = new Date(t); return `${x.getFullYear()}-${pad(x.getMonth() + 1)}-${pad(x.getDate())}T${pad(x.getHours())}:${pad(x.getMinutes())}`; };
    const from = h('input', { type: 'datetime-local', value: loc(Date.now() - 24 * 3600e3), min: loc(Date.now() - 7 * 24 * 3600e3) });
    const to = h('input', { type: 'datetime-local', value: loc(Date.now() + 60e3) });
    const lines = this.lines(r);
    const line = h('select', {}, h('option', { value: '' }, 'All lines'),
      lines.map((l) => h('option', { value: lineKey(l.rx, l.tx) }, `${this.devName(l.rx)} ← ${this.devName(l.tx)}`)));
    const state = h('select', {}, h('option', { value: '' }, 'Detecting and quiet'),
      h('option', { value: 'on' }, 'Detecting only'), h('option', { value: 'off' }, 'Quiet only'));
    const hourFrom = h('input', { type: 'time', value: '' });
    const hourTo = h('input', { type: 'time', value: '' });
    const out = h('div', { class: 'log hlog' });
    const info = h('p', { class: 'sub' });
    const run = async () => {
      info.textContent = 'Loading…';
      try {
        const since = from.value ? new Date(from.value).getTime() / 1000 : undefined;
        const until = to.value ? new Date(to.value).getTime() / 1000 : undefined;
        const { events } = await this.ws('history', { room_id: r.id, since, until, limit: 5000 });
        const mins = (v) => { const [a, b] = v.split(':').map(Number); return a * 60 + b; };
        const hf = hourFrom.value ? mins(hourFrom.value) : null;
        const ht = hourTo.value ? mins(hourTo.value) : null;
        const rows = events.filter((x) => {
          if (line.value && lineKey(x.rx, x.tx) !== line.value) return false;
          if (state.value && x.on !== (state.value === 'on')) return false;
          if (hf != null || ht != null) {
            const dt = new Date(x.t * 1000);
            const m = dt.getHours() * 60 + dt.getMinutes();
            const a = hf ?? 0, b = ht ?? 1439;
            if (a <= b ? (m < a || m > b) : (m < a && m > b)) return false;
          }
          return true;
        });
        out.replaceChildren(...(rows.length ? rows.map((x) => this.histRow(x)) : [h('div', { class: 'empty' }, 'No detections in this interval.')]));
        info.textContent = `${rows.length} event${rows.length === 1 ? '' : 's'}${events.length >= 5000 ? ' (first 5000 of the interval; narrow it)' : ''}.`;
      } catch (e) { info.textContent = e.message || String(e); }
    };
    const presets = [];
    const pick = (b) => presets.forEach((x) => { x.classList.toggle('on', x === b); x.setAttribute('aria-pressed', String(x === b)); });
    const preset = (label, ms) => {
      const b = h('button', { class: 'btn', 'aria-pressed': 'false', onclick: () => {
        from.value = loc(ms === 'today' ? new Date().setHours(0, 0, 0, 0) : Date.now() - ms); to.value = loc(Date.now() + 60e3); pick(b); run();
      } }, label);
      presets.push(b);
      return b;
    };
    // a hand-typed interval is no longer one of the presets
    from.addEventListener('input', () => pick(null));
    to.addEventListener('input', () => pick(null));
    dlgSet(d, h('h3', {}, `Detections in ${r.name}`),
      h('p', { class: 'sub' }, 'Every change of every line of this room, for the last 7 days, with Live on or off.'),
      h('div', { class: 'acts hpre' }, preset('1 h', 3600e3), preset('Today', 'today'), preset('24 h', 24 * 3600e3), preset('7 days', 7 * 24 * 3600e3)),
      h('div', { class: 'bform hform' },
        h('label', {}, 'From', from), h('label', {}, 'To', to),
        h('label', {}, 'Hours from (every day)', hourFrom), h('label', {}, 'Hours to', hourTo),
        h('label', {}, 'Line', line), h('label', {}, 'State', state)),
      h('div', { class: 'acts' }, h('button', { class: 'btn pri', onclick: run }, 'Apply')),
      info, out,
      h('div', { class: 'acts' }, h('button', { class: 'btn', onclick: () => d.close() }, 'Close')));
    d.classList.add('wide');
    d.addEventListener('close', () => { d.classList.remove('wide'); d.removeAttribute('tabindex'); }, { once: true });
    pick(presets[2]);
    d.showModal();
    // showModal focuses the first button (1 h) and draws a focus ring on it, next to the
    // highlighted 24 h; focus the dialog itself so only the chosen interval stands out
    d.tabIndex = -1;
    d.focus();
    run();
  }

  // devices capturing now: seconds left counted down from the last read of 0xff41, lines from the last Calibrate sent
  // a server timestamp (s) as local ms
  srvMs(ts) { return (ts + (this._skew || 0)) * 1000; }

  calibrations() {
    return ((this._st && this._st.switches) || []).map((s) => {
      const end = s.cal_left_at == null ? Date.now() : this.srvMs(s.cal_left_at + (s.cal_left || 0));
      const left = Math.ceil((end - Date.now()) / 1000);
      const on = (s.flags && s.flags.calibrating) || left > 0;
      if (!on) return null;
      const lines = s.cal_txs ? s.cal_txs.map((t) => `${s.name} ← ${this.devName(t)}`) : [`${s.name} (every line)`];
      const room = this._rooms().find((r) => r.members.includes(s.ieee));
      return { ieee: s.ieee, room, lines, left: Math.max(0, left), end };
    }).filter(Boolean);
  }

  calBar(cal) {
    return h('div', { key: 'calbar', class: 'calbar' }, h('b', {}, '◌ CALIBRATING'),
      h('div', { class: 'callist' }, cal.map((c) => h('span', {},
        `${c.room ? c.room.name + ': ' : ''}${c.lines.join(', ')}, `,
        h('span', { 'data-end': c.end, 'data-fmt': 'cal' }, countdown(c.end, 'cal'))))),
      h('span', { class: 'spacer' }), h('small', {}, 'Keep the room empty until it ends.'));
  }

  // ---------- data ----------

  _rooms() { return (this._st && this._st.rooms) || []; }
  room(id) { return this._rooms().find((r) => r.id === id); }
  sw(ieee) { return ((this._st && this._st.switches) || []).find((s) => s.ieee === ieee); }
  zdev(ieee) { return this._zha.find((d) => d.ieee === ieee); }
  devName(ieee) { return (this.sw(ieee) || this.zdev(ieee) || {}).name || ieee; }

  lines(r) {
    const out = [];
    for (const rx of r.members) {
      const s = this.sw(rx);
      for (const l of (s && s.links) || []) {
        out.push({ rx, tx: l.ieee, sens: l.sens, detecting: l.detecting, last: l.last_detection, parked: l.parked, state: l.state });
      }
    }
    return out;
  }

  // ---------- navigation ----------

  _where() {
    const p = ((this._route && this._route.path) || '').split('/').filter(Boolean).map(decodeURIComponent);
    const q = new URLSearchParams(window.location.search);
    const tab = ['rooms', 'devices', 'bindings', 'firmware'].includes(p[0]) ? p[0] : 'rooms';
    const byReg = tab === 'devices' && p[1] && ((this._st && this._st.switches) || []).find((s) => s.reg_id === p[1]);
    return { tab, room: tab === 'rooms' ? p[1] || null : null, device: tab === 'devices' ? (byReg ? byReg.ieee : p[1] || null) : null,
      from: q.get('from'), cat: q.get('cat') };
  }

  go(tab, extra = {}) {
    let path = `${this._base}/${tab}`;
    const id = extra.room || (extra.device && (this.sw(extra.device) || {}).reg_id) || extra.device;
    if (id) path += `/${encodeURIComponent(id)}`;
    const q = new URLSearchParams();
    if (extra.device && extra.from) q.set('from', extra.from);
    if (extra.device && this.S.cat[extra.device]) q.set('cat', this.S.cat[extra.device]);
    const url = path + (q.size ? `?${q}` : '');
    history.pushState(null, '', url);
    window.dispatchEvent(new CustomEvent('location-changed', { detail: { replace: false } }));
    this.render();
  }

  _toast(message) {
    this.dispatchEvent(new CustomEvent('hass-notification', { detail: { message }, bubbles: true, composed: true }));
  }

  async _call(type, data, ok) {
    try {
      const r = await this.ws(type, data);
      if (ok) this._toast(ok);
      return r ?? true;
    } catch (e) {
      this._toast(e.code === 'writes_disabled' ? 'Ripple is read-only: turn on "Allow writes to devices" in the Ripple settings.'
        : `Ripple could not do that: ${e.message || e.code || e}`);
      return null;
    } finally {
      // with the push subscription the change arrives as a delta
      if (!this._push) this._load().then(() => this.render()).catch(() => {});
    }
  }

  // ---------- render ----------

  render() {
    if (!this._main) return;
    if (document.hidden) { this._hiddenDirty = true; return; }
    const w = this._where();
    Object.assign(this.S, { tab: w.tab, room: w.room, device: w.device, from: w.from });
    if (w.tab === 'bindings' && this._lastTab !== 'bindings' && this._st) this.loadBinds();
    if (w.tab === 'firmware' && this._lastTab !== 'firmware' && this._st) this.loadFw();
    if (this._st) this._lastTab = w.tab;
    if (w.device && w.cat) this.S.cat[w.device] = w.cat;
    const menu = this._menu || (this._menu = h('ha-menu-button', {}));
    menu.hass = this._hass;
    menu.narrow = this._narrow;
    menu._keep = true;
    patch(this._header, [
      h('h1', {}, this._narrow ? menu : null, 'Ripple'),
      h('nav', { id: 'nav' }, [['rooms', 'Rooms'], ['devices', 'Devices'], ['bindings', 'Bindings'], ['firmware', 'Firmware']].map(([k, t]) =>
        h('button', { class: w.tab === k ? 'on' : '', onclick: () => this.go(k) }, t))),
      h('span', {}),
    ]);
    let view;
    if (!w.room) this._curRoom = null;
    if (!this._st) view = h('div', { class: 'card' }, h('p', { class: 'sub' }, this.S.msg || 'Loading Ripple…'));
    else if (w.room && this.room(w.room)) view = this.roomPage(this.room(w.room));
    else if (w.room) view = this.roomsPage();
    else if (w.device) view = this.sw(w.device) ? this.devicePage(this.sw(w.device)) : this.devicesPage();
    else view = w.tab === 'firmware' ? this.firmwarePage() : w.tab === 'bindings' ? this.bindingsPage()
      : w.tab === 'devices' ? this.devicesPage() : this.roomsPage();
    const top = [];
    if (this._st && !this._st.allow_writes) {
      top.push(h('div', { key: 'warnbox', class: 'card warnbox' }, h('p', { class: 'sub' },
        'Ripple is read-only. Changes are kept in Ripple but not sent to the devices. Turn on "Allow writes to devices" in the Ripple settings.')));
    }
    const cal = this._st ? this.calibrations() : [];
    if (cal.length) top.push(this.calBar(cal));
    if (w.room && this.S.live[w.room]) top.push(this.liveBar(this.room(w.room)));
    const bd = this.S.bmodal && this.bdevs().find((x) => x.ieee === this.S.bmodal);
    if (bd && this._bdlg.open) patch(this._bdlg, this.bindModal(bd, this.allBinds()));
    patch(this._main, [...top, view].flat().filter(Boolean));
  }

  roomOcc(r) {
    if (this.S.live[r.id]) return this.lines(r).some((l) => (this.S.lv[lineKey(l.rx, l.tx)] || {}).on);
    return r.occupied;
  }

  roomsPage() {
    const rooms = this._rooms();
    return [rooms.length ? h('div', { class: 'rooms' }, rooms.map((r) => h('div', { class: 'card', onclick: () => this.go('rooms', { room: r.id }) },
      h('div', { class: 'row' }, h('h2', {}, r.name), h('span', { class: 'spacer' }),
        this.S.live[r.id] ? h('span', { class: 'state livetag' }, '● Live') : null,
        h('span', { class: 'state ' + (this.roomOcc(r) ? 'occ' : 'free') }, this.roomOcc(r) ? 'Occupied' : 'Clear')),
      h('p', { class: 'sub' }, `${r.members.length} devices, ${this.lines(r).length} lines`))))
      : h('div', { class: 'card' }, h('p', { class: 'sub' }, 'No rooms yet. Give your Ripple devices an area in Home Assistant, or create a room.')),
    h('div', { class: 'row gap-top' }, h('button', { class: 'btn', onclick: () => this.addRoomDlg() }, '+ New room'))];
  }

  roomPage(r) {
    if (this._curRoom !== r.id) { this._curRoom = r.id; this.loadHist(r.id); }
    const live = !!this.S.live[r.id];
    const lines = this.lines(r);
    const hits = lines.filter((l) => (live ? (this.S.lv[lineKey(l.rx, l.tx)] || {}).on : l.detecting));
    const occ = live ? hits.length > 0 : r.occupied;
    return [
      h('div', { class: 'crumb' }, h('button', { class: 'link', onclick: () => this.go('rooms') }, 'Rooms'), ' / ', r.name,
        h('span', { class: 'spacer' }),
        h('button', { class: 'btn', title: r.kind === 'area' ? 'Hide this room. The Home Assistant area is not changed.' : 'Delete this room and its settings.', onclick: () => this.deleteRoomDlg(r) }, r.kind === 'area' ? 'Hide room' : 'Delete room')),
      h('div', { class: 'pair' }, h('div', { class: 'card' + (r.entity_id ? ' click' : ''), title: r.entity_id ? 'Open the history of the room motion sensor' : null,
        onclick: (e) => { if (!e.target.closest('button,input,select,a')) this.moreInfo(r.entity_id); } },
        h('div', { class: 'row' },
          h('h2', {}, r.name),
          h('span', { class: 'state ' + (occ ? 'occ' : 'free') }, occ ? 'Occupied' : 'Clear'),
          h('span', { class: 'spacer' }),
          this.S.live[r.id] && !this.S.live[r.id].only ? null
            : h('button', { class: 'btn live', disabled: !lines.length, onclick: () => this.liveDlg(r) }, '● Live Room')),
        h('p', { class: 'sub' }, hits.length
          ? ['Detected by: ', hits.map((l) => `${this.devName(l.rx)} ← ${this.devName(l.tx)}`).join(', ')]
          : 'No line is detecting right now.')),
      h('div', { class: 'card' },
        h('div', { class: 'row' }, h('h2', {}, 'Devices in this room'), h('span', { class: 'spacer' }),
          h('button', { class: 'btn', onclick: () => this.addDeviceDlg(r) }, '+ Add device')),
        h('p', { class: 'sub' }, 'The Ripple devices that listen in this room. Calibration, sensitivity and the room settings apply only to them. Click a name to open its Ripple settings.'),
        h('div', { class: 'row' }, r.members.map((id) => h('span', { class: 'chip' },
          h('button', { class: 'link', onclick: () => this.go('devices', { device: id, from: r.id }) }, this.devName(id)),
          h('button', { title: 'Remove from this room', onclick: () => this.setMembers(r, r.members.filter((m) => m !== id)) }, '×')))))),
      h('div', { class: 'card' },
        h('div', { class: 'row' }, h('h2', {}, 'Detection lines'), h('span', { class: 'spacer' }),
          h('button', { class: 'btn', disabled: !r.members.length, onclick: () => this.addLineDlg(r) }, '+ Add line')),
        h('p', { class: 'sub' }, 'A line is a Ripple device of this room listening to a sender. The sender can be any Zigbee device and does not have to be in the room. Each line has its own sensitivity.'),
        h('div', { class: 'row' },
          h('span', {}, 'Calibration: duration '),
          h('input', { type: 'number', min: 60, max: 1800, value: this.S.cal[r.id] ?? r.cal_s, class: 'num', oninput: (e) => { this.S.cal[r.id] = +e.target.value; } }), 's',
          h('span', { class: 'spacer' }),
          h('button', { class: 'btn', disabled: !lines.length, title: 'Calibrate every line of this room. Leave the room empty.', onclick: () => this.calibrateRoom(r) }, 'Calibrate room')),
        lines.length ? this.linesTable(r, lines) : h('div', { class: 'empty' }, 'No lines yet. Add one to start detection in this room.')),
      h('div', { class: 'pair' }, h('div', { class: 'card' },
        h('h2', {}, 'Room settings'),
        h('p', { class: 'sub' }, 'Settings of this room only. They do not change the devices.'),
        this.roomField(r, 'off_s', 'Turn off after leaving', 'Seconds the room motion sensor stays on after all its devices stopped detecting. Set per room, independent of the devices.', 0, 3600),
        this.roomTriggerField(r),
        this.roomSaveBar(r)),
      this.histCard(r)),
    ];
  }

  histCard(r) {
    const ev = ((this.S.hist[r.id] || {}).events || []).slice(0, 40);
    return this.memo('hist', JSON.stringify([r.id, ev.map((x) => [x.t, x.on, this.devName(x.rx), this.devName(x.tx)])]), () =>
      h('div', { key: 'hist', class: 'card click', title: 'Open the detections of the last 7 days, with filters', onclick: () => this.histDlg(this.room(r.id) || r) },
        h('div', { class: 'row' }, h('h2', {}, 'Recent detections'), h('span', { class: 'spacer' }), h('span', { class: 'sub' }, '7 days · filter ›')),
        h('div', { class: 'log' }, ev.map((x) => this.histRow(x)),
          ev.length ? null : h('div', { class: 'empty' }, 'No detection in the last 7 days.'))));
  }

  linesTable(r, lines) {
    return h('div', { class: 'lines' },
      h('div', { class: 'lrow lhead' }, ['Line', 'State', 'Live signal vs sensitivity', 'Sensitivity', 'Last detection', ''].map((t) => h('div', {}, t))),
      lines.map((l) => this.lineItem(r, l)));
  }

  // The row of one line, used by the page render and by the Live fast path alike.
  lineItem(r, l) {
    const k = lineKey(l.rx, l.tx);
    const live = this.lineLive(r, l);
    const roomLive = !!this.S.live[r.id] && !this.S.live[r.id].only;
    const cur = this.S.lineEdit[k] ?? l.sens;
    const v = live ? this.S.lv[k] : null;
    const sim = live && this._sim ? this._sim[k] : null;
    // Everything the row shows; a row whose inputs did not change is not rebuilt.
    const sig = JSON.stringify([r.id, l, live, roomLive, cur, v, sim, (this.S.lv[k] || {}).last_on,
      this.devName(l.rx), this.devName(l.tx)]);
    return this.memo(k, sig, () => this.lineRow(r, l, k, { live, roomLive, cur, v, sim }));
  }

  // An element whose inputs (sig) are the ones it was built from stays on screen as it is.
  // build() must return an element with { key }.
  memo(key, sig, build) { return memoNode(key, sig, build); }

  // The line of a room as it is now: handlers of a kept row must not act on the data the row was built from.
  freshLine(rid, k) {
    const r = this.room(rid);
    const l = r && this.lines(r).find((x) => lineKey(x.rx, x.tx) === k);
    return r && l ? { r, l } : null;
  }

  lineRow(r0, l0, k, { live, roomLive, cur, v, sim }) {
    const r = r0, l = l0;
    const act = (fn) => (...a) => { const f = this.freshLine(r0.id, k); if (f) return fn(f.r, f.l, ...a); };
        const changed = cur !== l.sens;
        const rc = !sim ? null : sim.meter !== undefined ? (sim.meter ? { e: sim.meter - 1, from: sim.meter } : { e: 100, from: null })
          : reachOf(sim.S, sim.H);
        const pos = rc ? rc.e : 100;
        const now = !!rc && rc.e <= cur - 1;
        const detecting = live ? !!(v && v.on) : l.detecting;
        // Live v4 (firmware 5.0.5): the line counts in its zones now; null on older firmware or without Live
        const vote = live && v && typeof v.vote === 'boolean' ? v.vote : null;
        const at = (st) => `left:${Math.max(0, st - 1)}%`;
        const cell = (name, sig, build) => this.memo(`${k}|${name}`, JSON.stringify([r0.id, sig]), build);
        const g = h('div', { class: 'gauge' + (rc ? '' : ' idle'),
          title: v ? `deviation ${v.d} dB, evidence reaches sensitivity ${rc && rc.from ? rc.from : '-'}` : '' },
          h('div', { class: 'fill' + (now ? ' over' : ''), style: `width:${100 - pos}%` }),
          cell('marks', [l.sens, cur], () => h('div', { key: `${k}|marks`, class: 'marks' },
            h('div', { class: 'mark', style: at(l.sens), title: `saved sensitivity ${l.sens}` }),
            changed ? h('div', { class: 'mark pend', style: at(cur), title: `new sensitivity ${cur}` }) : null)));
        const note = !live ? 'Start Live (room or line) to see the signal.'
          : !v ? 'Waiting for the first beacon.'
            : !rc ? 'Sensitivity data of this line is not read yet.'
              : changed ? (now ? 'With the new sensitivity it would trigger now.' : 'With the new sensitivity it would not trigger.')
                : now ? 'Triggering.' : rc.from ? `Would trigger from sensitivity ${rc.from}.` : 'Below every sensitivity.';
        const last = (this.S.lv[k] || {}).last_on || l.last;
        return h('div', { key: k, class: 'lrow' + (detecting ? ' hit' : '') + (changed ? ' mod' : '') },
          cell('name', [l.rx, l.tx, l.parked, this.devName(l.rx), this.devName(l.tx)], () =>
            h('div', { key: `${k}|name`, class: 'c-name linename' }, this.devLink(l.rx, r.id), ' listens to ', this.devLink(l.tx, r.id),
              h('small', {}, l.parked ? 'receiver ← sender, parked (does not vote)' : 'receiver ← sender'))),
          cell('state', [detecting, vote], () => h('div', { key: `${k}|state`, class: 'c-state' },
            detecting ? h('span', { class: 'state det' }, 'Detecting') : h('span', { class: 'state calm' }, 'Quiet'),
            vote === null ? null : h('small', { class: 'vote', title: VOTE_TITLE }, vote ? 'votes' : 'no vote'))),
          h('div', { key: `${k}|gauge`, class: 'c-gauge' }, g,
            cell('gscale', [], () => h('div', { key: `${k}|gscale`, class: 'gscale' }, h('span', {}, '1'), h('span', {}, '100'))),
            h('div', { class: 'gnote' + (changed && now ? ' would' : '') }, note)),
          cell('sens', [cur, l.sens], () => h('div', { key: `${k}|sens`, class: 'c-sens' }, h('div', { class: 'sens' },
            h('input', { type: 'range', min: 0, max: S_MAX, step: 1, value: cur,
              onpointerdown: () => this.sliderGrab(k, cur),
              oninput: act((r, l, e) => { this.sliderMove(k, +e.target.value); this.slide(r, l, +e.target.value); }),
              onchange: act((r, l, e) => { const v = this.sliderDrop(k); if (v != null) { e.target.value = v; this.slide(r, l, v); } }) }),
            h('button', { class: 'sensbox' + (changed ? ' changed' : ''), title: 'Set the sensitivity', onclick: act((r, l) => this.sensDlg(r, l)) }, String(cur))),
            h('small', {}, changed ? `saved: ${l.sens}` : cur === 0 ? '0 = off, the line does not vote' : '100 = most sensitive, 0 = off'))),
          cell('last', [last], () => h('div', { key: `${k}|last`, class: 'c-last', 'data-label': 'Last detection' }, clock(last))),
          cell('acts', [roomLive, live, cur, l.sens], () => h('div', { key: `${k}|acts`, class: 'c-acts acts-row' },
            roomLive ? null : h('button', { class: 'btn live' + (live ? ' on' : ''), title: live ? 'Stop Live of this line' : 'Live of this line only',
              onclick: act((r, l) => this.liveLine(r, l)) }, live ? '■ Live' : '● Live'),
            h('button', { class: 'btn' + (changed ? ' pri' : ''), disabled: !changed, title: changed ? `Save sensitivity ${cur} (saved: ${l.sens})` : 'Nothing to save', onclick: act((r, l) => this.saveLine(l, this.S.lineEdit[k] ?? l.sens)) }, 'Save'),
            h('button', { class: 'btn', title: 'Calibrate this line only. The other lines keep detecting.', onclick: act((r, l) => this.calibrateLine(r, l)) }, 'Calibrate'),
            h('button', { class: 'btn', title: 'Remove line', onclick: act((r, l) => this.removeLineDlg(l)) }, 'Remove'))));
  }

  slide(r, l, val) {
    const k = lineKey(l.rx, l.tx);
    if (val === l.sens) delete this.S.lineEdit[k]; else this.S.lineEdit[k] = val;
    this.render();
    if (!this.lineLive(r, l)) return;
    clearTimeout(this._cand?.[k]);
    (this._cand ||= {})[k] = setTimeout(() => this._call('live/candidate',
      { room_id: r.id, rx: l.rx, tx: l.tx, step: val === l.sens || !val ? null : val }), 250);
  }

  calSeconds(r) { return Math.min(1800, Math.max(60, +(this.S.cal[r.id] ?? r.cal_s) || 300)); }

  calibrateRoom(r) {
    return this._call('calibrate', { room_id: r.id, seconds: this.calSeconds(r) }, `${r.name}: calibration started. Leave the room empty.`);
  }

  calibrateLine(r, l) {
    return this._call('line/calibrate', { rx: l.rx, tx: l.tx, seconds: this.calSeconds(r) },
      `${this.devName(l.rx)} ← ${this.devName(l.tx)}: calibration started. Leave the room empty.`);
  }

  async saveLine(l, sens) {
    const r = await this._call('line/save', { rx: l.rx, tx: l.tx, sens }, `Saved: ${this.devName(l.rx)} ← ${this.devName(l.tx)} sensitivity ${sens}`);
    if (r) {
      delete this.S.lineEdit[lineKey(l.rx, l.tx)];
      await this._load();
      this.render();
    }
  }

  removeLineDlg(l) {
    const d = this._dlg;
    dlgSet(d, h('h3', {}, 'Remove line'),
      h('p', {}, `${this.devName(l.rx)} listens to ${this.devName(l.tx)}`),
      h('p', { class: 'sub' }, 'The receiver stops listening to this sender. The other lines stay.'),
      h('div', { class: 'acts' }, h('button', { class: 'btn', onclick: () => d.close() }, 'Cancel'),
        h('button', { class: 'btn live', onclick: async () => { d.close(); if (await this._call('line/remove', { rx: l.rx, tx: l.tx })) { await this._load(); this.render(); } } }, 'Remove')));
    d.showModal();
  }

  devLink(id, from) {
    return h('button', { class: 'link devlink', title: `Open ${this.devName(id)}`, onclick: () => this.sw(id) && this.go('devices', { device: id, from }) }, this.devName(id));
  }

  roomField(r, k, label, help, lo, hi) {
    const saved = r.settings ? r.settings[k] : null;
    const cur = this.S.redit[r.id]?.[k] ?? saved ?? '';
    const edited = cur !== saved && this.S.redit[r.id]?.[k] !== undefined;
    return h('div', { class: 'field' }, h('label', {}, label), h('div', { class: 'help' }, help),
      h('div', { class: 'ctl' }, h('div', { class: 'in' },
        h('input', { type: 'number', min: lo, max: hi, value: cur, class: edited ? 'changed' : '',
          oninput: (e) => { (this.S.redit[r.id] ||= {})[k] = e.target.value === '' ? '' : +e.target.value; this.render(); } }), 's'),
        h('span', { class: 'tech' }, edited ? `${k}, saved: ${saved}` : k)));
  }

  // how many lines of the room must detect at once before its motion turns on.
  roomTriggerField(r) {
    const t = r.trigger || { mode: 'any', k: null, threshold: 1, active: 0, total: 0, clamped: false };
    const ed = this.S.redit[r.id] || {};
    const mode = ed.trigger_mode ?? t.mode;
    const n = Math.max(1, t.total);
    const k = ed.trigger_k ?? t.k ?? Math.min(2, n);
    const edited = (ed.trigger_mode !== undefined && ed.trigger_mode !== t.mode) || (ed.trigger_k !== undefined && ed.trigger_k !== t.k);
    const set = (key, v) => { (this.S.redit[r.id] ||= {})[key] = v; this.render(); };
    const sel = h('select', { class: edited ? 'changed' : '', onchange: (e) => {
      const ne = (this.S.redit[r.id] ||= {});
      ne.trigger_mode = e.target.value;
      if (e.target.value === 'custom' && ne.trigger_k === undefined && t.k == null) ne.trigger_k = Math.min(2, n);
      this.render();
    } }, [['any', 'Any line'], ['all', 'All lines'], ['custom', 'Custom']].map(([v, l]) => h('option', { value: v, selected: v === mode }, l)));
    sel.value = mode; sel._val = mode;  // after the options exist, so a patch of a kept select follows the mode too
    const status = mode === t.mode && !edited
      ? `Now: ${t.active} of ${t.total} ${t.total === 1 ? 'line' : 'lines'} detecting, the room needs ${t.threshold}.`
      : `${t.total} ${t.total === 1 ? 'line' : 'lines'} in this room now.`;
    return h('div', { class: 'field' }, h('label', {}, 'Trigger the room when'),
      h('div', { class: 'help' }, 'How many lines of this room must detect at the same time before the room motion sensor turns on. Any line: one is enough. All lines: every line must detect. Custom: pick how many. A line is a device of the room listening to one sender, counted only while it votes for the room. A switch on firmware older than 5.0.5 counts as one line, its own motion. "Turn off after leaving" starts when fewer lines than needed still detect. ' + status,
        t.clamped ? ` The room has fewer lines than the ${t.k} chosen, so it uses ${t.threshold}.` : ''),
      h('div', { class: 'ctl' }, h('div', { class: 'in' }, sel,
        mode === 'custom' ? [h('input', { type: 'number', min: 1, max: n, step: 1, value: k, class: 'num' + (edited ? ' changed' : ''),
          oninput: (e) => set('trigger_k', e.target.value === '' ? '' : +e.target.value) }), `of ${t.total}`] : null),
        h('span', { class: 'tech' }, edited ? `trigger_mode/trigger_k, saved: ${t.mode}${t.mode === 'custom' ? ' ' + t.k : ''}` : 'trigger_mode/trigger_k')));
  }

  roomSaveBar(r) {
    const ed = { ...(this.S.redit[r.id] || {}) };
    const t = r.trigger || { mode: 'any', k: null, total: 0 };
    const saved = { ...(r.settings || {}), trigger_mode: t.mode, trigger_k: t.k };
    if ((ed.trigger_mode ?? t.mode) !== 'custom') delete ed.trigger_k;
    else if (ed.trigger_mode !== undefined && ed.trigger_k === undefined && t.k != null) ed.trigger_k = t.k;
    const LIM = { off_s: [0, 3600], trigger_k: [1, Math.max(1, t.total)] };
    const ch = ['off_s', 'trigger_mode', 'trigger_k'].filter((k) => ed[k] !== undefined && ed[k] !== saved[k]);
    if (!ch.length) return this.S.rmsg[r.id] ? h('div', { class: 'bfoot' }, h('span', {}, this.S.rmsg[r.id])) : null;
    const bad = ch.filter((k) => LIM[k] && (!Number.isInteger(ed[k]) || ed[k] < LIM[k][0] || ed[k] > LIM[k][1]));
    return h('div', { class: 'bfoot' },
      h('span', {}, bad.length ? `Value out of range: ${bad.map((k) => `${k} (${LIM[k][0]}-${LIM[k][1]})`).join(', ')}.`
        : `${ch.length} ${ch.length === 1 ? 'setting' : 'settings'} changed, not saved.`),
      h('span', { class: 'spacer' }),
      h('button', { class: 'btn', onclick: () => { delete this.S.redit[r.id]; this.S.rmsg[r.id] = ''; this.render(); } }, 'Cancel'),
      h('button', { class: 'btn pri', disabled: !!bad.length, onclick: async () => {
        const changes = Object.fromEntries(ch.map((k) => [k, ed[k]]));
        if (await this._call('room/settings', { room_id: r.id, changes })) {
          delete this.S.redit[r.id];
          this.S.rmsg[r.id] = `Saved at ${new Date().toLocaleTimeString()}: ${ch.map((k) => `${k}=${changes[k]}`).join(', ')}.`;
          await this._load();
          this.render();
        }
      } }, 'Save'));
  }

  liveBar(r) {
    const end = this.S.live[r.id].end;
    const only = this.S.live[r.id].only;
    const what = only ? this.lines(r).filter((l) => only.has(lineKey(l.rx, l.tx))).map((l) => `${this.devName(l.rx)} ← ${this.devName(l.tx)}`).join(', ')
      : 'every line of the room';
    return h('div', { key: 'livebar', class: 'livebar' }, h('b', {}, only ? '● LIVE LINE' : '● LIVE ROOM'),
      h('span', {}, `Real-time signal: ${what}. Stops by itself in `, h('span', { 'data-end': end }, countdown(end)), '.'),
      h('span', { class: 'spacer' }), h('button', { onclick: () => this.stopLive(r.id) }, 'Stop'));
  }

  liveDlg(r) {
    const d = this._dlg;
    const inp = h('input', { type: 'number', min: 10, max: 3600, value: this.S.liveDefault });
    const msg = h('p', { class: 'gnote would' });
    dlgSet(d, h('h3', {}, 'Start Live'),
      h('p', { class: 'sub' }, 'The receivers of this room send the value of every line at every beacon while Live runs. It stops by itself.'),
      h('label', {}, 'Duration (seconds, 10 to 3600)'), inp, msg,
      h('div', { class: 'acts' }, h('button', { class: 'btn', onclick: () => d.close() }, 'Cancel'),
        h('button', { class: 'btn live', onclick: async () => {
          const v = Math.min(3600, Math.max(10, +inp.value || this.S.liveDefault));
          this.S.liveDefault = v;
          try {
            const view = await this.ws('live/start', { room_id: r.id, seconds: v });
            this._liveState(view);
            d.close();
            this.render();
          } catch (e) { msg.textContent = e.message || String(e); }
        } }, 'Start')));
    d.showModal();
  }

  async stopLive(rid) {
    const view = await this._call('live/stop', { room_id: rid });
    if (view) this._liveState(view);
    const r = this.room(rid);
    if (r) this.lines(r).forEach((l) => { delete this.S.lv[lineKey(l.rx, l.tx)]; });
    this.render();
  }

  async setMembers(r, members) {
    const res = await this._call('room/save', { room_id: r.id, name: r.name, members });
    if (res) { await this._load(); this.render(); }
  }

  deleteRoomDlg(r) {
    const d = this._dlg;
    const area = r.kind === 'area';
    dlgSet(d, h('h3', {}, `${area ? 'Hide' : 'Delete'} ${r.name}?`),
      h('p', {}, area
        ? 'The room comes from a Home Assistant area. Ripple stops showing it; the area and its devices stay in Home Assistant.'
        : 'The room and its settings are removed. The devices and their lines stay.'),
      h('div', { class: 'acts' }, h('button', { class: 'btn', onclick: () => d.close() }, 'Cancel'),
        h('button', { class: 'btn pri', onclick: async () => {
          d.close();
          if (await this._call('room/delete', { room_id: r.id })) { await this._load(); this.go('rooms'); }
        } }, area ? 'Hide' : 'Delete')));
    d.showModal();
  }

  addDeviceDlg(r) {
    const all = (this._st && this._st.switches) || [];
    const free = all.filter((s) => !r.members.includes(s.ieee));
    const none = !all.length
      ? (this._st && this._st.status && this._st.status.probing ? 'Ripple devices are still being read. Try again in a few seconds.' : 'No Ripple device is available right now.')
      : 'Every Ripple device is already in this room.';
    const d = this._dlg;
    const sel = h('select', {}, free.map((x) => h('option', { value: x.ieee }, `${x.name} (${x.model || ''}${x.area ? ', ' + x.area : ''})`)));
    dlgSet(d, h('h3', {}, `Add a device to ${r.name}`),
      free.length ? [h('label', {}, 'Switch'), sel] : h('p', {}, none),
      h('div', { class: 'acts' }, h('button', { class: 'btn', onclick: () => d.close() }, 'Cancel'),
        h('button', { class: 'btn pri', disabled: !free.length, onclick: () => { d.close(); this.setMembers(r, [...r.members, sel.value]); } }, 'Add')));
    d.showModal();
  }

  addLineDlg(r) {
    const d = this._dlg;
    const rx = h('select', {}, r.members.map((id) => h('option', { value: id }, this.devName(id))));
    const tx = h('select', { disabled: true });
    const msg = h('p', { class: 'gnote would' });
    const add = h('button', { class: 'btn pri', disabled: true }, 'Add');
    const fill = async () => {
      const want = rx.value;
      tx.disabled = add.disabled = true;
      tx.replaceChildren(h('option', {}, 'Reading the Zigbee devices...'));
      msg.textContent = '';
      let c;
      try { c = await this.ws('candidates', { ieee: want }); } catch (e) {
        if (rx.value === want) { tx.replaceChildren(); msg.textContent = e.message || String(e); }
        return;
      }
      if (rx.value !== want) return;
      const have = new Set(this.lines(r).filter((l) => l.rx === want).map((l) => l.tx));
      const label = (x) => `${x.name || x.ieee}${x.area ? ' (' + x.area + ')' : ''}${x.available ? '' : ', offline'}`;
      const group = (title, list) => list.length ? h('optgroup', { label: title }, list.map((x) => h('option', { value: x.ieee }, label(x)))) : null;
      const free = c.filter((x) => !have.has(x.ieee));
      tx.replaceChildren(...[group('Heard by this device', free.filter((x) => x.heard)),
        group('Not in its neighbour table', free.filter((x) => !x.heard))].filter(Boolean));
      tx.disabled = add.disabled = !free.length;
      if (!free.length) msg.textContent = 'This device already listens to every Zigbee device.';
    };
    rx.onchange = fill;
    add.onclick = async () => {
      if (!tx.value) return;
      if (rx.value === tx.value) { msg.textContent = 'The receiver and the sender must be different.'; return; }
      if (this.lines(r).some((l) => l.rx === rx.value && l.tx === tx.value)) { msg.textContent = 'This line already exists.'; return; }
      try {
        await this.ws('line/add', { rx: rx.value, tx: tx.value });
        d.close();
        await this._load();
        this.render();
      } catch (e) { msg.textContent = e.message || String(e); }
    };
    dlgSet(d, h('h3', {}, 'New line'),
      h('label', {}, 'Receiver (the Ripple device that listens)'), rx,
      h('label', {}, 'Sender (any Zigbee device it listens to)'), tx,
      h('label', {}, 'Sensitivity'), h('p', { class: 'sub' }, `Starts at ${(this.sw(rx.value) || {}).sense_api >= 5 ? SENS_DEFAULT : 89} (${SENS_DEFAULT} on firmware 5.0.4 and 5.0.5, 89 on 5.0.3). Tune it later in the list, with Live.`), msg,
      h('div', { class: 'acts' }, h('button', { class: 'btn', onclick: () => d.close() }, 'Cancel'), add));
    d.showModal();
    fill();
  }

  addRoomDlg() {
    const d = this._dlg;
    const n = h('input', { placeholder: 'e.g. Kitchen' });
    const msg = h('p', { class: 'gnote would' });
    dlgSet(d, h('h3', {}, 'New room'), h('label', {}, 'Name'), n, msg,
      h('div', { class: 'acts' }, h('button', { class: 'btn', onclick: () => d.close() }, 'Cancel'),
        h('button', { class: 'btn pri', onclick: async () => {
          if (!n.value.trim()) { msg.textContent = 'Enter a name for the room.'; return; }
          try {
            const r = await this.ws('room/save', { name: n.value.trim(), members: [] });
            d.close();
            await this._load();
            this.go('rooms', { room: r.id });
          } catch (e) { msg.textContent = e.message || String(e); }
        } }, 'Create')));
    d.showModal();
  }

  // ---------- devices ----------

  devicesPage() {
    const sws = (this._st && this._st.switches) || [];
    return h('div', { class: 'card' }, h('h2', {}, 'Devices'),
      h('p', { class: 'sub' }, 'Devices with Ripple firmware. Click a row for its settings.'),
      sws.length ? h('div', { class: 'tscroll' }, h('table', {}, h('tr', {}, h('th', {}, 'Name'), h('th', {}, 'Model'), h('th', {}, 'Area'), h('th', {}, 'Ripple rooms'), h('th', {}, 'Listens to'), h('th', {}, 'Firmware')),
        sws.map((d) => h('tr', { style: 'cursor:pointer', onclick: () => this.go('devices', { device: d.ieee }) },
          h('td', {}, this.devLink(d.ieee)), h('td', {}, d.model || ''), h('td', {}, d.area || ''),
          h('td', {}, (() => {
            const rs = this._rooms().filter((r) => r.members.includes(d.ieee));
            return rs.length ? rs.map((r, i) => [i ? ', ' : '', h('button', { class: 'link', onclick: (e) => { e.stopPropagation(); this.go('rooms', { room: r.id }); } }, r.name)]) : 'none';
          })()),
          h('td', {}, `${(d.links || []).length} lines`),
          h('td', {}, d.available ? (d.sw_version || '') : h('span', { class: 'state novote' }, 'offline'),
            this.fwBadge(d))))))
        : h('div', { class: 'empty' }, 'No device with Ripple firmware found.'));
  }

  // a running install (HA's update entity) wins over the version check
  fwBadge(d) {
    const u = d.update;
    if (u && u.in_progress) {
      const pct = u.percentage == null ? '' : ` ${Math.floor(u.percentage)}%`;
      return h('span', { class: 'state upd busy', title: `Installing ${u.latest || 'an update'} (from ${u.installed || '?'})` }, `updating${pct}`);
    }
    return API_LABEL[d.api] ? h('span', { class: 'state upd', title: API_HELP[d.api] }, API_LABEL[d.api]) : null;
  }

  tuneValues(d) {
    const out = {};
    for (const a of d.advanced || []) {
      const v = a.value ?? a.device ?? a.default;
      out[a.key] = v == null ? null : v / (TO_BACKEND[a.key] || 1);
    }
    return out;
  }

  devicePage(d) {
    const from = this.S.from && this.room(this.S.from);
    const tune = this.tuneValues(d);
    const edit = this.S.dedit[d.ieee] ||= {};
    const changed = Object.keys(edit).filter((k) => edit[k] !== tune[k]);
    const lines = (d.links || []).map((l) => ({ rx: d.ieee, tx: l.ieee, sens: l.sens }));
    const roomOf = (l) => this._rooms().find((r) => r.members.includes(l.rx));
    return [
      h('div', { class: 'crumb' },
        from ? [h('button', { class: 'link', onclick: () => this.go('rooms', { room: from.id }) }, from.name), ' / ']
          : [h('button', { class: 'link', onclick: () => this.go('devices') }, 'Devices'), ' / '], d.name),
      h('div', { class: 'pair top' }, h('div', { class: 'col' }, h('div', { class: 'card' },
        h('div', { class: 'row' }, h('h2', {}, d.name), h('span', { class: 'spacer' }),
          d.reg_id ? h('button', { class: 'link', title: 'The generic Home Assistant device page (outside Ripple)', onclick: () => {
            history.pushState(null, '', `/config/devices/device/${d.reg_id}`);
            window.dispatchEvent(new CustomEvent('location-changed', { detail: { replace: false } }));
          } }, 'Open in Home Assistant ↗') : null),
        h('p', { class: 'sub' }, `${d.model || ''}, area ${d.area || 'none'}, firmware ${d.sw_version || '?'}${d.available ? '' : ', offline'}`,
          this.fwBadge(d))),
      this.switchSettings(d)),
      h('div', { class: 'card' }, h('h2', {}, 'Lines of this device'),
        lines.length ? h('div', { class: 'tscroll' }, h('table', {}, h('tr', {}, h('th', {}, 'Room'), h('th', {}, 'Listens to'), h('th', {}, 'Sensitivity')),
          lines.map((l) => {
            const r = roomOf(l);
            return h('tr', {},
              h('td', {}, r ? h('button', { class: 'link', onclick: () => this.go('rooms', { room: r.id }) }, r.name) : 'none'),
              h('td', {}, this.devLink(l.tx, r && r.id)), h('td', {}, String(l.sens)));
          })))
          : h('div', { class: 'empty' }, 'Listens to nobody.'))),
      h('div', { class: 'card' }, h('details', { class: 'fw', open: !!this.S.open[`${d.ieee}:fw`], ontoggle: (e) => { this.S.open[`${d.ieee}:fw`] = e.target.open; } },
        h('summary', {}, 'Advanced (firmware)', changed.length ? h('small', {}, `${changed.length} changed`) : h('small', {}, 'detection tuning, rarely needed')),
        h('p', { class: 'sub' }, 'Applies to every line this device listens to. Below each name is its technical name in the firmware.'),
        this.tunePanel(d, tune, edit, changed))),
      changed.length ? h('div', { class: 'savebar' },
        h('span', {}, `${changed.length} ${changed.length === 1 ? 'setting' : 'settings'} changed, not saved.`),
        h('span', { class: 'spacer' }),
        h('button', { class: 'btn', onclick: () => { this.S.dedit[d.ieee] = {}; this.render(); } }, 'Cancel'),
        h('button', { class: 'btn pri', onclick: async () => {
          const advanced = Object.fromEntries(changed.map((k) => [k, edit[k] * (TO_BACKEND[k] || 1)]));
          if (await this._call('switch/settings', { ieee: d.ieee, changes: { advanced } }, `Sent to ${d.name}: ${changed.length} settings.`)) {
            this.S.dedit[d.ieee] = {};
            await this._load();
            this.render();
          }
        } }, 'Save to device')) : null,
    ];
  }

  switchSettings(d) {
    const st = d.settings || {};
    const ed = this.S.sedit[d.ieee] ||= {};
    const val = (k) => (k in ed ? ed[k] : st[k]);
    const changed = Object.keys(ed).filter((k) => ed[k] !== st[k]);
    const num = (k, label, lo, hi, unit, help) => h('div', { class: 'field inline' },
      h('div', { class: 'name' }, h('label', {}, label), h('span', { class: 'tech' }, k)), h('div', { class: 'help' }, help),
      h('div', { class: 'ctl' }, h('input', { type: 'number', min: lo, max: hi, value: val(k) ?? '', class: k in ed && ed[k] !== st[k] ? 'changed' : '',
        oninput: (e) => { ed[k] = e.target.value === '' ? '' : +e.target.value; this.render(); } }), h('span', {}, unit)));
    if (!('detect' in st)) return h('div', { class: 'card' }, h('h2', {}, 'Device settings'), h('div', { class: 'empty' }, 'Settings not read from the device yet.'));
    return h('div', { class: 'card' }, h('h2', {}, 'Device settings'),
      h('div', { class: 'field inline' }, h('div', { class: 'name' }, h('label', {}, 'Detection'), h('span', { class: 'tech' }, 'detect')),
        h('div', { class: 'help' }, 'Turn off to keep the device quiet without removing it from rooms.'),
        h('div', { class: 'ctl' }, h('input', { type: 'checkbox', checked: !!val('detect'), onchange: (e) => { ed.detect = e.target.checked; this.render(); } }))),
      d.sense_api >= 5 ? h('div', { class: 'field inline' }, h('div', { class: 'name' }, h('label', {}, 'Self-tuning (24 h)'), h('span', { class: 'tech' }, 'self_tune')),
        h('div', { class: 'help' }, 'Firmware 5.0.4: once a day the device moves each line by at most one level, within two levels of where you or Calibrate put it, to follow slow drift. Off: it only measures.'),
        h('div', { class: 'ctl' }, h('input', { type: 'checkbox', checked: val('self_tune') ?? false, onchange: (e) => { ed.self_tune = e.target.checked; this.render(); } }))) : null,
      num('beacon_hz', 'Beacons per second', 0, 10, '/s', 'Radio packets that make links react faster. 0 turns them off, otherwise 2 to 10.'),
      num('off_s', 'Line on for', 1, 255, 's', 'How long this device keeps a detected line on after its last detection. Room timing is set on the room.'),
      changed.length ? h('div', { class: 'row' },
        h('span', {}, `${changed.length} changed, not saved.`), h('span', { class: 'spacer' }),
        h('button', { class: 'btn', onclick: () => { this.S.sedit[d.ieee] = {}; this.render(); } }, 'Cancel'),
        h('button', { class: 'btn pri', onclick: async () => {
          const changes = Object.fromEntries(changed.map((k) => [k, ed[k]]));
          if (await this._call('switch/settings', { ieee: d.ieee, changes }, `Sent to ${d.name}: ${changed.length} settings.`)) {
            this.S.sedit[d.ieee] = {};
            await this._load();
            this.render();
          }
        } }, 'Save to device')) : null);
  }

  tunePanel(d, tune, edit, changed) {
    const cat = this.S.cat[d.ieee] || TUNE[0][0];
    const [, title, fs] = TUNE.find(([id]) => id === cat);
    const ess = fs.filter((f) => DETAIL[f[0]][0]), adv = fs.filter((f) => !DETAIL[f[0]][0]);
    const advKey = `${d.ieee}:adv:${cat}`;
    const advChanged = adv.filter((f) => changed.includes(f[0])).length;
    return h('div', { class: 'tune' },
      h('nav', { class: 'cats' }, TUNE.map(([id, , cfs]) => {
        const n = cfs.filter((f) => changed.includes(f[0])).length;
        return h('button', { class: id === cat ? 'on' : '', onclick: () => this.pickCat(d.ieee, id) },
          h('span', {}, CAT[id][0]), n ? h('span', { class: 'n', title: 'changed, not saved' }, String(n)) : null);
      })),
      h('div', { class: 'catbody' },
        h('h3', {}, title), h('p', { class: 'catinfo' }, CAT[cat][1]),
        ess.length ? [h('div', { class: 'grp' }, 'Essentials'), ess.map((f) => this.tuneField(d, f, tune, edit))] : null,
        adv.length ? h('details', { class: 'adv', open: this.S.open[advKey] || advChanged > 0, ontoggle: (e) => { this.S.open[advKey] = e.target.open; } },
          h('summary', {}, `Advanced (${adv.length})`, advChanged ? h('small', {}, `${advChanged} changed`) : null),
          h('p', { class: 'catinfo' }, 'Rarely needed. The defaults suit most rooms.'),
          adv.map((f) => this.tuneField(d, f, tune, edit))) : null));
  }

  // HA re-sets route only when the path changes, so a query-only change must render itself
  pickCat(ieee, id) {
    this.S.cat[ieee] = id;
    const u = new URL(window.location.href);
    u.searchParams.set('cat', id);
    history.replaceState(history.state, '', u.pathname + u.search);
    this.render();
  }

  moreBox(d, f) {
    const [k, , , , , , def, unit] = f;
    const [, more, less, when] = DETAIL[k];
    const key = `${d.ieee}:more:${k}`;
    return h('details', { class: 'more', open: this.S.open[key], ontoggle: (e) => { this.S.open[key] = e.target.open; } },
      h('summary', {}, 'More'),
      h('dl', {},
        h('dt', {}, 'If you raise it'), h('dd', {}, more),
        h('dt', {}, 'If you lower it'), h('dd', {}, less),
        h('dt', {}, 'When to change it'), h('dd', {}, when),
        h('dt', {}, 'Default'), h('dd', {}, `${def}${unit ? ' ' + unit : ''}`)));
  }

  tuneField(d, f, tune, edit) {
    const [k, label, help, lo, hi, step, def, unit, tech] = f;
    const saved = tune[k];
    const v = edit[k] ?? saved ?? def;
    return h('div', { class: 'field' }, h('label', {}, label), h('div', { class: 'help' }, help, this.moreBox(d, f)),
      h('div', { class: 'ctl' },
        h('div', { class: 'in' }, h('input', { type: 'number', min: lo, max: hi, step, value: v, class: v !== saved ? 'changed' : '',
          onchange: (e) => { const n = Math.min(hi, Math.max(lo, +e.target.value)); if (n === saved) delete edit[k]; else edit[k] = n; this.render(); } }), unit),
        h('span', { class: 'def' }, v === def ? 'default' : h('button', { class: 'link', onclick: () => { if (def === saved) delete edit[k]; else edit[k] = def; this.render(); } }, `reset to ${def}`)),
        h('span', { class: 'tech' }, tech || k)));
  }

  // ---------- bindings ----------

  bdevs() {
    const ripple = ((this._st && this._st.switches) || []).map((s) => ({ ieee: s.ieee, name: s.name, ripple: true, ours: true, available: s.available, area: s.area }));
    const others = this._zha.filter((z) => z.kind !== 'ripple' && !ripple.some((r) => r.ieee === z.ieee))
      .map((z) => ({ ieee: z.ieee, name: z.name, ripple: false, ours: !!z.ours, available: z.available, area: z.area }));
    return [...ripple, ...others];
  }
  isRipple(ieee) { return !!this.sw(ieee); }
  // any build of our firmware (v4, v5): it can hold a binding; every other device is only a target
  isOurs(ieee) { return this.isRipple(ieee) || !!(this._zha.find((z) => z.ieee === ieee) || {}).ours; }
  eps(ieee) { return this.S.eps[ieee] || []; }
  async loadEps(ieee) {
    if (this.S.eps[ieee]) return;
    try { this.S.eps[ieee] = await this.ws('endpoints', { ieee }); } catch (e) { this.S.eps[ieee] = []; }
    this.render();
  }
  relays(ieee) { return this.eps(ieee).filter((e) => e.onoff_in).length; }
  epName(ieee, ep) {
    const e = this.eps(ieee).find((x) => x.ep === ep);
    let name = e && e.name ? e.name : `endpoint ${ep}`;
    if (e && this.isOurs(ieee) && e.onoff_out && !e.onoff_in) {
      const relay = this.eps(ieee).find((x) => x.ep === ep + this.relays(ieee));
      name = `Button ${ep}${relay && relay.name ? ` (relay ${relay.name})` : ''}`;
    }
    return [name, h('small', {}, `ep ${ep}`)];
  }
  revOf(b) {
    if (!this.isOurs(b.src) || !this.isOurs(b.dst)) return null;
    const n = this.relays(b.dst), ns = this.relays(b.src);
    if (!n || !ns || b.dep <= n) return null;
    return { src: b.dst, sep: b.dep - n, dst: b.src, dep: ns + b.sep };
  }
  allBinds() {
    const out = [];
    for (const [src, v] of Object.entries(this.S.binds)) {
      for (const r of v.controls || []) out.push({ src, sep: r.src_ep, dst: r.dst_ieee, dep: r.dst_ep });
    }
    return out;
  }
  findB(b) { return this.allBinds().find((x) => x.src === b.src && x.sep === b.sep && x.dst === b.dst && x.dep === b.dep); }
  dirTag(b) {
    if (this.isOurs(b.src) && this.isOurs(b.dst) && (!this.S.eps[b.src] || !this.S.eps[b.dst])) return 'checking';
    const r = this.revOf(b);
    if (!r) return 'one way';
    if (!this.readAt(r.src)) return 'reverse not read';
    return this.findB(r) ? 'both ways' : 'one way';
  }

  // the backend keeps the last table read from each device across restarts; the panel only shows it
  readAt(ieee) { return (this.S.binds[ieee] || {}).at || null; }

  async loadBinds() {
    try {
      const view = await this.ws('bindings');
      this.S.binds = Object.fromEntries(Object.entries(view).filter(([, v]) => v.at));
      this.S.bindsLoaded = true;
      for (const b of this.allBinds()) { this.loadEps(b.src); this.loadEps(b.dst); }
    } catch (e) { /* the tiles show what is already known */ }
    this.render();
  }

  // reads the table from the device; only for a device never read, "Read again", or after add / remove
  async readBinds(ieee) {
    this.loadEps(ieee);
    if (await this._call('bindings/read', { ieee })) await this.loadBinds();
    else this.render();
  }

  readTime(ts) {
    const t = new Date(ts * 1000);
    return t.toDateString() === new Date().toDateString() ? t.toLocaleTimeString() : t.toLocaleString();
  }

  // ---------- firmware ----------

  async loadFw() {
    try {
      this.S.fw = await this.ws('firmware/overview');
      this.S.fwErr = null;
    } catch (e) { this.S.fwErr = e.message || e.code || String(e); }
    const busy = Object.values((this.S.fw || {}).jobs || {}).some((j) => !['done', 'error'].includes(j.state));
    clearTimeout(this._fwTimer);
    if (busy && this.S.tab === 'firmware') this._fwTimer = setTimeout(() => this.loadFw(), 2000);
    this.render();
  }

  fwSum(sm) {
    return Object.entries(sm || {}).filter(([, n]) => n).map(([k, n]) => `${n} ${n === 1 ? k.replace(/es$|s$/, '') : k}`.replace(/_/g, ' ')).join(', ');
  }

  fwState(j) {
    if (!j) return '';
    const s = { queued: 'Waiting for the install before it', preparing: 'Preparing the image', rejoining: 'Waiting for the device to come back',
      configuring: 'Writing the board config', verifying: 'Checking the new config', rebuilding: 'Re-reading the device', done: 'Installed', error: `Failed: ${j.error}` };
    if (j.state === 'flashing') return `Flashing ${j.version || ''} ${j.progress != null ? `${Math.floor(j.progress)}%` : ''}`;
    return s[j.state] || j.state;
  }

  firmwarePage() {
    const fw = this.S.fw;
    const head = h('div', { class: 'card' }, h('h2', {}, 'Firmware'),
      h('p', { class: 'sub' }, 'Ripple firmware runs on Zigbee router devices with the Telink TLSR8258 chip. The board table says which devices it fits; Ripple builds the image for each device when you press Install and writes the board config (buttons, relays, LEDs) after the flash. One install at a time.'));
    if (this.S.fwErr) return [head, h('div', { class: 'card' }, h('p', { class: 'sub' }, `Could not read: ${this.S.fwErr}`))];
    if (!fw) return [head, h('div', { class: 'card' }, h('p', { class: 'sub' }, 'Loading…'))];
    const bin = fw.binaries[0];
    const info = !bin || !fw.available ? h('div', { class: 'card' },
      !bin ? h('p', { class: 'sub' }, `No Ripple-v<x.y.z>.bin in the integration or in ${fw.dir}.`) : null,
      !fw.available ? h('p', { class: 'sub' }, 'Not available in this mode (no Zigbee radio).') : null) : null;
    const pick = this.S.fwPick || (this.S.fwPick = {});
    const areas = (this._hass && this._hass.areas) || {};
    const rows = [...fw.devices].sort((a, b) => (a.name || '').localeCompare(b.name || '')).map((d) => {
      const ok = d.boards.filter((b) => b.flashable), j = fw.jobs[d.ieee.toLowerCase()];
      const board = this.fwBoard(d);
      const running = j && !['done', 'error'].includes(j.state);
      const router = d.device_type === 'Router';
      const why = d.protected ? 'Protected device'
        : !router && !ok.length ? (d.boards[0] || {}).not_flashable || 'Only router devices are supported'
        : !fw.allow_writes ? 'Writes are off'
        : !bin && (board || {}).how !== 'blank' ? 'No firmware file' : '';
      const pickBtn = d.protected ? h('span', { class: 'sub' }, why)
        : h('button', { class: 'link', onclick: () => this.fwBoardDlg(d) },
          board ? [board.human_name || board.key, h('small', {}, ` ${this.fwSum(board.summary)}`)] : 'Choose the board...');
      return h('tr', {},
        h('td', {}, d.name), h('td', {}, (areas[d.area_id] || {}).name || ''),
        h('td', {}, `${d.manufacturer || ''} ${d.model || ''}`), h('td', {}, pickBtn),
        h('td', {}, running || j ? this.fwState(j) : why),
        h('td', {}, h('button', { class: 'btn pri', disabled: !!why || running || !fw.available,
          onclick: () => (board ? this.fwInstallDlg(d, board) : this.fwBoardDlg(d, (b) => this.fwInstallDlg(d, b))) }, 'Install')));
    });
    const table = h('div', { class: 'card' }, h('h2', {}, 'Devices'),
      rows.length ? h('div', { class: 'tscroll' }, h('table', {},
        h('tr', {}, ['Name', 'Area', 'Reported as', 'Board', 'Status', ''].map((t) => h('th', {}, t))), rows))
        : h('p', { class: 'sub' }, 'No router device found.'));
    return [head, info, table].filter(Boolean);
  }

  // the board chosen for this device: picked by hand, else the only match, else the only tested match
  fwBoard(d) {
    const ok = d.boards.filter((b) => b.flashable), key = this.S.fwPick[d.ieee];
    if (key) return ok.find((b) => b.key === key) || (this.S.fwCustom || {})[d.ieee] || null;
    if (ok.length === 1) return ok[0];
    const tested = ok.filter((b) => b.tested);
    return tested.length === 1 ? tested[0] : null;
  }

  fwBoardDlg(d, next) {
    const dl = this._dlg, rows = [];
    const hows = new Set(d.boards.map((b) => b.how));
    const how = hows.has('blank') ? 'blank' : hows.has('stock') ? 'stock' : d.ripple ? 'flashed' : 'stock';
    const match = new Set(d.boards.filter((b) => b.flashable).map((b) => b.key));
    const choose = (b) => {
      const chosen = match.has(b.key) ? d.boards.find((x) => x.key === b.key) : { ...b, how };
      (this.S.fwCustom || (this.S.fwCustom = {}))[d.ieee] = chosen;
      this.S.fwPick[d.ieee] = b.key;
      dl.close();
      this.render();
      if (next) next(chosen);
    };
    const list = [...(this.S.fw.table || [])].sort((x, y) => match.has(y.key) - match.has(x.key));
    for (const b of list) {
      const stock = [[].concat(b.stock_manufacturer_name || []).join(', '), [].concat(b.stock_model_name || []).join(', ')].filter(Boolean).join(' ');
      const tr = h('tr', { class: 'pickrow', onclick: () => choose(b) },
        h('td', {}, b.human_name || b.key, b.tested ? h('small', {}, ' tested') : null, match.has(b.key) ? h('small', {}, ' detected') : null),
        h('td', {}, stock), h('td', {}, this.fwSum(b.summary)));
      tr._text = `${b.key} ${b.human_name || ''} ${stock} ${b.config_str || ''}`.toLowerCase();
      rows.push(tr);
    }
    const filter = (q) => { q = q.trim().toLowerCase(); rows.forEach((r) => { r.style.display = !q || r._text.includes(q) ? '' : 'none'; }); };
    const search = h('input', { type: 'search', placeholder: 'Search name, manufacturer, model, gangs...', class: 'bsearch',
      oninput: (e) => filter(e.target.value) });
    if (dl.open) dl.close();
    dl.classList.add('wide');
    dl.addEventListener('close', () => dl.classList.remove('wide'), { once: true });
    dlgSet(dl, h('h3', {}, `Choose the board for ${d.name}`),
      h('p', { class: 'sub' }, `The device reports ${d.manufacturer || '?'} ${d.model || '?'}.`),
      h('p', { class: 'sub' }, match.size ? 'Boards that match the device are listed first.' : 'No board in the table matches this device; pick the one with the same buttons, relays and LEDs.'),
      search,
      h('div', { class: 'tscroll' }, h('table', {}, h('tr', {}, ['Board', 'Stock name', 'Has'].map((t) => h('th', {}, t))), rows)),
      h('div', { class: 'acts' }, h('button', { class: 'btn', onclick: () => dl.close() }, 'Cancel')));
    dl.showModal();
    search.focus();
  }

  fwInstallDlg(d, b) {
    const dl = this._dlg;
    const detected = d.boards.some((x) => x.flashable && x.key === b.key);
    const go = async () => {
      dl.close();
      const r = await this._call('firmware/install', { ieee: d.ieee, board: b.key, custom: !detected });
      if (r) this.loadFw();
    };
    const blank = b.how === 'blank';
    dlgSet(dl, h('h3', {}, blank ? 'Write the board config' : 'Install Ripple firmware'),
      h('p', {}, h('b', {}, d.name), `, board ${b.human_name || b.key} (${this.fwSum(b.summary)}).`),
      h('p', {}, h('button', { class: 'link', onclick: () => this.fwBoardDlg(d, (x) => this.fwInstallDlg(d, x)) }, 'Change the board')),
      detected ? null : h('p', { class: 'sub fwwarn' }, 'Ripple cannot read the chip of a device. Install only if this device has the Telink TLSR8258 chip. On another chip the device can stop working.'),
      h('p', { class: 'sub' }, blank ? 'The device already runs Ripple firmware. Ripple writes the board config and the device restarts.'
        : `Ripple flashes ${this.S.fw.binaries[0].name} over the air and waits for the device to come back. A converted device rejoins; permit join stays open up to 30 min. Then Ripple writes the board config. Do not cut the power during the flash.`),
      h('div', { class: 'acts' }, h('button', { class: 'btn', onclick: () => dl.close() }, 'Cancel'),
        h('button', { class: 'btn live', onclick: go }, blank ? 'Write config' : 'Install')));
    dl.showModal();
  }

  bindingsPage() {
    const rows = this.allBinds();
    const groups = {};
    for (const d of this.bdevs().filter((x) => x.ours)) (groups[d.area || ''] ||= []).push(d);
    const names = Object.keys(groups).filter(Boolean).sort((a, b) => a.localeCompare(b));
    if (groups['']) names.push('');
    const byName = (a, b) => (a.name || '').localeCompare(b.name || '');
    return [h('div', { class: 'card' }, h('h2', {}, 'Bindings'),
      h('p', { class: 'sub' }, 'A binding links a button to another device directly over Zigbee, so it works even when Home Assistant is down. On Ripple firmware a binding follows the state of the button relay (physical or from Home Assistant). Only devices with Ripple firmware hold bindings; other devices can be their targets. Click a device to see its bindings.')),
    h('div', { class: 'bgroups' }, names.map((a) => h('section', { class: 'bgroup' },
      h('div', { class: 'bgh' }, a || 'Unassigned'),
      h('div', { class: 'tiles' }, groups[a].sort(byName).map((d) => this.bindTile(d, rows))))))];
  }

  bindTile(d, rows) {
    const n = rows.filter((b) => b.src === d.ieee || b.dst === d.ieee).length;
    const sec = n ? `${n} ${n === 1 ? 'binding' : 'bindings'}` : this.readAt(d.ieee) ? 'No bindings' : 'Not read yet';
    return h('button', { class: 'tile' + (n ? ' has' : ''), title: d.name, onclick: () => this.openBind(d.ieee) },
      h('span', { class: 'ti', props: { innerHTML: `<svg viewBox="0 0 24 24"><path d="${d.ripple ? P_SWITCH : P_DEVICE}"/></svg>` } }),
      h('span', { class: 'tt' }, h('span', { class: 'tn' }, d.name), h('span', { class: 'ts' }, d.available ? sec : `${sec}, offline`)));
  }

  openBind(ieee) {
    this.S.bmodal = ieee;
    const d = this.bdevs().find((x) => x.ieee === ieee);
    this._bdlg.replaceChildren(...this.bindModal(d, this.allBinds()));
    this._bdlg.showModal();
    this.loadEps(ieee);
    this.loadBinds().then(() => { if (this.S.bmodal === ieee && !this.readAt(ieee)) this.readBinds(ieee); });
  }

  bindModal(d, rows) {
    const at = this.readAt(d.ieee), err = (this.S.binds[d.ieee] || {}).error;
    const read = at ? (err ? `Last read at ${this.readTime(at)} failed: ${err}` : `Read from the device at ${this.readTime(at)}.`)
      : this.S.bindsLoaded ? 'Reading…' : 'Loading…';
    const canSend = this.eps(d.ieee).some((e) => e.onoff_out) || d.ours;
    const mine = rows.filter((b) => b.src === d.ieee), theirs = rows.filter((b) => b.dst === d.ieee);
    // a pair of bindings that link the same two elements in both directions is one element, not two
    const both = mine.filter((b) => this.dirTag(b) === 'both ways');
    const paired = (x) => both.some((b) => { const r = this.revOf(b); return r.src === x.src && r.sep === x.sep && r.dst === x.dst && r.dep === x.dep; });
    const controls = mine.filter((b) => !both.includes(b)), by = theirs.filter((b) => !paired(b));
    const tabs = [['both', 'Both ways', both], ['controls', 'Controls', canSend ? controls : []], ['by', 'Controlled by', by]];
    const want = (this.S.btab || {})[d.ieee];
    const tab = (tabs.find(([k, , l]) => k === want && l.length) || tabs.find(([, , l]) => l.length) || [])[0];
    const pair = (b) => h('div', { class: 'bind' },
      h('span', {}, h('b', {}, this.epName(d.ieee, b.sep)), ' ↔ ', this.devName(b.dst), ', ', this.epName(b.dst, b.dep)),
      h('button', { class: 'btn', onclick: () => this.unbindDlg(b) }, 'Remove'));
    const line = (b, out) => h('div', { class: 'bind' },
      h('span', {}, out ? [h('b', {}, this.epName(d.ieee, b.sep)), ' → ', this.devName(b.dst), ', ', this.epName(b.dst, b.dep)]
        : [this.devName(b.src), ', ', this.epName(b.src, b.sep), ' → ', h('b', {}, this.epName(d.ieee, b.dep))],
        h('span', { class: 'dir' }, this.dirTag(b)),
        this.dirTag(b) === 'reverse not read' ? h('button', { class: 'link', onclick: () => this.readBinds(this.revOf(b).src) }, `read ${this.devName(this.revOf(b).src)}`) : null),
      h('button', { class: 'btn', onclick: () => this.unbindDlg(b) }, 'Remove'));
    const list = (items, out) => (items.length ? items.map((b) => line(b, out)) : h('div', { class: 'empty left' }, 'None.'));
    return [
      h('h3', {}, d.name, d.ours ? null : [' ', h('span', { class: 'state novote' }, 'no Ripple firmware')]),
      d.area ? h('p', { class: 'sub' }, d.area) : null,
      h('div', { class: 'btabs', role: 'tablist' }, tabs.map(([k, t, l]) => h('button', {
        class: k === tab ? 'on' : '', role: 'tab', disabled: !l.length,
        onclick: () => { this.S.btab = { ...(this.S.btab || {}), [d.ieee]: k }; this.render(); },
      }, t, l.length ? h('small', {}, String(l.length)) : null))),
      tab === 'both' ? both.map(pair) : tab === 'controls' ? list(controls, true) : tab === 'by' ? list(by, false)
        : h('div', { class: 'empty left' }, 'No bindings.'),
      canSend ? this.bindForm(d) : null,
      h('div', { class: 'bfoot' }, h('span', {}, read),
        this.S.bmsg[d.ieee] ? h('span', {}, this.S.bmsg[d.ieee]) : null, h('span', { class: 'spacer' }),
        h('button', { class: 'btn', onclick: () => this.readBinds(d.ieee) }, 'Read again')),
      h('div', { class: 'acts' }, h('button', { class: 'btn pri', onclick: () => this._bdlg.close() }, 'Close')),
    ].flat(Infinity).filter((x) => x != null && x !== false);
  }

  bsel(ph, opts, cur, set) {
    const s = h('select', { onchange: (e) => { const v = e.target.value; set(v ? (/^\d+$/.test(v) ? +v : v) : null); this.render(); } },
      h('option', { value: '' }, ph), opts.map(([v, t]) => h('option', { value: v }, t)));
    s.value = cur ?? ''; s._val = String(cur ?? '');
    return s;
  }

  bindForm(d) {
    const f = (this.S.bf[d.ieee] ||= {});
    const txt = (id, ep) => this.epName(id, ep)[0];
    const dsts = this.bdevs().filter((x) => x.ieee !== d.ieee);
    if (f.dst) this.loadEps(f.dst);
    const rev = f.sep && f.dst && f.dep ? this.revOf({ src: d.ieee, sep: f.sep, dst: f.dst, dep: f.dep }) : null;
    const both = !!rev && f.both !== false;
    return [h('div', { class: 'bform' },
      h('label', {}, 'When you press', this.bsel('Pick a button', this.eps(d.ieee).filter((e) => e.onoff_out).map((e) => [e.ep, txt(d.ieee, e.ep)]), f.sep, (v) => { f.sep = v; })),
      h('label', {}, 'also device', this.bsel('Pick a device', dsts.map((x) => [x.ieee, x.name]), f.dst, (v) => { f.dst = v; f.dep = null; })),
      h('label', {}, 'relay / output', this.bsel(f.dst ? 'Pick an endpoint' : 'Pick a device first',
        f.dst ? this.eps(f.dst).filter((e) => e.onoff_in).map((e) => [e.ep, `${txt(f.dst, e.ep)}, ep ${e.ep}`]) : [], f.dep, (v) => { f.dep = v; })),
      h('label', { class: 'both' + (rev ? '' : ' off'), title: rev ? '' : f.dst && !this.isOurs(f.dst) ? 'This device cannot hold a binding: it does not run Ripple firmware.'
        : 'Only when the target is a relay of a Ripple device: only Ripple devices send commands on a button press.' },
        h('input', { type: 'checkbox', checked: both, disabled: !rev, onchange: (e) => { f.both = e.target.checked; this.render(); } }), 'also reverse'),
      h('button', { class: 'btn pri', disabled: !(f.sep && f.dst && f.dep), onclick: () => this.addBind(d, f) }, 'Add binding')),
    both ? h('p', { class: 'brev' }, `The reverse binding is added too: ${this.devName(rev.src)}, ${txt(rev.src, rev.sep)} → ${d.name}, ${txt(d.ieee, rev.dep)}.`) : null];
  }

  async addBind(d, f) {
    const b = { src: d.ieee, sep: f.sep, dst: f.dst, dep: f.dep };
    const rev = f.both !== false ? this.revOf(b) : null;
    const done = [];
    for (const x of [b, rev].filter(Boolean)) {
      if (this.findB(x)) continue;
      const ok = await this._call('bindings/add', { src: x.src, src_ep: x.sep, dst: x.dst, dst_ep: x.dep });
      if (ok) { done.push(`${this.devName(x.src)} ep ${x.sep} → ${this.devName(x.dst)} ep ${x.dep}`); await this.loadBinds(); }
    }
    this.S.bmsg[d.ieee] = done.length ? `Sent (On/Off), read back. ${done.join('; ')}.` : 'This binding already exists.';
    this.S.bf[d.ieee] = {};
    this.render();
  }

  unbindDlg(b) {
    const d = this._dlg;
    const r = this.revOf(b), back = r && this.findB(r);
    const del = (list) => async () => {
      d.close();
      for (const x of list) {
        if (await this._call('bindings/remove', { src: x.src, src_ep: x.sep, dst: x.dst })) await this.loadBinds();
      }
      this.S.bmsg[b.src] = `Removed: ${list.map((x) => `${this.devName(x.src)} ep ${x.sep} → ${this.devName(x.dst)} ep ${x.dep}`).join('; ')}.`;
      this.render();
    };
    dlgSet(d, h('h3', {}, 'Remove binding'),
      h('p', {}, this.devName(b.src), ', ', this.epName(b.src, b.sep), ' → ', this.devName(b.dst), ', ', this.epName(b.dst, b.dep)),
      back ? h('p', {}, 'The reverse exists too: ', this.devName(back.src), ', ', this.epName(back.src, back.sep), ' → ', this.devName(back.dst), ', ', this.epName(back.dst, back.dep)) : null,
      h('p', { class: 'sub' }, back ? 'You can remove only this direction or both. Other bindings and the ones to Home Assistant stay.'
        : 'Only this binding is removed (this button, this device, the On/Off cluster). Other bindings and the ones to Home Assistant stay.'),
      h('div', { class: 'acts' }, h('button', { class: 'btn', onclick: () => d.close() }, 'Cancel'),
        back ? h('button', { class: 'btn', onclick: del([b]) }, 'Only this direction') : null,
        h('button', { class: 'btn live', onclick: del(back ? [b, back] : [b]) }, back ? 'Both directions' : 'Remove')));
    d.showModal();
  }
}

if (!customElements.get('ripple-panel')) customElements.define('ripple-panel', RipplePanel);

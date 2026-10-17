/* Dev canvas (Ethan 2026-10-16: "a dev canvas so i can mess around and fine tune your designs"; standing rule: every site
   build ships an in-page toolkit). Off unless turned on: ?dev=1 turns it on for this browser (it stays on), ?dev=0 off;
   always on for localhost. It changes only this viewer's browser (localStorage aw.dev), so it is safe on the live site.
   Reaches: the layout (card / column), every colour token, the two type faces and the title size, the panel's width and
   margin, and the year scrubber (band darkness, tick heights and counts, swell width, glide). Export copies the picks as a
   CSS block plus the scrubber knobs, to paste back to Claude so they become the code. */
(() => {
  const q = new URLSearchParams(location.search).get('dev');
  const ls = { get(k) { try { return localStorage.getItem(k); } catch { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch {} }, del(k) { try { localStorage.removeItem(k); } catch {} } };
  if (q === '1') ls.set('aw.devOn', '1');
  if (q === '0') ls.del('aw.devOn');
  const local = ['localhost', '127.0.0.1'].includes(location.hostname);
  if (q === '0' || (!local && ls.get('aw.devOn') !== '1')) return;

  const root = document.documentElement;
  const COLORS = [
    ['--sheet', 'Panel paper'], ['--paper', 'Paper'], ['--paper-2', 'Paper, darker'], ['--ink', 'Ink'], ['--ink-2', 'Ink, mid grey'],
    ['--hair', 'Hairlines'], ['--rule', 'Rules'], ['--survey', 'State red'], ['--space', 'Space round the globe'],
    ['--on-map', 'Lettering on the map'],
  ];
  const FONTS = {
    '--title': ['"Inter", -apple-system, "Helvetica Neue", Arial, sans-serif', '"Old Standard TT", "Century Schoolbook", Georgia, serif', 'Georgia, serif', '"Iowan Old Style", Georgia, serif', '"Times New Roman", serif', '"Helvetica Neue", Arial, sans-serif'],
    '--label': ['"Inter", -apple-system, "Helvetica Neue", Arial, sans-serif', '"Archivo Narrow", "Arial Narrow", Arial, sans-serif', '"Helvetica Neue", Arial, sans-serif', 'ui-monospace, Menlo, monospace', '"Old Standard TT", Georgia, serif'],
  };
  // [token or TUNE key, label, min, max, step, unit]
  const KNOBS = [
    ['--title-size', 'Title size', 16, 44, 1, 'px'], ['--card-w', 'Card width', 260, 520, 10, 'px'], ['--col-w', 'Column width', 280, 520, 10, 'px'],
    ['--gap', 'Margin', 0, 48, 2, 'px'], ['--float-w', 'Floating width', 260, 560, 10, 'px'], ['--halo-a', 'Halo strength', 0, 1, .02, ''], ['--scrim-a', 'Shade behind text', 0, 1, .02, ''], ['--year-size', 'Year size', 24, 120, 2, 'px'],
    ['--tick-peak', 'Tick height, peak', 12, 80, 1, 'px'], ['--tick-base', 'Tick height, rest', 2, 24, 1, 'px'], ['--tick-stop', 'Tick height, a map', 2, 40, 1, 'px'],
    ['ticks', 'Ticks across (desktop)', 16, 160, 2, ''], ['ticksPhone', 'Ticks across (phone)', 12, 100, 2, ''],
    ['sigma', 'Swell width (ticks)', .5, 10, .25, ''], ['glide', 'Glide speed', .04, .6, .01, ''], ['follow', 'Drag follow', .1, 1, .05, ''],
  ];
  // 2026-10-17: the page's own palette is 'Neutral' (cool greys, white panel); 'Plate paper' is the cream it replaced
  const PRESETS = {
    'Neutral': {},
    'Stone': { '--sheet': '#FAFAF9', '--paper': '#F2F1EF', '--paper-2': '#E6E4E0', '--ink': '#1C1917', '--ink-2': '#57534E', '--hair': '#E7E5E4', '--rule': '#A8A29E' },
    'Graphite': { '--sheet': '#17191D', '--paper': '#0F1114', '--paper-2': '#262930', '--ink': '#EEF0F3', '--ink-2': '#9BA1AB', '--hair': '#2C3036', '--rule': '#5A606A', '--edge': 'rgba(255, 255, 255, .14)' },
    'Plate paper': { '--sheet': '#F8F4E8', '--paper': '#F3EDDC', '--paper-2': '#EAE2CC', '--ink': '#2B2724', '--ink-2': '#6B625A', '--hair': '#D9D0BD', '--rule': '#8E8478', '--space': '#10141C',
      '--title': '"Old Standard TT", "Century Schoolbook", Georgia, serif', '--label': '"Archivo Narrow", "Arial Narrow", Arial, sans-serif' },
  };
  const state = (() => { try { return JSON.parse(ls.get('aw.dev') || '{}'); } catch { return {}; } })();
  state.vars = state.vars || {}; state.tune = state.tune || {};
  const base = {};  // the page's own values, for reset and export diffs
  const cs = getComputedStyle(root);
  for (const [k] of COLORS) base[k] = cs.getPropertyValue(k).trim();
  for (const k of Object.keys(FONTS)) base[k] = cs.getPropertyValue(k).trim();
  for (const [k] of KNOBS) base[k] = k.startsWith('--') ? cs.getPropertyValue(k).trim() : TUNE[k];
  const save = () => ls.set('aw.dev', JSON.stringify(state));
  const num = v => parseFloat(v);
  // the scrubber reads tick sizes and counts when it is built: rebuild it (and the phone's lens bar) after a change
  let rb = 0;
  const rebuild = () => { cancelAnimationFrame(rb); rb = requestAnimationFrame(() => { try { if (S.sel && S.byId[S.sel] && !P.active && document.querySelector('#body .site-title')) renderSite(S.byId[S.sel]); } catch {} }); };
  function applyAll() {
    for (const [k, v] of Object.entries(state.vars)) root.style.setProperty(k, v);
    for (const [k, v] of Object.entries(state.tune)) TUNE[k] = v;
    if (state.layout) setLayout(state.layout);
  }
  applyAll();

  const css = `
  .dk { position: fixed; z-index: 50; top: 12px; right: 56px; width: 292px; max-height: calc(100% - 200px);  /* never down over the scrubber's band */ display: flex; flex-direction: column;
    background: #1B1916; color: #EDE6DA; font: 12px/1.35 -apple-system, "Helvetica Neue", Arial, sans-serif; box-shadow: 0 10px 30px rgba(0,0,0,.4); }
  .dk * { box-sizing: border-box; }
  .dk-h { display: flex; align-items: center; gap: 8px; padding: 8px 10px; cursor: move; user-select: none; border-bottom: 1px solid #36312B; }
  .dk-h b { flex: 1; font-size: 10.5px; letter-spacing: .16em; text-transform: uppercase; }
  .dk-h button, .dk button { background: #2A2622; color: #EDE6DA; border: 1px solid #45403A; font: 600 10.5px/1 inherit; letter-spacing: .06em; padding: 5px 8px; cursor: pointer; }
  .dk button:hover { border-color: #EDE6DA; }
  .dk button[aria-pressed="true"] { background: #EDE6DA; color: #1B1916; border-color: #EDE6DA; }
  .dk-b { overflow-y: auto; padding: 4px 10px 12px; }
  .dk.min .dk-b { display: none; }
  .dk h4 { margin: 12px 0 6px; font-size: 10px; letter-spacing: .16em; text-transform: uppercase; color: #9E968B; font-weight: 600; }
  .dk-row { display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 8px; padding: 2px 0; }
  .dk-row.k { grid-template-columns: 104px 1fr 40px; }
  .dk-row span { color: #CFC7BB; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .dk-row output { text-align: right; font-variant-numeric: tabular-nums; color: #9E968B; font-size: 11px; }
  .dk input[type=color] { width: 44px; height: 22px; padding: 0; border: 1px solid #45403A; background: none; cursor: pointer; }
  .dk input[type=range] { width: 100%; accent-color: #EDE6DA; height: auto; -webkit-appearance: auto; appearance: auto; }
  .dk input[type=range]::-webkit-slider-runnable-track, .dk input[type=range]::-webkit-slider-thumb { all: revert; }
  .dk select { width: 100%; background: #2A2622; color: #EDE6DA; border: 1px solid #45403A; font: 11px inherit; padding: 4px; }
  .dk-btns { display: flex; flex-wrap: wrap; gap: 5px; }
  .dk textarea { width: 100%; height: 120px; margin-top: 6px; background: #12100E; color: #CFC7BB; border: 1px solid #36312B; font: 10.5px/1.4 ui-monospace, Menlo, monospace; resize: vertical; }
  .dk-note { margin: 6px 0 0; color: #9E968B; font-size: 11px; }
  @media (max-width: 760px) { .dk { top: auto; bottom: 8px; right: 8px; left: 8px; width: auto; max-height: 52vh; } }`;
  const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);

  const el = document.createElement('section'); el.className = 'dk' + (state.min ? ' min' : ''); el.setAttribute('aria-label', 'Dev canvas');
  const cur = k => k.startsWith('--') ? (state.vars[k] ?? base[k]) : (state.tune[k] ?? base[k]);
  const hex = v => /^#[0-9a-f]{6}$/i.test(v) ? v : /^#[0-9a-f]{3}$/i.test(v) ? '#' + [...v.slice(1)].map(c => c + c).join('') : '#000000';
  el.innerHTML = `
    <div class="dk-h"><b>Dev canvas</b><button data-a="min">${state.min ? 'Open' : 'Fold'}</button><button data-a="off" title="Turn the dev canvas off in this browser">Off</button></div>
    <div class="dk-b">
      <h4>Layout</h4>
      <div class="dk-btns">${LAYOUTS.map(l => `<button data-lay="${l}">${{ float: 'Floating', card: 'Card', column: 'Column' }[l]}</button>`).join('')}</div>
      <h4>Presets</h4>
      <div class="dk-btns">${Object.keys(PRESETS).map(n => `<button data-pre="${n}">${n}</button>`).join('')}</div>
      <h4>Colour</h4>
      ${COLORS.map(([k, l]) => `<label class="dk-row"><span>${l} <small style="color:#7A7268">${k}</small></span><input type="color" data-c="${k}" value="${hex(cur(k))}"></label>`).join('')}
      <h4>Type</h4>
      ${Object.entries(FONTS).map(([k, opts]) => `<label class="dk-row" style="grid-template-columns:52px 1fr"><span>${k === '--title' ? 'Serif' : 'Labels'}</span><select data-f="${k}">${[...new Set([cur(k), ...opts])].map(o => `<option ${o === cur(k) ? 'selected' : ''}>${o.replace(/</g, '')}</option>`).join('')}</select></label>`).join('')}
      <h4>Size and scrubber</h4>
      ${KNOBS.map(([k, l, a, b, s, u]) => `<label class="dk-row k"><span title="${k}">${l}</span><input type="range" data-k="${k}" data-u="${u}" min="${a}" max="${b}" step="${s}" value="${num(cur(k))}"><output>${num(cur(k))}${u}</output></label>`).join('')}
      <h4>Keep it</h4>
      <div class="dk-btns"><button data-a="export">Copy export</button><button data-a="reset">Reset all</button></div>
      <textarea readonly placeholder="Copy export puts the picks here and on the clipboard: paste them to Claude."></textarea>
      <p class="dk-note">Only your browser sees these. Off (or ?dev=0) hides the canvas and its picks; ?dev=1 brings both back.</p>
    </div>`;
  document.body.appendChild(el);
  const $$ = s => el.querySelectorAll(s);
  const syncLay = () => $$('[data-lay]').forEach(b => b.setAttribute('aria-pressed', String(document.body.classList.contains('lay-' + b.dataset.lay))));
  syncLay();
  $$('[data-lay]').forEach(b => b.onclick = () => { state.layout = setLayout(b.dataset.lay, true); save(); syncLay(); });
  $$('[data-c]').forEach(i => i.oninput = () => { state.vars[i.dataset.c] = i.value; root.style.setProperty(i.dataset.c, i.value); save(); });
  $$('[data-f]').forEach(s => s.onchange = () => { state.vars[s.dataset.f] = s.value; root.style.setProperty(s.dataset.f, s.value); save(); });
  $$('[data-k]').forEach(i => i.oninput = () => {
    const k = i.dataset.k, v = +i.value;
    i.nextElementSibling.textContent = v + i.dataset.u;
    if (k.startsWith('--')) { state.vars[k] = v + i.dataset.u; root.style.setProperty(k, v + i.dataset.u); }
    else { state.tune[k] = v; TUNE[k] = v; }
    save();
    if (/tick|ticks|sigma/.test(k)) rebuild();
  });
  const refresh = () => {
    $$('[data-c]').forEach(i => { i.value = hex(cur(i.dataset.c)); });
    $$('[data-k]').forEach(i => { i.value = num(cur(i.dataset.k)); i.nextElementSibling.textContent = num(cur(i.dataset.k)) + i.dataset.u; });
    $$('[data-f]').forEach(s => { s.value = cur(s.dataset.f); });
  };
  $$('[data-pre]').forEach(b => b.onclick = () => {
    for (const k of new Set([...COLORS.map(c => c[0]), ...Object.values(PRESETS).flatMap(Object.keys)])) { delete state.vars[k]; root.style.removeProperty(k); }
    Object.assign(state.vars, PRESETS[b.dataset.pre]);
    applyAll(); save(); refresh();
  });
  el.querySelector('[data-a="reset"]').onclick = () => {
    for (const k of Object.keys(state.vars)) root.style.removeProperty(k);
    for (const k of Object.keys(state.tune)) TUNE[k] = base[k];
    state.vars = {}; state.tune = {}; delete state.layout; setLayout('card', true); save(); refresh(); syncLay(); rebuild();
  };
  el.querySelector('[data-a="export"]').onclick = () => {
    const lay = LAYOUTS.find(l => document.body.classList.contains('lay-' + l));
    const vars = Object.entries(state.vars).filter(([k, v]) => String(v) !== String(base[k]));
    const tune = Object.entries(state.tune).filter(([k, v]) => v !== base[k]);
    const out = `/* Resurface dev canvas export ${new Date().toISOString().slice(0, 16)} */\n/* layout: ${lay} */\n:root {\n${vars.map(([k, v]) => `  ${k}: ${v};`).join('\n') || '  /* no token changes */'}\n}\n/* scrubber knobs (TUNE) */\n${JSON.stringify(Object.fromEntries(tune))}\n`;
    const ta = el.querySelector('textarea'); ta.value = out; ta.select();
    try { navigator.clipboard.writeText(out); } catch {}
  };
  el.querySelector('[data-a="min"]').onclick = e => { state.min = !state.min; el.classList.toggle('min', state.min); e.target.textContent = state.min ? 'Open' : 'Fold'; save(); };
  el.querySelector('[data-a="off"]').onclick = () => { ls.del('aw.devOn'); el.remove(); };
  // drag by the header
  const h = el.querySelector('.dk-h'); let d = null;
  h.onpointerdown = e => { if (e.target.closest('button')) return; const r = el.getBoundingClientRect(); d = { x: e.clientX - r.left, y: e.clientY - r.top }; h.setPointerCapture(e.pointerId); };
  h.onpointermove = e => { if (!d) return; el.style.left = Math.max(0, e.clientX - d.x) + 'px'; el.style.top = Math.max(0, e.clientY - d.y) + 'px'; el.style.right = 'auto'; el.style.bottom = 'auto'; };
  h.onpointerup = () => { d = null; };
})();

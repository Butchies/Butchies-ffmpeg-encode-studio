/* ffmpeg_encode Studio – Oberfläche */
'use strict';
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const TOKEN = (location.hash.slice(1) || sessionStorage.getItem('fes-token') || '');
const KIWIN = new URLSearchParams(location.search).get('ki') === '1';     // eigenes KI-Video-Fenster (2. Monitor)
if (TOKEN) { sessionStorage.setItem('fes-token', TOKEN); history.replaceState(null, '', location.pathname + location.search) }

// Designs der Butchies-Webseite: id, Name, Untertitel, Hintergrund, Farbe A, Farbe B, Layout/Schrift, Überschrift-Schrift
const THEMES = [
  ['neon', 'Neon Lila', 'Das Original', '#0b0614', '#a46bff', '#ff6fc4', 'club', 'Unbounded'],
  ['ocean', 'Ozean', 'Kühles Blau', '#03101a', '#38bdf8', '#22d3ee', 'wellen', 'Quicksand'],
  ['sunset', 'Sunset', 'Warm & glühend', '#140708', '#ff7a45', '#ff4f9a', 'magazin', "'Playfair Display'"],
  ['emerald', 'Smaragd', 'Frisches Grün', '#04110c', '#2fd38f', '#a3e635', 'studio', "'Space Grotesk'"],
  ['gold', 'Gold Lounge', 'Edel & dunkel', '#0d0a05', '#f5b544', '#ffdf8a', 'lounge', "'Cormorant Garamond'"],
  ['mono', 'Mitternacht', 'Schwarz-Weiß', '#0a0a0a', '#e5e5e5', '#9ca3af', 'index', "'Archivo Black'"],
  ['light', 'Hell', 'Für den Tag', '#f6f2fb', '#7c3aed', '#db2777', 'tag', 'Manrope'],
  ['bluewhite', 'Blau-Weiß', 'Klar & frisch', '#ffffff', '#1668e3', '#38a3ff', 'klar', 'Outfit']
];
const FORMATS = [
  ['yt4k', 'YouTube 4K', '3840 × 2160 · 16:9', false, true],
  ['yt1440', 'YouTube 1440p', '2560 × 1440 · 16:9', false, false],
  ['yt1080', 'YouTube 1080p', '1920 × 1080 · 16:9', false, false],
  ['sh1080', 'YouTube Shorts', '1080 × 1920 · 9:16 · max. 3 Min.', true, false],
  ['sh4k', 'YouTube Shorts 4K', '2160 × 3840 · 9:16 · max. 3 Min.', true, true]
];
const FITS = [
  ['blur', 'Unschärfe-Hintergrund', 'Bild mittig, unscharfe Kopie füllt den Rand'],
  ['cover', 'Füllen', 'Bild füllt alles, Ränder werden abgeschnitten'],
  ['contain', 'Einpassen', 'Ganzes Bild sichtbar, schwarze Balken']
];
const ENC_SUB = { auto: 'nimmt die Grafikkarte, sonst die CPU',  x264: 'CPU · beste Kompatibilität', x265: 'CPU · kleinere Datei', nvenc: 'NVIDIA-Grafikkarte', qsv: 'Intel-Grafik', amf: 'AMD-Grafikkarte' };
const ENC_NAME = { auto: 'Automatisch',  x264: 'H.264', x265: 'H.265 / HEVC', nvenc: 'NVENC', qsv: 'Quick Sync', amf: 'AMD AMF' };
const PRESETS = [['Aus', 0, 0], ['Sanft · 1 s', 1, 1], ['Standard · 2 / 3 s', 2, 3], ['Lang · 5 s', 5, 5]];
const ICON = {
  music: '<svg viewBox="0 0 24 24"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>',
  image: '<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="M21 16l-5-5-9 9"/></svg>',
  x: '<svg viewBox="0 0 24 24"><path d="M18 6 6 18M6 6l12 12"/></svg>',
  check: '<svg viewBox="0 0 24 24"><path d="M20 6 9 17l-5-5"/></svg>',
  warn: '<svg viewBox="0 0 24 24"><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/></svg>',
  play: '<svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>',
  pause: '<svg viewBox="0 0 24 24"><path d="M7 5h4v14H7zM13 5h4v14h-4z"/></svg>'
};

const S = {
  info: null, settings: null, audio: null, image: null, outdir: '', outEdited: false, meta: null, autoName: '',
  wave: null, theme: localStorage.getItem('fes-theme') || 'gold', job: null, jobs: []
};

/* ---------- Hilfen ---------- */
async function api(path, body) {
  const r = await fetch(path, body === undefined ? { headers: { 'X-Studio': TOKEN } } : { method: 'POST', headers: { 'X-Studio': TOKEN, 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  let d = {}; try { d = await r.json() } catch (_) {}
  if (!r.ok) throw new Error(d.error || 'Fehler ' + r.status);
  return d;
}
function toast(msg, bad) {
  const t = document.createElement('div'); t.className = 'toast' + (bad ? ' bad' : ''); t.textContent = msg;
  $('#toasts').append(t); setTimeout(() => t.remove(), bad ? 6500 : 3200);
}
function el(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else if (k === 'html') e.innerHTML = v;
    else if (k === 'style') e.style.cssText = v;
    else e.setAttribute(k, v === true ? '' : v);
  }
  for (const k of kids.flat()) if (k != null && k !== false) e.append(k.nodeType ? k : document.createTextNode(k));
  return e;
}
const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms) } };
function toSec(t) {
  t = String(t || '').trim().replace(',', '.'); if (!t) return null;
  const p = t.split(':').map(Number); if (p.length > 3 || p.some(x => isNaN(x) || x < 0)) return NaN;
  return p.reduce((a, b) => a * 60 + b, 0);
}
function mmss(s) {
  s = Math.max(0, Math.round(s || 0)); const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), r = s % 60;
  return h ? `${h}:${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}` : `${m}:${String(r).padStart(2, '0')}`;
}
const secDe = v => (Math.round(v * 10) / 10).toFixed(1).replace('.', ',') + ' s';
const size = b => b > 1e9 ? (b / 1e9).toFixed(2).replace('.', ',') + ' GB' : b > 1e6 ? (b / 1e6).toFixed(1).replace('.', ',') + ' MB' : Math.round(b / 1e3) + ' KB';
const fmtOf = id => FORMATS.find(f => f[0] === id) || FORMATS[0];
const audioDur = () => (S.audio && S.audio.info.duration) || 0;
function ask(title, text, yes = 'OK') {
  return new Promise(res => {
    const d = $('#askDlg'); $('#askTitle').textContent = title; $('#askText').textContent = text; $('#askYes').textContent = yes;
    const done = v => { d.close(); res(v) };
    $('#askYes').onclick = () => done(true); $('#askNo').onclick = () => done(false); d.oncancel = () => res(false);
    d.showModal();
  });
}
$$('[data-close]').forEach(b => b.addEventListener('click', () => b.closest('dialog').close()));

/* ---------- Designs ---------- */
function applyTheme(id, save) {
  const t = THEMES.find(x => x[0] === id) || THEMES[4];
  S.theme = t[0]; document.body.dataset.theme = t[0]; document.body.dataset.skin = t[6];
  try { localStorage.setItem('fes-theme', t[0]) } catch (_) {}
  if (save) api('/api/config', { theme: t[0] }).catch(() => {});
  drawWave(); renderViz(true);
}
function openThemes() {
  const grid = $('#themeGrid'); grid.textContent = '';
  for (const [id, name, sub, bg, a, b, , font] of THEMES) {
    grid.append(el('button', {
      type: 'button', class: 'theme-opt' + (id === 'light' || id === 'bluewhite' ? ' is-light' : ''), 'aria-pressed': String(id === S.theme),
      style: `--tbg:${bg};--ta:${a};--tb:${b};--tf:${font}`,
      onclick: e => { applyTheme(id, true); $$('.theme-opt', grid).forEach(x => x.setAttribute('aria-pressed', String(x === e.currentTarget))) }
    }, el('div', { class: 'sw' }), el('b', {}, name), el('small', {}, sub), el('span', { class: 'tick', html: ICON.check })));
  }
  $('#introCheck').checked = !S.info || S.info.intro !== false;
  $('#themeDlg').showModal();
}
$('#themeBtn').onclick = openThemes;
$('#introCheck').onchange = e => { if (S.info) S.info.intro = e.target.checked; api('/api/config', { intro: e.target.checked }).catch(() => {}) };

/* ---------- Auswahl-Elemente ---------- */
function set(k, v) { S.settings[k] = v; changed(k) }
function renderFormats() {
  const box = $('#fmtList'); box.textContent = '';
  for (const [id, name, sub, tall, k4] of FORMATS) {
    box.append(el('button', { type: 'button', class: 'opt', 'aria-pressed': String(S.settings.fmt === id), onclick: () => set('fmt', id) },
      el('span', { class: 'ic', 'aria-hidden': 'true' }, el('i', { style: tall ? 'width:13px;height:22px' : 'width:22px;height:13px' })),
      el('span', { class: 'tx' }, el('b', {}, name), el('small', {}, sub)), k4 ? el('span', { class: 'tag4k' }, '4K') : null));
  }
}
function renderFits() {
  const box = $('#fitList'); box.textContent = '';
  for (const [id, name, sub] of FITS)
    box.append(el('button', { type: 'button', class: 'opt', 'aria-pressed': String(S.settings.fit === id), onclick: () => set('fit', id) },
      el('span', { class: 'tx' }, el('b', {}, name), el('small', {}, sub))));
}
function renderFps() {
  const box = $('#fpsSeg'); box.textContent = '';
  for (const f of [24, 25, 30, 50, 60]) box.append(el('button', { type: 'button', 'aria-pressed': String(S.settings.fps === f), onclick: () => set('fps', f) }, String(f)));
}
function renderEnc() {
  const box = $('#encGrid'); box.textContent = '';
  const encs = (S.info && S.info.encoders) || {};
  for (const id of ['auto', 'x264', 'x265', 'nvenc', 'qsv', 'amf']) {
    const ok = id === 'auto' ? true : encs[id] ? encs[id].ok : null;
    box.append(el('button', {
      type: 'button', class: 'enc', 'aria-pressed': String(S.settings.enc === id), disabled: ok === false,
      title: ok === false ? 'Auf diesem PC nicht verfügbar' : ok === null ? 'Wird geprüft …' : '', onclick: () => set('enc', id)
    }, el('b', {}, id === 'auto' ? 'Automatisch (schnellste)' : ENC_NAME[id]),
      el('small', {}, id === 'auto' ? autoLabel() : ok === false ? 'nicht verfügbar' : ok === null ? 'wird geprüft …' : ENC_SUB[id])));
    if (id === 'auto') box.lastChild.classList.add('auto');
  }
}
function autoLabel() {
  if (!S.info || !S.info.hw_done) return 'Grafikkarte wird gesucht …';
  const e = S.info.auto_enc;
  return ['nvenc', 'qsv', 'amf'].includes(e) ? '→ Grafikkarte: ' + ENC_NAME[e] : '→ keine Grafikkarte gefunden, nimmt CPU (H.264)';
}
const encLabel = id => id === 'auto' ? (S.info && S.info.hw_done ? ENC_NAME[S.info.auto_enc] + ' (auto)' : 'Automatisch') : ENC_NAME[id];
function renderSeg(sel, key) { $$('button', $(sel)).forEach(b => b.setAttribute('aria-pressed', String(String(S.settings[key]) === b.dataset.v))) }
$$('#colorSeg button').forEach(b => b.onclick = () => set('color', b.dataset.v));
PRESETS.forEach(([n, a, b]) => $('#presets').append(el('button', { type: 'button', onclick: () => { S.settings.fadeIn = a; S.settings.fadeOut = b; changed('fade') } }, n)));
$('#fadeIn').oninput = e => set('fadeIn', +e.target.value);
$('#fadeOut').oninput = e => set('fadeOut', +e.target.value);
$('#target').onchange = e => set('target', e.target.value);
$('#transIn').onchange = e => { set('transIn', e.target.value); previewTrans('in') };
$('#transOut').onchange = e => { set('transOut', e.target.value); previewTrans('out') };
$('#prevIn').onclick = () => previewTrans('in');
$('#prevOut').onclick = () => previewTrans('out');
function fillTransitions(list) {
  for (const id of ['#transIn', '#transOut']) {
    const sel = $(id); sel.textContent = '';
    sel.append(el('option', { value: 'none' }, 'Ohne Übergang (harter Schnitt)'));
    let grp = null, last = '';
    for (const t of list) {
      if (t.group !== last) { grp = el('optgroup', { label: t.group }); sel.append(grp); last = t.group }
      grp.append(el('option', { value: t.id }, t.name));
    }
  }
}
let clipSeq = 0;
async function previewTrans(which) {
  if (!S.image) { toast('Für die Vorschau zuerst ein Bild hineinziehen'); return }
  if ((which === 'in' ? S.settings.fadeIn : S.settings.fadeOut) <= 0) toast('Hinweis: Die Dauer steht auf 0 s – im Video ist der Übergang dann aus.');
  const my = ++clipSeq; $('#stillBusy').hidden = false;
  try {
    const d = await api('/api/trans-preview', { settings: S.settings, image: S.image.token, which });
    if (my !== clipSeq) return;
    const v = $('#clipVid'); v.src = d.url + '?t=' + Date.now(); v.hidden = false;
    v.onended = () => setTimeout(() => { v.hidden = true }, 500);
    v.play().catch(() => {});
  } catch (e) { toast(e.message, true) }
  finally { if (my === clipSeq) $('#stillBusy').hidden = true }
}
$('#quality').onchange = e => set('quality', e.target.value);
function themeColors() { const t = THEMES.find(x => x[0] === S.theme) || THEMES[4]; return [t[4], t[5]] }
/* ---------- Audio-Visualizer: Stile, Farben, Andocken ---------- */
const VSTYLES = [
  ['wave', 'Wellenform', 'Welle'], ['line', 'Feine Linie', 'Linie'], ['neon', 'Neon-Welle mit Leuchten', 'Neon'], ['dots', 'Punkte-Welle', 'Punkte'],
  ['strokes', 'Strich-Welle', 'Striche'], ['bundle', 'Wellenbündel', 'Bündel'], ['bars', 'Spektrum-Balken', 'Balken'], ['thin', 'Feine Spektrum-Striche', 'Fein'],
  ['specline', 'Spektrum-Linie', 'Kurve'], ['mirror', 'Spiegel-Spektrum (Mitte)', 'Spiegel'], ['reflect', 'Balken mit Bodenspiegelung', 'Boden'],
  ['centerbars', 'Balken oben + unten', 'Oben/Unten'], ['led', 'LED-Equalizer', 'LED'], ['leddots', 'LED-Punkte', 'LED-Punkte'], ['cqt', 'Musik-Balken (Tonleiter)', 'Tonleiter'],
  ['combo', 'Balken + Welle', 'Kombi'], ['spectro', 'Spektrogramm-Laufband', 'Laufband'], ['vu', 'VU-Meter (Pegel)', 'Pegel'], ['scope', 'Lissajous-Figur', 'Lissajous'],
  ['glowbars', 'Leucht-Balken', 'Leuchten']
];
const AI_WAVES = [['neon', 'Neon'], ['wave', 'Welle'], ['line', 'Linie'], ['dots', 'Punkte'], ['bundle', 'Bündel']];
const WAVE_FAMILY = ['wave', 'line', 'neon', 'dots', 'strokes', 'bundle'];
const effStyle = s => s.vizAi ? s.vizAiWave : s.vizStyle;
const VMODES = [['solid', 'Einfarbig'], ['gradient', 'Verlauf'], ['rainbow', 'Regenbogen'], ['random', 'Zufall'], ['sound', 'Nach Sound']];
const VHINT = {
  solid: 'Eine feste Farbe für den ganzen Visualizer.',
  gradient: 'Farbverlauf von links nach rechts zwischen Farbe 1 und Farbe 2.',
  rainbow: 'Alle Regenbogenfarben über die ganze Breite.',
  random: 'Zufällige Farbkombination, die sich im Video langsam weiterdreht. Gefällt sie nicht: neu würfeln.',
  sound: 'Farbe folgt der Musik: tiefe Töne warm, hohe kühl, laute Stellen heller. Wird beim Konvertieren aus deinem Song berechnet.'
};
const RAINBOW = ['#ff3b3b', '#ff9f1c', '#ffe14d', '#3ddc84', '#2ec5ff', '#5b6cff', '#c04dff'];
const DOCKS = [['tl', 'Oben links', 0, 0], ['tc', 'Oben mittig', 1, 0], ['tr', 'Oben rechts', 2, 0], ['ml', 'Mitte links', 0, 1], ['mc', 'Bildmitte', 1, 1], ['mr', 'Mitte rechts', 2, 1],
  ['bl', 'Unten links', 0, 2], ['bc', 'Unten mittig', 1, 2], ['br', 'Unten rechts', 2, 2]];
const BANDS = [['bandTop', 'Band oben', 0], ['bandMid', 'Band Mitte', 1], ['bandBot', 'Band unten', 2]];
const MARGIN = 4;
const SLIDERS = [
  ['vizStr', 'Stärke (Ausschlag)', 20, 200, 5, v => v + ' %', 'Wie hoch Balken und Wellen ausschlagen – für leise Songs höher.'],
  ['vizAlpha', 'Deckkraft', 10, 100, 5, v => v + ' %', 'Weniger = durchsichtiger, dein Bild scheint durch.'],
  ['vizGlow', 'Leuchten', 0, 100, 5, v => v + ' %', 'Neon-Schein um den Visualizer.'],
  ['vizDens', 'Dichte', 8, 128, 4, v => v + ' Balken', 'Wie viele Balken, Striche oder LEDs nebeneinander.'],
  ['vizSmooth', 'Ruhe', 0, 100, 5, v => v + ' %', 'Hoch = ruhige, weiche Bewegung · niedrig = zappelig.'],
  ['vizLine', 'Linienstärke', 1, 10, 0.5, v => String(v).replace('.', ',') + ' px', 'Dicke der Linien bei Wellen-Stilen (bei 1080p).']
];
const TOGGLES = [['vizCenter', 'Aus der Mitte', 'Balken wachsen nach oben und unten'], ['vizFloor', 'Bodenspiegelung', 'Gespiegeltes Abbild darunter (wie Glas)'],
  ['vizSoft', 'Weiche Ränder', 'Links und rechts sanft ausblenden'], ['snap', 'Magnetisch einrasten', 'Beim Ziehen an den Plätzen einrasten']];
let SNAP = localStorage.getItem('fes-snap') !== '0';

function dockPos(id, w, h) {
  const b = BANDS.find(x => x[0] === id);
  if (b) return { x: 0, y: b[2] === 0 ? 0 : b[2] === 1 ? (100 - h) / 2 : 100 - h, w: 100 };
  const d = DOCKS.find(x => x[0] === id); if (!d) return null;
  return { x: d[2] === 0 ? MARGIN : d[2] === 1 ? (100 - w) / 2 : 100 - w - MARGIN, y: d[3] === 0 ? MARGIN : d[3] === 1 ? (100 - h) / 2 : 100 - h - MARGIN, w };
}
const dockName = id => (DOCKS.concat(BANDS).find(x => x[0] === id) || [, ''])[1];
const r1 = v => Math.round(v * 10) / 10;
function h2r(h) { return [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16)) }
function mix(a, b, u) { const x = h2r(a), y = h2r(b); return 'rgb(' + [0, 1, 2].map(i => Math.round(x[i] + (y[i] - x[i]) * u)).join(',') + ')' }
function toHsl(hex) {
  const c = h2r(hex).map(v => v / 255), mx = Math.max(...c), mn = Math.min(...c), l = (mx + mn) / 2, d = mx - mn; let h = 0, s = 0;
  if (d) { s = l > 0.5 ? d / (2 - mx - mn) : d / (mx + mn); h = mx === c[0] ? (c[1] - c[2]) / d + (c[1] < c[2] ? 6 : 0) : mx === c[1] ? (c[2] - c[0]) / d + 2 : (c[0] - c[1]) / d + 4; h *= 60 }
  return [h, s * 100, l * 100];
}
function seeded(seed) { let s = (seed * 9301 + 49297) % 233280; return () => { s = (s * 9301 + 49297) % 233280; return s / 233280 } }
function randHues(seed) { const r = seeded(seed), b = r() * 360; return [b, b + 70 + r() * 80, b + 170 + r() * 90] }
const LIVE = { an: null, freq: null, time: null, on: false };
function level(t) { if (LIVE.on) { let m = 0; for (let i = 0; i < 64; i++) m += LIVE.freq[i]; return Math.min(1, m / 64 / 170) } return Math.max(0, Math.min(1, 0.5 + 0.5 * Math.sin(t * 2.3) * Math.sin(t * 0.71 + 1))) }
function colorAt(s, u, t) {
  const m = s.vizMode;
  if (m === 'solid') return s.vizColor;
  if (m === 'rainbow') { const k = u * (RAINBOW.length - 1), i = Math.min(RAINBOW.length - 2, Math.floor(k)); return mix(RAINBOW[i], RAINBOW[i + 1], k - i) }
  if (m === 'random') { const p = randHues(s.vizSeed), k = u * 2, i = Math.min(1, Math.floor(k)), h = p[i] + (p[i + 1] - p[i]) * (k - i) + t * 15; return `hsl(${Math.round(h % 360)},88%,60%)` }
  if (m === 'sound') {
    const a = toHsl(s.vizColor), b = toHsl(s.vizColor2), L = level(t), pitch = LIVE.on ? Math.min(1, centroid() * 2.2) : 0.5 + 0.5 * Math.sin(t * 0.9);
    const hh = a[0] + (b[0] - a[0]) * u + (pitch - 0.5) * 170;
    return `hsl(${Math.round((hh % 360 + 360) % 360)},${Math.round(Math.min(100, a[1] + 10))}%,${Math.round(46 + L * 24)}%)`;
  }
  return mix(s.vizColor, s.vizColor2, u);
}
function centroid() { let a = 0, w = 0; for (let i = 2; i < LIVE.freq.length; i++) { a += LIVE.freq[i] * i; w += LIVE.freq[i] } return w ? a / w / LIVE.freq.length : 0.3 }
function spec(n, t, s) {
  const out = [], g = s.vizStr / 100;
  if (LIVE.on) {
    const F = LIVE.freq, N = F.length;
    for (let i = 0; i < n; i++) { const a = Math.floor(Math.pow(N, i / n) - 1), b = Math.max(a + 1, Math.floor(Math.pow(N, (i + 1) / n) - 1)); let m = 0; for (let k = a; k < b && k < N; k++) m = Math.max(m, F[k]); out.push(Math.max(0.03, Math.min(1, Math.pow(m / 255, 1.4) * 1.25 * g))) }
    return out;
  }
  const jit = (1 - s.vizSmooth / 100) * 0.35;
  for (let i = 0; i < n; i++) {
    const u = i / Math.max(1, n - 1), env = 0.85 * Math.exp(-u * 1.5) + 0.22, w = 0.5 + 0.5 * Math.sin(t * 3.1 + i * 0.7) * Math.cos(t * 1.7 + i * 0.31);
    out.push(Math.max(0.03, Math.min(1, (env * (0.35 + 0.65 * w) + jit * Math.sin(t * 13 + i * 2.3) * env) * g)));
  }
  return out;
}
function wav(n, t, s, ph) {
  const out = [], g = s.vizStr / 100;
  if (LIVE.on) { const T = LIVE.time, N = T.length, off = Math.floor((ph || 0) * 40); for (let i = 0; i < n; i++) out.push(Math.max(-1, Math.min(1, (T[(Math.floor(i / n * N) + off) % N] - 128) / 128 * 1.6 * g))); return out }
  const jit = (1 - s.vizSmooth / 100) * 0.3;
  for (let i = 0; i < n; i++) {
    const u = i / Math.max(1, n - 1), env = Math.sin(u * Math.PI) * 0.9 + 0.1;
    out.push(Math.max(-1, Math.min(1, (0.55 * Math.sin(i * 0.19 + t * 4 + (ph || 0)) * Math.sin(i * 0.043 + t * 0.8) + 0.3 * Math.sin(i * 0.61 - t * 6) + jit * Math.sin(i * 1.7 + t * 11)) * env * g)));
  }
  return out;
}
/* liefert SVG-Inhalt für einen Stil (Skizze – das echte Bild rechnet FFmpeg) */
function vizSvg(id, W, H, t, s, mini, gid) {
  const out = [], dens = mini ? 22 : s.vizDens, sw = mini ? 1.6 : s.vizLine * Math.max(0.6, H / 120), grad = `url(#${gid})`;
  const bar = (x, y, w, h, u, o = 1) => out.push(`<rect x="${r1(x)}" y="${r1(y)}" width="${r1(Math.max(0.5, w))}" height="${r1(Math.max(0.5, h))}" rx="${r1(Math.min(w / 2, 3))}" fill="${colorAt(s, u, t)}" opacity="${o}"/>`);
  const line = (pts, o = 1, w = sw, dash = 'none', fill = 'none') => out.push(`<polyline points="${pts.map(q => r1(q[0]) + ',' + r1(q[1])).join(' ')}" fill="${fill}" stroke="${grad}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="${dash}" opacity="${o}"/>`);
  const barsLike = ['bars', 'thin', 'glowbars', 'mirror', 'centerbars', 'reflect', 'cqt'];
  if (barsLike.includes(id)) {
    const n = id === 'thin' ? dens * 2 : id === 'cqt' ? Math.round(dens * 1.5) : dens, sp = spec(n, t, s), slot = W / n;
    const bw = slot * (1 - (id === 'thin' ? 0.62 : 0.28)), floor = (!mini && s.vizFloor) || id === 'reflect', center = (!mini && s.vizCenter) || id === 'centerbars', topH = floor ? H * 0.7 : H;
    for (let i = 0; i < n; i++) {
      const k = id === 'mirror' ? Math.abs(i - (n - 1) / 2) * 2 / (n - 1) : i / (n - 1), v = sp[Math.min(n - 1, Math.round(k * (n - 1)))], u = i / (n - 1), x = i * slot + (slot - bw) / 2, h = v * topH;
      if (center) bar(x, (topH - h) / 2, bw, h, u); else bar(x, topH - h, bw, h, u);
      if (floor) bar(x, topH + 2, bw, v * (H - topH - 2), u, 0.28);
    }
  } else if (id === 'led' || id === 'leddots') {
    const cols = Math.max(12, Math.round(dens * 0.8)), rows = mini ? 6 : 12, sp = spec(cols, t, s), cw = W / cols, ch = H / rows;
    for (let c = 0; c < cols; c++) for (let r = 0; r < rows; r++) {
      const lit = (rows - r) <= Math.round(sp[c] * rows), f = colorAt(s, c / (cols - 1), t);
      out.push(id === 'leddots' ? `<circle cx="${r1(c * cw + cw / 2)}" cy="${r1(r * ch + ch / 2)}" r="${r1(Math.min(cw, ch) * 0.36)}" fill="${f}" opacity="${lit ? 1 : 0.07}"/>`
        : `<rect x="${r1(c * cw + cw * 0.12)}" y="${r1(r * ch + ch * 0.14)}" width="${r1(cw * 0.76)}" height="${r1(ch * 0.7)}" rx="1" fill="${f}" opacity="${lit ? 1 : 0.07}"/>`);
    }
  } else if (id === 'vu') {
    const lv = [level(t), level(t + 0.4)].map(v => v * s.vizStr / 100), seg = mini ? 14 : 32, sg = W / seg;
    for (let c = 0; c < 2; c++) for (let q = 0; q < seg; q++) out.push(`<rect x="${r1(q * sg + 1)}" y="${r1(c * H / 2 + H * 0.08)}" width="${r1(sg - 2)}" height="${r1(H * 0.34)}" rx="2" fill="${colorAt(s, q / (seg - 1), t)}" opacity="${q / seg < Math.min(1, lv[c]) ? 1 : 0.08}"/>`);
  } else if (id === 'spectro') {
    const cols = mini ? 24 : 56, rows = mini ? 8 : 14, cw = W / cols, ch = H / rows;
    for (let x = 0; x < cols; x++) { const sp = spec(rows, t - (cols - x) * 0.12, s); for (let y = 0; y < rows; y++) out.push(`<rect x="${r1(x * cw)}" y="${r1(y * ch)}" width="${r1(cw + 0.4)}" height="${r1(ch + 0.4)}" fill="${colorAt(s, y / (rows - 1), t)}" opacity="${r1(Math.pow(sp[rows - 1 - y], 1.6))}"/>`) }
  } else if (id === 'scope') {
    const pts = [], cx = W / 2, cy = H / 2, rad = Math.min(W, H) * 0.46 * Math.min(1.4, s.vizStr / 100), wv = LIVE.on ? wav(220, t, s) : null;
    for (let a = 0; a <= 220; a++) { const an = a / 220 * Math.PI * 2; pts.push(wv ? [cx + wv[a % 220] * rad, cy + wv[(a + 55) % 220] * rad] : [cx + Math.sin(an * 3 + t) * rad, cy + Math.sin(an * 2 + t * 0.7) * rad * 0.9]) }
    line(pts);
  } else {
    const N = mini ? 60 : 160, wv = wav(N, t, s), step = W / (N - 1), mid = H / 2;
    if (id === 'wave') { const top = [], bot = []; for (let j = 0; j < N; j++) { top.push([j * step, mid - Math.abs(wv[j]) * mid]); bot.unshift([j * step, mid + Math.abs(wv[j]) * mid]) } line(top.concat(bot), 1, 0.5, 'none', grad) }
    else if (['line', 'neon', 'dots'].includes(id)) {
      const p = []; for (let j = 0; j < N; j++) p.push([j * step, mid - wv[j] * mid * 0.9]);
      if (id === 'neon') { line(p, 0.35, sw * 3.2); line(p, 1, sw * 1.2) } else if (id === 'dots') line(p, 1, sw * 1.5, '0 ' + r1(sw * 3.2)); else line(p);
    } else if (id === 'strokes') {
      const n = Math.round(dens * 1.4), sl = W / n, w3 = wav(n, t, s);
      for (let j = 0; j < n; j++) { const hh = Math.max(2, Math.abs(w3[j]) * H); bar(j * sl + sl * 0.3, mid - hh / 2, sl * 0.4, hh, j / (n - 1), 0.5 + 0.5 * Math.abs(w3[j])) }
    } else if (id === 'bundle') {
      for (let b = 0; b < 5; b++) { const wb = wav(N, t, s, b * 0.5), p = []; for (let j = 0; j < N; j++) p.push([j * step, mid - wb[j] * mid * (0.95 - b * 0.13)]); line(p, 1 - b * 0.16, Math.max(0.8, sw * 0.6)) }
    } else if (id === 'specline') {
      const sp = spec(64, t, s), p = [[0, H]]; for (let j = 0; j < 64; j++) p.push([j / 63 * W, H - sp[j] * H * 0.95]); p.push([W, H]);
      line(p, 0.25, 0.5, 'none', grad); line(p.slice(1, -1));
    } else if (id === 'combo') {
      const n = dens, sp = spec(n, t, s), sl = W / n, tH = H * 0.66;
      for (let j = 0; j < n; j++) { const k = Math.abs(j - (n - 1) / 2) * 2 / (n - 1), v = sp[Math.round(k * (n - 1))] * tH; bar(j * sl + sl * 0.15, tH - v, sl * 0.7, v, j / (n - 1)) }
      const p = []; for (let j = 0; j < N; j++) p.push([j * step, tH + (H - tH) / 2 - wv[j] * (H - tH) * 0.45]); line(p, 1, Math.max(1, sw * 0.8));
    }
  }
  const stops = [0, 0.25, 0.5, 0.75, 1].map(u => `<stop offset="${u * 100}%" stop-color="${colorAt(s, u, t)}"/>`).join('');
  return `<defs><linearGradient id="${gid}" x1="0" y1="0" x2="1" y2="0">${stops}</linearGradient></defs>` + out.join('');
}

let VT = 0, lastFrame = 0, tilesKey = '';
function vizFrame(ts) {
  requestAnimationFrame(vizFrame);
  if (!S.settings || (!S.settings.viz && S.settings.fx === 'none') || document.hidden || ts - lastFrame < 70) return;
  lastFrame = ts; VT += 0.08;
  if (LIVE.an && !aud.paused) { LIVE.an.getByteFrequencyData(LIVE.freq); LIVE.an.getByteTimeDomainData(LIVE.time); LIVE.on = true } else LIVE.on = false;
  if (!S.settings.viz) return;
  if (S.settings.vizShape === 'path' || MK.mode === 'line' || MK.mode === 'ring') drawMarkSvg(); else drawVizBox();
}
requestAnimationFrame(vizFrame);
function drawVizBox() {
  const s = S.settings, box = $('#vizBox'), r = box.getBoundingClientRect();
  const W = Math.max(20, Math.round(r.width)), H = Math.max(10, Math.round(r.height)), svg = $('#vizSvg');
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  const st = effStyle(s);
  svg.innerHTML = vizSvg(st, W, H, VT, s, false, 'vgMain');
  const glow = st === 'neon' || st === 'glowbars' ? Math.max(s.vizGlow, 65) : s.vizGlow;
  svg.style.opacity = s.vizAlpha / 100;
  svg.style.filter = glow > 0 ? `drop-shadow(0 0 ${Math.round(glow / 8)}px ${colorAt(s, 0.3, VT)}) drop-shadow(0 0 ${Math.round(glow / 4)}px ${colorAt(s, 0.7, VT)})` : 'none';
  let m = s.vizSoft ? 'linear-gradient(90deg,transparent 0%,#000 12%,#000 88%,transparent 100%)' : 'none', ms = '', mp = '';
  if (s.vizShape === 'mask' && MURL.viz) {
    m = `url(${MURL.viz})`; ms = `${(100 / s.vizW * 100).toFixed(2)}% ${(100 / s.vizH * 100).toFixed(2)}%`;
    mp = `${s.vizW >= 99.9 ? 0 : (s.vizX / (100 - s.vizW) * 100).toFixed(2)}% ${s.vizH >= 99.9 ? 0 : (s.vizY / (100 - s.vizH) * 100).toFixed(2)}%`;
  }
  svg.style.webkitMaskImage = m; svg.style.maskImage = m;
  svg.style.webkitMaskSize = svg.style.maskSize = ms; svg.style.webkitMaskPosition = svg.style.maskPosition = mp;
  svg.style.webkitMaskRepeat = svg.style.maskRepeat = 'no-repeat';
}
function placeVizBox() {
  const s = S.settings, box = $('#vizBox');
  box.hidden = !s.viz || s.vizShape === 'path'; $('#vizHint').hidden = !s.viz || MK.mode !== 'box';
  box.classList.toggle('locked', s.vizShape === 'mask');
  box.style.left = s.vizX + '%'; box.style.top = s.vizY + '%'; box.style.width = s.vizW + '%'; box.style.height = s.vizH + '%';
  box.classList.toggle('low', s.vizY < 8);
  const st = VSTYLES.find(x => x[0] === effStyle(s)) || VSTYLES[0];
  $('#vbLabel').textContent = (s.vizAi ? '✨ KI-Welle: ' : '') + st[1] + (s.vizDock ? ' · ' + dockName(s.vizDock) : ' · frei');
  $('#dockStatus').textContent = s.vizDock ? 'Angedockt: ' + dockName(s.vizDock) : 'Frei platziert';
  if (s.viz && s.vizShape !== 'path') drawVizBox();
}
function renderViz(force) {
  if (!S.settings) return;
  const s = S.settings;
  $('#vizSwitch').setAttribute('aria-checked', String(s.viz));
  $('#vizCard').classList.toggle('off', !s.viz);
  placeVizBox();
  const key = [s.vizMode, s.vizColor, s.vizColor2, s.vizSeed, S.theme].join('|');
  if (force || key !== tilesKey || !$('#vizTiles').childElementCount) {
    tilesKey = key; const box = $('#vizTiles'); box.textContent = '';
    const ms = Object.assign({}, s, { vizStr: 100, vizSmooth: 60, vizCenter: false, vizFloor: false });
    VSTYLES.forEach(([id, name, short], i) => box.append(el('button', { type: 'button', class: 'vtile', 'data-id': id, title: name, 'aria-label': name, onclick: () => { if (S.settings.vizAi) { S.settings.vizAi = false; toast('Stil von Hand gewählt – die KI-Welle ist aus') } set('vizStyle', id) } },
      el('div', { class: 'vt-art', 'aria-hidden': 'true', html: `<svg viewBox="0 0 96 44">${vizSvg(id, 96, 44, 1.4, ms, true, 'vgT' + i)}</svg>` }), el('span', {}, short))));
  }
  $$('.vtile').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.id === s.vizStyle && !s.vizAi)));
  $('#vizAiNote').hidden = !s.vizAi;
  $('#vizAiNote').textContent = `✨ Die KI hat markiert – dargestellt als Welle „${(AI_WAVES.find(w => w[0] === s.vizAiWave) || AI_WAVES[0])[1]}“ (änderbar oben im Menü „Markieren → ✨ KI“). Ein Stil hier wählen = wieder von Hand.`;
  const mb = $('#vizModes'); mb.textContent = '';
  const hs = randHues(s.vizSeed).map(h => `hsl(${Math.round(h % 360)},88%,60%)`);
  const sw = { solid: s.vizColor, gradient: `linear-gradient(90deg,${s.vizColor},${s.vizColor2})`, rainbow: `linear-gradient(90deg,${RAINBOW.join(',')})`, random: `linear-gradient(90deg,${hs.join(',')})`, sound: 'linear-gradient(90deg,#ff7a45,#ffd34d,#3ddc84,#38bdf8)' };
  VMODES.forEach(([id, n]) => mb.append(el('button', { type: 'button', class: 'mode', 'aria-pressed': String(s.vizMode === id), onclick: () => set('vizMode', id) }, el('i', { style: 'background:' + sw[id] }), n)));
  $('#vizC1').value = s.vizColor; $('#vizC2').value = s.vizColor2;
  $('#vizColorRow').hidden = !['solid', 'gradient', 'sound'].includes(s.vizMode) && s.vizMode !== 'random';
  $('#vizC1').parentElement.hidden = s.vizMode === 'random' || s.vizMode === 'rainbow';
  $('#vizC2Wrap').hidden = !['gradient', 'sound'].includes(s.vizMode);
  $('#vizDesign').hidden = !['solid', 'gradient', 'sound'].includes(s.vizMode);
  $('#vizReroll').hidden = s.vizMode !== 'random';
  $('#vizModeHint').textContent = VHINT[s.vizMode];
  const dg = $('#dockGrid'); dg.textContent = '';
  DOCKS.forEach(q => dg.append(el('button', { type: 'button', 'aria-label': q[1], title: q[1], 'aria-pressed': String(s.vizDock === q[0]), onclick: () => goDock(q[0]) },
    el('i', { style: (q[2] === 0 ? 'left:4px' : q[2] === 1 ? 'left:calc(50% - 8px)' : 'right:4px') + ';' + (q[3] === 0 ? 'top:4px' : q[3] === 1 ? 'top:11px' : 'bottom:4px') }))));
  const bl = $('#bandList'); bl.textContent = '';
  BANDS.forEach(q => bl.append(el('button', { type: 'button', 'aria-pressed': String(s.vizDock === q[0]), onclick: () => goDock(q[0]) }, q[1] + ' – ganze Breite')));
  renderSliders($('#quickSliders'), SLIDERS.slice(0, 3), false);
  if ($('#vizDlg').open) renderWorkshop();
  renderMark();
}
function renderSliders(box, list, hints) {
  if (box.contains(document.activeElement) && document.activeElement.type === 'range') { list.forEach(([k, , , , , f]) => { const b = box.querySelector(`[data-k="${k}"]`); if (b) b.textContent = f(S.settings[k]) }); return }
  box.textContent = '';
  for (const [k, label, min, max, step, f, hint] of list) {
    const id = (hints ? 'ws-' : 'q-') + k, inp = el('input', { type: 'range', id, min, max, step, value: S.settings[k] });
    inp.oninput = () => { S.settings[k] = +inp.value; box.querySelector(`[data-k="${k}"]`).textContent = f(+inp.value); placeVizBox(); saveSettings(); refreshCommand(); if (hints) renderSliders($('#quickSliders'), SLIDERS.slice(0, 3), false); else if ($('#vizDlg').open) renderWorkshop() };
    box.append(el('div', { class: 'sl' }, el('div', { class: 'sl-top' }, el('label', { for: id }, label), el('b', { 'data-k': k }, f(S.settings[k]))), inp, hints ? el('small', {}, hint) : null));
  }
}
function renderWorkshop() {
  renderSliders($('#allSliders'), SLIDERS, true);
  const tb = $('#vizToggles'); tb.textContent = '';
  for (const [k, label, hint] of TOGGLES) {
    const on = k === 'snap' ? SNAP : !!S.settings[k];
    tb.append(el('button', { type: 'button', class: 'tg', role: 'switch', 'aria-checked': String(on), onclick: () => { if (k === 'snap') { SNAP = !SNAP; localStorage.setItem('fes-snap', SNAP ? '1' : '0'); renderWorkshop() } else set(k, !S.settings[k]) } },
      el('span', {}, el('b', {}, label), el('small', {}, hint)), el('span', { class: 'switch', 'aria-checked': String(on) }, el('i'))));
  }
  const s = S.settings;
  [['#posX', 'vizX'], ['#posY', 'vizY'], ['#posW', 'vizW'], ['#posH', 'vizH']].forEach(([sel, k]) => { if (document.activeElement !== $(sel)) $(sel).value = r1(s[k]) });
}
[['#posX', 'vizX', 0, 95], ['#posY', 'vizY', 0, 97], ['#posW', 'vizW', 5, 100], ['#posH', 'vizH', 3, 100]].forEach(([sel, k, lo, hi]) => {
  $(sel).addEventListener('change', e => { const v = Math.min(hi, Math.max(lo, parseFloat(String(e.target.value).replace(',', '.')) || 0)); S.settings[k] = v; S.settings.vizDock = ''; fitBox(); changed('viz') });
});
function fitBox() { const s = S.settings; s.vizW = Math.min(s.vizW, 100 - s.vizX); s.vizH = Math.min(s.vizH, 100 - s.vizY); if (s.vizX + s.vizW > 100) s.vizX = 100 - s.vizW; if (s.vizY + s.vizH > 100) s.vizY = 100 - s.vizH }
function goDock(id, ai) {
  const s = S.settings; s.vizAi = !!ai;
  if (id.startsWith('band')) { const p = dockPos(id, 100, s.vizH); Object.assign(s, { vizDock: id, vizX: 0, vizY: p.y, vizW: 100 }) }
  else { const w = s.vizW > 92 ? 80 : s.vizW, p = dockPos(id, w, s.vizH); Object.assign(s, { vizDock: id, vizX: p.x, vizY: p.y, vizW: w }) }
  changed('viz');
}
$('#vizSwitch').onclick = () => set('viz', !S.settings.viz);
$('#vizC1').oninput = e => { S.settings.vizColor = e.target.value; renderViz(); saveSettings(); refreshCommand() };
$('#vizC2').oninput = e => { S.settings.vizColor2 = e.target.value; renderViz(); saveSettings(); refreshCommand() };
$('#vizDesign').onclick = () => { const [a, b] = themeColors(); S.settings.vizColor = a; S.settings.vizColor2 = b; changed('viz') };
$('#vizReroll').onclick = () => { S.settings.vizSeed = (S.settings.vizSeed + 1 + Math.floor(Math.random() * 997)) % 999999; changed('viz') };
$('#vizWorkshop').onclick = () => { renderWorkshop(); $('#vizDlg').showModal() };

/* Ziehen, Skalieren, Einrasten im Vorschaubild */
let DRAG = null;
$('#vizBox').addEventListener('pointerdown', e => {
  if (e.button !== 0 || S.settings.vizShape === 'mask') return; e.preventDefault();
  const fr = $('#frame').getBoundingClientRect(), s = S.settings, h = e.target.dataset && e.target.dataset.h;
  DRAG = { mode: h || 'move', px: e.clientX, py: e.clientY, x: s.vizX, y: s.vizY, w: s.vizW, h: s.vizH, fw: fr.width, fh: fr.height, dock: s.vizDock };
  $('#vizBox').setPointerCapture(e.pointerId);
  if (DRAG.mode === 'move') showMarks(true);
});
$('#vizBox').addEventListener('pointermove', e => {
  if (!DRAG) return;
  const d = DRAG, s = S.settings, cl = (v, a, b) => Math.max(a, Math.min(b, v));
  const dx = (e.clientX - d.px) / d.fw * 100, dy = (e.clientY - d.py) / d.fh * 100;
  if (d.mode === 'move') {
    let x = cl(d.x + dx, 0, 100 - d.w), y = cl(d.y + dy, 0, 100 - d.h), dock = '';
    if (SNAP) {
      let best = 6; const ids = DOCKS.map(q => q[0]).concat(d.w > 97 ? BANDS.map(q => q[0]) : []);
      for (const id of ids) { const p = dockPos(id, d.w, d.h), dist = Math.hypot(p.x - x, p.y - y); if (dist < best) { best = dist; dock = id } }
      if (dock) { const p = dockPos(dock, d.w, d.h); x = p.x; y = p.y }
    }
    Object.assign(s, { vizX: x, vizY: y, vizDock: dock });
  } else {
    let { x, y, w, h } = d;
    if (d.mode.includes('e')) w = cl(d.w + dx, 5, 100 - d.x);
    if (d.mode.includes('s')) h = cl(d.h + dy, 3, 100 - d.y);
    if (d.mode.includes('w')) { w = cl(d.w - dx, 5, d.x + d.w); x = d.x + d.w - w }
    if (d.mode.includes('n')) { h = cl(d.h - dy, 3, d.y + d.h); y = d.y + d.h - h }
    if (d.dock) { if (d.dock.startsWith('band')) w = 100; const p = dockPos(d.dock, w, h); x = p.x; y = p.y }
    Object.assign(s, { vizX: x, vizY: y, vizW: w, vizH: h, vizDock: d.dock });
  }
  placeVizBox(); showMarks(d.mode === 'move');
});
const endDrag = () => { if (!DRAG) return; DRAG = null; S.settings.vizAi = false; showMarks(false); changed('viz') };
$('#vizBox').addEventListener('pointerup', endDrag);
$('#vizBox').addEventListener('pointercancel', endDrag);
function showMarks(on) {
  const s = S.settings, mk = $('#dockMarks'), gh = $('#dockGhost');
  mk.hidden = !on; gh.hidden = !on || !s.vizDock;
  if (!on) return;
  mk.textContent = '';
  DOCKS.forEach(q => { const p = dockPos(q[0], s.vizW, s.vizH); mk.append(el('i', { class: s.vizDock === q[0] ? 'on' : '', style: `left:${p.x + s.vizW / 2}%;top:${p.y + s.vizH / 2}%` })) });
  if (s.vizDock) { const p = dockPos(s.vizDock, s.vizW, s.vizH); Object.assign(gh.style, { left: p.x + '%', top: p.y + '%', width: (s.vizDock.startsWith('band') ? 100 : s.vizW) + '%', height: s.vizH + '%' }) }
}

/* Vorschau mit Ton (echter FFmpeg-Clip) */
async function previewViz() {
  if (!S.audio || !S.image) { toast('Für die Vorschau zuerst Song und Bild hineinziehen'); return }
  const my = ++clipSeq; $('#stillBusy').hidden = false; toast('Vorschau wird gerendert …');
  try {
    const d = await api('/api/viz-preview', { settings: S.settings, audio: S.audio.token, image: S.image.token });
    if (my !== clipSeq) return;
    if ($('#vizDlg').open) $('#vizDlg').close();
    aud.pause();
    const v = $('#clipVid'); v.muted = false; v.controls = true; v.src = d.url + '?t=' + Date.now(); v.hidden = false;
    v.onended = () => setTimeout(() => { v.hidden = true; v.controls = false; v.muted = true }, 600);
    v.play().catch(() => {});
  } catch (e) { toast(e.message, true) }
  finally { if (my === clipSeq) $('#stillBusy').hidden = true }
}
$('#vizPreviewBtn').onclick = previewViz;
$('#vizPreviewBtn2').onclick = previewViz;

/* echte Frequenzen beim Anhören */
function liveAudio() {
  if (LIVE.an) return;
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)(), src = ctx.createMediaElementSource(aud), an = ctx.createAnalyser();
    an.fftSize = 2048; an.smoothingTimeConstant = 0.72; src.connect(an); an.connect(ctx.destination);
    LIVE.an = an; LIVE.freq = new Uint8Array(an.frequencyBinCount); LIVE.time = new Uint8Array(an.fftSize); LIVE.ctx = ctx;
  } catch (_) { LIVE.an = null }
}

/* ---------- Vorlagen & Projekte ---------- */
function presetSwatch(st) {
  if (!st) return 'var(--a)';
  if (st.vizMode === 'rainbow') return `conic-gradient(${RAINBOW.join(',')},${RAINBOW[0]})`;
  if (st.vizMode === 'sound') return 'conic-gradient(#ff7a45,#ffd34d,#3ddc84,#38bdf8,#ff7a45)';
  if (st.vizMode === 'random') return `conic-gradient(${randHues(st.vizSeed).map(h => `hsl(${Math.round(h % 360)},88%,60%)`).join(',')})`;
  return `linear-gradient(135deg,${st.vizColor || '#f5b544'},${(st.vizMode === 'solid' ? st.vizColor : st.vizColor2) || '#ffdf8a'})`;
}
function presetSub(st) { const f = fmtOf(st.fmt); return f[1].replace('YouTube ', '') + (st.viz ? ' · ' + (VSTYLES.find(x => x[0] === st.vizStyle) || VSTYLES[0])[2] : '') }
function renderPresets() {
  const box = $('#presetChips'); box.textContent = '';
  const list = S.presets || [];
  if (!list.length) { box.append(el('span', { class: 'pb-empty' }, 'Noch keine Vorlagen – stell alles ein und klick auf „Speichern …“.')); return }
  list.slice(-8).reverse().forEach(p => box.append(el('button', { type: 'button', class: 'pchip', title: 'Laden: ' + p.name, onclick: () => applyPreset(p) },
    el('i', { style: 'background:' + presetSwatch(p.settings) }), p.name, el('small', {}, presetSub(p.settings)))));
}
function applyPreset(p) {
  const keep = {}; ['vizShape', 'vizMask', 'vizPath', 'vizClosed', 'vizBoth', 'vizThick', 'vizFeather', 'start', 'end',
    'fxArea', 'fxMask', 'fxPath', 'fxClosed', 'fxThick', 'fxFeather', 'fxX', 'fxY', 'fxW', 'fxH'].forEach(k => keep[k] = S.settings[k]);
  S.settings = Object.assign({}, S.settings, p.settings, keep);
  changed('fmt'); renderViz(true); toast('✓ Vorlage geladen: ' + p.name);
}
let saveKind = 'settings';
function renderSaveKind() {
  $$('#saveKind button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.v === saveKind)));
  $('#saveHint').textContent = saveKind === 'settings'
    ? 'Vorlage = alle Einstellungen (Format, Bild-Anpassung, Visualizer mit Platz, Farbe und Reglern, Übergänge, FPS, Encoder) – für jeden neuen Song wiederverwendbar.'
    : 'Projekt = Einstellungen + Song + Bild in einer .fesproj-Datei (Ordner „Projekte“ bei deinen Videos) – zum späteren Weiterarbeiten oder Neu-Rendern.';
}
$$('#saveKind button').forEach(b => b.onclick = () => { saveKind = b.dataset.v; renderSaveKind() });
$('#saveBtn').onclick = () => {
  saveKind = 'settings'; renderSaveKind();
  $('#saveName').value = S.audio ? S.audio.name.replace(/\.[^.]+$/, '') : '';
  $('#saveDlg').showModal(); $('#saveName').focus();
};
$('#saveGo').onclick = async () => {
  const name = $('#saveName').value.trim();
  if (!name) { toast('Bitte einen Namen eingeben', true); return }
  try {
    if (saveKind === 'settings') {
      if ((S.presets || []).some(p => p.name === name) && !await ask('Vorlage ersetzen?', `„${name}“ gibt es schon. Soll sie überschrieben werden?`, 'Ersetzen')) return;
      const d = await api('/api/presets/save', { name, settings: S.settings }); S.presets = d.presets; renderPresets(); toast('✓ Vorlage gespeichert: ' + name);
    } else {
      if (!S.audio || !S.image) { toast('Für ein Projekt müssen Song und Bild geladen sein', true); return }
      const d = await api('/api/project/save', { name, settings: S.settings, audio: S.audio.token, image: S.image.token }); toast('✓ Projekt gespeichert: ' + d.path);
    }
    $('#saveDlg').close();
  } catch (e) { toast(e.message, true) }
};
$('#saveName').addEventListener('keydown', e => { if (e.key === 'Enter') $('#saveGo').click() });
async function openLoad() {
  const pb = $('#loadPresets'); pb.textContent = '';
  const list = S.presets || [];
  if (!list.length) pb.append(el('div', { class: 'empty' }, 'Noch keine Vorlagen gespeichert.'));
  list.slice().reverse().forEach(p => pb.append(el('div', { class: 'li' }, el('i', { style: 'background:' + presetSwatch(p.settings) }),
    el('div', {}, el('b', {}, p.name), el('small', {}, presetSub(p.settings))),
    el('div', { class: 'acts' }, el('button', { type: 'button', class: 'btn small', onclick: () => { applyPreset(p); $('#loadDlg').close() } }, 'Laden'),
      el('button', { type: 'button', class: 'x', 'aria-label': 'Vorlage löschen: ' + p.name, html: ICON.x, onclick: async () => { if (await ask('Vorlage löschen?', `„${p.name}“ wird gelöscht.`, 'Löschen')) { const d = await api('/api/presets/delete', { name: p.name }); S.presets = d.presets; renderPresets(); openLoad() } } })))));
  const jb = $('#loadProjects'); jb.textContent = 'Wird geladen …';
  try {
    const d = await api('/api/projects'); jb.textContent = ''; S.projDir = d.folder;
    if (!d.projects.length) jb.append(el('div', { class: 'empty' }, 'Noch keine Projekte gespeichert.'));
    d.projects.forEach(p => jb.append(el('div', { class: 'li' }, el('i', { style: 'background:linear-gradient(135deg,var(--a),var(--b))' }),
      el('div', {}, el('b', { title: p.path }, p.name), el('small', {}, new Date(p.mtime * 1000).toLocaleString('de-DE', { dateStyle: 'short', timeStyle: 'short' }) + ' · ' + size(p.size))),
      el('div', { class: 'acts' }, el('button', { type: 'button', class: 'btn small', onclick: () => loadProject(api('/api/project/load', { path: p.path })) }, 'Laden'),
        el('button', { type: 'button', class: 'x', 'aria-label': 'Projekt löschen: ' + p.name, html: ICON.x, onclick: async () => { if (await ask('Projekt löschen?', `„${p.name}“ wird von der Festplatte gelöscht.`, 'Löschen')) { await api('/api/project/delete', { path: p.path }); openLoad() } } })))));
  } catch (e) { jb.textContent = e.message }
  if (!$('#loadDlg').open) $('#loadDlg').showModal();
}
async function loadProject(promise) {
  try {
    const d = await promise;
    for (const k of ['audio', 'image']) { const old = S[k]; if (old && old.token !== d[k].token) api('/api/unstage', { token: old.token }).catch(() => {}) }
    S.settings = Object.assign({}, S.settings, d.settings);
    MK.mode = modeFromSettings(); await loadMaskFromServer(S.settings.vizShape === 'mask' ? S.settings.vizMask : '', 'viz');
    await loadMaskFromServer(S.settings.fxArea === 'mask' ? S.settings.fxMask : '', 'fx');
    await loadMaskFromServer(S.settings.aiArea === 'mask' ? S.settings.aiMask : '', 'ai');
    adopt(d.audio, true); adopt(d.image, true);
    changed('fmt'); renderViz(true);
    if ($('#loadDlg').open) $('#loadDlg').close();
    toast('✓ Projekt geladen: ' + d.name);
  } catch (e) { toast(e.message, true) }
}
function openProjectFile(file) {
  toast('Projekt wird geöffnet …');
  loadProject(fetch('/api/project/open', { method: 'POST', headers: { 'X-Studio': TOKEN }, body: file }).then(async r => { const d = await r.json(); if (!r.ok) throw new Error(d.error || 'Fehler'); return d }));
}
$('#loadBtn').onclick = openLoad;
$('#openProjFile').onclick = () => $('#projInput').click();
$('#projInput').onchange = e => { if (e.target.files[0]) openProjectFile(e.target.files[0]); e.target.value = '' };
$('#showProjDir').onclick = () => api('/api/show', { path: S.projDir || S.outdir }).catch(e => toast(e.message, true));


/* ---------- Markieren: Fläche malen, Linie, Ring (+ KI) ---------- */
const MK = { tab: 'hand', target: 'viz', mode: 'box', tool: 'brush', size: 36, aiPts: [], aiBase: null, ringAi: false, drawing: false, last: null, start: null, line: [], busy: '', drag: -1, sugTimer: 0 };
const MASKC = { viz: document.createElement('canvas'), fx: document.createElement('canvas'), ai: document.createElement('canvas') };
const MURL = { viz: '', fx: '', ai: '' };
const mc = () => MASKC[MK.target];
/* Markieren gilt für den Visualizer ODER die Bild-Effekte: M.Path = vizPath bzw. fxPath usw. */
const P = k => (MK.target === 'viz' ? 'viz' : MK.target) + k;      // vizX / fxX / aiX
const M = new Proxy({}, { get: (_, k) => S.settings[P(k)], set: (_, k, v) => { S.settings[P(k)] = v; return true } });
function shp(t = MK.target) { const s = S.settings; if (t !== 'viz') return s[t + 'Area'] === 'full' ? 'box' : s[t + 'Area']; return s.vizShape }
function setShp(v) { if (MK.target !== 'viz') S.settings[MK.target + 'Area'] = v === 'box' ? 'full' : v; else { S.settings.vizShape = v; if (v !== 'box') S.settings.vizDock = '' } }
const fxOn = () => S.settings.fx && S.settings.fx !== 'none';
const aiOn = () => !!S.settings.ai;
function markOn() { return MK.target === 'fx' ? fxOn() : MK.target === 'ai' ? aiOn() : S.settings.viz }
function markTargets() { const s = S.settings; return ['viz', 'fx', 'ai'].filter(t => t === 'viz' ? s.viz : t === 'fx' ? fxOn() : aiOn()) }
function setAi(v) { if (MK.target === 'viz') S.settings.vizAi = !!v }
const tName = () => MK.target === 'fx' ? 'der Effekt' : MK.target === 'ai' ? 'die KI-Bewegung' : 'der Visualizer';
const isTall = () => fmtOf(S.settings.fmt)[3];
function maskSize() { return isTall() ? [540, 960] : [960, 540] }
function ensureMask() {
  const [w, h] = maskSize();
  for (const maskC of Object.values(MASKC)) if (maskC.width !== w || maskC.height !== h) {
    const old = maskC.width ? (() => { const c = document.createElement('canvas'); c.width = maskC.width; c.height = maskC.height; c.getContext('2d').drawImage(maskC, 0, 0); return c })() : null;
    maskC.width = w; maskC.height = h;
    if (old) maskC.getContext('2d').drawImage(old, 0, 0, w, h);
  }
  const v = $('#markCanvas'); if (v.width !== w || v.height !== h) { v.width = w; v.height = h }
}
function modeFromSettings() { const sh = shp(); return sh === 'mask' ? 'mask' : sh === 'path' ? (M.Closed ? 'ring' : 'line') : 'box' }
function frameSize() { const r = $('#frame').getBoundingClientRect(); return [r.width || 1, r.height || 1] }
function busy(text) { MK.busy = text || ''; renderMarkTools(); renderAiRow() }

function renderMark() {
  if (!S.settings) return;
  const s = S.settings;
  const tg = markTargets();
  if (tg.length && !tg.includes(MK.target)) { MK.target = tg[0]; MK.mode = modeFromSettings() }
  if (MK.target === 'ai' && (MK.mode === 'line' || MK.mode === 'ring')) MK.mode = modeFromSettings();
  const on = markOn();
  $('#markBar').hidden = !tg.length;
  $('#mkTarget').hidden = tg.length < 2;
  $$('#mkTarget button').forEach(b => { b.hidden = !tg.includes(b.dataset.t); b.setAttribute('aria-pressed', String(b.dataset.t === MK.target)) });
  $('#mkModes [data-m="box"]').textContent = MK.target === 'viz' ? 'Kasten' : 'Ganzes Bild';
  $$('#mkModes [data-m="line"],#mkModes [data-m="ring"]').forEach(b => { b.hidden = MK.target === 'ai' });
  $('#mkModes').setAttribute('aria-label', MK.target === 'fx' ? 'Wo soll der Effekt wirken?' : MK.target === 'ai' ? 'Wo soll sich das Bild bewegen?' : 'Wo soll der Visualizer entstehen?');
  ensureMask();
  if (MK.tab === 'hand' && MK.tool === 'ai') MK.tool = 'brush';
  if (MK.tab === 'ai' && MK.mode === 'mask') MK.tool = 'ai';
  $$('#mkTabs button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.tab === MK.tab)));
  $('#mkHandRow').hidden = MK.tab !== 'hand'; $('#mkAiRow').hidden = MK.tab !== 'ai';
  $$('#mkModes button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.m === MK.mode)));
  renderAiRow(); markSummary();
  const fr = $('#frame');
  fr.classList.toggle('mk-line', on && MK.mode === 'line'); fr.classList.toggle('mk-ring', on && MK.mode === 'ring');
  $('#markCanvas').hidden = !(on && MK.mode === 'mask');
  renderMaskOverlay(); renderMarkTools(); drawMarkSvg(); markHint();
}
function markHint() {
  const s = S.settings, h = $('#mkHint');
  const t = {
    box: 'Kasten: im Bild ziehen und an den Ecken skalieren. Ruhige Stellen findet die KI unter „✨ KI → Platzvorschlag“.',
    mask: MK.tool === 'ai' ? '✨ KI-Auswahl: auf das Motiv klicken = dazunehmen · Umschalt- oder Rechtsklick = wegnehmen · mehrere Klicks verfeinern.'
      : `Fläche malen: ${tName().replace(/^d/, 'D')} erscheint nur in der markierten Fläche. Die Markierung ist im fertigen Video unsichtbar.`,
    line: MK.line.length ? 'Weiter klicken für neue Punkte · Doppelklick (oder „Fertig“) beendet die Linie.' : shp() === 'path' && !M.Closed ? 'Punkte ziehen zum Anpassen · ✨ KI verfeinern legt die Linie an die nächste Kante im Bild.'
      : MK.target === 'fx' ? 'Klicke Punkte entlang der Stelle, an der die Lichtlinien laufen sollen · Doppelklick beendet.' : 'Klicke Punkte entlang der Stelle, an der die Balken stehen sollen · Doppelklick beendet.',
    ring: MK.ringAi ? '✨ Klick jetzt auf das Motiv – die KI legt den Ring passend darum.' : 'In die Mitte klicken und den Radius aufziehen – oder ✨ „Motiv antippen“.'
  }[MK.mode];
  if (MK.tab === 'ai') {
    h.hidden = !markOn();
    h.textContent = !(S.info && S.info.ai && S.info.ai.tools) ? 'Die KI-Werkzeuge sind auf diesem PC nicht verfügbar.'
      : { mask: '✨ Klick aufs Motiv – die KI erkennt die Fläche. Weitere Klicks verfeinern, Umschalt- oder Rechtsklick nimmt weg.',
        line: MK.line.length ? 'Weiter klicken · Doppelklick beendet – dann legt die KI die Linie an die nächste Kante.' : '✨ Klicke grob ein paar Punkte entlang einer Kante (z. B. Horizont) und beende mit Doppelklick – die KI legt die Linie genau an die Kante.',
        ring: '✨ Klick aufs Motiv – die KI legt den Ring passend darum.',
        box: '✨ Platzvorschlag: die KI zeigt ruhige Stellen im Bild – zum Übernehmen anklicken.' }[MK.mode] +
        (MK.target === 'viz' ? ' Was die KI markiert, wird als Welle dargestellt.' : '');
    return;
  }
  const fxBox = MK.target !== 'viz' && MK.mode === 'box';
  const none = (MK.mode === 'mask' && shp() !== 'mask') || ((MK.mode === 'line' || MK.mode === 'ring') && shp() !== 'path' && !MK.line.length);
  h.hidden = !markOn();
  h.textContent = fxBox ? (MK.target === 'ai' ? 'Das ganze Bild bewegt sich. Mit „Fläche“ legst du fest, dass sich nur ein Teil bewegt – der Rest bleibt dein scharfes Original.' : 'Der Effekt wirkt auf dem ganzen Bild. Mit Fläche, Linie oder Ring legst du fest, wo genau.')
    : t + (none && MK.mode !== 'box' ? (MK.target === 'fx' ? ' (Noch nichts markiert – bis dahin wirkt der Effekt auf dem ganzen Bild.)' : MK.target === 'ai' ? ' (Noch nichts markiert – bis dahin bewegt sich das ganze Bild.)' : ' (Noch nichts markiert – bis dahin gilt der Kasten.)') : '');
}
function renderMarkTools() {
  const box = $('#mkTools'); box.textContent = '';
  const s = S.settings, ai = S.info && S.info.ai;
  const btn = (label, fn, cls = '', extra = {}) => el('button', Object.assign({ type: 'button', class: 'btn small ' + cls, onclick: fn }, extra), label);
  const slider = (label, k, min, max, step, fmt) => { const i = el('input', { type: 'range', min, max, step, value: k === 'size' ? MK.size : s[k], 'aria-label': label }); const b = el('b', {}, fmt(k === 'size' ? MK.size : s[k])); i.oninput = () => { if (k === 'size') MK.size = +i.value; else { s[k] = +i.value; drawMarkSvg(); saveSettings(); refreshCommand() } b.textContent = fmt(+i.value) }; return el('label', { class: 'mini' }, label, i, b) };
  if (MK.busy) box.append(el('span', { class: 'mk-busy' }, el('span', { class: 'spin' }), MK.busy));
  if (MK.mode === 'box') {
    /* Kasten: im Bild ziehen */
  } else if (MK.mode === 'mask') {
    const seg = el('div', { class: 'seg', role: 'group', 'aria-label': 'Werkzeug' });
    [['brush', 'Pinsel'], ['erase', 'Radierer'], ['rect', 'Rechteck'], ['ellipse', 'Ellipse']].forEach(([id, n]) =>
      seg.append(el('button', { type: 'button', 'aria-pressed': String(MK.tool === id), onclick: () => { MK.tool = id; MK.aiPts = []; MK.aiBase = null; renderMarkTools(); markHint() } }, n)));
    box.append(seg);
    if (MK.tool === 'brush' || MK.tool === 'erase') box.append(slider('Größe', 'size', 6, 160, 2, v => v + ' px'));
    box.append(slider('Weiche Kante', P('Feather'), 0, 5, 0.1, v => String(v).replace('.', ',') + ' %'));
    box.append(btn('Alles löschen', () => { mc().getContext('2d').clearRect(0, 0, mc().width, mc().height); MK.aiPts = []; MK.aiBase = null; renderMaskOverlay(); uploadMask() }));
  } else {
    if (MK.mode === 'line') {
      if (MK.line.length) box.append(btn('Fertig', finishLine, 'glow'));
      box.append(btn('Neu zeichnen', () => { MK.line = []; if (shp() === 'path') { setShp('box'); changed('viz') } else renderMark() }));
    }
    if (MK.target === 'viz') {
      const seg = el('div', { class: 'seg', role: 'group', 'aria-label': 'Richtung' });
      [[false, MK.mode === 'ring' ? 'Nach außen' : 'Nach oben'], [true, 'Beidseitig']].forEach(([v, n]) => seg.append(el('button', { type: 'button', 'aria-pressed': String(s.vizBoth === v), onclick: () => set('vizBoth', v) }, n)));
      box.append(seg, slider('Dicke', 'vizThick', 3, 40, 1, v => v + ' %'));
    } else box.append(slider(s.fx === 'streaks' ? 'Leuchtbreite' : 'Bandbreite', 'fxThick', 2, 40, 1, v => v + ' %'));
  }
}
function pickMode(m) {
  MK.mode = m; MK.line = []; MK.ringAi = false; $('#sugBox').hidden = true;
  if (m === 'box') setShp('box');
  else if (m === 'mask') { if (M.Mask) setShp('mask') }
  else if (M.Path && M.Path.length > 1 && M.Closed === (m === 'ring')) setShp('path');
  else if (shp() !== 'box') setShp('box');
  changed('viz');
}
$$('#mkModes button').forEach(b => b.onclick = () => pickMode(b.dataset.m));
function pickTab(t) {
  MK.tab = t; MK.line = []; MK.ringAi = false; MK.aiPts = []; MK.aiBase = null; $('#sugBox').hidden = true;
  if (t === 'ai' && MK.mode === 'mask') MK.tool = 'ai';
  if (t === 'hand' && MK.tool === 'ai') MK.tool = 'brush';
  changed('viz');
}
$$('#mkTabs button').forEach(b => b.onclick = () => pickTab(b.dataset.tab));
function aiAction(m) {
  if (!S.image) { toast('Zuerst ein Bild hineinziehen'); return }
  MK.tab = 'ai'; MK.mode = m; MK.line = []; MK.aiPts = []; MK.aiBase = null; MK.ringAi = m === 'ring'; $('#sugBox').hidden = true;
  if (m === 'mask') MK.tool = 'ai';
  changed('viz');
  if (m === 'box') suggestPlaces();
}
function renderAiRow() {
  const row = $('#mkAiRow'); if (MK.tab !== 'ai') return; row.textContent = '';
  const ai = S.info && S.info.ai, ok = !!(ai && ai.tools) && !!S.image;
  const acts = MK.target === 'ai' ? [['mask', '✨ Motiv auswählen', 'Fläche']] : [['mask', '✨ Motiv auswählen', 'Fläche'], ['line', '✨ Linie an Kante', 'Linie'], ['ring', '✨ Ring ums Motiv', 'Ring']];
  if (MK.target === 'viz') acts.push(['box', '✨ Platzvorschlag', 'Kasten']);
  const seg = el('div', { class: 'seg', role: 'group', 'aria-label': 'KI-Werkzeug' });
  acts.forEach(([m, n, t]) => seg.append(el('button', { type: 'button', title: t, disabled: !ok, 'aria-pressed': String(MK.mode === m), onclick: () => aiAction(m) }, n)));
  row.append(seg);
  if (MK.target === 'viz') {
    const ws = el('div', { class: 'seg waves', role: 'group', 'aria-label': 'Wellenform der KI' });
    AI_WAVES.forEach(([id, n]) => ws.append(el('button', { type: 'button', 'aria-pressed': String(S.settings.vizAiWave === id), onclick: () => set('vizAiWave', id) }, n)));
    row.append(el('span', { class: 'mk-lbl' }, 'Welle:'), ws);
  }
  if (MK.mode === 'line' && MK.line.length) row.append(el('button', { type: 'button', class: 'btn small glow', onclick: finishLine }, 'Fertig'));
  if (MK.mode === 'mask' && MK.aiPts.length) row.append(el('button', { type: 'button', class: 'btn small', onclick: () => { MK.aiPts = []; MK.aiBase = null; renderAiRow() } }, 'Neue Auswahl'));
  if (MK.busy) row.append(el('span', { class: 'mk-busy' }, el('span', { class: 'spin' }), MK.busy));
  if (!(ai && ai.tools)) row.append(el('small', { class: 'mhint' }, 'KI auf diesem PC nicht verfügbar.'));
}
function markSummary() {
  const s = S.settings, part = [];
  const name = (t) => { const sh = shp(t), cl = t === 'fx' ? s.fxClosed : s.vizClosed; return sh === 'mask' ? 'Fläche' : sh === 'path' ? (cl ? 'Ring' : 'Linie') : t !== 'viz' ? 'ganzes Bild' : 'Kasten' };
  if (s.viz) part.push('Visualizer: ' + name('viz') + (s.vizAi ? ' (✨ KI-Welle)' : ''));
  if (fxOn()) part.push('Effekt: ' + name('fx'));
  if (aiOn()) part.push('KI-Video: ' + name('ai'));
  $('#mkSum').textContent = part.join(' · ');
}
function pickTarget(t) { MK.target = t; MK.line = []; MK.ringAi = false; MK.aiPts = []; MK.mode = modeFromSettings(); changed('viz') }
$$('#mkTarget button').forEach(b => b.onclick = () => pickTarget(b.dataset.t));

/* Fläche malen */
function renderMaskOverlay() {
  const v = $('#markCanvas'), g = v.getContext('2d');
  g.globalCompositeOperation = 'source-over'; g.clearRect(0, 0, v.width, v.height); g.drawImage(mc(), 0, 0);
  g.globalCompositeOperation = 'source-in'; g.fillStyle = 'rgba(255,90,170,.45)'; g.fillRect(0, 0, v.width, v.height);
  g.globalCompositeOperation = 'source-over';
}
function cpos(e) { const v = $('#markCanvas'), r = v.getBoundingClientRect(); return [(e.clientX - r.left) / r.width * v.width, (e.clientY - r.top) / r.height * v.height] }
function stroke(a, b) {
  const g = mc().getContext('2d'); g.globalCompositeOperation = MK.tool === 'erase' ? 'destination-out' : 'source-over';
  g.strokeStyle = g.fillStyle = '#fff'; g.lineCap = 'round'; g.lineWidth = MK.size * mc().width / 960;
  g.beginPath(); g.moveTo(a[0], a[1]); g.lineTo(b[0], b[1]); g.stroke();
  g.beginPath(); g.arc(b[0], b[1], g.lineWidth / 2, 0, Math.PI * 2); g.fill(); g.globalCompositeOperation = 'source-over';
}
function shapePath(g, a, b) { g.beginPath(); if (MK.tool === 'rect') g.rect(Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.abs(b[0] - a[0]), Math.abs(b[1] - a[1])); else g.ellipse((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, Math.abs(b[0] - a[0]) / 2, Math.abs(b[1] - a[1]) / 2, 0, 0, Math.PI * 2) }
$('#markCanvas').addEventListener('contextmenu', e => e.preventDefault());
$('#markCanvas').addEventListener('pointerdown', e => {
  e.preventDefault(); const p = cpos(e);
  if (MK.tool === 'ai') { aiClick(p[0] / mc().width, p[1] / mc().height, !(e.shiftKey || e.button === 2)); return }
  $('#markCanvas').setPointerCapture(e.pointerId); MK.drawing = true; MK.last = p; MK.start = p;
  if (MK.tool === 'brush' || MK.tool === 'erase') { stroke(p, p); renderMaskOverlay() }
});
$('#markCanvas').addEventListener('pointermove', e => {
  if (!MK.drawing) return; const p = cpos(e);
  if (MK.tool === 'brush' || MK.tool === 'erase') { stroke(MK.last, p); MK.last = p; renderMaskOverlay() }
  else { renderMaskOverlay(); const g = $('#markCanvas').getContext('2d'); shapePath(g, MK.start, p); g.fillStyle = 'rgba(255,90,170,.45)'; g.fill(); g.strokeStyle = '#fff'; g.setLineDash([6, 4]); g.stroke(); g.setLineDash([]) }
});
$('#markCanvas').addEventListener('pointerup', e => {
  if (!MK.drawing) return; MK.drawing = false; const p = cpos(e);
  if (MK.tool === 'rect' || MK.tool === 'ellipse') { const g = mc().getContext('2d'); shapePath(g, MK.start, p); g.fillStyle = '#fff'; g.fill() }
  renderMaskOverlay(); uploadMask();
});
const uploadMask = debounce(async () => {
  const tg = MK.target, maskC = MASKC[tg];
  try {
    const blob = await new Promise(r => maskC.toBlob(r, 'image/png'));
    const r = await fetch('/api/mark/mask', { method: 'POST', headers: { 'X-Studio': TOKEN }, body: blob });
    const d = await r.json(); if (!r.ok) throw new Error(d.error);
    const s = S.settings, k = tg === 'viz' ? 'viz' : tg;
    if (d.token) {
      MURL[tg] = maskC.toDataURL('image/png');
      Object.assign(s, { [k + 'Mask']: d.token, [k + 'X']: d.bbox[0], [k + 'Y']: d.bbox[1], [k + 'W']: Math.max(2, d.bbox[2]), [k + 'H']: Math.max(2, d.bbox[3]) });
      if (tg !== 'viz') s[tg + 'Area'] = 'mask'; else Object.assign(s, { vizShape: 'mask', vizDock: '', vizAi: MK.tab === 'ai' });
    } else { s[k + 'Mask'] = ''; MURL[tg] = ''; if (tg !== 'viz') s[tg + 'Area'] = 'full'; else { s.vizShape = 'box'; s.vizAi = false } }
    changed('viz');
  } catch (e) { toast('Maske: ' + e.message, true) }
}, 350);
async function loadMaskFromServer(tok, tg = 'viz') {
  ensureMask(); const maskC = MASKC[tg], g = maskC.getContext('2d'); g.clearRect(0, 0, maskC.width, maskC.height);
  if (!tok) { MURL[tg] = ''; renderMaskOverlay(); return }
  try {
    const resp = await fetch('/api/maskfile/' + tok, { headers: { 'X-Studio': TOKEN } });
    if (!resp.ok) {                                // Markierung von einer früheren Sitzung gibt es nicht mehr
      MURL[tg] = '';
      if (tg !== 'viz') { S.settings[tg + 'Mask'] = ''; if (S.settings[tg + 'Area'] === 'mask') S.settings[tg + 'Area'] = 'full' }
      else { S.settings.vizMask = ''; if (S.settings.vizShape === 'mask') S.settings.vizShape = 'box' }
      MK.mode = modeFromSettings(); changed('viz'); return;
    }
    const blob = await resp.blob();
    const img = await createImageBitmap(blob); grayToAlpha(img, g); MURL[tg] = maskC.toDataURL('image/png'); renderMaskOverlay(); placeVizBox();
  } catch (_) {}
}
function grayToAlpha(img, g) {
  const maskC = g.canvas, t = document.createElement('canvas'); t.width = maskC.width; t.height = maskC.height;
  const tg = t.getContext('2d'); tg.drawImage(img, 0, 0, t.width, t.height);
  const d = tg.getImageData(0, 0, t.width, t.height), a = d.data;
  for (let i = 0; i < a.length; i += 4) { const v = a[i]; a[i] = a[i + 1] = a[i + 2] = 255; a[i + 3] = v }
  tg.putImageData(d, 0, 0); g.globalCompositeOperation = 'source-over'; g.drawImage(t, 0, 0);
}
async function aiClick(x, y, add) {
  if (!S.image) { toast('Zuerst ein Bild hineinziehen'); return }
  const maskC = mc();
  if (!MK.aiPts.length) { MK.aiBase = document.createElement('canvas'); MK.aiBase.width = maskC.width; MK.aiBase.height = maskC.height; MK.aiBase.getContext('2d').drawImage(maskC, 0, 0) }
  MK.aiPts.push([x, y, add ? 1 : 0]);
  busy('KI erkennt das Motiv …');
  try {
    const d = await api('/api/mark/segment', { image: S.image.token, settings: S.settings, points: MK.aiPts });
    const img = await createImageBitmap(await (await fetch(d.url, { headers: { 'X-Studio': TOKEN } })).blob());
    const g = maskC.getContext('2d'); g.clearRect(0, 0, maskC.width, maskC.height); g.drawImage(MK.aiBase, 0, 0); grayToAlpha(img, g);
    renderMaskOverlay(); uploadMask();
    if (d.method !== 'ki' && !MK.warned) { MK.warned = true; toast('Hinweis: KI-Modell nicht gefunden – einfache Erkennung benutzt. Mit Pinsel/Radierer nachbessern.') }
  } catch (e) { toast(e.message, true); MK.aiPts.pop() }
  finally { busy('') }
}

/* Linie & Ring */
function spos(e) { const r = $('#frame').getBoundingClientRect(); return [(e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height] }
$('#markSvg').addEventListener('pointerdown', e => {
  if (!markOn() || (MK.mode !== 'line' && MK.mode !== 'ring')) return;
  e.preventDefault(); const p = spos(e);
  if (e.target.classList.contains('pt') && !MK.line.length) { MK.drag = +e.target.dataset.i; $('#markSvg').setPointerCapture(e.pointerId); return }
  if (MK.mode === 'line') {
    const [fw, fh] = frameSize(), q = MK.line[MK.line.length - 1], now = performance.now();
    if (q && now - MK.lastTap < 450 && Math.hypot((p[0] - q[0]) * fw, (p[1] - q[1]) * fh) < 10) { finishLine(); return }
    MK.lastTap = now; MK.line.push(p); drawMarkSvg(); renderMarkTools(); markHint(); return
  }
  if (MK.tab === 'ai' || MK.ringAi) { ringFromAi(p); return }
  MK.start = p; MK.drawing = true; $('#markSvg').setPointerCapture(e.pointerId);
});
$('#markSvg').addEventListener('pointermove', e => {
  const p = spos(e);
  if (MK.drag >= 0) { M.Path[MK.drag] = p; drawMarkSvg(); return }
  if (MK.drawing && MK.mode === 'ring') { setRing(MK.start, p); drawMarkSvg() }
});
$('#markSvg').addEventListener('pointerup', () => {
  if (MK.drag >= 0) { MK.drag = -1; setAi(false); changed('viz'); return }
  if (MK.drawing) { MK.drawing = false; setAi(false); changed('viz') }
});
function setRing(c, p) {
  const [fw, fh] = frameSize(), r = Math.max(8, Math.hypot((p[0] - c[0]) * fw, (p[1] - c[1]) * fh)), pts = [];
  for (let i = 0; i < 96; i++) { const a = i / 96 * Math.PI * 2; pts.push([+(c[0] + r / fw * Math.cos(a)).toFixed(5), +(c[1] + r / fh * Math.sin(a)).toFixed(5)]) }
  M.Closed = true; M.Path = pts; setShp('path');
}
function finishLine() {
  const [fw, fh] = frameSize(); MK.line = MK.line.filter((q, i, l) => !i || Math.hypot((q[0] - l[i - 1][0]) * fw, (q[1] - l[i - 1][1]) * fh) > 6);
  if (MK.line.length < 2) { toast('Für eine Linie mindestens zwei Punkte setzen'); return }
  M.Closed = false; M.Path = MK.line.map(q => [+q[0].toFixed(5), +q[1].toFixed(5)]); setShp('path');
  MK.line = []; setAi(false); changed('viz');
  if (MK.tab === 'ai') refineLine();
}
async function refineLine() {
  busy('KI legt die Linie an die Kante …');
  try { const d = await api('/api/mark/refine', { image: S.image.token, settings: S.settings, points: M.Path, closed: false }); M.Path = d.points; setAi(true); changed('viz'); toast('✓ Die KI hat die Linie an die Kante gelegt') }
  catch (e) { toast(e.message, true) } finally { busy('') }
}
async function ringFromAi(p) {
  busy('KI erkennt das Motiv …');
  try {
    const d = await api('/api/mark/segment', { image: S.image.token, settings: S.settings, points: [[p[0], p[1], 1]] });
    if (!d.bbox) throw new Error('Kein Motiv erkannt – anders klicken');
    const [x, y, w, h] = d.bbox, [fw, fh] = frameSize(), c = [(x + w / 2) / 100, (y + h / 2) / 100];
    const r = Math.max(w / 100 * fw, h / 100 * fh) / 2 * 1.08;
    setRing(c, [c[0] + r / fw, c[1]]); setAi(true); changed('viz');
    toast(d.method === 'ki' ? '✓ Ring um das Motiv gelegt' : '✓ Ring gelegt (einfache Erkennung)');
  } catch (e) { toast(e.message, true) } finally { busy('') }
}
function pathPx(pts, fw, fh) { return pts.map(q => [q[0] * fw, q[1] * fh]) }
function resamplePx(p, n, closed) {
  const q = closed ? p.concat([p[0]]) : p, seg = [], cum = [0];
  for (let i = 1; i < q.length; i++) { const l = Math.hypot(q[i][0] - q[i - 1][0], q[i][1] - q[i - 1][1]); seg.push(l); cum.push(cum[i - 1] + l) }
  const L = cum[cum.length - 1] || 1, out = [];
  for (let k = 0; k < n; k++) {
    const t = closed ? k / n * L : k / (n - 1) * L; let i = 1; while (i < cum.length - 1 && cum[i] < t) i++;
    const f = seg[i - 1] ? (t - cum[i - 1]) / seg[i - 1] : 0; out.push([q[i - 1][0] + (q[i][0] - q[i - 1][0]) * f, q[i - 1][1] + (q[i][1] - q[i - 1][1]) * f]);
  }
  return out;
}
function drawMarkSvg() {
  const svg = $('#markSvg'), s = S.settings; if (!s) return;
  const [fw, fh] = frameSize(); svg.setAttribute('viewBox', `0 0 ${fw} ${fh}`);
  let html = '';
  if (s.viz && s.vizShape === 'path' && !(MK.target === 'viz' && MK.line.length)) html += pathSketch(pathPx(s.vizPath, fw, fh), s.vizClosed, fw, fh);
  const editing = markOn() && (MK.mode === 'line' || MK.mode === 'ring');
  const editPts = MK.line.length ? MK.line : (editing && shp() === 'path' ? M.Path : []);
  if (editPts.length) {
    const px = pathPx(editPts, fw, fh), closed = !MK.line.length && M.Closed;
    html += `<polyline points="${px.concat(closed ? [px[0]] : []).map(q => q[0].toFixed(1) + ',' + q[1].toFixed(1)).join(' ')}" fill="none" stroke="#fff" stroke-width="1.5" stroke-dasharray="6 5" opacity=".8"/>`;
    const hand = MK.tab === 'hand' && (MK.target !== 'viz' || !s.vizAi) && editPts.length <= 24;
    if (MK.mode === 'line' && hand) px.forEach((q, i) => { html += `<circle class="pt" data-i="${i}" cx="${q[0].toFixed(1)}" cy="${q[1].toFixed(1)}" r="6"/>` });
  }
  svg.innerHTML = html;
}
function waveSketch(px, closed, fw, fh, st) {
  const s = S.settings, n = Math.max(40, Math.round(s.vizDens * 3)), pts = resamplePx(px, n, closed), wv = wav(n, VT, s, 0);
  const T = s.vizThick / 100 * fh, out = [], q = [];
  for (let i = 0; i < pts.length; i++) {
    const A = pts[closed ? (i - 1 + n) % n : Math.max(0, i - 1)], B = pts[closed ? (i + 1) % n : Math.min(n - 1, i + 1)];
    let nx = -(B[1] - A[1]), ny = B[0] - A[0]; const l = Math.hypot(nx, ny) || 1; nx /= l; ny /= l;
    const env = closed ? 1 : Math.sin(Math.min(1, i / (n - 1)) * Math.PI) * 0.8 + 0.2, h = wv[i] * T * env;
    q.push([pts[i][0] + nx * h, pts[i][1] + ny * h]);
  }
  if (closed) { q.push(q[0]); pts.push(pts[0]) }
  const lw = Math.max(1.5, s.vizLine * fh / 540);
  if (st === 'dots') q.forEach((p, i) => out.push(`<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="${(lw * 0.9).toFixed(1)}" fill="${colorAt(s, i / q.length, VT)}"/>`));
  else {
    const reps = st === 'bundle' ? 3 : 1;
    for (let r = 0; r < reps; r++) for (let i = 1; i < q.length; i++) {
      const k = 1 - r * 0.3, a = q[i - 1], b = q[i], m = pts[i - 1], m2 = pts[i];
      const ax = m[0] + (a[0] - m[0]) * k, ay = m[1] + (a[1] - m[1]) * k, bx = m2[0] + (b[0] - m2[0]) * k, by = m2[1] + (b[1] - m2[1]) * k;
      out.push(`<line x1="${ax.toFixed(1)}" y1="${ay.toFixed(1)}" x2="${bx.toFixed(1)}" y2="${by.toFixed(1)}" stroke="${colorAt(s, i / q.length, VT)}" stroke-width="${(st === 'line' ? lw * 0.6 : lw).toFixed(1)}" stroke-linecap="round" opacity="${(1 - r * 0.3).toFixed(2)}"/>`);
    }
  }
  const glow = st === 'neon' ? Math.max(s.vizGlow, 65) : s.vizGlow;
  const f = glow > 0 ? ` style="filter:drop-shadow(0 0 ${Math.round(glow / 9)}px ${colorAt(s, .5, VT)})"` : '';
  return `<g opacity="${s.vizAlpha / 100}"${f}>${out.join('')}</g>`;
}
function pathSketch(px, closed, fw, fh) {
  if (WAVE_FAMILY.includes(effStyle(S.settings))) return waveSketch(px, closed, fw, fh, effStyle(S.settings));
  const s = S.settings, n = Math.max(16, Math.round(s.vizDens * (closed ? 1.4 : 1))), pts = resamplePx(px, n, closed), sp = spec(n, VT, s);
  let area = 0; if (closed) for (let i = 0; i < pts.length; i++) { const a = pts[i], b = pts[(i + 1) % pts.length]; area += a[0] * b[1] - b[0] * a[1] }
  const T = s.vizThick / 100 * fh, glow = s.vizGlow, out = [];
  const sign = closed ? (area > 0 ? 1 : -1) : ((pts[pts.length - 1][0] - pts[0][0]) >= 0 ? -1 : 1);
  const step = closed ? 2 * Math.PI : 0, len = (closed ? pts.length : pts.length - 1) || 1, wdt = Math.max(1.5, (px.length > 1 ? 1 : 1) * 0.6 * ((closed ? 2 : 1) * Math.PI * 0 + 1) * (Math.hypot(fw, fh) / n) * 0.35);
  for (let i = 0; i < pts.length; i++) {
    const a = pts[(i - 1 + pts.length) % pts.length], b = pts[(i + 1) % pts.length];
    const A = closed || i > 0 ? a : pts[i], B = closed || i < pts.length - 1 ? b : pts[i];
    let nx = -(B[1] - A[1]), ny = B[0] - A[0]; const l = Math.hypot(nx, ny) || 1; nx = nx / l * sign; ny = ny / l * sign;
    const h = sp[i] * T, p = pts[i], c = colorAt(s, i / Math.max(1, pts.length - 1), VT);
    const x0 = s.vizBoth ? p[0] - nx * h : p[0], y0 = s.vizBoth ? p[1] - ny * h : p[1];
    out.push(`<line x1="${x0.toFixed(1)}" y1="${y0.toFixed(1)}" x2="${(p[0] + nx * h).toFixed(1)}" y2="${(p[1] + ny * h).toFixed(1)}" stroke="${c}" stroke-width="${wdt.toFixed(1)}" stroke-linecap="round"/>`);
  }
  const f = glow > 0 ? ` style="filter:drop-shadow(0 0 ${Math.round(glow / 9)}px ${colorAt(s, .5, VT)})"` : '';
  return `<g opacity="${s.vizAlpha / 100}"${f}>${out.join('')}</g>`;
}

/* KI-Platzvorschlag */
async function suggestPlaces() {
  busy('KI sucht ruhige Stellen …');
  try {
    const d = await api('/api/mark/suggest', { image: S.image.token, settings: S.settings });
    const sb = $('#sugBox'); sb.textContent = ''; sb.hidden = false;
    d.suggestions.forEach((c, i) => sb.append(el('button', { type: 'button', class: 'sug', style: `left:${c.x}%;top:${c.y}%;width:${c.w}%;height:${c.h}%`, onclick: () => { sb.hidden = true; goDock(c.dock, true); toast('✓ ' + c.name + ' – als KI-Welle') } },
      el('span', {}, `${i + 1} · ${c.name} – ${c.why}`))));
    clearTimeout(MK.sugTimer); MK.sugTimer = setTimeout(() => { sb.hidden = true }, 15000);
    if (d.faces) toast(`${d.faces} Gesicht(er) erkannt – die Vorschläge meiden sie.`);
  } catch (e) { toast(e.message, true) } finally { busy('') }
}


/* ---------- Bild-Effekte & Kamera ---------- */
const FX_ICON = {
  none: '<path d="M5 5l14 14M19 5L5 19"/>', streaks: '<path d="M3 17L14 6M8 20L20 8M2 11l6-6"/>', sparks: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5L18 18M18 6l-2.5 2.5M8.5 15.5L6 18"/>',
  glitter: '<path d="M12 2l1.8 6.2L20 10l-6.2 1.8L12 18l-1.8-6.2L4 10l6.2-1.8z"/>', bokeh: '<circle cx="8" cy="9" r="4"/><circle cx="16" cy="15" r="5"/><circle cx="17" cy="6" r="2"/>',
  dust: '<circle cx="6" cy="7" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="17" cy="6" r="1"/><circle cx="9" cy="17" r="1"/><circle cx="18" cy="16" r="1"/>',
  snow: '<path d="M12 3v18M4.2 7.5l15.6 9M4.2 16.5l15.6-9"/>', rain: '<path d="M8 3l-2 6M14 5l-2 6M20 3l-2 6M10 13l-2 6M16 13l-2 6"/>',
  fog: '<path d="M3 9h13a3 3 0 0 0 0-6M3 15h17a3 3 0 0 1 0 6M3 12h9"/>', flow: '<path d="M2 8c3-3 5 3 8 0s5 3 8 0 3-1 4-1M2 14c3-3 5 3 8 0s5 3 8 0 3-1 4-1"/>'
};
const FX_SLIDERS = [
  ['fxAmount', 'Menge', 1, 100, 1, v => v + ' %', 'wie viele Teilchen bzw. wie stark'],
  ['fxSpeed', 'Tempo', 1, 100, 1, v => v + ' %', 'wie schnell sie sich bewegen'],
  ['fxSize', 'Größe', 1, 100, 1, v => v + ' %', 'wie groß Teilchen und Linien sind'],
  ['fxAlpha', 'Deckkraft', 5, 100, 5, v => v + ' %', 'weniger = zarter'],
  ['fxAngle', 'Winkel', -75, 75, 5, v => v + '°', 'Richtung von Lichtlinien bzw. Regen']
];
const CAM_SLIDERS = [['camAmount', 'Stärke', 1, 100, 1, v => v + ' %'], ['camSpeed', 'Tempo', 1, 100, 1, v => v + ' %']];
const FXM = [['auto', 'Farben aus dem Bild'], ['solid', 'Eigene Farbe'], ['rainbow', 'Regenbogen']];
let IMGCOL = { key: '', cols: ['#f5b544', '#ff5fa2', '#7cc8ff'], avg: '#c8b8a0' };
function imageColors() {
  const img = $('#stillImg'); if (!img.complete || !img.naturalWidth || img.hidden) return IMGCOL;
  if (IMGCOL.key === img.src) return IMGCOL;
  try {
    const c = document.createElement('canvas'); c.width = 40; c.height = 24; const g = c.getContext('2d'); g.drawImage(img, 0, 0, 40, 24);
    const d = g.getImageData(0, 0, 40, 24).data, px = []; let r = 0, gg = 0, b = 0;
    for (let i = 0; i < d.length; i += 4) { r += d[i]; gg += d[i + 1]; b += d[i + 2]; const mx = Math.max(d[i], d[i + 1], d[i + 2]), mn = Math.min(d[i], d[i + 1], d[i + 2]); px.push([mx - mn + mx * 0.4, d[i], d[i + 1], d[i + 2]]) }
    const n = d.length / 4; px.sort((a, b) => b[0] - a[0]);
    const cols = [];
    for (const q of px) { if (cols.every(c => Math.abs(c[0] - q[1]) + Math.abs(c[1] - q[2]) + Math.abs(c[2] - q[3]) > 90)) cols.push(q.slice(1)); if (cols.length >= 3) break }
    const hx = c => '#' + c.map(v => Math.round(v).toString(16).padStart(2, '0')).join('');
    IMGCOL = { key: img.src, cols: cols.length ? cols.map(hx) : IMGCOL.cols, avg: hx([r / n, gg / n, b / n]) };
  } catch (_) {}
  return IMGCOL;
}
function fxColors() {
  const s = S.settings;
  if (s.fxColorMode === 'solid') return [s.fxColor, s.fxColor];
  if (s.fxColorMode === 'rainbow') return RAINBOW;
  const ic = imageColors();
  if (['snow', 'rain', 'fog', 'dust'].includes(s.fx)) return [mix(ic.avg, '#ffffff', .78), mix(ic.cols[0], '#ffffff', .7)];
  if (s.fx === 'sparks') return [mix(ic.cols[0], '#ff9628', .55), mix(ic.cols[0], '#ffecaa', .6)];
  return ic.cols;
}
function renderFx() {
  if (!S.settings || !S.info || !S.info.fx) return;
  const s = S.settings, info = S.info.fx, on = s.fx !== 'none';
  const tb = $('#fxTiles');
  if (!tb.childElementCount) {
    info.effects.forEach(e => tb.append(el('button', { type: 'button', class: 'fxtile', 'data-id': e.id, title: e.name, 'aria-label': e.name, onclick: () => setFx(e.id) },
      el('span', { class: 'fx-ic', 'aria-hidden': 'true', html: `<svg viewBox="0 0 24 24">${FX_ICON[e.id] || ''}</svg>` }), el('span', {}, e.short))));
    tb.append(el('button', { type: 'button', class: 'fxtile ai-tile', title: 'KI-Video – echte Bewegung aus deinem Bild', 'aria-label': 'KI-Video öffnen', onclick: openAiCard },
      el('em', {}, 'NEU'), el('span', { class: 'fx-ic', 'aria-hidden': 'true' }, '🎬'), el('span', {}, 'KI-Video')));
  }
  $$('.fxtile').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.id === s.fx)));
  const cur = info.effects.find(e => e.id === s.fx) || info.effects[0];
  $('#fxDesc').textContent = cur.desc;
  const camName = (info.cams.find(c => c.id === s.cam) || info.cams[0]).name;
  $('#fxChip').textContent = on ? cur.name + (s.cam !== 'none' ? ' + ' + camName : '') : s.cam !== 'none' ? camName : 'Aus';
  $('#fxChip').classList.toggle('acc', on || s.cam !== 'none');
  $('#fxBody').classList.toggle('off', !on);
  const where = shp('fx'), wm = where === 'path' ? (s.fxClosed ? 'ring' : 'line') : where;
  $$('#fxWhere button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.m === wm)));
  $('#fxWhereHint').textContent = s.fx === 'flow' ? 'Tipp: Fließen wirkt am schönsten auf einer gemalten Fläche (Wasser, Himmel, Feuer).'
    : s.fx === 'streaks' ? 'Mit Linie oder Ring laufen die Lichtlinien genau dort entlang.' : 'Markieren geht direkt im Vorschaubild oben.';
  const mb = $('#fxModes'); mb.textContent = '';
  const ic = imageColors(), sw = { auto: `linear-gradient(90deg,${ic.cols.join(',')})`, solid: s.fxColor, rainbow: `linear-gradient(90deg,${RAINBOW.join(',')})` };
  FXM.forEach(([id, n]) => mb.append(el('button', { type: 'button', class: 'mode', 'aria-pressed': String(s.fxColorMode === id), onclick: () => set('fxColorMode', id) }, el('i', { style: 'background:' + sw[id] }), n)));
  $('#fxColor').value = s.fxColor;
  $('#fxColorWrap').hidden = s.fxColorMode !== 'solid' || s.fx === 'flow';
  $('#fxModes').hidden = s.fx === 'flow';
  $('#fxBeat').setAttribute('aria-checked', String(s.fxBeat)); $('#fxBeat .switch').setAttribute('aria-checked', String(s.fxBeat));
  $('#fxBeat').hidden = s.fx === 'flow';
  const list = FX_SLIDERS.filter(q => q[0] !== 'fxAngle' || ['streaks', 'rain'].includes(s.fx)).filter(q => s.fx !== 'flow' || ['fxAmount', 'fxSpeed', 'fxSize'].includes(q[0]));
  fxSliders($('#fxSliders'), list);
  const cs = $('#camSeg'); if (!cs.childElementCount) info.cams.forEach(c => cs.append(el('button', { type: 'button', 'data-v': c.id, onclick: () => set('cam', c.id) }, c.name.replace(' (KI)', ''))));
  $$('#camSeg button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.v === s.cam)));
  const cd = info.cams.find(c => c.id === s.cam) || info.cams[0];
  $('#camHint').textContent = cd.desc + (s.cam === 'depth' ? (info.depth ? ' Die Tiefe erkennt eine KI auf deinem PC.' : ' (KI-Modell fehlt – es wird eine einfache Tiefenschätzung benutzt.)') + ' Braucht beim Umwandeln deutlich mehr Zeit.' : '');
  $('#camSliders').hidden = s.cam === 'none';
  fxSliders($('#camSliders'), CAM_SLIDERS);
  $('#fxPreviewBtn').disabled = !on && s.cam === 'none';
}
function fxSliders(box, list) {
  const key = list.map(q => q[0]).join();
  if (box.dataset.key === key && box.contains(document.activeElement) && document.activeElement.type === 'range') return;
  if (box.dataset.key === key) { list.forEach(([k, , , , , f]) => { const i = box.querySelector(`input[data-k="${k}"]`); if (i && document.activeElement !== i) i.value = S.settings[k]; box.querySelector(`b[data-k="${k}"]`).textContent = f(S.settings[k]) }); return }
  box.dataset.key = key; box.textContent = '';
  for (const [k, label, min, max, step, f, hint] of list) {
    const id = 'fx-' + k, inp = el('input', { type: 'range', id, min, max, step, value: S.settings[k], 'data-k': k });
    inp.oninput = () => { S.settings[k] = +inp.value; box.querySelector(`b[data-k="${k}"]`).textContent = f(+inp.value); FXS.key = ''; saveSettings(); refreshCommand() };
    box.append(el('div', { class: 'sl', title: hint || '' }, el('div', { class: 'sl-top' }, el('label', { for: id }, label), el('b', { 'data-k': k }, f(S.settings[k]))), inp));
  }
}
function setFx(id) {
  const s = S.settings, was = s.fx; s.fx = id;
  if (id !== 'none' && was === 'none') { MK.target = 'fx'; MK.mode = modeFromSettings() }
  if (id === 'streaks' && was !== 'streaks') s.fxAngle = -20;
  if (id === 'rain' && was !== 'rain') s.fxAngle = 20;
  FXS.key = ''; changed('fx');
}
$$('#fxWhere button').forEach(b => b.onclick = () => {
  if (S.settings.fx === 'none') { toast('Zuerst einen Effekt auswählen'); return }
  MK.target = 'fx'; pickMode(b.dataset.m);
  $('#stage').scrollIntoView({ behavior: 'smooth', block: 'center' });
});
$('#fxColor').oninput = e => { S.settings.fxColor = e.target.value; FXS.key = ''; saveSettings(); refreshCommand(); renderFx() };
$('#fxBeat').onclick = () => set('fxBeat', !S.settings.fxBeat);
$('#fxPreviewBtn').onclick = previewViz;

/* Skizze im Vorschaubild (das echte Ergebnis zeigt „Vorschau mit Ton“) */
const FXS = { key: '', parts: [], t: 0, last: 0 };
function fxParts(s, W, H) {
  const r = seeded(s.fxSeed + 7), u = H / 540, amt = s.fxAmount / 50, size = 0.4 + s.fxSize / 50 * 0.6, out = [];
  const lay = { sparks: [[40, 1.6, -88, 60], [20, 2.4, -85, 105], [8, 3.4, -82, 165]], snow: [[60, 1.2, 98, 22], [26, 2.2, 100, 42], [8, 3.6, 104, 75]],
    dust: [[60, .8, 20, 7], [30, 1.2, 12, 11], [10, 1.8, 30, 17]], bokeh: [[5, 13, -85, 5], [3, 22, -80, 8], [2, 34, -95, 12]],
    rain: [[70, 17, 90, 450], [30, 30, 90, 700], [10, 55, 90, 1050]], glitter: [[40, 3, 0, 0]], streaks: [[10, 130, 0, 210], [5, 210, 0, 350]], fog: [[5, 160, 0, 9], [4, 220, 180, 15]] }[s.fx] || [];
  for (const [n, rad, ang, v] of lay) for (let i = 0; i < Math.max(2, Math.round(n * amt * (W * H) / (960 * 540))); i++)
    out.push({ x: r() * W, y: r() * H, r: rad * u * size * (0.6 + r() * 0.8), ang, v: v * u, ph: r() * 6.28, b: 0.6 + r() * 0.4 });
  return out;
}
function fxFrame(ts) {
  requestAnimationFrame(fxFrame);
  if (!S.settings || document.hidden || ts - FXS.last < 40) return;
  const dt = Math.min(0.1, (ts - FXS.last) / 1000); FXS.last = ts;
  const s = S.settings, cv = $('#fxCanvas'), img = $('#stillImg');
  const spd = 0.15 + s.fxSpeed / 50; FXS.t += dt * spd;
  // Kamera als Skizze: Bild bewegt sich per CSS
  if (s.cam !== 'none' && !img.hidden) {
    const P = 40 - s.camSpeed * 0.32, ph = performance.now() / 1000 / P * 2 * Math.PI, A = s.camAmount / 100;
    img.style.transform = s.cam === 'zoom' ? `scale(${1 + (0.02 + A * 0.14) * (1 - Math.cos(ph)) / 2})`
      : s.cam === 'pan' ? `scale(${1 + 0.05 + A * 0.1}) translateX(${Math.sin(ph) * (0.05 + A * 0.1) / 2 * 100}%)`
      : `scale(${1.035 + A * 0.02 * (1 - Math.cos(ph / 2)) / 2}) translateX(${Math.sin(ph) * A * 0.6}%)`;
  } else img.style.transform = '';
  const r = cv.getBoundingClientRect(), W = Math.round(r.width), H = Math.round(r.height);
  if (!W || !H) return;
  if (cv.width !== W || cv.height !== H) { cv.width = W; cv.height = H; FXS.key = '' }
  const g = cv.getContext('2d'); g.clearRect(0, 0, W, H);
  if (s.fx === 'none' || s.fx === 'flow' || img.hidden) { cv.style.filter = ''; return }
  const key = [s.fx, s.fxAmount, s.fxSize, s.fxSeed, W, H].join();
  if (key !== FXS.key) { FXS.key = key; FXS.parts = fxParts(s, W, H) }
  const cols = fxColors(), t = FXS.t, lv = s.fxBeat ? 0.5 + 0.5 * level(VT) : 1;
  g.globalAlpha = Math.min(1, s.fxAlpha / 100 * lv * 1.2);
  const wrap = (v, m) => ((v % m) + m) % m;
  const pathMode = s.fx === 'streaks' && s.fxArea === 'path' && s.fxPath.length > 1;
  if (pathMode) {
    const pts = resamplePx(pathPx(s.fxPath, W, H), 240, s.fxClosed), n = Math.max(2, Math.round(pts.length / 40 * s.fxAmount / 50));
    g.lineCap = 'round'; g.lineWidth = Math.max(1.5, 2.2 * H / 540 * (0.4 + s.fxSize / 50 * 0.6)); g.shadowBlur = 8; 
    for (let k = 0; k < n; k++) {
      const head = Math.floor(wrap(k / n * pts.length + t * 60, pts.length)), len = 22;
      g.strokeStyle = g.shadowColor = cols[k % cols.length]; g.beginPath();
      for (let j = 0; j < len; j++) { const q = pts[s.fxClosed ? wrap(head - j, pts.length) : Math.max(0, head - j)]; j ? g.lineTo(q[0], q[1]) : g.moveTo(q[0], q[1]) }
      g.stroke();
    }
    g.shadowBlur = 0;
  } else for (const [i, p] of FXS.parts.entries()) {
    const c = cols[i % cols.length], a = p.ang * Math.PI / 180;
    let x = p.x, y = p.y;
    if (s.fx === 'streaks' || s.fx === 'rain') { const ang = (s.fx === 'rain' ? 90 + s.fxAngle * 0.5 : s.fxAngle) * Math.PI / 180;
      x = wrap(p.x + Math.cos(ang) * p.v * t, W); y = wrap(p.y + Math.sin(ang) * p.v * t, H);
      const L = p.r, tx = x - Math.cos(ang) * L, ty = y - Math.sin(ang) * L, gr = g.createLinearGradient(tx, ty, x, y);
      gr.addColorStop(0, 'rgba(255,255,255,0)'); gr.addColorStop(1, c);
      g.strokeStyle = gr; g.lineWidth = s.fx === 'rain' ? Math.max(1, p.r / 25) : Math.max(1.2, p.r / 60); g.beginPath(); g.moveTo(tx, ty); g.lineTo(x, y); g.stroke(); continue }
    if (s.fx !== 'glitter') { x = wrap(p.x + Math.cos(a) * p.v * t, W); y = wrap(p.y + Math.sin(a) * p.v * t, H) }
    let b = p.b;
    if (s.fx === 'glitter') b *= Math.max(0, Math.sin(t * 2.2 + p.ph));
    if (s.fx === 'sparks') b *= 0.55 + 0.45 * Math.sin(t * 9 + p.ph);
    if (s.fx === 'dust') b *= 0.6 + 0.4 * Math.sin(t * 1.5 + p.ph);
    g.globalAlpha = Math.min(1, s.fxAlpha / 100 * lv * 1.2) * b * (s.fx === 'fog' ? 0.32 : s.fx === 'bokeh' ? 0.45 : 1);
    const gr = g.createRadialGradient(x, y, 0, x, y, p.r * (s.fx === 'bokeh' ? 1 : 2.2));
    gr.addColorStop(0, c); gr.addColorStop(s.fx === 'bokeh' ? 0.85 : 0.35, c); gr.addColorStop(1, 'rgba(0,0,0,0)');
    g.fillStyle = gr; g.beginPath(); g.arc(x, y, p.r * (s.fx === 'bokeh' ? 1 : 2.2), 0, Math.PI * 2); g.fill();
    if (s.fx === 'glitter' && b > 0.3) { g.strokeStyle = c; g.lineWidth = 1; g.beginPath(); g.moveTo(x - p.r * 3, y); g.lineTo(x + p.r * 3, y); g.moveTo(x, y - p.r * 3); g.lineTo(x, y + p.r * 3); g.stroke() }
  }
  g.globalAlpha = 1;
  // Bereich: Fläche (Maske) bzw. Band entlang der Linie
  if (s.fxArea === 'mask' && MURL.fx) { g.globalCompositeOperation = 'destination-in'; g.drawImage(MASKC.fx, 0, 0, W, H); g.globalCompositeOperation = 'source-over' }
  else if (s.fxArea === 'path' && !pathMode && s.fxPath.length > 1) {
    g.globalCompositeOperation = 'destination-in'; g.lineWidth = s.fxThick / 100 * H * 2; g.lineCap = g.lineJoin = 'round'; g.strokeStyle = '#000';
    g.beginPath(); pathPx(s.fxPath, W, H).forEach((q, i) => i ? g.lineTo(q[0], q[1]) : g.moveTo(q[0], q[1])); if (s.fxClosed) g.closePath(); g.stroke();
    g.globalCompositeOperation = 'source-over';
  }
}
requestAnimationFrame(fxFrame);

/* ---------- KI-Video (1.8.0): echte Bewegung aus dem Bild, offline ---------- */
const AI = { st: null, info: null, infoKey: '', job: '', jobKind: '', timer: 0, seed: 0, poll: 0, fix: null, stars: 0, tags: [], view: '' };
/* KI-Video-Fenster (2. Monitor): gleiche Seite mit ?ki=1, Abgleich mit dem Hauptfenster per BroadcastChannel */
const KICH = 'BroadcastChannel' in window ? new BroadcastChannel('fes-ki') : null;
const NATIVE_KI = () => !KIWIN && !!(window.pywebview && window.pywebview.api && window.pywebview.api.ki_open);
let KI_RX = false;
function aiPatch(p) {                    // KI-Einstellung ändern – im KI-Fenster ans Hauptfenster melden (das speichert)
  Object.assign(S.settings, p);
  if (KIWIN) { if (KICH) KICH.postMessage({ type: 'set', patch: p }); renderAi(); renderKiStage() } else changed('ai');
}
const kiSend = debounce(() => {
  if (KIWIN || !KICH || !S.settings) return;
  KICH.postMessage({ type: 'state', settings: S.settings, image: S.image ? { token: S.image.token, name: S.image.name } : null,
    audio: S.audio ? { token: S.audio.token, name: S.audio.name } : null, theme: S.theme });
}, 150);
if (KICH) KICH.onmessage = e => {
  const d = e.data || {};
  if (!KIWIN) {
    if (d.type === 'hello') kiSend();
    else if (d.type === 'set') { Object.assign(S.settings, d.patch || {}); KI_RX = true; changed('ai'); KI_RX = false; aiInfo() }
    else if (d.type === 'mark') { S.settings.ai = true; MK.target = 'ai'; MK.mode = 'mask'; foldToggle($('#markBar'), true); changed('ai'); $('#markBar').scrollIntoView({ behavior: 'smooth', block: 'center' }); toast('Male im Vorschaubild die Fläche, die sich bewegen soll (Umschalter „🎬 KI-Video“).') }
  } else if (d.type === 'state') {
    S.settings = Object.assign({}, d.settings); S.image = d.image; S.audio = d.audio;
    if (d.theme && d.theme !== S.theme) applyTheme(d.theme);
    renderAi(); renderKiStage(); aiInfo();
  }
};
const dur = sec => { sec = Math.max(0, Math.round(sec)); if (sec < 90) return `${sec} s`; const h = Math.floor(sec / 3600), m = Math.round((sec % 3600) / 60); return h ? `${h} Std.${m ? ' ' + m + ' Min.' : ''}` : `${m} Min.` };
function openAiCard() {
  if (NATIVE_KI()) { window.pywebview.api.ki_open().then(ok => { if (!ok) openAiCardHere() }).catch(openAiCardHere); kiSend(); return }
  openAiCardHere();
}
function openAiCardHere() { const c = $('#aiCard'); foldToggle(c, true); c.scrollIntoView({ behavior: 'smooth', block: 'start' }); refreshAi() }
function kiBoot() {                     // Start im eigenen KI-Video-Fenster
  document.body.classList.add('kiwin');
  clearTimeout(splashTimer); const sp = $('#splash'); if (sp) sp.remove();
  document.title = 'ffmpeg_encode Studio – KI-Video';
  const card = $('#aiCard'); $('#kiLeft').append(card); foldToggle(card, true);
  $('#kiRoot').hidden = false;
  const b = $('.brand b'); if (b) b.innerHTML = '🎬 KI-Video <span class="ai-mark">AI</span>';
  const back = el('button', { type: 'button', class: 'btn ghost', id: 'kiBack', title: 'Zum Hauptfenster', onclick: () => { try { window.pywebview.api.show_main() } catch (_) {} } }, el('span', { class: 'lbl' }, '↩ Hauptfenster'));
  const nav = $('.top-actions'); nav.insertBefore(back, nav.firstChild);
  if (KICH) KICH.postMessage({ type: 'hello' });
  setTimeout(() => { if (KICH && !S.image) KICH.postMessage({ type: 'hello' }) }, 1500);
}
async function refreshAi() {
  try { AI.st = await api('/api/ai/status') } catch (_) { return }
  const r = (AI.st.running || [])[0];
  if (r && !AI.job) { AI.job = r.id; AI.jobKind = r.kind; $('#aiProg').hidden = false; aiPollJob() }   // läuft schon (z. B. Fenster neu geöffnet)
  renderAi(); aiInfo();
}
async function aiInfoNow() {
  if (!S.image || !AI.st || !AI.st.ready) { AI.info = null; renderAi(); return }
  try {
    AI.info = await api('/api/ai/info', Object.assign({ image: S.image.token, audio: S.audio && S.audio.token, settings: S.settings }, aiFixArgs()));
    const s = S.settings;
    if (s.aiClip && AI.info.clip_ok === false) aiPatch({ aiClip: '' });   // anderes Bild/Format -> altes KI-Video passt nicht mehr
    if (AI.seed && !AI.info.have.variants.some(v => v.seed === AI.seed)) AI.seed = 0;
    if (!AI.seed && s.aiClip) AI.seed = +(s.aiClip.match(/seed-(\d+)/) || [])[1] || 0;
  } catch (_) { AI.info = null }
  renderAi();
}
const aiInfo = debounce(aiInfoNow, 400);
aiInfo.now = aiInfoNow;
function renderAi() {
  const s = S.settings; if (!s) return;
  $('#aiSwitch').setAttribute('aria-checked', String(!!s.ai));
  const st = AI.st, pkg = $('#aiPkg'); pkg.textContent = '';
  const ready = !!(st && st.ready);
  const compact = NATIVE_KI();          // Hauptfenster mit eigenem KI-Fenster: nur Kurzfassung + Öffnen-Knopf
  $('#aiMain').hidden = !ready || compact;
  $('#aiOpenRow').hidden = !compact;
  if (st && !ready) {
    const d = st.download || {}, box = el('div', { class: 'box' });
    if (!st.tool) box.append(el('p', {}, 'Der KI-Motor fehlt in dieser Installation. Bitte das Programm mit dem neuesten Installer neu installieren.'));
    else if (d.state === 'running') {
      box.append(el('p', {}, el('b', {}, `KI-Video-Paket wird geladen … ${d.percent || 0} %`), ` (${String(d.done_gb || 0).replace('.', ',')} von ${String(d.total_gb || st.need_gb).replace('.', ',')} GB)`),
        el('div', { class: 'ai-prog', style: 'padding:0' }, el('div', { class: 'bar' }, el('i', { style: `width:${d.percent || 0}%` }))),
        el('p', { style: 'margin-top:8px' }, 'Du kannst währenddessen normal weiterarbeiten. Wird das Programm geschlossen, macht der Download beim nächsten Mal dort weiter.'));
      aiPollStatus();
    } else {
      box.append(el('p', {}, el('b', {}, 'Einmaliger Zusatz-Download: ca. ' + String(st.need_gb).replace('.', ',') + ' GB'), ` (KI-Modell Wan 2.2, Apache-2.0-Lizenz). Freier Speicher: ${String(st.free_gb).replace('.', ',')} GB.`),
        el('p', {}, 'Danach läuft alles offline auf deinem PC – nichts wird hochgeladen.'));
      if (d.state === 'error') box.append(el('p', { style: 'color:var(--bad)' }, d.error));
      box.append(el('div', { class: 'acts' }, el('button', { type: 'button', class: 'btn glow', onclick: aiDownload, disabled: st.free_gb < st.need_gb + 1 }, d.state === 'error' ? 'Erneut versuchen' : 'KI-Video-Paket laden')));
      if (st.free_gb < st.need_gb + 1) box.append(el('p', { style: 'color:var(--bad);margin-top:8px' }, 'Nicht genug freier Speicher auf dem Laufwerk mit dem Einstellungsordner.'));
    }
    if (st.devices && st.devices.length) box.append(el('div', { class: 'dev' }, 'Rechnet mit: ' + aiDevText(st.devices)));
    pkg.append(box);
  }
  if (!ready || compact) { if (compact && s.aiClip) aiResultBox(s); else $('#aiResult').hidden = true; return }
  // Bewegungen
  const mb = $('#aiMotions');
  if (!mb.childElementCount) st.motions.forEach(([id, n]) => mb.append(el('button', { type: 'button', 'data-v': id, onclick: () => aiSet('aiMotion', id) }, n)));
  const sc = (AI.info && AI.info.learned && AI.info.learned.scores) || {};
  $$('#aiMotions button').forEach(b => {
    b.setAttribute('aria-pressed', String(b.dataset.v === s.aiMotion));
    const n = (st.motions.find(m => m[0] === b.dataset.v) || [])[1] || '';
    b.textContent = n + (sc[b.dataset.v] ? ' · ' + String(sc[b.dataset.v]).replace('.', ',') + ' ★' : '');
    b.title = sc[b.dataset.v] ? 'Deine Durchschnittsnote für diese Bewegung' : '';
  });
  if (document.activeElement !== $('#aiDesc')) $('#aiDesc').value = s.aiText || '';
  $$('#aiWhere button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.v === s.aiArea || (b.dataset.v === 'full' && s.aiArea !== 'mask'))));
  $$('#aiQual button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.v === s.aiQual)));
  $$('#aiLens button').forEach(b => b.setAttribute('aria-pressed', String(+b.dataset.v === s.aiLen)));
  $('#aiWhereHint').textContent = s.aiArea === 'mask' ? 'Die Fläche malst du im Vorschaubild oben („Markieren“ → 🎬 KI-Video).' : 'Das ganze Bild bewegt sich.';
  $('#aiQualHint').textContent = s.aiQual === 'good' ? '1280 × 704 – schöner, braucht aber etwa 3–4× so lange.' : '832 × 480 – deutlich schneller, wird auf dein Videoformat hochgerechnet.';
  const inf = AI.info, run = !!AI.job;
  const est = inf && inf.estimate, ev = inf && inf.estimate_variants;
  $('#aiLenHint').textContent = !inf ? '' : `${inf.length >= 60 ? dur(inf.length) : Math.round(inf.length) + ' s'} = ${est.segments} Stücke · Rechenzeit ca. ${dur(est.seconds)}` + (est.measured ? '' : ' (grobe Schätzung – wird nach der ersten Variante genauer)');
  // Schritt 1: Varianten
  $('#aiVarBtn').disabled = run || !S.image;
  $('#aiVarHint').textContent = !S.image ? 'Zuerst ein Bild hineinziehen.' : ev ? `Erzeugt die ersten Sekunden in 3 Varianten · ca. ${dur(ev.seconds * 3)}` : '';
  const vb = $('#aiVars'); vb.textContent = '';
  for (const v of (inf && inf.have.variants) || []) {
    const sel = v.seed === AI.seed;
    const vid = el('video', { src: '/api/ai/video?p=' + encodeURIComponent(v.video), muted: true, loop: true, playsinline: true, preload: 'metadata' });
    vid.muted = true; vid.addEventListener('mouseenter', () => vid.play().catch(() => {})); vid.addEventListener('mouseleave', () => vid.pause());
    if (sel) setTimeout(() => vid.play().catch(() => {}), 50);
    vb.append(el('div', { class: 'ai-var' + (sel ? ' sel' : ''), onclick: () => { AI.seed = v.seed; AI.view = v.video; renderAi() } }, vid,
      inf.have.tip === v.seed ? el('b', { class: 'ai-tip', title: 'Die KI hält diese Variante für die beste (Schärfe, wenig Flackern, nah am Original) – lernt aus deinen Sternen' }, '🤖 KI-Tipp') : null,
      el('span', {}, sel ? '✓ Ausgewählt' : 'Diese nehmen', el('small', {}, '#' + v.seed + (v.score ? ' · Note ' + String(v.score).replace('.', ',') : '')))));
  }
  // Schritt 2: volle Länge
  const have = inf && inf.have.clips.find(c => c.seed === AI.seed && (c.seconds === (s.aiLen || Math.round(inf.length))));
  const part = inf && inf.have.partial.find(p => p.seed === AI.seed);
  const inUse = have && s.aiClip === have.clip;
  $('#aiFullBtn').disabled = run || !AI.seed || inUse;
  $('#aiFullBtn').textContent = inUse ? '✓ Wird verwendet' : have ? 'Schon fertig – verwenden' : part ? 'Weiterrechnen (angefangen)' : 'Volle Länge berechnen';
  $('#aiFullHint').textContent = !AI.seed ? 'Zuerst eine Variante auswählen.' : inUse ? 'Andere Länge oder Variante wählen, um ein neues KI-Video zu berechnen.' : have ? 'Für diese Länge gibt es schon ein fertiges KI-Video.'
    : est ? `ca. ${dur(est.seconds)} · fertige Stücke bleiben gespeichert – du kannst abbrechen und später weitermachen.` : '';
  // Upscaler
  $('#aiUpSw').setAttribute('aria-checked', String(!!s.aiUp));
  $('#aiUpSw').disabled = inf && !inf.upscaler;
  $('#aiUpHint').textContent = inf && !inf.upscaler ? 'Nicht verfügbar in dieser Installation.' : 'Rechnet das fertige KI-Video mit einer zweiten KI scharf auf Full HD (1920 × 1080) hoch.';
  aiResultBox(s); renderFb(); renderKiStage();
}
function aiResultBox(s) {
  const res = $('#aiResult');
  res.hidden = !s.aiClip; res.textContent = '';
  if (s.aiClip) {
    const sec = (s.aiClip.match(/ki-video-(\d+)s/) || [])[1];
    res.append(el('video', { src: '/api/ai/video?p=' + encodeURIComponent(s.aiClip), muted: true, loop: true, autoplay: true, playsinline: true }),
      el('div', { class: 'tx' }, el('b', {}, `✓ KI-Video fertig${sec ? ' (' + dur(+sec) + ')' : ''}`),
        el('small', {}, s.ai ? 'Wird beim Umwandeln eingesetzt' + (s.aiArea === 'mask' ? ' – nur in der markierten Fläche.' : '.') + ' Ist der Song länger, wird es nahtlos wiederholt.' : 'Schalter oben einschalten, damit es im Video verwendet wird.')),
      el('button', { type: 'button', class: 'btn small', onclick: () => aiPatch({ aiClip: '' }) }, 'Nicht verwenden'));
    res.querySelector('video').muted = true;
    res.querySelector('.tx b').textContent += /-hd\.mp4$/.test(s.aiClip) ? ' · Full HD' : '';
  }
}
/* ---------- Bewertung (Feedback) – die KI lernt daraus ---------- */
const AI_TAGS = [['perfect', 'Perfekt'], ['strong', 'Bewegung zu stark'], ['weak', 'Bewegung zu schwach'], ['face', 'Gesicht verzerrt'], ['flicker', 'Flackert / unruhig'], ['blur', 'Unscharf'], ['color', 'Farben falsch']];
function aiFixArgs() { return AI.fix ? { fix_tags: AI.fix.tags, fix_text: AI.fix.text } : {} }
function aiCurrent() {                 // was gerade angezeigt/bewertet wird: fertiges KI-Video oder ausgewählte Variante
  const s = S.settings, inf = AI.info;
  if (AI.view && (AI.view === s.aiClip || (inf && inf.have.variants.some(v => v.video === AI.view)))) return AI.view;
  if (s.aiClip) return s.aiClip;
  const v = inf && inf.have.variants.find(x => x.seed === AI.seed);
  return v ? v.video : '';
}
function renderFb() {
  const cur = aiCurrent(), box = $('#aiFb');
  box.hidden = !cur;
  if (!cur) return;
  $('#aiFbWhat').textContent = /ki-video/.test(cur) ? 'Fertiges KI-Video' : 'Variante #' + ((cur.match(/seed-(\d+)/) || [])[1] || '');
  const st = $('#aiStars');
  if (!st.childElementCount) for (let i = 1; i <= 5; i++) st.append(el('button', { type: 'button', role: 'radio', 'aria-label': i + ' Sterne', onclick: () => { AI.stars = i; renderFb() } }, '★'));
  $$('#aiStars button').forEach((b, i) => { b.classList.toggle('on', i < AI.stars); b.setAttribute('aria-checked', String(i + 1 === AI.stars)) });
  const tg = $('#aiTags');
  if (!tg.childElementCount) AI_TAGS.forEach(([id, n]) => tg.append(el('button', { type: 'button', 'data-v': id, onclick: () => {
    AI.tags = AI.tags.includes(id) ? AI.tags.filter(t => t !== id) : AI.tags.concat(id);
    if (id === 'perfect') AI.tags = AI.tags.includes('perfect') ? ['perfect'] : AI.tags; else AI.tags = AI.tags.filter(t => t !== 'perfect');
    if (id === 'strong') AI.tags = AI.tags.filter(t => t !== 'weak'); if (id === 'weak') AI.tags = AI.tags.filter(t => t !== 'strong');
    renderFb();
  } }, n)));
  $$('#aiTags button').forEach(b => b.setAttribute('aria-pressed', String(AI.tags.includes(b.dataset.v))));
  $('#aiRedo').disabled = !!AI.job;
  const L = AI.info && AI.info.learned;
  $('#aiLearned').textContent = L && L.n ? `🧠 Aus ${L.n} Bewertung${L.n === 1 ? '' : 'en'} gelernt` + (L.learned_names.length ? ' – gibt jetzt automatisch mit: ' + L.learned_names.join(', ') : '') : '🧠 Deine Bewertungen helfen der KI, beim nächsten Mal besser zu treffen.';
  const fb = $('#aiFixBar'); fb.textContent = '';
  fb.hidden = !AI.fix;
  if (AI.fix) fb.append(el('span', {}, '✏️ Änderungswunsch aktiv: ' + [...AI.fix.tags.map(t => (AI_TAGS.find(x => x[0] === t) || [, t])[1]), AI.fix.text].filter(Boolean).join(' · ')),
    el('button', { type: 'button', class: 'btn tiny', onclick: () => { AI.fix = null; AI.seed = 0; aiInfo() } }, 'Zurück zum Original-Wunsch'));
}
async function aiSendFeedback() {
  if (!AI.stars) { toast('Bitte zuerst Sterne vergeben'); return false }
  try {
    const d = await api('/api/ai/feedback', { motion: S.settings.aiMotion, stars: AI.stars, tags: AI.tags, text: $('#aiFix').value, ref: aiCurrent() });
    if (AI.info) AI.info.learned = d.learned;
    toast('✓ Danke! Die KI merkt sich deine Bewertung');
    return true;
  } catch (e) { toast(e.message, true); return false }
}
$('#aiRate').onclick = async () => { if (await aiSendFeedback()) { AI.stars = 0; AI.tags = []; $('#aiFix').value = ''; renderFb() } };
$('#aiRedo').onclick = async () => {
  const text = $('#aiFix').value.trim(), tags = AI.tags.filter(t => t !== 'perfect');
  if (!text && !tags.length) { toast('Wähle, was nicht passt, oder schreibe, was anders werden soll'); return }
  if (AI.stars) await aiSendFeedback();
  AI.fix = { tags, text }; AI.seed = 0; AI.stars = 0; AI.tags = []; $('#aiFix').value = '';
  await aiInfo.now(); aiStart('variants');
};
$('#aiUpSw').onclick = () => aiPatch({ aiUp: !S.settings.aiUp });
$('#aiOpenWin').onclick = () => { try { window.pywebview.api.ki_open() } catch (_) { openAiCard() } };
/* großer Player im KI-Fenster */
function renderKiStage() {
  if (!KIWIN) return;
  const cur = aiCurrent(), v = $('#kiVideo');
  const src = cur ? '/api/ai/video?p=' + encodeURIComponent(cur) : '';
  if (v.dataset.p !== src) { v.dataset.p = src; if (src) { v.src = src; v.play().catch(() => {}) } else v.removeAttribute('src') }
  $('#kiEmpty').hidden = !!src;
  const s = S.settings || {};
  $('#kiWhat').textContent = !cur ? '' : /ki-video/.test(cur) ? '✓ Fertiges KI-Video' + (/-hd/.test(cur) ? ' · Full HD' : '') : 'Variante #' + ((cur.match(/seed-(\d+)/) || [])[1] || '');
  $('#kiInfo').textContent = S.image ? 'Bild: ' + (S.image.name || '') + (s.aiArea === 'mask' ? ' · nur markierte Fläche' : ' · ganzes Bild') : 'Im Hauptfenster ein Bild hineinziehen.';
}
function aiDevText(devs) {
  const g = devs.filter(d => d.gpu);
  return g.length ? g.map(d => d.desc || d.name).join(' + ') : 'nur Prozessor (sehr langsam – keine passende Grafikkarte gefunden)';
}
function aiSet(k, v) { aiPatch({ [k]: v }); aiInfo() }
$('#aiSwitch').onclick = () => { aiPatch({ ai: !S.settings.ai }); if (S.settings.ai) { refreshAi(); foldToggle($('#aiCard'), true) } };
$$('#aiWhere button').forEach(b => b.onclick = () => {
  const area = b.dataset.v === 'mask' && S.settings.aiMask ? 'mask' : 'full';
  if (KIWIN) {
    aiPatch({ aiArea: area, ai: true });
    if (b.dataset.v === 'mask') { if (KICH) KICH.postMessage({ type: 'mark' }); try { window.pywebview.api.show_main() } catch (_) {} toast('Die Fläche malst du im Hauptfenster im Vorschaubild.') }
    return;
  }
  S.settings.aiArea = area;
  if (b.dataset.v === 'mask') { S.settings.ai = true; MK.target = 'ai'; MK.mode = 'mask'; foldToggle($('#markBar'), true); $('#markBar').scrollIntoView({ behavior: 'smooth', block: 'center' }); if (!S.settings.aiMask) toast('Male jetzt im Vorschaubild die Fläche, die sich bewegen soll.') }
  changed('ai');
});
$$('#aiQual button').forEach(b => b.onclick = () => aiSet('aiQual', b.dataset.v));
$$('#aiLens button').forEach(b => b.onclick = () => aiSet('aiLen', +b.dataset.v));
$('#aiDesc').addEventListener('input', debounce(() => aiSet('aiText', $('#aiDesc').value), 700));
async function aiDownload() {
  try { AI.st = await api('/api/ai/download', {}); renderAi(); aiPollStatus() } catch (e) { toast(e.message, true) }
}
function aiPollStatus() {
  clearTimeout(AI.poll);
  AI.poll = setTimeout(async () => {
    try { AI.st = await api('/api/ai/status') } catch (_) { return }
    renderAi();
    if (AI.st.ready) { toast('✓ KI-Video-Paket ist installiert'); aiInfo() }
  }, 2000);
}
async function aiStart(kind) {
  if (!S.image) { toast('Zuerst ein Bild hineinziehen'); return }
  try {
    const d = await api('/api/ai/start', Object.assign({ kind, image: S.image.token, audio: S.audio && S.audio.token, settings: S.settings, seed: AI.seed }, aiFixArgs()));
    AI.job = d.id; AI.jobKind = kind; $('#aiProg').hidden = false; renderAi(); aiPollJob();
  } catch (e) { toast(e.message, true) }
}
$('#aiVarBtn').onclick = () => aiStart('variants');
$('#aiFullBtn').onclick = () => {
  const inf = AI.info, s = S.settings;
  const have = inf && inf.have.clips.find(c => c.seed === AI.seed && c.seconds === (s.aiLen || Math.round(inf.length)));
  if (have) { aiPatch({ aiClip: have.clip, ai: true }); toast('✓ KI-Video wird verwendet'); return }
  aiStart('full');
};
$('#aiCancel').onclick = () => { if (AI.job) api('/api/ai/cancel', { id: AI.job }).catch(() => {}) };
function aiPollJob() {
  clearTimeout(AI.timer);
  AI.timer = setTimeout(async () => {
    let j; try { j = await api('/api/ai/job/' + AI.job) } catch (_) { AI.job = ''; renderAi(); return }
    $('#aiBar').style.width = (j.percent || 0) + '%';
    $('#aiProgText').textContent = `${j.percent || 0} % · ${j.note || (j.state === 'wartet' ? 'wartet …' : 'läuft …')}` + (j.eta ? ` · noch ca. ${dur(j.eta)}` : '');
    if (j.state === 'läuft' || j.state === 'wartet') { aiPollJob(); return }
    AI.job = ''; $('#aiProg').hidden = true;
    if (j.state === 'fertig' && j.result) {
      if (AI.jobKind === 'variants') { toast('✓ 3 Varianten fertig – wähle die schönste aus'); if (!AI.seed) AI.seed = j.result.variants[Math.max(0, j.result.tip)].seed }
      else { aiPatch({ aiClip: j.result.clip, ai: true }); AI.view = j.result.clip; toast('✓ KI-Video ist fertig und wird beim Umwandeln verwendet') }
    } else if (j.state === 'fehler') ask('KI-Video', j.error || 'Unbekannter Fehler', 'OK');
    aiInfo(); refreshAi();
  }, 1500);
}
refreshAi();

/* ---------- Shorts-Helfer: Länge + beste Stelle (KI) ---------- */
const HL = { id: '', timer: 0, res: null, stopAt: 0, lyrTimer: 0 };
const lenName = v => v < 60 ? v + ' s' : (v % 60 ? (v / 60).toFixed(1).replace('.', ',') : v / 60) + ':00'.slice(v % 60 ? 3 : 0);
function tstr(t) { const m = Math.floor(t / 60), s = t - m * 60; const ss = (Math.round(s * 10) / 10).toFixed(1).replace(/\.0$/, ''); return `${m}:${(s < 10 ? '0' : '') + ss}` }
function renderShort() {
  const s = S.settings, tall = fmtOf(s.fmt)[3], box = $('#shortExt');
  box.hidden = !tall; if (!tall) return;
  const lens = (S.info && S.info.short_lengths) || [15, 30, 45, 60, 90, 120, 180], lb = $('#shortLens');
  if (lb.childElementCount !== lens.length) { lb.textContent = ''; lens.forEach(v => lb.append(el('button', { type: 'button', 'data-v': v, onclick: () => set('shortLen', v) }, v < 60 ? v + ' s' : `${Math.floor(v / 60)}:${String(v % 60).padStart(2, '0')}`))) }
  $$('#shortLens button').forEach(b => b.setAttribute('aria-pressed', String(+b.dataset.v === s.shortLen)));
  const ly = (S.info && S.info.lyrics) || {}, on = !!s.shortLyrics && ly.lib;
  $('#lyrBtn').setAttribute('aria-checked', String(on)); $('#lyrBtn .switch').setAttribute('aria-checked', String(on));
  $('#lyrBtn').disabled = !ly.lib;
  $('#lyrSub').textContent = ly.lib ? 'liest den Gesang mit – findet Refrain und gefühlvolle Zeilen genauer' : 'in diesem Programm nicht verfügbar';
  const dl = $('#lyrDl'); dl.textContent = '';
  dl.hidden = !(on && !ly.model);
  if (on && !ly.model) {
    const d = ly.download || {};
    if (d.state === 'running') dl.append(el('div', { class: 'hl-bar' }, el('i', { style: `width:${d.percent}%` })), el('small', {}, `Songtext-Modell wird geladen … ${d.percent} %`));
    else dl.append(el('small', {}, d.state === 'error' ? d.error : `Einmalig ca. ${ly.mb || 145} MB herunterladen (danach offline).`),
      el('button', { type: 'button', class: 'btn small', onclick: startLyrDownload }, d.state === 'error' ? 'Nochmal versuchen' : 'Jetzt laden'));
  }
  $('#hlBtn').disabled = !S.audio || !!HL.id || (on && !ly.model);
  $('#hlBtn').textContent = S.audio ? `✨ Beste Stelle finden (${s.shortLen < 60 ? s.shortLen + ' s' : Math.floor(s.shortLen / 60) + ':' + String(s.shortLen % 60).padStart(2, '0')})` : 'Zuerst einen Song hineinziehen';
}
$('#lyrBtn').onclick = () => { set('shortLyrics', !S.settings.shortLyrics); refreshLyr() };
async function refreshLyr() { try { S.info.lyrics = await api('/api/lyrics/status'); renderShort() } catch (_) {} }
async function startLyrDownload() {
  try { S.info.lyrics = await api('/api/lyrics/download', {}); renderShort() } catch (e) { toast(e.message, true); return }
  clearInterval(HL.lyrTimer);
  HL.lyrTimer = setInterval(async () => {
    await refreshLyr(); const d = S.info.lyrics.download || {};
    if (d.state !== 'running') { clearInterval(HL.lyrTimer); if (d.state === 'done') toast('✓ Songtext-Modell geladen – ab jetzt offline') }
  }, 700);
}
$('#hlBtn').onclick = async () => {
  if (!S.audio) return;
  const s = S.settings;
  try {
    const d = await api('/api/highlight', { audio: S.audio.token, length: s.shortLen, lyrics: !!s.shortLyrics });
    HL.id = d.id; $('#hlList').textContent = ''; $('#hlNote').hidden = true; $('#hlProg').hidden = false; renderShort();
    clearInterval(HL.timer);
    HL.timer = setInterval(async () => {
      let j; try { j = await api('/api/highlight/' + HL.id) } catch (e) { return }
      $('#hlBar').style.width = j.percent + '%'; $('#hlPhase').textContent = j.phase;
      if (j.state === 'läuft') return;
      clearInterval(HL.timer); HL.id = ''; $('#hlProg').hidden = true; renderShort();
      if (j.state === 'fehler') { toast(j.error, true); return }
      HL.res = j.result; renderHl();
    }, 400);
  } catch (e) { toast(e.message, true) }
};
function renderHl() {
  const r = HL.res, box = $('#hlList'); box.textContent = ''; if (!r) return;
  const note = [r.lyrics ? (r.lines ? `${r.lines} Textzeilen erkannt${r.language ? ' (' + r.language.toUpperCase() + ')' : ''}` : '') : '', `Tempo ca. ${Math.round(r.bpm)} BPM`, r.note].filter(Boolean).join(' · ');
  $('#hlNote').textContent = note; $('#hlNote').hidden = !note;
  const ic = { chorus: '🎵', drop: '⚡', emo: '💗', all: '🎶' };
  r.suggestions.forEach(sg => box.append(el('div', { class: 'hl-card' },
    el('div', { class: 'hl-top' }, el('b', {}, `${ic[sg.kind] || '✨'} ${sg.name}`, sg.fav ? el('span', { class: 'hl-fav', title: 'Die KI hat gelernt, dass du diese Art meistens nimmst' }, '★ Dein Favorit') : null), el('span', { class: 'hl-time' }, `${tstr(sg.start)} – ${tstr(sg.end)}`)),
    el('small', {}, sg.why), sg.lyric ? el('q', {}, sg.lyric) : null,
    el('div', { class: 'hl-acts' },
      el('button', { type: 'button', class: 'btn small', onclick: () => playHl(sg) }, '▶ Anhören'),
      el('button', { type: 'button', class: 'btn small glow', onclick: () => applyHl(sg) }, 'Übernehmen')))));
  box.append(el('div', { class: 'hl-learn' },
    el('small', {}, r.learned ? `🧠 Die KI hat schon aus ${r.learned} deiner Entscheidungen gelernt` : '🧠 Die KI lernt mit: Was du übernimmst, kommt beim nächsten Mal weiter nach vorne'),
    r.text && r.text.length ? el('button', { type: 'button', class: 'btn tiny', onclick: openLyrEdit }, r.fixed ? '✏️ Text bearbeiten' : '✏️ Text korrigieren') : null));
}
function openLyrEdit() {
  const box = $('#lyrLines'); box.textContent = '';
  for (const l of (HL.res && HL.res.text) || [])
    box.append(el('div', { class: 'lyr-row' }, el('small', {}, tstr(l.start)), el('input', { type: 'text', value: l.text, 'data-s': l.start, 'data-e': l.end, spellcheck: 'false' })));
  $('#lyrDlg').showModal();
}
$('#lyrSave').onclick = async () => {
  const lines = $$('#lyrLines input').map(i => ({ start: +i.dataset.s, end: +i.dataset.e, text: i.value.trim() })).filter(l => l.text);
  try {
    const d = await api('/api/learn/lyrics', { audio: S.audio.token, lines });
    $('#lyrDlg').close();
    toast(d.learned.length ? `🧠 Gelernt: ${d.learned.slice(0, 6).join(', ')}${d.learned.length > 6 ? ' …' : ''}` : '✓ Text gespeichert');
    $('#hlBtn').click();
  } catch (e) { toast(e.message, true) }
};
function playHl(sg) {
  if (!S.audio) return;
  aud.currentTime = sg.start; HL.stopAt = sg.end; aud.play().catch(() => {});
}
setTimeout(() => {                                   // der Audio-Player wird weiter unten angelegt
  aud.addEventListener('timeupdate', () => { if (HL.stopAt && aud.currentTime >= HL.stopAt) { aud.pause(); HL.stopAt = 0 } });
  aud.addEventListener('pause', () => { if (HL.stopAt && aud.currentTime < HL.stopAt - 0.3) HL.stopAt = 0 });
}, 0);
function applyHl(sg) {
  const s = S.settings;
  if (sg.kind !== 'all') { api('/api/learn/hl', { kind: sg.kind, feat: sg.feat }).catch(() => {}); HL.applied = { start: sg.start, end: sg.end } }
  s.start = tstr(sg.start); s.end = tstr(sg.end);
  s.fadeIn = Math.min(s.fadeIn, 0.5); s.fadeOut = Math.min(Math.max(s.fadeOut, 1), 1.5);
  $('#tStart').value = s.start; $('#tEnd').value = s.end;
  changed('time'); toast(`✓ ${sg.name} übernommen: ${s.start} – ${s.end} (kurz ein-/ausgeblendet)`);
}

/* ---------- Vorlagen-Menü in der Kopfzeile ---------- */
function tplMenu(open) {
  const m = $('#tplMenu'), o = open === undefined ? m.hidden : open;
  m.hidden = !o; $('#tplBtn').setAttribute('aria-expanded', String(o));
  if (o) renderPresets();
}
$('#tplBtn').onclick = e => { e.stopPropagation(); tplMenu() };
document.addEventListener('click', e => { if (!$('#tplMenu').hidden && !e.target.closest('.tpl-wrap')) tplMenu(false) });
document.addEventListener('keydown', e => { if (e.key === 'Escape' && !$('#tplMenu').hidden) { tplMenu(false); $('#tplBtn').focus() } });
$('#tplMenu').addEventListener('click', e => { if (e.target.closest('button')) setTimeout(() => tplMenu(false), 0) });

/* ---------- Einklappbare Fenster (beim Start alle zu) ---------- */
const FOLD_SUM = {
  fmt: s => fmtOf(s.fmt)[1],
  fit: s => (FITS.find(f => f[0] === s.fit) || FITS[0])[1],
  viz: s => !s.viz ? 'Aus' : s.vizAi ? '✨ KI-Welle · ' + (AI_WAVES.find(w => w[0] === s.vizAiWave) || AI_WAVES[0])[1] : (VSTYLES.find(x => x[0] === s.vizStyle) || VSTYLES[0])[2],
  fx: s => '',
  ai: s => !s.ai ? 'Aus' : s.aiClip ? '✓ fertig · ' + (s.aiArea === 'mask' ? 'Fläche' : 'ganzes Bild') : 'An – noch nicht berechnet',
  time: s => {
    if (!S.audio) return 'Noch kein Song';
    const n = ((S.meta && S.meta.notes) || []).length;
    return `${s.start || '0:00'} – ${s.end || 'Song-Ende'} · Länge ${$('#durOut').textContent}` + (n ? ' · ⚠ Hinweis' : '');
  },
  enc: s => encLabel(s.enc) + ' · ' + (($('#quality').selectedOptions[0] || {}).textContent || '').split(' ')[0],
  fade: s => {
    const opt = id => { const o = $(`#${id}`).selectedOptions[0]; return o ? o.textContent : '' };
    return (s.fadeIn || s.fadeOut) ? `${secDe(s.fadeIn)} / ${secDe(s.fadeOut)} · ${opt('transIn')}` : 'Aus';
  }
};
function foldToggle(box, open) {
  const head = box.querySelector('.fold-head'), o = open === undefined ? box.classList.contains('folded') : open;
  box.classList.toggle('folded', !o); head.setAttribute('aria-expanded', String(o));
  if (o && box.id === 'markBar') renderMark();
  if (o) requestAnimationFrame(() => { drawWave(); drawMarkSvg() });
}
function foldHead(box, head) {
  head.classList.add('fold-head');
  if (!head.hasAttribute('role')) { head.setAttribute('role', 'button'); head.tabIndex = 0; head.setAttribute('aria-expanded', 'false') }
  head.addEventListener('click', e => { if (e.target.closest('button,input,select,a,label')) return; foldToggle(box) });
  head.addEventListener('keydown', e => { if ((e.key === 'Enter' || e.key === ' ') && e.target === head) { e.preventDefault(); foldToggle(box) } });
}
function setupFolds() {
  $$('.card[data-fold]').forEach(card => {
    const head = card.firstElementChild;
    const sum = el('span', { class: 'fold-sum', 'data-sum': card.dataset.fold }), chev = el('i', { class: 'chev', 'aria-hidden': 'true' });
    const sw = head.querySelector('.switch');
    if (sw) head.insertBefore(sum, sw); else head.append(sum);
    head.append(chev);
    card.classList.add('folded'); foldHead(card, head);
  });
  foldHead($('#markBar'), $('#mkHead'));
}
function foldSummaries() {
  if (!S.settings) return;
  $$('.fold-sum[data-sum]').forEach(x => { x.textContent = FOLD_SUM[x.dataset.sum](S.settings) });
}
setupFolds();

/* ---------- Änderungen ---------- */
const saveSettings = debounce(() => api('/api/config', { settings: S.settings }).catch(() => {}), 600);
function changed(what) {
  const s = S.settings;
  renderFormats(); renderFits(); renderFps(); renderEnc(); renderSeg('#colorSeg', 'color'); renderViz(); renderFx(); renderShort(); renderAi(); foldSummaries(); kiSend();
  if (what === 'image' || what === 'fmt' || what === 'fit' || what === 'audio') aiInfo();
  $('#fadeIn').value = s.fadeIn; $('#fadeOut').value = s.fadeOut;
  $('#fiVal').textContent = secDe(s.fadeIn); $('#foVal').textContent = secDe(s.fadeOut);
  $('#lgIn').textContent = secDe(s.fadeIn); $('#lgOut').textContent = secDe(s.fadeOut);
  $('#target').value = s.target; $('#quality').value = s.quality;
  $('#transIn').value = s.transIn; $('#transOut').value = s.transOut;
  if (document.activeElement !== $('#tStart')) $('#tStart').value = s.start === '0:00' ? '' : s.start;
  if (document.activeElement !== $('#tEnd')) $('#tEnd').value = s.end;
  const f = fmtOf(s.fmt);
  $('#resChip').textContent = f[2].split(' · ')[0];
  $('#fpsChip').textContent = s.fps + ' fps';
  $('#kindChip').textContent = f[3] ? 'Shorts · 9:16' : 'Video · 16:9';
  $('#frame').classList.toggle('tall', f[3]);
  if (what === 'fmt' || what === 'fit' || what === 'image') refreshStill();
  refreshCommand();
  if (what) saveSettings();
}

/* ---------- Befehl + Länge (vom Programm berechnet) ---------- */
const refreshCommand = debounce(async () => {
  try {
    const d = await api('/api/command', { settings: S.settings, audio: S.audio && S.audio.token, image: S.image && S.image.token, outname: S.outEdited ? $('#outName').value : '' });
    S.meta = d.meta; $('#cmdText').textContent = d.command;
    if (!S.outEdited) { $('#outName').value = d.outname; S.autoName = d.outname }
    timeline(); renderNotes(); updateGo();
  } catch (e) { /* Programm beendet? */ }
}, 120);

function renderNotes() {
  const box = $('#notes'); box.textContent = '';
  const notes = (S.meta && S.meta.notes) || [];
  const st = toSec($('#tStart').value), en = toSec($('#tEnd').value);
  if (Number.isNaN(st) || Number.isNaN(en)) notes.unshift('Bitte die Zeit so eingeben: 1:23 (Minuten:Sekunden) oder 83 (Sekunden).');
  for (const n of notes) box.append(el('div', { class: 'note' }, el('span', { html: ICON.warn }), el('span', {}, n)));
  $('#durOut').textContent = S.audio && S.meta ? mmss(S.meta.duration) : '0:00';
  foldSummaries();
}
$('#tStart').addEventListener('input', debounce(e => { S.settings.start = e.target.value.trim() || '0:00'; changed('time') }, 350));
$('#tEnd').addEventListener('input', debounce(e => { S.settings.end = e.target.value.trim(); changed('time') }, 350));
$('#resetTime').onclick = () => { S.settings.start = '0:00'; S.settings.end = ''; $('#tStart').value = ''; $('#tEnd').value = ''; changed('time') };
$('#outName').addEventListener('input', () => { S.outEdited = !!$('#outName').value.trim() && $('#outName').value !== S.autoName; refreshCommand() });

/* ---------- Vorschau-Bild (echtes FFmpeg-Ergebnis in klein) ---------- */
let stillSeq = 0;
const refreshStill = debounce(async () => {
  const img = $('#stillImg');
  if (!S.image) { img.hidden = true; $('#frameEmpty').hidden = false; return }
  const my = ++stillSeq; $('#stillBusy').hidden = false;
  try {
    const d = await api('/api/still', { settings: S.settings, image: S.image.token });
    if (my !== stillSeq) return;
    await new Promise(res => { img.onload = res; img.onerror = res; img.src = d.url + '?t=' + Date.now() });
    img.hidden = false; $('#frameEmpty').hidden = true;
  } catch (e) { toast('Vorschau: ' + e.message, true) }
  finally { if (my === stillSeq) $('#stillBusy').hidden = true }
}, 150);

/* ---------- Zeitleiste ---------- */
function timeline() {
  const total = audioDur(), has = !!S.audio;
  $('#tlEmpty').hidden = has; $('#wave').style.opacity = has ? 1 : 0;
  ['#dimL', '#dimR', '#tlIn', '#tlOut'].forEach(s => $(s).style.display = has ? '' : 'none');
  const tk = $('#ticks'); tk.textContent = '';
  if (!has || !total || !S.meta) return;
  const start = S.meta.start, dur = S.meta.duration, pct = s => Math.min(100, Math.max(0, s / total * 100));
  $('#dimL').style.width = pct(start) + '%';
  $('#dimR').style.width = (100 - pct(start + dur)) + '%';
  const vis = s => s > 0 ? Math.max(pct(s), 1.2) : 0;
  $('#tlIn').style.left = pct(start) + '%'; $('#tlIn').style.width = vis(S.meta.fadeIn) + '%';
  $('#tlIn').style.display = S.meta.fadeIn > 0 ? '' : 'none';
  $('#tlOut').style.left = (pct(start + dur) - vis(S.meta.fadeOut)) + '%'; $('#tlOut').style.width = vis(S.meta.fadeOut) + '%';
  $('#tlOut').style.display = S.meta.fadeOut > 0 ? '' : 'none';
  for (let i = 0; i <= 4; i++) tk.append(el('span', {}, mmss(total * i / 4)));
  $('#timeChip').textContent = `${mmss(Math.max(0, aud.currentTime - start))} / ${mmss(dur)}`;
}
async function loadWave() {
  S.wave = null; drawWave();
  if (!S.audio || S.audio.size > 400e6) return;
  try {
    const buf = await (await fetch('/api/file/' + S.audio.token, { headers: { 'X-Studio': TOKEN } })).arrayBuffer();
    const ctx = new (window.OfflineAudioContext || window.webkitOfflineAudioContext)(1, 2, 22050);
    const ab = await ctx.decodeAudioData(buf);
    const ch = ab.getChannelData(0), n = 900, step = Math.max(1, Math.floor(ch.length / n)), peaks = new Float32Array(n);
    for (let i = 0; i < n; i++) { let m = 0; for (let j = i * step, e = Math.min(ch.length, j + step); j < e; j += 4) { const v = Math.abs(ch[j]); if (v > m) m = v } peaks[i] = m }
    const max = Math.max(...peaks) || 1; S.wave = peaks.map(v => v / max); drawWave();
  } catch (_) { S.wave = 'fake'; drawWave() }
}
function drawWave() {
  const c = $('#wave'); if (!c) return;
  const r = c.getBoundingClientRect(), dpr = devicePixelRatio || 1;
  c.width = Math.max(1, r.width * dpr); c.height = Math.max(1, r.height * dpr);
  const g = c.getContext('2d'); g.clearRect(0, 0, c.width, c.height);
  if (!S.audio) return;
  const [a, b] = themeColors(), grad = g.createLinearGradient(0, 0, c.width, 0); grad.addColorStop(0, a); grad.addColorStop(1, b);
  g.fillStyle = grad;
  const bars = Math.floor(r.width / 4), w = c.width / bars, mid = c.height / 2;
  for (let i = 0; i < bars; i++) {
    let v;
    if (S.wave && S.wave !== 'fake') { const k = Math.floor(i / bars * S.wave.length); v = S.wave[k] } else v = Math.abs(Math.sin(i * 1.7) * .55 + Math.sin(i * .31) * .45);
    const h = Math.max(2 * dpr, v * (c.height - 16 * dpr));
    g.fillRect(i * w + dpr, mid - h / 2, Math.max(1, w - 2 * dpr), h);
  }
}
addEventListener('resize', debounce(drawWave, 100));

/* ---------- Anhören ---------- */
const aud = $('#audio');
$('#playBtn').onclick = () => {
  if (!S.audio) return;
  if (aud.paused) {
    const st = (S.meta && S.meta.start) || 0, en = st + ((S.meta && S.meta.duration) || 0);
    if (aud.currentTime < st || aud.currentTime >= en - .2) aud.currentTime = st;
    liveAudio(); if (LIVE.ctx && LIVE.ctx.state === 'suspended') LIVE.ctx.resume();
    aud.play().catch(() => toast('Abspielen nicht möglich', true));
  } else aud.pause();
};
aud.onplay = aud.onpause = () => { $('#playBtn').innerHTML = aud.paused ? ICON.play : ICON.pause; $('#playBtn').setAttribute('aria-label', aud.paused ? 'Song anhören' : 'Pause') };
aud.ontimeupdate = () => {
  const total = audioDur() || aud.duration || 0; if (!total) return;
  $('#tNow').textContent = mmss(aud.currentTime);
  if (document.activeElement !== $('#seek')) $('#seek').value = Math.round(aud.currentTime / total * 1000);
  const head = $('#tlHead'); head.style.display = 'block'; head.style.left = (aud.currentTime / total * 100) + '%';
  if (!S.meta) return;
  const rel = aud.currentTime - S.meta.start, d = S.meta.duration, s = S.settings;
  $('#timeChip').textContent = `${mmss(Math.max(0, rel))} / ${mmss(d)}`;
  // Fades in der Vorschau nachspielen
  let veil = 0;
  if (s.target !== 'a') {
    if (S.meta.fadeIn > 0 && rel < S.meta.fadeIn) veil = 1 - Math.max(rel, 0) / S.meta.fadeIn;
    if (S.meta.fadeOut > 0 && rel > d - S.meta.fadeOut) veil = Math.max(veil, (rel - (d - S.meta.fadeOut)) / S.meta.fadeOut);
    if (rel < 0 || rel > d) veil = 1;
  }
  const v = $('#fadeVeil'); v.style.background = s.color === 'white' ? '#fff' : '#000'; v.style.opacity = aud.paused ? 0 : Math.min(1, veil);
  let vol = 1;
  if (s.target !== 'v') {
    if (S.meta.fadeIn > 0 && rel < S.meta.fadeIn) vol = Math.max(rel, 0) / S.meta.fadeIn;
    if (S.meta.fadeOut > 0 && rel > d - S.meta.fadeOut) vol = Math.min(vol, Math.max(0, d - rel) / S.meta.fadeOut);
  }
  aud.volume = Math.min(1, Math.max(0, vol));
  if (rel >= d && !aud.paused) { aud.pause(); $('#fadeVeil').style.opacity = 0 }
};
aud.onloadedmetadata = () => { $('#tDur').textContent = mmss(audioDur() || aud.duration) };
$('#seek').oninput = e => { const total = audioDur() || aud.duration || 0; aud.currentTime = e.target.value / 1000 * total };
$('#timeline').onclick = e => { if (!S.audio) return; const r = e.currentTarget.getBoundingClientRect(); aud.currentTime = (e.clientX - r.left) / r.width * (audioDur() || aud.duration || 0); aud.ontimeupdate() };

/* ---------- Dateien ---------- */
const AUDIO_EXT = /\.(mp3|wav|flac|m4a|aac|ogg|opus|wma|aiff?)$/i, IMG_EXT = /\.(jpe?g|png|webp|bmp|gif|tiff?|heic|avif)$/i;
function guessKind(f) { if ((f.type || '').startsWith('audio/') || AUDIO_EXT.test(f.name)) return 'audio'; if ((f.type || '').startsWith('image/') || IMG_EXT.test(f.name)) return 'image'; return '' }
function addFiles(list) {
  const files = [...list]; if (!files.length) return;
  const proj = files.find(f => /\.fesproj$/i.test(f.name));
  if (proj) { openProjectFile(proj); return }
  let a = files.find(f => guessKind(f) === 'audio'), i = files.find(f => guessKind(f) === 'image');
  const rest = files.filter(f => !guessKind(f));
  if (!a && !i && rest.length) { stage(rest[0], ''); return }
  if (a) stage(a, 'audio'); if (i) stage(i, 'image');
  if (files.length > (a ? 1 : 0) + (i ? 1 : 0)) toast('Es werden nur ein Song und ein Bild verwendet.');
}
const UPLOADS = {};
function stage(file, kind) {
  const key = kind || 'x'; UPLOADS[key] = { name: file.name, pct: 0, kind: kind || 'audio' }; drawFiles();
  const x = new XMLHttpRequest();
  x.open('POST', '/api/stage?name=' + encodeURIComponent(file.name) + '&kind=' + kind);
  x.setRequestHeader('X-Studio', TOKEN);
  x.upload.onprogress = e => { if (e.lengthComputable) { UPLOADS[key].pct = e.loaded / e.total * 100; const b = $(`[data-up="${key}"] .bar i`); if (b) b.style.width = UPLOADS[key].pct + '%' } };
  x.onload = () => {
    delete UPLOADS[key];
    let d = {}; try { d = JSON.parse(x.responseText) } catch (_) {}
    if (x.status !== 200) { toast(d.error || 'Datei konnte nicht geladen werden', true); drawFiles(); return }
    const old = S[d.kind]; if (old) api('/api/unstage', { token: old.token }).catch(() => {});
    adopt(d);
    toast('✓ ' + (d.kind === 'audio' ? 'Song' : 'Bild') + ' geladen: ' + d.name);
  };
  x.onerror = () => { delete UPLOADS[key]; drawFiles(); toast('Das Programm antwortet nicht', true) };
  x.send(file);
}
function adopt(d, quiet) {
  S[d.kind] = d;
  if (d.kind === 'audio') { aud.src = '/api/file/' + d.token; $('#playBtn').disabled = false; $('#seek').disabled = false; $('#tDur').textContent = mmss(d.info.duration); S.outEdited = false; loadWave() }
  drawFiles(); if (!quiet) changed(d.kind); else if (d.kind === 'image') refreshStill();
  if (d.kind === 'image' && !quiet) offerStyle();
}
function drawFiles() {
  const box = $('#files'); box.textContent = '';
  for (const kind of ['audio', 'image']) {
    const f = S[kind], up = Object.entries(UPLOADS).find(([k, u]) => k === kind || (k === 'x' && kind === 'audio'));
    if (up) {
      box.append(el('div', { class: 'fcard', 'data-up': up[0] }, el('div', { class: 'thumb', html: kind === 'audio' ? ICON.music : ICON.image }),
        el('div', {}, el('b', {}, up[1].name), el('small', {}, 'Wird geladen …'), el('div', { class: 'bar' }, el('i', { style: `width:${up[1].pct}%` }))), el('span')));
    } else if (f) {
      const i = f.info, sub = kind === 'audio'
        ? [mmss(i.duration), i.bitrate ? Math.round(i.bitrate / 1000) + ' kbps' : '', i.sample_rate ? (i.sample_rate / 1000).toString().replace('.', ',') + ' kHz' : '', (i.acodec || '').toUpperCase()].filter(Boolean).join(' · ')
        : [i.width && i.height ? `${i.width} × ${i.height}` : '', (i.vcodec || '').toUpperCase(), size(f.size)].filter(Boolean).join(' · ');
      const warn = kind === 'image' && i.width && i.height && Math.max(i.width, i.height) < 1920 ? ' · klein für 4K' : '';
      box.append(el('div', { class: 'fcard' },
        el('div', { class: 'thumb' }, kind === 'image' ? el('img', { src: '/api/preview/' + f.token, alt: '' }) : el('span', { html: ICON.music })),
        el('div', {}, el('b', { title: f.name }, f.name), el('small', {}, sub + warn)),
        el('button', { type: 'button', class: 'x', 'aria-label': (kind === 'audio' ? 'Song' : 'Bild') + ' entfernen', html: ICON.x, onclick: () => removeFile(kind) })));
    } else {
      box.append(el('div', { class: 'fcard ph' }, el('div', { class: 'thumb', html: kind === 'audio' ? ICON.music : ICON.image }),
        el('div', {}, el('b', {}, kind === 'audio' ? 'Noch kein Song' : 'Noch kein Bild'), el('small', {}, kind === 'audio' ? 'MP3, WAV, FLAC, M4A …' : 'JPG, PNG, WEBP – am besten 3840 × 2160 oder größer')), el('span')));
    }
  }
}
function removeFile(kind) {
  const f = S[kind]; if (!f) return;
  api('/api/unstage', { token: f.token }).catch(() => {}); S[kind] = null;
  if (kind === 'audio') { aud.pause(); aud.removeAttribute('src'); aud.load(); $('#playBtn').disabled = true; $('#seek').disabled = true; $('#tlHead').style.display = 'none'; S.wave = null; drawWave(); $('#tNow').textContent = '0:00'; $('#tDur').textContent = '0:00' }
  drawFiles(); changed(kind);
}
$('#drop').onclick = () => $('#fileInput').click();
$('#drop').onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); $('#fileInput').click() } };
$('#fileInput').onchange = e => { addFiles(e.target.files); e.target.value = '' };
let dragN = 0;
addEventListener('dragenter', e => { if ([...(e.dataTransfer.types || [])].includes('Files')) { dragN++; $('#dropveil').classList.add('on') } });
addEventListener('dragleave', () => { dragN = Math.max(0, dragN - 1); if (!dragN) $('#dropveil').classList.remove('on') });
addEventListener('dragover', e => e.preventDefault());
addEventListener('drop', e => { e.preventDefault(); dragN = 0; $('#dropveil').classList.remove('on'); if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files) });

/* ---------- Ausgabeordner ---------- */
function showDir() { $('#outDir').textContent = '\u200e' + S.outdir + '\u200e'; $('#outDir').title = S.outdir }
$('#pickDir').onclick = async () => {
  let p = '';
  if (window.pywebview && window.pywebview.api && window.pywebview.api.pick_folder) p = await window.pywebview.api.pick_folder(S.outdir);
  else p = prompt('Ordner für die fertigen Videos:', S.outdir) || '';
  if (p) { S.outdir = p; showDir(); api('/api/config', { outdir: p }).catch(() => {}) }
};
$('#folderBtn').onclick = () => api('/api/show', { path: S.outdir }).catch(e => toast(e.message, true));

/* ---------- Konvertieren ---------- */
function updateGo() {
  const ok = !!(S.audio && S.image && S.info && S.info.ffmpeg);
  $('#goBtn').disabled = !ok; $('#queueAdd').disabled = !ok;
  const f = fmtOf(S.settings.fmt);
  $('#goSub').textContent = !S.info || !S.info.ffmpeg ? 'FFmpeg fehlt – bitte neu installieren'
    : !S.audio || !S.image ? 'Zuerst ' + (!S.audio && !S.image ? 'Song und Bild' : !S.audio ? 'einen Song' : 'ein Bild') + ' hineinziehen'
    : `${f[2].split(' · ')[0]} · ${S.settings.fps} fps · ${encLabel(S.settings.enc)} · ${mmss(S.meta ? S.meta.duration : audioDur())}`;
}
async function startJob(show) {
  try {
    let adj = null;
    if (HL.applied) {                               // Start/Ende nach dem Übernehmen noch verschoben? -> KI lernt den Feinschliff
      const a = toSec(S.settings.start), b = toSec(S.settings.end);
      if (a != null && b != null) adj = { ds: a - HL.applied.start, de: b - HL.applied.end };
      HL.applied = null;
    }
    const j = await api('/api/encode', { settings: S.settings, audio: S.audio.token, image: S.image.token, outdir: S.outdir, outname: S.outEdited ? $('#outName').value : '', hl_adjust: adj });
    S.outEdited = false;
    if (show) openProgress(j.id); else toast('In die Warteschlange gelegt: ' + j.name);
    pollJobs();
  } catch (e) { toast(e.message, true) }
}
$('#goBtn').onclick = () => startJob(true);
$('#queueAdd').onclick = () => startJob(false);

let progTimer = null;
const segs = $('#pgBar'); for (let i = 0; i < 20; i++) segs.append(el('i'));
function openProgress(id) {
  S.job = id; $('#pgErr').hidden = true; $('#pgLog').textContent = ''; renderProgress(null);
  if (!$('#progDlg').open) $('#progDlg').showModal();
  clearInterval(progTimer); progTimer = setInterval(async () => {
    try { const j = await api('/api/job/' + id); renderProgress(j); if (!['läuft', 'wartet'].includes(j.state)) clearInterval(progTimer) } catch (_) {}
  }, 500);
}
function renderProgress(j) {
  const st = j ? j.state : 'wartet', pct = j ? j.percent : 0, step = Math.floor(pct / 5) * 5;
  const done = st === 'fertig', err = st === 'fehler' || st === 'abgebrochen', run = !done && !err;
  $('#pgTitle').textContent = done ? 'Fertig! Dein Video ist bereit' : st === 'abgebrochen' ? 'Abgebrochen' : err ? 'Das hat nicht geklappt' : st === 'wartet' ? 'Wartet in der Schlange …' : 'Wird für YouTube konvertiert …';
  $('#pgIco').className = 'pg-ico' + (done ? ' done' : err ? ' err' : '');
  $('#pgIco').innerHTML = done ? ICON.check : err ? ICON.x : '<span class="spin"></span>';
  $('#pgFile').textContent = j ? (j.out || j.name) : '';
  $('#pgPct').textContent = (done ? 100 : step) + ' %';
  $('#pgPhase').textContent = j ? j.phase : 'Startet …';
  segs.classList.toggle('done', done);
  $$('i', segs).forEach((s, i) => s.classList.toggle('on', (i + 1) * 5 <= (done ? 100 : step)));
  segs.setAttribute('aria-valuenow', String(done ? 100 : step));
  if (j) {
    const m = j.meta || {}, sx = j.settings || {};
    $('#pgFmt').textContent = m.width ? `${m.width}×${m.height} · ${sx.fps} fps · ${m.encoder_name || ''}` : '–';
    $('#pgTime').textContent = m.duration ? `${mmss(done ? m.duration : j.time)} / ${mmss(m.duration)}` : '–';
    $('#pgSpeed').textContent = j.speed ? j.speed.replace('x', '×') + (j.fps ? ` · ${Math.round(j.fps)} B/s` : '') : '–';
    $('#pgEta').textContent = done ? 'fertig' : j.eta != null ? mmss(j.eta) : '–';
    $('#pgLog').textContent = j.log.join('\n'); $('#pgLog').scrollTop = 1e9;
    if (j.error) { $('#pgErr').hidden = false; $('#pgErr').textContent = j.error }
    if (done && m.check) $('#pgLog').textContent += `\n✓ Geprüft: ${m.check.width}×${m.check.height} · ${String(m.check.vcodec).toUpperCase()} + ${String(m.check.acodec).toUpperCase()} · ${mmss(m.check.duration)} · ${size(m.check.size)}`;
  }
  $('#pgCancel').hidden = !run; $('#pgHide').hidden = !run;
  $('#pgShow').hidden = !done; $('#pgNew').hidden = run;
  $('#pgNew').textContent = done ? 'Fertig' : 'Schließen';
}
$('#pgHide').onclick = () => { clearInterval(progTimer); $('#progDlg').close() };
$('#pgNew').onclick = () => { clearInterval(progTimer); $('#progDlg').close() };
$('#pgCancel').onclick = async () => { if (await ask('Konvertierung abbrechen?', 'Die halb fertige Datei wird gelöscht.', 'Abbrechen')) { api('/api/cancel', { id: S.job }).catch(() => {}); if (!$('#progDlg').open) $('#progDlg').showModal() } };
$('#pgShow').onclick = async () => { const j = await api('/api/job/' + S.job).catch(() => null); api('/api/show', { path: j && j.out }).catch(e => toast(e.message, true)) };
$('#progDlg').oncancel = e => { e.preventDefault(); $('#pgHide').hidden ? $('#pgNew').click() : $('#pgHide').click() };

/* ---------- Warteschlange ---------- */
const KNOWN = {};
async function pollJobs() {
  try {
    const d = await api('/api/jobs'); S.jobs = d.jobs;
    const open = d.jobs.filter(j => ['läuft', 'wartet'].includes(j.state)).length;
    $('#queueBadge').hidden = !open; $('#queueBadge').textContent = open;
    for (const j of d.jobs) {
      if (KNOWN[j.id] && KNOWN[j.id] !== j.state && !($('#progDlg').open && S.job === j.id)) {
        if (j.state === 'fertig') toast('✓ Fertig: ' + j.name); else if (j.state === 'fehler') toast('Fehler bei ' + j.name, true);
      }
      KNOWN[j.id] = j.state;
    }
    if ($('#queueDlg').open) drawQueue();
  } catch (_) {}
}
setInterval(pollJobs, 1500);
const Q_STATE = { 'läuft': 'Läuft', 'wartet': 'Wartet', 'fertig': 'Fertig', 'fehler': 'Fehler', 'abgebrochen': 'Abgebrochen' };
function drawQueue() {
  const box = $('#qList');
  const sig = S.jobs.map(j => j.id + j.state).join('|');
  if (sig && sig === box.dataset.sig) {        // nur Zahlen auffrischen – Knöpfe bleiben stehen (kein Flackern)
    for (const j of S.jobs) {
      const row = box.querySelector(`[data-id="${j.id}"]`); if (!row) continue;
      const pct = j.state === 'fertig' ? 100 : Math.floor(j.percent || 0);
      row.querySelector('.qi-pct').textContent = ['läuft', 'fertig'].includes(j.state) ? pct + ' %' : '';
      row.querySelector('.bar i').style.width = pct + '%';
      if (j.state === 'läuft') row.querySelector('.qi-foot small').textContent = [j.eta != null ? 'noch ' + mmss(j.eta) : 'wird berechnet …', j.speed ? 'Tempo ' + j.speed : ''].filter(Boolean).join(' · ');
    }
    return;
  }
  box.dataset.sig = sig; box.textContent = '';
  if (!S.jobs.length) { box.append(el('div', { class: 'empty' }, 'Noch keine Videos in der Warteschlange.')); return }
  for (const j of S.jobs) {
    const f = fmtOf(j.settings.fmt), run = j.state === 'läuft', live = run || j.state === 'wartet';
    const pct = j.state === 'fertig' ? 100 : Math.floor(j.percent || 0);
    const info = run ? [j.eta != null ? 'noch ' + mmss(j.eta) : 'wird berechnet …', j.speed ? 'Tempo ' + j.speed : ''].filter(Boolean).join(' · ')
      : j.state === 'fertig' ? 'Bereit für YouTube' : j.state === 'fehler' ? (j.error || '').split('\n')[0].slice(0, 90) : j.state === 'wartet' ? 'Startet, sobald das vorige Video fertig ist' : '';
    const open = () => { $('#queueDlg').close(); openProgress(j.id) };
    box.append(el('div', { class: 'qi ' + j.state, 'data-id': j.id },
      el('div', { class: 'qi-main' },
        el('b', { title: j.out || j.name }, j.name.replace(/\.mp4$/i, '')),
        el('div', { class: 'qi-meta' }, el('span', { class: 'qi-state' }, Q_STATE[j.state] || j.state), el('span', {}, `${f[1]} · ${j.settings.fps} fps`))),
      el('div', { class: 'qi-pct' }, run || j.state === 'fertig' ? pct + ' %' : ''),
      el('div', { class: 'bar' }, el('i', { style: `width:${pct}%` })),
      el('div', { class: 'qi-foot' }, el('small', {}, info),
        el('div', { class: 'qi-actions' },
          run ? el('button', { type: 'button', class: 'btn tiny', onclick: open }, 'Ansehen') : null,
          live ? el('button', { type: 'button', class: 'btn tiny danger', onclick: () => api('/api/cancel', { id: j.id }).then(pollJobs) }, 'Abbrechen') : null,
          j.state === 'fertig' ? el('button', { type: 'button', class: 'btn tiny', onclick: () => api('/api/show', { path: j.out }) }, 'Im Ordner zeigen') : null,
          j.state === 'fehler' ? el('button', { type: 'button', class: 'btn tiny', onclick: open }, 'Details') : null))));
  }
}
$('#queueBtn').onclick = () => { $('#qList').dataset.sig = ''; drawQueue(); $('#queueDlg').showModal(); pollJobs() };
$('#qClear').onclick = () => api('/api/clear-done', {}).then(pollJobs);
$('#copyCmd').onclick = async () => { try { await navigator.clipboard.writeText($('#cmdText').textContent); toast('✓ Befehl kopiert') } catch (_) { toast('Kopieren nicht möglich', true) } };

/* ---------- eigenes Programmfenster ---------- */
function nativeReady() {
  if (!window.pywebview || !window.pywebview.api || document.body.classList.contains('native')) return;
  document.body.classList.add('native'); requestAnimationFrame(fitHeader);
  const w = window.pywebview.api;
  const maxTitle = m => $('#winMax').setAttribute('aria-label', m ? 'Verkleinern' : 'Maximieren');
  $('#winMin').onclick = () => w.minimize();
  $('#winMax').onclick = async () => maxTitle(await w.toggle_max());
  $('#winClose').onclick = quit;
  $$('.dragzone').forEach(z => {
    z.addEventListener('mousedown', e => { if (e.button === 0 && e.detail < 2 && !document.body.classList.contains('full')) { e.preventDefault(); w.drag() } });
    z.addEventListener('dblclick', async e => { e.preventDefault(); maxTitle(await w.toggle_max()) });
  });
  $$('.grips i').forEach(g => g.addEventListener('mousedown', e => { if (e.button === 0) { e.preventDefault(); w.resize(g.dataset.edge) } }));
  w.is_max().then(maxTitle).catch(() => {});
  setTimeout(() => w.is_max().then(maxTitle).catch(() => {}), 1500);
}
addEventListener('pywebviewready', nativeReady); nativeReady();

/* F11 = Vollbild (ganzer Bildschirm), Esc verlässt es */
async function toggleFull() {
  const w = window.pywebview && window.pywebview.api;
  let on;
  if (w && w.toggle_fullscreen && document.body.classList.contains('native')) on = await w.toggle_fullscreen();
  else { if (document.fullscreenElement) await document.exitFullscreen(); else await document.documentElement.requestFullscreen().catch(() => {}); on = !!document.fullscreenElement }
  document.body.classList.toggle('full', !!on);
  fullUi();
  if (on) toast('Vollbild – F11 oder Esc = zurück. Fenster und Dateien vom anderen Monitor kannst du weiter hin- und herziehen.');
}
let MONS = 1;
async function fullUi() {
  const w = window.pywebview && window.pywebview.api, nat = document.body.classList.contains('native');
  if (nat && w && w.monitor_count) MONS = await w.monitor_count().catch(() => 1);
  $('#winMon').hidden = !(nat && MONS > 1);
  $('#winFull').setAttribute('aria-label', document.body.classList.contains('full') ? 'Vollbild beenden' : 'Vollbild');
}
$('#winFull').onclick = toggleFull;
$('#winMon').onclick = async () => { const w = window.pywebview && window.pywebview.api; if (w && w.next_monitor) await w.next_monitor() };
/* im Vollbild immer den ganzen aktuellen Monitor füllen (z. B. nach Win + Umschalt + Pfeil) */
addEventListener('resize', debounce(() => { const w = window.pywebview && window.pywebview.api; if (document.body.classList.contains('full') && w && w.fit_full) w.fit_full() }, 250));
addEventListener('pywebviewready', () => setTimeout(fullUi, 600));
addEventListener('keydown', e => {
  if (e.key === 'F11') { e.preventDefault(); toggleFull() }
  else if (e.key === 'Escape' && document.body.classList.contains('full') && !document.querySelector('dialog[open]')) toggleFull();
});
addEventListener('fullscreenchange', () => { if (!document.body.classList.contains('native')) document.body.classList.toggle('full', !!document.fullscreenElement) });

/* ---------- Beenden mit „Auf Wiedersehen“ (wie die Butchies-Webseite) ---------- */
let leaving = false;
function outroChime() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)(), master = ctx.createGain();
    master.gain.value = .9; master.connect(ctx.destination);
    const t0 = ctx.currentTime + .05;
    [76, 72, 69, 65, 60].forEach((n, k) => {
      const t = t0 + k * .16, o = ctx.createOscillator(), o2 = ctx.createOscillator(), g = ctx.createGain(), g2 = ctx.createGain();
      o.type = 'sine'; o2.type = 'triangle'; o.frequency.value = 440 * Math.pow(2, (n - 69) / 12); o2.frequency.value = o.frequency.value * 2.002;
      g2.gain.value = .18; o2.connect(g2); g2.connect(g); o.connect(g);
      g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(.07, t + .02); g.gain.exponentialRampToValueAtTime(.0006, t + 2.2); g.gain.linearRampToValueAtTime(0, t + 2.3);
      g.connect(master); o.start(t); o2.start(t); o.stop(t + 2.35); o2.stop(t + 2.35);
    });
  } catch (_) {}
}
async function quit() {
  if (KIWIN) {                          // KI-Fenster: nur dieses Fenster schließen – eine laufende KI-Rechnung läuft weiter
    if (AI.job) toast('Die KI rechnet im Hintergrund weiter.');
    try { window.pywebview.api.close() } catch (_) { window.close() }
    return;
  }
  if (leaving) return;
  const busy = S.jobs.some(j => ['läuft', 'wartet'].includes(j.state));
  if (busy && !await ask('Programm beenden?', 'Es wird gerade ein Video konvertiert. Beim Beenden wird es abgebrochen.', 'Beenden')) return;
  leaving = true;
  const done = S.jobs.filter(j => j.state === 'fertig').length;
  $('#gHint').textContent = done === 1 ? 'Dein neues Video wartet schon auf YouTube.' : done > 1 ? `Deine ${done} neuen Videos warten schon auf YouTube.` : 'Bis zum nächsten Song.';
  // Song sanft ausblenden
  if (!aud.paused) { const v0 = aud.volume; for (let i = 1; i <= 20; i++) setTimeout(() => { aud.volume = Math.max(0, v0 * (1 - i / 20)); if (i === 20) aud.pause() }, i * 70) }
  $$('dialog[open]').forEach(d => d.close());
  outroChime();
  const g = $('#goodbye'); g.hidden = false; requestAnimationFrame(() => g.classList.add('show'));
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  await new Promise(r => setTimeout(r, reduce ? 1200 : 3000));
  g.classList.add('closing');
  await new Promise(r => setTimeout(r, reduce ? 300 : 1500));
  try { await api('/api/quit', {}) } catch (_) {}
  if (window.pywebview && window.pywebview.api) window.pywebview.api.close();
  else { g.classList.add('done'); setTimeout(() => { window.close() }, 300) }
}
$('#quitBtn').onclick = quit;

/* ---------- Start-Animation ---------- */
function splashLeave() { const sp = $('#splash'); if (!sp || sp.classList.contains('leave')) return; sp.classList.add('leave'); setTimeout(() => sp.remove(), 950) }
$('#splash').addEventListener('click', splashLeave);
const splashTimer = setTimeout(splashLeave, matchMedia('(prefers-reduced-motion: reduce)').matches ? 600 : 3400);

/* ---------- Start ---------- */
function fitHeader() {                 // Kopfzeile passt sich an: erst Schild kürzen, dann ausblenden, dann nur Symbole
  const t = $('header.top'); if (!t) return;
  t.classList.remove('c1', 'c2', 'c3');
  for (const c of ['c1', 'c2', 'c3']) { if (t.scrollWidth <= t.clientWidth + 1) break; t.classList.add(c) }
}
window.addEventListener('resize', () => requestAnimationFrame(fitHeader));
function setVerBadge(info) {          // wie im Video Converter: Version + Grafikkarten
  const names = ((info.gpu && info.gpu.cards) || []).map(g => g.name.replace(/\(TM\)|\(R\)|Graphics/gi, '').replace(/\s+/g, ' ').trim());
  const b = $('#verBadge'); b.textContent = ''; b.append('Version ' + info.version, names.length ? el('span', { class: 'vb-gpu' }, ' · ' + names.join(' + ')) : '');
  b.title = b.textContent; b.hidden = false;
  requestAnimationFrame(fitHeader);
}
applyTheme(S.theme);
(async function init() {
  try {
    const info = await api('/api/info'); S.info = info;
    if (info.intro === false) { clearTimeout(splashTimer); const sp = $('#splash'); if (sp) sp.remove() }
    applyTheme(info.theme);
    fillTransitions(info.transitions || []);
    S.settings = info.settings; S.outdir = info.outdir; showDir();
    S.presets = info.presets || []; renderPresets();
    MK.mode = modeFromSettings(); if (S.settings.vizShape === 'mask') loadMaskFromServer(S.settings.vizMask, 'viz');
    if (S.settings.fxArea === 'mask') loadMaskFromServer(S.settings.fxMask, 'fx');
    if (S.settings.aiArea === 'mask') loadMaskFromServer(S.settings.aiMask, 'ai');
    renderFx(); refreshAi();
    if (KIWIN) kiBoot();
    $('#gpuText').textContent = info.gpu ? info.gpu.text : '';
    $('#aiText').textContent = info.ai ? (info.ai.model ? '✨ ' : '') + info.ai.text : '';
    $('#verText').textContent = info.version;
    setVerBadge(info);
    $('#ffDot').className = 'dot ' + (info.ffmpeg ? 'ok' : 'bad');
    $('#ffText').textContent = info.ffmpeg ? 'FFmpeg bereit' : 'FFmpeg fehlt';
    $('#ffWarn').hidden = info.ffmpeg;
    drawFiles(); changed(); timeline();
    // Encoder-Prüfung läuft im Hintergrund – nachladen
    const recheck = async (n) => {
      const i = await api('/api/info').catch(() => null); if (!i) return;
      setVerBadge(i); S.info.encoders = i.encoders; S.info.hw_done = i.hw_done; S.info.auto_enc = i.auto_enc; renderEnc(); updateGo();
      const hw = Object.entries(i.encoders).filter(([k, v]) => v.ok && !['x264', 'x265'].includes(k)).map(([k]) => ENC_NAME[k]);
      const pending = !i.hw_done;
      $('#hwText').textContent = pending ? 'Grafikkarte wird geprüft …' : hw.length ? '⚡ Grafikkarte nutzbar: ' + hw.join(', ') : 'Keine nutzbare Grafikkarte – CPU wird genutzt';
      if (S.settings.enc !== 'auto' && S.info.encoders[S.settings.enc] && S.info.encoders[S.settings.enc].ok === false) { S.settings.enc = 'auto'; changed('enc') }
      if (pending && n < 30) setTimeout(() => recheck(n + 1), 1000);
    };
    recheck(0); pollJobs();
  } catch (e) { toast('Das Programm antwortet nicht – bitte neu starten', true) }
})();
setInterval(() => api('/api/ping').catch(() => {}), 15000);

/* ---------- Selbst-Lernen (1.7.0) ---------- */
const LN = { styleOffered: false };
function actToast(msg, label, fn) {
  const t = el('div', { class: 'toast act' }, el('span', {}, msg), el('button', { type: 'button', class: 'btn small glow', onclick: () => { t.remove(); fn() } }, label));
  $('#toasts').append(t); setTimeout(() => t.remove(), 12000);
}
async function applyStyle(silent) {
  try {
    const d = await api('/api/learn/style');
    if (!d.values || !Object.keys(d.values).length) { if (!silent) toast('Noch nicht genug gelernt – nach ein paar Videos klappt das.', true); return }
    S.settings = Object.assign({}, S.settings, d.values);
    changed('fmt'); renderViz(true); renderFx();
    toast('✓ Dein gelernter Stil ist eingestellt');
  } catch (e) { toast(e.message, true) }
}
async function offerStyle() {
  if (LN.styleOffered) return;
  const d = await api('/api/learn/style').catch(() => null);
  if (!d || !d.values || !Object.keys(d.values).length) return;
  LN.styleOffered = true;
  actToast('🧠 Die KI kennt deinen Stil (Effekte, Kamera, Wellen).', 'Übernehmen', () => applyStyle());
}
const lnCard = (title, reset, ...kids) => el('div', { class: 'ln-card' },
  el('h3', {}, title, reset ? el('button', { type: 'button', class: 'btn tiny', onclick: () => resetLearn(reset) }, 'Vergessen') : null), ...kids);
async function drawLearn() {
  const d = await api('/api/learn'), box = $('#lnList'); box.textContent = '';
  const h = d.hl;
  box.append(lnCard('🎯 Beste Stelle für Shorts', h.n ? 'hl' : '',
    h.n ? el('p', {}, 'Aus ', el('b', {}, `${h.n} Entscheidung${h.n === 1 ? '' : 'en'}`), ' gelernt. Am liebsten nimmst du: ', el('b', {}, h.fav), '.') : el('p', {}, 'Noch nichts gelernt. Nimm bei „Beste Stelle finden“ einen Vorschlag – die KI merkt sich, was dir gefällt.'),
    h.taste ? el('p', {}, 'Du magst ', el('b', {}, h.taste), '.') : null,
    Math.abs(h.shift) >= 0.3 ? el('p', {}, 'Du startest meist ', el('b', {}, `${Math.abs(h.shift).toFixed(1).replace('.', ',')} s ${h.shift < 0 ? 'früher' : 'später'}`), ' – die Vorschläge machen das jetzt automatisch.') : null,
    h.n ? el('div', { class: 'ln-meter', title: 'Sicherheit' }, el('i', { style: `width:${h.conf}%` })) : null,
    h.n ? el('p', {}, `Sicherheit ${h.conf} % · ` + Object.entries(h.picks).map(([k, v]) => `${k}: ${v}`).join(' · ')) : null));
  box.append(lnCard('🎤 Songtext-Wörter', d.word_count ? 'words' : '',
    d.word_count ? el('p', {}, el('b', {}, `${d.word_count} Wörter`), ` gelernt${d.songs ? ` aus ${d.songs} korrigierten Song${d.songs === 1 ? '' : 's'}` : ''} – Whisper bekommt sie beim Erkennen als Hilfe mit.`) : el('p', {}, 'Noch keine Wörter. Korrigiere nach „Mit Songtext“ falsch erkannte Zeilen – die KI lernt deine Wörter.'),
    d.words.length ? el('div', { class: 'ln-words' }, ...d.words.slice(0, 30).map(w => el('span', {}, w))) : null));
  const st = d.style;
  box.append(lnCard('🎨 Dein Stil', st.n ? 'style' : '',
    st.ready ? el('p', {}, 'Aus ', el('b', {}, `${st.n} Videos`), ' gelernt' + (Object.keys(st.top).length ? ': ' : '.'), el('b', {}, Object.values(st.top).join(' · '))) : el('p', {}, st.n ? `${st.n} von 3 Videos – nach ${st.need} weiteren schlägt die KI deinen Stil bei neuen Bildern vor.` : 'Noch nichts gelernt. Nach 3 Videos schlägt die KI deine Lieblings-Effekte und Regler-Werte vor.'),
    !st.ready ? el('div', { class: 'ln-meter' }, el('i', { style: `width:${Math.min(100, st.n / 3 * 100)}%` })) : null,
    st.ready ? el('div', { class: 'ln-acts' }, el('button', { type: 'button', class: 'btn small glow', onclick: () => { $('#learnDlg').close(); applyStyle() } }, 'Meinen Stil jetzt einstellen')) : null));
  if (LN.update === undefined) LN.update = await api('/api/update').catch(() => null);
  const A = d.ai || { n: 0, learned_names: [], scores: {} };
  const mname = id => ((AI.st && AI.st.motions) || []).find(m => m[0] === id)?.[1] || id;
  box.append(lnCard('🎬 KI-Video', A.n ? 'ai' : '',
    A.n ? el('p', {}, 'Aus ', el('b', {}, `${A.n} Bewertung${A.n === 1 ? '' : 'en'}`), ' gelernt' + (A.learned_names.length ? ' – gibt jetzt automatisch mit: ' : '.'), A.learned_names.length ? el('b', {}, A.learned_names.join(', ')) : '')
      : el('p', {}, 'Noch nichts gelernt. Bewerte deine KI-Videos mit Sternen und sag, was anders werden soll – die KI passt sich an.'),
    Object.keys(A.scores || {}).length ? el('p', {}, 'Deine Noten: ' + Object.entries(A.scores).map(([m, v]) => `${mname(m)} ${String(v).replace('.', ',')} ★`).join(' · ')) : null));
  const u = LN.update;
  box.append(lnCard('⬆️ Neue KI-Versionen', '',
    el('p', {}, u ? (u.newer ? `Neue Version ${u.latest} ist da (du hast ${u.current}).` : u.latest ? `Du hast die neueste Version (${u.current}).` : 'Keine Verbindung zu GitHub – wird beim nächsten Start erneut geprüft.') : 'Wird geprüft …'),
    u && u.newer ? el('div', { class: 'ln-acts' }, el('button', { type: 'button', class: 'btn small glow', onclick: () => { $('#learnDlg').close(); openSettings('upd', true) } }, 'Jetzt aktualisieren')) : null));
}
async function resetLearn(part) {
  const what = { hl: 'die gelernte beste Stelle', words: 'die gelernten Songtext-Wörter und korrigierten Texte', style: 'deinen gelernten Stil', ai: 'die KI-Video-Bewertungen' }[part] || 'alles Gelernte';
  if (!await ask('Vergessen?', `Soll die KI ${what} vergessen? Das lässt sich nicht rückgängig machen.`, 'Vergessen')) { $('#learnDlg').showModal(); return }
  await api('/api/learn/reset', { part: part || 'all' }).catch(e => toast(e.message, true));
  toast('✓ Vergessen'); if (!$('#learnDlg').open) $('#learnDlg').showModal(); drawLearn();
}
$('#learnBtn').onclick = () => { $('#lnList').textContent = ''; $('#learnDlg').showModal(); drawLearn().catch(e => toast(e.message, true)) };
$('#lnResetAll').onclick = () => resetLearn('');
$('#updLater').onclick = () => { $('#updBar').hidden = true };
$('#updGo').onclick = () => { $('#updBar').hidden = true; openSettings('upd', true) };
setTimeout(async () => {
  const st = await api('/api/settings').catch(() => null);
  if (KIWIN || (st && st.upd_auto === false)) return;          // automatische Suche abgeschaltet
  const u = await api('/api/update').catch(() => null); LN.update = u;
  if (u && u.newer) { $('#updText').textContent = `⬆️ Neue Version ${u.latest} ist verfügbar (mit verbesserter KI und Fehlerkorrekturen) – du hast ${u.current}.`; $('#updBar').hidden = false }
}, 2500);


/* ---------- Einstellungen (1.9.0): Updates · KI-Hardware · Speicher ---------- */
const SET = { tab: 'upd', hw: null, st: null, updPoll: 0, benchPoll: 0 };
const gbTxt = x => String(Math.round(x * 10) / 10).replace('.', ',') + ' GB';
async function openSettings(tab, install) {
  SET.tab = tab || SET.tab; if (!$('#setDlg').open) $('#setDlg').showModal(); await drawSet();
  if (install) updInstall();
}
$('#setBtn').onclick = () => openSettings();
$$('#setTabs button').forEach(b => b.onclick = () => { SET.tab = b.dataset.t; drawSet() });
async function drawSet() {
  $$('#setTabs button').forEach(b => b.setAttribute('aria-selected', String(b.dataset.t === SET.tab)));
  const box = $('#setBody'); box.textContent = '';
  try {
    if (SET.tab === 'upd') await drawUpd(box);
    else if (SET.tab === 'hw') await drawHw(box);
    else await drawMem(box);
  } catch (e) { box.append(el('p', { class: 'hint' }, 'Fehler: ' + e.message)) }
}
async function drawUpd(box) {
  SET.st = await api('/api/settings');
  const u = LN.update || (LN.update = await api('/api/update').catch(() => null));
  const auto = el('button', { type: 'button', class: 'switch', role: 'switch', 'aria-checked': String(SET.st.upd_auto !== false), 'aria-label': 'Automatisch nach Updates suchen' }, el('i'));
  auto.onclick = async () => { const v = auto.getAttribute('aria-checked') !== 'true'; auto.setAttribute('aria-checked', String(v)); await api('/api/settings', { upd_auto: v }).catch(e => toast(e.message, true)) };
  const status = !u ? 'Wird geprüft …' : u.error ? 'Keine Verbindung zu GitHub – später nochmal versuchen.' : u.newer ? `Neue Version ${u.latest} ist da!` : `Du hast die neueste Version.`;
  box.append(
    lnCard('Installierte Version', '', el('div', { class: 'set-big' }, 'ffmpeg_encode Studio ' + SET.st.version), el('p', {}, status),
      el('div', { class: 'ln-acts' },
        el('button', { type: 'button', class: 'btn small', onclick: async () => { LN.update = await api('/api/update?force=1').catch(e => ({ error: e.message })); drawSet() } }, 'Jetzt nach Updates suchen'),
        u && u.newer ? el('button', { type: 'button', class: 'btn small glow', id: 'updInstBtn', onclick: updInstall }, `Auf ${u.latest} aktualisieren`) : null),
      el('div', { id: 'updProg', hidden: true }, el('div', { class: 'set-prog' }, el('i')), el('p', { id: 'updPhase' }, '')),
      u && u.newer && u.notes ? el('div', { class: 'set-notes' }, u.notes) : null),
    lnCard('Automatisch', '', el('div', { class: 'set-row' }, el('span', {}, el('b', {}, 'Beim Start nach Updates suchen'), el('small', {}, 'Zeigt oben einen Hinweis, sobald eine neue Version da ist. Installiert wird nur, wenn du es bestätigst.')), auto)),
    el('p', { class: 'hint' }, 'So läuft ein Update: Die neue Version wird von GitHub geladen, still installiert und das Programm startet danach von selbst neu. Deine Einstellungen, Vorlagen, Projekte, das Gelernte und das KI-Paket bleiben erhalten.'));
  if (SET.updPoll) updShow(await api('/api/update/task'));
}
function updShow(t) {
  const p = $('#updProg'); if (!p) return;
  p.hidden = false; $('#updProg i').style.width = (t.percent || 0) + '%';
  $('#updPhase').textContent = t.state === 'fehler' ? '⚠️ ' + t.error : t.state === 'abgebrochen' ? 'Abgebrochen.' : `${Math.round(t.percent || 0)} % · ${t.phase || ''}`;
  const b = $('#updInstBtn'); if (b) b.disabled = t.state === 'läuft' || t.state === 'fertig';
}
async function updInstall() {
  if (!await ask('Jetzt aktualisieren?', 'Die neue Version wird geladen und installiert. Das Programm schließt sich dafür kurz und startet danach von selbst neu.', 'Aktualisieren')) return;
  if (!$('#setDlg').open || SET.tab !== 'upd') await openSettings('upd');
  try { updShow(await api('/api/update/install', {})) } catch (e) { toast(e.message, true); return }
  clearInterval(SET.updPoll);
  SET.updPoll = setInterval(async () => {
    const t = await api('/api/update/task').catch(() => null); if (!t) return;
    updShow(t);
    if (t.state !== 'läuft') { clearInterval(SET.updPoll); SET.updPoll = 0; if (t.state === 'fertig') toast('✓ Update wird installiert – bis gleich!') }
  }, 700);
}
async function drawHw(box, fresh) {
  const h = SET.hw = fresh || await api('/api/hw');
  const a = h.active;
  box.append(el('p', { class: 'hint' }, 'Die KI prüft deinen PC und verteilt die Arbeit: die KI-Bewegung rechnet auf der stärksten Grafikkarte, der KI-Upscaler gleichzeitig auf der zweiten. Du kannst es hier auch selbst festlegen.'));
  const gp = el('div', { class: 'hw-gpus' });
  for (const g of h.gpus) {
    const isMain = g.vulkan && g.vulkan === a.gen, isUp = String(g.dxgi) === String(a.up);
    const t = h.bench && h.bench.gen && h.bench.gen[g.vulkan], tu = h.bench && h.bench.up && h.bench.up[String(g.dxgi)];
    gp.append(el('div', { class: 'hw-gpu' + (isMain ? ' main' : '') }, el('span', { class: 'ic' }, g.kind === 'dgpu' ? '🎮' : '💻'),
      el('div', {}, el('b', {}, g.name), el('small', {}, [g.kind === 'dgpu' ? 'Eigene Grafikkarte' : 'Prozessor-Grafik', g.vram ? gbTxt(g.vram) + ' Grafikspeicher' : (g.shared ? 'nutzt Arbeitsspeicher' : ''),
        t ? `Test KI ${String(t).replace('.', ',')} s` : '', tu ? `Upscaler ${String(tu).replace('.', ',')} s/Bild` : '', g.vulkan ? '' : 'für die KI nicht nutzbar'].filter(Boolean).join(' · '))),
      el('div', { class: 'hw-tags' }, isMain ? el('span', {}, 'KI-Bewegung') : null, isUp ? el('span', { class: isMain ? 'alt' : '' }, 'KI-Upscaler') : null)));
  }
  if (!h.gpus.length) gp.append(el('p', {}, 'Keine Grafikkarte erkannt – die KI rechnet auf dem Prozessor.'));
  box.append(lnCard('🖥️ Dein PC', '', el('p', {}, el('b', {}, h.cpu), ` · ${h.cores} Kerne · ${gbTxt(h.ram)} Arbeitsspeicher · ${gbTxt(h.disk_free)} frei`), gp,
    el('div', {}, ...h.notes.map(n => el('p', {}, '• ' + n)))));
  const opt = (v, txt, cur) => el('option', { value: v, selected: String(cur) === String(v) }, txt);
  const genSel = el('select', { class: 'set-sel', 'aria-label': 'KI-Bewegung rechnet auf' },
    opt('auto', `Automatisch (${h.rec.gen_name})`, h.choice.gen), ...h.gpus.filter(g => g.vulkan).map(g => opt(g.vulkan, g.name, h.choice.gen)), opt('cpu', 'Prozessor (sehr langsam)', h.choice.gen));
  const upSel = el('select', { class: 'set-sel', 'aria-label': 'KI-Upscaler rechnet auf' },
    opt('auto', `Automatisch (${h.rec.up_name})`, h.choice.up), ...h.gpus.filter(g => g.dxgi >= 0).map(g => opt(g.dxgi, g.name, h.choice.up)), opt('cpu', 'Prozessor', h.choice.up));
  const setHw = async v => { try { const r = await api('/api/hw/set', v); SET.hw = r; $('#setBody').textContent = ''; drawHw($('#setBody'), r); renderAiHw() } catch (e) { toast(e.message, true) } };
  genSel.onchange = () => setHw({ gen: genSel.value }); upSel.onchange = () => setHw({ up: upSel.value });
  const srv = el('button', { type: 'button', class: 'switch', role: 'switch', 'aria-checked': String(h.choice.server !== false), 'aria-label': 'KI geladen lassen' }, el('i'));
  srv.onclick = () => setHw({ server: srv.getAttribute('aria-checked') !== 'true' });
  box.append(lnCard('⚙️ Verteilung', '',
    el('div', { class: 'set-row' }, el('span', {}, el('b', {}, 'KI-Bewegung rechnet auf'), el('small', {}, a.te === 'cpu' && a.gen !== 'cpu' ? 'Text-Teil der KI im Arbeitsspeicher, damit der Grafikspeicher reicht' : 'alle Teile auf dieser Karte')), genSel),
    el('div', { class: 'set-row' }, el('span', {}, el('b', {}, 'KI-Upscaler rechnet auf'), el('small', {}, a.parallel ? '✓ gleichzeitig mit der KI-Bewegung (zwei Karten)' : 'nach jedem Stück (gleiche Karte)')), upSel),
    el('div', { class: 'set-row' }, el('span', {}, el('b', {}, 'KI zwischen den Stücken geladen lassen'), el('small', {}, h.server_ok ? (h.server_error ? '⚠️ ' + h.server_error + ' – es wird der langsamere Weg genutzt.' : 'Viel schneller: die 8 GB werden nur einmal pro Auftrag geladen.') : 'In dieser Version nicht enthalten.')), srv)));
  const bt = el('button', { type: 'button', class: 'btn small glow', disabled: !h.ai_ready }, h.bench && h.bench.t ? 'Schnelltest wiederholen' : 'Schnelltest starten');
  const bp = el('div', { hidden: true }, el('div', { class: 'set-prog' }, el('i')), el('p', {}, ''));
  bt.onclick = async () => {
    try { const r = await api('/api/hw/bench', {}); bt.disabled = true; bp.hidden = false;
      clearInterval(SET.benchPoll);
      SET.benchPoll = setInterval(async () => {
        const v = await api('/api/ai/job/' + r.id).catch(() => null); if (!v) return;
        bp.querySelector('i').style.width = v.percent + '%'; bp.querySelector('p').textContent = `${v.percent} % · ${v.note || ''}`;
        if (!['läuft', 'wartet'].includes(v.state)) {
          clearInterval(SET.benchPoll); SET.benchPoll = 0;
          if (v.state === 'fertig') { toast('✓ Schnelltest fertig – die schnellste Karte wird jetzt benutzt'); setTimeout(async () => { if (SET.tab === 'hw' && $('#setDlg').open) { const f = await api('/api/hw'); $('#setBody').textContent = ''; drawHw($('#setBody'), f); renderAiHw() } }, 2500) }
          else toast(v.error || 'Schnelltest abgebrochen', true);
        }
      }, 1000);
    } catch (e) { toast(e.message, true) }
  };
  box.append(lnCard('⏱️ Schnelltest', '', el('p', {}, h.ai_ready ? 'Misst jede Grafikkarte mit einem kleinen KI-Stück und dem Upscaler (dauert ein paar Minuten). Danach nimmt „Automatisch“ die wirklich schnellste Karte.' : 'Erst das KI-Video-Paket laden (Karte „KI-Video“), dann kann getestet werden.'),
    el('div', { class: 'ln-acts' }, bt, el('button', { type: 'button', class: 'btn small', onclick: async () => { const f = await api('/api/hw/refresh', {}); $('#setBody').textContent = ''; drawHw($('#setBody'), f) } }, 'Neu erkennen')), bp));
  // 1.10.0: Training + Gedächtnis
  const T = h.tuner || { speed: [], ratings: 0 };
  const qn = { fast: 'Schnell', good: 'Beste Qualität', test: 'Test' };
  const rows = T.speed.filter(r => r.best).map(r => el('p', {}, `• ${qn[r.quality] || r.quality} auf ${(h.gpus.find(g => g.vulkan === r.gen) || {}).name || (r.gen === 'cpu' ? 'Prozessor' : r.gen)}: bestes Rezept „${r.best_name}“ – ${String(r.spf).replace('.', ',')} s je Bild` +
    (r.worst_spf > r.spf * 1.05 ? ` (${Math.round((1 - r.spf / r.worst_spf) * 100)} % schneller als das langsamste)` : '') + (r.oom.length ? ` · ${r.oom.length}× Speicher zu knapp – gemieden` : '')));
  const tp = el('div', { hidden: true }, el('div', { class: 'set-prog' }, el('i')), el('p', {}, ''));
  const train = q => async () => {
    try { const r = await api('/api/ai/train', { quality: q }); tp.hidden = false;
      clearInterval(SET.benchPoll);
      SET.benchPoll = setInterval(async () => {
        const v = await api('/api/ai/job/' + r.id).catch(() => null); if (!v) return;
        tp.querySelector('i').style.width = v.percent + '%'; tp.querySelector('p').textContent = `${v.percent} % · ${v.note || ''}`;
        if (!['läuft', 'wartet'].includes(v.state)) {
          clearInterval(SET.benchPoll); SET.benchPoll = 0;
          if (v.state === 'fertig') toast(`✓ Training fertig – ab jetzt: „${v.result.best_name}“`); else toast(v.error || 'Training abgebrochen', true);
          if ($('#setDlg').open && SET.tab === 'hw') { const f = await api('/api/hw'); $('#setBody').textContent = ''; drawHw($('#setBody'), f) }
        }
      }, 1000);
    } catch (e) { toast(e.message, true) }
  };
  box.append(lnCard('🏋️ KI-Training & Gedächtnis', '',
    el('p', {}, `Die KI merkt sich, wie sie auf deinem PC am schnellsten läuft (Rezept gerade: „${h.recipe_name || 'Standard'}“), weicht bei zu wenig Grafikspeicher selbst aus und lernt aus deinen Sternen, welche Varianten gut aussehen (${T.ratings} Bewertungen, „🤖 KI-Tipp“ bei den Varianten).`),
    ...(rows.length ? rows : [el('p', { class: 'hint' }, 'Noch nichts gemessen – starte das Training oder rechne einfach los, die KI lernt bei jedem Stück mit.')]),
    el('div', { class: 'ln-acts' },
      el('button', { type: 'button', class: 'btn small glow', disabled: !h.ai_ready, onclick: train('fast') }, 'Training „Schnell“'),
      el('button', { type: 'button', class: 'btn small', disabled: !h.ai_ready, onclick: train('good') }, 'Training „Beste Qualität“'),
      el('button', { type: 'button', class: 'btn small', onclick: async () => { if (!await ask('Gedächtnis zurücksetzen?', 'Alle gemessenen Tempo-Werte und gelernten Qualitäts-Vorlieben werden gelöscht.', 'Zurücksetzen')) return; const f = await api('/api/ai/tuner-reset', {}); $('#setBody').textContent = ''; drawHw($('#setBody'), f) } }, 'Zurücksetzen')),
    el('p', { class: 'hint' }, 'Training: probiert jede Einstellung einmal mit einem echten Stück aus (dauert je nach Karte ca. 5–20 Minuten). Danach nimmt die KI immer die schnellste, die sicher läuft.'), tp));
}
async function drawMem(box) {
  const st = await api('/api/settings'); const ai = st.ai;
  const clr = el('button', { type: 'button', class: 'btn small', disabled: !st.ai_cache }, 'Zwischenspeicher leeren');
  clr.onclick = async () => {
    if (!await ask('Zwischenspeicher leeren?', 'Alle gespeicherten KI-Stücke und fertigen KI-Clips werden gelöscht (dein Video-Projekt bleibt, der KI-Clip muss dann neu berechnet werden).', 'Leeren')) { openSettings('mem'); return }
    try { await api('/api/ai/cache-clear', {}); toast('✓ Aufgeräumt') } catch (e) { toast(e.message, true) }
    openSettings('mem');
  };
  const rm = el('button', { type: 'button', class: 'btn small danger', disabled: !ai.ready }, 'KI-Paket entfernen');
  rm.onclick = async () => {
    if (!await ask('KI-Paket entfernen?', `Gibt ca. ${gbTxt(ai.need_gb)} frei. Für KI-Videos muss es danach neu geladen werden.`, 'Entfernen')) { openSettings('mem'); return }
    await api('/api/ai/remove', {}).catch(e => toast(e.message, true)); toast('✓ Entfernt'); openSettings('mem');
  };
  box.append(lnCard('🎬 KI-Video Zwischenspeicher', '', el('div', { class: 'set-big' }, gbTxt(st.ai_cache)), el('p', {}, 'Fertige Stücke und Varianten – damit ein Abbruch dort weitermacht und du Clips nicht doppelt rechnen musst.'), el('div', { class: 'ln-acts' }, clr)),
    lnCard('🧠 KI-Video-Paket', '', el('div', { class: 'set-big' }, ai.ready ? 'installiert · ' + gbTxt(ai.need_gb) : 'nicht installiert'), el('p', {}, `Ordner: ${ai.folder} · frei: ${gbTxt(ai.free_gb)}`), el('div', { class: 'ln-acts' }, rm)));
}
async function renderAiHw() {
  const l = $('#aiHwLine'); if (!l) return;
  if (!SET.hw) SET.hw = await api('/api/hw').catch(() => null);
  const a = SET.hw && SET.hw.active; l.textContent = '';
  if (!a) return;
  l.append(`🧠 KI rechnet auf ${a.gen_name}` + (a.up_name && a.up_name !== a.gen_name ? ` · Upscaler ${a.parallel ? 'gleichzeitig ' : ''}auf ${a.up_name}` : '') + ' · ',
    el('a', { onclick: () => openSettings('hw') }, 'ändern'));
}
setTimeout(renderAiHw, 3000);

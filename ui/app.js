/* ffmpeg_encode Studio – Oberfläche */
'use strict';
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const TOKEN = (location.hash.slice(1) || sessionStorage.getItem('fes-token') || '');
if (TOKEN) { sessionStorage.setItem('fes-token', TOKEN); history.replaceState(null, '', location.pathname) }

// Designs der Butchies-Webseite: id, Name, Untertitel, Hintergrund, Farbe A, Farbe B, Layout/Schrift, Überschrift-Schrift
const THEMES = [
  ['neon', 'Neon Lila', 'Das Original', '#0b0614', '#a46bff', '#ff6fc4', 'club', 'Unbounded'],
  ['ocean', 'Ozean', 'Kühles Blau', '#03101a', '#38bdf8', '#22d3ee', 'wellen', 'Quicksand'],
  ['sunset', 'Sunset', 'Warm & glühend', '#140708', '#ff7a45', '#ff4f9a', 'magazin', "'Playfair Display'"],
  ['emerald', 'Smaragd', 'Frisches Grün', '#04110c', '#2fd38f', '#a3e635', 'studio', "'Space Grotesk'"],
  ['gold', 'Gold Lounge', 'Edel & dunkel', '#0d0a05', '#f5b544', '#ffdf8a', 'lounge', "'Cormorant Garamond'"],
  ['mono', 'Mitternacht', 'Schwarz-Weiß', '#0a0a0a', '#e5e5e5', '#9ca3af', 'index', "'Archivo Black'"],
  ['light', 'Hell', 'Für den Tag', '#f6f2fb', '#7c3aed', '#db2777', 'tag', 'Manrope']
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
      type: 'button', class: 'theme-opt' + (id === 'light' ? ' is-light' : ''), 'aria-pressed': String(id === S.theme),
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
  if (!S.settings || !S.settings.viz || document.hidden || ts - lastFrame < 70) return;
  lastFrame = ts; VT += 0.08;
  if (LIVE.an && !aud.paused) { LIVE.an.getByteFrequencyData(LIVE.freq); LIVE.an.getByteTimeDomainData(LIVE.time); LIVE.on = true } else LIVE.on = false;
  drawVizBox();
}
requestAnimationFrame(vizFrame);
function drawVizBox() {
  const s = S.settings, box = $('#vizBox'), r = box.getBoundingClientRect();
  const W = Math.max(20, Math.round(r.width)), H = Math.max(10, Math.round(r.height)), svg = $('#vizSvg');
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svg.innerHTML = vizSvg(s.vizStyle, W, H, VT, s, false, 'vgMain');
  const glow = s.vizStyle === 'neon' || s.vizStyle === 'glowbars' ? Math.max(s.vizGlow, 65) : s.vizGlow;
  svg.style.opacity = s.vizAlpha / 100;
  svg.style.filter = glow > 0 ? `drop-shadow(0 0 ${Math.round(glow / 8)}px ${colorAt(s, 0.3, VT)}) drop-shadow(0 0 ${Math.round(glow / 4)}px ${colorAt(s, 0.7, VT)})` : 'none';
  const m = s.vizSoft ? 'linear-gradient(90deg,transparent 0%,#000 12%,#000 88%,transparent 100%)' : 'none';
  svg.style.webkitMaskImage = m; svg.style.maskImage = m;
}
function placeVizBox() {
  const s = S.settings, box = $('#vizBox');
  box.hidden = !s.viz; $('#vizHint').hidden = !s.viz;
  box.style.left = s.vizX + '%'; box.style.top = s.vizY + '%'; box.style.width = s.vizW + '%'; box.style.height = s.vizH + '%';
  box.classList.toggle('low', s.vizY < 8);
  const st = VSTYLES.find(x => x[0] === s.vizStyle) || VSTYLES[0];
  $('#vbLabel').textContent = st[1] + (s.vizDock ? ' · ' + dockName(s.vizDock) : ' · frei');
  $('#dockStatus').textContent = s.vizDock ? 'Angedockt: ' + dockName(s.vizDock) : 'Frei platziert';
  if (s.viz) drawVizBox();
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
    VSTYLES.forEach(([id, name, short], i) => box.append(el('button', { type: 'button', class: 'vtile', 'data-id': id, title: name, 'aria-label': name, onclick: () => set('vizStyle', id) },
      el('div', { class: 'vt-art', 'aria-hidden': 'true', html: `<svg viewBox="0 0 96 44">${vizSvg(id, 96, 44, 1.4, ms, true, 'vgT' + i)}</svg>` }), el('span', {}, short))));
  }
  $$('.vtile').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.id === s.vizStyle)));
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
function goDock(id) {
  const s = S.settings;
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
  if (e.button !== 0) return; e.preventDefault();
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
const endDrag = () => { if (!DRAG) return; DRAG = null; showMarks(false); changed('viz') };
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
  S.settings = Object.assign({}, S.settings, p.settings, { start: S.settings.start, end: S.settings.end });
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


/* ---------- Änderungen ---------- */
const saveSettings = debounce(() => api('/api/config', { settings: S.settings }).catch(() => {}), 600);
function changed(what) {
  const s = S.settings;
  renderFormats(); renderFits(); renderFps(); renderEnc(); renderSeg('#colorSeg', 'color'); renderViz();
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
    const j = await api('/api/encode', { settings: S.settings, audio: S.audio.token, image: S.image.token, outdir: S.outdir, outname: S.outEdited ? $('#outName').value : '' });
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
function drawQueue() {
  const box = $('#qList'); box.textContent = '';
  if (!S.jobs.length) { box.append(el('div', { class: 'empty' }, 'Noch keine Videos in der Warteschlange.')); return }
  for (const j of S.jobs) {
    const f = fmtOf(j.settings.fmt);
    box.append(el('div', { class: 'qi ' + j.state },
      el('div', {}, el('b', { title: j.out || j.name }, j.name), el('small', {}, `${f[1]} · ${j.settings.fps} fps · ${j.state === 'läuft' ? Math.floor(j.percent) + ' %' : j.state}`)),
      el('div', { class: 'qi-actions' },
        ['läuft', 'wartet'].includes(j.state) ? el('button', { type: 'button', class: 'btn small', onclick: () => { $('#queueDlg').close(); openProgress(j.id) } }, 'Ansehen') : null,
        ['läuft', 'wartet'].includes(j.state) ? el('button', { type: 'button', class: 'btn small danger', onclick: () => api('/api/cancel', { id: j.id }).then(pollJobs) }, 'Abbrechen') : null,
        j.state === 'fertig' ? el('button', { type: 'button', class: 'btn small', onclick: () => api('/api/show', { path: j.out }) }, 'Zeigen') : null,
        j.state === 'fehler' ? el('button', { type: 'button', class: 'btn small', onclick: () => { $('#queueDlg').close(); openProgress(j.id) } }, 'Details') : null),
      el('div', { class: 'bar' }, el('i', { style: `width:${j.state === 'fertig' ? 100 : j.percent}%` }))));
  }
}
$('#queueBtn').onclick = () => { drawQueue(); $('#queueDlg').showModal(); pollJobs() };
$('#qClear').onclick = () => api('/api/clear-done', {}).then(pollJobs);
$('#copyCmd').onclick = async () => { try { await navigator.clipboard.writeText($('#cmdText').textContent); toast('✓ Befehl kopiert') } catch (_) { toast('Kopieren nicht möglich', true) } };

/* ---------- eigenes Programmfenster ---------- */
function nativeReady() {
  if (!window.pywebview || !window.pywebview.api || document.body.classList.contains('native')) return;
  document.body.classList.add('native');
  const w = window.pywebview.api;
  const maxTitle = m => $('#winMax').setAttribute('aria-label', m ? 'Verkleinern' : 'Maximieren');
  $('#winMin').onclick = () => w.minimize();
  $('#winMax').onclick = async () => maxTitle(await w.toggle_max());
  $('#winClose').onclick = quit;
  $$('.dragzone').forEach(z => {
    z.addEventListener('mousedown', e => { if (e.button === 0 && e.detail < 2) { e.preventDefault(); w.drag() } });
    z.addEventListener('dblclick', async e => { e.preventDefault(); maxTitle(await w.toggle_max()) });
  });
  $$('.grips i').forEach(g => g.addEventListener('mousedown', e => { if (e.button === 0) { e.preventDefault(); w.resize(g.dataset.edge) } }));
  w.is_max().then(maxTitle).catch(() => {});
}
addEventListener('pywebviewready', nativeReady); nativeReady();

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
applyTheme(S.theme);
(async function init() {
  try {
    const info = await api('/api/info'); S.info = info;
    if (info.intro === false) { clearTimeout(splashTimer); const sp = $('#splash'); if (sp) sp.remove() }
    applyTheme(info.theme);
    fillTransitions(info.transitions || []);
    S.settings = info.settings; S.outdir = info.outdir; showDir();
    S.presets = info.presets || []; renderPresets();
    $('#verText').textContent = info.version;
    $('#ffDot').className = 'dot ' + (info.ffmpeg ? 'ok' : 'bad');
    $('#ffText').textContent = info.ffmpeg ? 'FFmpeg bereit' : 'FFmpeg fehlt';
    $('#ffWarn').hidden = info.ffmpeg;
    drawFiles(); changed(); timeline();
    // Encoder-Prüfung läuft im Hintergrund – nachladen
    const recheck = async (n) => {
      const i = await api('/api/info').catch(() => null); if (!i) return;
      S.info.encoders = i.encoders; S.info.hw_done = i.hw_done; S.info.auto_enc = i.auto_enc; renderEnc(); updateGo();
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

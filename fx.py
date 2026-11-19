"""Bild-Effekte für ffmpeg_encode Studio (ab 1.3.0).

Partikel-Effekte (Funken, Schnee, Regen, Lichtkreise …) werden EINMAL als nahtlos kachelbare Graustufen-Felder
(numpy) gezeichnet und im Video nur noch mit dem FFmpeg-Filter `scroll` verschoben – das ist schnell, auch in 4K.
  Felder (3 Tiefen) -> scroll -> aufhellen -> (Flackern/Funkeln multiplizieren) -> Deckkraft -> Maske
  Farbe (aus dem Bild / eigene / Regenbogen) -> alphamerge -> overlay
Lichtlinien entlang einer gezeichneten Linie: Streifen L×T, mit `remap` gebogen (wie der Visualizer).
Fließen + 3D-Kamerafahrt: `displace` mit Verschiebe-Karten (Rauschen bzw. Tiefenkarte der KI) in RGB (gbrp).
Kamera Zoom/Schwenk: `perspective` (pixelgenau weich, kein Ruckeln wie bei zoompan).
"""
import math
import random
import re
import threading
from pathlib import Path

try:
    import numpy as np
    import cv2
except Exception:  # noqa: BLE001
    np = cv2 = None

EFFECTS = [
    ('none', 'Kein Effekt', 'Aus', 'Das Bild bleibt, wie es ist.'),
    ('streaks', 'Lichtlinien', 'Linien', 'Leuchtende Linien ziehen durchs Bild – oder genau entlang deiner gezeichneten Linie bzw. deines Rings.'),
    ('sparks', 'Funken', 'Funken', 'Glühende Funken steigen auf und flackern.'),
    ('glitter', 'Glitzern', 'Glitzer', 'Kleine Lichtsterne funkeln an Ort und Stelle.'),
    ('bokeh', 'Lichtkreise', 'Bokeh', 'Weiche, unscharfe Lichtkreise schweben langsam – in den Farben des Bildes.'),
    ('dust', 'Schwebeteilchen', 'Staub', 'Feiner Staub schwebt schimmernd durchs Licht.'),
    ('snow', 'Schnee', 'Schnee', 'Schneeflocken fallen in drei Tiefen.'),
    ('rain', 'Regen', 'Regen', 'Regenfäden fallen schräg durchs Bild.'),
    ('fog', 'Nebel', 'Nebel', 'Weicher Nebel zieht langsam vorbei.'),
    ('flow', 'Fließen', 'Fließen', 'Die markierte Stelle bewegt sich wie Wasser oder flirrende Luft.'),
]
EFFECT_IDS = [e[0] for e in EFFECTS]
CAMS = [('none', 'Ruhig', 'Das Bild steht still.'),
        ('zoom', 'Sanfter Zoom', 'Langsames Heran- und Wegzoomen.'),
        ('pan', 'Langsamer Schwenk', 'Die Kamera gleitet sanft hin und her.'),
        ('depth', '3D-Kamerafahrt (KI)', 'Die KI erkennt, was vorne und hinten ist – Vordergrund bewegt sich stärker als der Hintergrund.')]
CAM_IDS = [c[0] for c in CAMS]
COLOR_MODES = ('auto', 'solid', 'rainbow')
RAINBOW = ['#ff3b3b', '#ff9f1c', '#ffe14d', '#3ddc84', '#2ec5ff', '#5b6cff', '#c04dff']

DEFAULTS = {
    'fx': 'none', 'fxColorMode': 'auto', 'fxColor': '#ffd27a', 'fxAmount': 50, 'fxSpeed': 50, 'fxSize': 50, 'fxAlpha': 85,
    'fxAngle': -20, 'fxBeat': True, 'fxSeed': 11,
    'cam': 'none', 'camAmount': 50, 'camSpeed': 40,
    # Wo der Effekt wirkt (gilt nur für dieses Video / Projekt, nicht für Vorlagen)
    'fxArea': 'full', 'fxMask': '', 'fxPath': [], 'fxClosed': False, 'fxThick': 8.0, 'fxFeather': 1.0,
    'fxX': 0.0, 'fxY': 0.0, 'fxW': 100.0, 'fxH': 100.0,
}
MARK_KEYS = ('fxArea', 'fxMask', 'fxPath', 'fxClosed', 'fxThick', 'fxFeather', 'fxX', 'fxY', 'fxW', 'fxH')
LIMITS = {'fxAmount': (1, 100), 'fxSpeed': (1, 100), 'fxSize': (1, 100), 'fxAlpha': (5, 100), 'fxAngle': (-75, 75),
          'fxSeed': (0, 999999), 'camAmount': (1, 100), 'camSpeed': (1, 100), 'fxThick': (2, 40), 'fxFeather': (0, 5),
          'fxX': (0, 98), 'fxY': (0, 98), 'fxW': (2, 100), 'fxH': (2, 100)}
HEX = re.compile(r'#[0-9a-fA-F]{6}')


def clean(s, out):
    for k, v in DEFAULTS.items():
        val = (s or {}).get(k, v)
        if k == 'fxPath':
            pts = []
            for q in (val if isinstance(val, list) else [])[:400]:
                try:
                    pts.append([min(max(float(q[0]), -0.2), 1.2), min(max(float(q[1]), -0.2), 1.2)])
                except (TypeError, ValueError, IndexError):
                    pass
            val = pts
        elif k in ('fx', 'fxColorMode', 'fxColor', 'cam', 'fxArea', 'fxMask'):
            val = str(val or '')
        elif isinstance(v, bool):
            val = bool(val)
        elif k in LIMITS:
            try:
                val = float(val)
            except (TypeError, ValueError):
                val = v
            lo, hi = LIMITS[k]
            val = min(max(val, lo), hi)
            if isinstance(v, int) and not isinstance(v, bool):
                val = int(round(val))
        out[k] = val
    if out['fx'] not in EFFECT_IDS:
        out['fx'] = 'none'
    if out['cam'] not in CAM_IDS:
        out['cam'] = 'none'
    if out['fxColorMode'] not in COLOR_MODES:
        out['fxColorMode'] = 'auto'
    if not HEX.fullmatch(out['fxColor']):
        out['fxColor'] = DEFAULTS['fxColor']
    if out['fxArea'] not in ('full', 'mask', 'path'):
        out['fxArea'] = 'full'
    if not re.fullmatch(r'[0-9a-f]{0,32}', out['fxMask']):
        out['fxMask'] = ''
    if out['fxArea'] == 'mask' and not out['fxMask']:
        out['fxArea'] = 'full'
    if out['fxArea'] == 'path' and len(out['fxPath']) < 2:
        out['fxArea'] = 'full'
    out['fxW'] = min(out['fxW'], 100 - out['fxX'])
    out['fxH'] = min(out['fxH'], 100 - out['fxY'])
    return out


def active(s):
    return s.get('fx', 'none') != 'none' or s.get('cam', 'none') != 'none'


def even(v):
    return max(2, int(v) // 2 * 2)


# ---------- Farben aus dem Bild ----------
def hexc(c):
    return '#%02x%02x%02x' % tuple(int(max(0, min(255, round(v)))) for v in c)


def rgb(h):
    return [int(h[i:i + 2], 16) for i in (1, 3, 5)]


def mix(a, b, k):
    return [x * (1 - k) + y * k for x, y in zip(a, b)]


def image_colors(img_path):
    """3–4 kräftige Farben + mittlere Farbe aus dem Bild (für „Farben aus dem Bild“)."""
    try:
        img = cv2.imdecode(np.fromfile(str(img_path), np.uint8), cv2.IMREAD_COLOR)
        small = cv2.resize(img, (64, 64), interpolation=cv2.INTER_AREA)
    except Exception:  # noqa: BLE001
        return ['#f5b544', '#ff5fa2', '#7cc8ff'], '#c8b8a0'
    rgbimg = cv2.cvtColor(small, cv2.COLOR_BGR2RGB).reshape(-1, 3).astype(np.float32)
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(np.float32)
    avg = hexc(rgbimg.mean(0))
    vivid = rgbimg[(hsv[:, 1] > 80) & (hsv[:, 2] > 110)]
    if len(vivid) < 24:
        vivid = rgbimg[hsv[:, 2] > 90]
    if len(vivid) < 8:
        return ['#f5b544', '#ff5fa2', '#7cc8ff'], avg
    k = min(4, len(vivid) // 6)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    cv2.setRNGSeed(5)
    _, lab, cen = cv2.kmeans(vivid, k, None, crit, 3, cv2.KMEANS_PP_CENTERS)
    order = np.argsort(-np.bincount(lab.ravel(), minlength=k))
    cols = []
    for i in order:
        c = cen[i]
        h, s, v = cv2.cvtColor(np.uint8([[c]]), cv2.COLOR_RGB2HSV)[0, 0]
        c = cv2.cvtColor(np.uint8([[[h, max(s, 150), max(v, 220)]]]), cv2.COLOR_HSV2RGB)[0, 0]  # etwas leuchtender
        cols.append(hexc(c))
    return cols[:4] if len(cols) > 1 else cols * 2, avg


def palette(s, img_colors):
    fx = s['fx']
    if s['fxColorMode'] == 'solid':
        return [s['fxColor'], s['fxColor']]
    if s['fxColorMode'] == 'rainbow':
        return RAINBOW
    cols, avg = img_colors
    white = [255, 255, 255]
    if fx in ('snow', 'rain', 'fog', 'dust'):
        a = mix(rgb(avg), white, 0.78 if fx != 'dust' else 0.6)
        b = mix(rgb(cols[0]), white, 0.7)
        return [hexc(a), hexc(b)]
    if fx == 'sparks':
        def hue_dist(c):
            h = int(cv2.cvtColor(np.uint8([[rgb(c)]]), cv2.COLOR_RGB2HSV)[0, 0, 0])
            return abs((h + 15) % 180 - 25)                      # Abstand zu Orange
        warm = sorted(cols, key=hue_dist)[0]
        return [hexc(mix(rgb(warm), [255, 150, 40], 0.55)), hexc(mix(rgb(warm), [255, 236, 170], 0.6))]
    return cols


# ---------- Bereich ----------
def area(s, W, H):
    """(ox, oy, bw, bh) des Effekt-Bereichs in Pixeln."""
    if s['fxArea'] == 'mask':
        bw, bh = even(W * s['fxW'] / 100), even(H * s['fxH'] / 100)
        return min(int(W * s['fxX'] / 100), W - bw), min(int(H * s['fxY'] / 100), H - bh), bw, bh
    if s['fxArea'] == 'path':
        t = thick_px(s, H)
        xs = [min(max(q[0], 0), 1) * W for q in s['fxPath']]
        ys = [min(max(q[1], 0), 1) * H for q in s['fxPath']]
        x0, y0 = max(0, int(min(xs) - t * 1.5)), max(0, int(min(ys) - t * 1.5))
        x1, y1 = min(W, int(max(xs) + t * 1.5)), min(H, int(max(ys) + t * 1.5))
        bw, bh = even(max(x1 - x0, 8)), even(max(y1 - y0, 8))
        return min(x0, W - bw), min(y0, H - bh), bw, bh
    return 0, 0, W, H


def thick_px(s, H):
    return max(4, int(H * s['fxThick'] / 100))


def path_band_mask(s, W, H, ox, oy, bw, bh):
    """Für Effekte (außer Lichtlinien) auf einer Linie: breites Band entlang der Linie als Maske."""
    m = np.zeros((bh, bw), np.uint8)
    pts = np.array([[q[0] * W - ox, q[1] * H - oy] for q in s['fxPath']], np.int32)
    cv2.polylines(m, [pts], bool(s['fxClosed']), 255, thickness=max(2, thick_px(s, H) * 2), lineType=cv2.LINE_AA)
    return cv2.GaussianBlur(m, (0, 0), max(1.0, thick_px(s, H) * 0.35))


# ---------- nahtlose Felder zeichnen ----------
def stamp(c, cx, cy, patch, wrap=True, wrap_y=None):
    """patch (h×w float) mit Mitte bei (cx, cy) per Maximum eintragen – an den Rändern umlaufend (nahtlos)."""
    H, W = c.shape
    ph, pw = patch.shape
    x0, y0 = int(round(cx - pw / 2)), int(round(cy - ph / 2))
    wy = wrap if wrap_y is None else wrap_y
    offs = [(dx, dy) for dx in ((-W, 0, W) if wrap else (0,)) for dy in ((-H, 0, H) if wy else (0,))]
    for dx, dy in offs:
        xa, ya = x0 + dx, y0 + dy
        if xa >= W or ya >= H or xa + pw <= 0 or ya + ph <= 0:
            continue
        sx, sy = max(0, -xa), max(0, -ya)
        ex, ey = min(pw, W - xa), min(ph, H - ya)
        sub = c[ya + sy:ya + ey, xa + sx:xa + ex]
        np.maximum(sub, patch[sy:ey, sx:ex], out=sub)


def dot(r, soft=1.0):
    R = max(1, int(math.ceil(r * 2.6)))
    y, x = np.mgrid[-R:R + 1, -R:R + 1].astype(np.float32)
    d = np.sqrt(x * x + y * y)
    core = np.clip(1.0 - d / max(r, 0.6), 0, 1) ** 1.5
    halo = np.exp(-(d * d) / (2 * (r * 1.1 * soft) ** 2)) * 0.55
    return np.maximum(core, halo)


def disc(r, edge=0.18, ring=0.25):
    R = int(math.ceil(r * 1.08)) + 2
    y, x = np.mgrid[-R:R + 1, -R:R + 1].astype(np.float32)
    d = np.sqrt(x * x + y * y) / r
    body = np.clip((1 - d) / edge, 0, 1)
    rim = np.exp(-((d - 0.93) ** 2) / 0.004) * ring
    return np.clip(body * (0.62 + 0.38 * d) + rim, 0, 1)


def star(r):
    p = dot(r * 0.8)
    R = p.shape[0] // 2
    L = int(r * 4)
    big = np.zeros((2 * L + 1, 2 * L + 1), np.float32)
    c = L
    big[c - R:c + R + 1, c - R:c + R + 1] = p
    t = np.arange(-L, L + 1, dtype=np.float32)
    fall = np.exp(-np.abs(t) / (r * 1.1)) * 0.9
    big[c, :] = np.maximum(big[c, :], fall)
    big[:, c] = np.maximum(big[:, c], fall)
    if r > 2:
        big[c - 1:c + 2, :] = np.maximum(big[c - 1:c + 2, :], fall * 0.45)
        big[:, c - 1:c + 2] = np.maximum(big[:, c - 1:c + 2], (fall * 0.45)[:, None])
    return big


def segment(length, width, angle, tail=1.6, both=False):
    """Leuchtender Strich (Kopf hell, Schweif läuft aus) in Richtung angle (Grad, 0 = nach rechts)."""
    a = math.radians(angle)
    ux, uy = math.cos(a), math.sin(a)
    R = int(length / 2 + width * 3) + 2
    y, x = np.mgrid[-R:R + 1, -R:R + 1].astype(np.float32)
    t = (x * ux + y * uy) / length + 0.5            # 0 = Schweif, 1 = Kopf
    d = -x * uy + y * ux
    inside = (t >= 0) & (t <= 1)
    prof = np.exp(-(d * d) / (2 * max(width, 0.5) ** 2))
    along = np.clip(t, 0, 1) ** tail if not both else np.sin(np.clip(t, 0, 1) * math.pi)
    return np.where(inside, prof * along, 0).astype(np.float32)


def noise(h, w, cells, rng, contrast=1.0):
    """Weiches, nahtlos kachelbares Rauschen 0..1 (cells = Anzahl Wolken quer)."""
    gw = max(2, int(cells))
    gh = max(2, int(round(cells * h / max(w, 1))))
    g = rng.random((gh, gw)).astype(np.float32)
    big = np.tile(g, (3, 3))
    up = cv2.resize(big, (w * 3, h * 3), interpolation=cv2.INTER_CUBIC)[h:2 * h, w:2 * w]
    up = (up - up.min()) / max(1e-6, up.max() - up.min())
    if contrast != 1.0:
        up = np.clip((up - 0.5) * contrast + 0.5, 0, 1)
    return up


def to8(a):
    return (np.clip(a, 0, 1) * 255).astype(np.uint8)


def unit(H):
    return H / 1080.0


def build_layers(s, bw, bh, H, fps, rng):
    """Liefert (Liste von Graustufen-Ebenen, Liste von (op, h_speed, v_speed)) für Partikel-Effekte.
    Geschwindigkeiten als Anteil der Ebenen-Breite/-Höhe pro Videobild (für den scroll-Filter)."""
    fx = s['fx']
    u = unit(H)
    amt = s['fxAmount'] / 50.0
    size = 0.4 + s['fxSize'] / 50.0 * 0.6          # 0,4 … 1,6
    spd = 0.15 + s['fxSpeed'] / 50.0                # 0,17 … 2,15
    mp = bw * bh / 1e6
    layers, ops = [], []

    def vel(px_per_sec, ang):
        """Bewegung in Richtung ang (0° = rechts, 90° = nach unten) -> scroll-Werte
        (scroll: positiv = Inhalt wandert nach links bzw. oben)."""
        a = math.radians(ang)
        return (-px_per_sec * math.cos(a) / fps / bw, -px_per_sec * math.sin(a) / fps / bh)

    def field():
        return np.zeros((bh, bw), np.float32)
    if fx in ('sparks', 'snow', 'dust', 'bokeh'):
        cfg = {
            # (Anzahl pro MP, Radius px@1080, Helligkeit, Geschwindigkeit px/s@1080, Richtung°)  für fern/mittel/nah
            'sparks': [(150, 1.6, .8, 120, -88), (70, 2.4, .95, 210, -85), (24, 3.5, 1.0, 330, -82)],
            'snow': [(170, 1.3, .55, 45, 98), (70, 2.4, .8, 85, 100), (16, 4.6, .95, 150, 104)],
            'dust': [(190, 1.2, .62, 14, 20), (90, 1.9, .8, 22, 12), (26, 2.8, .95, 34, 30)],
            'bokeh': [(10, 26, .32, 10, -85), (5, 44, .42, 16, -80), (2, 70, .5, 24, -95)],
        }[fx]
        for n, r, br, v, ang in cfg:
            f = field()
            count = max(3, int(n * mp * amt))
            rr = r * u * size
            for _ in range(count):
                rad = rr * (0.6 + rng.random() * 0.8)
                if fx == 'bokeh':
                    p = disc(rad)
                elif fx == 'sparks':                          # Funke mit kurzer Leuchtspur nach unten
                    p = segment(rad * (5 + rng.random() * 5), rad * 0.55, ang + (rng.random() - .5) * 14, tail=1.3)
                else:
                    p = dot(rad, 1.4 if fx == 'snow' and r > 3 else 1.0)
                stamp(f, rng.random() * bw, rng.random() * bh, p * (br * (0.7 + rng.random() * 0.3)))
            if fx == 'snow' and r > 3:
                f = cv2.GaussianBlur(f, (0, 0), 1.2 * u * size)
            if fx == 'sparks':
                f = np.maximum(f, cv2.GaussianBlur(f, (0, 0), 3 * u * size) * 1.4)     # Glühen
            layers.append(f)
            ops.append(('lighten',) + vel(v * u * spd, ang))
        ops[0] = ('base',) + ops[0][1:]
        if fx == 'sparks':                         # Flackern + nach oben ausblenden
            n = 0.45 + 0.55 * noise(bh, bw, max(4, bw / (90 * u)), rng, 1.8)
            layers.append(n)
            ops.append(('multiply', 0.0, 260 * u * spd / fps / bh))
            g = np.linspace(0.15, 1.0, bh, dtype=np.float32)[:, None] ** 0.7 * np.ones((1, bw), np.float32)
            layers.append(g)
            ops.append(('multiply', 0.0, 0.0))
        if fx == 'dust':                           # Schimmern wie Staub im Lichtstrahl
            layers.append(np.clip(0.3 + noise(bh, bw, 5, rng, 1.6), 0, 1))
            ops.append(('multiply', 18 * u * spd / fps / bw, 0.0))
    elif fx == 'glitter':
        f = field()
        for _ in range(max(6, int(70 * mp * amt))):
            stamp(f, rng.random() * bw, rng.random() * bh, star((3.2 + rng.random() * 5.0) * u * size) * (0.75 + rng.random() * 0.25))
        layers.append(f)
        ops.append(('base', 0.0, 0.0))
        layers.append(np.clip(noise(bh, bw, max(6, bw / (110 * u)), rng, 2.0) * 1.15, 0, 1))
        ops.append(('multiply', 70 * u * spd / fps / bw, 40 * u * spd / fps / bh))
    elif fx == 'rain':
        ang = 90 + s['fxAngle'] * 0.5
        for n, ln, wd, br, v in [(240, 34, 0.6, .4, 900), (110, 60, 0.9, .6, 1400), (30, 110, 1.4, .75, 2100)]:
            f = field()
            p = segment(ln * u * size, wd * u * size, ang, both=True)
            for _ in range(max(4, int(n * mp * amt))):
                stamp(f, rng.random() * bw, rng.random() * bh, p * br * (0.6 + rng.random() * 0.4))
            layers.append(f)
            ops.append(('lighten',) + vel(v * u * spd, ang))
        ops[0] = ('base',) + ops[0][1:]
    elif fx == 'fog':
        for cells, v, k in [(3, 18, 1.0), (6, -30, 0.8)]:
            n = np.clip((noise(bh, bw, cells * max(1.0, bw / bh), rng, 1.4) - 0.3) * 1.45, 0, 1) * k
            layers.append(np.clip(n * (0.22 + amt * 0.22), 0, 1))
            ops.append(('screen', v * u * spd / fps / bw, 0.0))
        ops[0] = ('base',) + ops[0][1:]
    elif fx == 'streaks':                         # Lichtlinien quer durchs Bild (Richtung = Winkel)
        ang = float(s['fxAngle'])
        for n, ln, wd, br, v in [(14, 260, 1.4, .55, 420), (7, 420, 2.4, .85, 700)]:
            f = field()
            p = segment(ln * u * size, wd * u * size, ang, tail=1.8)
            for _ in range(max(2, int(n * mp * amt))):
                stamp(f, rng.random() * bw, rng.random() * bh, p * br)
            f = np.maximum(f, cv2.GaussianBlur(f, (0, 0), 4 * u * size) * 0.8)   # Leuchten
            layers.append(f)
            ops.append(('lighten',) + vel(v * u * spd, ang))
        ops[0] = ('base',) + ops[0][1:]
    return [to8(l) for l in layers], ops


def strip_layer(s, L, T, H, fps, rng, closed=False):
    """Lichtlinien entlang eines Pfads: gerader Streifen L×T mit wandernden Leuchtstrichen.
    Die Linie selbst ist die UNTERSTE Zeile des Streifens (remap spiegelt den Streifen auf beide Seiten)."""
    u = unit(H)
    size = 0.4 + s['fxSize'] / 50.0 * 0.6
    spd = 0.15 + s['fxSpeed'] / 50.0
    f = np.zeros((T, L), np.float32)
    n = max(2, int(L / (200 * u) * s['fxAmount'] / 50))
    p = segment(min(L * 0.45, 240 * u * size), max(1.2, 2.2 * u * size, T * 0.07), 0, tail=1.8)
    for k in range(n):
        x = (k + rng.random() * 0.6) * L / n
        stamp(f, x, T - 1, p * (0.75 + rng.random() * 0.25), wrap=True, wrap_y=False)
    glow = cv2.GaussianBlur(np.vstack([f, f[::-1]]), (0, 0), max(1.5, T * 0.22))[:T] * 1.6   # Leuchten (gespiegelt berechnet)
    f = np.maximum(f, glow)
    if not closed:                                  # an den Linienenden weich ausblenden (keine Bögen)
        e = max(4, int(L * 0.04))
        ramp = np.ones(L, np.float32)
        ramp[:e] = np.linspace(0, 1, e)
        ramp[-e:] = np.linspace(1, 0, e)
        f *= ramp[None, :]
    return to8(f), -(420 * u * spd) / fps / L


# ---------- Tiefen-KI (Depth Anything V2 Small) ----------
class Depth:
    def __init__(self, folder):
        self.folder = Path(folder) if folder else None
        self.sess = None
        self.error = ''
        self.lock = threading.Lock()
        self.cache = {}

    def file(self):
        f = self.folder / 'depth_anything_v2_small.onnx' if self.folder else None
        return f if f and f.is_file() else None

    def available(self):
        return self.file() is not None

    def load(self):
        if self.sess is not None:
            return True
        f = self.file()
        if not f:
            return False
        try:
            import onnxruntime as ort
            prov = [p for p in ('DmlExecutionProvider', 'CUDAExecutionProvider') if p in ort.get_available_providers()] + ['CPUExecutionProvider']
            so = ort.SessionOptions()
            so.log_severity_level = 3
            try:
                self.sess = ort.InferenceSession(str(f), so, providers=prov)
            except Exception:  # noqa: BLE001
                self.sess = ort.InferenceSession(str(f), so, providers=['CPUExecutionProvider'])
            return True
        except Exception as ex:  # noqa: BLE001
            self.error = str(ex)
            self.sess = None
            return False

    def estimate(self, bgr):
        """Tiefenkarte 0..1 (1 = nah) in Bildgröße. Rückgabe (karte, 'ki'|'einfach')."""
        h, w = bgr.shape[:2]
        if self.load():
            try:
                with self.lock:
                    k = 518 / max(h, w)
                    nh, nw = max(14, int(round(h * k / 14)) * 14), max(14, int(round(w * k / 14)) * 14)
                    x = cv2.resize(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB), (nw, nh), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
                    x = (x - np.array([0.485, 0.456, 0.406], np.float32)) / np.array([0.229, 0.224, 0.225], np.float32)
                    x = x.transpose(2, 0, 1)[None].astype(np.float32)
                    inp = self.sess.get_inputs()[0]
                    if 'float16' in inp.type:
                        x = x.astype(np.float16)
                    d = np.squeeze(self.sess.run(None, {inp.name: x})[0]).astype(np.float32)
                lo, hi = np.percentile(d, 2), np.percentile(d, 98)
                d = np.clip((d - lo) / max(hi - lo, 1e-6), 0, 1)
                return cv2.resize(d, (w, h), interpolation=cv2.INTER_CUBIC), 'ki'
            except Exception as ex:  # noqa: BLE001
                self.error = str(ex)
        return simple_depth(bgr), 'einfach'


def simple_depth(bgr):
    """Ersatz ohne KI: unten = nah, oben = fern, scharfe/helle Motive etwas näher."""
    h, w = bgr.shape[:2]
    g = cv2.cvtColor(cv2.resize(bgr, (256, max(2, int(256 * h / w)))), cv2.COLOR_BGR2GRAY).astype(np.float32)
    detail = cv2.GaussianBlur(np.abs(cv2.Laplacian(g, cv2.CV_32F)), (0, 0), 6)
    detail /= max(detail.max(), 1e-6)
    y = np.linspace(0, 1, g.shape[0], dtype=np.float32)[:, None] * np.ones((1, g.shape[1]), np.float32)
    d = 0.65 * y + 0.35 * detail
    d = (d - d.min()) / max(d.max() - d.min(), 1e-6)
    return cv2.resize(d, (w, h), interpolation=cv2.INTER_CUBIC)


# ---------- Dateien für FFmpeg vorbereiten ----------
def prepare(s, W, H, fps, dur, workdir, tag, still_png, first_index, masks, depth=None, mark=None, img_colors=None):
    """Erzeugt die Zusatz-Dateien und liefert (Eingabedateien, info) für graph().
    workdir None = nur Platzhalter (für die Befehlsanzeige)."""
    info = {'inputs': {}, 'notes': []}
    files = []
    if not active(s):
        return files, info
    fx = s['fx']

    def add(name, kind):
        info['inputs'][kind] = '[%d:v]' % (first_index + len(files))
        files.append(name)
    if workdir is None or np is None:
        if s['cam'] == 'depth':
            add('tiefe.png', 'depth')
        if fx == 'flow':
            add('fliessen.png', 'flow')
        elif fx == 'streaks' and s['fxArea'] == 'path':
            add('linien.png', 'strip')
            add('karte-x.pgm', 'xm')
            add('karte-y.pgm', 'ym')
            info['strip'] = {'L': 1000, 'T': 40, 'speed': -0.01}
            info['area'] = (0, 0, 100, 100)
        elif fx != 'none':
            add('effekt.png', 'field')
            info['ops'] = [('base', 0, -0.002)]
        if fx not in ('none',) and s['fxArea'] != 'full' and not (fx == 'streaks' and s['fxArea'] == 'path'):
            add('effekt-maske.png', 'mask')
        info.setdefault('area', area(s, W, H))
        info['colors'] = ['#ffffff', '#ffd27a']
        return files, info
    wd = Path(workdir)
    rng = np.random.default_rng(int(s['fxSeed']) + 1)
    cols = img_colors or image_colors(still_png)
    info['colors'] = palette(s, cols) if fx != 'none' else []
    # Kamera: Tiefenkarte (klein, 3 gleiche Kanäle -> exakt in RGB)
    if s['cam'] == 'depth':
        bgr = cv2.imdecode(np.fromfile(str(still_png), np.uint8), cv2.IMREAD_COLOR)
        d, how = (depth.estimate(bgr) if depth else (simple_depth(bgr), 'einfach'))
        info['depth_method'] = how
        dw = 384 if W >= H else 216
        dh = even(dw * H / W)
        small = cv2.resize(cv2.GaussianBlur(d, (0, 0), max(1.0, min(d.shape) / 260)), (dw, dh), interpolation=cv2.INTER_AREA)
        p = wd / ('tiefe-%s.png' % tag)
        cv2.imencode('.png', to8(small))[1].tofile(str(p))
        add(str(p), 'depth')
        info['depth_size'] = (dw, dh)
    if fx == 'none':
        return files, info
    ox, oy, bw, bh = area(s, W, H)
    info['area'] = (ox, oy, bw, bh)
    if fx == 'flow':
        u = unit(H)
        cells = max(3, bw / ((40 + s['fxSize'] * 2.4) * u))
        amp = (1.5 + s['fxAmount'] / 100 * 9) * u
        nx = noise(bh, bw, cells, rng)
        ny = noise(bh, bw, cells, rng)
        k = min(120, amp) / 0.5
        # beide Karten untereinander in eine Datei (3 gleiche Kanäle)
        both = np.vstack([128 + (nx - 0.5) * k, 128 + (ny - 0.5) * k])
        g = np.clip(both, 0, 255).astype(np.uint8)
        p = wd / ('fliessen-%s.png' % tag)
        cv2.imencode('.png', g)[1].tofile(str(p))
        add(str(p), 'flow')
        spd = 0.15 + s['fxSpeed'] / 50.0
        info['flow'] = (34 * u * spd / fps / bw, 26 * u * spd / fps / bh)
    elif fx == 'streaks' and s['fxArea'] == 'path':
        T = thick_px(s, H)
        xp, yp = wd / ('fx-xmap-%s.pgm' % tag), wd / ('fx-ymap-%s.pgm' % tag)
        ox, oy, bw, bh, L, T = mark.path_maps(s['fxPath'], s['fxClosed'], True, W, H, T, xp, yp)
        img, speed = strip_layer(s, L, T, H, fps, rng, s['fxClosed'])
        p = wd / ('linien-%s.png' % tag)
        cv2.imencode('.png', img)[1].tofile(str(p))
        add(str(p), 'strip')
        add(str(xp), 'xm')
        add(str(yp), 'ym')
        info['strip'] = {'L': L, 'T': T, 'speed': speed}
        info['area'] = (ox, oy, bw, bh)
    else:
        layers, ops = build_layers(s, bw, bh, H, fps, rng)
        p = wd / ('effekt-%s.png' % tag)
        cv2.imencode('.png', np.vstack(layers))[1].tofile(str(p))
        add(str(p), 'field')
        info['ops'] = ops
    # Maske (Fläche gemalt bzw. Band entlang einer Linie)
    if not (fx == 'streaks' and s['fxArea'] == 'path') and s['fxArea'] != 'full':
        mp = wd / ('fx-maske-%s.png' % tag)
        if s['fxArea'] == 'mask':
            src = masks.get(s['fxMask'])
            if src and Path(src).is_file() and mark:
                mark.mask_crop(src, W, H, ox, oy, bw, bh, mp, s['fxFeather'])
            else:
                mp = None
        else:
            cv2.imencode('.png', path_band_mask(s, W, H, ox, oy, bw, bh))[1].tofile(str(mp))
        if mp:
            add(str(mp), 'mask')
    return files, info


# ---------- FFmpeg-Filtergraph ----------
def esc(e):
    return e.replace(',', '\\,')


def graph(s, W, H, fps, dur, info, chain, cmdfile=None):
    """Hängt Kamera + Effekt an die Bild-Kette an. Rückgabe (Teile, neue Kette)."""
    parts = []
    if not active(s):
        return parts, chain
    n = [0]
    D = dur + 1

    def lab(p='f'):
        n[0] += 1
        return '[x%s%d]' % (p, n[0])

    def still(src, fmt):
        return '%sformat=%s,loop=loop=-1:size=1,setpts=N/%d/TB,trim=duration=%.3f' % (src, fmt, fps, D)
    inp = info['inputs']
    # ---- Kamera ----
    P = (40 - s['camSpeed'] * 0.32) * fps          # Dauer einer Bewegung in Videobildern (≈ 8–40 s)
    if s['cam'] in ('zoom', 'pan', 'depth'):
        if s['cam'] == 'zoom':
            A = 0.02 + s['camAmount'] / 100 * 0.14
            z = '(%.5f*(1-cos(2*PI*on/%.2f))/2)' % (A, P)
            dx = '0'
        elif s['cam'] == 'pan':
            z = '%.5f' % (0.05 + s['camAmount'] / 100 * 0.1)
            dx = '(W*%s/2*sin(2*PI*on/%.2f))' % (z, P)
        else:
            z = '(0.035+%.5f*(1-cos(2*PI*on/%.2f))/2)' % (0.04 * s['camAmount'] / 100, P * 2)
            dx = '0'
        persp = ('perspective=x0=W*{z}/2+{dx}:y0=H*{z}/2:x1=W-W*{z}/2+{dx}:y1=H*{z}/2:x2=W*{z}/2+{dx}:y2=H-H*{z}/2:'
                 'x3=W-W*{z}/2+{dx}:y3=H-H*{z}/2:interpolation=linear:eval=frame').format(z=z, dx=dx)
        if s['cam'] == 'depth' and 'depth' in inp:
            A = (0.005 + s['camAmount'] / 100 * 0.022) * W          # größte Verschiebung (nah) in Pixeln
            K = min(A, 120) / 127.0
            ph = '2*PI*T/%.3f' % (P / fps)
            dw, dh = info.get('depth_size', (384, 216))
            a, b, mx, my, base, out = lab(), lab(), lab('m'), lab('m'), lab(), lab()
            parts.append('%s,split=2%s%s' % (still(inp['depth'], 'gray'), a, b))
            for src, dst, fn, k in ((a, mx, 'sin', K), (b, my, 'cos', K * 0.35)):
                e = "128+(lum(X,Y)-128)*%.5f*%s(%s)" % (k, fn, ph)
                parts.append("%sgeq=lum='%s',scale=%d:%d:flags=bicubic,format=gbrp%s" % (src, esc(e), W, H, dst))
            parts.append('%s,format=gbrp%s' % (chain, base))
            parts.append('%s%s%sdisplace=edge=smear,%s,format=yuv420p%s' % (base, mx, my, persp, out))
            chain = '%snull' % out
            _ = (dw, dh)
        else:
            chain = '%s,%s' % (chain, persp)
    fx = s['fx']
    if fx == 'none':
        return parts, chain
    ox, oy, bw, bh = info['area']
    full = (ox, oy, bw, bh) == (0, 0, W, H)
    # ---- Fließen ----
    if fx == 'flow':
        hs, vs = info['flow']
        f, fa, fb, mx, my = lab(), lab(), lab(), lab('m'), lab('m')
        parts.append('%s,split=2%s%s' % (still(inp['flow'], 'gray'), fa, fb))
        parts.append('%scrop=%d:%d:0:0,scroll=horizontal=%.6f:vertical=%.6f,format=gbrp%s' % (fa, bw, bh, hs, vs * 0.4, mx))
        parts.append('%scrop=%d:%d:0:%d,scroll=horizontal=%.6f:vertical=%.6f,format=gbrp%s' % (fb, bw, bh, bh, -hs * 0.5, vs, my))
        base, out = lab(), lab()
        if full and 'mask' not in inp:
            parts.append('%s,format=gbrp%s' % (chain, base))
            parts.append('%s%s%sdisplace=edge=smear,format=yuv420p%s' % (base, mx, my, out))
        else:
            keep, cut, disp, mk, dm = lab(), lab(), lab(), lab('k'), lab()
            parts.append('%s,split=2%s%s' % (chain, keep, cut))
            parts.append('%scrop=%d:%d:%d:%d,format=gbrp%s' % (cut, bw, bh, ox, oy, base))
            parts.append('%s%s%sdisplace=edge=smear%s' % (base, mx, my, disp))
            if 'mask' in inp:
                parts.append('%s,scale=%d:%d%s' % (still(inp['mask'], 'gray'), bw, bh, mk))
                parts.append('%s%salphamerge%s' % (disp, mk, dm))
                disp = dm
            parts.append('%s%soverlay=%d:%d:shortest=0:eof_action=pass,format=yuv420p%s' % (keep, disp, ox, oy, out))
        return parts, '%snull' % out
    # ---- Leucht-/Partikel-Ebene (Graustufen) ----
    G = lab('g')
    if 'strip' in inp:
        st = info['strip']
        raw, xm, ym = lab(), lab('m'), lab('m')
        parts.append('%s,scroll=horizontal=%.6f%s' % (still(inp['strip'], 'gray'), st['speed'], raw))
        for src, dst in ((inp['xm'], xm), (inp['ym'], ym)):
            parts.append('%sloop=loop=-1:size=1,setpts=N/%d/TB,trim=duration=%.3f,format=gray16%s' % (src, fps, D, dst))
        parts.append('%s%s%sremap=fill=black,format=gray%s' % (raw, xm, ym, G))
    else:
        ops = info['ops']
        ls = [lab() for _ in ops]
        parts.append('%s,split=%d%s' % (still(inp['field'], 'gray'), len(ops), ''.join(ls)) if len(ops) > 1 else
                     '%s%s' % (still(inp['field'], 'gray'), ls[0]))
        cur = None
        for i, (op, hs, vs) in enumerate(ops):
            m = lab()
            sc = ',scroll=horizontal=%.6f:vertical=%.6f' % (hs, vs) if (hs or vs) else ''
            parts.append('%scrop=%d:%d:0:%d%s%s' % (ls[i], bw, bh, i * bh, sc, m))
            if cur is None:
                cur = m
            else:
                nx = lab()
                parts.append('%s%sblend=all_mode=%s:shortest=1%s' % (cur, m, op, nx))
                cur = nx
        parts.append('%snull%s' % (cur, G))
    al = lab('a')
    beat = bool(cmdfile and s['fxBeat'])
    gain = {'sparks': 1.45, 'glitter': 1.4, 'dust': 1.25}.get(fx, 1.0) * (255 / 235 if beat else 1)
    parts.append("%slut=c0='min(255\\,val*%.3f)'%s" % (G, s['fxAlpha'] / 100 * gain, al))
    if beat:                                       # im Takt: Sichtbarkeit folgt der Lautstärke
        md, a2 = lab('k'), lab('a')
        parts.append('color@fxb=c=0xffffff:s=%dx%d:r=%d:d=%.3f,sendcmd=f=%s,format=gray%s' % (bw, bh, fps, D, cmdfile, md))
        parts.append('%s%sblend=all_mode=multiply:shortest=1%s' % (al, md, a2))
        al = a2
    if 'mask' in inp:
        mk, a2 = lab('k'), lab('a')
        parts.append('%s,scale=%d:%d%s' % (still(inp['mask'], 'gray'), bw, bh, mk))
        parts.append('%s%sblend=all_mode=multiply:shortest=1%s' % (al, mk, a2))
        al = a2
    cols = info['colors'][:8] or ['#ffffff', '#ffffff']
    if len(cols) < 2:
        cols = cols * 2
    cs = ':'.join('c%d=0x%s' % (i, c[1:]) for i, c in enumerate(cols))
    col, lay, out = lab('c'), lab('l'), lab()
    parts.append('gradients=s=%dx%d:%s:nb_colors=%d:x0=0:y0=0:x1=%d:y1=%d:r=%d:d=1:speed=0.00001,trim=end_frame=1,'
                 'loop=loop=-1:size=1,setpts=N/%d/TB,trim=duration=%.3f,format=yuv420p%s' % (
                     bw, bh, cs, len(cols), bw, bh, fps, fps, D, col))
    parts.append('%s%salphamerge,format=yuva420p%s' % (col, al, lay))
    base = lab('b')
    parts.append('%s%s' % (chain, base))
    parts.append('%s%soverlay=%d:%d:shortest=0:eof_action=pass,format=yuv420p%s' % (base, lay, ox, oy, out))
    return parts, '%snull' % out


def beat_commands(levels, step=0.1):
    """Im Takt: Sichtbarkeit der Effekte folgt der Lautstärke (sendcmd ändert die Graustufe von color@fxb)."""
    out = []
    for k, lv in enumerate(levels):
        v = int(round((0.5 + 0.5 * lv) * 255))
        out.append('%.2f color@fxb c 0x%02x%02x%02x;\n' % (k * step, v, v, v))
    return ''.join(out)

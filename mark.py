"""Markieren + KI-Helfer für den Audio-Visualizer (ffmpeg_encode Studio).

- Maske: Visualizer nur innerhalb einer gemalten / KI-ausgewählten Fläche.
- Pfad: Visualizer entlang einer Linie oder eines Rings (FFmpeg `remap` mit hier berechneten Karten).
- KI-Auswahl: MobileSAM (ONNX, läuft offline). Ohne Modell: OpenCV GrabCut als Ersatz.
- Linie verfeinern: rastet an der stärksten Bildkante in der Nähe ein und wird geglättet.
- Platzvorschlag: ruhige Bildbereiche ohne Gesichter.
Alle Koordinaten zwischen Programm und Oberfläche sind normiert (0..1 bezogen auf das fertige Videobild).
"""
import math
import os
import threading
from pathlib import Path

import numpy as np

try:
    import cv2
except Exception:  # noqa: BLE001
    cv2 = None


def imread(path, flags=None):
    """Bild lesen – auch mit Umlauten im Pfad (Windows)."""
    data = np.fromfile(str(path), dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR if flags is None else flags)


def imwrite(path, img):
    ext = Path(path).suffix or '.png'
    ok, buf = cv2.imencode(ext, img)
    if not ok:
        raise RuntimeError('Bild konnte nicht gespeichert werden')
    buf.tofile(str(path))


# ---------- KI: MobileSAM ----------
class Sam:
    """Segment-Anything (MobileSAM) über onnxruntime. Einmal pro Bild 'embed', dann beliebig viele Klicks."""

    def __init__(self, folder):
        self.folder = Path(folder) if folder else None
        self.enc = self.dec = None
        self.error = ''
        self.lock = threading.Lock()
        self.cache = {}        # key -> (embedding, h, w)

    def files(self):
        if not self.folder:
            return None, None
        e = self.folder / 'mobile_sam_image_encoder.onnx'
        d = self.folder / 'sam_mask_decoder_single.onnx'
        return (e, d) if e.is_file() and d.is_file() else (None, None)

    def available(self):
        return all(self.files())

    def load(self):
        if self.enc is not None:
            return True
        e, d = self.files()
        if not e:
            return False
        try:
            import onnxruntime as ort
            prov = [p for p in ('DmlExecutionProvider', 'CUDAExecutionProvider') if p in ort.get_available_providers()] + ['CPUExecutionProvider']
            so = ort.SessionOptions()
            so.log_severity_level = 3
            try:
                self.enc = ort.InferenceSession(str(e), so, providers=prov)
            except Exception:  # noqa: BLE001  (Grafikkarte zickt -> CPU)
                self.enc = ort.InferenceSession(str(e), so, providers=['CPUExecutionProvider'])
            self.dec = ort.InferenceSession(str(d), so, providers=['CPUExecutionProvider'])
            return True
        except Exception as ex:  # noqa: BLE001
            self.error = str(ex)
            self.enc = self.dec = None
            return False

    def embed(self, key, rgb):
        with self.lock:
            if key in self.cache:
                return self.cache[key]
            h, w = rgb.shape[:2]
            s = 1024 / max(h, w)
            nh, nw = int(round(h * s)), int(round(w * s))
            img = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_AREA).astype(np.float32)
            inp = self.enc.get_inputs()[0]
            if len(inp.shape) == 3:                       # Modell macht Normalisieren + Auffüllen selbst (HWC, 0..255)
                x = img
            else:                                          # klassisch: NCHW, normalisiert, auf 1024 aufgefüllt
                mean = np.array([123.675, 116.28, 103.53], np.float32)
                std = np.array([58.395, 57.12, 57.375], np.float32)
                x = np.zeros((1024, 1024, 3), np.float32)
                x[:nh, :nw] = (img - mean) / std
                x = x.transpose(2, 0, 1)[None]
            emb = self.enc.run(None, {inp.name: x})[0]
            if len(self.cache) > 6:
                self.cache.clear()
            self.cache[key] = (emb, h, w, s)
            return self.cache[key]

    def predict(self, key, rgb, points, labels, box=None):
        emb, h, w, s = self.embed(key, rgb)
        pts = [[x * s, y * s] for x, y in points]
        lab = list(labels)
        if box is not None:
            x0, y0, x1, y1 = box
            pts += [[x0 * s, y0 * s], [x1 * s, y1 * s]]
            lab += [2, 3]
        else:
            pts.append([0.0, 0.0])
            lab.append(-1)
        feed = {'image_embeddings': emb,
                'point_coords': np.array([pts], np.float32),
                'point_labels': np.array([lab], np.float32),
                'mask_input': np.zeros((1, 1, 256, 256), np.float32),
                'has_mask_input': np.zeros(1, np.float32),
                'orig_im_size': np.array([h, w], np.float32)}
        names = {i.name for i in self.dec.get_inputs()}
        feed = {k: v for k, v in feed.items() if k in names}
        masks = self.dec.run(None, feed)[0]
        m = masks[0, 0] if masks.ndim == 4 else masks[0]
        if m.shape != (h, w):
            m = cv2.resize(m, (w, h), interpolation=cv2.INTER_LINEAR)
        return (m > 0).astype(np.uint8) * 255


def grabcut(rgb, points, labels, box=None):
    """Ersatz ohne KI-Modell: OpenCV GrabCut, gestartet an den Klicks / am Rahmen."""
    h, w = rgb.shape[:2]
    pos = [p for p, l in zip(points, labels) if l == 1]
    if box is None:
        if pos:
            xs, ys = [p[0] for p in pos], [p[1] for p in pos]
            r = max(w, h) * 0.18
            box = (max(0, min(xs) - r), max(0, min(ys) - r), min(w - 1, max(xs) + r), min(h - 1, max(ys) + r))
        else:
            return np.zeros((h, w), np.uint8)
    x0, y0, x1, y1 = [int(v) for v in box]
    mask = np.full((h, w), cv2.GC_BGD, np.uint8)
    mask[y0:y1, x0:x1] = cv2.GC_PR_FGD
    rad = max(3, int(min(w, h) * 0.02))
    for (x, y), l in zip(points, labels):
        cv2.circle(mask, (int(x), int(y)), rad, cv2.GC_FGD if l == 1 else cv2.GC_BGD, -1)
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    cv2.grabCut(bgr, mask, (x0, y0, max(1, x1 - x0), max(1, y1 - y0)), bgd, fgd, 5, cv2.GC_INIT_WITH_MASK)
    return np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)


def clean_mask(m, points, labels):
    """Nur Teile behalten, die einen Plus-Klick enthalten (keine Krümel), Löcher schließen, Kante glätten."""
    if not m.any():
        return m
    n, lab = cv2.connectedComponents((m > 0).astype(np.uint8))
    keep = {lab[min(m.shape[0] - 1, int(y)), min(m.shape[1] - 1, int(x))] for (x, y), l in zip(points, labels) if l == 1}
    keep.discard(0)
    if keep:
        m = np.isin(lab, list(keep)).astype(np.uint8) * 255
    k = max(3, int(min(m.shape) * 0.006) | 1)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    return m


def segment(sam, key, img_path, points, labels, box=None):
    """points/box in Pixeln des Analysebilds. Rückgabe (Maske 0/255, Methode)."""
    bgr = imread(img_path)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    method = 'ki'
    m = None
    if sam is not None and sam.load():
        try:
            m = sam.predict(key, rgb, points, labels, box)
        except Exception as ex:  # noqa: BLE001
            sam.error = str(ex)
            m = None
    if m is None:
        method = 'grabcut'
        m = grabcut(rgb, points, labels, box)
    return clean_mask(m, points, labels), method


# ---------- Linie verfeinern ----------
def resample(pts, step, closed=False):
    p = np.asarray(pts, np.float64)
    if closed:
        p = np.vstack([p, p[:1]])
    seg = np.hypot(*np.diff(p, axis=0).T)
    L = seg.sum()
    if L < 1e-6:
        return p
    n = max(2, int(L / step) + 1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    t = np.linspace(0, L, n, endpoint=not closed)
    x = np.interp(t, cum, p[:, 0])
    y = np.interp(t, cum, p[:, 1])
    return np.stack([x, y], 1)


def smooth(p, it=3, closed=False):
    p = p.copy()
    for _ in range(it):
        if closed:
            p = (np.roll(p, 1, 0) + 2 * p + np.roll(p, -1, 0)) / 4
        else:
            q = p.copy()
            q[1:-1] = (p[:-2] + 2 * p[1:-1] + p[2:]) / 4
            p = q
    return p


def refine_line(img_path, pts_norm, closed=False):
    """Grobe Linie an die passende Kante in der Nähe ziehen (Rückgabe normiert).
    Kanten quer zur Linie zählen, feine Pinsel-Struktur wird weggefiltert, und die ganze Linie wird
    gemeinsam optimiert (dynamische Programmierung) – so springt sie nicht von Kante zu Kante."""
    bgr = imread(img_path)
    h, w = bgr.shape[:2]
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)[:, :, 0].astype(np.float32)
    g = cv2.bilateralFilter(g, 9, 40, 9)
    g = cv2.GaussianBlur(g, (0, 0), max(1.5, h / 260))
    gx, gy = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=5), cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=5)
    pts = np.array([[x * w, y * h] for x, y in pts_norm])
    p = smooth(resample(pts, max(5.0, math.hypot(w, h) / 90), closed), 2, closed)
    n = len(p)
    rad = max(8, int(h * 0.08))
    offs = np.arange(-rad, rad + 1)
    score = np.zeros((n, len(offs)), np.float32)
    normals = np.zeros((n, 2))
    for i in range(n):
        a = p[(i - 1) % n] if (closed or i > 0) else p[i]
        b = p[(i + 1) % n] if (closed or i < n - 1) else p[i]
        d = b - a
        nrm = np.array([-d[1], d[0]]) / (np.hypot(*d) or 1)
        normals[i] = nrm
        xs = np.clip((p[i, 0] + offs * nrm[0]).round().astype(int), 0, w - 1)
        ys = np.clip((p[i, 1] + offs * nrm[1]).round().astype(int), 0, h - 1)
        score[i] = np.abs(gx[ys, xs] * nrm[0] + gy[ys, xs] * nrm[1])      # Kante quer zur Linie
    score /= (np.percentile(score, 99) or 1)
    score = np.minimum(score, 1.5) - 0.15 * (np.abs(offs) / rad)[None, :]  # Nähe zur Zeichnung leicht bevorzugen
    jump = 0.15                                                           # Strafe für Sprünge zwischen Nachbarn
    acc = score[0].copy()
    back = np.zeros((n, len(offs)), np.int32)
    idx = np.arange(len(offs))
    for i in range(1, n):
        cost = acc[None, :] - jump * np.abs(idx[:, None] - idx[None, :])
        back[i] = np.argmax(cost, 1)
        acc = score[i] + cost[idx, back[i]]
    k = int(np.argmax(acc))
    choice = np.zeros(n, np.int32)
    for i in range(n - 1, -1, -1):
        choice[i] = k
        k = back[i, k]
    out = p + offs[choice][:, None] * normals
    out[:, 0] = np.clip(out[:, 0], 0, w - 1)
    out[:, 1] = np.clip(out[:, 1], 0, h - 1)
    out = smooth(out, 3, closed)
    keep = resample(out, max(6.0, math.hypot(w, h) / 70), closed)
    return [[round(float(x) / w, 5), round(float(y) / h, 5)] for x, y in keep]


# ---------- Platzvorschlag ----------
DOCKS = [('tl', 0, 0), ('tc', 1, 0), ('tr', 2, 0), ('ml', 0, 1), ('mc', 1, 1), ('mr', 2, 1), ('bl', 0, 2), ('bc', 1, 2), ('br', 2, 2)]
NAMES = {'tl': 'Oben links', 'tc': 'Oben mittig', 'tr': 'Oben rechts', 'ml': 'Mitte links', 'mc': 'Bildmitte', 'mr': 'Mitte rechts',
         'bl': 'Unten links', 'bc': 'Unten mittig', 'br': 'Unten rechts', 'bandTop': 'Band oben', 'bandMid': 'Band Mitte', 'bandBot': 'Band unten'}


def faces(gray):
    try:
        f = os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml')
        if not os.path.isfile(f):
            return []
        c = cv2.CascadeClassifier(f)
        return [tuple(r) for r in c.detectMultiScale(gray, 1.1, 5, minSize=(max(24, gray.shape[0] // 20),) * 2)]
    except Exception:  # noqa: BLE001
        return []


def suggest(img_path, w_pct, h_pct, margin=4):
    bgr = imread(img_path)
    H, W = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    g = cv2.GaussianBlur(gray, (3, 3), 0).astype(np.float32)
    det = np.hypot(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1))
    det = cv2.GaussianBlur(det, (0, 0), 3)
    det /= (np.percentile(det, 99) or 1)
    fc = faces(gray)
    face_map = np.zeros_like(det)
    for x, y, fw, fh in fc:
        cv2.rectangle(face_map, (int(x - fw * .3), int(y - fh * .3)), (int(x + fw * 1.3), int(y + fh * 1.5)), 1.0, -1)
    cands = []
    for did, ax, ay in DOCKS:
        x = margin if ax == 0 else (100 - w_pct) / 2 if ax == 1 else 100 - w_pct - margin
        y = margin if ay == 0 else (100 - h_pct) / 2 if ay == 1 else 100 - h_pct - margin
        cands.append((did, x, y, w_pct))
    for bid, y in (('bandTop', 0), ('bandBot', 100 - h_pct)):
        cands.append((bid, 0, y, 100))
    out = []
    for did, x, y, ww in cands:
        x0, y0 = int(W * x / 100), int(H * y / 100)
        x1, y1 = int(W * (x + ww) / 100), int(H * (y + h_pct) / 100)
        if x1 <= x0 or y1 <= y0:
            continue
        d = float(det[y0:y1, x0:x1].mean())
        f = float(face_map[y0:y1, x0:x1].mean())
        score = d + f * 4 + (0.05 if did in ('mc', 'bandMid') else 0)
        out.append({'dock': did, 'name': NAMES[did], 'x': x, 'y': y, 'w': ww, 'h': h_pct, 'score': round(score, 3), 'd': d, 'f': f})
    out.sort(key=lambda c: c['score'])
    med = sorted(c['d'] for c in out)[len(out) // 2] or 1
    for i, c in enumerate(out):
        why = ['ruhigste Stelle im Bild' if i == 0 else 'ruhiger als die meisten Stellen' if c['d'] < med * 0.9 else 'durchschnittlich viel Bilddetail']
        if fc:
            why.append('verdeckt kein Gesicht' if c['f'] < 0.01 else 'würde ein Gesicht verdecken')
        c['why'] = ', '.join(why)
        c.pop('d'); c.pop('f')
    return {'suggestions': out[:3], 'faces': len(fc)}


# ---------- Masken ----------
def store_mask(png_bytes, out_path):
    """Maske aus der Oberfläche (PNG mit Transparenz) als Graustufen speichern; Rückgabe Begrenzung normiert."""
    img = cv2.imdecode(np.frombuffer(png_bytes, np.uint8), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError('Maske ist kein gültiges Bild')
    if img.ndim == 3 and img.shape[2] == 4:
        m = img[:, :, 3]
    elif img.ndim == 3:
        m = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        m = img
    imwrite(out_path, m)
    return bbox(m)


def bbox(m):
    h, w = m.shape[:2]
    ys, xs = np.nonzero(m > 8)
    if not len(xs):
        return None
    return [xs.min() / w * 100, ys.min() / h * 100, (xs.max() + 1 - xs.min()) / w * 100, (ys.max() + 1 - ys.min()) / h * 100]


def mask_crop(mask_path, W, H, ox, oy, vw, vh, out_path, feather=0.0):
    m = imread(mask_path, cv2.IMREAD_GRAYSCALE)
    m = cv2.resize(m, (W, H), interpolation=cv2.INTER_LINEAR)
    if feather > 0:
        m = cv2.GaussianBlur(m, (0, 0), max(0.5, feather * H / 100))
    imwrite(out_path, m[oy:oy + vh, ox:ox + vw])


# ---------- Pfad (Linie / Ring) -> remap-Karten ----------
def path_maps(path_norm, closed, both, W, H, thick_px, out_x, out_y):
    """Berechnet die FFmpeg-remap-Karten, die einen geraden Streifen (Länge L × Dicke T) entlang des Pfads biegen.
    Rückgabe: (ox, oy, bw, bh, L, T)."""
    pts = np.array([[x * W, y * H] for x, y in path_norm], np.float64)
    if len(pts) < 2:
        raise ValueError('Für eine Linie mindestens zwei Punkte setzen')
    p = resample(pts, max(3.0, math.hypot(W, H) / 300), closed)
    if closed:
        p = np.vstack([p, p[:1]])
        area = np.sum(p[:-1, 0] * p[1:, 1] - p[1:, 0] * p[:-1, 1]) / 2
        sign = 1.0 if area > 0 else -1.0                  # Normale nach außen
    else:
        # Normale soll im Mittel nach oben zeigen (Balken "stehen" auf der Linie)
        d = p[-1] - p[0]
        sign = -1.0 if d[0] >= 0 else 1.0
    T = max(4, int(thick_px))
    seg = np.diff(p, axis=0)
    slen = np.hypot(seg[:, 0], seg[:, 1])
    cum = np.concatenate([[0], np.cumsum(slen)])
    Ltot = cum[-1]
    L = int(min(4096, max(64, Ltot)))
    pad = T + 2
    x0, y0 = int(max(0, p[:, 0].min() - pad)), int(max(0, p[:, 1].min() - pad))
    x1, y1 = int(min(W, p[:, 0].max() + pad + 1)), int(min(H, p[:, 1].max() + pad + 1))
    x0, y0 = x0 // 2 * 2, y0 // 2 * 2
    bw, bh = max(2, (x1 - x0) // 2 * 2), max(2, (y1 - y0) // 2 * 2)
    best = np.full((bh, bw), np.inf, np.float32)
    sx = np.full((bh, bw), 65535, np.float32)
    sy = np.full((bh, bw), 65535, np.float32)
    for i in range(len(seg)):
        a, v, l2 = p[i], seg[i], slen[i] ** 2
        if l2 < 1e-9:
            continue
        rx0, ry0 = int(max(x0, min(a[0], a[0] + v[0]) - pad)), int(max(y0, min(a[1], a[1] + v[1]) - pad))
        rx1, ry1 = int(min(x0 + bw, max(a[0], a[0] + v[0]) + pad + 1)), int(min(y0 + bh, max(a[1], a[1] + v[1]) + pad + 1))
        if rx1 <= rx0 or ry1 <= ry0:
            continue
        yy, xx = np.mgrid[ry0:ry1, rx0:rx1].astype(np.float32)
        t = np.clip(((xx - a[0]) * v[0] + (yy - a[1]) * v[1]) / l2, 0, 1)
        px, py = a[0] + t * v[0], a[1] + t * v[1]
        dx, dy = xx - px, yy - py
        dist = np.hypot(dx, dy)
        side = sign * (v[0] * dy - v[1] * dx) / slen[i]          # >0 = gewünschte Seite
        sub = best[ry0 - y0:ry1 - y0, rx0 - x0:rx1 - x0]
        upd = dist < sub
        sub[upd] = dist[upd]
        s_along = (cum[i] + t * slen[i]) / max(Ltot, 1e-6) * (L - 1)
        if both:
            ok = dist < T
            ymap = (T - 1) - np.minimum(dist, T - 1)
        else:
            ok = (dist < T) & (side >= -0.6)
            ymap = (T - 1) - np.clip(dist, 0, T - 1)
        sxs = sx[ry0 - y0:ry1 - y0, rx0 - x0:rx1 - x0]
        sys_ = sy[ry0 - y0:ry1 - y0, rx0 - x0:rx1 - x0]
        sxs[upd] = np.where(ok, s_along, 65535)[upd]
        sys_[upd] = np.where(ok, ymap, 65535)[upd]
    imwrite(out_x, np.clip(sx, 0, 65535).astype(np.uint16))
    imwrite(out_y, np.clip(sy, 0, 65535).astype(np.uint16))
    return x0, y0, bw, bh, L, T


def circle_path(cx, cy, r_px_w, aspect, n=160):
    """Kreis (in Pixeln rund) als normierte Punkte; aspect = Bildbreite/Bildhöhe."""
    return [[cx + r_px_w * math.cos(a), cy + r_px_w * aspect * math.sin(a)] for a in np.linspace(0, 2 * math.pi, n, endpoint=False)]

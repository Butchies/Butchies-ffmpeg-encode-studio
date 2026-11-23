"""KI-Selbstoptimierung (1.10.0): die KI merkt sich, wie sie auf DIESEM PC am schnellsten und stabilsten läuft
und welche Ergebnisse gut aussehen.

1) Tempo-Rezepte: Kombinationen der Schalter von stable-diffusion.cpp (Flash-Attention, Direkt-Faltung,
   Text-Teil auf Karte oder Prozessor, Auslagern in den Arbeitsspeicher). Jede echte Rechnung und das
   „Tempo-Training“ speichern Sekunden je Bild pro Grafikkarte + Qualität. Gewählt wird das schnellste
   Rezept, das nie am Grafikspeicher gescheitert ist.
2) Ausweichen: scheitert ein Stück am Grafikspeicher, wird das Rezept gesperrt und das Stück automatisch mit
   dem nächst-sichereren Rezept wiederholt – beim nächsten Mal gleich richtig.
3) Qualitäts-Note: jedes Stück bekommt Messwerte (Schärfe, Flackern, Bewegung, Abweichung vom Original).
   Daraus eine Note; aus deinen Sternen lernt die KI, welche Messwerte dir wichtig sind (kleinste Quadrate).

Alles in einer JSON-Datei, nur Standardbibliothek + numpy/OpenCV (falls vorhanden)."""
import json
import threading
import time
from pathlib import Path

import numpy as np

try:
    import cv2
except Exception:  # noqa: BLE001
    cv2 = None

# Rezepte: von schnell/riskant bis sicher. te 'gpu' = Text-Teil auch auf die Karte (nur bei genug Grafikspeicher).
RECIPES = {
    'standard': {'name': 'Standard (automatisch)', 'fa': 'auto', 'cd': 'auto', 'te': 'cpu', 'offload': False},
    'fa_on':    {'name': 'Flash-Attention an', 'fa': 'on', 'cd': 'auto', 'te': 'cpu', 'offload': False},
    'fa_off':   {'name': 'Flash-Attention aus', 'fa': 'off', 'cd': 'auto', 'te': 'cpu', 'offload': False},
    'cd_off':   {'name': 'Direkt-Faltung aus', 'fa': 'auto', 'cd': 'off', 'te': 'cpu', 'offload': False},
    'te_gpu':   {'name': 'Alles auf der Grafikkarte', 'fa': 'auto', 'cd': 'auto', 'te': 'gpu', 'offload': False},
    'safe':     {'name': 'Sicher (Auslagern in Arbeitsspeicher)', 'fa': 'auto', 'cd': 'auto', 'te': 'cpu', 'offload': True},
}
SAFE_ORDER = ['te_gpu', 'fa_on', 'standard', 'cd_off', 'fa_off', 'safe']    # bei Speicherfehler weiter nach rechts

# Vorwissen („vortrainiert“): Startwerte, bevor auf diesem PC gemessen wurde. Kleiner = besser.
PRIOR = {
    # Vulkan auf AMD/Intel: Flash-Attention lohnt sich je nach Treiber, „auto“ misst selbst -> Standard zuerst
    'amd': ['standard', 'fa_on', 'cd_off', 'fa_off', 'safe'],
    'intel': ['standard', 'fa_off', 'cd_off', 'safe'],
    'nvidia': ['fa_on', 'standard', 'cd_off', 'safe'],
    'cpu': ['standard', 'fa_off'],
}
# Startgewichte der Qualitäts-Note (vor eigenen Sternen): Schärfe gut, Flackern schlecht, etwas Bewegung gut,
# starkes Abweichen vom Original schlecht.
W_PRIOR = {'sharp': 0.8, 'flicker': -1.2, 'motion': 0.5, 'drift': -0.9, 'bias': 3.2}
FEATS = ['sharp', 'flicker', 'motion', 'drift']


def recipe_args(rid, gen, vram):
    """Kommandozeile für ein Rezept (zusätzlich zu Modell-Dateien)."""
    r = RECIPES.get(rid) or RECIPES['standard']
    out = ['--flash-attn', r['fa'], '--conv-direct', r['cd']]
    if r['offload']:
        out += ['--offload-to-cpu']
    te = gen if (r['te'] == 'gpu' and gen not in ('cpu', 'auto')) else 'cpu'
    if gen == 'cpu':
        out += ['--backend', 'cpu']
    elif gen != 'auto':
        out += ['--backend', 'diffusion=%s,vae=%s,te=%s' % (gen, gen, te)]
    if vram >= 12:
        out += ['--extra-tiling-args', 'temporal_decode_frames=2']
    return out


class Tuner:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()
        try:
            self.d = json.loads(self.path.read_text('utf-8'))
        except Exception:  # noqa: BLE001
            self.d = {}
        self.d.setdefault('runs', {})       # "<gpu>|<quality>" -> {rid: {'n','spf','oom','fail','t'}}
        self.d.setdefault('quality', [])    # [{'f': {...}, 'stars': n}]
        self.d.setdefault('trained', {})    # "<gpu>" -> Zeitpunkt Tempo-Training

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix('.tmp')
            tmp.write_text(json.dumps(self.d, ensure_ascii=False), 'utf-8')
            tmp.replace(self.path)
        except OSError:
            pass

    # ---------- Tempo ----------
    @staticmethod
    def slot(gen, quality):
        return '%s|%s' % (gen or 'auto', quality)

    def candidates(self, vendor, vram, gen):
        base = list(PRIOR.get('cpu' if gen == 'cpu' else vendor, PRIOR['amd']))
        if gen not in ('cpu', 'auto') and vram >= 10 and 'te_gpu' not in base:
            base.insert(0, 'te_gpu')                                 # genug Grafikspeicher: alles auf die Karte probieren
        return base

    def record(self, gen, quality, rid, sec_per_frame=None, oom=False, fail=False):
        with self.lock:
            r = self.d['runs'].setdefault(self.slot(gen, quality), {}).setdefault(rid, {'n': 0, 'spf': 0, 'oom': 0, 'fail': 0})
            if sec_per_frame:
                r['spf'] = round(sec_per_frame if not r['n'] else 0.7 * r['spf'] + 0.3 * sec_per_frame, 3)
                r['n'] += 1
            r['oom'] += int(bool(oom))
            r['fail'] += int(bool(fail))
            r['t'] = int(time.time())
            self._save()

    def best(self, gen, quality, vendor, vram):
        """Schnellstes bewährtes Rezept; ohne Messung das erste aus dem Vorwissen."""
        runs = self.d['runs'].get(self.slot(gen, quality), {})
        cands = self.candidates(vendor, vram, gen)
        # Auslagern kostet meist Tempo und schwankt -> nur nehmen, wenn es klar (>5 %) schneller ist
        ok = [(v['spf'] * (1.05 if RECIPES[k]['offload'] else 1), k) for k, v in runs.items() if k in RECIPES and v['n'] and not v['oom'] and v['fail'] < 2]
        if ok:
            return min(ok)[1]
        for k in cands:
            v = runs.get(k) or {}
            if not v.get('oom') and v.get('fail', 0) < 2:
                return k
        return 'safe'

    def safer(self, rid, gen, quality):
        """Nach Speicherfehler: nächstes sichereres Rezept, das nicht schon gescheitert ist."""
        runs = self.d['runs'].get(self.slot(gen, quality), {})
        i = SAFE_ORDER.index(rid) if rid in SAFE_ORDER else 0
        for k in SAFE_ORDER[i + 1:]:
            if not (runs.get(k) or {}).get('oom'):
                return k
        return None

    def untested(self, gen, quality, vendor, vram):
        runs = self.d['runs'].get(self.slot(gen, quality), {})
        return [k for k in self.candidates(vendor, vram, gen) if not (runs.get(k) or {}).get('n') and not (runs.get(k) or {}).get('oom')]

    def mark_trained(self, gen):
        with self.lock:
            self.d['trained'][gen] = int(time.time())
            self._save()

    # ---------- Qualität ----------
    def weights(self):
        Q = self.d['quality'][-120:]
        w = dict(W_PRIOR)
        if len(Q) >= 6:
            X = np.array([[q['f'].get(k, 0) for k in FEATS] + [1.0] for q in Q])
            y = np.array([q['stars'] for q in Q], float)
            prior = np.array([W_PRIOR[k] for k in FEATS] + [W_PRIOR['bias']])
            lam = 3.0                                             # Vorwissen zieht, eigene Sterne überwiegen mit der Zeit
            A = X.T @ X + lam * np.eye(len(prior))
            sol = np.linalg.solve(A, X.T @ y + lam * prior)
            w = dict(zip(FEATS + ['bias'], [round(float(v), 3) for v in sol]))
        return w

    def score(self, f):
        if not f:
            return None
        w = self.weights()
        s = w['bias'] + sum(w[k] * f.get(k, 0) for k in FEATS)
        return round(float(min(5, max(1, s))), 2)

    def learn_quality(self, f, stars):
        if not f:
            return
        with self.lock:
            self.d['quality'].append({'f': {k: float(f.get(k, 0)) for k in FEATS}, 'stars': int(stars), 't': int(time.time())})
            self.d['quality'] = self.d['quality'][-200:]
            self._save()

    def summary(self):
        out = []
        for slot, runs in self.d['runs'].items():
            gen, q = slot.split('|', 1)
            ok = sorted((v['spf'], k) for k, v in runs.items() if v['n'] and not v['oom'] and k in RECIPES)
            out.append({'gen': gen, 'quality': q, 'best': ok[0][1] if ok else '', 'best_name': RECIPES[ok[0][1]]['name'] if ok else '',
                        'spf': ok[0][0] if ok else 0, 'worst_spf': ok[-1][0] if ok else 0,
                        'tested': sorted(k for k, v in runs.items() if v['n']), 'oom': sorted(k for k, v in runs.items() if v['oom'])})
        return {'speed': out, 'ratings': len(self.d['quality']), 'weights': self.weights(), 'trained': self.d['trained']}

    def reset(self):
        with self.lock:
            self.d = {'runs': {}, 'quality': [], 'trained': {}}
            self._save()


def features(frames, ref=None):
    """Messwerte eines Stücks (Liste BGR/RGB-Bilder), grob auf 0…1 gebracht.
    sharp = Schärfe gegenüber dem Original, flicker = Helligkeitszittern, motion = Bewegung, drift = Abweichung vom Original."""
    if cv2 is None or not frames:
        return {}
    small = [cv2.resize(f, (192, 108 if f.shape[1] >= f.shape[0] else 192), interpolation=cv2.INTER_AREA) for f in frames]
    g = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32) for f in small]
    lap = [cv2.Laplacian(x, cv2.CV_32F).var() for x in g]
    r = cv2.resize(ref, small[0].shape[1::-1], interpolation=cv2.INTER_AREA) if ref is not None else small[0]
    rg = cv2.cvtColor(r, cv2.COLOR_BGR2GRAY).astype(np.float32)
    rl = cv2.Laplacian(rg, cv2.CV_32F).var() + 1e-3
    sharp = float(np.clip(np.median(lap) / rl, 0, 1.5) / 1.5)
    means = np.array([x.mean() for x in g])
    flick = float(np.clip(np.abs(np.diff(means, 2)).mean() / 3.0, 0, 1)) if len(means) > 2 else 0.0
    diffs = [np.abs(a - b).mean() for a, b in zip(g, g[1:])]
    motion = float(np.clip(np.median(diffs) / 6.0, 0, 1)) if diffs else 0.0
    drift = float(np.clip(np.abs(g[-1] - rg).mean() / 40.0, 0, 1))
    return {'sharp': round(sharp, 3), 'flicker': round(flick, 3), 'motion': round(motion, 3), 'drift': round(drift, 3)}

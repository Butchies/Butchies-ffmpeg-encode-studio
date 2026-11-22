"""Selbst-Lernen (offline, nur auf diesem PC).

Das Programm merkt sich, was der Nutzer tut, und passt sich daran an:
- Beste Stelle: welche Art (Refrain/Drop/Emotional) gewählt wird, wie der Ausschnitt klingt
  (Energie, Wiederholung, Anstieg) und wie Start/Ende danach noch verschoben werden.
- Songtext: korrigierte Wörter werden Whisper beim nächsten Mal als Hilfe mitgegeben.
- Stil: oft genutzte Effekte, Wellen, Kamera und Regler-Werte -> Startwerte für neue Videos.
Alles liegt in learn.json im Einstellungsordner und lässt sich jederzeit zurücksetzen.
"""
import json
import re
import threading
import time
from collections import Counter
from pathlib import Path

KINDS = ('chorus', 'drop', 'emo')
KIND_NAMES = {'chorus': 'Refrain', 'drop': 'Höhepunkt / Drop', 'emo': 'Emotionaler Aufbau'}
FEATS = ('energy', 'rep', 'rise')
# Stil: Auswahl-Felder (häufigster Wert) und Regler (gleitender Mittelwert)
STYLE_PICK = ('fx', 'fxColorMode', 'cam', 'viz', 'vizStyle', 'vizColorMode', 'fit', 'transIn', 'transOut')
STYLE_NUM = ('fxAmount', 'fxSpeed', 'fxSize', 'fxAlpha', 'camAmount', 'camSpeed', 'vizStr', 'vizAlpha', 'vizGlow',
             'fadeIn', 'fadeOut')
STYLE_BOOL = ('fxBeat',)
STOP = set('''der die das und ich du er sie es wir ihr ein eine einen einem einer nicht mit von zu auf in im ist bin bist sind
war mir mich dich dir uns euch so wie was wo wenn dann noch nur auch aber oder doch ja nein mal schon
the a an and i you he she it we they is are am was be to of in on at for with my your me our not no yes so but or
oh ah yeah na la hey ooh uh'''.split())
# KI-Video-Bewertungen: Stichwort -> (Anzeige, Zusatz für die KI-Beschreibung)
AI_TAGS = {
    'strong': ('Bewegung zu stark', 'very subtle and gentle movement, minimal motion'),
    'weak': ('Bewegung zu schwach', 'clearly visible, more pronounced movement'),
    'face': ('Gesicht verzerrt', 'preserve the face exactly, no facial distortion, consistent identity'),
    'flicker': ('Flackert / unruhig', 'temporally stable, smooth, no flicker'),
    'blur': ('Unscharf', 'sharp crisp details'),
    'color': ('Farben falsch', ''),
    'perfect': ('Perfekt', ''),
}
MIN_STYLE = 3          # ab so vielen Videos werden Startwerte vorgeschlagen
ALPHA = 0.3            # Lernrate (wie stark ein neues Beispiel zählt)


def _empty():
    return {'version': 1, 'created': time.time(),
            'hl': {'picks': {k: 0 for k in KINDS}, 'n': 0, 'feat': None, 'shift': 0.0, 'shift_n': 0,
                   'end_shift': 0.0},
            'words': {}, 'songs': {},
            'ai': {'ratings': [], 'n': 0},
            'style': {'n': 0, 'pick': {}, 'num': {}, 'bool': {}}}


class Learner:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()
        self.d = self._load()

    def _load(self):
        try:
            d = json.loads(self.path.read_text('utf-8'))
            base = _empty()
            for k, v in base.items():
                d.setdefault(k, v)
            for k, v in base['hl'].items():
                d['hl'].setdefault(k, v)
            for k in KINDS:
                d['hl']['picks'].setdefault(k, 0)
            for k, v in base['style'].items():
                d['style'].setdefault(k, v)
            d['ai'].setdefault('ratings', [])
            d['ai'].setdefault('n', 0)
            return d
        except Exception:  # noqa: BLE001
            return _empty()

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix('.tmp')
            tmp.write_text(json.dumps(self.d, ensure_ascii=False), 'utf-8')
            tmp.replace(self.path)
        except OSError:
            pass

    def reset(self, part=None):
        with self.lock:
            fresh = _empty()
            if part in ('hl', 'words', 'style', 'ai'):
                self.d[part] = fresh[part]
                if part == 'words':
                    self.d['songs'] = {}
            else:
                self.d = fresh
            self._save()

    # ---------- Beste Stelle ----------
    def hl_pick(self, kind, feat):
        """Nutzer hat einen Vorschlag übernommen."""
        if kind not in KINDS:
            return
        with self.lock:
            h = self.d['hl']
            h['picks'][kind] += 1
            h['n'] += 1
            if isinstance(feat, dict) and all(isinstance(feat.get(f), (int, float)) for f in FEATS):
                if h['feat'] is None:
                    h['feat'] = {f: float(feat[f]) for f in FEATS}
                else:
                    for f in FEATS:
                        h['feat'][f] = (1 - ALPHA) * h['feat'][f] + ALPHA * float(feat[f])
            self._save()

    def hl_adjust(self, d_start, d_end):
        """Nutzer hat Start/Ende nach dem Übernehmen noch verschoben (Sekunden)."""
        try:
            ds, de = float(d_start), float(d_end)
        except (TypeError, ValueError):
            return
        if abs(ds) > 20 or abs(de) > 20:          # ganz andere Stelle gewählt -> kein Feinschliff
            return
        with self.lock:
            h = self.d['hl']
            h['shift'] = (1 - ALPHA) * h['shift'] + ALPHA * ds
            h['end_shift'] = (1 - ALPHA) * h['end_shift'] + ALPHA * de
            h['shift_n'] += 1
            self._save()

    def hl_model(self):
        """Gelerntes für highlight.suggest: Vorliebe je Art, Wunsch-Klang, Verschiebung."""
        with self.lock:
            h = json.loads(json.dumps(self.d['hl']))
        n = h['n']
        prefs = {k: (h['picks'][k] + 1) / (n + 3) for k in KINDS}          # Laplace-geglättet
        conf = min(1.0, n / 6.0)
        return {'n': n, 'prefs': prefs, 'conf': conf, 'feat': h['feat'],
                'shift': h['shift'] if h['shift_n'] >= 2 else 0.0}

    # ---------- Songtext ----------
    @staticmethod
    def _words(text):
        return [w for w in re.findall(r"[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß'’-]{1,}", text or '')]

    def lyrics_fix(self, song_key, old_lines, new_lines):
        """Korrigierte Zeilen speichern; neue/geänderte Wörter lernen. Rückgabe: gelernte Wörter."""
        old = Counter(w.lower() for l in old_lines for w in self._words(l.get('text', '')))
        learned = []
        with self.lock:
            W = self.d['words']
            for l in new_lines:
                for w in self._words(l.get('text', '')):
                    lw = w.lower()
                    if lw in STOP or len(lw) < 3:
                        continue
                    if old[lw] > 0:
                        old[lw] -= 1
                        continue
                    W[w] = W.get(w, 0) + 1
                    learned.append(w)
            if len(W) > 400:                       # nur die häufigsten behalten
                self.d['words'] = dict(sorted(W.items(), key=lambda kv: -kv[1])[:300])
            S = self.d['songs']
            S[song_key] = {'lines': new_lines, 't': time.time()}
            if len(S) > 60:
                for k, _ in sorted(S.items(), key=lambda kv: kv[1]['t'])[:len(S) - 60]:
                    S.pop(k, None)
            self._save()
        return sorted(set(learned))

    def song_lines(self, song_key):
        with self.lock:
            s = self.d['songs'].get(song_key)
            return json.loads(json.dumps(s['lines'])) if s else None

    def hotwords(self, limit=40):
        with self.lock:
            W = sorted(self.d['words'].items(), key=lambda kv: -kv[1])[:limit]
        return [w for w, _ in W]

    # ---------- Stil ----------
    def style_observe(self, s):
        with self.lock:
            st = self.d['style']
            st['n'] += 1
            for k in STYLE_PICK:
                if k in s:
                    c = st['pick'].setdefault(k, {})
                    v = str(s[k])
                    c[v] = c.get(v, 0) + 1
            for k in STYLE_NUM:
                if isinstance(s.get(k), (int, float)) and not isinstance(s.get(k), bool):
                    old = st['num'].get(k)
                    st['num'][k] = float(s[k]) if old is None else (1 - ALPHA) * old + ALPHA * float(s[k])
            for k in STYLE_BOOL:
                if k in s:
                    old = st['bool'].get(k, 0.5)
                    st['bool'][k] = (1 - ALPHA) * old + ALPHA * (1.0 if s[k] else 0.0)
            self._save()

    def style_suggest(self, defaults):
        """Startwerte im Stil des Nutzers (nur bekannte Schlüssel, Typen wie in defaults)."""
        with self.lock:
            st = json.loads(json.dumps(self.d['style']))
        if st['n'] < MIN_STYLE:
            return {}
        out = {}
        for k, c in st['pick'].items():
            if k in defaults and c:
                v = max(c.items(), key=lambda kv: kv[1])[0]
                d = defaults[k]
                out[k] = (v == 'True') if isinstance(d, bool) else type(d)(v) if isinstance(d, (int, float)) else v
        for k, v in st['num'].items():
            if k in defaults:
                out[k] = round(v, 1) if isinstance(defaults[k], float) else int(round(v))
        for k, v in st['bool'].items():
            if k in defaults:
                out[k] = v >= 0.5
        return out

    # ---------- KI-Video: Bewertungen ----------
    def ai_feedback(self, motion, stars, tags, text, ref=''):
        try:
            stars = max(1, min(5, int(stars)))
        except (TypeError, ValueError):
            stars = 3
        tags = [t for t in (tags or []) if t in AI_TAGS]
        with self.lock:
            a = self.d['ai']
            a['ratings'].append({'motion': str(motion)[:20], 'stars': stars, 'tags': tags, 'text': str(text or '')[:300],
                                 'ref': str(ref or '')[:120], 't': time.time()})
            a['ratings'] = a['ratings'][-200:]
            a['n'] += 1
            self._save()

    def ai_model(self):
        """Gelerntes: welche Wünsche automatisch mitgegeben werden, Farbabgleich-Stärke, Noten je Bewegung."""
        with self.lock:
            R = json.loads(json.dumps(self.d['ai']['ratings']))
        recent = R[-12:]
        cnt = Counter(t for r in recent for t in r['tags'] if r['stars'] <= 3 or t == 'perfect')
        learned = [t for t in ('face', 'flicker', 'blur') if cnt[t] >= 2]
        if cnt['strong'] >= 2 and cnt['strong'] > cnt['weak']:
            learned.append('strong')
        elif cnt['weak'] >= 2 and cnt['weak'] > cnt['strong']:
            learned.append('weak')
        cmatch = 0.85 + (0.15 if cnt['color'] >= 2 else 0.0)
        per = {}
        for r in R:
            per.setdefault(r['motion'], []).append(r['stars'])
        scores = {m: round(sum(v) / len(v), 1) for m, v in per.items()}
        good = [r for r in R if r['stars'] >= 4]
        return {'n': len(R), 'learned': learned, 'extra': [AI_TAGS[t][1] for t in learned if AI_TAGS[t][1]],
                'cmatch': cmatch, 'scores': scores, 'good': len(good),
                'learned_names': [AI_TAGS[t][0] for t in learned] + (['Farben stärker angleichen'] if cmatch > 0.9 else [])}

    @staticmethod
    def ai_fix(tags, text):
        """Änderungswünsche für einen neuen Versuch -> Zusätze für die KI-Beschreibung."""
        out = [AI_TAGS[t][1] for t in (tags or []) if t in AI_TAGS and AI_TAGS[t][1]]
        text = re.sub(r'\s+', ' ', str(text or '')).strip()[:200]
        return out + ([text] if text else [])

    # ---------- Übersicht ----------
    def summary(self, defaults=None, names=None):
        names = names or {}
        m = self.hl_model()
        with self.lock:
            st = json.loads(json.dumps(self.d['style']))
            words = sorted(self.d['words'].items(), key=lambda kv: -kv[1])
            songs = len(self.d['songs'])
        fav = max(m['prefs'].items(), key=lambda kv: kv[1])[0] if m['n'] else ''
        hl = {'n': m['n'], 'fav': KIND_NAMES.get(fav, ''), 'fav_kind': fav,
              'picks': {KIND_NAMES[k]: self.d['hl']['picks'][k] for k in KINDS},
              'shift': round(m['shift'], 1), 'conf': round(m['conf'] * 100)}
        if m['feat']:
            f = m['feat']
            hl['taste'] = ('kräftige, laute Stellen' if f['energy'] > 0.62 else 'ruhigere Stellen' if f['energy'] < 0.4 else 'mittlere Lautstärke') + \
                          (' mit Wiederholung (Refrain-artig)' if f['rep'] > 0.55 else '') + \
                          (' und starkem Anstieg' if f['rise'] > 0.12 else '')
        sug = self.style_suggest(defaults or {}) if defaults else {}
        style = {'n': st['n'], 'ready': st['n'] >= MIN_STYLE, 'need': max(0, MIN_STYLE - st['n']),
                 'top': {k: names[k].get(str(v), str(v)) for k, v in sug.items()
                         if k in names and not (k == 'vizStyle' and not sug.get('viz')) and not (k == 'fx' and v == 'none')}}
        return {'hl': hl, 'words': [w for w, _ in words[:40]], 'word_count': len(words), 'songs': songs,
                'style': style, 'ai': self.ai_model()}

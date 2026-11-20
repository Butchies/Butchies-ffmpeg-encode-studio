"""Beste Stelle im Song für Shorts finden (ab 1.6.0) – komplett offline, nur numpy.

Ablauf:  Song (mono, 22 050 Hz) -> Spektrum -> Einsatzstärke (Onsets) -> Tempo + Taktschläge (dynamische Programmierung)
         -> je Schlag: Lautstärke/Energie, Harmonien (Chroma) -> Wiederholung (Selbstähnlichkeit = Refrain-Kandidat)
         -> Fenster der gewünschten Länge auf Taktanfängen bewerten:
            Refrain (wiederholt + kräftig) · Höhepunkt/Drop (größter Energiesprung) · Emotionaler Aufbau (steigt zum Höhepunkt
            bzw. – mit Songtext – die meisten Gefühlswörter)
Optional „Mit Songtext“: Zeilen + Zeitstempel (lyrics.py) – wiederholte Zeilen = Refrain, Gefühlswörter = emotional.
"""
import math
import re
import subprocess
from difflib import SequenceMatcher

try:
    import numpy as np
except Exception:  # noqa: BLE001
    np = None

SR = 22050
HOP = 512
NFFT = 2048
LENGTHS = (15, 30, 45, 60, 90, 120, 180)

EMO_WORDS = {
    # Deutsch
    'liebe', 'lieb', 'liebst', 'herz', 'herzen', 'träne', 'tränen', 'weinen', 'wein', 'vermiss', 'vermisse', 'vermissen',
    'sehnsucht', 'für immer', 'nie wieder', 'niemals', 'allein', 'einsam', 'schmerz', 'verloren', 'seele', 'gefühl',
    'gefühle', 'traum', 'träume', 'brennt', 'feuer', 'himmel', 'halt mich', 'bleib', 'ewig', 'zusammen', 'abschied',
    'leben', 'sterben', 'frei', 'freiheit', 'glück', 'hoffnung', 'nacht', 'sterne', 'küss', 'kuss', 'umarm',
    # Englisch
    'love', 'heart', 'tears', 'cry', 'crying', 'miss you', 'forever', 'never', 'alone', 'lonely', 'pain', 'lost',
    'soul', 'feel', 'feeling', 'dream', 'dreams', 'fire', 'burn', 'heaven', 'hold me', 'stay', 'together', 'goodbye',
    'life', 'die', 'free', 'hope', 'night', 'stars', 'kiss', 'baby', 'remember', 'tonight', 'fly', 'light',
}


def load_audio(ffmpeg, path, run, start=0.0, dur=None):
    args = [ffmpeg, '-v', 'error', '-nostdin']
    if start:
        args += ['-ss', '%.3f' % start]
    args += ['-i', str(path)]
    if dur:
        args += ['-t', '%.3f' % dur]
    args += ['-vn', '-ac', '1', '-ar', str(SR), '-f', 's16le', '-']
    r = run(args, timeout=600)
    if r.returncode:
        raise RuntimeError('Song konnte nicht gelesen werden')
    return np.frombuffer(r.stdout, np.int16).astype(np.float32) / 32768.0


def stft_mag(y):
    if len(y) < NFFT:
        y = np.pad(y, (0, NFFT - len(y)))
    n = 1 + (len(y) - NFFT) // HOP
    win = np.hanning(NFFT).astype(np.float32)
    out = np.empty((n, NFFT // 2 + 1), np.float32)
    step = 2048
    for a in range(0, n, step):                         # in Blöcken (Speicher schonen)
        b = min(n, a + step)
        idx = np.arange(a, b)[:, None] * HOP + np.arange(NFFT)[None, :]
        out[a:b] = np.abs(np.fft.rfft(y[idx] * win, axis=1))
    return out


def onset_envelope(S):
    L = np.log1p(S * 50)
    flux = np.maximum(0, np.diff(L, axis=0)).sum(axis=1)
    flux = np.concatenate([[0], flux])
    flux = flux - np.convolve(flux, np.ones(16) / 16, 'same')    # Grundrauschen abziehen
    flux = np.maximum(flux, 0)
    return flux / (flux.std() + 1e-9)


def tempo_period(o, fps):
    """Taktschlag-Abstand in Frames (Autokorrelation, bevorzugt um 120 BPM)."""
    o = o - o.mean()
    n = len(o)
    size = 1 << (2 * n - 1).bit_length()
    ac = np.fft.irfft(np.abs(np.fft.rfft(o, size)) ** 2)[:n]
    lo, hi = int(fps * 60 / 200), int(fps * 60 / 55)
    lags = np.arange(lo, min(hi, n - 1))
    if not len(lags):
        return fps * 0.5
    bpm = 60 * fps / lags
    weight = np.exp(-0.5 * (np.log2(bpm / 118.0) / 0.9) ** 2)
    score = ac[lags] * weight
    p = lags[int(np.argmax(score))]
    # Feinjustierung (Parabel)
    if 0 < p < n - 1:
        a, b, c = ac[p - 1], ac[p], ac[p + 1]
        d = (a - 2 * b + c)
        if d < 0:
            return p + 0.5 * (a - c) / d
    return float(p)


def track_beats(o, period, tight=100.0):
    """Ellis-Beat-Tracking: Schläge an Onsets, Abstand möglichst gleichmäßig."""
    n = len(o)
    score = o.copy().astype(np.float64)
    back = np.full(n, -1)
    lo, hi = int(round(period * 0.5)), int(round(period * 2))
    offs = np.arange(-hi, -lo + 1)
    pen = -tight * (np.log(-offs / period)) ** 2
    for t in range(hi, n):
        cand = score[t + offs] + pen
        k = int(np.argmax(cand))
        score[t] = o[t] + cand[k]
        back[t] = t + offs[k]
    # Ende: bester Wert in der letzten Periode
    tail = max(0, n - int(period * 1.5))
    t = tail + int(np.argmax(score[tail:]))
    beats = []
    while t >= 0:
        beats.append(t)
        t = back[t]
    beats = np.array(beats[::-1])
    if len(beats) < 4:                                    # Notfall: gleichmäßiges Raster
        beats = np.arange(0, n, max(1, int(period)))
    return beats


def chroma_frames(S):
    freqs = np.fft.rfftfreq(NFFT, 1.0 / SR)
    ok = (freqs > 60) & (freqs < 2400)
    pc = np.round(12 * np.log2(freqs[ok] / 440.0)).astype(int) % 12
    M = np.zeros((ok.sum(), 12), np.float32)
    M[np.arange(ok.sum()), pc] = 1
    C = (S[:, ok] ** 2) @ M
    return C


def sync(feat, beats, n_frames):
    edges = np.concatenate([beats, [n_frames]])
    out = []
    for a, b in zip(edges[:-1], edges[1:]):
        b = max(b, a + 1)
        out.append(feat[a:b].mean(axis=0))
    return np.array(out)


def norm01(x):
    lo, hi = np.percentile(x, 5), np.percentile(x, 95)
    return np.clip((x - lo) / max(hi - lo, 1e-9), 0, 1)


def repetition(C, bar=4):
    """Je Schlag: wie stark sich die Harmonien an anderer Stelle (≥ 4 Takte entfernt) wiederholen."""
    nb = len(C)
    if nb < bar * 6:
        return np.zeros(nb)
    Cn = C / (np.linalg.norm(C, axis=1, keepdims=True) + 1e-9)
    X = np.concatenate([np.roll(Cn, -k, axis=0) for k in range(bar)], axis=1)
    X /= (np.linalg.norm(X, axis=1, keepdims=True) + 1e-9)
    Sm = X @ X.T
    L = bar * 2                                           # 2 Takte am Stück ähnlich
    D = np.zeros_like(Sm)
    for m in range(L):
        D[:nb - m, :nb - m] += Sm[m:, m:]
    D /= L
    idx = np.arange(nb)
    far = np.abs(idx[:, None] - idx[None, :]) >= bar * 4
    D = np.where(far, D, -1)
    rep = D.max(axis=1)
    # über ein Fenster von 2 Takten verteilen (jeder Schlag im wiederholten Stück zählt)
    rep = np.array([rep[max(0, i - L + 1):i + 1].max() for i in range(nb)])
    return norm01(rep)


def analyse(ffmpeg, path, run, duration=None):
    y = load_audio(ffmpeg, path, run)
    fps = SR / HOP
    S = stft_mag(y)
    o = onset_envelope(S)
    period = tempo_period(o, fps)
    beats = track_beats(o, period)
    bt = beats * HOP / SR
    rms = np.sqrt(np.mean((S ** 2), axis=1) + 1e-12)
    E = sync(20 * np.log10(rms + 1e-9)[:, None], beats, len(S))[:, 0]
    En = norm01(E)
    C = sync(chroma_frames(S), beats, len(S))
    rep = repetition(C)
    on = norm01(sync(o[:, None], beats, len(S))[:, 0])
    # Taktanfang: Phase (0..3) mit den stärksten Einsätzen
    phase = int(np.argmax([on[p::4].mean() if len(on[p::4]) else 0 for p in range(4)]))
    total = duration or len(y) / SR
    return {'beats': bt, 'energy': En, 'rep': rep, 'onset': on, 'phase': phase, 'bpm': 60 * fps / period, 'total': total}


# ---------- Songtext ----------
def clean_line(t):
    return re.sub(r'[^\w\s]', '', t.lower()).strip()


def lyric_features(lines, beats):
    """lines: [{start, end, text}] -> je Schlag: Wiederholung (0/1) + Gefühlswörter."""
    nb = len(beats)
    lrep = np.zeros(nb)
    lemo = np.zeros(nb)
    keys = [clean_line(l['text']) for l in lines]
    counts = []
    for i, k in enumerate(keys):
        c = sum(1 for j, q in enumerate(keys) if j != i and k and q and SequenceMatcher(None, k, q).ratio() >= 0.75)
        counts.append(c)
    for l, k, c in zip(lines, keys, counts):
        sel = (beats >= l['start'] - 0.2) & (beats <= l['end'] + 0.2)
        if c >= 1 and len(k) > 3:
            lrep[sel] = np.maximum(lrep[sel], min(1.0, 0.6 + 0.2 * c))
        txt = ' ' + k + ' '
        emo = sum(1 for w in EMO_WORDS if (' ' + w + ' ') in txt or (' ' + w) in txt and len(w) > 4)
        if emo:
            lemo[sel] = np.maximum(lemo[sel], min(1.0, 0.4 + 0.3 * emo))
    return lrep, lemo, counts


# ---------- Vorschläge ----------
def suggest(A, length, lines=None, learned=None):
    bt, E, R, ph = A['beats'], A['energy'], A['rep'], A['phase']
    total = A['total']
    nb = len(bt)
    if total <= length + 0.5 or nb < 8:
        return [{'kind': 'all', 'name': 'Ganzer Song', 'start': 0.0, 'end': round(total, 2),
                 'why': 'Der Song ist nicht länger als die gewählte Länge.', 'score': 1.0}]
    bp = float(np.median(np.diff(bt))) if nb > 1 else 0.5
    n = max(4, int(round(length / bp)))
    starts = [i for i in range(ph, nb, 4) if bt[i] + length <= total + 0.01] or [0]
    lrep, lemo = (np.zeros(nb), np.zeros(nb))
    lyr = bool(lines)
    if lyr:
        lrep, lemo, _ = lyric_features(lines, bt)
    rise = np.zeros(nb)
    w = 16
    for i in range(w, nb - w):
        rise[i] = E[i:i + w].mean() - E[i - w:i].mean()

    def win(i):
        return slice(i, min(nb, i + n))

    def chorus(i):
        s = win(i)
        return 0.5 * R[s].mean() + 0.35 * E[s].mean() + (0.35 * lrep[s].mean() if lyr else 0)

    def drop(i):
        s = win(i)
        lead = max(2, min(8, n // 5))                     # kurz vor dem Drop anfangen
        j = min(nb - 1, i + lead)
        return 0.7 * max(0, rise[max(0, j - 2):j + 3].max()) + 0.4 * E[s].mean()

    def feat(i):
        s = win(i)
        return {'energy': float(E[s].mean()), 'rep': float(R[s].mean()), 'rise': float(max(0.0, rise[s].max()))}

    L = learned or {}
    pref, conf = L.get('feat'), float(L.get('conf') or 0)

    def taste(i):
        """Gelernt: wie nah klingt die Stelle an dem, was der Nutzer bisher gewählt hat (0 … 0,25)."""
        if not pref or conf <= 0:
            return 0.0
        f = feat(i)
        d = sum(abs(f[k] - pref.get(k, f[k])) for k in f) / len(f)
        return 0.25 * conf * max(0.0, 1.0 - 2.0 * d)

    def emo(i):
        s = win(i)
        e = E[s]
        if lyr and lemo[s].sum() > 0:
            return 0.6 * lemo[s].mean() + 0.25 * E[s].mean() + 0.15 * R[s].mean()
        k = max(2, len(e) // 4)
        return 0.6 * max(0, e[-k:].mean() - e[:k].mean()) + 0.4 * e[-k:].mean()

    kinds = [('chorus', 'Refrain', chorus), ('drop', 'Höhepunkt / Drop', drop), ('emo', 'Emotionaler Aufbau', emo)]
    out = []
    for kind, name, fn in kinds:
        scored = sorted(((fn(i) + taste(i), i) for i in starts), reverse=True)
        for sc, i in scored:
            a = bt[i]
            if all(abs(a - o['start']) >= length * 0.75 for o in out):
                sh = float(L.get('shift') or 0)
                if abs(sh) >= bp * 0.5:                       # gelernt: Nutzer verschiebt meist um sh Sekunden -> auf Schlag runden
                    k = int(np.argmin(np.abs(bt - (a + sh))))
                    if bt[k] + length <= total + 0.01:
                        a = bt[k]
                a = max(0.0, a - 0.03)                       # Anschlag des ersten Schlags nicht abschneiden
                end = min(a + length, total)
                out.append({'kind': kind, 'name': name, 'start': round(float(a), 2), 'end': round(float(end), 2),
                            'score': round(float(sc), 3), 'why': why(kind, i, n, E, R, rise, lrep, lemo, lyr),
                            'feat': {k: round(v, 4) for k, v in feat(i).items()}})
                break
    for o in out:
        o['lyric'] = excerpt(lines, o['start'], o['end']) if lyr else ''
    prefs = L.get('prefs')
    if prefs and (L.get('n') or 0) >= 2:                  # gelernt: Lieblings-Art zuerst
        out.sort(key=lambda o: -prefs.get(o['kind'], 0))
        out[0]['fav'] = True
    return out


def why(kind, i, n, E, R, rise, lrep, lemo, lyr):
    s = slice(i, i + n)
    if kind == 'chorus':
        if lyr and lrep[s].mean() > 0.25:
            return 'Diese Textzeilen kommen im Song mehrmals vor – typisch für den Refrain.'
        return 'Dieser Teil wiederholt sich im Song und ist kräftig – typisch für den Refrain.'
    if kind == 'drop':
        return 'Hier steigt die Energie am stärksten an – der Höhepunkt des Songs.'
    if lyr and lemo[s].sum() > 0:
        return 'Hier stehen die meisten gefühlvollen Worte im Text.'
    return 'Die Musik baut sich hier auf und wird zum Ende hin stärker.'


def excerpt(lines, a, b):
    if not lines:
        return ''
    t = [l['text'].strip() for l in lines if l['end'] > a and l['start'] < b and l['text'].strip()]
    s = ' / '.join(t)
    return (s[:110] + ' …') if len(s) > 110 else s


def fmt(t):
    t = max(0.0, float(t))
    m = int(t // 60)
    s = t - m * 60
    return '%d:%04.1f' % (m, s) if abs(s - round(s)) > 0.05 else '%d:%02d' % (m, int(round(s)))

"""Echter KI-Video-Test (GitHub, Windows, nur Prozessor): Paket laden wie beim Nutzer, dann winzige Stücke
mit dem echten Modell rechnen, aneinanderreihen, zusammensetzen und prüfen.

Aufruf: python tools/aivideo_test.py <sd-cli.exe> <ffmpeg.exe> <ausgabeordner>
"""
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import aivideo  # noqa: E402
import upscale  # noqa: E402
import hwinfo  # noqa: E402

sd, ffmpeg, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
UPDIR = sys.argv[sys.argv.index('--upscaler') + 1] if '--upscaler' in sys.argv else None
out.mkdir(parents=True, exist_ok=True)
log = []


def say(*a):
    t = ' '.join(str(x) for x in a)
    print(t, flush=True)
    log.append(t)


home = out / 'home'
A = aivideo.AIVideo(home, Path(sd).parent.parent, Path(sd).parent.parent, ffmpeg)
A.sd = sd
say('Geräte:', A.devices())
say('KI-Dienst (sd-server):', A.server_exe or 'fehlt')
say('Hardware-Analyse:', json.dumps(hwinfo.analyze(A.devices(), home, A.need_gb()), ensure_ascii=False))

# 1) Paket laden – genau wie beim Nutzer
t0 = time.time()
A.download()
while A.dl['state'] == 'running':
    time.sleep(5)
    say('Download %d %% (%s GB) %s' % (A.dl['percent'], A.dl['done_gb'], A.dl.get('file', '')))
say('Download:', A.dl['state'], A.dl['error'], 'in %d s' % (time.time() - t0))
if not A.ready():
    raise SystemExit('Paket nicht bereit')
say('Dateien:', {k: (v.name, round(v.stat().st_size / 1024 ** 3, 2)) for k, v in A.files().items()})
if '--download-only' in sys.argv:
    raise SystemExit(0)

# 2) Testbild (Gesicht-ähnliche Formen, kräftige Farben)
img = np.zeros((704, 1280, 3), np.uint8)
for y in range(704):
    img[y] = (60 + y // 6, 20, 120 + y // 8)
cv2.circle(img, (640, 330), 190, (150, 170, 230), -1)
cv2.circle(img, (570, 290), 26, (40, 40, 40), -1)
cv2.circle(img, (710, 290), 26, (40, 40, 40), -1)
cv2.ellipse(img, (640, 420), (80, 30), 0, 0, 180, (60, 40, 160), 10)
for i in range(40):
    cv2.line(img, (300 + i * 3, 520), (220 + i * 9, 704), (200, 120, 255), 2)
still = out / 'start.png'
cv2.imwrite(str(still), img)

# winzige Größe, damit es auf dem Prozessor in Minuten geht; Ablauf ist derselbe wie beim Nutzer
aivideo.QUALITIES['test'] = (256, 160, 9, 120)
aivideo.ANCHOR = 2
aivideo.XFADE = 3
opts = {'key': '0123456789abcdef', 'quality': 'test', 'motion': 'hair', 'text': 'sanfte Bewegung', 'vertical': False,
        'fmt': 'yt1080', 'seed': 11, 'length': 1.0}


def wait(jid):
    while True:
        v = A.view(jid)
        if v['state'] not in ('läuft', 'wartet'):
            return v
        time.sleep(5)
        say('  %s %d %% %s' % (v['kind'], v['percent'], v.get('note', '')))


t0 = time.time()
v = wait(A.start('variants', still, dict(opts, seeds=[11])))
say('Variante:', v['state'], v['error'], 'in %d s' % (time.time() - t0), '· Weg:', 'sd-server' if A.server else 'sd-cli', A.server_error)
if v['state'] != 'fertig':
    for lg in (home / 'aivideo' / 'jobs').rglob('sd.log'):
        say(lg.read_text('utf-8', 'replace')[-3000:])
    raise SystemExit('Variante fehlgeschlagen')
for lg in (home / 'aivideo' / 'jobs').rglob('segment-000.log'):
    say('--- sd-cli Protokoll (Auszug) ---')
    for ln in lg.read_text('utf-8', 'replace').replace('\r', '\n').splitlines():
        if any(w in ln.lower() for w in ('loaded', 'load', 'sampling', 'completed', 'decode', 'backend', 'vulkan', 'cpu', 'took', 'time', 'mb')) and len(ln) < 300:
            say('   ', ln.strip())
# 3 Stücke: 0 (vorhanden), 1 (angehängt), 2 (Rückkehr zum Original mit Überblendung)
segs = aivideo.plan(1.0, 9)
opts['length'] = (9 + 8 + 6) / aivideo.GEN_FPS
say('Plan:', aivideo.plan(opts['length'], 9))
t0 = time.time()
v = wait(A.start('full', still, opts))
say('Volle Länge:', v['state'], v['error'], v.get('result'), 'in %d s' % (time.time() - t0))
if v['state'] != 'fertig':
    raise SystemExit('Volle Länge fehlgeschlagen')
clip = A.clip_path(v['result']['clip'])
say('Volle Länge über:', 'sd-server (Modell blieb geladen)' if A.server else 'sd-cli', A.server_error)
say('Länge Ergebnis:', A.duration(clip), 's · Tempo je Stück:', A.speeds())

# 3) Prüfen: erstes Bild ähnelt dem Startbild, es gibt Bewegung, keine kaputten (einfarbigen) Bilder
frames = list(A._frames(clip, 256, 160))
start_small = cv2.cvtColor(cv2.resize(img, (256, 160), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB).astype(np.float32)
f0 = frames[0].astype(np.float32)
corr = float(np.corrcoef(f0.ravel(), start_small.ravel())[0, 1])
motion = float(np.mean([np.abs(frames[i + 1].astype(np.float32) - frames[i].astype(np.float32)).mean() for i in range(len(frames) - 1)]))
flat = min(float(f.std()) for f in frames)
say('Bilder: %d · Ähnlichkeit erstes Bild/Start: %.3f · Bewegung je Bild: %.2f · kleinste Streuung: %.1f' % (len(frames), corr, motion, flat))
sheet = np.vstack([np.hstack(frames[i:i + 6]) for i in range(0, len(frames) - len(frames) % 6, 6)][:4])
cv2.imwrite(str(out / 'bilder.png'), cv2.cvtColor(sheet, cv2.COLOR_RGB2BGR))
for p in (home / 'aivideo' / 'jobs').rglob('*.mp4'):
    (out / ('video-' + p.parent.name + '-' + p.name)).write_bytes(p.read_bytes())
(out / 'ergebnis.txt').write_text('\n'.join(log), 'utf-8')
# KI-Upscaler: Full-HD-Lauf mit Hochrechnung je Stück + Schärfevergleich
if UPDIR:
    U = upscale.Upscaler(UPDIR)
    A.upscaler = U
    say('Upscaler verfügbar:', U.available())
    t0 = time.time()
    v = wait(A.start('full', still, dict(opts, up=True)))
    say('Volle Länge mit Upscaler:', v['state'], v['error'], v.get('result'), 'in %d s' % (time.time() - t0), 'Gerät:', U.device)
    if v['state'] != 'fertig' or not v['result']['clip'].endswith('-hd.mp4'):
        raise SystemExit('Upscaler-Lauf fehlgeschlagen')
    hd = list(A._frames(A.clip_path(v['result']['clip']), 1920, 1080))
    say('HD-Bilder:', len(hd), hd[0].shape)
    small = cv2.cvtColor(cv2.resize(img, (480, 270), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)
    t0 = time.time()
    ki = U.to_size(small, 1920, 1080)
    say('Upscaler 480x270 -> 1920x1080 in %.2f s' % (time.time() - t0))
    bic = cv2.resize(small, (1920, 1080), interpolation=cv2.INTER_CUBIC)
    sharp = lambda a: float(cv2.Laplacian(cv2.cvtColor(a, cv2.COLOR_RGB2GRAY), cv2.CV_64F).var())
    say('Schärfe KI %.1f · normal %.1f' % (sharp(ki), sharp(bic)))
    cv2.imwrite(str(out / 'upscaler.png'), cv2.cvtColor(np.hstack([bic[300:780, 400:1100], ki[300:780, 400:1100]]), cv2.COLOR_RGB2BGR))

# Qualitätsblick in echter Größe (832 × 480, kurz): einzelne Bilder fürs Auge
if '--quality' in sys.argv:
    aivideo.QUALITIES['q'] = (832, 480, 9, 900)
    t0 = time.time()
    v = wait(A.start('variants', still, dict(opts, key='fedcba9876543210', quality='q', seeds=[7], cmatch=0.85)))
    say('Qualitätsblick 832x480:', v['state'], v['error'], 'in %d s' % (time.time() - t0))
    if v['state'] == 'fertig':
        fr = list(A._frames(A.jobs_dir / 'fedcba9876543210' / 'seed-7' / 'segment-000.mp4', 832, 480))
        pick = [fr[i] for i in (0, len(fr) // 3, 2 * len(fr) // 3, len(fr) - 1)]
        cv2.imwrite(str(out / 'qualitaet.png'), cv2.cvtColor(np.vstack([np.hstack(pick[:2]), np.hstack(pick[2:])]), cv2.COLOR_RGB2BGR))
# Schnelltest der Hardware (wie Knopf „Schnelltest“) – auf GitHub nur Prozessor
t0 = time.time()
v = wait(A.start_bench(['cpu'], [-1] if A.upscaler is not None else []))
say('Schnelltest:', v['state'], v['error'], v.get('result'), 'in %d s' % (time.time() - t0))
bench_ok = v['state'] == 'fertig' and v['result']['gen'].get('cpu')
# Vergleich: dasselbe Stück über sd-cli (Modell wird neu geladen)
if A.server_exe:
    A.shutdown()
    A.hw = dict(A.hw, server=False)
    t0 = time.time()
    v = wait(A.start('variants', still, dict(opts, key='0123456789abcd00', seeds=[5])))
    say('Gleiches Stück über sd-cli (lädt neu):', v['state'], 'in %d s' % (time.time() - t0), '· Tempo je Stück:', A.speeds())
# 1.10.0 Tempo-Training (prüft auch, dass alle Schalter vom echten KI-Motor angenommen werden)
A.hw = dict(A.hw, server=True, gen='cpu', vendor='cpu', vram=0)
t0 = time.time()
v = wait(A.start_training('test'))
say('Training:', v['state'], v['error'], v.get('result'), 'in %d s' % (time.time() - t0))
say('Gedächtnis:', json.dumps(A.tuner.summary(), ensure_ascii=False))
q = A.quality_of('0123456789abcdef/seed-11')
say('Qualitäts-Messwerte:', q, 'Note:', A.tuner.score(q))
train_ok = v['state'] == 'fertig' and any(isinstance(x, float) for x in v['result']['recipes'].values())
ok = bench_ok and train_ok and corr > 0.5 and motion > 0.2 and flat > 3
say('ERGEBNIS:', 'OK' if ok else 'AUFFÄLLIG')
sys.exit(0 if ok else 2)

"""KI-Video (1.8.0): echte Bewegung aus einem Bild – offline auf dem eigenen PC.

Motor: stable-diffusion.cpp (sd-cli, Vulkan – läuft auf AMD/NVIDIA/Intel ohne Zusatz-Installation)
Modell: Wan 2.2 TI2V 5B Turbo (Apache 2.0) als 4-Bit-GGUF + umt5-Text-Encoder + Wan-2.2-VAE.
Die Modelle sind ein freiwilliges Zusatz-Paket (ca. 8 GB) im Einstellungsordner.

Ablauf
- Varianten: das erste Stück (ca. 4–5 s) mit 3 verschiedenen Zufallszahlen -> Nutzer wählt.
- Volle Länge: Stück für Stück aneinandergereiht (Startbild = letztes Bild des vorigen Stücks).
  Alle ANCHOR Stücke startet ein Stück wieder beim Original-Bild und wird weich überblendet
  (verhindert, dass Farben/Gesicht mit der Zeit „verlaufen“). Am Ende Rückkehr zum Original
  -> die Datei lässt sich nahtlos wiederholen.
- Jedes fertige Stück wird gespeichert (segment-XXX.mp4 + letztes Bild) -> Abbruch/Neustart macht dort weiter.

1.9.0 Tempo
- Die KI bleibt geladen (sd-server): die 8 GB werden einmal pro Auftrag geladen statt für jedes Stück neu.
  Klappt der Server nicht, rechnet sd-cli wie bisher (automatischer Rückfall).
- Feste Zuordnung aus der Hardware-Analyse: Bewegung + VAE auf der stärksten Karte, Text-Teil auf Prozessor,
  KI-Upscaler gleichzeitig auf der zweiten Karte (eigener Arbeitsfaden, rechnet Stück n während Stück n+1 entsteht).
"""
import base64
import tuner as tunerlib
import hwinfo
import queue
import socket
import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

import numpy as np

try:
    import cv2
except Exception:  # noqa: BLE001
    cv2 = None

GEN_FPS = 24                       # Wan 2.2 TI2V 5B arbeitet mit 24 Bildern/s
XFADE = 12                         # Bilder für weiche Überblendung (0,5 s)
ANCHOR = 6                         # alle 6 Stücke (~25–30 s) zurück zum Original
QUALITIES = {                      # Kurzname: (lange Seite, kurze Seite, Bilder je Stück, Schätzung Sekunden je Stück)
    'turbo': (640, 352, 97, 140),  # 1.11.0: sehr schnell, danach KI-Upscaler (unter 832×480 wird die KI weicher)
    'fast': (832, 480, 97, 240),
    'good': (1280, 704, 121, 900),
}
QUALITY_NAMES = {'turbo': 'Sehr schnell (640 × 352)', 'fast': 'Schnell (832 × 480)', 'good': 'Beste Qualität (1280 × 704)'}
MODEL = {
    'steps': 4, 'cfg': 1.0, 'sampler': 'euler', 'flow_shift': 5.0,
    'files': [  # Schlüssel, Hugging-Face-Repo, Dateimuster, ungefähre Größe (GB)
        ('diffusion', 'hum-ma/Wan2.2-TI2V-5B-Turbo-GGUF', r'(?i)(^|/)[^/]*q4_k_m\.gguf$', 3.2),
        ('t5', 'city96/umt5-xxl-encoder-gguf', r'(?i)(^|/)umt5-xxl-encoder-q4_k_m\.gguf$', 3.4),
        ('vae', 'QuantStack/Wan2.2-TI2V-5B-GGUF', r'(?i)^vae/wan2\.2_vae\.safetensors$', 1.3),
    ],
}
HF = os.environ.get('BES_HF', 'https://huggingface.co')
MOTIONS = [  # Kennung, Anzeige, englische Beschreibung für die KI
    ('hair', 'Haare wehen', 'hair gently blowing in a soft breeze, subtle natural movement'),
    ('blink', 'Blinzeln + leichte Kopfbewegung', 'the person blinks naturally and slightly turns the head, calm and subtle'),
    ('breath', 'Sanftes Atmen', 'subtle breathing motion, chest and shoulders gently rising and falling, calm'),
    ('cloth', 'Stoff / Kleidung bewegt sich', 'fabric and clothes gently flowing and rippling in the wind'),
    ('dance', 'Tanzen zur Musik', 'the person dances smoothly to the music, rhythmic body movement'),
    ('sing', 'Singen', 'the person sings emotionally, mouth moving with the lyrics, expressive face'),
    ('water', 'Wasser / Wellen', 'water surface rippling and waves moving gently, shimmering reflections'),
    ('sky', 'Wolken / Himmel ziehen', 'clouds slowly drifting across the sky, gentle light changes'),
    ('light', 'Licht flackert', 'lights softly flickering and glowing, neon reflections pulsing'),
    ('smoke', 'Rauch / Nebel wabert', 'smoke and mist slowly swirling and drifting'),
    ('fire', 'Feuer / Kerzen', 'flames and candle light flickering naturally'),
    ('camera', 'Langsame Kamerafahrt', 'slow cinematic camera push-in, subtle parallax, stable subject'),
]
MOTION_IDS = [m[0] for m in MOTIONS]
STYLE_SUFFIX = 'high quality, smooth motion, consistent colors, stable composition, no text'


HD = {False: (1920, 1080), True: (1080, 1920)}     # Ziel des KI-Upscalers (Full HD)


def prompt_for(motion, text, extra=()):
    """Beschreibung für die KI: Bewegung + eigener Text + Änderungswünsche/Gelerntes aus den Bewertungen."""
    base = dict((m[0], m[2]) for m in MOTIONS).get(motion, MOTIONS[0][2])
    text = re.sub(r'\s+', ' ', str(text or '')).strip()[:300]
    parts = [base] + ([text] if text else []) + [e for e in extra if e] + [STYLE_SUFFIX]
    return ', '.join(parts)


def color_match(frames, ref, strength=0.9):
    """Farben der KI-Bilder ans Original angleichen (Lab-Mittelwert/Streuung). Die Korrektur wird aus dem Durchschnitt
    des ganzen Stücks berechnet und auf alle Bilder gleich angewendet – so gibt es keinen Farbsprung nach dem ersten Bild,
    kein Flackern und kein Wegdriften der Farben bei langen Videos. Das erste Bild (= Startbild) bleibt unverändert."""
    if cv2 is None or strength <= 0 or len(frames) < 2:
        return frames
    r = cv2.cvtColor(ref, cv2.COLOR_BGR2LAB).astype(np.float32).reshape(-1, 3)
    rm, rs = r.mean(0), r.std(0) + 1e-3
    labs = [cv2.cvtColor(f, cv2.COLOR_BGR2LAB).astype(np.float32) for f in frames]
    st = np.array([[l.reshape(-1, 3).mean(0), l.reshape(-1, 3).std(0) + 1e-3] for l in labs[1:]])
    m, sd = st[:, 0].mean(0), st[:, 1].mean(0)
    out = [frames[0]]
    for lab in labs[1:]:
        fixed = (lab - m) / sd * rs + rm
        lab = lab * (1 - strength) + fixed * strength
        out.append(cv2.cvtColor(np.clip(lab, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR))
    return out


def gen_size(quality, vertical):
    lw, sw, frames, _ = QUALITIES.get(quality, QUALITIES['fast'])
    return (sw, lw, frames) if vertical else (lw, sw, frames)


def plan(length_s, frames):
    """Stücke für eine Ziellänge: [(index, anchor)], anchor=True -> startet beim Original."""
    want = max(frames, int(round(length_s * GEN_FPS)))
    segs, total, i = [(0, True)], frames, 1
    while total < want:
        anchor = i % ANCHOR == 0
        segs.append((i, anchor))
        total += frames - (XFADE if anchor else 1)
        i += 1
    return segs


RAM_MSG = ('Der Arbeitsspeicher war voll – Windows hat die KI beendet. Bitte große Programme (Browser, Spiele) schließen '
           'und „Aufräumen & starten“ benutzen.')
OOM = re.compile(r'out of memory|ErrorOutOfDeviceMemory|failed to allocate', re.I)
NOPROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class SdServer:
    """stable-diffusion.cpp als Hintergrund-Dienst (nur 127.0.0.1): Modelle bleiben im Grafikspeicher."""

    def __init__(self, exe, args, log, nw, sig):
        self.exe, self.args, self.log, self.nw, self.sig = exe, args, Path(log), nw, sig
        self.proc = None
        self.port = 0
        self.last = time.time()
        self.ram_low = 0.0                 # 1.11.0: letzter Zeitpunkt mit < 1 GB freiem Arbeitsspeicher

    def _watch_ram(self):
        while self.alive():
            if (hwinfo.ram_gb()[1] or 99) < 1.0:
                self.ram_low = time.time()
            time.sleep(0.5)

    def ram_crash(self):
        """War der Arbeitsspeicher kurz vor dem Absturz voll?"""
        return time.time() - self.ram_low < 15 or bool(re.search(r'bad_alloc|not enough memory|cannot allocate', self.tail(), re.I))

    def touch(self):
        self.last = time.time()

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def tail(self, n=3000):
        try:
            return self.log.read_bytes()[-n:].decode('utf-8', 'replace')
        except OSError:
            return ''

    def _req(self, path, body=None, timeout=10):
        data = json.dumps(body).encode('utf-8') if body is not None else None
        rq = urllib.request.Request('http://127.0.0.1:%d%s' % (self.port, path), data=data,
                                    headers={'Content-Type': 'application/json'} if data else {})
        with NOPROXY.open(rq, timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8') or '{}')

    def start(self, job, timeout=1800):
        with socket.socket() as so:
            so.bind(('127.0.0.1', 0))
            self.port = so.getsockname()[1]
        self.log.parent.mkdir(parents=True, exist_ok=True)
        lf = open(self.log, 'wb')
        self.proc = subprocess.Popen([self.exe, '--listen-ip', '127.0.0.1', '--listen-port', str(self.port)] + self.args,
                                     stdout=lf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, creationflags=self.nw,
                                     cwd=str(self.log.parent))
        lf.close()
        threading.Thread(target=self._watch_ram, daemon=True).start()
        t0 = time.time()
        while time.time() - t0 < timeout:
            if job.get('cancel'):
                raise RuntimeError('abgebrochen')
            if self.proc.poll() is not None:
                t = self.tail()
                if OOM.search(t):
                    raise RuntimeError('Der Grafikspeicher reicht nicht.')
                if self.ram_crash():
                    raise RuntimeError(RAM_MSG)
                raise RuntimeError('KI-Dienst beendet: ' + (t.strip().splitlines() or [''])[-1][:200])
            try:
                self._req('/sdcpp/v1/capabilities', timeout=3)
                return
            except Exception:  # noqa: BLE001
                time.sleep(1.5)
        raise RuntimeError('KI-Dienst startet nicht (Zeit überschritten)')

    def generate(self, body, job, prog):
        try:
            r = self._req('/sdcpp/v1/vid_gen', body, timeout=120)
        except Exception as ex:  # noqa: BLE001  – Dienst beim Auftrag abgestürzt (oft Grafikspeicher)
            for _ in range(20):
                if not self.alive():
                    break
                time.sleep(0.25)
            if OOM.search(self.tail()):
                raise RuntimeError('Der Grafikspeicher reicht nicht – bitte „Schnell“ wählen oder andere Programme schließen.')
            if self.ram_crash():
                raise RuntimeError(RAM_MSG)
            raise RuntimeError('Die KI hat den Auftrag nicht angenommen: %s' % ex)
        jid = r.get('id')
        if not jid:
            raise RuntimeError('KI-Dienst hat den Auftrag abgelehnt: %s' % (r.get('error') or r))
        try:
            while True:
                if job.get('cancel'):
                    try:
                        self._req('/sdcpp/v1/jobs/%s/cancel' % jid, {}, timeout=5)
                    except Exception:  # noqa: BLE001
                        pass
                    raise RuntimeError('abgebrochen')
                if not self.alive():
                    t = self.tail()
                    if OOM.search(t):
                        raise RuntimeError('Der Grafikspeicher reicht nicht – bitte „Schnell“ wählen oder andere Programme schließen.')
                    if self.ram_crash():
                        raise RuntimeError(RAM_MSG)
                    raise RuntimeError('Die KI wurde unerwartet beendet.')
                try:
                    st = self._req('/sdcpp/v1/jobs/' + jid, timeout=30)
                except Exception:  # noqa: BLE001
                    time.sleep(1)
                    continue
                pg = st.get('progress') or {}
                if pg.get('total'):
                    prog(int(pg.get('completed') or 0), int(pg['total']))
                state = st.get('status')
                if state == 'completed':
                    self.touch()
                    return st.get('result') or {}
                if state in ('failed', 'cancelled'):
                    t = self.tail()
                    if OOM.search(t):
                        raise RuntimeError('Der Grafikspeicher reicht nicht – bitte „Schnell“ wählen oder andere Programme schließen.')
                    raise RuntimeError('Die KI konnte das Stück nicht berechnen. %s' % (st.get('error') or (t.strip().splitlines() or [''])[-1][:200]))
                time.sleep(0.8)
        finally:
            self.touch()

    def stop(self):
        p, self.proc = self.proc, None
        if p and p.poll() is None:
            try:
                p.kill()
                p.wait(10)
            except Exception:  # noqa: BLE001
                pass


class AIVideo:
    def __init__(self, home, app_dir, base_dir, ffmpeg, no_window=0):
        self.dir = Path(home).resolve() / 'aivideo'
        self.models = Path(os.environ.get('BES_AIMODELS') or (self.dir / 'models')).resolve()
        self.jobs_dir = self.dir / 'jobs'
        self.tuner = tunerlib.Tuner(self.dir / 'tuner.json')     # 1.10.0: Gedächtnis für Tempo + Qualität
        self.active_rid = None                                    # Rezept des laufenden Auftrags
        self.ffmpeg = ffmpeg
        self.nw = no_window
        cands = [os.environ.get('BES_SDCLI') or '']
        for d in (Path(app_dir), Path(base_dir)):
            cands += [str(d / 'sdcpp' / 'sd-cli.exe'), str(d / 'sdcpp' / 'sd-cli')]
        cands.append(shutil.which('sd-cli') or '')
        self.sd = next((c for c in cands if c and Path(c).is_file()), '')
        self.dl = {'state': 'idle', 'percent': 0, 'error': '', 'done_gb': 0.0, 'total_gb': 0.0}
        self.jobs = {}
        self.lock = threading.Lock()          # nur eine KI-Rechnung gleichzeitig
        self.blocker = lambda: False          # 1.11.0: vom Programm gesetzt (normale Umwandlung läuft?)
        self._devices = None
        self.speed_file = self.dir / 'speed.json'
        self.upscaler = None                 # wird vom Programm gesetzt (upscale.Upscaler)
        self.hw = {}                         # 1.9.0: Zuordnung aus der Hardware-Analyse (gen/te/decode_frames/server)
        srv = [str(Path(self.sd).with_name('sd-server' + Path(self.sd).suffix))] if self.sd else []
        self.server_exe = next((c for c in srv + [os.environ.get('BES_SDSERVER') or ''] if c and Path(c).is_file()), '')
        self.server = None
        self.server_error = ''

    # ---------- Paket ----------
    def manifest_path(self):
        return self.models / 'manifest.json'

    def files(self):
        try:
            m = json.loads(self.manifest_path().read_text('utf-8'))
            return {k: self.models / v for k, v in m.items()}
        except Exception:  # noqa: BLE001
            return {}

    def ready(self):
        f = self.files()
        return bool(self.sd) and all(k in f and f[k].is_file() for k, *_ in MODEL['files'])

    def need_gb(self):
        return round(sum(x[3] for x in MODEL['files']), 1)

    def free_gb(self):
        try:
            self.models.mkdir(parents=True, exist_ok=True)
            return round(shutil.disk_usage(str(self.models)).free / 1024 ** 3, 1)
        except OSError:
            return 0.0

    def status(self):
        running = [self.view(j['id']) for j in self.jobs.values() if j['state'] in ('läuft', 'wartet') and j['kind'] != 'bench']
        return {'tool': bool(self.sd), 'ready': self.ready(), 'download': dict(self.dl), 'need_gb': self.need_gb(), 'running': running,
                'free_gb': self.free_gb(), 'devices': self.devices() if self.sd else [], 'speed': self.speeds(),
                'motions': [[m[0], m[1]] for m in MOTIONS], 'qualities': QUALITY_NAMES, 'folder': str(self.models)}

    def download(self):
        if self.dl['state'] == 'running':
            return
        self.dl = {'state': 'running', 'percent': 0, 'error': '', 'done_gb': 0.0, 'total_gb': self.need_gb(), 'file': ''}
        threading.Thread(target=self._download, daemon=True).start()

    def _hf_list(self, repo):
        req = urllib.request.Request('%s/api/models/%s/tree/main?recursive=1' % (HF, repo), headers={'User-Agent': 'ffmpeg_encode-Studio'})
        with urllib.request.urlopen(req, timeout=30) as r:
            items = json.loads(r.read().decode('utf-8'))
        return [(i['path'], int(i.get('size') or (i.get('lfs') or {}).get('size') or 0)) for i in items if i.get('type') == 'file']

    def _download(self):
        try:
            self.models.mkdir(parents=True, exist_ok=True)
            todo, man = [], {}
            for key, repo, pat, gb in MODEL['files']:
                hits = [(p, s) for p, s in self._hf_list(repo) if re.search(pat, p)]
                if not hits:
                    raise RuntimeError('Datei im Modell-Lager nicht gefunden (%s)' % repo)
                path, size = sorted(hits, key=lambda x: len(x[0]))[0]
                name = path.split('/')[-1]
                man[key] = name
                todo.append((repo, path, name, size))
            if self.free_gb() < sum(t[3] for t in todo) / 1024 ** 3 + 1:
                raise RuntimeError('Zu wenig freier Speicher – es werden ca. %.1f GB gebraucht.' % (sum(t[3] for t in todo) / 1024 ** 3 + 1))
            total = sum(max(t[3], 1) for t in todo)
            self.dl['total_gb'] = round(total / 1024 ** 3, 1)
            done = 0
            for repo, path, name, size in todo:
                dest = self.models / name
                self.dl['file'] = name
                if dest.is_file() and (not size or dest.stat().st_size == size):
                    done += max(size, 1)
                    continue
                part = dest.with_suffix(dest.suffix + '.part')
                have = part.stat().st_size if part.is_file() else 0
                for attempt in range(6):            # Wiederaufnehmen bei Abbruch (Range)
                    try:
                        hdr = {'User-Agent': 'ffmpeg_encode-Studio'}
                        if have:
                            hdr['Range'] = 'bytes=%d-' % have
                        req = urllib.request.Request('%s/%s/resolve/main/%s' % (HF, repo, path), headers=hdr)
                        with urllib.request.urlopen(req, timeout=60) as r:
                            if have and r.status != 206:
                                have = 0
                            with open(part, 'ab' if have else 'wb') as f:
                                while True:
                                    chunk = r.read(1 << 20)
                                    if not chunk:
                                        break
                                    f.write(chunk)
                                    have += len(chunk)
                                    cur = done + min(have, max(size, 1))
                                    self.dl.update(percent=int(cur / total * 100), done_gb=round(cur / 1024 ** 3, 2))
                        break
                    except Exception:  # noqa: BLE001
                        if attempt == 5:
                            raise
                        time.sleep(3 + attempt * 3)
                if size and part.stat().st_size != size:
                    raise RuntimeError('Datei unvollständig: %s' % name)
                os.replace(part, dest)
                done += max(size, 1)
            self.manifest_path().write_text(json.dumps(man), 'utf-8')
            self.dl.update(state='done', percent=100, error='', file='')
        except Exception as ex:  # noqa: BLE001
            self.dl.update(state='error', error='Download fehlgeschlagen: %s – später erneut versuchen, er macht dann dort weiter.' % ex)

    def remove(self):
        shutil.rmtree(self.models, ignore_errors=True)
        self.dl = {'state': 'idle', 'percent': 0, 'error': '', 'done_gb': 0.0, 'total_gb': 0.0}

    # ---------- Geräte / Tempo ----------
    def quality_of(self, ref):
        """Qualitäts-Messwerte zu einem Clip/Ordner (für die Note und das Lernen aus Sternen)."""
        p = Path(ref)
        if not p.is_absolute():
            p = self.jobs_dir / p
        for c in (p, p.parent):
            try:
                return json.loads((c / 'quality.json').read_text('utf-8')).get('f') or {}
            except Exception:  # noqa: BLE001
                pass
        return {}

    def start_training(self, quality='fast', devices=()):
        """Tempo-Training: jedes Rezept einmal mit einem echten Stück (Größe der Qualität, 33 Bilder) messen."""
        if not self.ready():
            raise RuntimeError('Für das Training muss das KI-Video-Paket installiert sein.')
        jid = hashlib.sha1(('%s train' % time.time()).encode()).hexdigest()[:10]
        job = {'id': jid, 'kind': 'bench', 'state': 'wartet', 'percent': 0, 'error': '', 'note': '', 'result': None,
               'cancel': False, 'proc': None, 'started': time.time()}
        self.jobs[jid] = job
        threading.Thread(target=self._train, args=(job, quality, list(devices)), daemon=True).start()
        return jid

    def _train(self, job, quality, devices=()):
        with self.lock:
            job['state'] = 'läuft'
            hw = dict(self.hw)
            gen = hw.get('gen') or 'auto'
            res = {}
            try:
                W, H = QUALITIES[quality][:2]
                d = (self.dir / 'train').resolve()
                d.mkdir(parents=True, exist_ok=True)
                init = d / 'start.png'
                img = np.zeros((H, W, 3), np.uint8)
                img[:] = (70, 50, 120)
                if cv2 is not None:
                    cv2.circle(img, (W // 2, H // 2), H // 3, (150, 190, 235), -1)
                    cv2.GaussianBlur(img, (0, 0), 3, dst=img)
                    cv2.imencode('.png', img)[1].tofile(str(init))
                # 1.11.0 (ersetzt den Schnelltest): bei mehreren Grafikkarten zuerst jede Karte messen, dann die schnellste nehmen
                gpus = {}
                devs = [x for x in devices if x] if len(devices) > 1 else []
                steps = len(devs) + len(self.tuner.candidates(hw.get('vendor') or 'amd', float(hw.get('vram') or 0), gen))
                for k, dev in enumerate(devs):
                    if job['cancel']:
                        raise RuntimeError('abgebrochen')
                    job['note'] = 'Grafikkarte %d von %d wird gemessen …' % (k + 1, len(devs))
                    if self.server:
                        self.server.stop()
                        self.server = None
                    h2 = dict(hw, gen=dev, recipe='standard')
                    try:
                        self._run_sd(init, d / 'f', 'gentle motion, calm', 1, W, H, 9, job, k * 100 // steps, k * 100 // steps, hw=h2)
                        t0 = time.time()
                        self._run_sd(init, d / 'f', 'gentle motion, hair moving in the wind', 2, W, H, 33, job, k * 100 // steps, (k + 1) * 100 // steps, hw=h2)
                        gpus[dev] = round((time.time() - t0) / 33, 3)
                        self.tuner.record(dev, quality, 'standard', sec_per_frame=gpus[dev])
                    except RuntimeError as ex:
                        if job['cancel']:
                            raise
                        gpus[dev] = None
                if gpus and any(gpus.values()):
                    gen = min((v, k) for k, v in gpus.items() if v)[1]
                    hw['gen'] = gen
                cands = self.tuner.candidates(hw.get('vendor') or 'amd', float(hw.get('vram') or 0), gen)
                off = len(devs)
                for n, rid in enumerate(cands):
                    if job['cancel']:
                        raise RuntimeError('abgebrochen')
                    job['note'] = 'Einstellung %d von %d: %s' % (n + 1, len(cands), tunerlib.RECIPES[rid]['name'])
                    if rid == 'standard' and gpus.get(gen):
                        res[rid] = gpus[gen]                # schon beim Kartenvergleich gemessen
                        continue
                    a0, a1 = (off + n) * 100 // steps, (off + n + 1) * 100 // steps
                    if self.server:
                        self.server.stop()
                        self.server = None
                    h2 = dict(hw, recipe=rid)
                    try:
                        # erst laden (kurzes Stück, nicht gemessen), dann messen
                        self._run_sd(init, d / 'f', 'gentle motion, calm', 1, W, H, 9, job, a0, a0, hw=h2)
                        t0 = time.time()
                        self._run_sd(init, d / 'f', 'gentle motion, hair moving in the wind', 2, W, H, 33, job, a0, a1, hw=h2)
                        spf = (time.time() - t0) / 33
                        if self.server is None:      # sd-cli: Ladezeit steckt mit drin -> nur grob
                            spf *= 0.6
                        self.tuner.record(gen, quality, rid, sec_per_frame=spf)
                        res[rid] = round(spf, 3)
                    except RuntimeError as ex:
                        if job['cancel']:
                            raise
                        oom = 'Grafikspeicher' in str(ex)
                        self.tuner.record(gen, quality, rid, oom=oom, fail=not oom)
                        res[rid] = 'Speicher reicht nicht' if oom else 'Fehler'
                    job['percent'] = (off + n + 1) * 100 // steps
                if self.server:
                    self.server.stop()
                    self.server = None
                self.tuner.mark_trained(gen)
                shutil.rmtree(d, ignore_errors=True)
                best = self.tuner.best(gen, quality, hw.get('vendor') or 'amd', float(hw.get('vram') or 0))
                job.update(state='fertig', percent=100, note='', result={'recipes': res, 'best': best, 'gpus': gpus, 'gen': gen,
                                                                        'best_name': tunerlib.RECIPES[best]['name']})
            except Exception as ex:  # noqa: BLE001
                job.update(state='abgebrochen' if job['cancel'] else 'fehler', error=str(ex), result={'recipes': res})

    def cache_info(self):
        """Größe des KI-Zwischenspeichers (fertige Stücke/Clips) in GB."""
        tot = 0
        for f in self.jobs_dir.rglob('*') if self.jobs_dir.is_dir() else []:
            try:
                tot += f.stat().st_size if f.is_file() else 0
            except OSError:
                pass
        return round(tot / 1024 ** 3, 2)

    def clear_cache(self):
        if self.lock.locked():
            raise RuntimeError('Gerade läuft eine KI-Rechnung – bitte erst abwarten oder abbrechen.')
        shutil.rmtree(self.jobs_dir, ignore_errors=True)
        return self.cache_info()

    def devices(self):
        if self._devices is None:
            out = []
            try:
                r = subprocess.run([self.sd, '--list-devices'], capture_output=True, timeout=40, creationflags=self.nw,
                                   stdin=subprocess.DEVNULL)
                for line in (r.stdout or b'').decode('utf-8', 'replace').splitlines():
                    if '\t' in line:
                        n, d = line.split('\t', 1)
                        out.append({'name': n.strip(), 'desc': d.strip(), 'gpu': not n.lower().startswith('cpu')})
            except Exception:  # noqa: BLE001
                pass
            self._devices = out
        return self._devices

    def speeds(self):
        try:
            return json.loads(self.speed_file.read_text('utf-8'))
        except Exception:  # noqa: BLE001
            return {}

    def _store_speed(self, quality, sec):
        sp = self.speeds()
        old = sp.get(quality)
        sp[quality] = round(sec if not old else 0.6 * old + 0.4 * sec, 1)
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            self.speed_file.write_text(json.dumps(sp), 'utf-8')
        except OSError:
            pass

    def estimate(self, quality, length_s):
        frames = QUALITIES[quality][2]
        per = self.speeds().get(quality) or QUALITIES[quality][3]
        n = len(plan(length_s, frames))
        return {'segments': n, 'seconds': int(n * per), 'measured': quality in self.speeds()}

    # ---------- Erzeugen ----------
    @staticmethod
    def key(still_bytes, quality, motion, text, vertical):
        h = hashlib.sha1(still_bytes)
        h.update(('|%s|%s|%s|%s' % (quality, motion, text, vertical)).encode('utf-8'))
        return h.hexdigest()[:16]

    def job_dir(self, key):
        return self.jobs_dir / key

    # ---------- Grafikkarten-Zuordnung ----------
    def backend_args(self, hw=None):
        """--backend aus der Hardware-Analyse: Bewegung+VAE auf einer Karte, Text-Teil (umT5) auf Prozessor/Karte."""
        hw = self.hw if hw is None else hw
        rid = hw.get('recipe') or self.active_rid or 'standard'
        return tunerlib.recipe_args(rid, hw.get('gen') or 'auto', float(hw.get('vram') or 0))

    def pick_recipe(self, quality, hw=None):
        hw = self.hw if hw is None else hw
        return self.tuner.best(hw.get('gen') or 'auto', quality, hw.get('vendor') or 'amd', float(hw.get('vram') or 0))

    def model_args(self):
        f = {k: v.resolve() for k, v in self.files().items()}
        return ['--diffusion-model', str(f['diffusion']), '--vae', str(f['vae']), '--t5xxl', str(f['t5']),
                '--cfg-scale', str(MODEL['cfg']), '--sampling-method', MODEL['sampler'], '--steps', str(MODEL['steps']),
                '--flow-shift', str(MODEL['flow_shift']), '--fps', str(GEN_FPS), '--vae-tiling',
                '--mmap']        # 1.11.0: Modelle einblenden statt kopieren -> Text-Teil belegt ~3 GB weniger festen Arbeitsspeicher

    def _server_for(self, job, hw=None):
        """Geladene KI holen (oder starten). None = Server nicht nutzbar -> sd-cli."""
        hw = self.hw if hw is None else hw
        if not self.server_exe or hw.get('server') is False or os.environ.get('BES_NO_SDSERVER'):
            return None
        sig = json.dumps([self.model_args(), self.backend_args(hw)])
        if self.server and (self.server.sig != sig or not self.server.alive()):
            self.server.stop()
            self.server = None
        if self.server is None:
            sv = SdServer(self.server_exe, self.model_args() + self.backend_args(hw), self.dir / 'server.log', self.nw, sig)
            try:
                job['note'] = (job.get('note') or '') + ' · KI wird geladen …'
                sv.start(job)
            except Exception as ex:  # noqa: BLE001
                sv.stop()
                if job.get('cancel'):
                    raise RuntimeError('abgebrochen')
                if str(ex) == RAM_MSG:
                    raise                                  # Arbeitsspeicher voll: nicht still auf sd-cli ausweichen
                self.server_error = str(ex)
                return None
            finally:
                job['note'] = (job.get('note') or '').replace(' · KI wird geladen …', '')
            self.server = sv
            self.server_error = ''
        self.server.touch()
        return self.server

    def release_server(self, idle=180):
        """Nach einem Auftrag: KI noch kurz geladen lassen (nächster Auftrag startet sofort), dann Grafikspeicher freigeben."""
        sv = self.server
        if sv:
            sv.touch()

            def later():
                time.sleep(idle + 1)
                if self.server is sv and time.time() - sv.last >= idle and not self.lock.locked():
                    sv.stop()
                    self.server = None
            threading.Thread(target=later, daemon=True).start()

    def _run_sd(self, init_png, out_dir, prompt, seed, W, H, frames, job, p0, p1, hw=None):
        """Ein Stück erzeugen -> PNG-Bilder in out_dir. Fortschritt p0…p1 (%)."""
        out_dir = Path(out_dir).resolve()
        init_png = Path(init_png).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        for old in out_dir.glob('f_*.png'):
            old.unlink()
        sv = self._server_for(job, hw)
        if sv is not None:
            return self._run_server(sv, init_png, out_dir, prompt, seed, W, H, frames, job, p0, p1)
        args = [self.sd, '-M', 'vid_gen'] + self.model_args() + self.backend_args(hw) + [
                '-p', prompt, '-i', str(init_png), '-W', str(W), '-H', str(H), '--video-frames', str(frames),
                '-s', str(int(seed)), '-o', str(out_dir / 'f_%04d.png')]
        args += [a for a in os.environ.get('BES_SD_EXTRA', '').split() if a]
        log = out_dir / 'sd.log'
        t0 = time.time()
        with open(log, 'wb') as lf:
            pr = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                  creationflags=self.nw, cwd=str(out_dir))
            job['proc'] = pr
            ram_min = 99.0
            buf, phase = b'', 0
            while True:
                ch = pr.stdout.read(256)
                if not ch:
                    break
                lf.write(ch)
                buf += ch
                parts = re.split(rb'[\r\n]', buf)
                buf = parts.pop()
                for ln in parts:
                    s = ln.decode('utf-8', 'replace')
                    m = re.search(r'\|\s*(\d+)/(\d+)', s)
                    if m:
                        a, b = int(m.group(1)), max(1, int(m.group(2)))
                        if b == MODEL['steps']:
                            phase = 1
                            frac = 0.1 + 0.6 * a / b
                        else:                       # VAE-Kacheln beim Entpacken
                            frac = 0.7 + 0.3 * a / b if phase else 0.05
                        job['percent'] = int(p0 + (p1 - p0) * frac)
                    elif 'sampling' in s.lower() and job.get('percent', 0) < p0 + 2:
                        job['percent'] = p0 + 1
                if job.get('cancel'):
                    pr.kill()
                ram_min = min(ram_min, hwinfo.ram_gb()[1] or 99.0)
            pr.wait()
            job['proc'] = None
        if job.get('cancel'):
            raise RuntimeError('abgebrochen')
        imgs = sorted(out_dir.glob('f_*.png'))
        if pr.returncode or len(imgs) < 2:
            tail = log.read_bytes()[-1500:].decode('utf-8', 'replace')
            if re.search(r'out of memory|ErrorOutOfDeviceMemory|failed to allocate', tail, re.I):
                raise RuntimeError('Der Grafikspeicher reicht nicht – bitte „Schnell“ wählen oder andere Programme schließen.')
            if ram_min < 1.0 or re.search(r'bad_alloc|not enough memory|cannot allocate', tail, re.I):
                raise RuntimeError(RAM_MSG)
            raise RuntimeError('Die KI konnte das Stück nicht berechnen. ' + tail.strip().splitlines()[-1][:200] if tail.strip() else 'Die KI wurde unerwartet beendet.')
        return imgs, time.time() - t0

    def _run_server(self, sv, init_png, out_dir, prompt, seed, W, H, frames, job, p0, p1):
        t0 = time.time()
        body = {'prompt': prompt, 'init_image': base64.b64encode(init_png.read_bytes()).decode('ascii'),
                'width': W, 'height': H, 'video_frames': frames, 'fps': GEN_FPS, 'seed': int(seed),
                'sample_params': {'sample_steps': MODEL['steps'], 'sample_method': MODEL['sampler'], 'flow_shift': MODEL['flow_shift'],
                                  'guidance': {'txt_cfg': MODEL['cfg']}},
                'vae_tiling_params': {'enabled': True}, 'output_format': 'avi', 'output_compression': 100}
        phase = [0]

        def prog(done, total):
            if total == MODEL['steps']:
                phase[0] = 1
                frac = 0.1 + 0.6 * done / total
            else:
                frac = 0.7 + 0.3 * done / max(1, total) if phase[0] else 0.05
            job['percent'] = max(job.get('percent', 0), int(p0 + (p1 - p0) * frac))
        res = sv.generate(body, job, prog)
        avi = out_dir / 'stueck.avi'
        avi.write_bytes(base64.b64decode(res.get('b64_json') or ''))
        (out_dir / 'sd.log').write_text(json.dumps({k: v for k, v in res.items() if k != 'b64_json'}, ensure_ascii=False) +
                                        '\n' + sv.tail(), 'utf-8')
        r = subprocess.run([self.ffmpeg, '-hide_banner', '-v', 'error', '-y', '-i', str(avi), '-start_number', '1',
                            str(out_dir / 'f_%04d.png')], capture_output=True, creationflags=self.nw, stdin=subprocess.DEVNULL, timeout=600)
        avi.unlink()
        imgs = sorted(out_dir.glob('f_*.png'))
        if r.returncode or len(imgs) < 2:
            raise RuntimeError('Die KI-Bilder konnten nicht gelesen werden.')
        return imgs, time.time() - t0

    def _encode_frames(self, imgs, out_mp4, skip_first=False):
        lst = out_mp4.with_suffix('.txt')
        lst.write_text(''.join("file '%s'\n" % p.as_posix() for p in (imgs[1:] if skip_first else imgs)), 'utf-8')
        r = subprocess.run([self.ffmpeg, '-hide_banner', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-r', str(GEN_FPS), '-i', str(lst),
                            '-c:v', 'libx264', '-preset', 'medium', '-crf', '14', '-pix_fmt', 'yuv420p', '-r', str(GEN_FPS), str(out_mp4)],
                           capture_output=True, creationflags=self.nw, stdin=subprocess.DEVNULL, timeout=900)
        lst.unlink()
        if r.returncode:
            raise RuntimeError('Stück konnte nicht gespeichert werden: ' + r.stderr.decode('utf-8', 'replace')[-200:])

    def _segment(self, d, idx, init_png, prompt, seed, W, H, frames, job, p0, p1, quality, ref=None, cmatch=0.9):
        """Stück idx erzeugen (oder vom letzten Mal übernehmen). Rückgabe: Pfad letztes Bild."""
        seg = d / ('segment-%03d.mp4' % idx)
        last = d / ('segment-%03d-last.png' % idx)
        if seg.is_file() and last.is_file():
            return last
        tmp = d / ('tmp-%03d' % idx)
        gen = self.hw.get('gen') or 'auto'
        if not self.active_rid:
            self.active_rid = self.pick_recipe(quality)
        for _try in range(len(tunerlib.SAFE_ORDER)):
            try:
                imgs, sec = self._run_sd(init_png, tmp, prompt, seed, W, H, frames, job, p0, p1)
                break
            except RuntimeError as ex:
                if 'Grafikspeicher' not in str(ex) or job.get('cancel'):
                    if not job.get('cancel'):
                        self.tuner.record(gen, quality, self.active_rid, fail=True)
                    raise
                # 1.10.0: Speicher reicht nicht -> Rezept merken + automatisch mit sichererem Rezept wiederholen
                self.tuner.record(gen, quality, self.active_rid, oom=True)
                nxt = self.tuner.safer(self.active_rid, gen, quality)
                if not nxt:
                    raise
                self.active_rid = nxt
                if self.server:
                    self.server.stop()
                    self.server = None
                job['note'] = (job.get('note') or '') + ' · Speicher knapp – KI weicht aus (%s)' % tunerlib.RECIPES[nxt]['name']
        self._store_speed(quality, sec)
        self.tuner.record(gen, quality, self.active_rid, sec_per_frame=sec / max(1, frames))
        if cv2 is not None:
            refimg = cv2.imdecode(np.fromfile(str(ref or init_png), np.uint8), cv2.IMREAD_COLOR)
            fr = [cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR) for p in imgs]
            if ref is not None and cmatch > 0:
                fr = color_match(fr, refimg, cmatch)
                for p, f in zip(imgs, fr):
                    cv2.imencode('.png', f)[1].tofile(str(p))
            if idx == 0:                                   # Qualitäts-Messwerte fürs Lernen aus deinen Sternen
                f = tunerlib.features(fr, refimg)
                (d / 'quality.json').write_text(json.dumps({'f': f, 'recipe': self.active_rid}), 'utf-8')
        shutil.copyfile(imgs[-1], last)
        if idx == 0:
            shutil.copyfile(imgs[0], d / 'first.png')
        self._encode_frames(imgs, seg)
        try:                                       # 1.11.0: Live-Vorschau – zuletzt fertiges Stück
            job['preview'] = seg.relative_to(self.jobs_dir).as_posix()
            job['preview_n'] = idx + 1
        except ValueError:
            pass
        try:
            shutil.copyfile(tmp / 'sd.log', d / ('segment-%03d.log' % idx))
        except OSError:
            pass
        shutil.rmtree(tmp, ignore_errors=True)
        return last

    def _upscale_segment(self, d, idx, W2, H2, job, cb):
        """Stück idx mit der KI auf Full HD hochrechnen (segment-XXX-hd.mp4, bleibt gespeichert)."""
        src, dst = d / ('segment-%03d.mp4' % idx), d / ('segment-%03d-hd.mp4' % idx)
        if dst.is_file():
            return dst
        meta = json.loads((d.parent / 'meta.json').read_text('utf-8'))
        W, H = meta['W'], meta['H']
        part = dst.with_suffix('.part.mp4')
        enc = subprocess.Popen([self.ffmpeg, '-hide_banner', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (W2, H2),
                                '-r', str(GEN_FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', '15', '-pix_fmt', 'yuv420p',
                                str(part)], stdin=subprocess.PIPE, creationflags=self.nw)
        frames = list(self._frames(src, W, H))
        for k, fr in enumerate(frames):
            if job.get('cancel'):
                enc.kill()
                raise RuntimeError('abgebrochen')
            enc.stdin.write(self.upscaler.to_size(fr, W2, H2).tobytes())
            cb((k + 1) / max(1, len(frames)))
        enc.stdin.close()
        enc.wait()
        if enc.returncode:
            raise RuntimeError('Hochrechnen fehlgeschlagen')
        os.replace(part, dst)
        return dst

    def start(self, kind, still_png, opts):
        """kind 'variants' (3 Vorschläge) oder 'full' (volle Länge mit gewählter Variante)."""
        if not self.ready():
            raise RuntimeError('Das KI-Video-Paket ist noch nicht installiert.')
        jid = hashlib.sha1(('%s%s' % (time.time(), kind)).encode()).hexdigest()[:10]
        job = {'id': jid, 'kind': kind, 'state': 'wartet', 'percent': 0, 'error': '', 'note': '', 'result': None,
               'cancel': False, 'proc': None, 'started': time.time()}
        self.jobs[jid] = job
        threading.Thread(target=self._job, args=(job, Path(still_png), opts), daemon=True).start()
        return jid

    def cancel(self, jid):
        j = self.jobs.get(jid)
        if j:
            j['cancel'] = True
            p = j.get('proc')
            if p:
                try:
                    p.kill()
                except OSError:
                    pass

    def shutdown(self):
        """Beim Beenden des Programms laufende KI-Rechnungen stoppen (fertige Stücke bleiben gespeichert)."""
        if self.server:
            self.server.stop()
            self.server = None
        for j in self.jobs.values():
            j['cancel'] = True
            p = j.get('proc')
            if p:
                try:
                    p.kill()
                except OSError:
                    pass

    def view(self, jid):
        j = self.jobs.get(jid)
        if not j:
            return None
        return {k: v for k, v in j.items() if k not in ('proc', 'cancel')}

    def _prepare_init(self, still_png, d, W, H):
        init = d / 'original.png'
        if not init.is_file():
            img = cv2.imdecode(np.fromfile(str(still_png), np.uint8), cv2.IMREAD_COLOR)
            img = cv2.resize(img, (W, H), interpolation=cv2.INTER_AREA)
            cv2.imencode('.png', img)[1].tofile(str(init))
        return init

    def _job(self, job, still_png, o):
        # 1.11.0: läuft gerade eine normale Video-Umwandlung, wartet die KI (nicht beides gleichzeitig rechnen)
        while self.blocker() and not job['cancel']:
            job['note'] = 'Wartet, bis die Video-Umwandlung fertig ist …'
            time.sleep(1)
        job['note'] = ''
        with self.lock:
            self.active_rid = None                    # pro Auftrag neu das beste Rezept wählen
            if job['cancel']:
                job.update(state='abgebrochen')
                return
            job['state'] = 'läuft'
            try:
                W, H, frames = gen_size(o['quality'], o['vertical'])
                prompt = prompt_for(o['motion'], o.get('text'), o.get('extra') or ())
                cm = float(o.get('cmatch', 0.9))
                d = self.job_dir(o['key'])
                d.mkdir(parents=True, exist_ok=True)
                mf = d / 'meta.json'
                old = {}
                try:
                    old = json.loads(mf.read_text('utf-8'))
                except Exception:  # noqa: BLE001
                    pass
                if job['kind'] == 'full' and old.get('extra') is not None:
                    o['extra'] = old['extra']            # gleiche Beschreibung wie bei den Varianten (Gelerntes kann sich inzwischen geändert haben)
                    prompt = prompt_for(o['motion'], o.get('text'), o['extra'])
                mf.write_text(json.dumps({'motion': o['motion'], 'text': o.get('text', ''), 'quality': o['quality'], 'extra': o.get('extra') or [],
                                          'vertical': o['vertical'], 'W': W, 'H': H, 'fmt': o.get('fmt'), 'prompt': prompt,
                                          'imgkey': o.get('imgkey')}), 'utf-8')
                init = self._prepare_init(still_png, d, W, H)
                if job['kind'] == 'variants':
                    seeds = o.get('seeds') or [11, 222, 3333]
                    out = []
                    for n, sd in enumerate(seeds):
                        vd = d / ('seed-%d' % sd)
                        vd.mkdir(exist_ok=True)
                        job['note'] = 'Variante %d von %d wird berechnet …' % (n + 1, len(seeds))
                        self._segment(vd, 0, init, prompt, sd, W, H, frames, job, n * 100 // len(seeds), (n + 1) * 100 // len(seeds), o['quality'],
                                      ref=init, cmatch=cm)
                        q = self.quality_of(vd)
                        out.append({'seed': sd, 'video': str(vd / 'segment-000.mp4'), 'score': self.tuner.score(q)})
                    sc = [v['score'] or 0 for v in out]
                    tip = sc.index(max(sc)) if any(sc) else -1
                    job.update(state='fertig', percent=100, note='', result={'variants': out, 'key': o['key'], 'tip': tip})
                    return
                # volle Länge
                sd = int(o['seed'])
                vd = d / ('seed-%d' % sd)
                vd.mkdir(exist_ok=True)
                segs = plan(float(o['length']), frames)
                up = bool(o.get('up')) and self.upscaler is not None and self.upscaler.available()
                share = 0.8 if up else 0.95                  # Anteil der Fortschrittsanzeige für die KI-Bewegung
                prev = None
                t_seg = []
                W2, H2 = HD[bool(o['vertical'])]
                # 1.9.0: Upscaler in eigenem Arbeitsfaden – auf der zweiten Grafikkarte gleichzeitig mit der KI-Bewegung
                par = up and bool(self.hw.get('parallel'))
                us = {'done': 0, 'cur': 0.0, 'err': None}
                uq = queue.Queue()

                def upworker():
                    while True:
                        i = uq.get()
                        if i is None:
                            return
                        if us['err'] is None and not job['cancel']:
                            try:
                                self._upscale_segment(vd, i, W2, H2, job, lambda f: us.__setitem__('cur', f))
                            except Exception as ex:  # noqa: BLE001
                                us['err'] = ex
                        us['done'] += 1
                        us['cur'] = 0.0
                uth = threading.Thread(target=upworker, daemon=True)
                if up:
                    uth.start()
                for n, (idx, anchor) in enumerate(segs):
                    if us['err']:
                        raise us['err']
                    src = init if anchor else prev
                    job['note'] = 'Stück %d von %d%s' % (n + 1, len(segs), ' · Full HD: %d fertig' % us['done'] if par else '')
                    t0 = time.time()
                    already = (vd / ('segment-%03d.mp4' % idx)).is_file()
                    a, b = n / len(segs) * 100, (n + 1) / len(segs) * 100
                    prev = self._segment(vd, idx, src, prompt, sd + idx * 7919, W, H, frames, job,
                                         int(a * share), int(b * share), o['quality'], ref=init, cmatch=cm)
                    if up:
                        uq.put(idx)
                        while not par and us['done'] <= n and uth.is_alive():      # eine Karte: nacheinander
                            job['note'] = 'Stück %d von %d · KI-Upscaler (Full HD)' % (n + 1, len(segs))
                            time.sleep(0.3)
                    if not already:
                        t_seg.append(time.time() - t0)
                    if t_seg:
                        left = (len(segs) - n - 1) * (sum(t_seg) / len(t_seg))
                        job['eta'] = int(left)
                if up:
                    uq.put(None)
                    while uth.is_alive():
                        if job['cancel']:
                            raise RuntimeError('abgebrochen')
                        f = (us['done'] + us['cur']) / len(segs)
                        job['percent'] = max(job.get('percent', 0), int(share * 100 + (95 - share * 100) * f))
                        job['note'] = 'KI-Upscaler (Full HD): Stück %d von %d' % (min(len(segs), us['done'] + 1), len(segs))
                        time.sleep(0.4)
                    if us['err']:
                        raise us['err']
                job['note'] = 'Stücke werden zusammengesetzt …'
                clip = vd / ('ki-video-%ds%s.mp4' % (int(round(float(o['length']))), '-hd' if up else ''))
                if up:
                    ohd = vd / 'original-hd.png'
                    if not ohd.is_file():
                        org = cv2.cvtColor(cv2.imdecode(np.fromfile(str(init), np.uint8), cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
                        cv2.imencode('.png', cv2.cvtColor(self.upscaler.to_size(org, W2, H2), cv2.COLOR_RGB2BGR))[1].tofile(str(ohd))
                    self.assemble(vd, segs, ohd, clip, W2, H2, suffix='-hd')
                else:
                    self.assemble(vd, segs, init, clip, W, H)
                job.update(state='fertig', percent=100, note='', eta=0,
                           result={'clip': clip.relative_to(self.jobs_dir).as_posix(), 'seconds': self.duration(clip), 'key': o['key'], 'seed': sd})
            except Exception as ex:  # noqa: BLE001
                job.update(state='abgebrochen' if job['cancel'] else 'fehler', error=str(ex))
            finally:
                self.release_server()

    # ---------- Zusammensetzen ----------
    def _frames(self, mp4, W, H):
        p = subprocess.Popen([self.ffmpeg, '-hide_banner', '-v', 'error', '-i', str(mp4), '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                              '-s', '%dx%d' % (W, H), '-'], stdout=subprocess.PIPE, stdin=subprocess.DEVNULL, creationflags=self.nw)
        n = W * H * 3
        while True:
            b = p.stdout.read(n)
            if len(b) < n:
                break
            yield np.frombuffer(b, np.uint8).reshape(H, W, 3)
        p.wait()

    def assemble(self, vd, segs, init_png, out_mp4, W, H, suffix=''):
        enc = subprocess.Popen([self.ffmpeg, '-hide_banner', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (W, H),
                                '-r', str(GEN_FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', '15', '-pix_fmt', 'yuv420p',
                                '-movflags', '+faststart', str(out_mp4)], stdin=subprocess.PIPE, creationflags=self.nw)
        orig = cv2.cvtColor(cv2.imdecode(np.fromfile(str(init_png), np.uint8), cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
        tail = []                                   # die letzten XFADE Bilder werden zurückgehalten (für Überblendung)

        def emit(fr):
            tail.append(fr)
            if len(tail) > XFADE:
                enc.stdin.write(tail.pop(0).tobytes())

        for n, (idx, anchor) in enumerate(segs):
            frames = self._frames(vd / ('segment-%03d%s.mp4' % (idx, suffix)), W, H)
            if n and anchor:                        # weich vom bisherigen Verlauf zurück zum Original-Start überblenden
                head = [next(frames) for _ in range(XFADE)]
                for k, (a, b) in enumerate(zip(tail, head)):
                    t = (k + 1) / (XFADE + 1)
                    tail[k] = (a.astype(np.float32) * (1 - t) + b.astype(np.float32) * t).astype(np.uint8)
            elif n:
                next(frames, None)                  # erstes Bild = letztes Bild des vorigen Stücks
            for fr in frames:
                emit(fr)
        for k in range(len(tail)):                  # Ende: zurück zum Original -> nahtlose Wiederholung
            t = (k + 1) / (len(tail) + 1)
            tail[k] = (tail[k].astype(np.float32) * (1 - t) + orig.astype(np.float32) * t).astype(np.uint8)
        for fr in tail:
            enc.stdin.write(fr.tobytes())
        enc.stdin.close()
        enc.wait()
        if enc.returncode:
            raise RuntimeError('Das KI-Video konnte nicht zusammengesetzt werden.')

    def duration(self, mp4):
        try:
            r = subprocess.run([self.ffmpeg, '-hide_banner', '-i', str(mp4)], capture_output=True, creationflags=self.nw,
                               stdin=subprocess.DEVNULL, timeout=30)
            m = re.search(rb'Duration: (\d+):(\d+):(\d+\.\d+)', r.stderr)
            return round(int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)), 2) if m else 0
        except Exception:  # noqa: BLE001
            return 0

    def clip_path(self, rel):
        """Sicherer Pfad zu einem fertigen KI-Video (nur innerhalb des jobs-Ordners)."""
        if not rel or not re.fullmatch(r'[0-9a-f]{16}/seed-\d+/(ki-video-\d+s(-hd)?|segment-000)\.mp4', str(rel)):
            return None
        p = self.jobs_dir / rel
        return p if p.is_file() else None

    def clips(self, key):
        """Was es für dieses Bild/diese Einstellung schon gibt (Varianten, fertige Längen, angefangene Arbeit)."""
        d = self.job_dir(key)
        out = {'variants': [], 'clips': [], 'partial': []}
        if not d.is_dir():
            return out
        for vd in sorted(d.glob('seed-*')):
            sd = int(vd.name[5:])
            if (vd / 'segment-000.mp4').is_file():
                out['variants'].append({'seed': sd, 'video': (vd / 'segment-000.mp4').relative_to(self.jobs_dir).as_posix(),
                                        'score': self.tuner.score(self.quality_of(vd))})
            for c in vd.glob('ki-video-*.mp4'):
                m = re.fullmatch(r'ki-video-(\d+)s(-hd)?', c.stem)
                if m:
                    out['clips'].append({'seed': sd, 'clip': c.relative_to(self.jobs_dir).as_posix(), 'seconds': int(m.group(1)), 'hd': bool(m.group(2))})
            n = len([p for p in vd.glob('segment-*.mp4') if re.fullmatch(r'segment-\d+', p.stem)])
            if n > 1:
                out['partial'].append({'seed': sd, 'segments': n})
        sc = [v['score'] or 0 for v in out['variants']]
        out['tip'] = out['variants'][sc.index(max(sc))]['seed'] if len(sc) > 1 and max(sc) > 0 else 0
        return out

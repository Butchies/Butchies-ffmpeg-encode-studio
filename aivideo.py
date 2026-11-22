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
"""
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
    'fast': (832, 480, 97, 240),
    'good': (1280, 704, 121, 900),
}
QUALITY_NAMES = {'fast': 'Schnell (832 × 480)', 'good': 'Beste Qualität (1280 × 704)'}
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


class AIVideo:
    def __init__(self, home, app_dir, base_dir, ffmpeg, no_window=0):
        self.dir = Path(home).resolve() / 'aivideo'
        self.models = Path(os.environ.get('BES_AIMODELS') or (self.dir / 'models')).resolve()
        self.jobs_dir = self.dir / 'jobs'
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
        self._devices = None
        self.speed_file = self.dir / 'speed.json'
        self.upscaler = None                 # wird vom Programm gesetzt (upscale.Upscaler)

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
        running = [self.view(j['id']) for j in self.jobs.values() if j['state'] in ('läuft', 'wartet')]
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

    def _run_sd(self, init_png, out_dir, prompt, seed, W, H, frames, job, p0, p1):
        """Ein Stück erzeugen -> PNG-Bilder in out_dir. Fortschritt p0…p1 (%)."""
        f = {k: v.resolve() for k, v in self.files().items()}
        out_dir = Path(out_dir).resolve()
        init_png = Path(init_png).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        for old in out_dir.glob('f_*.png'):
            old.unlink()
        args = [self.sd, '-M', 'vid_gen', '--diffusion-model', str(f['diffusion']), '--vae', str(f['vae']),
                '--t5xxl', str(f['t5']), '-p', prompt, '-i', str(init_png), '--cfg-scale', str(MODEL['cfg']),
                '--sampling-method', MODEL['sampler'], '--steps', str(MODEL['steps']), '--flow-shift', str(MODEL['flow_shift']),
                '-W', str(W), '-H', str(H), '--video-frames', str(frames), '--fps', str(GEN_FPS), '-s', str(int(seed)),
                '--vae-tiling', '-o', str(out_dir / 'f_%04d.png')]
        args += [a for a in os.environ.get('BES_SD_EXTRA', '').split() if a]
        log = out_dir / 'sd.log'
        t0 = time.time()
        with open(log, 'wb') as lf:
            pr = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                  creationflags=self.nw, cwd=str(out_dir))
            job['proc'] = pr
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
            pr.wait()
            job['proc'] = None
        if job.get('cancel'):
            raise RuntimeError('abgebrochen')
        imgs = sorted(out_dir.glob('f_*.png'))
        if pr.returncode or len(imgs) < 2:
            tail = log.read_bytes()[-1500:].decode('utf-8', 'replace')
            if re.search(r'out of memory|ErrorOutOfDeviceMemory|failed to allocate', tail, re.I):
                raise RuntimeError('Der Grafikspeicher reicht nicht – bitte „Schnell“ wählen oder andere Programme schließen.')
            raise RuntimeError('Die KI konnte das Stück nicht berechnen. ' + tail.strip().splitlines()[-1][:200] if tail.strip() else 'Die KI wurde unerwartet beendet.')
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
        imgs, sec = self._run_sd(init_png, tmp, prompt, seed, W, H, frames, job, p0, p1)
        self._store_speed(quality, sec)
        if ref is not None and cv2 is not None and cmatch > 0:
            refimg = cv2.imdecode(np.fromfile(str(ref), np.uint8), cv2.IMREAD_COLOR)
            fr = [cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR) for p in imgs]
            for p, f in zip(imgs, color_match(fr, refimg, cmatch)):
                cv2.imencode('.png', f)[1].tofile(str(p))
        shutil.copyfile(imgs[-1], last)
        if idx == 0:
            shutil.copyfile(imgs[0], d / 'first.png')
        self._encode_frames(imgs, seg)
        try:
            shutil.copyfile(tmp / 'sd.log', d / ('segment-%03d.log' % idx))
        except OSError:
            pass
        shutil.rmtree(tmp, ignore_errors=True)
        return last

    def _upscale_segment(self, d, idx, W2, H2, job, p0, p1):
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
            job['percent'] = int(p0 + (p1 - p0) * (k + 1) / max(1, len(frames)))
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
        with self.lock:
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
                        out.append({'seed': sd, 'video': str(vd / 'segment-000.mp4')})
                    job.update(state='fertig', percent=100, note='', result={'variants': out, 'key': o['key']})
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
                for n, (idx, anchor) in enumerate(segs):
                    src = init if anchor else prev
                    job['note'] = 'Stück %d von %d' % (n + 1, len(segs))
                    t0 = time.time()
                    already = (vd / ('segment-%03d.mp4' % idx)).is_file()
                    a, b = n / len(segs) * 100, (n + 1) / len(segs) * 100
                    prev = self._segment(vd, idx, src, prompt, sd + idx * 7919, W, H, frames, job,
                                         int(a * share), int(a * share + (b - a) * share * (0.75 if up else 1)), o['quality'], ref=init, cmatch=cm)
                    if up:
                        job['note'] = 'Stück %d von %d · KI-Upscaler (Full HD)' % (n + 1, len(segs))
                        self._upscale_segment(vd, idx, *HD[bool(o['vertical'])], job,
                                              int(a * share + (b - a) * share * 0.75), int(b * share))
                    if not already:
                        t_seg.append(time.time() - t0)
                    if t_seg:
                        left = (len(segs) - n - 1) * (sum(t_seg) / len(t_seg))
                        job['eta'] = int(left)
                job['note'] = 'Stücke werden zusammengesetzt …'
                clip = vd / ('ki-video-%ds%s.mp4' % (int(round(float(o['length']))), '-hd' if up else ''))
                if up:
                    W2, H2 = HD[bool(o['vertical'])]
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
                out['variants'].append({'seed': sd, 'video': (vd / 'segment-000.mp4').relative_to(self.jobs_dir).as_posix()})
            for c in vd.glob('ki-video-*.mp4'):
                m = re.fullmatch(r'ki-video-(\d+)s(-hd)?', c.stem)
                if m:
                    out['clips'].append({'seed': sd, 'clip': c.relative_to(self.jobs_dir).as_posix(), 'seconds': int(m.group(1)), 'hd': bool(m.group(2))})
            n = len([p for p in vd.glob('segment-*.mp4') if re.fullmatch(r'segment-\d+', p.stem)])
            if n > 1:
                out['partial'].append({'seed': sd, 'segments': n})
        return out

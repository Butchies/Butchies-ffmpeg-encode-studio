"""„Mit Songtext“ (ab 1.6.0): Whisper light – nur gesungene Zeilen + Zeitstempel erkennen.

faster-whisper (CTranslate2, MIT) mit dem kleinen mehrsprachigen Modell „base“ (int8 auf dem Prozessor).
Das Modell (~145 MB) wird beim ersten Benutzen einmal heruntergeladen (Hugging Face: Systran/faster-whisper-base, MIT)
und liegt danach offline im Einstellungsordner. Keine Übersetzung, keine Sprachaktivitäts-KI, kein PyAV.
"""
import os
import sys
import threading
import types
import urllib.request
from pathlib import Path

MODEL_NAME = 'base'
REPO = 'https://huggingface.co/Systran/faster-whisper-base/resolve/main/'
FILES = [('config.json', 0), ('tokenizer.json', 0), ('vocabulary.txt', 0), ('model.bin', 145_000_000)]
APPROX_MB = 145


class Lyrics:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.dl = {'state': 'idle', 'percent': 0, 'error': ''}
        self.model = None
        self.lock = threading.Lock()
        self.error = ''

    # ---------- verfügbar? ----------
    def lib_ok(self):
        try:
            self._import()
            return True
        except Exception as ex:  # noqa: BLE001
            self.error = str(ex)
            return False

    def model_ok(self):
        return all((self.folder / f).is_file() and (self.folder / f).stat().st_size > 0 for f, _ in FILES)

    def status(self):
        return {'lib': self.lib_ok(), 'model': self.model_ok(), 'download': dict(self.dl), 'mb': APPROX_MB,
                'error': self.error if not self.lib_ok() else ''}

    @staticmethod
    def _import():
        if 'av' not in sys.modules:                       # PyAV wird nicht gebraucht (Audio liefert FFmpeg)
            try:
                import av  # noqa: F401
            except Exception:  # noqa: BLE001
                stub = types.ModuleType('av')
                stub.__dict__.update({'open': None, 'AudioResampler': None, 'AudioFifo': None, 'error': types.SimpleNamespace(InvalidDataError=Exception)})
                sys.modules['av'] = stub
        from faster_whisper import WhisperModel  # noqa: F401
        return WhisperModel

    # ---------- Modell herunterladen ----------
    def download(self):
        if self.dl['state'] == 'running':
            return
        self.dl = {'state': 'running', 'percent': 0, 'error': ''}
        threading.Thread(target=self._download, daemon=True).start()

    def _download(self):
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            total = sum(max(s, 1) for _, s in FILES)
            done = 0
            for name, size in FILES:
                dest = self.folder / name
                part = dest.with_suffix(dest.suffix + '.part')
                req = urllib.request.Request(REPO + name, headers={'User-Agent': 'ffmpeg_encode-Studio'})
                with urllib.request.urlopen(req, timeout=60) as r, open(part, 'wb') as f:
                    real = int(r.headers.get('Content-Length') or 0) or max(size, 1)
                    got = 0
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        f.write(chunk)
                        got += len(chunk)
                        self.dl['percent'] = int((done + min(got, real) * max(size, 1) / real) / total * 100)
                os.replace(part, dest)
                done += max(size, 1)
            self.dl = {'state': 'done', 'percent': 100, 'error': ''}
        except Exception as ex:  # noqa: BLE001
            self.dl = {'state': 'error', 'percent': 0, 'error': 'Download fehlgeschlagen – bitte Internetverbindung prüfen (%s)' % ex}

    # ---------- Text erkennen ----------
    def load(self):
        if self.model is None:
            WhisperModel = self._import()
            threads = max(1, min(8, (os.cpu_count() or 2)))
            self.model = WhisperModel(str(self.folder), device='cpu', compute_type='int8', cpu_threads=threads)
        return self.model

    def transcribe(self, samples_16k, progress=None):
        """samples_16k: float32-numpy (mono, 16 kHz). Rückgabe: [{start, end, text}], Sprache."""
        with self.lock:
            m = self.load()
            total = max(1.0, len(samples_16k) / 16000)
            segs, info = m.transcribe(samples_16k, beam_size=1, best_of=1, vad_filter=False, word_timestamps=False,
                                      condition_on_previous_text=False, temperature=0.0, no_speech_threshold=0.5)
            out = []
            for s in segs:
                t = (s.text or '').strip()
                if t and s.no_speech_prob < 0.8:
                    out.append({'start': round(float(s.start), 2), 'end': round(float(s.end), 2), 'text': t})
                if progress:
                    progress(min(99, int(s.end / total * 100)))
            return out, getattr(info, 'language', '')

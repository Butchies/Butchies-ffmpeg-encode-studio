"""KI-Upscaler (1.8.0): Real-ESRGAN „general x4v3“ (BSD-3, xinntao) als ONNX – offline über onnxruntime
(DirectML = Grafikkarte, sonst Prozessor). Rechnet die KI-Video-Bilder 4× hoch, danach exakt auf Full HD.
Das ONNX-Modell wird im Build-Workflow aus den offiziellen Gewichten erzeugt (tools/make_upscaler.py)."""
import threading
from pathlib import Path

import numpy as np

try:
    import cv2
except Exception:  # noqa: BLE001
    cv2 = None

MODEL_FILE = 'realesr-general-x4v3.onnx'
SCALE = 4
TILE = 320           # Kachelgröße (Eingabe) – hält den Grafikspeicher klein
PAD = 12             # Überlappung gegen Kanten zwischen den Kacheln


class Upscaler:
    def __init__(self, folder):
        self.folder = Path(folder) if folder else None
        self.sess = None
        self.error = ''
        self.device = ''
        self.lock = threading.Lock()

    def file(self):
        f = self.folder / MODEL_FILE if self.folder else None
        return f if f and f.is_file() else None

    def available(self):
        return self.file() is not None and cv2 is not None

    def load(self):
        if self.sess is not None:
            return True
        f = self.file()
        if not f:
            return False
        try:
            import onnxruntime as ort
            so = ort.SessionOptions()
            so.log_severity_level = 3
            avail = ort.get_available_providers()
            tries = []
            if 'DmlExecutionProvider' in avail:   # die stärkste Grafikkarte nehmen (nicht die Prozessor-Grafik)
                tries.append([('DmlExecutionProvider', {'performance_preference': 'high_performance', 'device_filter': 'gpu'}), 'CPUExecutionProvider'])
                tries.append(['DmlExecutionProvider', 'CPUExecutionProvider'])
            if 'CUDAExecutionProvider' in avail:
                tries.append(['CUDAExecutionProvider', 'CPUExecutionProvider'])
            tries.append(['CPUExecutionProvider'])
            for prov in tries:
                try:
                    self.sess = ort.InferenceSession(str(f), so, providers=prov)
                    break
                except Exception as ex:  # noqa: BLE001
                    self.error = str(ex)
            if self.sess is None:
                return False
            p = self.sess.get_providers()[0]
            self.device = 'Grafikkarte' if p != 'CPUExecutionProvider' else 'Prozessor'
            return True
        except Exception as ex:  # noqa: BLE001
            self.error = str(ex)
            return False

    def _run(self, x):
        name = self.sess.get_inputs()[0].name
        return self.sess.run(None, {name: x})[0]

    def up(self, rgb):
        """rgb: uint8 H×W×3 -> uint8 (4H)×(4W)×3 (in Kacheln gerechnet)."""
        h, w = rgb.shape[:2]
        x = rgb.astype(np.float32).transpose(2, 0, 1)[None] / 255.0
        out = np.zeros((1, 3, h * SCALE, w * SCALE), np.float32)
        for ty in range(0, h, TILE):
            for tx in range(0, w, TILE):
                y0, x0 = max(ty - PAD, 0), max(tx - PAD, 0)
                y1, x1 = min(ty + TILE + PAD, h), min(tx + TILE + PAD, w)
                o = self._run(np.ascontiguousarray(x[:, :, y0:y1, x0:x1]))
                cy0, cx0 = (ty - y0) * SCALE, (tx - x0) * SCALE
                th, tw = (min(ty + TILE, h) - ty) * SCALE, (min(tx + TILE, w) - tx) * SCALE
                out[:, :, ty * SCALE:ty * SCALE + th, tx * SCALE:tx * SCALE + tw] = o[:, :, cy0:cy0 + th, cx0:cx0 + tw]
        return (np.clip(out[0].transpose(1, 2, 0), 0, 1) * 255.0 + 0.5).astype(np.uint8)

    def to_size(self, rgb, W, H):
        """KI-Hochrechnung und danach exakt auf W×H (z. B. 1920×1080)."""
        with self.lock:
            if not self.load():
                raise RuntimeError('KI-Upscaler nicht verfügbar')
            big = self.up(rgb)
        return cv2.resize(big, (W, H), interpolation=cv2.INTER_AREA)

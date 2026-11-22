"""ffmpeg_encode Studio – macht aus einer MP3 und einem Bild ein fertiges YouTube-Video (16:9 bis 4K oder Shorts 9:16).

Alles per Drag & Drop: Song und Bild hineinziehen, Format, FPS, Fades und Länge wählen, konvertieren.
Technik: Python-Standardbibliothek + FFmpeg (wird vom Installer mitgeliefert). Die Oberfläche läuft in einem
rahmenlosen Programmfenster (WebView2 über pywebview); ohne WebView2 öffnet sich ein Edge/Chrome-App-Fenster.
"""
import json, mimetypes, os, re, secrets, shutil, subprocess, sys, tempfile, threading, time, urllib.parse, webbrowser, zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import viz
import fx
import highlight
import lyrics
import learn
import aivideo
try:
    import mark          # braucht numpy + OpenCV (+ onnxruntime für die KI)
except Exception:  # noqa: BLE001
    mark = None

APP_NAME = 'ffmpeg_encode Studio'
APP_DIRNAME = 'ffmpeg_encode Studio'      # Ordnername für Einstellungen/Videos bleibt (deine Daten bleiben erhalten)
VERSION = '1.7.0'
WEBSITE = 'https://butchies-groove.duckdns.org'
FROZEN = getattr(sys, 'frozen', False)
BASE = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
UI = BASE / 'ui'
APP_DIR = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent
HOME = Path(os.environ.get('APPDATA') or Path.home() / '.config') / APP_DIRNAME
STAGE = Path(tempfile.mkdtemp(prefix='ffmpeg-encode-studio-'))
CONFIG_FILE = HOME / 'config.json'
NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
TOKEN = secrets.token_urlsafe(16)
LAST_PING = [time.time()]
NATIVE = [False]
MASKS = {}         # token -> Pfad der Maske (Graustufen-PNG, ganzes Bild)
SEGS = {}          # id -> KI-Ergebnis (PNG)
ANALYSIS = {}      # (bild, format, fit) -> Analysebild (max. 1024 px)
MODEL_DIR = next((d for d in (APP_DIR / 'models', BASE / 'models', Path(__file__).resolve().parent / 'models') if d.is_dir()), APP_DIR / 'models')
SAM = mark.Sam(MODEL_DIR) if mark and mark.cv2 is not None else None
DEPTH = fx.Depth(MODEL_DIR) if fx.cv2 is not None else None
GPU = []           # erkannte Grafikkarten [{name, vram, vendor}]
# Songtext-Modell: liegt seit 1.6.1 direkt im Programm (Installer); sonst Ersatz-Ort im Einstellungsordner
_WHISPER = 'whisper-' + lyrics.MODEL_NAME
LEARN = learn.Learner(HOME / 'learn.json')     # Selbst-Lernen (offline)
LYRICS = lyrics.Lyrics(MODEL_DIR / _WHISPER if (MODEL_DIR / _WHISPER / 'model.bin').is_file() else HOME / 'models' / _WHISPER)
HL_JOBS = {}       # Stellensuche: id -> {state, percent, phase, result, error}
HL_CACHE = {}      # (Song-Pfad, mtime) -> Analyse bzw. Songtext

# Zielformate (Breite, Höhe, Hochformat?)
FORMATS = {
    'yt4k':   ('YouTube 4K', 3840, 2160, False),
    'yt1440': ('YouTube 1440p', 2560, 1440, False),
    'yt1080': ('YouTube 1080p', 1920, 1080, False),
    'sh1080': ('YouTube Shorts', 1080, 1920, True),
    'sh4k':   ('YouTube Shorts 4K', 2160, 3840, True),
}
SHORTS_MAX = 180          # YouTube Shorts: höchstens 3 Minuten
FPS_LIST = (24, 25, 30, 50, 60)
QUALITY = {'16': ('slow', 0), '18': ('medium', 0), '22': ('fast', 0)}     # CRF-Stufe -> x264-Preset
ENCODERS = {               # id -> (ffmpeg-Encoder, Anzeigename)
    'x264': ('libx264', 'H.264 (CPU)'),
    'x265': ('libx265', 'H.265 (CPU)'),
    'nvenc': ('h264_nvenc', 'NVIDIA NVENC'),
    'qsv': ('h264_qsv', 'Intel Quick Sync'),
    'amf': ('h264_amf', 'AMD AMF'),
}
# Übergänge für "Bild kommt" / "Bild geht" (FFmpeg xfade) – Gruppe, id, deutscher Name
TRANSITIONS = [
    ('Blenden', 'fade', 'Weich blenden (klassisch)'), ('Blenden', 'fadeslow', 'Langsam blenden'),
    ('Blenden', 'fadefast', 'Schnell blenden'), ('Blenden', 'fadegrays', 'Über Schwarz-Weiß blenden'),
    ('Blenden', 'dissolve', 'Auflösen (Pixelstaub)'), ('Blenden', 'hblur', 'Bewegungsunschärfe'),
    ('Wischen', 'wipeleft', 'Wischen nach links'), ('Wischen', 'wiperight', 'Wischen nach rechts'),
    ('Wischen', 'wipeup', 'Wischen nach oben'), ('Wischen', 'wipedown', 'Wischen nach unten'),
    ('Wischen', 'wipetl', 'Wischen zur Ecke oben links'), ('Wischen', 'wipebr', 'Wischen zur Ecke unten rechts'),
    ('Weich wischen', 'smoothleft', 'Weich nach links'), ('Weich wischen', 'smoothright', 'Weich nach rechts'),
    ('Weich wischen', 'smoothup', 'Weich nach oben'), ('Weich wischen', 'smoothdown', 'Weich nach unten'),
    ('Schieben', 'slideleft', 'Schieben nach links'), ('Schieben', 'slideright', 'Schieben nach rechts'),
    ('Schieben', 'slideup', 'Schieben nach oben'), ('Schieben', 'slidedown', 'Schieben nach unten'),
    ('Schieben', 'coverleft', 'Überdecken von rechts'), ('Schieben', 'revealright', 'Aufdecken nach rechts'),
    ('Formen', 'circleopen', 'Kreis öffnet sich'), ('Formen', 'circleclose', 'Kreis schließt sich'),
    ('Formen', 'circlecrop', 'Kreis-Blende'), ('Formen', 'rectcrop', 'Rechteck-Blende'),
    ('Formen', 'radial', 'Uhrzeiger (radial)'), ('Formen', 'vertopen', 'Vorhang auf (senkrecht)'),
    ('Formen', 'horzopen', 'Vorhang auf (waagerecht)'), ('Formen', 'diagtl', 'Diagonal von oben links'),
    ('Formen', 'diagbr', 'Diagonal von unten rechts'),
    ('Effekte', 'pixelize', 'Verpixeln'), ('Effekte', 'zoomin', 'Zoom (am schönsten beim Ausblenden)'),
    ('Effekte', 'squeezeh', 'Zusammendrücken'), ('Effekte', 'hlslice', 'Streifen nach links'),
    ('Effekte', 'hrwind', 'Wind nach rechts'),
]
TRANS_IDS = {t[1] for t in TRANSITIONS} | {'none'}

DEFAULTS = {'fmt': 'yt4k', 'fps': 30, 'fadeIn': 2.0, 'fadeOut': 3.0, 'color': 'black', 'target': 'av', 'fit': 'blur',
            'enc': 'auto', 'quality': '18', 'start': '0:00', 'end': '',
            'transIn': 'fade', 'transOut': 'fade', 'shortLen': 60, 'shortLyrics': False,
            # KI-Video (1.8.0)
            'ai': False, 'aiClip': '', 'aiArea': 'full', 'aiMask': '', 'aiFeather': 1.5, 'aiMotion': 'hair', 'aiText': '',
            'aiLen': 30, 'aiQual': 'fast'}
AI_LENS = (10, 30, 60, 120, 0)      # Sekunden; 0 = ganzer Song
DEFAULTS.update(viz.DEFAULTS)
DEFAULTS.update(fx.DEFAULTS)

STAGED = {}        # token -> {'path', 'name', 'kind', 'info'}
JOBS = {}          # id -> job dict
QUEUE = []         # job ids in order
QLOCK = threading.Lock()
QEVENT = threading.Event()
HW = {'x264': None, 'x265': None, 'nvenc': None, 'qsv': None, 'amf': None}
HW_DONE = threading.Event()
GPU_ORDER = ('nvenc', 'qsv', 'amf')     # bevorzugte Reihenfolge bei "Automatisch"


def resolve_enc(enc, wait=0):
    """'auto' -> beste funktionierende Grafikkarte, sonst CPU (x264)."""
    if enc != 'auto':
        return enc
    if wait:
        HW_DONE.wait(wait)
    return next((k for k in GPU_ORDER if HW.get(k)), 'x264')


# ---------- Hilfsfunktionen ----------
def find_tool(name):
    exe = name + ('.exe' if os.name == 'nt' else '')
    for d in (APP_DIR / 'ffmpeg' / 'bin', APP_DIR / 'ffmpeg', APP_DIR, BASE / 'ffmpeg' / 'bin'):
        if (d / exe).is_file():
            return str(d / exe)
    env = os.environ.get('FFMPEG_DIR')
    if env and (Path(env) / exe).is_file():
        return str(Path(env) / exe)
    return shutil.which(name)


FFMPEG = find_tool('ffmpeg')
AIV = aivideo.AIVideo(HOME, APP_DIR, BASE, FFMPEG, NO_WINDOW)     # KI-Video (freiwilliges Zusatz-Paket)
import atexit
atexit.register(AIV.shutdown)
FFPROBE = find_tool('ffprobe')


def run(args, timeout=60):
    return subprocess.run(args, capture_output=True, timeout=timeout, creationflags=NO_WINDOW,
                          stdin=subprocess.DEVNULL)


def load_config():
    try:
        return json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def save_config(conf):
    HOME.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(conf, indent=1, ensure_ascii=False), encoding='utf-8')


def default_outdir():
    base = Path.home() / 'Videos'
    if os.name == 'nt':
        try:   # echter "Videos"-Ordner (kann verschoben sein)
            import ctypes, uuid
            # FOLDERID_Videos {18989B1D-99B5-455B-841C-AB7C74E4DDFC}
            g = uuid.UUID('18989B1D-99B5-455B-841C-AB7C74E4DDFC').bytes_le
            guid = (ctypes.c_byte * 16)(*g)
            p = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(p)) == 0:
                base = Path(p.value)
                ctypes.windll.ole32.CoTaskMemFree(p)
        except Exception:  # noqa: BLE001
            pass
    return str(base / APP_DIRNAME)


def to_sec(t):
    """'1:23', '01:02:03', '83', '1:23,5' -> Sekunden (float) oder None."""
    t = str(t or '').strip().replace(',', '.')
    if not t:
        return None
    try:
        parts = [float(p) for p in t.split(':')]
    except ValueError:
        return None
    if len(parts) > 3 or any(p < 0 for p in parts):
        return None
    s = 0.0
    for p in parts:
        s = s * 60 + p
    return s


def mmss(s):
    s = max(0, int(round(s)))
    h, r = divmod(s, 3600)
    m, r = divmod(r, 60)
    return '%d:%02d:%02d' % (h, m, r) if h else '%d:%02d' % (m, r)


def num(x):
    """Zahl für FFmpeg ohne überflüssige Nachkommastellen."""
    return ('%.3f' % x).rstrip('0').rstrip('.')


def safe_name(name):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', name).strip(' .')
    return name[:120] or 'video'


def probe(path):
    if not FFPROBE:
        raise RuntimeError('FFprobe fehlt – bitte das Programm neu installieren.')
    r = run([FFPROBE, '-v', 'error', '-print_format', 'json', '-show_format', '-show_streams', str(path)], timeout=40)
    if r.returncode:
        raise RuntimeError('Datei kann nicht gelesen werden.')
    d = json.loads(r.stdout.decode('utf-8', 'replace') or '{}')
    fmt = d.get('format') or {}
    streams = d.get('streams') or []
    a = next((s for s in streams if s.get('codec_type') == 'audio'), None)
    v = next((s for s in streams if s.get('codec_type') == 'video'), None)
    info = {'format': fmt.get('format_name', ''), 'duration': float(fmt.get('duration') or 0) or None,
            'bitrate': int(fmt.get('bit_rate') or 0) or None}
    if a:
        info.update(audio=True, acodec=a.get('codec_name'), sample_rate=int(a.get('sample_rate') or 0) or None,
                    channels=a.get('channels'))
        if not info['duration'] and a.get('duration'):
            info['duration'] = float(a['duration'])
    if v:
        info.update(video=True, vcodec=v.get('codec_name'), width=v.get('width'), height=v.get('height'),
                    attached_pic=bool((v.get('disposition') or {}).get('attached_pic')))
    return info


def hw_check():
    """Prüft im Hintergrund, welche Encoder auf diesem PC wirklich funktionieren (1 Testbild)."""
    try:
        _hw_check()
    finally:
        HW_DONE.set()


def _hw_check():
    if not FFMPEG:
        for k in HW:
            HW[k] = False
        return
    try:
        listed = run([FFMPEG, '-hide_banner', '-encoders'], timeout=30).stdout.decode('utf-8', 'replace')
    except Exception:  # noqa: BLE001
        listed = ''
    for key, (enc, _) in ENCODERS.items():
        if (' ' + enc + ' ') not in listed:
            HW[key] = False
            continue
        if key in ('x264', 'x265'):
            HW[key] = True
            continue
        try:
            r = run([FFMPEG, '-hide_banner', '-v', 'error', '-f', 'lavfi', '-i', 'color=black:s=256x256:d=0.2', '-frames:v', '2',
                     '-c:v', enc, '-f', 'null', '-'], timeout=25)
            HW[key] = r.returncode == 0
        except Exception:  # noqa: BLE001
            HW[key] = False


# ---------- Einstellungen -> FFmpeg ----------
def clean_settings(s):
    out = dict(DEFAULTS)
    out.update({k: v for k, v in (s or {}).items() if k in DEFAULTS})
    if out['fmt'] not in FORMATS:
        out['fmt'] = 'yt4k'
    try:
        out['fps'] = int(out['fps'])
    except (TypeError, ValueError):
        out['fps'] = 30
    if out['fps'] not in FPS_LIST:
        out['fps'] = 30
    for k in ('fadeIn', 'fadeOut'):
        try:
            out[k] = min(max(float(out[k]), 0.0), 15.0)
        except (TypeError, ValueError):
            out[k] = DEFAULTS[k]
    for k in ('transIn', 'transOut'):
        if out[k] not in TRANS_IDS:
            out[k] = 'fade'
    if out['color'] not in ('black', 'white'):
        out['color'] = 'black'
    if out['target'] not in ('av', 'v', 'a'):
        out['target'] = 'av'
    if out['fit'] not in ('blur', 'cover', 'contain'):
        out['fit'] = 'blur'
    if out['enc'] not in ENCODERS and out['enc'] != 'auto':
        out['enc'] = 'auto'
    if str(out['quality']) not in QUALITY:
        out['quality'] = '18'
    out['quality'] = str(out['quality'])
    try:
        out['shortLen'] = int(out['shortLen'])
    except (TypeError, ValueError):
        out['shortLen'] = 60
    if out['shortLen'] not in highlight.LENGTHS:
        out['shortLen'] = 60
    out['shortLyrics'] = bool(out['shortLyrics'])
    # KI-Video
    out['ai'] = bool(out['ai'])
    out['aiClip'] = str(out['aiClip'] or '') if AIV.clip_path(out['aiClip']) else ''
    if out['aiArea'] not in ('full', 'mask'):
        out['aiArea'] = 'full'
    if not isinstance(out['aiMask'], str) or out['aiMask'] not in MASKS:
        out['aiMask'] = ''
    if out['aiArea'] == 'mask' and not out['aiMask']:
        out['aiArea'] = 'full'
    try:
        out['aiFeather'] = min(max(float(out['aiFeather']), 0.0), 6.0)
    except (TypeError, ValueError):
        out['aiFeather'] = 1.5
    if out['aiMotion'] not in aivideo.MOTION_IDS:
        out['aiMotion'] = 'hair'
    out['aiText'] = re.sub(r'\s+', ' ', str(out['aiText'] or ''))[:300]
    try:
        out['aiLen'] = int(out['aiLen'])
    except (TypeError, ValueError):
        out['aiLen'] = 30
    if out['aiLen'] not in AI_LENS:
        out['aiLen'] = 30
    if out['aiQual'] not in aivideo.QUALITIES:
        out['aiQual'] = 'fast'
    viz.clean(s, out)
    fx.clean(s, out)
    # Markierungen aus einer früheren Sitzung (Maske nicht mehr vorhanden) zurücksetzen
    if out.get('vizMask') and out['vizMask'] not in MASKS:
        out['vizMask'] = ''
        if out.get('vizShape') == 'mask':
            out['vizShape'] = 'box'
    if out.get('fxMask') and out['fxMask'] not in MASKS:
        out['fxMask'] = ''
        if out.get('fxArea') == 'mask':
            out['fxArea'] = 'full'
    return out


def timing(s, audio_dur):
    """Start, Länge, Hinweise. audio_dur kann None sein (dann Schätzung 0)."""
    total = audio_dur or 0
    notes = []
    start = to_sec(s['start']) or 0.0
    if total and start >= total:
        notes.append('Der Start liegt hinter dem Song-Ende – es wird ab 0:00 genommen.')
        start = 0.0
    end = to_sec(s['end'])
    if end is None or (total and end > total) or end <= start:
        if end is not None and str(s['end']).strip() and end <= start:
            notes.append('Das Ende liegt vor dem Start – es wird bis zum Song-Ende genommen.')
        end = total
    dur = max(end - start, 0)
    vertical = FORMATS[s['fmt']][3]
    if vertical and dur > SHORTS_MAX:
        dur = SHORTS_MAX
        notes.append('YouTube Shorts dürfen höchstens 3:00 Minuten lang sein. Das Video endet automatisch nach 3:00 '
                     '(ab %s). Mit Start/Ende wählst du den besten Teil.' % mmss(start))
    fi = min(s['fadeIn'], dur / 2) if dur else s['fadeIn']
    fo = min(s['fadeOut'], dur / 2) if dur else s['fadeOut']
    return start, dur, fi, fo, notes


def fit_filter(fit, w, h):
    """Filterkette: Bild auf w×h bringen (wird nur EINMAL berechnet, nicht für jedes Videobild)."""
    if fit == 'cover':
        return '[0:v]scale=%d:%d:force_original_aspect_ratio=increase:flags=lanczos,crop=%d:%d,setsar=1[o]' % (w, h, w, h)
    if fit == 'contain':
        return ('[0:v]scale=%d:%d:force_original_aspect_ratio=decrease:flags=lanczos,'
                'pad=%d:%d:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1[o]' % (w, h, w, h))
    sigma = max(w, h) / 40
    return ('[0:v]split=2[a][b];[a]scale=%d:%d:force_original_aspect_ratio=increase:flags=bilinear,crop=%d:%d,'
            'gblur=sigma=%s:steps=2,eq=brightness=-0.08:saturation=1.15[bg];'
            '[b]scale=%d:%d:force_original_aspect_ratio=decrease:flags=lanczos[fg];'
            '[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[o]' % (w, h, w, h, num(sigma), w, h))


def still_command(img_path, out_png, s, scale=1.0):
    _, w, h, _ = FORMATS[s['fmt']]
    w, h = int(w * scale) // 2 * 2, int(h * scale) // 2 * 2
    return [FFMPEG, '-hide_banner', '-v', 'error', '-y', '-i', str(img_path), '-filter_complex', fit_filter(s['fit'], w, h),
            '-map', '[o]', '-frames:v', '1', '-update', '1', str(out_png)]


def transition_graph(vchain, w, h, fps, dur, fi, fo, t_in, t_out, color, label='v'):
    """Bild kommt (Farbe -> Bild) und Bild geht (Bild -> Farbe) mit FFmpeg-xfade-Übergängen."""
    c = 'white' if color == 'white' else 'black'
    tb = ',settb=1/%d' % fps
    out = []
    use_in = fi > 0 and t_in != 'none'
    use_out = fo > 0 and t_out != 'none'
    cur = '%s,trim=duration=%s%s' % (vchain, num(dur), tb)
    if use_in:
        out.append('color=c=%s:s=%dx%d:r=%d:d=%s,format=yuv420p,setsar=1%s[cin]' % (c, w, h, fps, num(fi), tb))
        out.append('%s[pin]' % cur)
        cur = '[cin][pin]xfade=transition=%s:duration=%s:offset=0' % (t_in, num(fi))
    if use_out:
        out.append('color=c=%s:s=%dx%d:r=%d:d=%s,format=yuv420p,setsar=1%s[cout]' % (c, w, h, fps, num(fo), tb))
        out.append('%s[pout]' % cur)
        cur = '[pout][cout]xfade=transition=%s:duration=%s:offset=%s' % (t_out, num(fo), num(max(dur - fo, 0)))
    out.append('%s,format=yuv420p[%s]' % (cur, label))
    return out


def prepare_mark(s, W, H, dur, workdir=None, tag='x'):
    """Masken-/Pfad-Dateien für FFmpeg erzeugen. Rückgabe (zusätzliche Eingabedateien, extra-Infos für viz.graph)."""
    if not s['viz'] or s['vizShape'] == 'box':
        return [], {}
    if s['vizShape'] == 'mask':
        if workdir is None or not mark:
            return ['maske.png'], {'mask': '[2:v]'}
        src = MASKS.get(s['vizMask'])
        if not src or not Path(src).is_file():
            return [], {}
        vw, vh = viz.even(W * s['vizW'] / 100), viz.even(H * s['vizH'] / 100)
        ox, oy = min(int(W * s['vizX'] / 100), W - vw), min(int(H * s['vizY'] / 100), H - vh)
        out = Path(workdir) / ('mask-%s.png' % tag)
        mark.mask_crop(src, W, H, ox, oy, vw, vh, out, s['vizFeather'])
        return [str(out)], {'mask': '[2:v]'}
    thick = max(4, int(H * s['vizThick'] / 100))
    both = s['vizBoth']
    if s['vizStyle'] in viz.WAVE_FAMILY:          # Wellen schwingen mittig um die Linie (sonst erscheinen sie doppelt)
        both, thick = 'center', thick * 2
    if workdir is None or not mark:
        xs = [q[0] for q in s['vizPath']]
        ys = [q[1] for q in s['vizPath']]
        bw, bh = viz.even(W * max(0.02, max(xs) - min(xs)) + 2 * thick), viz.even(H * max(0.02, max(ys) - min(ys)) + 2 * thick)
        return ['karte-x.pgm', 'karte-y.pgm'], {'path': {'xm': '[2:v]', 'ym': '[3:v]', 'L': 1000, 'T': thick, 'ox': max(0, int(W * min(xs)) - thick),
                                                       'oy': max(0, int(H * min(ys)) - thick), 'bw': bw, 'bh': bh, 'closed': s['vizClosed']}}
    xp, yp = Path(workdir) / ('xmap-%s.pgm' % tag), Path(workdir) / ('ymap-%s.pgm' % tag)
    ox, oy, bw, bh, L, T = mark.path_maps(s['vizPath'], s['vizClosed'], both, W, H, thick, xp, yp)
    return [str(xp), str(yp)], {'path': {'xm': '[2:v]', 'ym': '[3:v]', 'L': L, 'T': T, 'ox': ox, 'oy': oy, 'bw': bw, 'bh': bh, 'closed': s['vizClosed']}}


def encode_command(still_png, audio_path, out_path, s, audio_dur, scale=1.0, fast=False, cmdfile=None, mark_dir=None, tag='x'):
    fx_notes = []
    s = dict(viz.effective(s), enc='x264' if fast else resolve_enc(s['enc']))
    name, w, h, vertical = FORMATS[s['fmt']]
    w, h = int(w * scale) // 2 * 2, int(h * scale) // 2 * 2
    fps = s['fps']
    start, dur, fi, fo, notes = timing(s, audio_dur)
    do_v, do_a = s['target'] != 'a', s['target'] != 'v'
    parts = []
    # Ton: Fades (+ Abzweig für den Visualizer)
    afx = []
    if do_a and fi > 0:
        afx.append('afade=t=in:st=0:d=%s' % num(fi))
    if do_a and fo > 0:
        afx.append('afade=t=out:st=%s:d=%s' % (num(max(dur - fo, 0)), num(fo)))
    afx.append('aresample=48000')
    # Bild nur EINMAL dekodieren und im Speicher wiederholen (schneller als -loop 1)
    vid = '[0:v]format=yuv420p,loop=loop=-1:size=1:start=0,fps=%d,setpts=N/%d/TB' % (fps, fps)
    extra_in, extra = prepare_mark(s, w, h, dur, mark_dir, tag) if s['viz'] else ([], {})
    fx_in = []
    fxinfo = None
    if fx.active(s) and do_v:
        fx_in, fxinfo = fx.prepare(s, w, h, fps, dur, mark_dir, tag, still_png, 2 + len(extra_in), MASKS, DEPTH, mark)
    ai_in = []
    if s.get('ai') and do_v:
        ai_in, vid, ai_note = ai_graph(s, w, h, fps, vid, parts, 2 + len(extra_in) + len(fx_in), mark_dir, tag)
        if ai_note:
            fx_notes.append(ai_note)
    if fxinfo is not None:
        fparts, vid = fx.graph(s, w, h, fps, dur, fxinfo, vid, cmdfile)
        parts.extend(fparts)
        if fxinfo.get('depth_method') == 'einfach':
            fx_notes.append('3D-Kamerafahrt: Das KI-Tiefenmodell fehlt – es wurde eine einfache Tiefenschätzung benutzt.')
    if s['viz']:
        parts.append('[1:a]%s,asplit=2[aout][av]' % ','.join(afx))
        vparts, ox, oy = viz.graph(s, w, h, fps, dur, cmdfile, extra)
        parts.extend(vparts)
        parts.append('%s[base];[base][wv]overlay=%d:%d:shortest=0:eof_action=pass,format=yuv420p' % (vid, ox, oy))
        vchain = parts.pop()
    else:
        parts.append('[1:a]%s[aout]' % ','.join(afx))
        vchain = vid
    parts.extend(transition_graph(vchain, w, h, fps, dur, fi if do_v else 0, fo if do_v else 0,
                                  s['transIn'], s['transOut'], s['color']))
    graph = ';'.join(parts)

    enc, _ = ENCODERS[s['enc']]
    q = int(s['quality'])
    preset = QUALITY[s['quality']][0]
    gop = max(int(round(fps / 2)), 1)            # YouTube empfiehlt: GOP = halbe Bildrate, geschlossen
    if s['enc'] == 'x265':
        venc = ['-c:v', 'libx265', '-preset', preset, '-crf', str(q + 2), '-tag:v', 'hvc1', '-x265-params', 'log-level=error']
    elif s['enc'] == 'nvenc':
        venc = ['-c:v', 'h264_nvenc', '-preset', 'p5', '-tune', 'hq', '-rc', 'vbr', '-cq', str(q + 1), '-b:v', '0',
                '-spatial-aq', '1', '-profile:v', 'high']
    elif s['enc'] == 'qsv':
        venc = ['-c:v', 'h264_qsv', '-preset', 'medium', '-global_quality', str(q + 2), '-look_ahead', '0']
    elif s['enc'] == 'amf':
        venc = ['-c:v', 'h264_amf', '-quality', 'quality', '-rc', 'cqp', '-qp_i', str(q + 2), '-qp_p', str(q + 4)]
    else:
        venc = ['-c:v', 'libx264', '-preset', 'ultrafast' if fast else preset, '-crf', str(26 if fast else q), '-profile:v', 'high']
        if not s['viz'] and not fx.active(s) and not s.get('ai'):
            venc += ['-tune', 'stillimage']
    venc += ['-g', str(gop), '-bf', '2', '-pix_fmt', 'yuv420p', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709']
    if s['enc'] == 'x264':
        venc += ['-flags', '+cgop']

    args = [FFMPEG, '-hide_banner', '-y', '-i', str(still_png)]
    if start > 0:
        args += ['-ss', num(start)]
    args += ['-t', num(dur), '-i', str(audio_path)]
    for f in extra_in + fx_in:
        args += ['-i', str(f)]
    for f in ai_in:
        args += (['-stream_loop', '-1'] if str(f).endswith('.mp4') else []) + ['-i', str(f)]
    args += ['-filter_complex', graph, '-map', '[v]', '-map', '[aout]']
    args += venc + ['-r', str(fps), '-c:a', 'aac', '-b:a', '384k', '-ac', '2', '-t', num(dur), '-movflags', '+faststart',
                    '-metadata', 'encoder=%s %s' % (APP_NAME, VERSION), str(out_path)]
    return args, {'encoder': s['enc'], 'encoder_name': ENCODERS[s['enc']][1], 'start': start, 'duration': dur, 'fadeIn': fi, 'fadeOut': fo, 'notes': notes + fx_notes, 'width': w, 'height': h,
                  'format': name, 'vertical': vertical}


def ai_graph(s, w, h, fps, vid, parts, idx, mark_dir, tag):
    """KI-Video einsetzen: ganzes Bild ersetzen oder nur in der markierten Fläche (Rest bleibt das scharfe Original)."""
    clip = AIV.clip_path(s.get('aiClip'))
    if not clip:
        return [], vid, 'KI-Video: noch kein fertiges KI-Video ausgewählt – das Bild bleibt unbewegt.'
    try:
        meta = json.loads((clip.parent.parent / 'meta.json').read_text('utf-8'))
    except Exception:  # noqa: BLE001
        meta = {}
    if 'vertical' in meta and bool(meta['vertical']) != bool(FORMATS[s['fmt']][3]):
        return [], vid, 'KI-Video: passt nicht zum Hoch-/Querformat – bitte für dieses Format neu erzeugen.'
    files = [str(clip)]
    ai = '[%d:v]fps=%d,scale=%d:%d:flags=bicubic,setsar=1' % (idx, fps, w, h)
    mp = None
    if mark and s['aiArea'] == 'mask' and MASKS.get(s['aiMask']) and Path(MASKS[s['aiMask']]).is_file():
        mp = Path(mark_dir or STAGE) / ('ki-maske-%s.png' % tag)
        mark.mask_crop(MASKS[s['aiMask']], w, h, 0, 0, w, h, str(mp), s['aiFeather'])
    if not mp:
        parts.append(ai + ',format=yuv420p[aio]')
        return files, '[aio]null', ''
    files.append(str(mp))
    parts.append(ai + ',format=gbrp[aiv]')
    parts.append('%s,format=gbrp[aib]' % vid)
    parts.append('[%d:v]format=gray,scale=%d:%d,format=gbrp,loop=loop=-1:size=1,fps=%d[aim]' % (idx + 1, w, h, fps))
    parts.append('[aib][aiv][aim]maskedmerge,format=yuv420p[aio]')
    return files, '[aio]null', ''


IMG_HASH = {}


def ai_key(img, s):
    """Kennung für Bild + Zuschnitt + Format + Bewegung (gleiche Kennung = vorhandene Stücke wiederverwenden)."""
    p = Path(img['path'])
    k = (str(p), p.stat().st_mtime)
    if k not in IMG_HASH:
        import hashlib
        IMG_HASH[k] = hashlib.sha1(p.read_bytes()).hexdigest()
    return aivideo.AIVideo.key(('%s|%s' % (IMG_HASH[k], s['fit'])).encode(), s['aiQual'], s['aiMotion'], s['aiText'],
                               bool(FORMATS[s['fmt']][3]))


def ai_length(s, audio):
    if s['aiLen']:
        return float(s['aiLen'])
    _, dur, *_ = timing(s, (audio or {}).get('info', {}).get('duration') if audio else None)
    return float(dur or 60)


def ai_still(img, s):
    """Bild im Zielformat (mit Zuschnitt) in ausreichender Größe für die KI."""
    _, W, H, vertical = FORMATS[s['fmt']]
    gw, gh, _ = aivideo.gen_size(s['aiQual'], vertical)
    k = min(1.0, max(gw / W, gh / H) * 1.05)
    out = STAGE / ('ki-start-%s.png' % secrets.token_hex(4))
    r = run(still_command(img['path'], out, s, k), timeout=120)
    if r.returncode or not out.is_file():
        raise RuntimeError('Bild konnte nicht vorbereitet werden')
    return out


def quote(a):
    a = str(a)
    return '"%s"' % a if re.search(r'[\s;\[\]()|&]', a) or a == '' else a


def command_text(s, audio_name, image_name, out_name, audio_dur):
    args, meta = encode_command('bild.png', audio_name or 'song.mp3', out_name or 'video.mp4', s, audio_dur,
                                cmdfile='klang.txt' if needs_sound(s) else None)
    args[0] = 'ffmpeg'
    pre = 'ffmpeg -i %s -filter_complex "%s" -frames:v 1 bild.png' % (quote(image_name or 'bild.jpg'), fit_filter(s['fit'], meta['width'], meta['height']))
    return pre + '\n\n' + ' '.join(quote(a) for a in args), meta


def transition_preview(img_path, out_mp4, s, which):
    """Kurzer Vorschau-Clip (klein, ohne Ton) eines Übergangs mit dem echten Bild."""
    _, W, H, vertical = FORMATS[s['fmt']]
    k = 640 / max(W, H)
    w, h = int(W * k) // 2 * 2, int(H * k) // 2 * 2
    still = Path(str(out_mp4) + '.png')
    r = run(still_command(img_path, still, s, k), timeout=120)
    if r.returncode:
        return False
    d = max(min(s['fadeIn'] if which == 'in' else s['fadeOut'], 4.0), 1.2)
    fps = 30
    total = d + 1.0
    vid = '[0:v]scale=%d:%d,format=yuv420p,loop=loop=-1:size=1:start=0,fps=%d,setpts=N/%d/TB' % (w, h, fps, fps)
    t = s['transIn'] if which == 'in' else s['transOut']
    if t == 'none':
        t = 'fadefast'
        d = 0.04
    g = transition_graph(vid, w, h, fps, total, d if which == 'in' else 0, d if which == 'out' else 0,
                         t, t, s['color'])
    r = run([FFMPEG, '-hide_banner', '-v', 'error', '-y', '-i', str(still), '-filter_complex', ';'.join(g), '-map', '[v]',
             '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '26', '-pix_fmt', 'yuv420p', '-t', num(total), '-an',
             '-movflags', '+faststart', str(out_mp4)], timeout=120)
    still.unlink(missing_ok=True)
    return r.returncode == 0 and Path(out_mp4).is_file()


def viz_preview(audio, img_path, out_mp4, s):
    """6-Sekunden-Clip (640 px, mit Ton) – genau wie im fertigen Video, nur kleiner."""
    total = audio['info'].get('duration') or 0
    start, dur, _, _, _ = timing(s, total)
    off = start + max(0.0, min(dur * 0.35, dur - 6))
    s2 = dict(s, start=num(off), end=num(min(off + 6, total or off + 6)), fadeIn=0.3, fadeOut=0.3, transIn='fade', transOut='fade')
    _, W, H, _ = FORMATS[s['fmt']]
    k = 640 / max(W, H)
    still = Path(str(out_mp4) + '.png')
    r = run(still_command(img_path, still, s2, k), timeout=120)
    if r.returncode:
        return False, 'Bild konnte nicht vorbereitet werden'
    name = Path(str(out_mp4)).name + '.snd.txt'
    cmd = make_sound_cmds(audio['path'], s2, total, name)
    args, _ = encode_command(still, audio['path'], out_mp4, s2, total, scale=k, fast=True, cmdfile=cmd, mark_dir=STAGE, tag='prev')
    r = subprocess.run(args, capture_output=True, timeout=240, creationflags=NO_WINDOW, stdin=subprocess.DEVNULL, cwd=str(STAGE))
    still.unlink(missing_ok=True)
    if cmd:
        (STAGE / cmd).unlink(missing_ok=True)
    if r.returncode or not Path(out_mp4).is_file():
        return False, r.stderr.decode('utf-8', 'replace')[-500:]
    return True, ''


def output_name(s, audio_name):
    stem = Path(audio_name or 'video').stem
    _, w, h, vertical = FORMATS[s['fmt']]
    tag = ('shorts_%dx%d' % (w, h)) if vertical else ('%dp' % h)
    return safe_name('%s_%s_%dfps' % (stem, tag, s['fps'])) + '.mp4'


def unique_path(folder, name):
    p = Path(folder) / name
    i = 2
    while p.exists():
        p = Path(folder) / ('%s (%d)%s' % (Path(name).stem, i, Path(name).suffix))
        i += 1
    return p


# ---------- Konvertier-Aufträge ----------
def new_job(settings, audio_tok, image_tok, outdir, outname):
    a, i = STAGED.get(audio_tok), STAGED.get(image_tok)
    if not a or not i:
        raise ValueError('Bitte zuerst eine Audiodatei und ein Bild hineinziehen.')
    s = clean_settings(settings)
    if not FFMPEG:
        raise ValueError('FFmpeg wurde nicht gefunden – bitte das Programm neu installieren.')
    if s['enc'] != 'auto' and HW.get(s['enc']) is False:
        raise ValueError('Der gewählte Encoder (%s) funktioniert auf diesem PC nicht.' % ENCODERS[s['enc']][1])
    outdir = Path(outdir or default_outdir())
    outdir.mkdir(parents=True, exist_ok=True)
    name = safe_name(Path(outname).stem) + '.mp4' if outname else output_name(s, a['name'])
    jid = secrets.token_hex(6)
    job = {'id': jid, 'state': 'wartet', 'percent': 0, 'phase': 'In der Warteschlange', 'settings': s, 'audio': a, 'image': i,
           'outdir': str(outdir), 'name': name, 'out': '', 'speed': '', 'fps': '', 'frame': 0, 'time': 0.0, 'eta': None,
           'log': [], 'error': '', 'created': time.time(), 'proc': None, 'cancel': False, 'meta': {}}
    with QLOCK:
        JOBS[jid] = job
        QUEUE.append(jid)
    QEVENT.set()
    return job


def job_view(j):
    return {k: j[k] for k in ('id', 'state', 'percent', 'phase', 'name', 'out', 'speed', 'fps', 'frame', 'time', 'eta', 'error', 'meta')} | {
        'log': j['log'][-14:], 'audio': j['audio']['name'], 'image': j['image']['name'], 'outdir': j['outdir'],
        'settings': j['settings']}


def needs_sound(s):
    return (s['viz'] and s['vizMode'] == 'sound') or (s['fx'] not in ('none', 'flow') and s['fxBeat'])


def make_sound_cmds(audio_path, s, audio_dur, name):
    """„Nach Sound“ (Visualizer) und „Im Takt“ (Effekte): Befehle aus dem Song berechnen
    (eine gemeinsame sendcmd-Datei im Arbeitsordner, FFmpeg läuft dort)."""
    if not needs_sound(s):
        return None
    start, dur, _, _, _ = timing(s, audio_dur)
    text = ''
    if s['viz'] and s['vizMode'] == 'sound':
        text += viz.sound_commands(FFMPEG, audio_path, start, dur, run)
    if s['fx'] not in ('none', 'flow') and s['fxBeat']:
        text += fx.beat_commands(viz.loudness(FFMPEG, audio_path, start, dur, run))
    if not text:
        return None
    (STAGE / name).write_text(text, encoding='ascii')
    return name


def encode_pass(j, still, part, s, cmdfile=None):
    """Ein FFmpeg-Durchlauf mit Fortschritt. Rückgabe (ok, letzte Fehlerzeilen)."""
    args, meta = encode_command(still, j['audio']['path'], part, s, j['audio']['info'].get('duration'), cmdfile=cmdfile,
                                mark_dir=STAGE, tag=j['id'])
    j['meta'] = meta
    dur = meta['duration'] or 1
    args[1:1] = ['-progress', 'pipe:1', '-nostats']
    j['log'].append('FFmpeg startet: %s · %s → %s' % (meta['format'], meta['encoder_name'], Path(j['out']).name))
    j['phase'] = 'Video wird encodiert (%s) …' % meta['encoder_name']
    errlog = STAGE / ('err-%s.txt' % j['id'])
    with open(errlog, 'wb') as ef:
        p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=ef, stdin=subprocess.PIPE, creationflags=NO_WINDOW, cwd=str(STAGE))
        j['proc'] = p
        t0 = time.time()
        cur = {}
        last_step = -1
        for raw in p.stdout:
            line = raw.decode('utf-8', 'replace').strip()
            if '=' not in line:
                continue
            k, v = line.split('=', 1)
            cur[k] = v
            if k != 'progress':
                continue
            us = cur.get('out_time_us') or cur.get('out_time_ms') or '0'
            try:
                t = max(int(us), 0) / 1e6
            except ValueError:
                t = 0
            j['time'] = t
            j['frame'] = int(cur.get('frame', '0') or 0)
            j['fps'] = cur.get('fps', '')
            j['speed'] = cur.get('speed', '').strip()
            pct = min(99.0, 1 + t / dur * 98)
            j['percent'] = round(pct, 1)
            el = time.time() - t0
            j['eta'] = round(el / (t / dur) - el) if t > 0.5 else None
            step = int(pct // 5) * 5
            if step != last_step and step > 0:
                last_step = step
                j['log'].append('[%3d %%] Bild %s · %s · Tempo %s' % (step, cur.get('frame', '?'), mmss(t), j['speed'] or '–'))
            if v == 'end':
                break
        p.wait()
    j['proc'] = None
    ok = p.returncode == 0 and part.is_file() and not j['cancel']
    tail = '' if ok else '\n'.join(errlog.read_text('utf-8', 'replace').strip().splitlines()[-12:])
    if not ok:
        part.unlink(missing_ok=True)
    return ok, tail


def run_job(j):
    s = j['settings']
    try:
        j['state'] = 'läuft'
        j['phase'] = 'Bild wird vorbereitet …'
        still = STAGE / ('still-%s.png' % j['id'])
        r = run(still_command(j['image']['path'], still, s), timeout=300)
        if r.returncode or not still.is_file():
            raise RuntimeError('Das Bild konnte nicht vorbereitet werden.\n' + r.stderr.decode('utf-8', 'replace')[-600:])
        j['percent'] = 1
        out = unique_path(j['outdir'], j['name'])
        part = out.with_name(out.stem + '.part.mp4')
        j['out'] = str(out)
        s = dict(s, enc=resolve_enc(s['enc'], wait=30))
        if needs_sound(s):
            j['phase'] = 'Klang wird analysiert …'
        if fx.active(s):
            j['log'].append('Effekte: %s%s' % (dict((e[0], e[1]) for e in fx.EFFECTS)[s['fx']],
                                                '' if s['cam'] == 'none' else ' · Kamera: ' + dict((c[0], c[1]) for c in fx.CAMS)[s['cam']]))
            if s['fx'] != 'none':
                j['log'].append('  Übernommen: Menge %d %% · Tempo %d %% · Größe %d %% · Deckkraft %d %%%s' % (
                    s['fxAmount'], s['fxSpeed'], s['fxSize'], s['fxAlpha'], ' · im Takt' if s['fxBeat'] else ''))
            if s['cam'] != 'none':
                j['log'].append('  Kamera: Stärke %d %% · Tempo %d %%' % (s['camAmount'], s['camSpeed']))
        cmd = make_sound_cmds(j['audio']['path'], s, j['audio']['info'].get('duration'), 'snd-%s.txt' % j['id'])
        ok, tail = encode_pass(j, still, part, s, cmd)
        if not ok and not j['cancel'] and s['enc'] in GPU_ORDER:
            j['log'].append('Grafikkarte (%s) hat abgebrochen – es geht automatisch mit der CPU weiter.' % ENCODERS[s['enc']][1])
            j['percent'] = 1
            ok, tail = encode_pass(j, still, part, dict(s, enc='x264'), cmd)
        if j['cancel']:
            part.unlink(missing_ok=True)
            j['state'] = 'abgebrochen'
            j['phase'] = 'Abgebrochen'
            return
        if not ok:
            part.unlink(missing_ok=True)
            raise RuntimeError('FFmpeg hat einen Fehler gemeldet:\n' + tail)
        part.replace(out)
        j['phase'] = 'Wird geprüft …'
        try:
            info = probe(out)
            j['meta']['check'] = {'duration': info.get('duration'), 'width': info.get('width'), 'height': info.get('height'),
                                  'vcodec': info.get('vcodec'), 'acodec': info.get('acodec'), 'size': out.stat().st_size}
        except Exception:  # noqa: BLE001
            pass
        j['percent'] = 100
        j['state'] = 'fertig'
        j['phase'] = 'Fertig – bereit für YouTube'
        j['log'].append('[100 %] Fertig: ' + out.name)
    except Exception as e:  # noqa: BLE001
        j['state'] = 'fehler'
        j['error'] = str(e)
        j['phase'] = 'Fehler'
    finally:
        j['proc'] = None
        for f in STAGE.glob('*-%s.*' % j['id']):
            f.unlink(missing_ok=True)


def worker():
    while True:
        QEVENT.wait()
        with QLOCK:
            nxt = next((JOBS[i] for i in QUEUE if JOBS[i]['state'] == 'wartet'), None)
            if not nxt:
                QEVENT.clear()
                continue
        run_job(nxt)


def cancel_job(jid):
    j = JOBS.get(jid)
    if not j:
        return
    j['cancel'] = True
    if j['state'] == 'wartet':
        j['state'] = 'abgebrochen'
        j['phase'] = 'Abgebrochen'
    p = j.get('proc')
    if p and p.poll() is None:
        try:
            p.stdin.write(b'q')
            p.stdin.flush()
        except Exception:  # noqa: BLE001
            pass
        threading.Timer(4, lambda: p.poll() is None and p.kill()).start()


def busy():
    return any(j['state'] in ('läuft', 'wartet') for j in JOBS.values()) or \
        any(j['state'] in ('läuft', 'wartet') for j in AIV.jobs.values())


def stop_all():
    for jid in list(JOBS):
        cancel_job(jid)
    AIV.shutdown()


def show_in_folder(path):
    path = Path(path)
    if os.name == 'nt':
        if path.is_file():
            subprocess.Popen('explorer /select,"%s"' % path)
        else:
            os.startfile(str(path if path.exists() else path.parent))  # noqa: S606
    else:
        webbrowser.open(path.parent.as_uri() if path.is_file() else path.as_uri())


# ---------- Dateien annehmen ----------
def stage_file(dest, name, kind, tok):
    """Prüft eine Datei im Arbeitsordner und nimmt sie als Song oder Bild auf (ValueError bei Problemen)."""
    dest = Path(dest)
    try:
        info = probe(dest)
    except Exception as e:  # noqa: BLE001
        dest.unlink(missing_ok=True)
        raise ValueError('„%s“: %s' % (name, e))
    fmt = info.get('format', '')
    is_image = bool(info.get('video')) and not info.get('audio') and (
        not info.get('duration') or info['duration'] < 1 or fmt.endswith('_pipe') or fmt == 'image2')
    if kind not in ('audio', 'image'):
        kind = 'image' if is_image else ('audio' if info.get('audio') else '')
    if kind == 'audio' and not info.get('audio'):
        dest.unlink(missing_ok=True)
        raise ValueError('„%s“ enthält keinen Ton.' % name)
    if kind == 'image' and not info.get('video'):
        dest.unlink(missing_ok=True)
        raise ValueError('„%s“ ist kein Bild.' % name)
    if not kind:
        dest.unlink(missing_ok=True)
        raise ValueError('„%s“ ist weder Audio noch Bild.' % name)
    entry = {'path': str(dest), 'name': name, 'kind': kind, 'info': info, 'size': dest.stat().st_size}
    if kind == 'image':
        pv = STAGE / ('%s-thumb.jpg' % tok)
        r = run([FFMPEG, '-hide_banner', '-v', 'error', '-y', '-i', str(dest), '-frames:v', '1', '-vf',
                 'scale=640:640:force_original_aspect_ratio=decrease', '-q:v', '3', str(pv)], timeout=60)
        if r.returncode == 0 and pv.is_file():
            entry['preview'] = str(pv)
    STAGED[tok] = entry
    return entry


def public_entry(tok, e):
    return {'token': tok, 'name': e['name'], 'kind': e['kind'], 'info': e['info'], 'size': e['size']}


# ---------- Markieren / KI ----------
def analysis_image(image_tok, s):
    """Das fertige Videobild (Format + Bild-Anpassung) in max. 1024 px – darauf arbeitet die KI."""
    i = STAGED.get(image_tok or '')
    if not i:
        raise ValueError('Zuerst ein Bild hineinziehen.')
    key = (image_tok, s['fmt'], s['fit'])
    p = ANALYSIS.get(key)
    if p and Path(p).is_file():
        return p, key
    _, W, H, _ = FORMATS[s['fmt']]
    out = STAGE / ('ana-%s-%s-%s.png' % (image_tok, s['fmt'], s['fit']))
    r = run(still_command(i['path'], out, s, 1024 / max(W, H)), timeout=120)
    if r.returncode or not out.is_file():
        raise ValueError('Bild konnte nicht vorbereitet werden.')
    ANALYSIS[key] = str(out)
    return str(out), key


def detect_gpus():
    """Grafikkarten mit Name + Grafikspeicher (Windows: Treiber-Registry, NVIDIA genauer über nvidia-smi)."""
    found = []
    if os.name == 'nt':
        try:
            import winreg
            root = r'SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}'
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, root) as k:
                for i in range(64):
                    try:
                        sub = winreg.EnumKey(k, i)
                    except OSError:
                        break
                    if not sub.isdigit():
                        continue
                    try:
                        with winreg.OpenKey(k, sub) as d:
                            name = str(winreg.QueryValueEx(d, 'DriverDesc')[0])
                            mem = 0
                            for val in ('HardwareInformation.qwMemorySize', 'HardwareInformation.MemorySize'):
                                try:
                                    v = winreg.QueryValueEx(d, val)[0]
                                    v = int.from_bytes(v[:8], 'little') if isinstance(v, (bytes, bytearray)) else int(v)
                                    if v > mem:
                                        mem = v
                                except OSError:
                                    pass
                    except OSError:
                        continue
                    if re.search(r'basic display|basic render|remote|virtual|parsec|dameware|citrix', name, re.I):
                        continue
                    found.append({'name': name, 'vram': round(mem / 1024 ** 3, 1)})
        except Exception:  # noqa: BLE001
            pass
    smi = shutil.which('nvidia-smi') or (r'C:\Windows\System32\nvidia-smi.exe' if os.name == 'nt' else None)
    if smi and Path(smi).is_file():
        try:
            r = run([smi, '--query-gpu=name,memory.total', '--format=csv,noheader,nounits'], timeout=10)
            for line in r.stdout.decode('utf-8', 'replace').splitlines():
                parts = [x.strip() for x in line.split(',')]
                if len(parts) == 2 and parts[1].isdigit():
                    vram = round(int(parts[1]) / 1024, 1)
                    for g in found:
                        if parts[0].lower() in g['name'].lower() or g['name'].lower() in parts[0].lower():
                            g['vram'] = vram
                            break
                    else:
                        found.append({'name': parts[0], 'vram': vram})
        except Exception:  # noqa: BLE001
            pass
    for g in found:
        n = g['name'].lower()
        g['vendor'] = 'nvidia' if ('nvidia' in n or 'geforce' in n or 'rtx' in n) else 'amd' if ('amd' in n or 'radeon' in n) else \
            'intel' if 'intel' in n else 'andere'
    found.sort(key=lambda g: -g['vram'])
    GPU[:] = found


def gpu_view():
    """Anzeige + Einschätzung für das (spätere) KI-Video."""
    if not GPU:
        return {'cards': [], 'text': 'Grafikkarte: nicht erkannt', 'video_ai': 'unbekannt',
                'video_text': 'Die Grafikkarte konnte nicht erkannt werden.'}
    g = GPU[0]
    mem = ('%s GB' % ('%g' % g['vram']).replace('.', ',')) if g['vram'] else 'Speicher unbekannt'
    if g['vendor'] == 'nvidia' and g['vram'] >= 16:
        lvl, txt = 'gut', 'Deine Grafikkarte reicht für KI-Videos gut aus.'
    elif g['vendor'] == 'nvidia' and g['vram'] >= 12:
        lvl, txt = 'ok', 'Deine Grafikkarte reicht für kurze KI-Clips (kleines Modell).'
    elif g['vendor'] == 'nvidia' and g['vram'] >= 8:
        lvl, txt = 'knapp', 'Mit %s wird es knapp – nur sehr kleine, kurze Clips wären möglich.' % mem
    else:
        lvl, txt = 'nein', 'Für KI-Videos braucht es eine NVIDIA-Grafikkarte mit mindestens 12 GB – deine reicht dafür leider nicht.'
    return {'cards': GPU, 'text': 'Grafikkarte: %s · %s' % (g['name'], mem), 'video_ai': lvl, 'video_text': txt}


def song_key(audio):
    """Wiedererkennung eines Songs über Name + Größe (auch nach erneutem Hineinziehen)."""
    p = Path(audio['path'])
    try:
        size = p.stat().st_size
    except OSError:
        size = 0
    return '%s|%d' % (audio.get('name') or p.name, size)


UPDATE = {'t': 0, 'data': None}


def update_check():
    """Neueste Version auf GitHub (höchstens alle 6 Stunden nachsehen)."""
    if UPDATE['data'] is not None and time.time() - UPDATE['t'] < 6 * 3600:
        return UPDATE['data']
    import urllib.request
    res = {'current': VERSION, 'latest': '', 'newer': False, 'url': ''}
    try:
        req = urllib.request.Request('https://api.github.com/repos/Butchies/Butchies-ffmpeg-encode-studio/releases?per_page=20',
                                     headers={'User-Agent': 'ffmpeg_encode-Studio', 'Accept': 'application/vnd.github+json'})
        with urllib.request.urlopen(req, timeout=8) as r:
            rel = json.loads(r.read().decode('utf-8'))
        vers = []
        for x in rel:
            m = re.fullmatch(r'encoder-v(\d+)\.(\d+)\.(\d+)', x.get('tag_name') or '')
            if m and not x.get('draft'):
                vers.append((tuple(int(g) for g in m.groups()), x.get('html_url') or ''))
        if vers:
            best = max(vers)
            cur = tuple(int(g) for g in VERSION.split('.'))
            res.update(latest='.'.join(map(str, best[0])), newer=best[0] > cur, url=best[1])
    except Exception:  # noqa: BLE001
        res['error'] = 'offline'
    UPDATE.update(t=time.time(), data=res)
    return res


STYLE_NAMES = {'fx': {e[0]: e[1] for e in fx.EFFECTS}, 'cam': {c[0]: c[1] for c in fx.CAMS},
               'vizStyle': {v[0]: v[1] for v in viz.STYLES}}


def highlight_job(jid, audio, length, with_lyrics):
    """Beste Stelle für Shorts suchen (Hintergrund-Thread)."""
    j = HL_JOBS[jid]
    try:
        p = Path(audio['path'])
        key = (str(p), p.stat().st_mtime)
        dur = audio['info'].get('duration') or None
        j.update(phase='Song wird analysiert …', percent=5)
        if ('a',) + key not in HL_CACHE:
            HL_CACHE[('a',) + key] = highlight.analyse(FFMPEG, p, run, dur)
        A = HL_CACHE[('a',) + key]
        lines, lang = None, ''
        skey = song_key(audio)
        fixed = LEARN.song_lines(skey) if with_lyrics else None
        if fixed is not None and ('l',) + key not in HL_CACHE:   # vom Nutzer korrigierter Text -> direkt nehmen
            HL_CACHE[('l',) + key] = (fixed, '')
        if with_lyrics:
            if not LYRICS.model_ok() and ('l',) + key not in HL_CACHE:
                raise RuntimeError('Das Songtext-Modell ist noch nicht heruntergeladen.')
            if ('l',) + key not in HL_CACHE:
                j.update(phase='Songtext wird erkannt (das dauert etwas) …', percent=15)
                r = run([FFMPEG, '-v', 'error', '-nostdin', '-i', str(p), '-vn', '-ac', '1', '-ar', '16000', '-f', 's16le', '-'], timeout=600)
                if r.returncode:
                    raise RuntimeError('Song konnte nicht gelesen werden')
                import numpy as np
                pcm = np.frombuffer(r.stdout, np.int16).astype(np.float32) / 32768.0
                HL_CACHE[('l',) + key] = LYRICS.transcribe(pcm, lambda pc: j.update(percent=15 + int(pc * 0.8)),
                                                           hotwords=LEARN.hotwords())
            lines, lang = HL_CACHE[('l',) + key]
        j.update(phase='Vorschläge werden berechnet …', percent=96)
        model = LEARN.hl_model()
        sug = highlight.suggest(A, length, lines, model)
        j.update(state='fertig', percent=100, result={
            'suggestions': sug, 'bpm': round(float(A['bpm']), 1), 'lyrics': bool(with_lyrics),
            'lines': len(lines or []), 'language': lang, 'text': lines or [], 'fixed': fixed is not None,
            'learned': model['n'],
            'note': ('Kein Gesang erkannt – die Vorschläge beruhen nur auf dem Klang.' if with_lyrics and not lines else '')})
    except Exception as ex:  # noqa: BLE001
        j.update(state='fehler', error=str(ex) or 'Unbekannter Fehler')


def ai_info():
    if not mark or mark.cv2 is None:
        return {'tools': False, 'model': False, 'text': 'KI-Helfer nicht verfügbar (OpenCV fehlt)'}
    model = bool(SAM and SAM.available())
    return {'tools': True, 'model': model,
            'text': 'KI-Auswahl: MobileSAM (offline)' if model else 'KI-Auswahl: einfache Erkennung (KI-Modell nicht gefunden)',
            'depth': bool(DEPTH and DEPTH.available())}


# ---------- Vorlagen & Projekte ----------
PROJ_EXT = '.fesproj'


def project_dir():
    return Path(load_config().get('outdir') or default_outdir()) / 'Projekte'


def list_projects():
    d = project_dir()
    out = []
    if d.is_dir():
        for f in sorted(d.glob('*' + PROJ_EXT), key=lambda p: p.stat().st_mtime, reverse=True):
            out.append({'name': f.stem, 'path': str(f), 'size': f.stat().st_size, 'mtime': f.stat().st_mtime})
    return out


def save_project(name, settings, audio_tok, image_tok):
    a, i = STAGED.get(audio_tok or ''), STAGED.get(image_tok or '')
    if not a or not i:
        raise ValueError('Für ein Projekt müssen Song und Bild geladen sein.')
    d = project_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / (safe_name(name) + PROJ_EXT)
    meta = {'app': APP_NAME, 'version': VERSION, 'settings': clean_settings(settings),
            'audio': {'name': a['name'], 'file': 'song' + Path(a['path']).suffix},
            'image': {'name': i['name'], 'file': 'bild' + Path(i['path']).suffix}, 'saved': time.time()}
    tmp = path.with_suffix('.tmp')
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_STORED) as z:
        z.writestr('projekt.json', json.dumps(meta, ensure_ascii=False, indent=1))
        z.write(a['path'], meta['audio']['file'])
        z.write(i['path'], meta['image']['file'])
        mp = MASKS.get(meta['settings'].get('vizMask') or '')
        if meta['settings'].get('vizShape') == 'mask' and mp and Path(mp).is_file():
            z.write(mp, 'maske.png')
        mp = MASKS.get(meta['settings'].get('fxMask') or '')
        if meta['settings'].get('fxArea') == 'mask' and mp and Path(mp).is_file():
            z.write(mp, 'effekt-maske.png')
        mp = MASKS.get(meta['settings'].get('aiMask') or '')
        if meta['settings'].get('aiArea') == 'mask' and mp and Path(mp).is_file():
            z.write(mp, 'ki-maske.png')
    tmp.replace(path)
    return path


def open_project(path):
    """Projektdatei entpacken: Einstellungen + Song + Bild werden wie hineingezogen geladen."""
    try:
        z = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile):
        raise ValueError('Das ist keine gültige Projektdatei.')
    with z:
        try:
            meta = json.loads(z.read('projekt.json').decode('utf-8'))
        except (KeyError, ValueError):
            raise ValueError('In der Projektdatei fehlen die Einstellungen.')
        out = {'settings': dict(meta.get('settings') or {}), 'name': Path(path).stem}
        for fn, key in (('maske.png', 'vizMask'), ('effekt-maske.png', 'fxMask'), ('ki-maske.png', 'aiMask')):
            if fn in z.namelist():
                tok = secrets.token_hex(8)
                dest = STAGE / ('mask-%s.png' % tok)
                with z.open(fn) as src, open(dest, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
                MASKS[tok] = str(dest)
                out['settings'][key] = tok
        out['settings'] = clean_settings(out['settings'])
        for kind in ('audio', 'image'):
            ent = meta.get(kind) or {}
            fn = ent.get('file', '')
            if fn not in z.namelist() or '/' in fn or '\\' in fn:
                raise ValueError('In der Projektdatei fehlt %s.' % ('der Song' if kind == 'audio' else 'das Bild'))
            tok = secrets.token_hex(8)
            dest = STAGE / (tok + Path(fn).suffix.lower()[:8])
            with z.open(fn) as src, open(dest, 'wb') as dst:
                shutil.copyfileobj(src, dst)
            out[kind] = public_entry(tok, stage_file(dest, safe_name(ent.get('name') or fn), kind, tok))
    return out


# ---------- lokaler Webserver für die Oberfläche ----------
class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.0'

    def log_message(self, *a):
        pass

    def send_json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def local_only(self):
        host = (self.headers.get('Host') or '').split(':')[0]
        origin = self.headers.get('Origin')
        if host not in ('127.0.0.1', 'localhost') or (origin and urllib.parse.urlsplit(origin).hostname not in ('127.0.0.1', 'localhost')):
            self.send_json(403, {'error': 'Nicht erlaubt'})
            return False
        if self.command == 'POST' and self.headers.get('X-Studio') != TOKEN:
            self.send_json(403, {'error': 'Nicht erlaubt'})
            return False
        return True

    def body_json(self):
        n = int(self.headers.get('Content-Length') or 0)
        return json.loads(self.rfile.read(n).decode('utf-8') or '{}') if n else {}

    def send_file(self, path, ctype=None):
        path = Path(path)
        size = path.stat().st_size
        ctype = ctype or mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        rng = self.headers.get('Range')
        start, end = 0, size - 1
        m = re.match(r'bytes=(\d*)-(\d*)', rng or '')
        if m and size:
            if m.group(1):
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else size - 1
            else:
                start = max(size - int(m.group(2) or 0), 0)
            end = min(end, size - 1)
            if start > end:
                self.send_response(416)
                self.send_header('Content-Range', 'bytes */%d' % size)
                self.end_headers()
                return
            self.send_response(206)
            self.send_header('Content-Range', 'bytes %d-%d/%d' % (start, end, size))
        else:
            self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(end - start + 1 if size else 0))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        with open(path, 'rb') as f:
            f.seek(start)
            left = end - start + 1 if size else 0
            while left > 0:
                chunk = f.read(min(1 << 20, left))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return
                left -= len(chunk)

    def do_GET(self):
        if not self.local_only():
            return
        u = urllib.parse.urlsplit(self.path)
        path = u.path
        LAST_PING[0] = time.time()
        if path == '/api/lyrics/status':
            return self.send_json(200, LYRICS.status())
        m = re.fullmatch(r'/api/highlight/([0-9a-f]+)', path)
        if m:
            j = HL_JOBS.get(m.group(1))
            return self.send_json(200 if j else 404, j or {'error': 'Unbekannte Suche'})
        if path == '/api/ai/status':
            return self.send_json(200, AIV.status())
        m = re.fullmatch(r'/api/ai/job/([0-9a-f]+)', path)
        if m:
            v = AIV.view(m.group(1))
            return self.send_json(200, v) if v else self.send_json(404, {'error': 'Unbekannt'})
        if path == '/api/ai/video':
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            p = AIV.clip_path((q.get('p') or [''])[0])
            return self.send_file(p, 'video/mp4') if p else self.send_json(404, {'error': 'Nicht gefunden'})
        if path == '/api/learn':
            return self.send_json(200, LEARN.summary(DEFAULTS, STYLE_NAMES))
        if path == '/api/learn/style':
            return self.send_json(200, {'values': LEARN.style_suggest(DEFAULTS)})
        if path == '/api/update':
            return self.send_json(200, update_check())
        if path == '/api/info':
            conf = load_config()
            return self.send_json(200, {
                'version': VERSION, 'name': APP_NAME, 'ffmpeg': bool(FFMPEG), 'ffprobe': bool(FFPROBE), 'website': WEBSITE,
                'ffmpeg_path': FFMPEG or '', 'encoders': {k: {'name': v[1], 'ok': HW[k]} for k, v in ENCODERS.items()},
                'hw_done': HW_DONE.is_set(), 'auto_enc': resolve_enc('auto'),
                'transitions': [{'group': g, 'id': i, 'name': n} for g, i, n in TRANSITIONS],
                'vizStyles': [{'id': i, 'name': n, 'short': k} for i, n, k in viz.STYLES],
                'presets': conf.get('presets') or [], 'ai': ai_info(), 'gpu': gpu_view(),
                'lyrics': LYRICS.status(), 'short_lengths': list(highlight.LENGTHS),
                'ai_waves': [{'id': i, 'name': n} for i, n in viz.AI_WAVES],
                'fx': {'effects': [{'id': i, 'name': n, 'short': k, 'desc': d} for i, n, k, d in fx.EFFECTS],
                       'cams': [{'id': i, 'name': n, 'desc': d} for i, n, d in fx.CAMS],
                       'tools': fx.cv2 is not None, 'depth': bool(DEPTH and DEPTH.available())},
                'formats': {k: {'name': v[0], 'w': v[1], 'h': v[2], 'vertical': v[3]} for k, v in FORMATS.items()},
                'outdir': conf.get('outdir') or default_outdir(), 'theme': conf.get('theme') or 'gold',
                'settings': clean_settings(conf.get('settings')), 'intro': conf.get('intro', True)})
        m = re.fullmatch(r'/api/(maskimg|maskfile)/([0-9a-f]+)', path)
        if m:
            p = SEGS.get(m.group(2)) if m.group(1) == 'maskimg' else MASKS.get(m.group(2))
            return self.send_file(p, 'image/png') if p and Path(p).is_file() else self.send_json(404, {'error': 'Keine Maske'})
        if path == '/api/projects':
            return self.send_json(200, {'projects': list_projects(), 'folder': str(project_dir())})
        if path == '/api/presets':
            return self.send_json(200, {'presets': load_config().get('presets') or []})
        if path == '/api/ping':
            return self.send_json(200, {'ok': True, 'busy': busy()})
        if path == '/api/jobs':
            return self.send_json(200, {'jobs': [job_view(JOBS[i]) for i in QUEUE]})
        m = re.fullmatch(r'/api/job/([0-9a-f]+)', path)
        if m:
            j = JOBS.get(m.group(1))
            return self.send_json(200, job_view(j)) if j else self.send_json(404, {'error': 'Unbekannt'})
        m = re.fullmatch(r'/api/(file|preview|still|clip)/([\w-]+)', path)
        if m:
            kind, tok = m.groups()
            if kind == 'clip':
                p = STAGE / ('clip-%s.mp4' % tok)
                return self.send_file(p, 'video/mp4') if p.is_file() else self.send_json(404, {'error': 'Keine Vorschau'})
            if kind == 'still':
                p = STAGE / ('preview-%s.jpg' % tok)
                return self.send_file(p, 'image/jpeg') if p.is_file() else self.send_json(404, {'error': 'Keine Vorschau'})
            st = STAGED.get(tok)
            if not st:
                return self.send_json(404, {'error': 'Unbekannt'})
            if kind == 'preview':
                p = st.get('preview')
                return self.send_file(p, 'image/jpeg') if p and Path(p).is_file() else self.send_json(404, {'error': 'Keine Vorschau'})
            return self.send_file(st['path'])
        # statische Dateien der Oberfläche
        rel = 'index.html' if path in ('/', '') else urllib.parse.unquote(path.lstrip('/'))
        f = (UI / rel).resolve()
        if UI.resolve() not in f.parents or not f.is_file():
            return self.send_json(404, {'error': 'Nicht gefunden'})
        data = f.read_bytes()
        ctype = mimetypes.guess_type(f.name)[0] or 'application/octet-stream'
        if f.suffix == '.woff2':
            ctype = 'font/woff2'
        if f.suffix in ('.js', '.css', '.html', '.svg'):
            ctype += '; charset=utf-8'
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if not self.local_only():
            return
        u = urllib.parse.urlsplit(self.path)
        path = u.path
        LAST_PING[0] = time.time()
        try:
            if path == '/api/stage':
                q = urllib.parse.parse_qs(u.query)
                name = safe_name(Path(q.get('name', ['datei'])[0]).name)
                kind = q.get('kind', [''])[0]
                n = int(self.headers.get('Content-Length') or 0)
                if n <= 0 or n > 4 * 1024 ** 3:
                    return self.send_json(400, {'error': 'Datei ist leer oder zu groß.'})
                tok = secrets.token_hex(8)
                dest = STAGE / ('%s%s' % (tok, Path(name).suffix.lower()[:8]))
                with open(dest, 'wb') as f:
                    left = n
                    while left > 0:
                        chunk = self.rfile.read(min(1 << 20, left))
                        if not chunk:
                            break
                        f.write(chunk)
                        left -= len(chunk)
                try:
                    entry = stage_file(dest, name, kind, tok)
                except ValueError as e:
                    return self.send_json(400, {'error': str(e)})
                return self.send_json(200, public_entry(tok, entry))

            if path == '/api/mark/mask':
                if not mark:
                    return self.send_json(400, {'error': 'Markieren ist nicht verfügbar (OpenCV fehlt).'})
                n = int(self.headers.get('Content-Length') or 0)
                if n <= 0 or n > 64 * 1024 ** 2:
                    return self.send_json(400, {'error': 'Maske ist leer oder zu groß.'})
                tok = secrets.token_hex(8)
                dest = STAGE / ('mask-%s.png' % tok)
                bb = mark.store_mask(self.rfile.read(n), dest)
                if not bb:
                    dest.unlink(missing_ok=True)
                    return self.send_json(200, {'token': '', 'bbox': None})
                MASKS[tok] = str(dest)
                return self.send_json(200, {'token': tok, 'bbox': bb})
            if path == '/api/project/open':
                n = int(self.headers.get('Content-Length') or 0)
                if n <= 0 or n > 4 * 1024 ** 3:
                    return self.send_json(400, {'error': 'Datei ist leer oder zu groß.'})
                tmp = STAGE / ('upload-%s%s' % (secrets.token_hex(6), PROJ_EXT))
                with open(tmp, 'wb') as f:
                    left = n
                    while left > 0:
                        chunk = self.rfile.read(min(1 << 20, left))
                        if not chunk:
                            break
                        f.write(chunk)
                        left -= len(chunk)
                try:
                    return self.send_json(200, open_project(tmp))
                finally:
                    tmp.unlink(missing_ok=True)
            data = self.body_json()
            if path == '/api/lyrics/download':
                if not LYRICS.lib_ok():
                    return self.send_json(400, {'error': 'Die Songtext-Erkennung ist in diesem Programm nicht enthalten.'})
                LYRICS.download()
                return self.send_json(200, LYRICS.status())
            if path == '/api/ai/download':
                AIV.download()
                return self.send_json(200, AIV.status())
            if path == '/api/ai/remove':
                AIV.remove()
                return self.send_json(200, AIV.status())
            if path == '/api/ai/cancel':
                AIV.cancel(str(data.get('id') or ''))
                return self.send_json(200, {'ok': True})
            if path in ('/api/ai/info', '/api/ai/start'):
                img = STAGED.get(data.get('image') or '')
                if not img:
                    return self.send_json(400, {'error': 'Bitte zuerst ein Bild laden.'})
                st = clean_settings(data.get('settings'))
                key = ai_key(img, st)
                length = ai_length(st, STAGED.get(data.get('audio') or ''))
                if path == '/api/ai/info':
                    return self.send_json(200, {'key': key, 'have': AIV.clips(key), 'length': length,
                                                'estimate': AIV.estimate(st['aiQual'], length),
                                                'estimate_variants': AIV.estimate(st['aiQual'], 1)})
                kind = 'full' if data.get('kind') == 'full' else 'variants'
                try:
                    jid = AIV.start(kind, ai_still(img, st), {
                        'key': key, 'quality': st['aiQual'], 'motion': st['aiMotion'], 'text': st['aiText'], 'fmt': st['fmt'],
                        'vertical': bool(FORMATS[st['fmt']][3]), 'seed': int(data.get('seed') or 11), 'length': length})
                except RuntimeError as ex:
                    return self.send_json(400, {'error': str(ex)})
                return self.send_json(200, {'id': jid, 'key': key})
            if path == '/api/learn/hl':
                LEARN.hl_pick(data.get('kind'), data.get('feat'))
                return self.send_json(200, {'ok': True})
            if path == '/api/learn/reset':
                LEARN.reset(data.get('part'))
                return self.send_json(200, LEARN.summary(DEFAULTS, STYLE_NAMES))
            if path == '/api/learn/lyrics':
                a = STAGED.get(data.get('audio') or '')
                if not a:
                    return self.send_json(400, {'error': 'Der Song ist nicht mehr geladen.'})
                new = []
                for l in data.get('lines') or []:
                    try:
                        t = str(l.get('text', '')).strip()[:300]
                        if t:
                            new.append({'start': round(float(l['start']), 2), 'end': round(float(l['end']), 2), 'text': t})
                    except (KeyError, TypeError, ValueError):
                        continue
                p = Path(a['path'])
                key = ('l', str(p), p.stat().st_mtime)
                old = (HL_CACHE.get(key) or (LEARN.song_lines(song_key(a)) or [], ''))[0]
                words = LEARN.lyrics_fix(song_key(a), old, new)
                HL_CACHE[key] = (new, (HL_CACHE.get(key) or ([], ''))[1])
                return self.send_json(200, {'learned': words, 'total': len(LEARN.hotwords(10000))})
            if path == '/api/highlight':
                a = STAGED.get(data.get('audio') or '')
                if not a or a.get('kind') != 'audio':
                    return self.send_json(400, {'error': 'Zuerst einen Song hineinziehen.'})
                if highlight.np is None:
                    return self.send_json(400, {'error': 'Die Song-Analyse ist nicht verfügbar (numpy fehlt).'})
                length = int(data.get('length') or 60)
                length = length if length in highlight.LENGTHS else 60
                jid = secrets.token_hex(6)
                HL_JOBS[jid] = {'state': 'läuft', 'percent': 0, 'phase': 'Start …', 'result': None, 'error': ''}
                threading.Thread(target=highlight_job, args=(jid, a, length, bool(data.get('lyrics'))), daemon=True).start()
                return self.send_json(200, {'id': jid})
            if path in ('/api/mark/segment', '/api/mark/refine', '/api/mark/suggest'):
                if not mark or mark.cv2 is None:
                    return self.send_json(400, {'error': 'KI-Helfer sind nicht verfügbar (OpenCV fehlt).'})
                st = clean_settings(data.get('settings'))
                img, key = analysis_image(data.get('image'), st)
                if path == '/api/mark/suggest':
                    return self.send_json(200, mark.suggest(img, st['vizW'], st['vizH']))
                if path == '/api/mark/refine':
                    pts = data.get('points') or []
                    if len(pts) < 2:
                        return self.send_json(400, {'error': 'Zuerst eine Linie zeichnen.'})
                    return self.send_json(200, {'points': mark.refine_line(img, pts, bool(data.get('closed')))})
                bgr = mark.imread(img)
                h, w = bgr.shape[:2]
                pts = [[float(q[0]) * w, float(q[1]) * h] for q in (data.get('points') or [])]
                labels = [1 if (len(q) < 3 or q[2]) else 0 for q in (data.get('points') or [])]
                box = data.get('box')
                box = [box[0] * w, box[1] * h, box[2] * w, box[3] * h] if box else None
                if not pts and not box:
                    return self.send_json(400, {'error': 'Zuerst auf das Motiv klicken.'})
                t0 = time.time()
                msk, method = mark.segment(SAM, key, img, pts, labels, box)
                sid = secrets.token_hex(6)
                out = STAGE / ('seg-%s.png' % sid)
                mark.imwrite(out, msk)
                SEGS[sid] = str(out)
                return self.send_json(200, {'url': '/api/maskimg/' + sid, 'method': method, 'bbox': mark.bbox(msk),
                                            'seconds': round(time.time() - t0, 2), 'note': (SAM.error if SAM else '')[:200]})
            if path == '/api/presets/save':
                raw_name = str(data.get('name') or '').strip()
                name = safe_name(raw_name)[:60] if raw_name else ''
                if not name:
                    return self.send_json(400, {'error': 'Bitte einen Namen eingeben.'})
                conf = load_config()
                lst = [p for p in (conf.get('presets') or []) if p.get('name') != name]
                ps = clean_settings(data.get('settings'))
                ps.update({k: viz.DEFAULTS[k] for k in viz.MARK_KEYS})
                ps.update({k: fx.DEFAULTS[k] for k in fx.MARK_KEYS})       # Markierung gehört nur zum Video, nicht zur Vorlage
                lst.append({'name': name, 'settings': ps, 'saved': time.time()})
                conf['presets'] = lst[-60:]
                save_config(conf)
                return self.send_json(200, {'presets': conf['presets']})
            if path == '/api/presets/delete':
                conf = load_config()
                conf['presets'] = [p for p in (conf.get('presets') or []) if p.get('name') != data.get('name')]
                save_config(conf)
                return self.send_json(200, {'presets': conf['presets']})
            if path == '/api/project/save':
                name = str(data.get('name') or '').strip()
                if not name:
                    return self.send_json(400, {'error': 'Bitte einen Namen eingeben.'})
                pth = save_project(name, data.get('settings'), data.get('audio'), data.get('image'))
                return self.send_json(200, {'path': str(pth), 'projects': list_projects()})
            if path == '/api/project/load':
                pth = Path(str(data.get('path') or ''))
                if pth.parent.resolve() != project_dir().resolve() or pth.suffix != PROJ_EXT or not pth.is_file():
                    return self.send_json(400, {'error': 'Projekt nicht gefunden.'})
                return self.send_json(200, open_project(pth))
            if path == '/api/project/delete':
                pth = Path(str(data.get('path') or ''))
                if pth.parent.resolve() == project_dir().resolve() and pth.suffix == PROJ_EXT and pth.is_file():
                    pth.unlink()
                return self.send_json(200, {'projects': list_projects()})
            if path == '/api/command':
                s = clean_settings(data.get('settings'))
                a = STAGED.get(data.get('audio') or '')
                i = STAGED.get(data.get('image') or '')
                adur = a['info'].get('duration') if a else None
                out = data.get('outname') or output_name(s, a['name'] if a else 'song.mp3')
                text, meta = command_text(s, a['name'] if a else '', i['name'] if i else '', out, adur)
                return self.send_json(200, {'command': text, 'meta': meta, 'outname': output_name(s, a['name'] if a else 'song.mp3')})
            if path == '/api/still':
                s = clean_settings(data.get('settings'))
                i = STAGED.get(data.get('image') or '')
                if not i:
                    return self.send_json(400, {'error': 'Kein Bild'})
                key = secrets.token_hex(6)
                out = STAGE / ('preview-%s.jpg' % key)
                _, w, h, _ = FORMATS[s['fmt']]
                scale = 960 / max(w, h)
                r = run(still_command(i['path'], out, s, scale), timeout=120)
                if r.returncode or not out.is_file():
                    return self.send_json(500, {'error': 'Vorschau fehlgeschlagen'})
                for old in STAGE.glob('preview-*.jpg'):
                    if old != out and time.time() - old.stat().st_mtime > 30:
                        old.unlink(missing_ok=True)
                return self.send_json(200, {'url': '/api/still/' + key})
            if path == '/api/trans-preview':
                s = clean_settings(data.get('settings'))
                i = STAGED.get(data.get('image') or '')
                if not i:
                    return self.send_json(400, {'error': 'Zuerst ein Bild hineinziehen'})
                key = secrets.token_hex(6)
                for old in STAGE.glob('clip-*.mp4'):
                    old.unlink(missing_ok=True)
                if not transition_preview(i['path'], STAGE / ('clip-%s.mp4' % key), s, 'out' if data.get('which') == 'out' else 'in'):
                    return self.send_json(500, {'error': 'Vorschau fehlgeschlagen'})
                return self.send_json(200, {'url': '/api/clip/' + key})
            if path == '/api/viz-preview':
                s = clean_settings(data.get('settings'))
                if not s['viz'] and not fx.active(s):
                    s['viz'] = True
                a, i = STAGED.get(data.get('audio') or ''), STAGED.get(data.get('image') or '')
                if not a or not i:
                    return self.send_json(400, {'error': 'Für die Vorschau zuerst Song und Bild hineinziehen'})
                key = secrets.token_hex(6)
                for old in STAGE.glob('clip-*.mp4'):
                    old.unlink(missing_ok=True)
                ok, err = viz_preview(a, i['path'], STAGE / ('clip-%s.mp4' % key), s)
                if not ok:
                    return self.send_json(500, {'error': 'Vorschau fehlgeschlagen: ' + err})
                return self.send_json(200, {'url': '/api/clip/' + key})
            if path == '/api/quit':
                stop_all()
                if not NATIVE[0]:
                    threading.Timer(0.6, lambda: (AIV.shutdown(), os._exit(0))).start()
                return self.send_json(200, {'ok': True})
            if path == '/api/encode':
                conf = load_config()
                conf['settings'] = clean_settings(data.get('settings'))
                if data.get('hl_adjust'):
                    LEARN.hl_adjust(data['hl_adjust'].get('ds'), data['hl_adjust'].get('de'))
                if data.get('outdir'):
                    conf['outdir'] = data['outdir']
                save_config(conf)
                job = new_job(data.get('settings'), data.get('audio'), data.get('image'), data.get('outdir'), data.get('outname'))
                LEARN.style_observe(job['settings'])
                return self.send_json(200, job_view(job))
            if path == '/api/cancel':
                cancel_job(data.get('id', ''))
                return self.send_json(200, {'ok': True})
            if path == '/api/clear-done':
                with QLOCK:
                    for jid in [i for i in QUEUE if JOBS[i]['state'] in ('fertig', 'fehler', 'abgebrochen')]:
                        QUEUE.remove(jid)
                        JOBS.pop(jid, None)
                return self.send_json(200, {'ok': True})
            if path == '/api/unstage':
                st = STAGED.pop(data.get('token', ''), None)
                if st and not any(j['state'] in ('läuft', 'wartet') and st in (j['audio'], j['image']) for j in JOBS.values()):
                    Path(st['path']).unlink(missing_ok=True)
                return self.send_json(200, {'ok': True})
            if path == '/api/config':
                conf = load_config()
                for k in ('theme', 'outdir', 'intro'):
                    if k in data:
                        conf[k] = data[k]
                if 'settings' in data:
                    conf['settings'] = clean_settings(data['settings'])
                save_config(conf)
                return self.send_json(200, {'ok': True})
            if path == '/api/show':
                target = data.get('path') or load_config().get('outdir') or default_outdir()
                Path(target if not Path(target).suffix else Path(target).parent).mkdir(parents=True, exist_ok=True)
                show_in_folder(target)
                return self.send_json(200, {'ok': True})
            if path == '/api/open-url':
                url = data.get('url', '')
                if url.startswith('https://'):
                    webbrowser.open(url)
                return self.send_json(200, {'ok': True})
            return self.send_json(404, {'error': 'Unbekannt'})
        except ValueError as e:
            return self.send_json(400, {'error': str(e)})
        except Exception as e:  # noqa: BLE001
            return self.send_json(500, {'error': 'Interner Fehler: %s' % e})


# ---------- Programmfenster ----------
def open_window(url):
    """Ersatz ohne WebView2: App-Fenster von Edge oder Chrome."""
    candidates = []
    if os.name == 'nt':
        for base in (os.environ.get('PROGRAMFILES(X86)'), os.environ.get('PROGRAMFILES'), os.environ.get('LOCALAPPDATA')):
            if base:
                candidates += [Path(base) / 'Microsoft/Edge/Application/msedge.exe', Path(base) / 'Google/Chrome/Application/chrome.exe']
    else:
        candidates += [Path(p) for p in ('/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/microsoft-edge')]
    for exe in candidates:
        if exe.is_file():
            try:
                return subprocess.Popen([str(exe), '--app=' + url, '--start-maximized', '--user-data-dir=' + str(HOME / 'window'),
                                         '--no-first-run', '--no-default-browser-check'])
            except OSError:
                pass
    webbrowser.open(url)
    return None


class WinFrame:
    """Verschiebt, vergrößert und maximiert das rahmenlose Fenster über die Windows-API (wie im Butchies Uploader)."""

    def __init__(self):
        self.win = None
        self.hwnd = 0
        self.saved = None
        self.full = None
        self.busy = False

    def _user32(self):
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32
        u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        u.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
        return ctypes, wintypes, u

    def handle(self):
        if self.hwnd:
            return self.hwnd
        try:
            self.hwnd = int(self.win.native.Handle.ToInt64())
        except Exception:  # noqa: BLE001
            ctypes, wintypes, u = self._user32()
            self.hwnd = u.FindWindowW(None, APP_NAME) or 0
        return self.hwnd

    def _rect(self):
        ctypes, wintypes, u = self._user32()
        r = wintypes.RECT()
        u.GetWindowRect(self.handle(), ctypes.byref(r))
        return [r.left, r.top, r.right - r.left, r.bottom - r.top]

    def _set(self, x, y, w, h):
        ctypes, wintypes, u = self._user32()
        u.SetWindowPos(self.handle(), 0, int(x), int(y), int(w), int(h), 0x0004 | 0x0010)

    def _cursor(self):
        ctypes, wintypes, u = self._user32()
        pt = wintypes.POINT()
        u.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y

    def _button_down(self):
        ctypes, wintypes, u = self._user32()
        vk = 0x02 if u.GetSystemMetrics(23) else 0x01
        return bool(u.GetAsyncKeyState(vk) & 0x8000)

    def _work_area(self, full=False):
        ctypes, wintypes, u = self._user32()

        class MONITORINFO(ctypes.Structure):
            _fields_ = [('cbSize', wintypes.DWORD), ('rcMonitor', wintypes.RECT), ('rcWork', wintypes.RECT), ('dwFlags', wintypes.DWORD)]
        u.MonitorFromWindow.restype = wintypes.HANDLE
        u.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        u.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFO)]
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        u.GetMonitorInfoW(u.MonitorFromWindow(self.handle(), 2), ctypes.byref(mi))
        w = mi.rcMonitor if full else mi.rcWork
        return [w.left, w.top, w.right - w.left, w.bottom - w.top]

    def _scale(self):
        try:
            ctypes, wintypes, u = self._user32()
            return (u.GetDpiForWindow(self.handle()) or 96) / 96
        except Exception:  # noqa: BLE001
            return 1.0

    def _loop(self, fn):
        if self.busy:
            return
        self.busy = True

        def go():
            try:
                for _ in range(20):
                    if self._button_down():
                        break
                    time.sleep(0.01)
                while self._button_down():
                    fn()
                    time.sleep(0.008)
            except Exception:  # noqa: BLE001
                pass
            finally:
                self.busy = False
        threading.Thread(target=go, daemon=True).start()

    def drag(self):
        cx, cy = self._cursor()
        x, y, w, h = self._rect()
        if self.saved:
            rx = (cx - x) / max(w, 1)
            w, h = self.saved[2], self.saved[3]
            x, y = cx - int(w * rx), cy - 20
            self.saved = None
            self._set(x, y, w, h)
        ox, oy = cx - x, cy - y

        def step():
            px, py = self._cursor()
            self._set(px - ox, py - oy, w, h)
        self._loop(step)

    def resize(self, edge):
        if self.saved:
            return
        cx, cy = self._cursor()
        x, y, w, h = self._rect()
        s = self._scale()
        mw, mh = int(960 * s), int(620 * s)

        def step():
            px, py = self._cursor()
            dx, dy = px - cx, py - cy
            nx, ny, nw, nh = x, y, w, h
            if 'r' in edge:
                nw = max(mw, w + dx)
            if 'b' in edge:
                nh = max(mh, h + dy)
            if 'l' in edge:
                nw = max(mw, w - dx)
                nx = x + w - nw
            if 't' in edge:
                nh = max(mh, h - dy)
                ny = y + h - nh
            self._set(nx, ny, nw, nh)
        self._loop(step)

    def toggle_max(self):
        if self.saved:
            self._set(*self.saved)
            self.saved = None
            return False
        self.saved = self._rect()
        self._set(*self._work_area())
        return True

    def is_max(self):
        return bool(self.saved)

    def _monitor(self):
        ctypes, wintypes, u = self._user32()
        u.MonitorFromWindow.restype = wintypes.HANDLE
        u.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        return u.MonitorFromWindow(self.handle(), 2)

    def monitors(self):
        """Alle Bildschirme als [(links, oben, breite, höhe), …] (ganze Fläche)."""
        ctypes, wintypes, u = self._user32()
        out = []
        proc = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HANDLE, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

        def cb(hmon, hdc, rect, data):
            r = rect.contents
            out.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
            return 1
        u.EnumDisplayMonitors(None, None, proc(cb), 0)
        return sorted(out)

    def _place(self, x, y, w, h):
        ctypes, wintypes, u = self._user32()
        # HWND_TOP (kein „immer im Vordergrund“): Fenster vom 2. Monitor dürfen darüber, Ziehen & Ablegen geht weiter
        u.SetWindowPos(self.handle(), 0, int(x), int(y), int(w), int(h), 0x0010 | 0x0040)

    def toggle_full(self):
        """F11: echtes Vollbild über den ganzen Monitor (ohne Rahmen und Taskleiste), aber NICHT „immer im Vordergrund“ –
        so kann man mit zwei Monitoren weiter Fenster und Dateien hin- und herziehen. Nochmal F11 (oder Esc) = zurück."""
        if self.full:
            rect, mon = self.full
            self.full = None
            if self._monitor() != mon:                      # inzwischen anderer Monitor: dort maximiert
                self.saved = self.saved or rect
                self._place(*self._work_area())
            else:
                self._place(*rect)
            return False
        self.full = (self._rect(), self._monitor())
        self._place(*self._work_area(True))
        return True

    def fit_full(self):
        """Im Vollbild: an den Monitor anpassen, auf dem das Fenster gerade ist (z. B. nach Win+Umschalt+Pfeil)."""
        if self.full and self._rect() != self._work_area(True):
            self._place(*self._work_area(True))
        return bool(self.full)

    def next_monitor(self):
        """Fenster (Vollbild oder maximiert) auf den nächsten Monitor schieben."""
        mons = self.monitors()
        if len(mons) < 2:
            return False
        x, y, w, h = self._rect()
        cx, cy = x + w // 2, y + h // 2
        cur = next((i for i, m in enumerate(mons) if m[0] <= cx < m[0] + m[2] and m[1] <= cy < m[1] + m[3]), 0)
        nx, ny, nw, nh = mons[(cur + 1) % len(mons)]
        # erst grob hinschieben, dann an Monitor bzw. Arbeitsfläche anpassen
        self._place(nx + 40, ny + 40, min(w, nw - 80), min(h, nh - 80))
        if self.full:
            self.full = (self.full[0], self._monitor())
            self._place(*self._work_area(True))
        elif self.saved:
            self._place(*self._work_area())
        return True

    def minimize(self):
        self.win.minimize()

    def close(self):
        stop_all()
        self.win.destroy()


def native_window(url):
    if os.name != 'nt' and '--native' not in sys.argv:
        return False
    try:
        import webview
    except Exception:  # noqa: BLE001
        return False
    frame = WinFrame()
    NATIVE[0] = True

    class Api:
        def minimize(self):
            frame.minimize()

        def toggle_max(self):
            return frame.toggle_max()

        def is_max(self):
            return frame.is_max()

        def drag(self):
            frame.drag()

        def resize(self, edge):
            frame.resize(str(edge))

        def close(self):
            frame.close()

        def toggle_fullscreen(self):
            try:
                return frame.toggle_full()
            except Exception:  # noqa: BLE001
                return False

        def is_full(self):
            return bool(frame.full)

        def fit_full(self):
            try:
                return frame.fit_full()
            except Exception:  # noqa: BLE001
                return False

        def next_monitor(self):
            try:
                return frame.next_monitor()
            except Exception:  # noqa: BLE001
                return False

        def monitor_count(self):
            try:
                return len(frame.monitors())
            except Exception:  # noqa: BLE001
                return 1

        def pick_folder(self, start=''):
            try:
                res = frame.win.create_file_dialog(webview.FOLDER_DIALOG, directory=start or '')
            except Exception:  # noqa: BLE001
                return ''
            return res[0] if res else ''

    # Programm startet immer bildschirmfüllend (maximiert, Taskleiste bleibt sichtbar); F11 = echtes Vollbild
    win = webview.create_window(APP_NAME, url, width=1400, height=920, min_size=(960, 620), frameless=True, easy_drag=False,
                                background_color='#0d0a05', js_api=Api(), text_select=True)
    frame.win = win

    def fit():
        time.sleep(0.4)
        try:
            if not frame.is_max():
                frame.toggle_max()
        except Exception:  # noqa: BLE001
            pass
    if os.name == 'nt':
        win.events.shown += lambda *a: threading.Thread(target=fit, daemon=True).start()
    try:
        webview.start(gui='edgechromium' if os.name == 'nt' else None, private_mode=False, storage_path=str(HOME / 'webview'))
    except Exception:  # noqa: BLE001
        return False
    return True


def main():
    HOME.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=hw_check, daemon=True).start()
    threading.Thread(target=detect_gpus, daemon=True).start()
    threading.Thread(target=worker, daemon=True).start()
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    url = 'http://127.0.0.1:%d/#%s' % (server.server_address[1], TOKEN)
    print('%s %s läuft: %s' % (APP_NAME, VERSION, url if '--no-window' in sys.argv else url.split('#')[0]), flush=True)
    print('FFmpeg: %s' % (FFMPEG or 'NICHT GEFUNDEN'), flush=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    if '--check-native' in sys.argv:
        import webview  # noqa: F401
        if os.name == 'nt':
            from webview.platforms import winforms, edgechromium  # noqa: F401
        print('native ok', flush=True)
        return
    try:
        if '--no-window' not in sys.argv:
            if native_window(url):
                stop_all()
                time.sleep(0.5)
                return
            open_window(url)
        while True:
            time.sleep(5)
            if '--no-window' not in sys.argv and not busy() and time.time() - LAST_PING[0] > 40:
                break
    except KeyboardInterrupt:
        pass
    finally:
        stop_all()
        time.sleep(0.3)
        shutil.rmtree(STAGE, ignore_errors=True)


if __name__ == '__main__':
    main()

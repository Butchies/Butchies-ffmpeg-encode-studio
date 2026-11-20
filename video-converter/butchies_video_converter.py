"""Butchies Video Converter AI – wandelt Videos mit KI-Hilfe in H.264 / H.265 um.

Eigenständiges Programm (liegt nur im selben Repo wie das ffmpeg_encode Studio).
Technik: Python-Standardbibliothek + FFmpeg/FFprobe (vom Installer mitgeliefert). Oberfläche in einem
rahmenlosen Programmfenster (WebView2 über pywebview); ohne WebView2 öffnet sich ein Edge/Chrome-App-Fenster.
"""
import concurrent.futures, hashlib, json, mimetypes, os, re, secrets, shutil, signal, subprocess, sys, tempfile, threading, time
import urllib.parse, urllib.request, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

APP_NAME = 'Butchies Video Converter'
VERSION = '1.1.7'
FROZEN = getattr(sys, 'frozen', False)
BASE = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
UI = BASE / 'ui'
APP_DIR = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent
HOME = Path(os.environ.get('APPDATA') or Path.home() / '.config') / APP_NAME
STAGE = Path(tempfile.mkdtemp(prefix='butchies-converter-'))
CONFIG_FILE = HOME / 'config.json'
NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
TOKEN = secrets.token_urlsafe(16)
LAST_PING = [time.time()]
NATIVE = [False]
WIN = [None]           # pywebview-Fenster (für Datei-Dialoge)
VIDEXT = {'.mp4', '.m4v', '.mkv', '.mov', '.avi', '.ts', '.m2ts', '.mts', '.wmv', '.webm', '.flv', '.mpg', '.mpeg', '.vob',
          '.3gp', '.divx', '.ogv', '.mxf', '.rmvb', '.asf'}
SKIP_DIRS = {'$recycle.bin', 'system volume information', '_papierkorb', '.trash', '.trashes'}
FILES = {}             # id -> Datei-Info (Pfad, ffprobe-Daten)
JOBS = {}              # id -> Umwandlung
QUEUE = []
QLOCK = threading.Lock()
QEVENT = threading.Event()
TASKS = {}             # id -> Hintergrund-Aufgabe (VMAF, Vorher/Nachher, Bild-Abgleich)
HW = {}                # Encoder -> funktioniert?
FILTERS = {'libvmaf': False, 'zscale': False}
GPU = []
HW_DONE = threading.Event()
STREAMS = {}           # Player: Client -> laufender ffmpeg
TMDB_CACHE = {}
POWER = {'timer': None}
LANG3 = {'ger': 'de', 'deu': 'de', 'de': 'de', 'eng': 'en', 'en': 'en', 'ita': 'it', 'it': 'it', 'fre': 'fr', 'fra': 'fr', 'fr': 'fr',
         'spa': 'es', 'es': 'es', 'tur': 'tr', 'pol': 'pl', 'rus': 'ru', 'jpn': 'ja', 'dut': 'nl', 'nld': 'nl', 'por': 'pt'}
TEXT_SUBS = {'subrip', 'srt', 'ass', 'ssa', 'mov_text', 'webvtt', 'text'}
HW_ENCODERS = ('h264_amf', 'hevc_amf', 'h264_nvenc', 'hevc_nvenc', 'h264_qsv', 'hevc_qsv')
TONEMAP = 'zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p'


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
FFPROBE = find_tool('ffprobe')


def run(args, timeout=60, cwd=None):
    return subprocess.run(args, capture_output=True, timeout=timeout, creationflags=NO_WINDOW, stdin=subprocess.DEVNULL, cwd=cwd)


def popen(args, cwd=None):
    return subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, cwd=cwd,
                            creationflags=NO_WINDOW)


def load_config():
    try:
        return json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def save_config(conf):
    HOME.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(conf, indent=1, ensure_ascii=False), encoding='utf-8')


def videos_folder():
    base = Path.home() / 'Videos'
    if os.name == 'nt':
        try:
            import ctypes, uuid
            g = uuid.UUID('18989B1D-99B5-455B-841C-AB7C74E4DDFC').bytes_le
            guid = (ctypes.c_byte * 16)(*g)
            p = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(p)) == 0:
                base = Path(p.value)
                ctypes.windll.ole32.CoTaskMemFree(p)
        except Exception:  # noqa: BLE001
            pass
    return base


def default_outdir():
    """Vom Installer vorgeschlagener Ordner (Laufwerk mit dem meisten freien Speicher), sonst Videos\\Butchies Converter."""
    try:
        data = json.loads((APP_DIR / 'install.json').read_text(encoding='utf-8-sig'))
        if data.get('outdir'):
            return data['outdir']
    except (OSError, ValueError):
        pass
    return str(videos_folder() / 'Butchies Converter')


def outdir():
    return load_config().get('outdir') or default_outdir()


def disks():
    """Feste Laufwerke mit freiem Speicher (Windows) – größter freier Platz zuerst."""
    out = []
    if os.name == 'nt':
        import ctypes
        k = ctypes.windll.kernel32
        for letter in 'CDEFGHIJKLMNOPQRSTUVWXYZ':
            root = letter + ':\\'
            if k.GetDriveTypeW(root) != 3:
                continue
            free, total = ctypes.c_ulonglong(), ctypes.c_ulonglong()
            if k.GetDiskFreeSpaceExW(root, ctypes.byref(free), ctypes.byref(total), None):
                out.append({'drive': letter + ':', 'free': free.value, 'total': total.value})
    else:
        u = shutil.disk_usage('/')
        out.append({'drive': '/', 'free': u.free, 'total': u.total})
    return sorted(out, key=lambda d: -d['free'])


def fnum(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def safe_name(name):
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '-', str(name)).strip(' .')
    return name[:180] or 'video'


def unique_path(folder, name):
    p = Path(folder) / name
    i = 2
    while p.exists():
        p = Path(folder) / ('%s (%d)%s' % (Path(name).stem, i, Path(name).suffix))
        i += 1
    return p


def show_in_folder(path):
    path = Path(path)
    if os.name == 'nt':
        if path.is_file():
            subprocess.Popen('explorer /select,"%s"' % path)
        else:
            os.startfile(str(path if path.exists() else path.parent))  # noqa: S606
    else:
        webbrowser.open(path.parent.as_uri() if path.is_file() else path.as_uri())


# ---------- Encoder / Grafikkarten ----------
FFMPEG_IGPU = [None]   # Kopie von ffmpeg.exe, die Windows auf die zweite (integrierte) Grafikkarte schickt
WORKERS = []           # Arbeiter: Prozessor + bis zu 2 Grafikkarten
HW2 = {}               # Encoder auf der zweiten Grafikkarte -> funktioniert?
SUFFIX = {'amd': 'amf', 'nvidia': 'nvenc', 'intel': 'qsv'}


def gpu_info(name, vram=0):
    n = name.lower()
    vendor = 'nvidia' if re.search(r'nvidia|geforce|rtx|gtx|quadro', n) else 'amd' if re.search(r'amd|radeon', n) else \
        'intel' if 'intel' in n else 'andere'
    igpu = bool(re.search(r'\d{3}m\b|radeon\(tm\) graphics|vega \d+|uhd|iris|hd graphics', n))
    dgpu = bool(re.search(r'\brx\s?\d|geforce|rtx|gtx|quadro|radeon pro|\barc\b|titan', n)) or (vram >= 3.5 and not igpu)
    return {'name': name, 'vram': vram, 'vendor': vendor, 'kind': 'dgpu' if dgpu else 'igpu'}


def detect_gpus():
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
                                    mem = max(mem, v)
                                except (OSError, ValueError):
                                    pass
                    except OSError:
                        continue
                    if not re.search(r'basic display|basic render|remote|virtual|parsec|citrix|dameware', name, re.I):
                        found.append(gpu_info(name, round(mem / 1024 ** 3, 1)))
        except Exception:  # noqa: BLE001
            pass
    found.sort(key=lambda g: (g['kind'] != 'dgpu', -g['vram']))
    GPU[:] = found


def set_gpu_pref(exe, pref):
    """Windows-Grafikeinstellung pro Programm: 2 = Hochleistung (eigene Grafikkarte), 1 = Energiesparen (Prozessor-Grafik)."""
    if os.name != 'nt' or not exe:
        return
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\DirectX\UserGpuPreferences') as k:
            winreg.SetValueEx(k, str(Path(exe).resolve()), 0, winreg.REG_SZ, 'GpuPreference=%d;' % pref)
    except OSError:
        pass


def prepare_gpu_exes():
    if os.name != 'nt' or not FFMPEG:
        return
    set_gpu_pref(FFMPEG, 2)
    if len(GPU) < 2:
        return
    dst = Path(FFMPEG).with_name('ffmpeg-igpu.exe')
    try:
        if not dst.is_file() or dst.stat().st_size != Path(FFMPEG).stat().st_size:
            shutil.copy2(FFMPEG, dst)
        FFMPEG_IGPU[0] = str(dst)
        set_gpu_pref(dst, 1)
    except OSError:
        FFMPEG_IGPU[0] = None


def enc_works(exe, enc):
    try:
        r = run([exe, '-hide_banner', '-v', 'error', '-f', 'lavfi', '-i', 'color=black:s=256x256:d=0.2', '-frames:v', '2',
                 '-c:v', enc, '-f', 'null', '-'], timeout=25)
        return r.returncode == 0
    except Exception:  # noqa: BLE001
        return False


def hw_check():
    try:
        detect_gpus()
        prepare_gpu_exes()
        listed = run([FFMPEG, '-hide_banner', '-encoders'], timeout=30).stdout.decode('utf-8', 'replace') if FFMPEG else ''
        filt = run([FFMPEG, '-hide_banner', '-filters'], timeout=30).stdout.decode('utf-8', 'replace') if FFMPEG else ''
        FILTERS['libvmaf'] = ' libvmaf ' in filt
        FILTERS['zscale'] = ' zscale ' in filt
        for enc in ('libx264', 'libx265') + HW_ENCODERS:
            if (' ' + enc + ' ') not in listed:
                HW[enc] = False
            elif enc.startswith('lib'):
                HW[enc] = True
            else:
                HW[enc] = enc_works(FFMPEG, enc)
        ws = [{'slot': 'cpu', 'name': 'Prozessor', 'kind': 'cpu', 'vendor': '', 'enc': {'h264': 'libx264', 'h265': 'libx265'},
               'ok': bool(HW.get('libx265'))}]
        for i, g in enumerate(GPU[:2]):
            suf = SUFFIX.get(g['vendor'])
            if not suf:
                continue
            enc = {'h264': 'h264_' + suf, 'h265': 'hevc_' + suf}
            if i == 0:
                ok = HW.get(enc['h265']) or HW.get(enc['h264'])
            else:
                exe = FFMPEG_IGPU[0]
                for e in enc.values():
                    HW2[e] = bool(exe) and enc_works(exe, e)
                ok = HW2.get(enc['h265']) or HW2.get(enc['h264'])
            ws.append({'slot': 'gpu%d' % (i + 1), 'name': g['name'], 'kind': g['kind'], 'vendor': g['vendor'], 'enc': enc, 'ok': bool(ok),
                       'hevc': bool((HW if i == 0 else HW2).get(enc['h265']))})
        if os.environ.get('BVC_FAKE_GPU'):    # nur zum Testen ohne Grafikkarte
            for i, n in enumerate(('Test Radeon RX 7700 XT', 'Test Radeon 760M Graphics')):
                ws.append({'slot': 'gpu%d' % (i + 1), 'name': n, 'kind': 'dgpu' if i == 0 else 'igpu', 'vendor': 'amd',
                           'enc': {'h264': 'libx264', 'h265': 'libx265'}, 'ok': True, 'hevc': True})
        WORKERS[:] = ws
    finally:
        HW_DONE.set()


# ---------- Dateien prüfen (ffprobe) ----------
def lang2(tag):
    t = (tag or 'und').lower()
    return LANG3.get(t, t[:2] if t not in ('und', '') else 'und')


def layout(st):
    ch = int(st.get('channels') or 2)
    return {1: '1.0', 2: '2.0', 3: '2.1', 6: '5.1', 7: '6.1', 8: '7.1'}.get(ch, '%d.0' % ch)


def stream_kbps(st, fallback):
    b = st.get('bit_rate') or (st.get('tags') or {}).get('BPS') or (st.get('tags') or {}).get('BPS-eng')
    v = fnum(b) / 1000
    return int(v) if v > 0 else fallback


def probe(path):
    """Liest Auflösung, Länge, Bildrate, HDR, Ton- und Untertitelspuren, Kapitel. Wirft ValueError bei kaputten Dateien."""
    r = run([FFPROBE, '-v', 'error', '-print_format', 'json', '-show_format', '-show_streams', '-show_chapters', str(path)], timeout=60)
    if r.returncode != 0:
        raise ValueError('Datei lässt sich nicht lesen – vermutlich beschädigt oder unvollständig')
    d = json.loads(r.stdout.decode('utf-8', 'replace') or '{}')
    fmt = d.get('format') or {}
    streams = d.get('streams') or []
    v = next((s for s in streams if s.get('codec_type') == 'video' and not (s.get('disposition') or {}).get('attached_pic')), None)
    if not v:
        raise ValueError('Kein Bild in der Datei gefunden')
    dur = fnum(fmt.get('duration')) or fnum(v.get('duration'))
    num, _, den = (v.get('avg_frame_rate') or v.get('r_frame_rate') or '25/1').partition('/')
    fps = round(fnum(num) / fnum(den, 1), 3) if fnum(den, 1) else 25
    if not 1 <= fps <= 300:
        fps = 25.0
    trc = (v.get('color_transfer') or '').lower()
    side = json.dumps(v.get('side_data_list') or [])
    hdr = trc in ('smpte2084', 'arib-std-b67') or 'DOVI' in side or 'Dolby Vision' in side
    w, h = int(v.get('width') or 0), int(v.get('height') or 0)
    sar = v.get('sample_aspect_ratio') or '1:1'
    try:
        sn, sd = [int(x) for x in sar.split(':')]
        if sn and sd and sn != sd:
            w = int(round(w * sn / sd / 2)) * 2       # anamorph (z. B. DVD) -> echte Bildbreite
    except ValueError:
        pass
    audio, subs = [], []
    for s in streams:
        tags = s.get('tags') or {}
        title = (tags.get('title') or '').lower()
        disp = s.get('disposition') or {}
        if s.get('codec_type') == 'audio':
            ch = layout(s)
            fb = 192 if fnum(ch) <= 2.1 else 640
            audio.append({'lang': lang2(tags.get('language')), 'codec': (s.get('profile') if s.get('codec_name') == 'dts' and s.get('profile') else
                                                                    s.get('codec_name') or '?').upper().replace('_', ' '),
                          'ch': ch, 'kbps': stream_kbps(s, fb), 'comment': bool(re.search(r'comment|kommentar', title)) or bool(disp.get('comment')),
                          'title': tags.get('title') or ''})
        elif s.get('codec_type') == 'subtitle':
            subs.append({'lang': lang2(tags.get('language')), 'codec': s.get('codec_name') or '?', 'forced': bool(disp.get('forced')) or 'forced' in title,
                         'sdh': bool(disp.get('hearing_impaired')) or 'sdh' in title, 'title': tags.get('title') or ''})
    vcodec = v.get('codec_name') or '?'
    ext = Path(path).suffix.lower()
    acodecs = {s.get('codec_name') for s in streams if s.get('codec_type') == 'audio'}
    direct = (vcodec in ('h264', 'vp9', 'av1') and (v.get('pix_fmt') or '') in ('yuv420p', 'yuvj420p') and ext in ('.mp4', '.m4v', '.mov', '.webm')
              and acodecs <= {'aac', 'mp3', 'opus', 'vorbis'})
    return {'w': w, 'h': h, 'dur': round(dur, 3), 'fps': fps, 'hdr': hdr, 'vcodec': vcodec, 'pix': v.get('pix_fmt') or '',
            'bits': 10 if '10' in (v.get('pix_fmt') or '') else 8, 'direct': direct,
            'akbps': sum(a['kbps'] for a in audio),
            'tracks': {'audio': audio, 'subs': subs, 'chapters': len(d.get('chapters') or [])}}


def tail_check(path, dur):
    """Kurzer Prüflauf: lassen sich die letzten Sekunden dekodieren? (findet abgebrochene Downloads)"""
    if dur <= 0:
        return 'Länge unbekannt – Datei ist vermutlich unvollständig'
    try:
        r = run([FFMPEG, '-hide_banner', '-v', 'error', '-ss', str(max(0, dur - 4)), '-i', str(path), '-t', '3', '-map', '0:v:0',
                 '-f', 'null', '-'], timeout=60)
    except subprocess.TimeoutExpired:
        return None
    err = r.stderr.decode('utf-8', 'replace')
    if r.returncode != 0 or len(re.findall(r'(?i)invalid data|corrupt|error while decoding|truncat', err)) >= 3:
        return 'Ende der Datei lässt sich nicht lesen – vermutlich abgebrochen oder beschädigt'
    return None


def file_entry(path):
    path = Path(path)
    fid = hashlib.sha1(str(path).encode('utf-8', 'replace')).hexdigest()[:12]
    e = {'id': fid, 'path': str(path), 'name': path.name, 'size': 0}
    try:
        e['size'] = path.stat().st_size
        if not e['size']:
            raise ValueError('Datei ist leer (0 Byte)')
        e.update(probe(path))
        bad = tail_check(path, e['dur'])
        if bad:
            e['bad'] = bad
    except subprocess.TimeoutExpired:
        e['bad'] = 'Prüfung dauerte zu lange'
    except (ValueError, OSError) as ex:
        e['bad'] = str(ex)
    FILES[fid] = e
    return e


def expand(paths, limit=5000):
    out = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            for root, dirs, files in os.walk(p):
                dirs[:] = sorted(d for d in dirs if d.lower() not in SKIP_DIRS)
                for f in sorted(files):
                    if Path(f).suffix.lower() in VIDEXT:
                        out.append(Path(root) / f)
                        if len(out) >= limit:
                            return out
        elif p.is_file() and p.suffix.lower() in VIDEXT:
            out.append(p)
    return out


def add_files(paths):
    files = expand(paths)
    with concurrent.futures.ThreadPoolExecutor(4) as ex:
        return list(ex.map(file_entry, files))


def fpath(fid):
    e = FILES.get(fid)
    if not e:
        raise ValueError('Datei unbekannt – bitte neu hinzufügen')
    return e


# ---------- Umwandeln ----------
PLACE = {'{NULL}': 'NUL' if os.name == 'nt' else '/dev/null', '{PASSLOG}': 'ffpass'}
ALLOWED_OUT = {'.mkv', '.mp4', '.mov'}


def fill_args(args, src, out):
    res = []
    for a in args:
        a = str(a)
        if a == '{IN}':
            a = src
        elif a == '{OUT}':
            a = out
        else:
            for k, v in PLACE.items():
                a = a.replace(k, v)
        res.append(a)
    return res


def new_job(item):
    e = fpath(item['id'])
    passes = item.get('passes') or []
    if not passes or not all(isinstance(p, list) for p in passes):
        raise ValueError('Keine Einstellungen übergeben')
    name = safe_name(Path(item.get('outname') or e['name']).name)
    if Path(name).suffix.lower() not in ALLOWED_OUT:
        name += '.mkv'
    folder = Path(item.get('outdir') or outdir())
    jid = secrets.token_hex(6)
    slot = item.get('slot') if item.get('slot') in ('cpu', 'gpu1', 'gpu2') else 'cpu'
    j = {'id': jid, 'slot': slot, 'fid': e['id'], 'src': e['path'], 'name': e['name'], 'folder': str(folder), 'outname': name, 'passes': passes,
         'dur': e.get('dur') or 0, 'state': 'wartet', 'pct': 0.0, 'fps': 0, 'speed': 0, 'kbps': 0, 'size': 0, 'eta': None,
         'error': '', 'out': '', 'proc': None, 'paused': False, 'cancel': False, 'started': 0, 'pass': 0}
    with QLOCK:
        JOBS[jid] = j
        QUEUE.append(jid)
    QEVENT.set()
    return j


def job_view(j):
    return {k: v for k, v in j.items() if k not in ('proc', 'passes')}


def suspend(proc, on):
    if not proc or proc.poll() is not None:
        return
    if os.name == 'nt':
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x0800, False, proc.pid)   # PROCESS_SUSPEND_RESUME
        if h:
            (ctypes.windll.ntdll.NtSuspendProcess if on else ctypes.windll.ntdll.NtResumeProcess)(h)
            ctypes.windll.kernel32.CloseHandle(h)
    else:
        os.kill(proc.pid, signal.SIGSTOP if on else signal.SIGCONT)


def run_job(j):
    folder = Path(j['folder'])
    folder.mkdir(parents=True, exist_ok=True)
    final = unique_path(folder, j['outname'])
    tmp = folder / ('%s.teil%s' % (final.stem, final.suffix))
    work = STAGE / ('job-' + j['id'])
    work.mkdir(parents=True, exist_ok=True)
    j['state'], j['started'] = 'läuft', time.time()
    if j['cancel']:
        j['state'] = 'abgebrochen'
        return
    n = len(j['passes'])
    log = []
    for i, args in enumerate(j['passes']):
        j['pass'] = i + 1
        exe = FFMPEG_IGPU[0] if j.get('slot') == 'gpu2' and FFMPEG_IGPU[0] else FFMPEG
        cmd = [exe, '-hide_banner', '-nostdin', '-y', '-progress', 'pipe:1', '-nostats'] + fill_args(args, j['src'], str(tmp))
        p = popen(cmd, cwd=str(work))
        j['proc'] = p
        errbuf = []
        threading.Thread(target=lambda: errbuf.extend(p.stderr.read().decode('utf-8', 'replace').splitlines()[-40:]), daemon=True).start()
        cur = {}
        for raw in p.stdout:
            line = raw.decode('utf-8', 'replace').strip()
            if '=' not in line:
                continue
            k, _, v = line.partition('=')
            cur[k] = v
            if k == 'progress':
                t = fnum(cur.get('out_time_us') or cur.get('out_time_ms')) / 1e6
                if j['dur']:
                    j['pct'] = round(min(99.9, (i + min(1, t / j['dur'])) / n * 100), 2)
                j['fps'] = fnum(cur.get('fps'))
                j['speed'] = fnum((cur.get('speed') or '0').rstrip('x'))
                j['kbps'] = fnum((cur.get('bitrate') or '0').replace('kbits/s', ''))
                j['size'] = int(fnum(cur.get('total_size')))
                j['t'] = t
                el = time.time() - j['started']
                j['eta'] = round(el / (j['pct'] / 100) - el) if j['pct'] > 0.5 else None
        p.wait()
        log += errbuf
        if j['cancel']:
            tmp.unlink(missing_ok=True)
            j['state'] = 'abgebrochen'
            return
        if p.returncode != 0:
            tmp.unlink(missing_ok=True)
            txt = '\n'.join(log[-12:])
            hw = any(a in HW_ENCODERS for a in args)
            j['error'] = ('Die Grafikkarte konnte dieses Video nicht kodieren – bitte beim Encoder „Software“ wählen.\n' if hw else '') + txt
            j['state'] = 'fehler'
            return
    tmp.replace(final)
    j['out'], j['pct'], j['state'], j['size'] = str(final), 100.0, 'fertig', final.stat().st_size
    shutil.rmtree(work, ignore_errors=True)


def worker(slot='cpu'):
    """Ein Arbeiter pro Prozessor / Grafikkarte – so laufen mehrere Videos gleichzeitig."""
    while True:
        with QLOCK:
            jid = next((x for x in QUEUE if JOBS.get(x, {}).get('state') == 'wartet' and JOBS[x].get('slot', 'cpu') == slot), None)
            if jid:
                JOBS[jid]['state'] = 'läuft'
        if not jid:
            QEVENT.wait(1)
            QEVENT.clear()
            continue
        j = JOBS[jid]
        try:
            run_job(j)
        except Exception as e:  # noqa: BLE001
            j['state'], j['error'] = 'fehler', str(e)
        j['proc'] = None


def cancel_job(jid):
    j = JOBS.get(jid)
    if not j:
        return
    j['cancel'] = True
    if j['state'] == 'wartet':
        j['state'] = 'abgebrochen'
    p = j.get('proc')
    if p and p.poll() is None:
        if j.get('paused'):
            suspend(p, False)
        p.kill()


def busy():
    return any(j['state'] in ('läuft', 'wartet') for j in JOBS.values())


def stop_all():
    for jid in list(JOBS):
        cancel_job(jid)
    for p in list(STREAMS.values()):
        try:
            p.kill()
        except Exception:  # noqa: BLE001
            pass


# ---------- Standbilder, Proben, VMAF ----------
def frame_vf(e, w, tonemap=True):
    vf = []
    if e.get('hdr') and tonemap and FILTERS['zscale']:
        vf.append(TONEMAP)
    vf.append('scale=%d:-2:flags=bicubic' % w)
    return ','.join(vf)


def grab(path, t, out, vf, timeout=60):
    r = run([FFMPEG, '-hide_banner', '-v', 'error', '-y', '-ss', '%.3f' % max(0, t), '-i', str(path), '-frames:v', '1', '-vf', vf,
             '-q:v', '2', str(out)], timeout=timeout)
    return r.returncode == 0 and Path(out).is_file()


def img_url(p):
    key = secrets.token_hex(6)
    IMGS[key] = str(p)
    return '/api/img/' + key


IMGS = {}


def clean_vargs(vargs):
    """Nur Bild-Einstellungen (ohne 2-Pass), damit ein Probestück kodiert werden kann."""
    out, skip = [], False
    for i, a in enumerate(vargs):
        if skip:
            skip = False
            continue
        a = str(a)
        if a in ('-pass', '-passlogfile'):
            skip = True
            continue
        if i > 0 and str(vargs[i - 1]) == '-x265-params':
            a = ':'.join(x for x in a.split(':') if not x.startswith(('pass=', 'stats=')))
            if not a:
                out.pop()
                continue
        out.append(a)
    return out


def encode_sample(e, vargs, t, seg, out):
    cmd = [FFMPEG, '-hide_banner', '-v', 'error', '-y', '-ss', '%.3f' % t, '-i', e['path'], '-t', str(seg), '-map', '0:v:0'] + \
        clean_vargs(vargs) + ['-an', '-sn', '-dn', str(out)]
    r = run(cmd, timeout=1800, cwd=str(STAGE))
    if r.returncode != 0:
        raise ValueError('Probestück konnte nicht kodiert werden: ' + r.stderr.decode('utf-8', 'replace')[-300:])


def measure(e, enc, t, seg, w, h, out_hdr=False):
    tm = (TONEMAP + ',') if e.get('hdr') and FILTERS['zscale'] else ''
    td = (TONEMAP + ',') if out_hdr and FILTERS['zscale'] else ''
    sc = 'scale=%d:%d:flags=bicubic,format=yuv420p,setpts=PTS-STARTPTS' % (w, h)
    if FILTERS['libvmaf']:
        log = STAGE / ('vmaf-%s.json' % secrets.token_hex(4))
        lav = '[0:v]%s%s[d];[1:v]%s%s[r];[d][r]libvmaf=log_fmt=json:log_path=%s:n_threads=%d' % (
            td, sc, tm, sc, log.name, max(2, (os.cpu_count() or 4) // 2))
        r = run([FFMPEG, '-hide_banner', '-v', 'error', '-i', str(enc), '-ss', '%.3f' % t, '-t', str(seg), '-i', e['path'], '-lavfi', lav,
                 '-f', 'null', '-'], timeout=3600, cwd=str(STAGE))
        try:
            data = json.loads(log.read_text(encoding='utf-8'))
            return round(fnum(data['pooled_metrics']['vmaf']['mean']), 2), 'vmaf'
        except (OSError, ValueError, KeyError):
            if r.returncode != 0:
                raise ValueError('VMAF-Messung fehlgeschlagen: ' + r.stderr.decode('utf-8', 'replace')[-200:])
    lav = '[0:v]%s%s[d];[1:v]%s%s[r];[d][r]ssim' % (td, sc, tm, sc)
    r = run([FFMPEG, '-hide_banner', '-i', str(enc), '-ss', '%.3f' % t, '-t', str(seg), '-i', e['path'], '-lavfi', lav, '-f', 'null', '-'],
            timeout=3600)
    m = re.findall(r'All:([0-9.]+)', r.stderr.decode('utf-8', 'replace'))
    if not m:
        raise ValueError('Messung fehlgeschlagen')
    ssim = fnum(m[-1])
    return round(max(0.0, min(100.0, 100 - (1 - ssim) * 450)), 2), 'ssim'


def task_vmaf(tid, e, vargs, fracs, seg):
    T = TASKS[tid]
    dur = e.get('dur') or 0
    seg = min(seg, max(2, dur / 6)) if dur else seg
    W = min(1920, e.get('w') or 1920) // 2 * 2
    H = int(round(W * (e.get('h') or 1080) / max(1, e.get('w') or 1920) / 2)) * 2
    samples, bits, secs = [], 0, 0
    out_hdr = bool(e.get('hdr')) and 'bt2020' in ' '.join(map(str, vargs))
    for i, f in enumerate(fracs):
        t = max(0, dur * f - seg / 2) if dur else 0
        enc = STAGE / ('probe-%s-%d.mkv' % (tid, i))
        T['phase'] = 'Kodiere Probestück %d von %d' % (i + 1, len(fracs))
        T['pct'] = round(i / len(fracs) * 100 + 5)
        encode_sample(e, vargs, t, seg, enc)
        bits += enc.stat().st_size * 8
        secs += seg
        T['phase'] = 'Messe Probestück %d von %d' % (i + 1, len(fracs))
        T['pct'] = round((i + .55) / len(fracs) * 100)
        v, method = measure(e, enc, t, seg, W, H, out_hdr)
        b, a = STAGE / ('pb-%s-%d.jpg' % (tid, i)), STAGE / ('pa-%s-%d.jpg' % (tid, i))
        grab(e['path'], t + seg / 2, b, frame_vf(e, W))
        grab(enc, seg / 2, a, ('%s,' % TONEMAP if out_hdr and FILTERS['zscale'] else '') +
             'scale=%d:%d:flags=bicubic' % (W, H))
        samples.append({'frac': f, 'v': v, 'before': img_url(b), 'after': img_url(a)})
        T['method'] = method
    T['result'] = {'vmaf': round(sum(s['v'] for s in samples) / len(samples), 2), 'samples': samples, 'kbps': round(bits / max(secs, .1) / 1000),
                   'method': T.get('method', 'vmaf')}
    T['pct'], T['state'] = 100, 'fertig'


def task_abshot(tid, e, vargs, frac):
    T = TASKS[tid]
    dur = e.get('dur') or 0
    t = max(0, dur * frac - 1) if dur else 0
    W = min(1920, e.get('w') or 1920) // 2 * 2
    H = int(round(W * (e.get('h') or 1080) / max(1, e.get('w') or 1920) / 2)) * 2
    T['phase'], T['pct'] = 'Kodiere Probestück mit deinen Einstellungen …', 20
    enc = STAGE / ('ab-%s.mkv' % tid)
    encode_sample(e, vargs, t, 2, enc)
    b, a = STAGE / ('ab-%s-b.jpg' % tid), STAGE / ('ab-%s-a.jpg' % tid)
    grab(e['path'], t + 1, b, frame_vf(e, W))
    grab(enc, 1, a, ('%s,' % TONEMAP if e.get('hdr') and FILTERS['zscale'] and 'bt2020' in ' '.join(map(str, vargs)) else '') +
         'scale=%d:%d:flags=bicubic' % (W, H))
    T['result'] = {'before': img_url(b), 'after': img_url(a), 't': t + 1, 'kbps': round(enc.stat().st_size * 8 / 2 / 1000)}
    T['pct'], T['state'] = 100, 'fertig'


def start_task(fn, *args):
    tid = secrets.token_hex(6)
    TASKS[tid] = {'id': tid, 'state': 'läuft', 'pct': 0, 'phase': 'Starte …'}

    def go():
        try:
            fn(tid, *args)
        except Exception as ex:  # noqa: BLE001
            TASKS[tid].update(state='fehler', error=str(ex))
    threading.Thread(target=go, daemon=True).start()
    return tid


# ---------- Ordner-Abgleich ----------
def scan(folder, limit=100000, T=None, recursive=True):
    """Ordner rekursiv einlesen. os.scandir liefert unter Windows die Größe gleich mit (schnell, auch übers Netzwerk/NAS).
    Fortschritt: jeder Unterordner bekommt einen gleichen Anteil vom Anteil seines Elternordners."""
    root = Path(folder)
    if not root.is_dir():
        raise ValueError('Ordner nicht gefunden')
    out, done = [], [0.0]

    def walk(d, w):
        if len(out) >= limit:
            return
        try:
            entries = list(os.scandir(d))
        except OSError:
            done[0] += w
            return
        subs = []
        for e in entries:
            try:
                if e.is_dir(follow_symlinks=False):
                    if e.name.lower() not in SKIP_DIRS:
                        subs.append(e.path)
                elif e.is_file(follow_symlinks=False):
                    p = Path(e.path)
                    out.append({'name': e.name, 'full': e.path, 'size': e.stat().st_size,
                                'path': root.name + '/' + str(p.relative_to(root)).replace('\\', '/')})
            except (OSError, ValueError):
                pass
        share = w / (len(subs) + 1)
        done[0] += share
        if T is not None:
            T['pct'] = min(99, int(done[0] * 100))
            T['phase'] = '%s Dateien gefunden · %s' % (format(len(out), ',').replace(',', '.'), Path(d).name or str(d))
        if not recursive:
            done[0] += w - share
            return
        for sub in sorted(subs, key=str.lower):
            walk(sub, share)
    walk(root, 1.0)
    out.sort(key=lambda f: f['path'].lower())
    return out


def task_scan(tid, folder, recursive=True):
    T = TASKS[tid]
    files = scan(folder, T=T, recursive=recursive)
    T['result'] = {'root': str(Path(folder)), 'files': files}
    T['pct'], T['state'] = 100, 'fertig'


def task_hash(tid, paths):
    T = TASKS[tid]
    res = {}
    for i, p in enumerate(paths):
        T['pct'], T['phase'] = round(i / max(1, len(paths)) * 100), Path(p).name
        try:
            res[p] = quick_hash(p)
        except OSError:
            res[p] = None
    T['result'] = res
    T['pct'], T['state'] = 100, 'fertig'


def quick_hash(path):
    h = hashlib.sha256()
    size = os.path.getsize(path)
    with open(path, 'rb') as f:
        h.update(f.read(4 << 20))
        if size > 8 << 20:
            f.seek(size - (4 << 20))
            h.update(f.read(4 << 20))
    h.update(str(size).encode())
    return h.hexdigest()[:16]


def frame_bits(path):
    r = run([FFPROBE, '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(path)], timeout=30)
    dur = fnum(r.stdout.decode().strip())
    if dur <= 0:
        return None
    bits = ''
    for f in (.2, .5, .8):
        r = run([FFMPEG, '-hide_banner', '-v', 'error', '-ss', '%.2f' % (dur * f), '-i', str(path), '-frames:v', '1',
                 '-vf', 'scale=8:8:flags=area,format=gray', '-f', 'rawvideo', '-'], timeout=60)
        px = list(r.stdout[:64])
        if len(px) < 64:
            return None
        m = sum(px) / 64
        bits += ''.join('1' if v > m else '0' for v in px)
    return bits


def task_fp(tid, paths):
    T = TASKS[tid]
    res = {}
    for i, p in enumerate(paths):
        T['pct'] = round(i / max(1, len(paths)) * 100)
        T['phase'] = Path(p).name
        try:
            res[p] = frame_bits(p)
        except Exception:  # noqa: BLE001
            res[p] = None
    T['result'] = res
    T['pct'], T['state'] = 100, 'fertig'


def recycle(path):
    """In den Windows-Papierkorb verschieben (rückholbar)."""
    if os.name != 'nt':
        raise OSError('Papierkorb nur unter Windows')
    import ctypes
    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [('hwnd', wintypes.HWND), ('wFunc', wintypes.UINT), ('pFrom', wintypes.LPCWSTR), ('pTo', wintypes.LPCWSTR),
                    ('fFlags', ctypes.c_ushort), ('fAnyOperationsAborted', wintypes.BOOL), ('hNameMappings', ctypes.c_void_p),
                    ('lpszProgressTitle', wintypes.LPCWSTR)]
    op = SHFILEOPSTRUCTW(None, 3, str(path) + '\0', None, 0x0040 | 0x0010 | 0x0004 | 0x0400, False, None, None)  # DELETE, ALLOWUNDO|NOCONFIRM|SILENT|NOERRORUI
    if ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op)) != 0 or op.fAnyOperationsAborted:
        raise OSError('konnte nicht in den Papierkorb')


def delete_items(items):
    res = []
    for it in items:
        p = Path(it.get('path', ''))
        try:
            if not p.is_file():
                raise OSError('Datei nicht gefunden')
            if it.get('protect') and it.get('root'):
                root = Path(it['root'])
                rel = p.relative_to(root) if str(p).startswith(str(root)) else Path(p.name)
                dest = unique_path((root / '_Papierkorb' / rel).parent, p.name)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(p), str(dest))
                res.append({'path': str(p), 'ok': True, 'moved': str(dest)})
            else:
                recycle(p)
                res.append({'path': str(p), 'ok': True, 'recycled': True})
        except Exception as ex:  # noqa: BLE001
            res.append({'path': str(p), 'ok': False, 'error': str(ex)})
    return res


def rename_items(items):
    res = []
    for it in items:
        p = Path(it.get('path', ''))
        new = p.with_name(safe_name(it.get('new', '')))
        try:
            if not p.is_file():
                raise OSError('Datei nicht gefunden')
            if new.exists() and new != p:
                raise OSError('Name gibt es schon')
            p.rename(new)
            res.append({'path': str(p), 'newpath': str(new), 'ok': True})
        except Exception as ex:  # noqa: BLE001
            res.append({'path': str(p), 'ok': False, 'error': str(ex)})
    return res


def tmdb(names, key):
    """names: [{title, year}] -> {"Titel|Jahr": {title, year} oder None} (deutsche Titel von themoviedb.org)."""
    out = {}
    for n in names[:200]:
        k = '%s|%s' % (n.get('title', ''), n.get('year') or '')
        if k not in TMDB_CACHE:
            q = {'api_key': key, 'query': n.get('title', ''), 'language': 'de-DE'}
            if n.get('year'):
                q['year'] = n['year']
            try:
                with urllib.request.urlopen('https://api.themoviedb.org/3/search/movie?' + urllib.parse.urlencode(q), timeout=10) as r:
                    data = json.loads(r.read().decode('utf-8'))
                hit = (data.get('results') or [None])[0]
                TMDB_CACHE[k] = {'title': hit['title'], 'year': (hit.get('release_date') or '')[:4]} if hit else None
            except Exception:  # noqa: BLE001
                TMDB_CACHE[k] = None
        out[k] = TMDB_CACHE[k]
    return out


def notify(topic, msg):
    topic = re.sub(r'[^\w-]', '', topic or '')
    if not topic:
        raise ValueError('Kein Thema angegeben')
    req = urllib.request.Request('https://ntfy.sh/' + topic, data=msg.encode('utf-8'), method='POST',
                                 headers={'Title': APP_NAME, 'Tags': 'clapper'})
    with urllib.request.urlopen(req, timeout=10):
        pass


def power(action):
    if POWER['timer']:
        POWER['timer'].cancel()
        POWER['timer'] = None
    if os.name != 'nt':
        return
    if action == 'off':
        subprocess.Popen(['shutdown', '/s', '/t', '60', '/c', 'Butchies Video Converter: alle Videos fertig – PC fährt herunter.'],
                         creationflags=NO_WINDOW)
    elif action == 'sleep':
        POWER['timer'] = threading.Timer(60, lambda: subprocess.Popen(['rundll32.exe', 'powrprof.dll,SetSuspendState', '0,1,0'],
                                                                      creationflags=NO_WINDOW))
        POWER['timer'].start()
    elif action == 'cancel':
        subprocess.Popen(['shutdown', '/a'], creationflags=NO_WINDOW)


def stream_cmd(e, t, aidx):
    enc = next((x for x in ('h264_nvenc', 'h264_qsv', 'h264_amf') if HW.get(x)), 'libx264')
    vf = []
    if e.get('hdr') and FILTERS['zscale']:
        vf.append(TONEMAP)
    vf.append("scale='min(1920,iw)':-2")
    if not e.get('hdr'):
        vf.append('format=yuv420p')
    q = {'libx264': ['-preset', 'veryfast', '-crf', '21'], 'h264_nvenc': ['-preset', 'p3', '-cq', '22'],
         'h264_qsv': ['-preset', 'veryfast', '-global_quality', '22'], 'h264_amf': ['-quality', 'speed', '-rc', 'cqp', '-qp_i', '22', '-qp_p', '24']}[enc]
    return [FFMPEG, '-hide_banner', '-v', 'error', '-ss', '%.3f' % t, '-i', e['path'], '-map', '0:v:0', '-map', '0:a:%d?' % aidx,
            '-vf', ','.join(vf), '-c:v', enc] + q + ['-g', '50', '-c:a', 'aac', '-ac', '2', '-b:a', '192k',
                                                   '-f', 'mp4', '-movflags', 'frag_keyframe+empty_moov+default_base_moof', 'pipe:1']


# ---------- Webserver ----------
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
        start, end = 0, size - 1
        m = re.match(r'bytes=(\d*)-(\d*)', self.headers.get('Range') or '')
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
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    return
                left -= len(chunk)

    def send_stream(self, cmd, client):
        old = STREAMS.pop(client, None)
        if old:
            try:
                old.kill()
            except Exception:  # noqa: BLE001
                pass
        p = popen(cmd)
        STREAMS[client] = p
        threading.Thread(target=p.stderr.read, daemon=True).start()
        self.send_response(200)
        self.send_header('Content-Type', 'video/mp4')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        try:
            while True:
                chunk = p.stdout.read(1 << 16)
                if not chunk:
                    break
                self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass
        finally:
            try:
                p.kill()
            except Exception:  # noqa: BLE001
                pass
            if STREAMS.get(client) is p:
                STREAMS.pop(client, None)

    def do_GET(self):
        if not self.local_only():
            return
        u = urllib.parse.urlsplit(self.path)
        path, q = u.path, {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        LAST_PING[0] = time.time()
        try:
            if path in ('/', '/index.html'):
                # gespeicherte Einstellungen (Design, Auto/Manuell, Vorlagen) gleich mitgeben – vor dem ersten Zeichnen
                html = (UI / 'index.html').read_text(encoding='utf-8')
                conf = json.dumps({'ls': load_config().get('ls') or {}}, ensure_ascii=False).replace('</', '<\\/')
                body = html.replace('<script>\n(()=>{', '<script>window.BVC_CONF=%s;</script>\n<script>\n(()=>{' % conf, 1).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(body)
                return None
            if path.startswith('/fonts/'):
                f = (UI / path.lstrip('/')).resolve()
                if UI.resolve() in f.parents and f.is_file():
                    return self.send_file(f)
                return self.send_json(404, {'error': 'Unbekannt'})
            if path == '/favicon.ico':
                self.send_response(204)
                self.end_headers()
                return None
            if path == '/api/ping':
                return self.send_json(200, {'ok': True})
            if path == '/api/info':
                HW_DONE.wait(20)
                conf = load_config()
                return self.send_json(200, {'version': VERSION, 'ffmpeg': bool(FFMPEG and FFPROBE), 'hw': HW, 'filters': FILTERS, 'gpus': GPU, 'workers': WORKERS,
                                            'disks': disks(), 'outdir': outdir(), 'config': conf, 'native': NATIVE[0]})
            if path == '/api/jobs':
                return self.send_json(200, {'jobs': [job_view(JOBS[j]) for j in QUEUE if j in JOBS]})
            m = re.fullmatch(r'/api/task/([0-9a-f]+)', path)
            if m:
                t = TASKS.get(m.group(1))
                return self.send_json(200 if t else 404, t or {'error': 'Unbekannt'})
            m = re.fullmatch(r'/api/img/([0-9a-f]+)', path)
            if m and m.group(1) in IMGS and Path(IMGS[m.group(1)]).is_file():
                return self.send_file(IMGS[m.group(1)], 'image/jpeg')
            if path == '/api/frame':
                e = fpath(q.get('id', ''))
                w = max(64, min(3840, int(fnum(q.get('w'), 1920))))
                w = min(w, (e.get('w') or w)) // 2 * 2
                out = STAGE / ('fr-%s-%d-%d.jpg' % (e['id'], int(fnum(q.get('t')) * 10), w))
                if out.is_file() or grab(e['path'], fnum(q.get('t')), out, frame_vf(e, w)):
                    return self.send_file(out, 'image/jpeg')
                return self.send_json(500, {'error': 'Standbild nicht möglich'})
            if path == '/api/file':
                e = fpath(q.get('id', ''))
                return self.send_file(e['path'], 'video/mp4' if Path(e['path']).suffix.lower() in ('.mp4', '.m4v', '.mov') else None)
            if path == '/api/stream':
                e = fpath(q.get('id', ''))
                return self.send_stream(stream_cmd(e, fnum(q.get('t')), int(fnum(q.get('a')))), q.get('c', 'x'))
            return self.send_json(404, {'error': 'Unbekannt'})
        except ValueError as ex:
            return self.send_json(400, {'error': str(ex)})
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return None
        except Exception as ex:  # noqa: BLE001
            return self.send_json(500, {'error': 'Interner Fehler: %s' % ex})

    def do_POST(self):
        if not self.local_only():
            return
        path = urllib.parse.urlsplit(self.path).path
        LAST_PING[0] = time.time()
        try:
            d = self.body_json()
            if path == '/api/pick':
                return self.send_json(200, {'paths': pick(d.get('kind', 'files'), d.get('start', ''))})
            if path == '/api/add':
                return self.send_json(200, {'files': add_files([p for p in d.get('paths', []) if p])})
            if path == '/api/convert':
                jobs = [new_job(it) for it in d.get('items', [])]
                return self.send_json(200, {'jobs': [job_view(j) for j in jobs]})
            if path == '/api/cancel':
                for jid in d.get('ids') or list(JOBS):
                    cancel_job(jid)
                return self.send_json(200, {'ok': True})
            if path == '/api/pause':
                for j in JOBS.values():
                    if j['state'] in ('läuft',) and j.get('proc'):
                        suspend(j['proc'], bool(d.get('on')))
                        j['paused'] = bool(d.get('on'))
                return self.send_json(200, {'ok': True})
            if path == '/api/clear':
                with QLOCK:
                    for jid in [x for x in QUEUE if JOBS[x]['state'] in ('fertig', 'fehler', 'abgebrochen')]:
                        QUEUE.remove(jid)
                        JOBS.pop(jid, None)
                return self.send_json(200, {'ok': True})
            if path == '/api/vmaf':
                e = fpath(d.get('id', ''))
                fr = [f for f in d.get('fracs', [.25, .5, .75]) if 0 <= fnum(f) <= 1][:5] or [.5]
                return self.send_json(200, {'task': start_task(task_vmaf, e, list(d.get('vargs') or []), fr, int(fnum(d.get('seg'), 8)))})
            if path == '/api/abshot':
                e = fpath(d.get('id', ''))
                return self.send_json(200, {'task': start_task(task_abshot, e, list(d.get('vargs') or []), fnum(d.get('frac'), .5))})
            if path == '/api/scan':
                if not Path(d.get('path', '')).is_dir():
                    raise ValueError('Ordner nicht gefunden')
                return self.send_json(200, {'task': start_task(task_scan, d.get('path', ''), d.get('recursive', True) is not False)})
            if path == '/api/hashtask':
                return self.send_json(200, {'task': start_task(task_hash, [p for p in d.get('paths', [])][:2000])})
            if path == '/api/hash':
                out = {}
                for p in d.get('paths', [])[:2000]:
                    try:
                        out[p] = quick_hash(p)
                    except OSError:
                        out[p] = None
                return self.send_json(200, {'hashes': out})
            if path == '/api/fp':
                return self.send_json(200, {'task': start_task(task_fp, [p for p in d.get('paths', [])][:500])})
            if path == '/api/delete':
                return self.send_json(200, {'results': delete_items(d.get('items', []))})
            if path == '/api/restore':
                res = []
                for mv in d.get('moves', []):
                    try:
                        Path(mv['from']).parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(mv['to'], mv['from'])
                        res.append({'ok': True, 'path': mv['from']})
                    except Exception as ex:  # noqa: BLE001
                        res.append({'ok': False, 'path': mv.get('from'), 'error': str(ex)})
                return self.send_json(200, {'results': res})
            if path == '/api/rename':
                return self.send_json(200, {'results': rename_items(d.get('items', []))})
            if path == '/api/tmdb':
                key = d.get('key') or load_config().get('tmdb', '')
                if not key:
                    raise ValueError('Kein TMDB-Schlüssel eingetragen')
                return self.send_json(200, {'titles': tmdb(d.get('names', []), key)})
            if path == '/api/notify':
                notify(d.get('topic', ''), d.get('msg', 'Fertig'))
                return self.send_json(200, {'ok': True})
            if path == '/api/power':
                power(d.get('action', 'cancel'))
                return self.send_json(200, {'ok': True})
            if path == '/api/config':
                conf = load_config()
                for k in ('outdir', 'theme', 'intro', 'tmdb', 'ntfy', 'auto', 'presets', 'ls'):
                    if k in d:
                        conf[k] = d[k]
                save_config(conf)
                return self.send_json(200, {'ok': True, 'outdir': outdir()})
            if path == '/api/show':
                target = d.get('path') or outdir()
                Path(target if not Path(target).suffix else Path(target).parent).mkdir(parents=True, exist_ok=True)
                show_in_folder(target)
                return self.send_json(200, {'ok': True})
            if path == '/api/open-url':
                if str(d.get('url', '')).startswith('https://'):
                    webbrowser.open(d['url'])
                return self.send_json(200, {'ok': True})
            if path == '/api/quit':
                stop_all()
                if not NATIVE[0]:
                    threading.Timer(0.6, lambda: os._exit(0)).start()
                return self.send_json(200, {'ok': True})
            return self.send_json(404, {'error': 'Unbekannt'})
        except ValueError as ex:
            return self.send_json(400, {'error': str(ex)})
        except Exception as ex:  # noqa: BLE001
            return self.send_json(500, {'error': 'Interner Fehler: %s' % ex})


def pick(kind, start=''):
    """Datei- bzw. Ordner-Auswahl im Programmfenster."""
    win = WIN[0]
    if not win:
        raise ValueError('Auswahl-Fenster gibt es nur im Programm – bitte Dateien hineinziehen.')
    import webview
    try:
        if kind == 'folder':
            res = win.create_file_dialog(webview.FOLDER_DIALOG, directory=start or '')
        else:
            exts = ';'.join('*' + x for x in sorted(VIDEXT))
            res = win.create_file_dialog(webview.OPEN_DIALOG, directory=start or '', allow_multiple=True,
                                         file_types=('Videos (%s)' % exts, 'Alle Dateien (*.*)'))
    except Exception:  # noqa: BLE001
        return []
    return list(res or [])


# ---------- Programmfenster (wie im ffmpeg_encode Studio) ----------
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
    WIN[0] = win

    def on_loaded(*a):
        # Ziehen & Ablegen: WebView2 gibt den echten Pfad nur über pywebview heraus
        try:
            from webview.dom import DOMEventHandler

            def on_drop(ev):
                files = (ev.get('dataTransfer') or {}).get('files') or []
                paths = [f.get('pywebviewFullPath') for f in files if f.get('pywebviewFullPath')]
                if paths:
                    win.evaluate_js('window.nativeDrop && window.nativeDrop(%s)' % json.dumps(paths))
            win.dom.document.events.drop += DOMEventHandler(on_drop, True, True)
        except Exception as ex:  # noqa: BLE001
            print('Drop-Handler:', ex, flush=True)
    win.events.loaded += on_loaded

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




# ---------- Selbsttest (läuft im GitHub-Build auf echtem Windows) ----------
def selftest():
    ok = True

    def check(name, cond, info=''):
        nonlocal ok
        print(('OK   ' if cond else 'FEHLER ') + name + (' – ' + str(info) if info else ''), flush=True)
        ok = ok and bool(cond)
    print('%s %s Selbsttest' % (APP_NAME, VERSION), flush=True)
    check('ffmpeg + ffprobe gefunden', FFMPEG and FFPROBE, FFMPEG)
    hw_check()
    check('x264 + x265 vorhanden', HW.get('libx264') and HW.get('libx265'), {k: v for k, v in HW.items() if v})
    print('     Filter: %s' % FILTERS, flush=True)
    work = STAGE / 'selftest'
    work.mkdir(parents=True, exist_ok=True)
    srt = work / 'sub.srt'
    srt.write_text('1\n00:00:01,000 --> 00:00:03,000\nHallo Welt\n', encoding='utf-8')
    src = work / 'Testfilm.2020.German.1080p.mkv'
    r = run([FFMPEG, '-hide_banner', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=s=1280x720:r=25:d=8', '-f', 'lavfi', '-i',
             'sine=f=440:d=8', '-f', 'lavfi', '-i', 'sine=f=660:d=8', '-i', str(srt), '-map', '0', '-map', '1', '-map', '2', '-map', '3',
             '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-c:s', 'srt',
             '-metadata:s:a:0', 'language=ger', '-metadata:s:a:1', 'language=eng', '-metadata:s:s:0', 'language=ger', str(src)], timeout=120)
    check('Testvideo erzeugt', r.returncode == 0, r.stderr.decode('utf-8', 'replace')[-200:])
    e = file_entry(src)
    check('Datei prüfen (ffprobe)', e.get('w') == 1280 and len(e['tracks']['audio']) == 2 and len(e['tracks']['subs']) == 1 and not e.get('bad'),
          {k: e.get(k) for k in ('w', 'h', 'dur', 'fps', 'bad')})
    vargs = ['-c:v', 'libx265', '-preset', 'fast', '-profile:v', 'main10', '-pix_fmt', 'yuv420p10le', '-b:v', '800k', '-maxrate', '1280k',
             '-bufsize', '2560k', '-vf', 'scale=960:540:flags=lanczos']
    base = ['-i', '{IN}', '-map', '0:v:0', '-map', '0:a:0', '-map', '0:s:0', '-map_chapters', '0']
    p1 = base + vargs + ['-x265-params', 'pass=1:stats=ffpass.log', '-an', '-sn', '-f', 'null', '{NULL}']
    p2 = base + vargs + ['-x265-params', 'pass=2:stats=ffpass.log', '-c:a', 'aac', '-b:a:0', '160k', '-c:s', 'copy', '{OUT}']
    outd = work / 'out'
    j = new_job({'id': e['id'], 'passes': [p1, p2], 'outname': 'Testfilm (2020).mkv', 'outdir': str(outd)})
    with QLOCK:
        QUEUE.remove(j['id'])
    run_job(j)
    check('Umwandeln H.265 2-Pass', j['state'] == 'fertig' and Path(j['out']).is_file(), j.get('error') or j.get('out'))
    if j['state'] == 'fertig':
        o = probe(j['out'])
        check('Ergebnis lesbar', o['w'] == 960 and o['vcodec'] == 'hevc' and len(o['tracks']['audio']) == 1 and len(o['tracks']['subs']) == 1,
              {k: o.get(k) for k in ('w', 'h', 'vcodec', 'dur')})
    print('     Grafikkarten: %s' % [g['name'] + ' (' + g['kind'] + ')' for g in GPU], flush=True)
    print('     Arbeiter: %s' % [(w['slot'], w['name'], w['ok']) for w in WORKERS], flush=True)
    for slot in ('cpu', 'gpu1'):
        threading.Thread(target=worker, args=(slot,), daemon=True).start()
    fast = ['-i', '{IN}', '-map', '0:v:0', '-c:v', 'libx264', '-preset', 'ultrafast', '-an', '{OUT}']
    pj = [new_job({'id': e['id'], 'passes': [fast], 'outname': 'parallel-%s.mkv' % sl, 'outdir': str(outd), 'slot': sl}) for sl in ('cpu', 'gpu1')]
    QEVENT.set()
    both, t0 = False, time.time()
    while time.time() - t0 < 120 and any(x['state'] in ('wartet', 'läuft') for x in pj):
        both = both or all(x['state'] == 'läuft' for x in pj)
        time.sleep(0.05)
    check('Parallel umwandeln (2 Arbeiter)', all(x['state'] == 'fertig' for x in pj), [x['slot'] + ':' + x['state'] for x in pj] + ['gleichzeitig' if both else 'nacheinander'])
    tid = secrets.token_hex(4)
    TASKS[tid] = {'state': 'läuft'}
    try:
        task_vmaf(tid, e, vargs, [.5], 2)
        res = TASKS[tid]['result']
        check('Qualitäts-Messung (%s)' % res['method'], 0 < res['vmaf'] <= 100 and Path(IMGS[res['samples'][0]['after'].split('/')[-1]]).is_file(), res['vmaf'])
    except Exception as ex:  # noqa: BLE001
        check('Qualitäts-Messung', False, ex)
    TASKS[tid] = {'state': 'läuft'}
    try:
        task_abshot(tid, e, vargs, .5)
        check('Vorher/Nachher-Probe', Path(IMGS[TASKS[tid]['result']['after'].split('/')[-1]]).is_file())
    except Exception as ex:  # noqa: BLE001
        check('Vorher/Nachher-Probe', False, ex)
    if FILTERS['zscale']:
        r = run([FFMPEG, '-hide_banner', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=640x360:d=1', '-vf',
                 'format=yuv420p10le,setparams=color_primaries=bt2020:color_trc=smpte2084:colorspace=bt2020nc,' + TONEMAP,
                 '-f', 'null', '-'], timeout=60)
        check('HDR -> SDR (Tonemapping)', r.returncode == 0, r.stderr.decode('utf-8', 'replace')[-200:])
    else:
        check('HDR -> SDR (zscale fehlt)', False)
    files = scan(work)
    check('Ordner scannen', any(f['name'].endswith('.mkv') for f in files), len(files))
    check('Prüfsumme', len(quick_hash(src)) == 16)
    check('Bild-Fingerabdruck', (frame_bits(src) or '').count('1') > 10)
    p = popen(stream_cmd(e, 1, 0))
    got = p.stdout.read(200000)
    p.kill()
    check('Player-Stream', len(got) > 20000, len(got))
    d = disks()
    check('Laufwerke', bool(d), ['%s %.0f GB frei' % (x['drive'], x['free'] / 1e9) for x in d])
    print('selftest ok' if ok else 'selftest FEHLER', flush=True)
    return ok


def main():
    if '--selftest' in sys.argv:
        ok = selftest()
        shutil.rmtree(STAGE, ignore_errors=True)
        sys.exit(0 if ok else 1)
    HOME.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=hw_check, daemon=True).start()
    for slot in ('cpu', 'gpu1', 'gpu2'):
        threading.Thread(target=worker, args=(slot,), daemon=True).start()
    port = 0
    if '--port' in sys.argv:
        port = int(sys.argv[sys.argv.index('--port') + 1])
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    url = 'http://127.0.0.1:%d/#%s' % (server.server_address[1], TOKEN)
    print('%s %s läuft: %s' % (APP_NAME, VERSION, url if '--no-window' in sys.argv else url.split('#')[0]), flush=True)
    print('FFmpeg: %s' % (FFMPEG or 'NICHT GEFUNDEN'), flush=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    if '--check-native' in sys.argv:
        import webview  # noqa: F401
        if os.name == 'nt':
            from webview.platforms import winforms, edgechromium  # noqa: F401
        from webview.dom import DOMEventHandler  # noqa: F401
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

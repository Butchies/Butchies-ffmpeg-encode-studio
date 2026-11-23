"""KI-Hardware-Analyse (1.9.0): Prozessor, Arbeitsspeicher, Grafikkarten (DXGI = Reihenfolge für DirectML),
Vulkan-Geräte von stable-diffusion.cpp und freier Platz. Daraus eine Empfehlung, welche Grafikkarte die
KI-Bewegung rechnet und welche (andere) den KI-Upscaler – beide laufen dann gleichzeitig.

Nur Standardbibliothek + ctypes. Ohne Windows liefert die DXGI-Abfrage einfach eine leere Liste."""
import ctypes
import os
import re
import shutil
import sys


def gpu_kind(name, vram):
    """Eigene Grafikkarte (dgpu) oder Prozessor-Grafik (igpu) – gleiche Regel wie im Video Converter."""
    n = name.lower()
    igpu = bool(re.search(r'\d{3}m\b|radeon\(tm\) graphics|vega \d+|uhd|iris|hd graphics', n))
    dgpu = bool(re.search(r'\brx\s?\d|geforce|rtx|gtx|quadro|radeon pro|\barc\b|titan', n)) or (vram >= 3.5 and not igpu)
    return 'dgpu' if dgpu else 'igpu'


def vendor(name):
    n = name.lower()
    return 'nvidia' if re.search(r'nvidia|geforce|rtx|gtx|quadro', n) else 'amd' if re.search(r'amd|radeon', n) else \
        'intel' if 'intel' in n else 'andere'


# ---------- Windows: DXGI ----------
class _DESC1(ctypes.Structure):
    _fields_ = [('Description', ctypes.c_wchar * 128), ('VendorId', ctypes.c_uint), ('DeviceId', ctypes.c_uint),
                ('SubSysId', ctypes.c_uint), ('Revision', ctypes.c_uint), ('DedicatedVideoMemory', ctypes.c_size_t),
                ('DedicatedSystemMemory', ctypes.c_size_t), ('SharedSystemMemory', ctypes.c_size_t),
                ('LuidLow', ctypes.c_uint32), ('LuidHigh', ctypes.c_int32), ('Flags', ctypes.c_uint)]


class _GUID(ctypes.Structure):
    _fields_ = [('a', ctypes.c_uint32), ('b', ctypes.c_uint16), ('c', ctypes.c_uint16), ('d', ctypes.c_ubyte * 8)]


def _vcall(obj, index, restype, *argtypes):
    vt = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    return ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)(vt[index])


def dxgi_adapters():
    """Grafikkarten in DXGI-Reihenfolge (= device_id von DirectML). Software-Adapter werden übersprungen,
    der Index bleibt aber der echte DXGI-Index."""
    if os.name != 'nt':
        return []
    out = []
    try:
        iid = _GUID(0x770aae78, 0xf26f, 0x4dba, (ctypes.c_ubyte * 8)(0xa8, 0x29, 0x25, 0x3c, 0x83, 0xd1, 0xb3, 0x87))
        fac = ctypes.c_void_p()
        if ctypes.windll.dxgi.CreateDXGIFactory1(ctypes.byref(iid), ctypes.byref(fac)) != 0:
            return []
        enum1 = _vcall(fac, 12, ctypes.c_long, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p))
        for i in range(16):
            ad = ctypes.c_void_p()
            if enum1(fac, i, ctypes.byref(ad)) != 0:
                break
            d = _DESC1()
            _vcall(ad, 10, ctypes.c_long, ctypes.POINTER(_DESC1))(ad, ctypes.byref(d))
            _vcall(ad, 2, ctypes.c_ulong)(ad)
            if d.Flags & 2 or d.VendorId == 0x1414:          # Microsoft Basic Render / Software
                continue
            vram = round(d.DedicatedVideoMemory / 1024 ** 3, 1)
            shared = round(d.SharedSystemMemory / 1024 ** 3, 1)
            out.append({'dxgi': i, 'name': d.Description.strip(), 'vram': vram, 'shared': shared,
                        'vendor': vendor(d.Description), 'kind': gpu_kind(d.Description, vram)})
        _vcall(fac, 2, ctypes.c_ulong)(fac)
    except Exception:  # noqa: BLE001
        return out
    return out


def ram_gb():
    try:
        if os.name == 'nt':
            class MS(ctypes.Structure):
                _fields_ = [('len', ctypes.c_ulong), ('load', ctypes.c_ulong), ('total', ctypes.c_ulonglong), ('avail', ctypes.c_ulonglong),
                            ('tp', ctypes.c_ulonglong), ('ap', ctypes.c_ulonglong), ('tv', ctypes.c_ulonglong), ('av', ctypes.c_ulonglong),
                            ('ae', ctypes.c_ulonglong)]
            m = MS()
            m.len = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return round(m.total / 1024 ** 3, 1), round(m.avail / 1024 ** 3, 1)
        info = dict(ln.split(':', 1) for ln in open('/proc/meminfo') if ':' in ln)
        kb = lambda k: int(info[k].split()[0])  # noqa: E731
        return round(kb('MemTotal') / 1024 ** 2, 1), round(kb('MemAvailable') / 1024 ** 2, 1)
    except Exception:  # noqa: BLE001
        return 0, 0


def cpu_name():
    try:
        if os.name == 'nt':
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as k:
                return str(winreg.QueryValueEx(k, 'ProcessorNameString')[0]).strip()
        for ln in open('/proc/cpuinfo'):
            if ln.startswith('model name'):
                return ln.split(':', 1)[1].strip()
    except Exception:  # noqa: BLE001
        pass
    return 'Prozessor'


def gb(x):
    return ('%g' % x).replace('.', ',')


def _words(s):
    return set(w for w in re.findall(r'[a-z0-9]+', s.lower()) if w not in ('amd', 'radeon', 'tm', 'graphics', 'nvidia', 'geforce', 'intel', 'r', 'gpu'))


def match_vulkan(gpu, vulkan):
    """Vulkan-Gerät (z. B. „Vulkan0 · AMD Radeon RX 7600M XT“) zur DXGI-Grafikkarte finden."""
    best, score = None, 0
    gw = _words(gpu['name'])
    for v in vulkan:
        vw = _words(v['desc'])
        s = len(gw & vw) * 2 - len(gw ^ vw) * 0.1
        if gw & vw and s > score:
            best, score = v, s
    if best is None:
        same = [v for v in vulkan if vendor(v['desc']) == gpu['vendor']]
        if len(same) == 1:
            best = same[0]
    return best['name'] if best else ''


def analyze(vulkan, home, need_gb=8.0, bench=None):
    """Alles einsammeln und eine Empfehlung geben.
    vulkan: Liste von sd-cli --list-devices (name/desc/gpu). bench: gemessene Zeiten (optional)."""
    total, avail = ram_gb()
    gpus = dxgi_adapters()
    vk = [v for v in vulkan if v.get('gpu')]
    for g in gpus:
        g['vulkan'] = match_vulkan(g, vk)
    if not gpus:                                  # z. B. Linux-Test: nur Vulkan-Liste
        for v in vk:
            gpus.append({'dxgi': -1, 'name': v['desc'], 'vram': 0, 'shared': 0, 'vendor': vendor(v['desc']),
                         'kind': gpu_kind(v['desc'], 0), 'vulkan': v['name']})
    try:
        free = round(shutil.disk_usage(str(home)).free / 1024 ** 3, 1)
    except OSError:
        free = 0
    bench = bench or {}
    usable = [g for g in gpus if g['vulkan']]

    def speed(g):                                 # kleiner = schneller; ohne Messung nach Art + Grafikspeicher
        t = (bench.get('gen') or {}).get(g['vulkan'])
        return t if t else (0 if g['kind'] == 'dgpu' else 1000) - g['vram']

    main = min(usable, key=speed) if usable else None
    helper = None
    others = [g for g in gpus if g is not main]
    if others:
        ub = bench.get('up') or {}
        helper = min(others, key=lambda g: ub.get(str(g['dxgi'])) or (0 if g['kind'] == 'igpu' else 50) - g['vram'] / 100)
    vram = main['vram'] if main else 0
    rec = {
        'gen': main['vulkan'] if main else 'cpu',
        'gen_name': main['name'] if main else 'Prozessor',
        # Text-Teil (umT5, ~3 GB) nur bei viel Grafikspeicher mit auf die Karte, sonst Arbeitsspeicher/Prozessor
        'te': (main['vulkan'] if main and vram >= 12 else 'cpu'),
        'up': helper['dxgi'] if helper and helper['dxgi'] >= 0 else (main['dxgi'] if main and main['dxgi'] >= 0 else -1),
        'up_name': helper['name'] if helper else (main['name'] if main else 'Prozessor'),
        'parallel': bool(helper and main),
        'quality': 'good' if vram >= 11 else 'fast',
        'decode_frames': 2 if vram >= 12 else 1,
    }
    notes = []
    if not main:
        notes.append('Keine passende Grafikkarte für die KI gefunden – sie rechnet auf dem Prozessor (sehr langsam).')
    else:
        notes.append('KI-Bewegung auf „%s“%s.' % (main['name'], ' (%s GB)' % gb(main['vram']) if main['vram'] else ''))
        if rec['parallel']:
            notes.append('KI-Upscaler gleichzeitig auf „%s“ – beide Karten arbeiten parallel.' % helper['name'])
        if rec['te'] == 'cpu':
            notes.append('Der Text-Teil der KI läuft im Arbeitsspeicher, damit der Grafikspeicher für das Bild reicht.')
        if vram and vram < 11:
            notes.append('Mit %s GB Grafikspeicher ist „Schnell (832 × 480)“ am flüssigsten; „Beste Qualität“ geht, braucht aber länger.' % gb(vram))
    if total and total < 16:
        notes.append('Nur %s GB Arbeitsspeicher – bitte während der KI-Rechnung andere große Programme schließen.' % gb(total))
    if free and free < need_gb + 5:
        notes.append('Wenig freier Platz (%s GB) – das KI-Paket braucht ca. %.0f GB plus Platz für Stücke.' % (gb(free), need_gb))
    return {'cpu': cpu_name(), 'cores': os.cpu_count() or 0, 'ram': total, 'ram_free': avail, 'disk_free': free,
            'gpus': gpus, 'vulkan': vulkan, 'rec': rec, 'notes': notes, 'bench': bench,
            'platform': sys.platform}

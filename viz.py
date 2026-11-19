"""Audio-Visualizer für ffmpeg_encode Studio: 20 Stile, 5 Farbarten, freie Position/Größe.

Aufbau des FFmpeg-Filtergraphen:
  Ton -> Stil (Graustufen-Bild, hell = sichtbar) -> Leuchten -> Deckkraft/weiche Ränder
  Farbe (Verlauf/Regenbogen/Zufall/Sound) -> mit dem Graustufen-Bild als Transparenz zusammenführen -> [wv]
"""
import array
import colorsys
import math
import random
import re
import subprocess

STYLES = [
    ('wave', 'Wellenform', 'Welle'), ('line', 'Feine Linie', 'Linie'), ('neon', 'Neon-Welle mit Leuchten', 'Neon'),
    ('dots', 'Punkte-Welle', 'Punkte'), ('strokes', 'Strich-Welle', 'Striche'), ('bundle', 'Wellenbündel', 'Bündel'),
    ('bars', 'Spektrum-Balken', 'Balken'), ('thin', 'Feine Spektrum-Striche', 'Fein'), ('specline', 'Spektrum-Linie', 'Kurve'),
    ('mirror', 'Spiegel-Spektrum (Mitte)', 'Spiegel'), ('reflect', 'Balken mit Bodenspiegelung', 'Boden'),
    ('centerbars', 'Balken oben + unten', 'Oben/Unten'), ('led', 'LED-Equalizer', 'LED'), ('leddots', 'LED-Punkte', 'LED-Punkte'),
    ('cqt', 'Musik-Balken (Tonleiter)', 'Tonleiter'), ('combo', 'Balken + Welle', 'Kombi'), ('spectro', 'Spektrogramm-Laufband', 'Laufband'),
    ('vu', 'VU-Meter (Pegel)', 'Pegel'), ('scope', 'Lissajous-Figur', 'Lissajous'), ('glowbars', 'Leucht-Balken', 'Leuchten'),
]
STYLE_IDS = [s[0] for s in STYLES]
MODES = ('solid', 'gradient', 'rainbow', 'random', 'sound')
WAVE_FAMILY = {'wave', 'line', 'neon', 'dots', 'strokes', 'bundle'}
# Was die KI markiert, wird immer als Welle dargestellt – 5 Formen zur Auswahl
AI_WAVES = [('neon', 'Neon'), ('wave', 'Welle'), ('line', 'Linie'), ('dots', 'Punkte'), ('bundle', 'Bündel')]
BAR_FAMILY = {'bars', 'thin', 'glowbars', 'mirror', 'centerbars', 'reflect', 'cqt'}
RAINBOW = ['#ff3b3b', '#ff9f1c', '#ffe14d', '#3ddc84', '#2ec5ff', '#5b6cff', '#c04dff']

DEFAULTS = {
    'viz': False, 'vizStyle': 'mirror', 'vizMode': 'gradient', 'vizColor': '#f5b544', 'vizColor2': '#ff5fa2', 'vizSeed': 7,
    'vizX': 10.0, 'vizY': 72.0, 'vizW': 80.0, 'vizH': 24.0, 'vizDock': 'bc',
    'vizStr': 100, 'vizAlpha': 90, 'vizGlow': 45, 'vizDens': 48, 'vizSmooth': 55, 'vizLine': 3.0,
    'vizCenter': False, 'vizFloor': False, 'vizSoft': True,
    # Markierung (gilt nur für dieses Video / Projekt, nicht für Vorlagen)
    'vizShape': 'box', 'vizMask': '', 'vizPath': [], 'vizClosed': False, 'vizBoth': True, 'vizThick': 14.0, 'vizFeather': 0.6,
    'vizAi': False, 'vizAiWave': 'neon',
}
MARK_KEYS = ('vizShape', 'vizMask', 'vizPath', 'vizClosed', 'vizBoth', 'vizThick', 'vizFeather', 'vizAi')


def effective(s):
    """KI-Markierung -> immer eine der 5 Wellenformen statt des gewählten Stils."""
    return dict(s, vizStyle=s['vizAiWave']) if s.get('vizAi') else s
LIMITS = {'vizX': (0, 95), 'vizY': (0, 98), 'vizW': (5, 100), 'vizH': (3, 100), 'vizStr': (20, 200), 'vizAlpha': (10, 100),
          'vizGlow': (0, 100), 'vizDens': (8, 128), 'vizSmooth': (0, 100), 'vizLine': (1, 10), 'vizSeed': (0, 999999),
          'vizThick': (2, 60), 'vizFeather': (0, 5)}
HEX = re.compile(r'#[0-9a-fA-F]{6}')


def clean(s, out):
    """Visualizer-Einstellungen prüfen (out = bereits bereinigte Einstellungen, wird ergänzt)."""
    for k, v in DEFAULTS.items():
        val = (s or {}).get(k, v)
        if k == 'vizPath':
            pts = []
            for q in (val if isinstance(val, list) else [])[:400]:
                try:
                    pts.append([min(max(float(q[0]), -0.2), 1.2), min(max(float(q[1]), -0.2), 1.2)])
                except (TypeError, ValueError, IndexError):
                    pass
            val = pts
        elif k in ('vizShape', 'vizMask'):
            val = str(val or '')
        elif isinstance(v, bool):
            val = bool(val)
        elif k in LIMITS:
            try:
                val = float(val)
            except (TypeError, ValueError):
                val = v
            lo, hi = LIMITS[k]
            val = min(max(val, lo), hi)
            if isinstance(v, int) and not isinstance(v, bool):
                val = int(round(val))
        out[k] = val
    if out['vizStyle'] not in STYLE_IDS:
        out['vizStyle'] = 'mirror' if out['vizStyle'] != 'wave' else 'wave'
    if out['vizMode'] not in MODES:
        out['vizMode'] = 'gradient'
    if out['vizAiWave'] not in [w[0] for w in AI_WAVES]:
        out['vizAiWave'] = 'neon'
    for k in ('vizColor', 'vizColor2'):
        if not HEX.fullmatch(str(out[k])):
            out[k] = DEFAULTS[k]
    out['vizDock'] = str(out.get('vizDock') or '')[:12]
    if out['vizShape'] not in ('box', 'mask', 'path'):
        out['vizShape'] = 'box'
    if not re.fullmatch(r'[0-9a-f]{0,32}', out['vizMask']):
        out['vizMask'] = ''
    if out['vizShape'] == 'mask' and not out['vizMask']:
        out['vizShape'] = 'box'
    if out['vizShape'] == 'path' and len(out['vizPath']) < 2:
        out['vizShape'] = 'box'
    out['vizW'] = min(out['vizW'], 100 - out['vizX'])
    out['vizH'] = min(out['vizH'], 100 - out['vizY'])
    return out


def palette(s):
    m = s['vizMode']
    if m == 'solid':
        return [s['vizColor'], s['vizColor']]
    if m == 'rainbow':
        return RAINBOW
    if m == 'random':
        r = random.Random(int(s['vizSeed']))
        base = r.random()
        hues = [base, base + 0.2 + r.random() * 0.22, base + 0.47 + r.random() * 0.25]
        return ['#%02x%02x%02x' % tuple(int(c * 255) for c in colorsys.hsv_to_rgb(h % 1, 0.82, 1.0)) for h in hues]
    return [s['vizColor'], s['vizColor2']]


def even(v):
    return max(2, int(v) // 2 * 2)


# ---------- Klang-Analyse für "Nach Sound" (reines Python, keine Zusatzbibliothek) ----------
def sound_commands(ffmpeg, audio, start, dur, run, step=0.1):
    """Liest den Song (mono, 11 kHz) und erzeugt sendcmd-Befehle: Farbton nach Klanghelligkeit
    (Nulldurchgänge ≈ hohe/tiefe Töne), Helligkeit nach Lautstärke."""
    rms, zcr = analyse(ffmpeg, audio, start, dur, run, step)
    if not rms:
        return ''
    return _sound_text(rms, zcr, step)


def loudness(ffmpeg, audio, start, dur, run, step=0.1):
    """Lautstärke-Hüllkurve 0..1 (schnell hoch, langsam runter) – für „Effekte im Takt“."""
    rms, _ = analyse(ffmpeg, audio, start, dur, run, step)
    if not rms:
        return []
    top = sorted(rms)[int(len(rms) * 0.95)] or 1
    out, lv = [], 0.0
    for a in rms:
        level = min(1.0, a / top)
        lv = level if level > lv else lv * 0.8 + level * 0.2
        out.append(lv)
    return out


_ANALYSE = {}


def analyse(ffmpeg, audio, start, dur, run, step=0.1):
    key = (str(audio), round(start, 3), round(dur, 3), step)
    if key not in _ANALYSE:
        if len(_ANALYSE) > 8:
            _ANALYSE.clear()
        _ANALYSE[key] = _analyse(ffmpeg, audio, start, dur, run, step)
    return _ANALYSE[key]


def _analyse(ffmpeg, audio, start, dur, run, step=0.1):
    rate = 11025
    args = [ffmpeg, '-v', 'error']
    if start > 0:
        args += ['-ss', '%.3f' % start]
    args += ['-t', '%.3f' % dur, '-i', str(audio), '-ac', '1', '-ar', str(rate), '-f', 's16le', '-']
    r = run(args, timeout=300)
    pcm = array.array('h')
    pcm.frombytes(r.stdout[:len(r.stdout) // 2 * 2])
    n = int(rate * step)
    rms, zcr = [], []
    for i in range(0, max(len(pcm) - n, 0) + 1, n):
        blk = pcm[i:i + n]
        if not blk:
            break
        acc = 0
        prev = blk[0]
        z = 0
        for v in blk:
            acc += v * v
            if (v >= 0) != (prev >= 0):
                z += 1
            prev = v
        rms.append(math.sqrt(acc / len(blk)) / 32768)
        zcr.append(z / len(blk))
    return rms, zcr


def _sound_text(rms, zcr, step):
    top = sorted(rms)[int(len(rms) * 0.95)] or 1
    zs = sorted(zcr)
    zlo, zhi = zs[int(len(zs) * 0.05)], zs[int(len(zs) * 0.95)] or 1
    lines, lv, hz = [], 0.0, 0.5
    for k, (a, z) in enumerate(zip(rms, zcr)):
        level = min(1.0, a / top)
        lv = level if level > lv else lv * 0.82 + level * 0.18          # schnell hoch, langsam runter
        bright = min(1.0, max(0.0, (z - zlo) / max(zhi - zlo, 1e-6)))
        hz = hz * 0.7 + bright * 0.3
        h = (hz - 0.5) * 170                                           # tief = warm, hoch = kühl
        lines.append('%.2f hue@snd h %.1f, hue@snd b %.2f, hue@snd s %.2f;' % (k * step, h, -2.2 + lv * 4.2, 0.85 + lv * 0.5))
    return '\n'.join(lines) + '\n'


# ---------- Filtergraph ----------
class G:
    def __init__(self):
        self.n = 0
        self.parts = []

    def lab(self, p='v'):
        self.n += 1
        return '[z%s%d]' % (p, self.n)

    def add(self, s):
        self.parts.append(s)


def graph(s, W, H, fps, dur, cmdfile=None, extra=None):
    """Liefert (Filter-Teile, x, y) – die Teile erzeugen aus [av] den Visualizer [wv] (mit Transparenz).
    extra: {'mask': '[2:v]'} oder {'path': {'xm': '[2:v]', 'ym': '[3:v]', 'L', 'T', 'ox', 'oy', 'bw', 'bh', 'closed'}}"""
    g = G()
    extra = extra or {}
    path = extra.get('path')
    vw, vh = even(W * s['vizW'] / 100), even(H * s['vizH'] / 100)
    ox, oy = int(W * s['vizX'] / 100), int(H * s['vizY'] / 100)
    ox, oy = min(ox, W - vw), min(oy, H - vh)
    if path:
        vw, vh = even(path['L']), even(path['T'])       # erst als gerader Streifen rendern …
    st = s['vizStyle']
    dens = int(s['vizDens'])
    avg = int(round(s['vizSmooth'] / 100 * 8))
    lp = int(9000 - s['vizSmooth'] * 75)
    th = max(1, min(10, int(round(s['vizLine'] * H / 1080))))
    if st == 'neon':
        th = max(th, int(round(3 * H / 1080)) or 1)
    glow = max(s['vizGlow'], 65) if st in ('neon', 'glowbars') else s['vizGlow']
    center = s['vizCenter'] or st == 'centerbars'
    floor = s['vizFloor'] or st == 'reflect'
    k = s['vizStr'] / 100
    vol = 'volume=%.2f' % (1.6 * k)            # Wellen: Grundverstärkung
    kf = 1.7 * k                               # Spektrum: Höhe strecken (höher rendern, unten zuschneiden)

    def stretch(w, h, rh):
        return ('crop=%d:%d:0:%d' % (w, h, rh - h)) if rh >= h else ('pad=%d:%d:0:%d:black' % (w, h, h - rh))
    src = g.lab('a')
    g.add('[av]%s%s' % (vol, src))

    def freqs(inp, w, h, count, mode='bar', gap=0.28, cqt=False):
        """Spektrum als Graustufen-Bild w×h mit 'count' Balken."""
        count = max(4, int(count))
        rh = even(h * kf)
        if cqt:
            core = 'showcqt=s=1280x%d:fps=%d:sono_h=0:bar_h=%d:axis_h=0:axis=0:bar_g=2,format=gray,scale=%d:%d:flags=area,%s' % (
                max(16, rh), fps, max(16, rh), count, rh, stretch(count, h, rh))
        else:
            core = 'showfreqs=s=%dx%d:mode=%s:ascale=cbrt:fscale=log:win_size=2048:averaging=%d:rate=%d:colors=white,format=gray,%s' % (
                count, rh, mode, avg, fps, stretch(count, h, rh))
        out = '%s%s,scale=%d:%d:flags=neighbor' % (inp, core, w, h)
        gp = int(w / count * gap)
        if gp >= 1 and mode == 'bar':
            out += ',format=yuv420p,drawgrid=w=iw/%d:h=ih+8:t=%d:c=black,format=gray' % (count, gp)
        return out

    def waves(inp, w, h, mode, thick=th):
        t = max(1, thick)
        return '%slowpass=f=%d,showwaves=s=%dx%d:mode=%s:rate=%d:scale=sqrt:draw=full:colors=white,format=gray,scale=%d:%d:flags=bicubic' % (
            inp, lp, even(w / t), even(h / t), mode, fps, w, h)

    raw = g.lab('r')
    if st in BAR_FAMILY:
        hb = even(vh * 0.7) if floor else vh
        count = dens * 2 if st == 'thin' else int(dens * 1.5) if st == 'cqt' else dens
        gap = 0.6 if st == 'thin' else 0.3
        cq = st == 'cqt'
        main = g.lab()
        if st == 'mirror':
            half = even(vw / 2)
            a, b, c = g.lab(), g.lab(), g.lab()
            g.add('%s,split=2%s%s' % (freqs(src, half, hb if not center else even(hb / 2), max(4, count // 2), gap=gap), a, b))
            g.add('%shflip%s' % (b, c))
            g.add('%s%shstack,scale=%d:%d%s' % (c, a, vw, hb if not center else even(hb / 2), main))
        else:
            g.add('%s%s' % (freqs(src, vw, hb if not center else even(hb / 2), count, gap=gap, cqt=cq), main))
        if center:
            a, b, c, m2 = g.lab(), g.lab(), g.lab(), g.lab()
            g.add('%ssplit=2%s%s' % (main, a, b))
            g.add('%svflip%s' % (b, c))
            g.add('%s%svstack,scale=%d:%d%s' % (a, c, vw, hb, m2))
            main = m2
        if floor:
            a, b, c = g.lab(), g.lab(), g.lab()
            g.add('%ssplit=2%s%s' % (main, a, b))
            g.add("%svflip,scale=%d:%d,lut=c0='val*0.3'%s" % (b, vw, vh - hb, c))
            g.add('%s%svstack%s' % (a, c, raw))
        else:
            g.add('%snull%s' % (main, raw))
    elif st in ('led', 'leddots'):
        cols = max(10, int(dens * 0.8))
        rows = max(6, min(24, int(vh / max(vw / cols, 1)))) if st == 'leddots' else max(6, min(20, int(vh / 14)))
        grid = g.lab()
        rh = even(rows * 8 * kf)
        g.add("%sshowfreqs=s=%dx%d:mode=bar:ascale=cbrt:fscale=log:win_size=2048:averaging=%d:rate=%d:colors=white,format=gray,%s,"
              "scale=%d:%d:flags=area,lut=c0='if(gt(val,70),255,18)',scale=%d:%d:flags=neighbor%s" % (
                  src, cols, rh, avg, fps, stretch(cols, rows * 8, rh), cols, rows, vw, vh, grid))
        if st == 'led':
            g.add('%sformat=yuv420p,drawgrid=w=iw/%d:h=ih/%d:t=%d:c=black,format=gray%s' % (
                grid, cols, rows, max(1, int(min(vw / cols, vh / rows) * 0.22)), raw))
        else:
            cw, ch = vw / cols, vh / rows
            rad = min(cw, ch) * 0.38
            mask = g.lab('m')
            g.add("color=c=black:s=%dx%d:r=%d:d=1,format=gray,geq=lum='255*lte(hypot(mod(X\\,%.3f)-%.3f\\,mod(Y\\,%.3f)-%.3f)\\,%.3f)',"
                  "trim=end_frame=1,loop=loop=-1:size=1,setpts=N/%d/TB,trim=duration=%.3f%s" % (vw, vh, fps, cw, cw / 2, ch, ch / 2, rad, fps, dur + 1, mask))
            g.add('%s%sblend=all_mode=multiply:shortest=1%s' % (grid, mask, raw))
    elif st == 'vu':
        chh = max(6, even(vh / 2) - 4)
        g.add('%sshowvolume=r=%d:w=%d:h=%d:b=4:t=0:v=0:f=0.85:ds=lin,format=gray,scale=%d:%d,'
              'lut=c0=\'if(gt(val,8),255,0)\',format=yuv420p,drawgrid=w=iw/%d:h=ih+8:t=%d:c=black,format=gray%s' % (
                  src, fps, vw, chh, vw, vh, max(8, dens // 2), max(1, int(vw / max(8, dens // 2) * 0.2)), raw))
    elif st == 'spectro':
        g.add('%sshowspectrum=s=%dx%d:mode=combined:slide=scroll:color=intensity:scale=cbrt:fscale=log:legend=0,format=gray,fps=%d%s' % (
            src, vw, vh, fps, raw))
    elif st == 'scope':
        sq = even(min(vw, vh))
        g.add('%savectorscope=s=%dx%d:mode=lissajous_xy:draw=line:zoom=1.3:rc=255:gc=255:bc=255:ac=255:rf=40:gf=40:bf=40:af=40:rate=%d,'
              'format=gray,pad=%d:%d:(ow-iw)/2:(oh-ih)/2:black%s' % (src, sq, sq, fps, vw, vh, raw))
    elif st == 'combo':
        hb = even(vh * 0.68)
        a, b, t1, t2, t3, bot = g.lab(), g.lab(), g.lab(), g.lab(), g.lab(), g.lab()
        g.add('%sasplit=2%s%s' % (src, a, b))
        half = even(vw / 2)
        g.add('%s,split=2%s%s' % (freqs(a, half, hb, max(4, dens // 2)), t1, t2))
        g.add('%shflip%s' % (t2, t3))
        g.add('%s%shstack,scale=%d:%d[zcombotop]' % (t3, t1, vw, hb))
        g.add('%s%s' % (waves(b, vw, vh - hb, 'p2p'), bot))
        g.add('[zcombotop]%svstack%s' % (bot, raw))
    elif st == 'bundle':
        outs = []
        labs = [g.lab('b') for _ in range(5)]
        g.add('%sasplit=5%s' % (src, ''.join(labs)))
        for k, lb in enumerate(labs):
            o = g.lab()
            g.add("%sadelay=%d|%d,volume=%.2f,%s,lut=c0='val*%.2f'%s" % (
                lb, k * 35 + 1, k * 35 + 1, 1 - k * 0.13, waves('', vw, vh, 'p2p')[0:], 1 - k * 0.16, o))
            outs.append(o)
        cur = outs[0]
        for k, o in enumerate(outs[1:]):
            nx = g.lab() if k < len(outs) - 2 else raw
            g.add('%s%sblend=all_mode=lighten:shortest=1%s' % (cur, o, nx))
            cur = nx
    elif st == 'strokes':
        cols = max(8, int(dens * 1.4))
        g.add('%slowpass=f=%d,showwaves=s=%dx%d:mode=cline:rate=%d:scale=sqrt:draw=full:colors=white,format=gray,scale=%d:%d:flags=neighbor,'
              'format=yuv420p,drawgrid=w=iw/%d:h=ih+8:t=%d:c=black,format=gray%s' % (
                  src, lp, cols, vh, fps, vw, vh, cols, max(1, int(vw / cols * 0.55)), raw))
    elif st == 'specline':
        t = max(1, th)
        lw, lh = even(vw / t), even(vh / t)
        g.add('%sshowfreqs=s=%dx%d:mode=line:ascale=cbrt:fscale=log:win_size=2048:averaging=%d:rate=%d:colors=white,format=gray,%s,scale=%d:%d:flags=bicubic%s' % (
            src, lw, even(lh * kf), max(1, avg), fps, stretch(lw, lh, even(lh * kf)), vw, vh, raw))
    else:   # wave, line, neon, dots
        mode = {'wave': 'cline', 'line': 'p2p', 'neon': 'p2p', 'dots': 'point'}.get(st, 'cline')
        g.add('%s%s' % (waves(src, vw, vh, mode, 1 if st == 'wave' else th), raw))

    cur = raw
    if path:                                              # … dann entlang der Linie / des Rings biegen
        if s['vizSoft'] and not path['closed']:
            sm, tmp = g.lab('m'), g.lab()
            e = max(2, vw * 0.08)
            g.add("color=c=black:s=%dx%d:r=%d:d=1,format=gray,geq=lum='255*min(1\\,min(X\\,W-1-X)/%.2f)',"
                  "trim=end_frame=1,loop=loop=-1:size=1,setpts=N/%d/TB,trim=duration=%.3f%s" % (vw, vh, fps, e, fps, dur + 1, sm))
            g.add('%s%sblend=all_mode=multiply:shortest=1%s' % (cur, sm, tmp))
            cur = tmp
        xm, ym, bent = g.lab('x'), g.lab('y'), g.lab()
        for src_lab, dst in ((path['xm'], xm), (path['ym'], ym)):
            g.add('%sloop=loop=-1:size=1,setpts=N/%d/TB,trim=duration=%.3f,format=gray16%s' % (src_lab, fps, dur + 1, dst))
        g.add('%s%s%sremap=fill=black,format=gray%s' % (cur, xm, ym, bent))
        cur = bent
        vw, vh, ox, oy = path['bw'], path['bh'], path['ox'], path['oy']
    # Leuchten
    if glow > 0:
        a, b, c, d = g.lab(), g.lab(), g.lab(), g.lab()
        g.add('%ssplit=2%s%s' % (cur, a, b))
        sig = 1 + glow / 100 * max(vh, 40) / 16
        gain = 1.2 + glow / 100 * 1.6
        cap = int(70 + glow * 0.9)                      # Schein höchstens ~60 % deckend
        g.add("%sgblur=sigma=%.1f,lut=c0='min(val*%.2f\\,%d)'%s" % (b, sig, gain, cap, c))
        g.add('%s%sblend=all_mode=lighten:shortest=1%s' % (a, c, d))
        cur = d
    # Deckkraft + weiche Ränder -> Alpha
    alpha = g.lab('al')
    chain = "%slut=c0='val*%.2f'" % (cur, s['vizAlpha'] / 100)
    if s['vizSoft'] and not path and not extra.get('mask'):
        sm = g.lab('m')
        e = max(2, vw * 0.12)
        g.add("color=c=black:s=%dx%d:r=%d:d=1,format=gray,geq=lum='255*min(1\\,min(X\\,W-1-X)/%.2f)',"
              "trim=end_frame=1,loop=loop=-1:size=1,setpts=N/%d/TB,trim=duration=%.3f%s" % (vw, vh, fps, e, fps, dur + 1, sm))
        tmp = g.lab()
        g.add('%s%s' % (chain, tmp))
        g.add('%s%sblend=all_mode=multiply:shortest=1%s' % (tmp, sm, alpha))
    else:
        g.add('%s%s' % (chain, alpha))
    # Farbe
    cols = palette(s)
    cs = ':'.join('c%d=0x%s' % (i, c[1:]) for i, c in enumerate(cols[:8]))
    hue = ''
    if s['vizMode'] == 'random':
        hue = ',hue=H=2*PI*t/24'
    elif s['vizMode'] == 'sound' and cmdfile:
        hue = ',sendcmd=f=%s,hue@snd=h=0:b=0:s=1' % cmdfile
    col = g.lab('c')
    g.add('gradients=s=%dx%d:%s:nb_colors=%d:x0=0:y0=0:x1=%d:y1=0:r=%d:d=1:speed=0.00001,trim=end_frame=1,'
          'loop=loop=-1:size=1,setpts=N/%d/TB,trim=duration=%.3f,format=yuv420p%s%s' % (
              vw, vh, cs, max(2, len(cols[:8])), vw, fps, fps, dur + 1, hue, col))
    if extra.get('mask'):                                 # nur innerhalb der markierten Fläche
        mk, al2 = g.lab('k'), g.lab('al')
        g.add('%sloop=loop=-1:size=1,setpts=N/%d/TB,trim=duration=%.3f,format=gray,scale=%d:%d%s' % (extra['mask'], fps, dur + 1, vw, vh, mk))
        g.add('%s%sblend=all_mode=multiply:shortest=1%s' % (alpha, mk, al2))
        alpha = al2
    g.add('%s%salphamerge,format=yuva420p[wv]' % (col, alpha))
    return g.parts, ox, oy

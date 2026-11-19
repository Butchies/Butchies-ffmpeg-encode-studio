"""Erzeugt icon.ico, ui/icon.svg und die Installer-Bilder (Neon-Ringe + Play, Farben Gold Lounge)."""
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
A, B, BG = (245, 181, 68), (255, 223, 138), (13, 10, 5)


def lerp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def logo(size, bg=True):
    S = size * 4
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if bg:
        d.rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * .22), fill=BG + (255,))
    glow = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx = cy = S / 2
    for k, (r, w, start) in enumerate(((.40, .045, 0), (.31, .035, 140), (.22, .03, 260))):
        R = S * r
        steps = 180
        for i in range(steps):
            t = i / steps
            if t > .78:
                continue
            a0 = math.radians(start + t * 360)
            col = lerp(A, B, abs(math.sin(t * math.pi))) + (int(255 * (1 - t * .9)),)
            box = [cx - R, cy - R, cx + R, cy + R]
            d.arc(box, math.degrees(a0), math.degrees(a0) + 2.4, fill=col, width=max(1, int(S * w)))
            if k == 0:
                gd.arc(box, math.degrees(a0), math.degrees(a0) + 2.4, fill=A + (140,), width=int(S * w * 2.2))
    glow = glow.filter(ImageFilter.GaussianBlur(S * .03))
    im = Image.alpha_composite(im, glow) if not bg else Image.alpha_composite(im, glow)
    d = ImageDraw.Draw(im)
    p = S * .13
    d.polygon([(cx - p * .8, cy - p), (cx - p * .8, cy + p), (cx + p * 1.05, cy)], fill=B + (255,))
    return im.resize((size, size), Image.LANCZOS)


def main():
    big = logo(256)
    big.save(ROOT / 'icon.ico', sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    logo(512).save(ROOT / 'tools' / 'icon-512.png')
    # Installer-Seitenbild 164x314 (bei 100 %) – doppelt groß für scharfe Darstellung
    side = Image.new('RGB', (328, 628), BG)
    sd = ImageDraw.Draw(side)
    for y in range(628):
        sd.line([(0, y), (328, y)], fill=lerp((31, 23, 8), BG, y / 628))
    lg = logo(220, bg=False)
    side.paste(lg, (54, 120), lg)
    try:
        f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 30)
        f2 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 19)
    except OSError:
        f = f2 = ImageFont.load_default()
    sd.text((164, 400), 'ffmpeg_encode', font=f, fill=B, anchor='mm')
    sd.text((164, 438), 'Studio', font=f, fill=A, anchor='mm')
    sd.text((164, 500), 'MP3 + Bild → YouTube', font=f2, fill=(201, 185, 145), anchor='mm')
    side.save(ROOT / 'installer-side.bmp')
    small = Image.new('RGB', (110, 110), BG)
    s2 = logo(110)
    small.paste(s2, (0, 0), s2)
    small.save(ROOT / 'installer-small.bmp')


if __name__ == '__main__':
    main()

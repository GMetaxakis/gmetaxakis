#!/usr/bin/env python3
"""Turn a background-removed portrait (RGBA PNG) into manga ink.

    python3 scripts/ink_portrait.py path/to/cutout.png [out.png] [--scale 2]

--scale upsamples the photo first (and scales line/dot sizes with it) for bigger output,
e.g. a profile picture. Default output: assets/manga/portrait-ink.png at scale 1.

Only the inked result goes in the repo; the photo stays wherever you keep it.
Output: 3-colour PNG (paper / ink / transparent) with screentone shading.
"""
import math
import sys
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent.parent

# luminance cut points (after auto-contrast) → ink, dark tone, light tone, paper
CUTS = (0.13, 0.30, 0.52)
TONE = {3: 0.55, 2: 0.22}   # dot coverage for dark / light tone
PERIOD = 7                  # screentone cell size in source pixels
EDGE = 38                   # sobel magnitude threshold for line art


def sobel(gray):
    kx = ImageFilter.Kernel((3, 3), [-1, 0, 1, -2, 0, 2, -1, 0, 1], scale=1, offset=128)
    ky = ImageFilter.Kernel((3, 3), [-1, -2, -1, 0, 0, 0, 1, 2, 1], scale=1, offset=128)
    gx, gy = gray.filter(kx).load(), gray.filter(ky).load()
    w, h = gray.size
    out = Image.new("L", (w, h))
    op = out.load()
    for y in range(h):
        for x in range(w):
            op[x, y] = min(255, int(math.hypot(gx[x, y] - 128, gy[x, y] - 128)))
    return out


def odd(n):
    n = max(3, round(n))
    return n if n % 2 else n + 1


def ink(src, dst, k=1.0):
    im = Image.open(src).convert("RGBA")
    if k != 1:
        im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    period = PERIOD * k
    alpha = im.getchannel("A").point(lambda a: 255 if a > 128 else 0)
    gray = ImageOps.autocontrast(im.convert("L"), cutoff=1, mask=alpha)
    smooth = gray.filter(ImageFilter.GaussianBlur(2 * k))
    w, h = im.size

    # posterise, then clean speckles with a median pass on the level map
    sp = smooth.load()
    lv_img = Image.new("L", (w, h))
    lp = lv_img.load()
    for y in range(h):
        for x in range(w):
            v = sp[x, y] / 255
            lp[x, y] = 4 if v < CUTS[0] else 3 if v < CUTS[1] else 2 if v < CUTS[2] else 1
    lp = lv_img.filter(ImageFilter.ModeFilter(odd(5 * k))).load()

    edges = sobel(gray.filter(ImageFilter.GaussianBlur(1.4 * k))).point(lambda v: 255 if v > EDGE / k else 0)
    edges = edges.filter(ImageFilter.MedianFilter(odd(3 * k)))
    # silhouette outline
    sil = alpha.filter(ImageFilter.MaxFilter(odd(5 * k))).point(lambda v: 255 if v else 0)
    inner = alpha.filter(ImageFilter.MinFilter(odd(3 * k)))
    ep, ap, sp_, ip = edges.load(), alpha.load(), sil.load(), inner.load()

    out = Image.new("P", (w, h), 2)
    out.putpalette([255, 255, 255, 17, 17, 17, 0, 0, 0] + [0] * 759)
    op = out.load()
    half, s2 = period / 2, math.sqrt(2)
    for y in range(h):
        for x in range(w):
            if not ap[x, y]:
                # outline only where the subject meets real background, not the photo's crop edge
                if sp_[x, y] and 2 * k < x < w - 3 * k and 2 * k < y < h - 3 * k:
                    op[x, y] = 1
                continue
            if not ip[x, y] or ep[x, y]:
                op[x, y] = 1
                continue
            v = lp[x, y]
            if v == 4:
                op[x, y] = 1
            elif v == 1:
                op[x, y] = 0
            else:
                u, t = (x + y) / s2, (x - y) / s2
                d = math.hypot((u % period) - half, (t % period) - half) / half
                op[x, y] = 1 if d < math.sqrt(TONE[v]) * 1.05 else 0
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    out.save(dst, "PNG", transparency=2, optimize=True)
    print(f"wrote {dst} ({w}x{h}, {Path(dst).stat().st_size // 1024} KB)")


if __name__ == "__main__":
    args, scale = sys.argv[1:], 1.0
    if "--scale" in args:
        i = args.index("--scale")
        scale = float(args[i + 1])
        del args[i:i + 2]
    ink(args[0], args[1] if len(args) > 1 else ROOT / "assets/manga/portrait-ink.png", scale)

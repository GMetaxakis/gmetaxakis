#!/usr/bin/env python3
"""Compose the GitHub profile picture from a high-res inked portrait.

    python3 scripts/ink_portrait.py cutout.png /tmp/ink-2x.png --scale 2
    python3 scripts/make_avatar.py /tmp/ink-2x.png [assets/manga/github-avatar.png]

GitHub crops avatars to a circle, so everything that matters stays inside it.
Upload the result by hand: github.com/settings/profile → Profile picture → Edit.
"""
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SIZE, SS = 800, 2            # output size, supersampling factor
INK, RED = (17, 17, 17), (224, 16, 30)
# where the face sits in the 2x ink, where it goes in the output (px), and output px per ink px.
# The ink's right edge is the photo's crop edge; it disappears under the name strip.
FACE_IN, FACE_OUT, ZOOM = (560, 800), (292, 452), 0.59
STRIP_X = 534                # name strip starts here (output px)
SEAL_FONTS = ["/System/Library/Fonts/ヒラギノ角ゴシック W9.ttc",
              "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"]


def focus_lines(draw, cx, cy, r_min, r_max, n, seed, outer):
    rnd = random.Random(seed)
    for i in range(n):
        a = (i + rnd.uniform(-0.4, 0.4)) * 2 * math.pi / n
        w = rnd.uniform(0.003, 0.014)
        r = rnd.uniform(r_min, r_max)
        draw.polygon([(cx + r * math.cos(a), cy + r * math.sin(a)),
                      (cx + outer * math.cos(a - w), cy + outer * math.sin(a - w)),
                      (cx + outer * math.cos(a + w), cy + outer * math.sin(a + w))], fill=INK)


def seal(text, size):
    """Red hanko with white glyphs, stacked vertically."""
    font = next((ImageFont.truetype(f, int(size * 0.36)) for f in SEAL_FONTS if Path(f).exists()), None)
    w, h = int(size * 0.8), size
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=size // 10, fill=RED)
    m = size // 14
    d.rounded_rectangle((m, m, w - 1 - m, h - 1 - m), radius=size // 16, outline="white", width=max(2, size // 40))
    if font:
        for i, ch in enumerate(text):
            d.text((w / 2, h * (0.3 + 0.4 * i)), ch, font=font, fill="white", anchor="mm")
    return im.rotate(8, resample=Image.BICUBIC, expand=True)


def main(src, dst):
    S = SIZE * SS
    canvas = Image.new("RGB", (S, S), "white")
    d = ImageDraw.Draw(canvas)
    fx, fy = FACE_OUT[0] * SS, FACE_OUT[1] * SS
    d.ellipse((fx - S * 0.4, fy - S * 0.42, fx - S * 0.02, fy - S * 0.04), fill=RED)   # red sun behind the head
    focus_lines(d, fx, fy, S * 0.33, S * 0.42, 150, 3, S * 1.5)

    ink = Image.open(src).convert("RGBA")
    z = ZOOM * SS
    ink = ink.resize((round(ink.width * z), round(ink.height * z)), Image.LANCZOS)
    canvas.paste(ink, (round(fx - FACE_IN[0] * z), round(fy - FACE_IN[1] * z)), ink)

    # vertical name strip (hides the photo edge), like the profile's title page
    sx = STRIP_X * SS
    d.polygon([(sx + 14 * SS, 0), (S, 0), (S, S), (sx, S)], fill=INK)
    d.line([(sx + 14 * SS - 6 * SS, 0), (sx - 6 * SS, S)], fill="white", width=5 * SS)
    font = next((ImageFont.truetype(f, int(S * 0.078)) for f in SEAL_FONTS if Path(f).exists()), None)
    if font:
        name = "ゲオルギオス"
        step = S * 0.09
        for i, ch in enumerate(name):
            d.text((sx + (S - sx) * 0.42, S / 2 + (i - (len(name) - 1) / 2) * step), ch,
                   font=font, fill="white", anchor="mm")

    st = seal("押忍", int(S * 0.17))
    canvas.paste(st, (int(S * 0.1), int(S * 0.6)), st)

    out = canvas.resize((SIZE, SIZE), Image.LANCZOS)
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    out.save(dst, optimize=True)
    print(f"wrote {dst} ({SIZE}x{SIZE}, {Path(dst).stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else ROOT / "assets/manga/github-avatar.png")

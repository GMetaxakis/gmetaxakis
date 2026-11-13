#!/usr/bin/env python3
"""Generate the manga-style profile panels (SVG) from profile.config.json.

    python3 scripts/gen_profile.py              # write assets/manga/*.svg + README.md
    python3 scripts/gen_profile.py --jp-chars   # list the Japanese glyphs in use

Requires Pillow (text measuring). The portrait is inked once by scripts/ink_portrait.py. Fonts are pre-subset in
scripts/fonts and embedded into each SVG so the panels look the same everywhere.
If you add new Japanese text, re-subset NotoSansJP (see scripts/fonts/README.md).
"""
import base64
import json
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "scripts" / "fonts"
OUT = ROOT / "assets" / "manga"
CFG = json.loads((ROOT / "profile.config.json").read_text())

INK, PAPER, RED = "#111", "#fff", "#e0101e"

FONT_FILES = {
    "Bng": "Bangers-Regular.subset.woff2",
    "Cmc": "ComicNeue-Bold.subset.woff2",
    "MJP": "NotoSansJP-Black.subset.woff2",
}
FAMILY = {
    "Bng": "Bng,Impact,'Arial Black',sans-serif",
    "Cmc": "Cmc,'Comic Sans MS','Chalkboard SE',sans-serif",
    "MJP": "MJP,'Hiragino Sans','Noto Sans JP','Yu Gothic',sans-serif",
}
_pil_fonts = {}


def measure(text, font, size, ls=0):
    """Advance width in px; `ls` is the SVG letter-spacing applied to the text."""
    return _measure(text, font, size) + ls * len(text)


def _measure(text, font, size):
    key = (font, size)
    if key not in _pil_fonts:
        _pil_fonts[key] = ImageFont.truetype(str(FONTS / FONT_FILES[font]), size)
    return _pil_fonts[key].getlength(text)


def wrap(text, font, size, width):
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if cur and measure(trial, font, size) > width:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + [cur] if cur else lines


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, s, font, size, fill=INK, anchor="start", extra=""):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FAMILY[font]}" font-size="{size}" '
            f'fill="{fill}" text-anchor="{anchor}" {extra}>{esc(s)}</text>')


def text_lines(x, y, lines, font, size, lh, **kw):
    return "".join(text(x, y + i * lh, ln, font, size, **kw) for i, ln in enumerate(lines))


def sfx(x, y, s, size, rot=-10, fill=INK, stroke=PAPER, sw=None, cls="shake", delay=0):
    """Manga sound effect: heavy JP glyphs with a thick paper outline."""
    sw = sw or size * 0.16
    t = text(0, 0, s, "MJP", size, fill=fill, anchor="middle",
             extra=f'stroke="{stroke}" stroke-width="{sw:.1f}" stroke-linejoin="round" paint-order="stroke"')
    return (f'<g transform="translate({x},{y}) rotate({rot})"><g class="{cls}" '
            f'style="animation-delay:{delay}s">{t}</g></g>')


# ---------------------------------------------------------------- drawing bits

def focus_lines(cx, cy, r_min, r_max, n, seed, outer=900):
    """集中線: thin ink wedges converging on a point."""
    rnd = random.Random(seed)
    parts = []
    for i in range(n):
        a = (i + rnd.uniform(-0.4, 0.4)) * 2 * math.pi / n
        w = rnd.uniform(0.003, 0.016)
        r = rnd.uniform(r_min, r_max)
        tip = (cx + r * math.cos(a), cy + r * math.sin(a))
        b1 = (cx + outer * math.cos(a - w), cy + outer * math.sin(a - w))
        b2 = (cx + outer * math.cos(a + w), cy + outer * math.sin(a + w))
        parts.append("M{:.1f},{:.1f}L{:.1f},{:.1f}L{:.1f},{:.1f}Z".format(*tip, *b1, *b2))
    return "".join(parts)


def speed_lines(x0, x1, y0, y1, n, seed):
    """Horizontal action lines."""
    rnd = random.Random(seed)
    parts = []
    for _ in range(n):
        y = rnd.uniform(y0, y1)
        h = rnd.uniform(0.6, 3.2)
        a = rnd.uniform(x0, x0 + (x1 - x0) * 0.45)
        b = rnd.uniform(a + 80, x1)
        parts.append(f"M{a:.1f},{y:.1f}L{b:.1f},{y - h / 2:.1f}L{b:.1f},{y + h / 2:.1f}Z")
    return "".join(parts)


def burst(cx, cy, r_in, r_out, spikes, seed):
    rnd = random.Random(seed)
    pts = []
    for i in range(spikes * 2):
        a = i * math.pi / spikes
        r = rnd.uniform(r_out * 0.8, r_out) if i % 2 == 0 else rnd.uniform(r_in * 0.85, r_in)
        pts.append(f"{cx + r * math.cos(a):.1f},{cy + r * math.sin(a):.1f}")
    return " ".join(pts)


def bubble(cx, cy, rx, ry, tail):
    """Speech balloon (ellipse + tail toward `tail`), as one path so the outline is clean."""
    ang = math.atan2(tail[1] - cy, tail[0] - cx)
    sp = 0.22
    p1 = (cx + rx * math.cos(ang - sp), cy + ry * math.sin(ang - sp))
    p2 = (cx + rx * math.cos(ang + sp), cy + ry * math.sin(ang + sp))
    return (f'<path d="M{p2[0]:.1f},{p2[1]:.1f} A{rx},{ry} 0 1 1 {p1[0]:.1f},{p1[1]:.1f} '
            f'L{tail[0]:.1f},{tail[1]:.1f} Z" fill="{PAPER}" stroke="{INK}" stroke-width="3" '
            f'stroke-linejoin="round"/>')


def caption_box(x, y, w, lines, size=17, lh=21, pad=10, font="Cmc", shadow=True):
    """Narration box: square, inked border, hard offset shadow."""
    h = pad * 2 + lh * len(lines) - (lh - size)
    out = ""
    if shadow:
        out += f'<rect x="{x + 5}" y="{y + 5}" width="{w}" height="{h}" fill="{INK}"/>'
    out += f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{PAPER}" stroke="{INK}" stroke-width="3"/>'
    out += text_lines(x + pad, y + pad + size * 0.85, lines, font, size, lh)
    return out, h


def tag(x, y, label, jp=None, size=20, bg=INK, fg=PAPER):
    """Chapter label, optional JP prefix."""
    w_jp = (size * 0.85 * len(jp) + 8) if jp else 0
    w = w_jp + measure(label, "Bng", size, ls=1) + 20
    out = f'<rect x="{x}" y="{y}" width="{w:.0f}" height="{size + 12}" fill="{bg}"/>'
    if jp:
        out += text(x + 10, y + size + 2, jp, "MJP", round(size * 0.85), fill=fg)
    out += text(x + 10 + w_jp, y + size + 4, label, "Bng", size, fill=fg, extra='letter-spacing="1"')
    return out


def panel(points, fill=PAPER):
    pts = " ".join(f"{x},{y}" for x, y in points)
    return f'<polygon points="{pts}" fill="{fill}" stroke="{INK}" stroke-width="4" stroke-linejoin="miter"/>'


def clip(cid, points):
    pts = " ".join(f"{x},{y}" for x, y in points)
    return f'<clipPath id="{cid}"><polygon points="{pts}"/></clipPath>'


SCREENTONE = (
    '<pattern id="tone" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
    f'<circle cx="3.5" cy="3.5" r="1.5" fill="{INK}"/></pattern>'
    '<pattern id="toneL" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
    f'<circle cx="3.5" cy="3.5" r="0.9" fill="{INK}"/></pattern>'
    '<linearGradient id="gR" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
    '<stop offset=".8" stop-color="#fff"/></linearGradient>'
    '<linearGradient id="gD" x1="0" y1="0" x2=".35" y2="1"><stop offset="0" stop-color="#fff"/>'
    '<stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
    '<mask id="fadeR" maskContentUnits="objectBoundingBox"><rect width="1" height="1" fill="url(#gR)"/></mask>'
    '<mask id="fadeD" maskContentUnits="objectBoundingBox"><rect width="1" height="1" fill="url(#gD)"/></mask>'
)

STYLE = """
.pop{transform-box:fill-box;transform-origin:center;animation:pop .45s cubic-bezier(.2,1.6,.4,1) both}
@keyframes pop{0%{transform:scale(0);opacity:0}100%{transform:scale(1);opacity:1}}
.inR{animation:inR .4s cubic-bezier(.2,1.3,.4,1) both}
@keyframes inR{from{transform:translateX(60px);opacity:0}to{transform:none;opacity:1}}
.stamp{transform-box:fill-box;transform-origin:center;animation:stamp .3s cubic-bezier(.3,1.4,.5,1) both}
@keyframes stamp{0%{transform:scale(3.2) rotate(-30deg);opacity:0}100%{transform:none;opacity:1}}
.shake{transform-box:fill-box;transform-origin:center;animation:shake .5s steps(1) infinite}
@keyframes shake{0%{transform:translate(0,0)}25%{transform:translate(1.5px,-1px)}50%{transform:translate(-1px,1px)}75%{transform:translate(1px,1px)}}
.flA{animation:fl .3s steps(1) infinite}
.flB{animation:fl .3s steps(1) infinite;animation-delay:-.15s}
@keyframes fl{0%{opacity:1}50%{opacity:0}}
.zoom{transform-box:fill-box;transform-origin:center;animation:zoom .6s ease-out both}
@keyframes zoom{from{transform:scale(1.25);opacity:0}to{transform:none;opacity:1}}
.fade{animation:fade .5s ease-out both}
@keyframes fade{from{opacity:0}to{opacity:1}}
@media (prefers-reduced-motion:reduce){*{animation-duration:0s!important;animation-iteration-count:1!important;animation-delay:0s!important}}
"""


def font_css(used):
    rules = []
    for fam in used:
        data = base64.b64encode((FONTS / FONT_FILES[fam]).read_bytes()).decode()
        rules.append(f"@font-face{{font-family:{fam};src:url(data:font/woff2;base64,{data}) format('woff2')}}")
    return "".join(rules)


def svg(w, h, label, defs, body, paper=True):
    fonts = [f for f in FONT_FILES if f'font-family="{FAMILY[f]}"' in body]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'role="img" aria-label="{esc(label)}"><title>{esc(label)}</title>'
            f'<style>{font_css(fonts)}{STYLE}</style><defs>{SCREENTONE}{defs}</defs>'
            + (f'<rect width="{w}" height="{h}" fill="{PAPER}"/>' if paper else "") + f'{body}</svg>')


# ---------------------------------------------------------------- panels

def hero():
    W, H = 900, 400
    A = [(10, 10), (476, 10), (452, 390), (10, 390)]
    B = [(488, 10), (890, 10), (890, 390), (464, 390)]
    # inked portrait made by scripts/ink_portrait.py; its right/bottom edges are the photo crop,
    # so anchor it to the panel's bottom-right and let the clip hide them
    portrait = ROOT / CFG["portrait"]
    png = portrait.read_bytes()
    aw, ah = Image.open(portrait).size
    disp_h = 384
    disp_w = aw * disp_h / ah
    ax, ay = 458 - disp_w, 8
    cx, cy = ax + disp_w * 0.6, ay + disp_h * 0.6

    defs = clip("cA", A) + clip("cB", B)
    b = []
    # Panel A: focus lines + inked avatar + balloon
    b.append(panel(A))
    b.append('<g clip-path="url(#cA)">')
    b.append(f'<path class="flA" d="{focus_lines(cx, cy, 170, 245, 120, 1)}" fill="{INK}"/>')
    b.append(f'<path class="flB" d="{focus_lines(cx, cy, 170, 245, 120, 2)}" fill="{INK}"/>')
    img = base64.b64encode(png).decode()
    b.append(f'<g class="zoom"><image href="data:image/png;base64,{img}" x="{ax:.1f}" y="{ay}" '
             f'width="{disp_w:.1f}" height="{disp_h}" style="image-rendering:auto"/></g>')
    b.append('</g>')
    b.append(panel(A, fill="none"))
    bub = CFG["hero_bubble"]
    b.append('<g class="pop" style="animation-delay:.5s">')
    b.append(bubble(112, 66, 86, 36, (205, 150)))
    b.append(text(112, 75, bub.upper(), "Bng", 27, anchor="middle", extra='letter-spacing="0.5"'))
    b.append('</g>')

    # Panel B: title page
    b.append(panel(B))
    b.append('<g clip-path="url(#cB)">')
    b.append(f'<rect x="452" y="10" width="440" height="140" fill="url(#tone)" mask="url(#fadeD)" opacity=".5"/>')
    # vertical katakana strip
    b.append(f'<rect x="842" y="10" width="48" height="380" fill="{INK}"/>')
    jp = CFG["name_jp"]
    y0 = 200 - (len(jp) - 1) * 19
    for i, ch in enumerate(jp):
        b.append(text(866, y0 + i * 38 + 11, ch, "MJP", 28, fill=PAPER, anchor="middle"))
    b.append('</g>')

    b.append(f'<g class="inR" style="animation-delay:.15s">{tag(560, 32, CFG["volume"].upper(), "第1巻", 19)}</g>')

    first, last = CFG["name_first"].upper(), CFG["name_last"].upper()
    size = 82
    while max(measure(first, "Bng", size), measure(last, "Bng", size)) > 272:
        size -= 2
    nx = 545
    lw = measure(last, "Bng", size)
    b.append(f'<g class="inR" style="animation-delay:.25s">'
             f'<polygon points="{nx - 10},{232 - size * .62} {nx + lw + 22},{232 - size * .78} '
             f'{nx + lw + 8},{232 + 10} {nx - 18},{232 + 14}" fill="{RED}"/></g>')
    b.append(f'<g class="inR" style="animation-delay:.2s">{text(nx, 150, first, "Bng", size, extra="letter-spacing=\"1\"")}</g>')
    b.append(f'<g class="inR" style="animation-delay:.3s">{text(nx, 232, last, "Bng", size, extra="letter-spacing=\"1\"")}</g>')

    cap, ch = caption_box(530, 268, 236, [CFG["role"].upper(), CFG["location"].upper()], size=18, lh=23)
    b.append(f'<g class="inR" style="animation-delay:.45s">{cap}</g>')

    # red seal (hanko)
    seal = CFG["hero_seal"]
    b.append(f'<g transform="translate(784,334) rotate(-8)"><g class="stamp" style="animation-delay:.9s">'
             f'<rect x="-32" y="-40" width="64" height="80" rx="7" fill="{RED}"/>'
             f'<rect x="-27" y="-35" width="54" height="70" rx="4" fill="none" stroke="{PAPER}" stroke-width="2"/>'
             + "".join(text(0, -6 + i * 29, c, "MJP", 26, fill=PAPER, anchor="middle") for i, c in enumerate(seal))
             + '</g></g>')

    b.append(sfx(122, 350, CFG["hero_sfx"], 58, rot=-12, delay=0))

    label = (f'{CFG["name_first"]} {CFG["name_last"]}, {CFG["role"]} from {CFG["location"]}. '
             'Manga-style title page.')
    return svg(W, H, label, defs, "".join(b))


def about():
    W, H = 900, 480
    P1 = [(10, 10), (562, 10), (542, 236), (10, 236)]
    P2 = [(574, 10), (890, 10), (890, 236), (554, 236)]
    P3 = [(10, 248), (372, 248), (392, 470), (10, 470)]
    P4 = [(384, 248), (890, 248), (890, 470), (404, 470)]
    defs = "".join(clip(f"c{i}", p) for i, p in enumerate((P1, P2, P3, P4), 1))
    b = []
    now, before, dojo, life = CFG["now"], CFG["before"], CFG["dojo"], CFG["life"]

    # P1 — now
    b.append(panel(P1))
    b.append('<g clip-path="url(#c1)">')
    b.append(f'<rect x="300" y="10" width="270" height="230" fill="url(#tone)" mask="url(#fadeR)" opacity=".45"/>')
    # phone
    b.append('<g class="pop" style="animation-delay:.2s">'
             f'<g transform="translate(446,66) rotate(8)">'
             f'<rect x="0" y="0" width="78" height="150" rx="14" fill="{INK}"/>'
             f'<rect x="6" y="16" width="66" height="118" rx="3" fill="{PAPER}"/>'
             f'<rect x="28" y="6" width="22" height="4" rx="2" fill="{PAPER}"/>'
             f'{text(39, 86, "</>", "Bng", 30, anchor="middle")}'
             f'<rect x="14" y="104" width="50" height="6" fill="url(#tone)"/>'
             f'<rect x="14" y="116" width="34" height="6" fill="url(#tone)"/>'
             '</g></g>')
    b.append(sfx(500, 46, now["sfx"], 22, rot=-6, delay=.1))
    b.append('</g>')
    b.append(tag(22, 22, now["tag"], now["tag_jp"], 18))
    bl = wrap(now["bubble"].upper(), "Cmc", 17, 330)
    bcy, bry = 62 + len(bl) * 11, len(bl) * 11 + 24
    b.append('<g class="pop" style="animation-delay:.35s">')
    b.append(bubble(215, bcy, 200, bry, (436, 128)))
    b.append(text_lines(215, bcy - (len(bl) - 1) * 10.5 + 6, bl, "Cmc", 17, 21, anchor="middle"))
    b.append('</g>')
    cl = wrap(now["caption"], "Cmc", 15, 370)
    cap, _ = caption_box(26, 236 - 18 - (len(cl) * 19 + 15), 390, cl, size=15, lh=19, pad=9)
    b.append(f'<g class="fade" style="animation-delay:.6s">{cap}</g>')

    # P2 — flashback (black panel)
    b.append(panel(P2, fill=INK))
    b.append('<g clip-path="url(#c2)">')
    b.append(f'<path d="{speed_lines(554, 900, 20, 230, 34, 7)}" fill="#3a3a3a"/>')
    b.append('</g>')
    b.append(tag(586, 22, before["tag"], before["tag_jp"], 18, bg=PAPER, fg=INK))
    y = 72
    for i, job in enumerate(before["jobs"]):
        lines = [job["title"].upper(), "@ " + job["at"].upper()]
        cap, h = caption_box(590 - i * 8, y, 270, lines, size=16, lh=20, pad=9, shadow=False)
        b.append(f'<g class="inR" style="animation-delay:{.3 + i * .15}s">{cap}</g>')
        y += h + 16

    # P3 — dojo
    b.append(panel(P3))
    b.append('<g clip-path="url(#c3)">')
    b.append(f'<path class="flA" d="{speed_lines(0, 400, 256, 466, 60, 3)}" fill="{INK}"/>')
    b.append(f'<path class="flB" d="{speed_lines(0, 400, 256, 466, 60, 4)}" fill="{INK}"/>')
    b.append(f'<g class="pop" style="animation-delay:.3s"><polygon points="{burst(272, 360, 50, 104, 14, 5)}" '
             f'fill="{PAPER}" stroke="{INK}" stroke-width="4" stroke-linejoin="miter"/></g>')
    # belt knot, in the ladder's brown (see stats_panel fills)
    b.append('<g transform="translate(272,346) rotate(-8)"><g class="pop" style="animation-delay:.45s">'
             f'<path d="M-70,-12 Q0,-20 70,-12 L70,10 Q0,2 -70,10 Z" fill="#555" stroke="{PAPER}" stroke-width="2"/>'
             f'<path d="M-6,8 L-30,70 L-12,74 L6,14 Z" fill="#555" stroke="{PAPER}" stroke-width="2"/>'
             f'<path d="M4,8 L34,66 L50,58 L16,4 Z" fill="#555" stroke="{PAPER}" stroke-width="2"/>'
             f'<rect x="-16" y="-18" width="32" height="34" rx="5" fill="#555" stroke="{PAPER}" stroke-width="2.5"/>'
             f'<path d="M-9,-12 L9,10 M9,-12 L-9,10" stroke="{PAPER}" stroke-width="1.5"/>'
             '</g></g>')
    b.append('</g>')
    b.append(sfx(112, 345, dojo["sfx"], 52, rot=-14, delay=.2))
    b.append(tag(22, 260, dojo["tag"], "押忍", 18))
    cap, _ = caption_box(26, 420, measure(dojo["caption"].upper(), "Cmc", 16) + 18, [dojo["caption"].upper()], size=16, lh=20, pad=8)
    b.append(f'<g class="fade" style="animation-delay:.6s">{cap}</g>')

    # P4 — side quests
    b.append(panel(P4))
    b.append('<g clip-path="url(#c4)">')
    b.append(f'<rect x="640" y="248" width="260" height="230" fill="url(#toneL)" mask="url(#fadeR)"/>')
    b.append('</g>')
    b.append(tag(416, 260, life["tag"], None, 18))
    y = 312
    for i, item in enumerate(life["items"]):
        b.append(f'<g class="inR" style="animation-delay:{.25 + i * .12}s">'
                 f'{text(424 + i * 4, y, "★", "Cmc", 18, fill=RED)}'
                 f'{text(448 + i * 4, y, item.upper(), "Cmc", 18)}</g>')
        y += 36
    b.append(sfx(800, 300, life["sfx"], 30, rot=8, cls="fade", delay=.8))

    label = (f'Now: {now["bubble"]} {now["caption"]} Before: '
             + "; ".join(f'{j["title"]} at {j["at"]}' for j in before["jobs"])
             + f'. {dojo["caption"]}. ' + ", ".join(life["items"]) + ".")
    return svg(W, H, label, defs, "".join(b))



def header_band(y, label, jp, W=900):
    """Slanted black title band used at the top of a section."""
    out = f'<polygon points="10,{y} {W - 10},{y} {W - 30},{y + 50} 10,{y + 50}" fill="{INK}"/>'
    out += f'<path d="{speed_lines(300, W - 30, y + 6, y + 44, 14, len(label))}" fill="#3a3a3a"/>'
    out += text(28, y + 37, jp, "MJP", 26, fill=PAPER)
    out += text(36 + 27 * len(jp), y + 39, label, "Bng", 34, fill=PAPER, extra='letter-spacing="1.5"')
    out += f'<rect x="{W - 120}" y="{y + 18}" width="60" height="14" fill="{RED}" transform="skewX(-20)"/>'
    return out


def moves():
    cfg = CFG["moves"]
    items = cfg["list"]
    cols, cw, ch, gap = 3, 284, 74, 12
    rows = math.ceil(len(items) / cols)
    W, H = 900, 80 + rows * (ch + gap) + 4
    b = [header_band(10, cfg["tag"], cfg["tag_jp"])]
    for i, it in enumerate(items):
        x = 14 + (i % cols) * (cw + gap)
        y = 76 + (i // cols) * (ch + gap)
        g = (f'<rect x="{x + 5}" y="{y + 5}" width="{cw}" height="{ch}" fill="{INK}"/>'
             f'<rect x="{x}" y="{y}" width="{cw}" height="{ch}" fill="{PAPER}" stroke="{INK}" stroke-width="3"/>'
             f'<rect x="{x + cw - 110}" y="{y + 2}" width="108" height="{ch - 4}" fill="url(#toneL)" mask="url(#fadeR)"/>'
             f'<rect x="{x}" y="{y}" width="46" height="{ch}" fill="{INK}"/>'
             + text(x + 23, y + 34, "技", "MJP", 20, fill=PAPER, anchor="middle")
             + text(x + 23, y + 58, f"{i + 1:02d}", "Bng", 20, fill=RED, anchor="middle"))
        size = 30
        while measure(it["tech"].upper(), "Bng", size) > cw - 70:
            size -= 1
        g += text(x + 60, y + 36, it["tech"].upper(), "Bng", size, extra='letter-spacing="1"')
        g += text(x + 60, y + 59, "★ " + it["move"].upper(), "Cmc", 13, fill="#444")
        b.append(f'<g class="pop" style="animation-delay:{.1 + i * .07:.2f}s">{g}</g>')
    label = "Special moves (tech stack): " + ", ".join(i["tech"] for i in items) + "."
    return svg(W, H, label, "", "".join(b))


def chapters_header():
    c = CFG["chapters"]
    return svg(900, 70, f'{c["tag"]}: articles and papers', "", header_band(10, c["tag"], c["tag_jp"]))


def chapter_card(i, ch):
    W, H = 900, 86
    kind = f'{ch["kind"]} · {ch["source"]}'.upper()
    kw = measure(kind, "Bng", 16, ls=1) + 24
    lines = wrap(ch["title"], "Cmc", 19, 806 - kw - 126 - 18)
    if len(lines) > 2:
        lines = lines[:2]
        lines[1] = lines[1].rstrip(".,:") + "…"
    b = [f'<rect x="12" y="8" width="876" height="70" fill="{INK}" transform="translate(5,4)"/>',
         f'<rect x="12" y="8" width="876" height="70" fill="{PAPER}" stroke="{INK}" stroke-width="3"/>',
         f'<rect x="12" y="8" width="96" height="70" fill="{INK}"/>',
         text(60, 40, f"第{i + 1}話", "MJP", 19, fill=PAPER, anchor="middle"),
         text(60, 66, f"EP.{i + 1:02d}", "Bng", 18, fill=RED, anchor="middle", extra='letter-spacing="1"')]
    ty = 43 - (len(lines) - 1) * 11 + 6
    b.append(text_lines(126, ty, lines, "Cmc", 19, 23))
    b.append(f'<rect x="{806 - kw:.0f}" y="30" width="{kw:.0f}" height="26" fill="{INK}"/>')
    b.append(text(806 - kw / 2, 49, kind, "Bng", 16, fill=PAPER, anchor="middle", extra='letter-spacing="1"'))
    b.append(f'<g transform="translate(846,43)"><circle r="22" fill="{RED}"/>'
             f'<path d="M-9,-1 L5,-1 L5,-8 L14,0 L5,8 L5,1 L-9,1 Z" fill="{PAPER}" stroke="{PAPER}" stroke-width="3" stroke-linejoin="round"/></g>')
    body = f'<g class="inR" style="animation-delay:{.1 + i * .1:.1f}s">{"".join(b)}</g>'
    return svg(W, H, f'Chapter {i + 1}: {ch["title"]} ({ch["kind"]}, {ch["source"]})', "", body)


# ---------------------------------------------------------------- stats

STATS_CACHE = OUT / "stats.json"
STATS_QUERY = """query($login:String!){user(login:$login){createdAt
 pullRequests(states:MERGED){totalCount}
 repositories(ownerAffiliations:OWNER){totalCount}
 contributionsCollection{contributionCalendar{totalContributions}}}}"""


def fetch_stats():
    """Live numbers from the GitHub GraphQL API; falls back to the last cached values."""
    import os
    import subprocess
    import urllib.request
    from datetime import datetime, timezone
    # Deliberately not GITHUB_TOKEN: in Actions it only sees public activity, which would
    # overwrite the cached numbers with much lower ones. Use a PAT (secret GH_STATS_TOKEN).
    token = os.environ.get("GH_STATS_TOKEN")
    if not token:
        try:
            token = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True).stdout.strip()
        except OSError:
            token = ""
    cached = json.loads(STATS_CACHE.read_text()) if STATS_CACHE.exists() else None
    if not token:
        print("no GitHub token; using cached stats", file=sys.stderr)
        return cached
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": STATS_QUERY, "variables": {"login": CFG["github_user"]}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "profile-generator"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            u = json.load(r)["data"]["user"]
    except Exception as e:  # network/API trouble shouldn't break the profile
        print(f"stats fetch failed ({e}); using cached stats", file=sys.stderr)
        return cached
    created = datetime.fromisoformat(u["createdAt"].replace("Z", "+00:00"))
    stats = {
        "contributions": u["contributionsCollection"]["contributionCalendar"]["totalContributions"],
        "prs_merged": u["pullRequests"]["totalCount"],
        "repos": u["repositories"]["totalCount"],
        "years": (datetime.now(timezone.utc) - created).days // 365,
    }
    STATS_CACHE.write_text(json.dumps(stats, indent=2) + "\n")
    return stats


def stats_panel(st):
    cfg = CFG["stats"]
    W, H = 900, 300
    b = [header_band(10, cfg["tag"], cfg["tag_jp"])]
    tiles = [("contributions", "Contributions · 1 yr"), ("prs_merged", "PRs merged"),
             ("repos", "Repositories"), ("years", "Years on GitHub")]
    tw = 206
    for i, (k, lbl) in enumerate(tiles):
        x, y = 14 + i * (tw + 12), 76
        val = f'{st[k]:,}' if st else "?"
        g = (f'<rect x="{x + 5}" y="{y + 5}" width="{tw}" height="92" fill="{INK}"/>'
             f'<rect x="{x}" y="{y}" width="{tw}" height="92" fill="{PAPER}" stroke="{INK}" stroke-width="3"/>'
             f'<rect x="{x + 2}" y="{y + 2}" width="{tw - 4}" height="40" fill="url(#toneL)" mask="url(#fadeD)"/>'
             + text(x + tw / 2, y + 56, val, "Bng", 50, anchor="middle", extra='letter-spacing="1"')
             + text(x + tw / 2, y + 80, lbl.upper(), "Cmc", 13, fill="#444", anchor="middle"))
        b.append(f'<g class="pop" style="animation-delay:{.15 + i * .1:.2f}s">{g}</g>')

    # belt ladder: my actual Kyokushin rank (config "belt"), not something computed from GitHub
    belts = cfg["belts"]
    rank = [en.lower() for _, en in belts].index(cfg["belt"].lower())
    fills = [PAPER, "url(#toneL)", "url(#tone)", "url(#toneM)", "url(#toneD)", "#555", INK]
    bx, by, bw = 30, 222, 840 / len(belts)
    for i, (jp, en) in enumerate(belts):
        x = bx + i * bw
        b.append(f'<rect x="{x:.1f}" y="{by}" width="{bw - 6:.1f}" height="22" fill="{fills[i]}" '
                 f'stroke="{RED if i == rank else INK}" stroke-width="{4 if i == rank else 2}"/>')
        b.append(text(x + (bw - 6) / 2, by + 44, f"{jp}  {en.upper()}", "Cmc", 13,
                      fill=RED if i == rank else INK, anchor="middle"))
    mx = bx + rank * bw + (bw - 6) / 2
    jp, en = belts[rank]
    b.append(f'<g class="stamp" style="animation-delay:.7s"><polygon points="{mx - 9},{by - 12} {mx + 9},{by - 12} {mx},{by - 2}" fill="{RED}"/></g>')
    rank_txt = f"RANK: {en.upper()} BELT"
    rw = measure(rank_txt, "Bng", 20, ls=1) + 66
    rx = min(max(mx - rw / 2, 20), W - 20 - rw)
    b.append(f'<g class="stamp" style="animation-delay:.6s"><rect x="{rx:.0f}" y="{by - 44}" width="{rw:.0f}" height="28" fill="{RED}"/>'
             + text(rx + 12, by - 23, jp + "帯", "MJP", 17, fill=PAPER)
             + text(rx + 52, by - 22, rank_txt, "Bng", 20, fill=PAPER, extra='letter-spacing="1"') + '</g>')
    defs = ('<pattern id="toneM" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
            f'<circle cx="3.5" cy="3.5" r="2.3" fill="{INK}"/></pattern>'
            '<pattern id="toneD" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
            f'<circle cx="3.5" cy="3.5" r="3.1" fill="{INK}"/></pattern>')
    label = ("Power level: " + (", ".join(f"{st[k]} {l}" for k, l in tiles) + f". Rank: {en} belt." if st
                                else "stats unavailable."))
    return svg(W, H, label, defs, "".join(b))


# ---------------------------------------------------------------- ending

def contact():
    c = CFG["contact"]
    W, H = 900, 200
    P = [(10, 10), (890, 10), (890, 190), (10, 190)]
    b = [panel(P), f'<g clip-path="url(#cE)"><path class="flA" d="{speed_lines(10, 900, 20, 182, 46, 11)}" fill="{INK}" opacity=".85"/>'
         f'<path class="flB" d="{speed_lines(10, 900, 20, 182, 46, 12)}" fill="{INK}" opacity=".85"/></g>']
    bl = wrap(c["bubble"].upper(), "Cmc", 19, 380)
    b.append('<g class="pop" style="animation-delay:.2s">' + bubble(300, 74, 240, 24 + len(bl) * 12, (590, 120))
             + text_lines(300, 74 - (len(bl) - 1) * 12 + 7, bl, "Cmc", 19, 24, anchor="middle") + '</g>')
    cap, _ = caption_box(40, 148, measure(c["next"].upper(), "Cmc", 15) + 22, [c["next"].upper()], size=15, lh=19, pad=8)
    b.append(f'<g class="fade" style="animation-delay:.5s">{cap}</g>')
    b.append(f'<rect x="640" y="10" width="250" height="180" fill="{INK}"/>')
    b.append(f'<g transform="translate(765,122) rotate(-6)"><g class="stamp" style="animation-delay:.4s">'
             + text(0, 0, c["end"], "MJP", 58, fill=PAPER, anchor="middle") + '</g></g>')
    b.append(text(765, 172, "TO BE CONTINUED", "Bng", 22, fill=RED, anchor="middle", extra='letter-spacing="2"'))
    b.append(panel(P, fill="none"))
    return svg(W, H, f'To be continued. {c["bubble"]}', clip("cE", P), "".join(b))


def button(label):
    w = measure(label.upper(), "Bng", 24, ls=1) + 58
    h = 46
    body = (f'<polygon points="10,4 {w},4 {w - 8},{h - 2} 2,{h - 2}" fill="{INK}" transform="translate(3,2)"/>'
            f'<polygon points="10,2 {w - 2},2 {w - 10},{h - 4} 2,{h - 4}" fill="{PAPER}" stroke="{INK}" stroke-width="3"/>'
            f'<rect x="14" y="{h / 2 - 8}" width="10" height="12" fill="{RED}" transform="skewX(-12)"/>'
            + text(34, 32, label.upper(), "Bng", 24, extra='letter-spacing="1"'))
    return svg(int(w + 6), h + 2, label, "", body, paper=False)


# ---------------------------------------------------------------- readme

def slug(s):
    return "".join(ch if ch.isalnum() else "-" for ch in s.lower()).strip("-")


def readme(n_chapters):
    def img(name, alt, extra='width="100%"'):
        return f'<img src="assets/manga/{name}.svg" {extra} alt="{esc(alt)}" />'
    c, ch = CFG, CFG["chapters"]["list"]
    links = " · ".join(f'<a href="{l["url"]}">{l["label"]}</a>' for l in c["links"])
    out = [
        "<!--\n  GENERATED by scripts/gen_profile.py. Do not edit by hand.\n"
        "  Edit profile.config.json and run: python3 scripts/gen_profile.py\n"
        "  (the \"Refresh profile\" GitHub Action also does this daily with fresh stats)\n-->\n",
        f'<p align="center">{img("hero", f"{c["name_first"]} {c["name_last"]}, {c["role"]}, {c["location"]}")}</p>\n',
        f'<p align="center">{img("about", "About: " + c["now"]["bubble"] + " Previously " + ", ".join(j["title"] + " at " + j["at"] for j in c["before"]["jobs"]) + ". Kyokushin karateka. " + ", ".join(c["life"]["items"]) + ".")}<br>',
        f'<sub>{links}</sub></p>\n',
        f'<p align="center">{img("moves", "Tech stack: " + ", ".join(m["tech"] for m in c["moves"]["list"]))}</p>\n',
        f'<p align="center">{img("h-chapters", "Chapters: articles and papers")}<br>',
    ]
    for i, it in enumerate(ch[:n_chapters]):
        out.append(f'<a href="{it["url"]}">{img(f"chapter-{i}", it["title"])}</a><br>')
    out.append("</p>\n")
    out.append(f'<p align="center">{img("stats", "GitHub stats and Kyokushin belt rank: " + CFG["stats"]["belt"])}</p>\n')
    out.append(f'<p align="center">{img("contact", "To be continued")}<br>')
    out.append("\n".join(f'<a href="{l["url"]}">{img("contact-" + slug(l["label"]), l["label"], "height=\"48\"")}</a>'
                         for l in c["contact"]["list"]))
    out.append("</p>\n")
    return "\n".join(out)


def jp_chars():
    """Every JP glyph the panels can draw: config text + literals in this script."""
    s = json.dumps(CFG, ensure_ascii=False) + Path(__file__).read_text() + "0123456789"
    return "".join(sorted({c for c in s if 0x3000 <= ord(c) <= 0x9FFF or 0xFF00 <= ord(c) <= 0xFFEF}))


def main():
    if "--jp-chars" in sys.argv:
        print(jp_chars())
        return
    OUT.mkdir(parents=True, exist_ok=True)
    files = {"hero": hero(), "about": about(), "moves": moves(), "h-chapters": chapters_header(),
             "stats": stats_panel(fetch_stats()), "contact": contact()}
    chapters = CFG["chapters"]["list"]
    for i, ch in enumerate(chapters):
        files[f"chapter-{i}"] = chapter_card(i, ch)
    for l in CFG["contact"]["list"]:
        files["contact-" + slug(l["label"])] = button(l["label"])
    keep = {f"{n}.svg" for n in files}
    for old in OUT.glob("*.svg"):   # drop panels for removed chapters/links
        if old.name not in keep:
            old.unlink()
    for name, body in files.items():
        (OUT / f"{name}.svg").write_text(body)
    (ROOT / "README.md").write_text(readme(len(chapters)))
    total = sum((OUT / f"{n}.svg").stat().st_size for n in files) // 1024
    print(f"wrote {len(files)} panels ({total} KB) + README.md")


if __name__ == "__main__":
    main()

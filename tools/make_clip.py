"""Render the ~33-second "what changed" clip (NBG's original report -> our dashboard) as a 1080p MP4.

Built to the Oracle design system in docs/design/oracle.md, so it avoids the usual generated-video look:
flat full-bleed bands on the warm neutral ladder, square corners, no shadows, no gradients, no pills, Georgia display type,
one gold rule as the only ornament, charcoal for chrome, Oracle's focus colour for highlights, and the red used exactly once
(our own mark on the end card). The motion is UI motion over the real screenshots: a cursor that clicks the real controls,
a circular theme reveal from the toggle, a before/after slider, camera pushes and masked text reveals. The animated
topographic contour lines (Oracle's hero pattern) are drawn procedurally. Oracle Sans is proprietary, so Source Sans 3 (OFL,
video/fonts) stands in for it.

Inputs: reference/Comparison/ (NBG OLD = NBG's report, Current = ours light, Current dark = ours dark; English pages).
Usage:  python tools/make_clip.py                      -> video/nbg-fx-what-changed.mp4
        python tools/make_clip.py --still 1.0 4.5 ...  -> video/still-<t>.png (preview single frames)
"""
import math
import os
import subprocess
import sys

import contourpy
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "video")
CMP = os.path.join(ROOT, "reference", "Comparison")


def shot(folder, n):
    return os.path.join(CMP, folder, f"Screenshot 2026-10-16 {n}.png")


SRC = {
    "nbg_overview": shot("NBG OLD", "164000"), "nbg_daily": shot("NBG OLD", "164037"),
    "light_overview": shot("Current", "164329"), "light_daily": shot("Current", "164336"),
    "dark_overview": shot("Current dark", "164303"), "dark_daily": shot("Current dark", "164309"),
    "dark_overview_ka": shot("Current dark", "164224"),
}
W, H, FPS, DUR = 1920, 1080, 30, 24.2
SLOW = 1.35                              # 1.0 was too fast: every scene, move and hold is stretched by this factor
SW, SH = 1536, 864                      # the stage (screenshot area)
SX, SY = (W - SW) // 2, 88
R = 1.5                                 # screenshots are kept at 1.5x the stage so camera pushes stay sharp

# Oracle tokens (docs/design/oracle.md)
CANVAS, WHITE, INK, INK_DEEP, PRIMARY = "#f1efed", "#ffffff", "#161513", "#211e1c", "#312d2a"
FOREST, TEAL, GOLD, GOLD_SOFT = "#33553c", "#d6e5e5", "#f0cc71", "#f7e0a1"
FOCUS, HAIR, FIELD, DISABLED, RED = "#227e9e", "#e4e1dd", "#d4cfca", "#aea8a2", "#c74634"
MUTED = "#5f5a55"
CONTOUR_ON_FOREST, CONTOUR_ON_DEEP = "#416a4b", "#2e2a27"

F = "C:/Windows/Fonts/"
SANS = os.path.join(OUT, "fonts", "SourceSans3.ttf")
_fonts = {}


def serif(px):
    return font(F + "georgia.ttf", px)


def sans(px, wght=400):
    return font(SANS, px, wght)


def font(path, px, wght=None):
    k = (path, px, wght)
    if k not in _fonts:
        f = ImageFont.truetype(path, px)
        if wght:
            f.set_variation_by_axes([wght])
        _fonts[k] = f
    return _fonts[k]


def clamp(x, a=0.0, b=1.0):
    return min(max(x, a), b)


def inout(x):
    x = clamp(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def out_expo(x):
    x = clamp(x)
    return 1.0 if x >= 1 else 1 - 2 ** (-10 * x)


def seg(t, a, b):
    return (t - a) / (b - a)


def lerp(a, b, u):
    return a + (b - a) * u


# ------------------------------------------------------------------ drawing helpers
def fade(layer, alpha):
    if alpha < 1:
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * alpha)))
    return layer


def text(img, x, y, s, f, fill, anchor="ls", alpha=1.0):
    l, t, r, b = f.getbbox(s, anchor=anchor)
    pad = 4
    tmp = Image.new("RGBA", (r - l + 2 * pad, b - t + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((pad - l, pad - t), s, font=f, fill=fill, anchor=anchor)
    img.alpha_composite(fade(tmp, alpha), (round(x + l - pad), round(y + t - pad)))


def reveal(img, x, y, s, f, fill, p, alpha=1.0):
    """Masked slide-up: the line rises out of its own baseline box (y is the baseline)."""
    asc, desc = f.getmetrics()
    w = round(f.getlength(s)) + 8
    box = Image.new("RGBA", (w, asc + desc + 4), (0, 0, 0, 0))
    ImageDraw.Draw(box).text((0, asc), s, font=f, fill=fill, anchor="ls")
    moved = Image.new("RGBA", box.size, (0, 0, 0, 0))
    moved.paste(box, (0, round((1 - clamp(p)) * (asc + desc) * 1.05)))
    img.alpha_composite(fade(moved, alpha), (round(x), round(y - asc)))


def rect(img, box, fill=None, outline=None, width=1, alpha=1.0):
    x0, y0, x1, y1 = [round(v) for v in box]
    w, h = max(x1 - x0, 1), max(y1 - y0, 1)
    layer = Image.new("RGBA", (w + 1, h + 1), (0, 0, 0, 0))
    ImageDraw.Draw(layer).rectangle((0, 0, w, h), fill=fill, outline=outline, width=width)
    img.alpha_composite(fade(layer, alpha), (x0, y0))


# ------------------------------------------------------------------ contour pattern (Oracle's hero texture)
GX, GY = 160, 90
_XS, _YS = np.linspace(0, W, GX), np.linspace(0, H, GY)
_U, _V = np.meshgrid(_XS / W, _YS / H)


def contours(t, bg, line, seed=0.0):
    ss = 2
    img = Image.new("RGB", (W * ss, H * ss), bg)
    d = ImageDraw.Draw(img)
    f = (np.sin(3.2 * _U + 1.7 * _V + 0.35 * t + seed) + 0.8 * np.sin(5.1 * _U - 2.3 * _V - 0.27 * t + 1.2 + seed)
         + 0.6 * np.sin(2.0 * _U + 6.2 * _V + 0.2 * t + 0.5) + 0.5 * np.sin(7.3 * _U + 3.1 * _V - 0.31 * t))
    gen = contourpy.contour_generator(_XS * ss, _YS * ss, f)
    for level in np.linspace(-2.2, 2.2, 24):
        for pl in gen.lines(level):
            d.line([tuple(p) for p in pl], fill=line, width=3)
    return img.resize((W, H), Image.LANCZOS).convert("RGBA")


# ------------------------------------------------------------------ screenshots and the camera
_prep = {}


def prep(key):
    """(hi-res image, scale to stage px, x offset): cover-fit to the stage, anchored top and centre."""
    if key not in _prep:
        im = Image.open(SRC[key]).convert("RGB")
        s = max(SW / im.width, SH / im.height)
        hi = im.resize((round(im.width * s * R), round(im.height * s * R)), Image.LANCZOS)
        ox = (hi.width / R - SW) / 2
        hi = hi.crop((round(ox * R), 0, round(ox * R) + round(SW * R), round(SH * R)))
        _prep[key] = (hi, s, ox)
    return _prep[key]


def view_box(view):
    cx, cy, z = view
    w, h = SW / z, SH / z
    x0, y0 = clamp(cx - w / 2, 0, SW - w), clamp(cy - h / 2, 0, SH - h)
    return x0, y0, z


def seen(key, view):
    x0, y0, z = view_box(view)
    hi = prep(key)[0]
    return hi.resize((SW, SH), Image.LANCZOS, box=(x0 * R, y0 * R, (x0 + SW / z) * R, (y0 + SH / z) * R))


def proj(key, pt, view):
    """Source-screenshot pixel -> position inside the stage as seen through the camera."""
    _, s, ox = prep(key)
    x0, y0, z = view_box(view)
    return ((pt[0] * s - ox - x0) * z, (pt[1] * s - y0) * z)


# ------------------------------------------------------------------ UI overlays: cursor, focus ring, callout
POINTER = [(5.65376, 12.3673), (5.46026, 12.3673), (5.31717, 12.4976), (0.500002, 16.8829), (0.500002, 1.19841), (11.7841, 12.3673)]


def cursor(img, x, y, press=0.0, ring=0.0):
    """Pointer from the supplied SVG (viewBox 12.5 x 17.5, shown 32 px high): black fill, white 1.2 outline, tip at (x, y)."""
    ss, k = 8, 32 / 17.5 * (1 - 0.08 * press)
    pad = 6
    box = Image.new("RGBA", (round(26 * ss), round(36 * ss)), (0, 0, 0, 0))
    d = ImageDraw.Draw(box)
    pts = [((px - POINTER[4][0]) * k * ss + pad * ss, (py - POINTER[4][1]) * k * ss + pad * ss) for px, py in POINTER]
    d.polygon(pts, fill="#1a1a1a")
    d.line(pts + [pts[0], pts[1]], fill=WHITE, width=round(1.2 * k * ss), joint="curve")
    box = box.resize((26, 36), Image.LANCZOS)
    if 0 < ring < 1:
        r = round(8 + 34 * out_expo(ring))
        lay = Image.new("RGBA", (2 * r + 4, 2 * r + 4), (0, 0, 0, 0))
        ImageDraw.Draw(lay).ellipse((2, 2, 2 * r + 2, 2 * r + 2), outline=FOCUS, width=3)
        img.alpha_composite(fade(lay, 1 - ring), (round(x - r - 2), round(y - r - 2)))
    img.alpha_composite(box, (round(x - pad), round(y - pad)))


def focus_ring(img, box, alpha=1.0, grow=0):
    x0, y0, x1, y1 = box
    rect(img, (x0 - grow, y0 - grow, x1 + grow, y1 + grow), outline=FOCUS, width=3, alpha=alpha)


def ring_label(img, box, label, p, below=False):
    """Design-review style annotation: focus ring plus a flat focus-colour label attached to its corner (no shadow)."""
    if p <= 0:
        return
    x0, y0, x1, y1 = box
    focus_ring(img, (x0 + 2, y0 + 2, x1 - 2, y1 - 2), clamp(p * 1.5))
    f = sans(24, 700)
    wd = round(f.getlength(label)) + 36
    ly = y1 + 4 if below else y0 - 42
    lay = Image.new("RGBA", (wd, 42), FOCUS)
    ImageDraw.Draw(lay).text((18, 22), label, font=f, fill=WHITE, anchor="lm")
    img.alpha_composite(fade(lay, clamp(p * 1.5 - 0.2)), (round(x0 + 2), round(ly)))


def tag(img, x, y, label, alpha):
    """Flat charcoal label, square corners (Oracle label type)."""
    f = sans(21, 700)
    wd = round(f.getlength(label)) + 36
    box = Image.new("RGBA", (wd, 44), PRIMARY)
    ImageDraw.Draw(box).text((18, 23), label, font=f, fill=WHITE, anchor="lm")
    img.alpha_composite(fade(box, alpha), (x, y))


# ------------------------------------------------------------------ chrome: sub-navigation and caption band
CHAPTERS = ["Before and after", "Dark theme", "Language", "Features"]


def subnav(img, t, active, slide):
    y = round(-64 * (1 - slide))
    rect(img, (0, y, W, y + 64), fill=INK_DEEP)
    text(img, 60, y + 41, "NBG FX Rates", sans(24, 800), WHITE)
    x = 520
    pos = []
    for name in CHAPTERS:
        wd = round(sans(21, 600).getlength(name))
        pos.append((x, wd))
        x += wd + 64
    tabs = [p for p in pos]
    for i, (name, (px, wd)) in enumerate(zip(CHAPTERS, pos)):
        text(img, px, y + 40, name, sans(21, 600), WHITE if i == active else DISABLED)
    return y, pos


def caption(img, head, body, p):
    """Bottom band: Georgia headline left, body right, flat white on a hairline."""
    y = round(lerp(H, H - 110, inout(p)))
    rect(img, (0, y, W, H), fill=WHITE)
    rect(img, (0, y, W, y + 1), fill=HAIR)


def caption_text(img, head, body, p):
    y = H - 110
    reveal(img, 192, y + 70, head, serif(40), INK, p)
    reveal(img, 760, y + 64, body[0], sans(24, 400), MUTED, p - 0.08)
    if len(body) > 1:
        reveal(img, 760, y + 94, body[1], sans(24, 400), MUTED, p - 0.14)


# ------------------------------------------------------------------ the film
CAP = [  # (start, end, headline, body lines)
    (2.7, 10.2, "Official rates and daily table", ["One top bar and a single filter row replace NBG's side rail and stacked slicers;", "KPI cards add the daily change."]),
    (10.2, 14.6, "Dark theme", ["One click switches every page. Period, currency and filters stay as they are."]),
    (14.6, 17.4, "Georgian and English", ["Switch the whole report, currency names included."]),
]
FEATURES = [
    ("Dark and light theme", "One click on every page"),
    ("Georgian and English", "Currency names included"),
    ("Info panel", "Built-in help on every page"),
    ("Reset filters", "Back to the defaults in one click"),
    ("Dimmed weekend rows", "Friday's rate carries over"),
    ("History since 2001", "Refreshed from NBG's public files"),
]
# click targets in source-screenshot pixels (our English pages, 1917 px wide)
TOGGLE, LANG, TAB_RATES = (1740, 36), (1680, 36), (954, 41)
TOGGLE_BOX, LANG_BOX = (1720, 12, 1762, 60), (1658, 12, 1702, 60)


def path(t, pts):
    """Cursor position along waypoints [(t, (x, y))...] with ease-in-out between them."""
    if t <= pts[0][0]:
        return pts[0][1]
    for (t0, p0), (t1, p1) in zip(pts, pts[1:]):
        if t <= t1:
            u = inout(seg(t, t0, t1))
            return (lerp(p0[0], p1[0], u), lerp(p0[1], p1[1], u))
    return pts[-1][1]


def hero(t):
    img = contours(t, FOREST, CONTOUR_ON_FOREST)
    reveal(img, 160, 470, "Official exchange rates,", serif(104), WHITE, inout(seg(t, 0.2, 0.9)))
    reveal(img, 160, 590, "redesigned.", serif(104), WHITE, inout(seg(t, 0.35, 1.05)))
    rect(img, (160, 640, 240, 648), fill=GOLD, alpha=inout(seg(t, 0.9, 1.2)))
    reveal(img, 160, 720, "NBG's Power BI report, rebuilt for daily use.", sans(38, 300), WHITE, inout(seg(t, 1.0, 1.6)))
    return img


def features(t):
    img = contours(t * 0.8, FOREST, CONTOUR_ON_FOREST, 1.7)
    reveal(img, 160, 360, "Built for", serif(88), WHITE, inout(seg(t, 0.4, 1.1)))
    reveal(img, 160, 460, "daily use.", serif(88), WHITE, inout(seg(t, 0.5, 1.2)))
    rect(img, (160, 500, 240, 508), fill=GOLD, alpha=inout(seg(t, 1.0, 1.3)))
    x0, y0, rw = 860, 250, 120
    for i, (a, b) in enumerate(FEATURES):
        p = inout(seg(t, 0.7 + 0.28 * i, 1.3 + 0.28 * i))
        y = y0 + i * rw
        rect(img, (x0, y, x0 + 900 * p, y + 2), fill="#7f9985")
        reveal(img, x0, y + 60, a, sans(34, 800), WHITE, p)
        reveal(img, x0, y + 100, b, sans(26, 300), "#e4ebe5", p - 0.08)
    rect(img, (x0, y0 + 6 * rw, x0 + 900 * clamp(seg(t, 2.2, 2.6)), y0 + 6 * rw + 2), fill="#7f9985")
    return img


def end(t):
    img = contours(t * 0.6, INK_DEEP, CONTOUR_ON_DEEP, 3.1)
    p = inout(seg(t, 0.2, 0.9))
    rect(img, (160, 395, 160 + 26 * clamp(p * 2), 395 + 26), fill=RED)          # our mark: the only red in the film
    reveal(img, 160, 560, "NBG FX Rates", serif(124), WHITE, p)
    rect(img, (160, 600, 240, 608), fill=GOLD, alpha=inout(seg(t, 0.7, 1.0)))
    reveal(img, 160, 690, "Luka Tcheishvili", sans(36, 800), WHITE, inout(seg(t, 0.8, 1.4)))
    reveal(img, 160, 735, "Official daily exchange rates in Power BI", sans(28, 300), "#d4cfca", inout(seg(t, 0.9, 1.5)))
    text(img, 160, 1030, "Personal project. Not affiliated with the National Bank of Georgia.", sans(20, 400), DISABLED,
         alpha=inout(seg(t, 1.2, 1.7)))
    return img


def stage(t):
    """Everything inside the screenshot area, plus the cursor and call-outs that live on it. Returns (img, chapter)."""
    stage_img = Image.new("RGBA", (SW, SH), CANVAS)
    pad_view = (SW / 2, SH / 2, 1.0 + 0.035 * inout(seg(t, 2.7, 10.2)))          # slow push over the two comparisons
    chapter = 0
    ov = ""                                                                     # which overlay to draw afterwards

    if t < 10.2:                                                                # --- before / after, overview then daily
        view = pad_view
        a_key, b_key, wipe_a, wipe_b = "nbg_overview", "light_overview", 3.9, 4.9
        if t >= 6.6:
            a_key, b_key, wipe_a, wipe_b = "nbg_daily", "light_daily", 7.5, 8.5
        base = seen(a_key, view)
        after = seen(b_key, view)
        sw = inout(seg(t, wipe_a, wipe_b))
        wx = round(sw * SW)
        out = base.copy()
        if wx > 0:
            out.paste(after.crop((0, 0, wx, SH)), (0, 0))
        if 6.6 <= t < 6.95:                                                     # overview -> daily: the next page pushes in
            push = round(inout(seg(t, 6.6, 6.95)) * SW)
            canvas = Image.new("RGB", (SW, SH), CANVAS)
            canvas.paste(seen("light_overview", view), (-push, 0))
            canvas.paste(out, (SW - push, 0))
            out = canvas
        stage_img.paste(out, (0, 0))
        if 0 < sw < 1:                                                          # slider: charcoal bar and a square handle
            d = ImageDraw.Draw(stage_img)
            d.rectangle((wx - 2, 0, wx + 2, SH), fill=PRIMARY)
            d.rectangle((wx - 22, SH // 2 - 22, wx + 22, SH // 2 + 22), fill=PRIMARY)
            d.polygon([(wx - 5, SH // 2 - 9), (wx - 5, SH // 2 + 9), (wx - 14, SH // 2)], fill=WHITE)
            d.polygon([(wx + 5, SH // 2 - 9), (wx + 5, SH // 2 + 9), (wx + 14, SH // 2)], fill=WHITE)
        label = "BEFORE  NBG original" if sw < 0.5 else "AFTER  Rebuilt in Power BI"
        tag(stage_img, 0, SH - 44, label, 1.0)
        if t < 6.6:                                                             # call-outs on the overview, one at a time
            for box, text_, below, t0, t1 in (((0, 0, 1912, 78), "Top bar instead of a side rail", True, 5.0, 5.55),
                                              ((38, 210, 1882, 352), "KPI cards with the daily change", False, 5.55, 6.1),
                                              ((1322, 380, 1884, 1050), "Flags, arrows and signs", False, 6.1, 6.6)):
                p = inout(seg(t, t0, t0 + 0.22)) * (1 - inout(seg(t, t1 - 0.1, t1)))
                if p > 0:
                    x0, y0 = proj("light_overview", (box[0], box[1]), view)
                    x1, y1 = proj("light_overview", (box[2], box[3]), view)
                    ring_label(stage_img, (x0, y0, x1, min(y1, SH - 2)), text_, p, below)
        else:                                                                   # call-out on the daily table
            p = inout(seg(t, 8.7, 9.2)) * (1 - inout(seg(t, 9.9, 10.2)))
            if p > 0:
                x0, y0 = proj("light_daily", (55, 650), view)
                x1, y1 = proj("light_daily", (1262, 724), view)
                ring_label(stage_img, (x0, y0, x1, y1), "Weekend rows are dimmed", p)
        chapter = 0

    elif t < 14.6:                                                              # --- dark theme: click the toggle, then a tab
        chapter = 1
        zin = inout(seg(t, 10.2, 10.9)) - inout(seg(t, 12.2, 12.7))
        cam = (lerp(SW / 2, 1380, clamp(zin)), lerp(SH / 2, 140, clamp(zin)), lerp(1.0, 1.4, clamp(zin)))
        pages = ("light_daily", "dark_daily")
        circle = inout(seg(t, 11.4, 12.2))
        base = seen(pages[0], cam)
        if circle > 0:
            tgt = proj(pages[1], TOGGLE, cam)
            far = math.hypot(max(tgt[0], SW - tgt[0]), max(tgt[1], SH - tgt[1]))
            ss = 2
            mask = Image.new("L", (SW * ss, SH * ss), 0)
            r = circle * far * ss
            ImageDraw.Draw(mask).ellipse((tgt[0] * ss - r, tgt[1] * ss - r, tgt[0] * ss + r, tgt[1] * ss + r), fill=255)
            mask = mask.resize((SW, SH), Image.LANCZOS)
            base = Image.composite(seen(pages[1], cam), base, mask)
        page_swap = inout(seg(t, 13.35, 13.6))
        if page_swap > 0:
            base = Image.blend(base, seen("dark_overview", cam), page_swap)
        stage_img.paste(base, (0, 0))
        key = "dark_overview" if page_swap > 0.5 else ("dark_daily" if circle > 0.5 else "light_daily")
        cur = path(t, [(10.4, (1100, 600)), (11.3, TOGGLE), (12.4, TOGGLE), (13.2, TAB_RATES), (14.6, (1300, 700))])
        cx, cy = proj(key, cur, cam)
        if 10.9 < t < 11.4:
            fx0, fy0 = proj(key, TOGGLE_BOX[:2], cam)
            fx1, fy1 = proj(key, TOGGLE_BOX[2:], cam)
            focus_ring(stage_img, (fx0, fy0, fx1, fy1), inout(seg(t, 10.9, 11.1)))
        press = clamp(1 - abs(t - 11.35) / 0.12) + clamp(1 - abs(t - 13.25) / 0.12)
        ringp = seg(t, 11.35, 11.9) if 11.35 < t < 11.9 else (seg(t, 13.25, 13.8) if 13.25 < t < 13.8 else 0.0)
        cursor(stage_img, cx, cy, press, ringp)
        tag(stage_img, 0, SH - 44, "DARK THEME" if circle > 0.5 else "LIGHT THEME", 1.0)

    else:                                                                       # --- language: click the ქა button
        chapter = 2
        cam = (SW / 2, SH / 2, 1.0)
        sw = inout(seg(t, 15.55, 15.8))
        base = Image.blend(seen("dark_overview", cam), seen("dark_overview_ka", cam), sw)
        stage_img.paste(base, (0, 0))
        key = "dark_overview"
        cur = path(t, [(14.7, (1300, 650)), (15.45, LANG), (17.4, (1500, 500))])
        cx, cy = proj(key, cur, cam)
        if 15.1 < t < 15.6:
            fx0, fy0 = proj(key, LANG_BOX[:2], cam)
            fx1, fy1 = proj(key, LANG_BOX[2:], cam)
            focus_ring(stage_img, (fx0, fy0, fx1, fy1), inout(seg(t, 15.1, 15.3)))
        press = clamp(1 - abs(t - 15.5) / 0.12)
        ringp = seg(t, 15.5, 16.0) if 15.5 < t < 16.0 else 0.0
        cursor(stage_img, cx, cy, press, ringp)
        tag(stage_img, 0, SH - 44, "GEORGIAN" if sw > 0.5 else "ENGLISH", 1.0)
    return stage_img, chapter


def render(t):
    if t < 2.4 + 0.6:                                                           # hero, sliding up and away
        frame = Image.new("RGBA", (W, H), CANVAS)
        if t > 2.4:
            frame = app(t)
        slide = round(inout(seg(t, 2.4, 3.0)) * H)
        frame.alpha_composite(hero(t), (0, -slide)) if slide < H else None
        return frame.convert("RGB")
    if t >= 17.4:
        if t < 21.2:
            frame = features(t - 17.4)
            if t < 17.9:                                                        # features band rises over the app
                base = app(17.4)
                up = round((1 - inout(seg(t, 17.4, 17.9))) * H)
                base.alpha_composite(frame, (0, up)) if up < H else None
                return base.convert("RGB")
            return frame.convert("RGB")
        frame = end(t - 21.2)
        if t < 21.6:
            f2 = features(t - 17.4)
            f2 = Image.blend(f2, frame, inout(seg(t, 21.2, 21.6)))
            return f2.convert("RGB")
        return frame.convert("RGB")
    return app(t).convert("RGB")


def app(t):
    img = Image.new("RGBA", (W, H), CANVAS)
    stage_img, chapter = stage(t)
    img.alpha_composite(stage_img, (SX, SY))
    rect(img, (SX - 1, SY - 1, SX + SW, SY + SH), outline=FIELD, width=1)
    sub = inout(seg(t, 2.7, 3.1))
    subnav(img, t, chapter, sub)
    # moving gold tab under the active chapter
    x = 520
    pos = []
    for name in CHAPTERS:
        wd = round(sans(21, 600).getlength(name))
        pos.append((x, wd))
        x += wd + 64
    ax = lerp(pos[max(chapter - 1, 0)][0], pos[chapter][0], inout(seg(t, [0, 10.2, 14.6, 17.4][chapter], [0, 10.2, 14.6, 17.4][chapter] + 0.35))) if chapter else pos[0][0]
    aw = pos[chapter][1]
    rect(img, (ax - 6, round(-64 * (1 - sub)) + 59, ax + aw + 6, round(-64 * (1 - sub)) + 64), fill=GOLD_SOFT)
    cap_p = inout(seg(t, 2.8, 3.3))
    for t0, t1, head, body in CAP:
        if t0 <= t < t1:
            caption(img, head, body, cap_p)
            p = inout(seg(t, t0 + 0.25, t0 + 0.9))
            caption_text(img, head, body, p)
    return img


def main():
    missing = [f"{k} ({p})" for k, p in SRC.items() if not os.path.exists(p)] + ([SANS] if not os.path.exists(SANS) else [])
    if missing:
        sys.exit("missing inputs: " + ", ".join(missing))
    os.makedirs(OUT, exist_ok=True)
    if "--still" in sys.argv:
        for s in sys.argv[sys.argv.index("--still") + 1:]:
            p = os.path.join(OUT, f"still-{s}.png")
            render(float(s) / SLOW).save(p)
            print(p)
        return
    out = os.path.join(OUT, "nbg-fx-what-changed.mp4")
    ff = subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p",
                           "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    n = round(DUR * SLOW * FPS)
    for k in range(n):
        ff.stdin.write(np.asarray(render(k / FPS / SLOW)).tobytes())
    ff.stdin.close()
    assert ff.wait() == 0, "ffmpeg failed"
    print(out, f"{n} frames, {DUR * SLOW:.1f}s, {os.path.getsize(out) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()

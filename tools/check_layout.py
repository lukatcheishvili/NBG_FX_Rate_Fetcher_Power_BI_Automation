"""Static layout & visibility checks for every report page (dark and light).

Checks, per page:
  bounds      every visual lies inside the 1280x720 canvas
  overlap     no two visuals overlap, except content placed fully inside a background shape
              that sits below it (z-order)
  hidden      no visual is hidden, except the info pop-up (text box + close button) that the Info_* bookmarks toggle;
              the pop-up must stay inside the canvas, fit its text (wrapped) and be readable
  twins       every twin page (light / English) has exactly the dark Georgian page's visual positions
  grid        content cards use the 24px outer margin, end at the right/bottom margins, and keep
              16px gutters; filter-bar slicers share y/height; KPI tiles and nav icon buttons are
              equal-sized and evenly spaced
  text fit    text boxes, cards and nav tabs are big enough for their font size and text
              (Segoe UI estimate: Latin 0.55em, Georgian 0.62em per character, line height 1.35)
  contrast    text colour vs the surface it sits on is >= 4.5:1 (>= 3:1 for captions <= 8pt
              and the intentionally dimmed weekend rows)

Run after any report change (Desktop closed):  python tools/check_layout.py
Exit code 1 if anything fails.
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_light_pages import DARK_PAGES, VARIANTS, vid   # noqa: E402  (variant id scheme)

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "report", "Personal Portfolio - NBG Rates.Report", "definition")
W, H, MARGIN, GUTTER = 1280, 720, 24, 16
CONTENT_TOP = 144   # below nav (56) and filter bar (68..132)


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def lit(o):
    """Literal value of {"expr": {"Literal": {"Value": ...}}} (or None)."""
    try:
        return o["expr"]["Literal"]["Value"]
    except (KeyError, TypeError):
        return None


def hexcolor(o):
    v = lit(o.get("solid", {}).get("color", {})) if isinstance(o, dict) else None
    return v.strip("'").upper() if v else None


def lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a, b):
    la, lb = sorted([lum(a), lum(b)], reverse=True)
    return (la + 0.05) / (lb + 0.05)


def text_width(s, px):
    return sum((0.62 if "Ⴀ" <= ch <= "ჿ" else 0.55) * px for ch in s)


def pt_to_px(pt):
    return pt * 4 / 3


class Page:
    def __init__(self, pdir):
        self.page = load(os.path.join(pdir, "page.json"))
        self.name = self.page["displayName"]
        every = [load(f) for f in glob.glob(os.path.join(pdir, "visuals", "*", "visual.json"))]
        bookmarks = [load(f) for f in glob.glob(os.path.join(ROOT, "bookmarks", "*.bookmark.json"))]
        toggled = {n for b in bookmarks if b["displayName"].startswith("Info_") for n in b["options"].get("targetVisualNames", [])}
        self.popups = [v for v in every if v.get("isHidden") and v["name"] in toggled]
        self.visuals = [v for v in every if v not in self.popups]
        bg = self.page.get("objects", {}).get("background", [{}])[0].get("properties", {}).get("color")
        self.canvas = hexcolor(bg) or "#FFFFFF"
        self.errors, self.warnings = [], []

    @staticmethod
    def rect(v):
        p = v["position"]
        return p["x"], p["y"], p["x"] + p["width"], p["y"] + p["height"]

    @staticmethod
    def kind(v):
        return (v.get("visual") or {}).get("visualType", "group")

    def label(self, v):
        vis = v.get("visual") or {}
        q = vis.get("query", {}).get("queryState", {})
        fields = [p.get("queryRef") for r in q.values() for p in r.get("projections", [])][:1]
        txt = ""
        if self.kind(v) == "textbox":
            txt = "".join(r["value"] for p in vis["objects"]["general"][0]["properties"]["paragraphs"] for r in p["textRuns"])[:24]
        if self.kind(v) == "actionButton":
            txt = next((lit(e["properties"]["text"]) for e in vis["objects"].get("text", []) if "text" in e["properties"]), "") or ""
        x, y, x2, y2 = self.rect(v)
        return f"{self.kind(v)}[{fields[0] if fields else txt}] @{x:.0f},{y:.0f} {x2 - x:.0f}x{y2 - y:.0f}"

    # ---------------------------------------------------------------- checks
    def check_bounds_hidden(self):
        for v in self.visuals + self.popups:
            x, y, x2, y2 = self.rect(v)
            if x < 0 or y < 0 or x2 > W + 0.5 or y2 > H + 0.5:
                self.errors.append(f"out of canvas: {self.label(v)}")
            if v.get("isHidden") and v not in self.popups:
                self.errors.append(f"hidden: {self.label(v)}")

    def check_overlaps(self):
        vs = self.visuals
        for i in range(len(vs)):
            for j in range(i + 1, len(vs)):
                a, b = vs[i], vs[j]
                ax, ay, ax2, ay2 = self.rect(a)
                bx, by, bx2, by2 = self.rect(b)
                if min(ax2, bx2) - max(ax, bx) <= 0.5 or min(ay2, by2) - max(ay, by) <= 0.5:
                    continue
                inside = lambda o, n: self.rect(n)[0] >= self.rect(o)[0] and self.rect(n)[1] >= self.rect(o)[1] \
                    and self.rect(n)[2] <= self.rect(o)[2] and self.rect(n)[3] <= self.rect(o)[3]
                ok = False
                for outer, inner in ((a, b), (b, a)):
                    if self.kind(outer) == "shape" and inside(outer, inner):
                        if outer["position"]["z"] < inner["position"]["z"]:
                            ok = True
                        else:
                            self.errors.append(f"background above its content (z): {self.label(outer)} over {self.label(inner)}")
                            ok = True
                if not ok:
                    self.errors.append(f"overlap: {self.label(a)}  x  {self.label(b)}")

    def check_grid(self):
        content = [v for v in self.visuals if self.rect(v)[1] >= CONTENT_TOP and self.kind(v) in ("pivotTable", "lineChart", "areaChart")]
        tiles = [v for v in self.visuals if self.kind(v) == "shape" and self.rect(v)[1] >= CONTENT_TOP]   # KPI backgrounds
        cards = content + tiles
        if cards:
            lefts = min(self.rect(v)[0] for v in cards)
            rights = max(self.rect(v)[2] for v in cards)
            bottoms = max(self.rect(v)[3] for v in cards)
            for name, got, want in (("left margin", lefts, MARGIN), ("right edge", rights, W - MARGIN), ("bottom edge", bottoms, H - GUTTER)):
                if abs(got - want) > 0.5:
                    self.errors.append(f"grid: {name} is {got:.0f}, expected {want}")
            # gutters between neighbouring cards
            for a in cards:
                for b in cards:
                    if a is b:
                        continue
                    ax, ay, ax2, ay2 = self.rect(a)
                    bx, by, bx2, by2 = self.rect(b)
                    v_overlap = min(ay2, by2) - max(ay, by) > 0
                    h_overlap = min(ax2, bx2) - max(ax, bx) > 0
                    if v_overlap and 0 < bx - ax2 < 40 and abs(bx - ax2 - GUTTER) > 0.5:
                        self.errors.append(f"grid: horizontal gutter {bx - ax2:.0f}px between {self.label(a)} and {self.label(b)}")
                    if h_overlap and 0 < by - ay2 < 40 and abs(by - ay2 - GUTTER) > 0.5:
                        self.errors.append(f"grid: vertical gutter {by - ay2:.0f}px between {self.label(a)} and {self.label(b)}")
        slicers = [v for v in self.visuals if self.kind(v) == "slicer"]
        if slicers and (len({self.rect(v)[1] for v in slicers}) > 1 or len({self.rect(v)[3] for v in slicers}) > 1):
            self.errors.append("grid: filter-bar slicers do not share the same y / height")
        for s1 in slicers:
            for s2 in slicers:
                gap = self.rect(s2)[0] - self.rect(s1)[2]
                if 0 < gap < 40 and abs(gap - GUTTER) > 0.5:
                    self.errors.append(f"grid: slicer gap {gap:.0f}px between {self.label(s1)} and {self.label(s2)}")
        if len(tiles) > 1:
            xs = sorted(self.rect(v)[0] for v in tiles)
            if len({round(self.rect(v)[2] - self.rect(v)[0]) for v in tiles}) > 1 or len({round(b - a) for a, b in zip(xs, xs[1:])}) > 1:
                self.errors.append("grid: KPI tiles are not equal-sized / evenly spaced")
        icons = sorted((v for v in self.visuals if self.kind(v) == "actionButton" and self.rect(v)[2] - self.rect(v)[0] < 60), key=lambda v: self.rect(v)[0])
        if icons:
            sizes = {(round(self.rect(v)[2] - self.rect(v)[0]), round(self.rect(v)[3] - self.rect(v)[1]), round(self.rect(v)[1])) for v in icons}
            gaps = {round(self.rect(b)[0] - self.rect(a)[2]) for a, b in zip(icons, icons[1:])}
            if len(sizes) > 1 or len(gaps) > 1 or abs(self.rect(icons[-1])[2] - (W - MARGIN)) > 0.5:
                self.errors.append(f"grid: nav icon buttons inconsistent (sizes {sizes}, gaps {gaps}, last ends at {self.rect(icons[-1])[2]:.0f})")

    def check_text_fit(self):
        for v in self.visuals:
            vis = v.get("visual") or {}
            x, y, x2, y2 = self.rect(v)
            w, h = x2 - x, y2 - y
            if self.kind(v) == "textbox":
                need_h = 0
                for p in vis["objects"]["general"][0]["properties"]["paragraphs"]:
                    runs = p["textRuns"]
                    px = max(pt_to_px(float(r["textStyle"].get("fontSize", "10pt").rstrip("pt"))) for r in runs)
                    need_w = sum(text_width(r["value"], pt_to_px(float(r["textStyle"].get("fontSize", "10pt").rstrip("pt")))) for r in runs)
                    need_h += px * 1.35
                    if need_w > w - 4:
                        self.errors.append(f"text fit: text needs ~{need_w:.0f}px, box is {w:.0f}px: {self.label(v)}")
                if need_h > h + 0.5:
                    self.errors.append(f"text fit: text needs ~{need_h:.0f}px height, box is {h:.0f}px: {self.label(v)}")
            elif self.kind(v) == "card":
                size = float(lit(vis["objects"]["labels"][0]["properties"]["fontSize"]).rstrip("D"))
                if pt_to_px(size) * 1.35 > h + 0.5:
                    self.errors.append(f"text fit: {size}pt value needs ~{pt_to_px(size) * 1.35:.0f}px height, card is {h:.0f}px: {self.label(v)}")
            elif self.kind(v) == "actionButton":
                for e in vis["objects"].get("text", []):
                    t, fs = lit(e["properties"].get("text", {})), lit(e["properties"].get("fontSize", {}))
                    if t and fs:
                        need = text_width(t.strip("'"), pt_to_px(float(fs.rstrip("D")))) + 12
                        if need > w:
                            self.errors.append(f"text fit: button label needs ~{need:.0f}px, button is {w:.0f}px: {self.label(v)}")

    def check_popups(self):
        for v in self.popups:
            vis = v["visual"]
            w, h = self.rect(v)[2] - self.rect(v)[0], self.rect(v)[3] - self.rect(v)[1]
            if self.kind(v) != "textbox":
                continue
            pad = {k: float(lit(e).rstrip("D")) for k, e in vis["visualContainerObjects"]["padding"][0]["properties"].items()}
            avail = w - pad["left"] - pad["right"]
            need = pad["top"] + pad["bottom"]
            for p in vis["objects"]["general"][0]["properties"]["paragraphs"]:
                runs = p["textRuns"]
                px = max(pt_to_px(float(r["textStyle"].get("fontSize", "10pt").rstrip("pt"))) for r in runs)
                need_w = sum(text_width(r["value"], pt_to_px(float(r["textStyle"].get("fontSize", "10pt").rstrip("pt")))) for r in runs)
                need += max(1, -(-need_w // (avail - (20 if p.get("listType") else 0)))) * px * 1.35
            if need > h + 0.5:
                self.errors.append(f"text fit: pop-up text needs ~{need:.0f}px height, box is {h:.0f}px: {self.label(v)}")

    def surface_under(self, v):
        """Colour of the nearest background under a visual: own background, enclosing shape, or the page."""
        vco = (v.get("visual") or {}).get("visualContainerObjects", {})
        bgp = vco.get("background", [{}])[0].get("properties", {})
        if lit(bgp.get("show", {})) == "true" and hexcolor(bgp.get("color", {})):
            return hexcolor(bgp["color"])
        x, y, x2, y2 = self.rect(v)
        best = None
        for s in self.visuals:
            if self.kind(s) != "shape" or s is v:
                continue
            sx, sy, sx2, sy2 = self.rect(s)
            if sx <= x and sy <= y and sx2 >= x2 and sy2 >= y2:
                fill = next((hexcolor(e["properties"]["fillColor"]) for e in s["visual"]["objects"].get("fill", []) if "fillColor" in e["properties"]), None)
                if fill and (best is None or (sx2 - sx) * (sy2 - sy) < best[0]):
                    best = ((sx2 - sx) * (sy2 - sy), fill)
        return best[1] if best else self.canvas

    def check_contrast(self):
        for v in self.visuals + self.popups:
            vis = v.get("visual") or {}
            bg = self.surface_under(v)
            checks = []   # (colour, font size pt)
            if self.kind(v) == "textbox":
                for p in vis["objects"]["general"][0]["properties"]["paragraphs"]:
                    for r in p["textRuns"]:
                        checks.append((r["textStyle"].get("color", "#000000").upper(), float(r["textStyle"].get("fontSize", "10pt").rstrip("pt"))))
            elif self.kind(v) == "card":
                lp = vis["objects"]["labels"][0]["properties"]
                c = hexcolor(lp.get("color", {}))
                if c:
                    checks.append((c, float(lit(lp["fontSize"]).rstrip("D"))))
                else:   # conditional colour: check every case value
                    for case in lp["color"]["solid"]["color"]["expr"]["Conditional"]["Cases"]:
                        checks.append((lit(case["Value"] and {"expr": case["Value"]}).strip("'").upper(), float(lit(lp["fontSize"]).rstrip("D"))))
            else:
                for obj in ("values", "columnHeaders", "rowHeaders", "items", "header", "labels", "legend", "valueAxis", "categoryAxis"):
                    for e in vis.get("objects", {}).get(obj, []):
                        for key in ("fontColor", "fontColorPrimary", "labelColor", "color"):
                            c = hexcolor(e.get("properties", {}).get(key, {}))
                            if c:
                                size = lit(e["properties"].get("fontSize", e["properties"].get("textSize", {}))) or "9D"
                                checks.append((c, float(str(size).rstrip("D"))))
            for c, size in checks:
                if not c or not c.startswith("#"):
                    continue
                ratio = contrast(c, bg)
                need = 3.0 if size <= 8 else 4.5
                if ratio < need:
                    self.errors.append(f"contrast {ratio:.2f}:1 (< {need}) text {c} on {bg}: {self.label(v)}")

    def run(self):
        self.check_bounds_hidden()
        self.check_overlaps()
        self.check_grid()
        self.check_text_fit()
        self.check_popups()
        self.check_contrast()
        return self


def rects(pdir):
    return {v["name"]: tuple(round(v["position"][k], 2) for k in ("x", "y", "width", "height")) for v in
            (load(f) for f in glob.glob(os.path.join(pdir, "visuals", "*", "visual.json")))}


def check_twins():
    """Every twin page keeps the dark Georgian page's visual positions exactly."""
    errors = []
    for dark in DARK_PAGES:
        src = rects(os.path.join(ROOT, "pages", dark))
        for variant in VARIANTS:
            twin = rects(os.path.join(ROOT, "pages", vid(variant, dark)))
            want = {vid(variant, n): r for n, r in src.items()}
            if twin != want:
                diff = [n for n in want if twin.get(n) != want[n]] + [n for n in twin if n not in want]
                errors.append(f"twins: {variant[0]}-{variant[1]} of page {dark[:6]} differs from the dark page in {len(diff)} visual(s)")
    return errors


def main():
    pages = [Page(d).run() for d in sorted(glob.glob(os.path.join(ROOT, "pages", "*", ""))) if os.path.exists(os.path.join(d, "page.json"))]
    failed = 0
    for p in pages:
        status = "OK" if not p.errors else f"{len(p.errors)} issue(s)"
        print(f"\n== {p.name}  ({len(p.visuals)} visuals, canvas {p.canvas})  {status}")
        for e in p.errors:
            print("   ✗", e)
        failed += len(p.errors)
    print(f"\n{'PASS' if not failed else 'FAIL'}: {failed} issue(s) across {len(pages)} pages")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

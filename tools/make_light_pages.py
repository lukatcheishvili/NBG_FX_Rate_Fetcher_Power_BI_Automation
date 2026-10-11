"""Generate the light-mode twin of every dark report page.

The dark pages are the source of truth. This script:
  1. adds a sun (light-mode) toggle to each dark page's top nav (once) and syncs its slicers,
  2. (re)creates a light copy of each dark page with deterministic page/visual IDs,
     recoloured with the light palette from docs/decisions.md,
  3. rewires the copies (nav tabs, info, reset bookmark, interactions) to the light pages.

Never edit the light pages by hand: change the dark page, close Power BI Desktop, then run
    python tools/make_light_pages.py
"""
import glob
import hashlib
import json
import os
import re
import shutil

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "report", "Personal Portfolio - NBG Rates.Report", "definition")
VC_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.13.0/schema.json"
DARK_PAGES = ["c3f04a68e646beb08f26", "3bcc3906b609a5ffe1ba", "5b2b60aaacad67c46039"]
HOME_BOOKMARK = {"c3f04a68e646beb08f26": "daec94e35a90330350bd", "3bcc3906b609a5ffe1ba": "1389e2acf97263acf89b",
                 "5b2b60aaacad67c46039": "5fd1248811f3e14aca92"}

# dark (Ferrari, docs/design/ferrari.md) -> light v3: warm, low-glare palette approved in Figma
# (file H8YXahhpwjKxgJWpwr2exe, "— Light" screens). No pure white or black. See docs/decisions.md, "Light mode".
PALETTE = {
    "181818": "EFEEEA",  # canvas       -> warm grey page
    "222222": "FAF9F7",  # card         -> warm off-white
    "303030": "E2DFD9",  # elevated / hairline borders and grid lines
    "FFFFFF": "22201C",  # ink          (15.5:1 on card)
    "969696": "5F5B54",  # body         (6.4:1)
    "666666": "8A857C",  # muted        (3.5:1)
    "2C2C2A": "E8E5E0",  # chart grid
    "F0EFEC": "22201C",  # area line    -> ink
    "FF5A4F": "B42318",  # rate up      (6.3:1)
    "22B066": "0E7A43",  # rate down    (5.1:1)
    # accent #DA291C (Ferrari red) is kept in both modes
    "3987E5": "2A78D6", "D95926": "EB6834", "199E70": "1BAF7A", "C98500": "EDA100", "D55181": "E87BA4",
}
LIGHT_CARD, LIGHT_HAIRLINE = "'#FAF9F7'", "'#E2DFD9'"
CARD_RADIUS = ("8D", "8D")       # same corners as dark mode
SHAPE_RADIUS = ("8L", "8L")
HEX = re.compile(r"#([0-9A-Fa-f]{6})\b")


def light_id(dark_id):
    return hashlib.md5(("light:" + dark_id).encode()).hexdigest()[:20]


def toggle_id(page_id):
    return hashlib.md5(("toggle:" + page_id).encode()).hexdigest()[:20]


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def lit(v):
    return {"expr": {"Literal": {"Value": v}}}


def text_lit(s):
    return lit("'" + s.replace("'", "''") + "'")


def color(h):
    return {"solid": {"color": lit("'" + h + "'")}}


def toggle_button(name, target_page, symbol, tooltip):
    """32x32 nav button (same look as reset/info) that jumps to the other mode's twin page."""
    p = lambda props, sel=None: {"properties": props, **({"selector": sel} if sel else {})}
    return {
        "$schema": VC_SCHEMA, "name": name,
        "position": {"x": 1144, "y": 12, "z": 1032, "height": 32, "width": 32, "tabOrder": 1032},
        "visual": {
            "visualType": "actionButton",
            "objects": {
                "icon": [p({"shapeType": text_lit("blank")}, {"id": "default"}), p({"show": lit("false")})],
                "text": [p({"show": lit("true")}),
                         p({"text": text_lit(symbol), "fontColor": color("#969696"), "fontSize": lit("12D"),
                            "fontFamily": text_lit("Segoe UI Symbol"), "horizontalAlignment": text_lit("center"),
                            "verticalAlignment": text_lit("middle"), "leftMargin": lit("0L"), "rightMargin": lit("0L"),
                            "topMargin": lit("0L"), "bottomMargin": lit("0L")}, {"id": "default"}),
                         p({"fontColor": color("#FFFFFF")}, {"id": "hover"})],
                "fill": [p({"show": lit("true")}), p({"fillColor": color("#222222"), "transparency": lit("0D")}, {"id": "default"}),
                         p({"fillColor": color("#303030"), "transparency": lit("0D")}, {"id": "hover"})],
                "outline": [p({"show": lit("true")}), p({"lineColor": color("#303030"), "weight": lit("1D")}, {"id": "default"})],
                "shape": [p({"tileShape": text_lit("rectangle"), "roundEdge": lit("4L")})],
            },
            # identical container to the reset/info buttons so all three icons sit on the same grid
            "visualContainerObjects": {
                "background": [p({"show": lit("false")})],
                "border": [p({"show": lit("false"), "radius": lit("8D")})],
                "dropShadow": [p({"show": lit("false")})],
                "title": [p({"show": lit("false")})],
                "padding": [p({"top": lit("0D"), "bottom": lit("0D"), "left": lit("2D"), "right": lit("2D")})],
                "visualHeader": [p({"show": lit("false")})],
                "visualLink": [p({"show": lit("true"), "type": text_lit("PageNavigation"), "navigationSection": text_lit(target_page),
                                  "tooltip": text_lit(tooltip), "showDefaultTooltip": lit("false")})],
            },
            "drillFilterOtherVisuals": True,
        },
    }


def soften(v):
    """Light cards get a hairline edge (dark mode separates cards by brightness alone)."""
    vis = v.get("visual") or {}
    for e in vis.get("visualContainerObjects", {}).get("border", []):
        p = e.get("properties", {})
        if p.get("color") == color(LIGHT_CARD.strip("'")):
            p["color"] = color(LIGHT_HAIRLINE.strip("'"))
        if p.get("radius") == lit(CARD_RADIUS[0]):
            p["radius"] = lit(CARD_RADIUS[1])
    for e in vis.get("objects", {}).get("shape", []) if vis.get("visualType") == "shape" else []:
        p = e.get("properties", {})
        if p.get("roundEdge") == lit(SHAPE_RADIUS[0]):
            p["roundEdge"] = lit(SHAPE_RADIUS[1])
            vis["objects"]["outline"] = [{"properties": {"show": lit("true"), "lineColor": color(LIGHT_HAIRLINE.strip("'")), "weight": lit("1D")}}]
    return v


def is_nav_tab(v):
    vis = v.get("visual") or {}
    if vis.get("visualType") != "actionButton":
        return False
    link = (vis.get("visualContainerObjects", {}).get("visualLink") or [{}])[0].get("properties", {})
    has_text = any("text" in e.get("properties", {}) for e in vis.get("objects", {}).get("text", []))
    return link.get("type") == text_lit("PageNavigation") and has_text and v["position"]["width"] > 100


def main():
    light_pages = {d: light_id(d) for d in DARK_PAGES}

    # 1. dark pages: toggle (once), tab shift (once), slicer sync groups
    for dark in DARK_PAGES:
        vdir = os.path.join(ROOT, "pages", dark, "visuals")
        tid = toggle_id(dark)
        first_run = not os.path.exists(os.path.join(vdir, tid))
        for f in glob.glob(os.path.join(vdir, "*", "visual.json")):
            v = load(f)
            vis = v.get("visual") or {}
            changed = False
            if first_run and (is_nav_tab(v) or (vis.get("visualType") == "shape" and v["position"]["height"] == 2 and v["position"]["y"] == 54)):
                v["position"]["x"] -= 40
                changed = True
            if vis.get("visualType") == "slicer":
                vis["syncGroup"] = {"groupName": "sync_" + v["name"], "fieldChanges": True, "filterChanges": True}
                changed = True
            if changed:
                save(f, v)
        save(os.path.join(vdir, tid, "visual.json"), toggle_button(tid, light_pages[dark], "☀", "ღია რეჟიმი"))

    # 2. remove previous light pages and light bookmarks
    for lp in light_pages.values():
        shutil.rmtree(os.path.join(ROOT, "pages", lp), ignore_errors=True)
    bdir = os.path.join(ROOT, "bookmarks")
    light_bookmarks = {HOME_BOOKMARK[d]: light_id(HOME_BOOKMARK[d]) for d in DARK_PAGES}
    for lb in light_bookmarks.values():
        p = os.path.join(bdir, lb + ".bookmark.json")
        if os.path.exists(p):
            os.remove(p)

    # 3. build light twins
    for dark, lp in light_pages.items():
        src = os.path.join(ROOT, "pages", dark)
        vmap = {}
        visuals = []
        for f in glob.glob(os.path.join(src, "visuals", "*", "visual.json")):
            v = load(f)
            vmap[v["name"]] = light_id(v["name"])
            visuals.append(v)

        def to_light(obj):
            s = json.dumps(obj, ensure_ascii=False)
            s = HEX.sub(lambda m: "#" + PALETTE.get(m.group(1).upper(), m.group(1)), s)
            s = s.replace('"Property": "Weekend_Font_Color"', '"Property": "Weekend_Font_Color_Light"')
            for d, l in light_pages.items():
                s = s.replace("'" + d + "'", "'" + l + "'")
            for d, l in light_bookmarks.items():
                s = s.replace("'" + d + "'", "'" + l + "'")
            return json.loads(s)

        for v in visuals:
            lv = to_light(v)
            lv["name"] = vmap[v["name"]]
            if lv.get("parentGroupName"):
                lv["parentGroupName"] = vmap.get(lv["parentGroupName"], lv["parentGroupName"])
            if v["name"] == toggle_id(dark):
                lv = toggle_button(lv["name"], dark, "☾", "მუქი რეჟიმი")
                lv = to_light(lv)
                lv["visual"]["visualContainerObjects"]["visualLink"][0]["properties"]["navigationSection"] = text_lit(dark)
            soften(lv)
            save(os.path.join(ROOT, "pages", lp, "visuals", lv["name"], "visual.json"), lv)

        page = to_light(load(os.path.join(src, "page.json")))
        page["name"] = lp
        page["displayName"] = page["displayName"] + " · ღია"
        page["visibility"] = "HiddenInViewMode"
        page["visualInteractions"] = [{**i, "source": vmap.get(i["source"], i["source"]), "target": vmap.get(i["target"], i["target"])}
                                      for i in page.get("visualInteractions", [])]
        save(os.path.join(ROOT, "pages", lp, "page.json"), page)

        # reset bookmark for the light page
        b = load(os.path.join(bdir, HOME_BOOKMARK[dark] + ".bookmark.json"))
        s = json.dumps(b, ensure_ascii=False).replace(dark, lp)
        for d, l in vmap.items():
            s = s.replace(d, l)
        lb = json.loads(s)
        lb["name"] = light_bookmarks[HOME_BOOKMARK[dark]]
        lb["displayName"] = b.get("displayName", "Home") + "_Light"
        save(os.path.join(bdir, lb["name"] + ".bookmark.json"), lb)

    # 4. register pages and bookmarks
    pj = os.path.join(ROOT, "pages", "pages.json")
    pages = load(pj)
    pages["pageOrder"] = [p for p in pages["pageOrder"] if p not in light_pages.values()] + list(light_pages.values())
    save(pj, pages)
    bj = os.path.join(bdir, "bookmarks.json")
    bm = load(bj)
    bm["items"] = [i for i in bm["items"] if i["name"] not in light_bookmarks.values()] + [{"name": n} for n in light_bookmarks.values()]
    save(bj, bm)
    print("light pages:", light_pages)


if __name__ == "__main__":
    main()

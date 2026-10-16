"""Generate the twin pages of every dark Georgian report page: light mode and English.

The dark Georgian pages are the source of truth. For each of them this script:
  1. adds the nav buttons (language EN/ქა, sun, info), the info pop-up panel with its two bookmarks,
     and syncs the slicers (once-only layout shifts are keyed on the buttons already existing),
  2. (re)creates three twins with deterministic page/visual IDs: light-ka, dark-en, light-en
     (light = palette below; en = English texts and the *_En model fields from docs/decisions.md),
  3. rewires every twin (nav tabs, buttons, reset and info bookmarks, interactions) to its own variant.

Never edit the twin pages by hand: change the dark Georgian page, close Power BI Desktop, then run
    python tools/make_light_pages.py
"""
import glob
import hashlib
import json
import math
import os
import re
import shutil
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "report", "Personal Portfolio - NBG Rates.Report", "definition")
VC_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.13.0/schema.json"
BM_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/bookmark/2.1.0/schema.json"
DARK_PAGES = ["c3f04a68e646beb08f26", "3bcc3906b609a5ffe1ba", "5b2b60aaacad67c46039"]
HOME_BOOKMARK = {"c3f04a68e646beb08f26": "daec94e35a90330350bd", "3bcc3906b609a5ffe1ba": "1389e2acf97263acf89b",
                 "5b2b60aaacad67c46039": "5fd1248811f3e14aca92"}

# (mode, language) of the dark Georgian source is ("dark", "ka"); these are the generated twins
VARIANTS = [("light", "ka"), ("dark", "en"), ("light", "en")]
_PREFIX = {("light", "ka"): "light:", ("dark", "en"): "en:", ("light", "en"): "light-en:"}
_SUFFIX = {("light", "ka"): " · ღია", ("dark", "en"): "", ("light", "en"): " · Light"}
_BM_SUFFIX = {("light", "ka"): "_Light", ("dark", "en"): "_En", ("light", "en"): "_Light_En"}

# moon for the dark-mode button; U+FE0E asks for the plain (grey) glyph instead of the coloured emoji
MOON = "🌛︎"

# nav icon row: x of each 32x32 button (8px gaps, 24px right margin)
LANG_X, TOGGLE_X, INFO_X = 1104, 1144, 1224
# info pop-up panel, aligned with the right column; the close button sits 8px inside its top-right corner
PANEL = {"x": 880, "y": 68, "w": 376, "pad_l": 16, "pad_r": 40, "pad_v": 16}
CLOSE = {"x": 1224, "y": 76, "size": 24}
POPUP_Z = 4000   # above every page visual (they stop at z 3012), so the open panel is never hidden by a slicer or table
CREATOR = {"ka": "ლუკა ჭეიშვილი", "en": "Luka Tcheishvili"}

# dark (Ferrari, docs/design/ferrari.md) -> light v4 "Stone": a calm, low-glare grey palette chosen from a side-by-side mock
# (v3 was a warm off-white that still read as too bright). No pure white or black. See docs/decisions.md, "Twin pages".
PALETTE = {
    "181818": "E1E2E0",  # canvas       -> soft stone grey page
    "222222": "EBECEA",  # card         -> light stone
    "303030": "D9DBD8",  # elevated: inputs, button fills, table grid lines
    "FFFFFF": "20221F",  # ink          (13.5:1 on card)
    "969696": "50544F",  # body         (6.5:1)
    "666666": "737772",  # muted        (3.8:1)
    "2C2C2A": "D6D8D5",  # chart grid
    "F0EFEC": "20221F",  # area line    -> ink
    "FF5A4F": "B42318",  # rate up      (5.5:1)
    "22B066": "0E7A43",  # rate down    (4.6:1)
    # accent #DA291C (Ferrari red) is kept in both modes
    "3987E5": "2A78D6", "D95926": "EB6834", "199E70": "1BAF7A", "C98500": "EDA100", "D55181": "E87BA4",
}
LIGHT_CARD, LIGHT_HAIRLINE = "'#EBECEA'", "'#CFD1CE'"
CARD_RADIUS = ("8D", "8D")       # same corners as dark mode
SHAPE_RADIUS = ("8L", "8L")
HEX = re.compile(r"#([0-9A-Fa-f]{6})\b")
GEORGIAN = re.compile(r"[Ⴀ-ჿ]")

# ---------------------------------------------------------------------------- English texts
# Static strings of the Georgian pages. Whole-value match (a Literal's surrounding quotes are ignored).
TEXT_EN = {
    "ვალუტა · გრაფიკი": "Currency · chart",
    "ვალუტა": "Currency",
    "კურსი K ერთეულზე · შაბათ-კვირა: პარასკევს დადგენილი კურსი": "Rate per K units · Weekends: the rate set on Friday",
    "მიმდინარე, დაუსრულებელი თვე არ ჩანს": "The current, unfinished month is not shown",
    "ოფიციალური კურსები": "Official rates",
    "ოფიციალური საშუალოთვიური გაცვლითი კურსები": "Official average monthly exchange rates",
    "ოფიციალური ყოველდღიური გაცვლითი კურსები": "Official daily exchange rates",
    "პერიოდი": "Period",
    "საშუალოთვიური ცხრილი": "Monthly table",
    "სიხშირე": "Frequency",
    "უცხოური ვალუტის ცვლილება ლართან მიმართებაში": "Change of foreign currencies against the lari",
    "ფილტრების საწყის მდგომარეობაზე დაბრუნება": "Reset filters to default",
    "ყოველდღიური ცხრილი": "Daily table",
    "შედარებისთვის": "Compare",
    "ბოლო განახლება": "Last update",
    "თვის ბოლოს": "End of month",
    "ლარი (GEL) · წყარო: საქართველოს ეროვნული ბანკი": "Lari (GEL) · Source: National Bank of Georgia",
    "მაქსიმალური": "Maximum",
    "მინიმალური": "Minimum",
    "მიმდინარე გაცვლითი კურსი": "Current exchange rate",
    "ოფიციალური გაცვლითი კურსები": "Official exchange rates",
    "საბაზისო გაცვლითი კურსი": "Base exchange rate",
    "საშუალოდ თვეში": "Monthly average",
}
# Georgian currency name -> English name. Source: the header rows of NBG's two English rate files
# (exchange_rates/eng/official-daily-exchange-rateseng.xlsx, exratesyearseng.xlsx), matched to the Georgian files by ISO code;
# where codes share a Georgian name, the code NBG still publishes wins (as in the Mapping query).
# The last three keys are spellings used by NBG's original report that differ from the current files.
CURRENCY_EN = {
    "ბულგარული ლევი": "Bulgarian Lev",
    "დანიური კრონი": "Danish Krone",
    "ევრო": "Euro",
    "დიდი ბრიტანეთის გირვანქა სტერლინგი": "Pound Sterling",
    "ისლანდიური კრონი": "Iceland Krona",
    "სერბიული დინარი": "Serbian Dinar",
    "ნორვეგიული კრონი": "Norwegian Krone",
    "პოლონური ზლოტი": "Polish Zloty",
    "რუმინული ლეი": "Romanian Leu",
    "უნგრული ფორინტი": "Hungarian Forint",
    "შვედური კრონი": "Swedish Krona",
    "შვეიცარიული ფრანკი": "Swiss Franc",
    "ჩეხური კრონა": "Czech Koruna",
    "აშშ დოლარი": "US Dollar",
    "კანადური დოლარი": "Canadian Dollar",
    "ავსტრალიური დოლარი": "Australian Dollar",
    "ეგვიპტური გირვანქა": "Egyptian Pound",
    "თურქული ლირა": "Turkish Lira",
    "იაპონური იენი": "Japanese Yen",
    "არაბეთის გაერთიანებული საამიროების დირჰამი": "UAE Dirham",
    "ირანული რიალი": "Iranian Rial",
    "ისრაელის შეკელი": "New Israeli Sheqel",
    "სინგაპურული დოლარი": "Singapore Dollar",
    "ქუვეითური დინარი": "Kuwaiti Dinar",
    "ჩინური იუანი": "Chinese Yuan Renminbi",
    "ჰონკონგური დოლარი": "Hong Kong Dollar",
    "ინდური რუპია": "Indian Rupee",
    "ახალზელანდიური დოლარი": "New Zealand Dollar",
    "რუსული რუბლი": "Russian Ruble",
    "აზერბაიჯანული მანათი": "Azerbaijanian Manat",
    "ბელარუსული რუბლი": "Belarussian Ruble",
    "ესტონური კრონა": "Estonian Kroon",
    "თურქმენული მანათი": "Turkmenistan New Manat",
    "ლატვიური ლატი": "Latvian Lats",
    "ლიეტუვური ლიტი": "Lithuanian Litas",
    "მოლდოვური ლეი": "Moldovan Leu",
    "სომხური დრამი": "Armenian Dram",
    "ტაჯიკური სომონი": "Tajikistan Somoni",
    "უზბეკური სუმი": "Uzbekistan Sum",
    "უკრაინული გრივნა": "Ukrainian Hryvnia",
    "ყაზახური ტენგე": "Kazakhstan Tenge",
    "ყირგიზული სომი": "Kyrgyzstan Som",
    "სამხრეთ აფრიკული რანდი": "South African Rand",
    "ბრაზილიური რიალი": "Brazilian Real",
    "კატარული რიალი": "Qatari Rial",
    "სამხრეთ კორეული ვონი": "South Korean Won",
    "კვიპროსული გირვანქა სტერლინგი": "Cypriot Pounds",
    "ავსტრიული შილინგი": "Austrian Schilling",
    "ბელგიური ფრანკი": "Belgian Franc",
    "გერმანული მარკა": "German Mark",
    "ჰოლანდიური გულდენი": "Dutch Guilder",
    "იტალიური ლირა": "Italian Lira",
    "ფინური მარკა": "Finnish Mark",
    "ფრანგული ფრანკი": "French Franc",
    "ესპანური პესეტა": "Spanish Peseta",
    "ბერძნული დრაჰმა": "Greek Drachma",
    "ირლანდიური ფუნტი": "Irish Pound",
    "ლუქსემბურგული ფრანკი": "Luxembourg Franc",
    "პორტუგალიური ესკუდო": "Portuguese Escudo",
    "ყატარული რიალი": "Qatari Rial",
    "მოლდავური ლეი": "Moldovan Leu",
    "ესტონური კრონი": "Estonian Kroon",
}

# Info pop-up content: (kind, text...) per page and language. kinds: title, blank, kv(label, value), head, bullet, note
INFO = {
    "c3f04a68e646beb08f26": {
        "ka": [("title", "ოფიციალური ყოველდღიური გაცვლითი კურსები"), ("blank",),
               ("kv", "პერიოდულობა: ", "ყოველდღიური"),
               ("head", "საერთო ფილტრები:"), ("bullet", "პერიოდის შუალედი"), ("bullet", "სიხშირე"),
               ("head", "ფილტრები:"),
               ("bullet", "ვალუტა | ფილტრი მოქმედებს ოფიციალური გაცვლითი კურსის გრაფიკზე"),
               ("bullet", "შეარჩიეთ ვალუტა შედარებისთვის | ფილტრი მოქმედებს უცხოური ვალუტის ლართან მიმართებაში ცვლილების გრაფიკზე"),
               ("kv", "საბაზისო თარიღი:", " ცვალებადია და დამოკიდებულია პერიოდის შუალედის და სიხშირის ფილტრებზე"),
               ("blank",), ("note", "მონაცემები ხელმისაწვდომია 2001 წლის იანვრიდან"),
               ("blank",), ("kv", "შემქმნელი: ", CREATOR["ka"])],
        "en": [("title", "Official Daily Exchange Rates"), ("blank",),
               ("kv", "Frequency: ", "Daily"),
               ("head", "Common Filters:"), ("bullet", "Period Range"), ("bullet", "Frequency"),
               ("head", "Filters:"),
               ("bullet", "Currency | filter has effect on diagram of official daily exchange rate"),
               ("bullet", "Choose currency for comparison | filter has effect on diagram of change of foreign currency against Georgian Lari"),
               ("kv", "Base Date:", " Varies and depends on period range and frequency filters"),
               ("blank",), ("note", "Data is available from January 2001"),
               ("blank",), ("kv", "Created by: ", CREATOR["en"])],
    },
    "3bcc3906b609a5ffe1ba": {
        "ka": [("title", "ცხრილი - ოფიციალური ყოველდღიური გაცვლითი კურსები"), ("blank",),
               ("kv", "პერიოდულობა: ", "ყოველდღიური"), ("blank",),
               ("head", "საერთო ფილტრები:"), ("bullet", "პერიოდის შუალედი"), ("bullet", "სიხშირე"), ("bullet", "ვალუტა"),
               ("blank",), ("note", "მონაცემები ხელმისაწვდომია 2001 წლის იანვრიდან"),
               ("blank",), ("kv", "შემქმნელი: ", CREATOR["ka"])],
        "en": [("title", "Table - Official Daily Exchange Rates"), ("blank",),
               ("kv", "Frequency: ", "Daily"), ("blank",),
               ("head", "Common Filters:"), ("bullet", "Period Range"), ("bullet", "Frequency"), ("bullet", "Currency"),
               ("blank",), ("note", "Data is available from January 2001"),
               ("blank",), ("kv", "Created by: ", CREATOR["en"])],
    },
    "5b2b60aaacad67c46039": {
        "ka": [("title", "ცხრილი - ოფიციალური საშუალოთვიური გაცვლითი კურსები"), ("blank",),
               ("kv", "პერიოდულობა: ", "ყოველდღიური"), ("blank",),
               ("head", "საერთო ფილტრები:"), ("bullet", "პერიოდის შუალედი"), ("bullet", "ვალუტა"),
               ("blank",), ("note", "მონაცემები ხელმისაწვდომია 2001 წლის იანვრიდან"),
               ("blank",), ("kv", "შემქმნელი: ", CREATOR["ka"])],
        "en": [("title", "Table - Official Average Monthly Exchange Rates"), ("blank",),
               ("kv", "Frequency: ", "Daily"), ("blank",),
               ("head", "Common Filters:"), ("bullet", "Period Range"), ("bullet", "Currency"),
               ("blank",), ("note", "Data is available from January 2001"),
               ("blank",), ("kv", "Created by: ", CREATOR["en"])],
    },
}
TOOLTIPS = {  # (key, lang)
    ("light", "ka"): "ღია რეჟიმი", ("light", "en"): "Light mode", ("dark", "ka"): "მუქი რეჟიმი", ("dark", "en"): "Dark mode",
    ("info", "ka"): "ინფორმაცია", ("info", "en"): "Information", ("lang", "ka"): "English", ("lang", "en"): "ქართული",
}
# model fields that have an English twin ("<name>_En"); \b stops Base_Date from matching Base_Date_Rate
EN_FIELDS = re.compile(r"\b(Currency_Long|Currency_Desc|Base_Date|Title_Ex_Rate|Compare_Caption|Title_Cur_to_Gel)\b")


# ---------------------------------------------------------------------------- ids
def _h(s):
    return hashlib.md5(s.encode()).hexdigest()[:20]


def vid(variant, dark_id):
    """Deterministic id of a page, visual or bookmark in a twin variant."""
    return _h(_PREFIX[variant] + dark_id)


def light_id(dark_id):
    return vid(("light", "ka"), dark_id)


def toggle_id(page_id):
    return _h("toggle:" + page_id)


def lang_id(page_id):
    return _h("lang:" + page_id)


def info_text_id(page_id):
    return _h("info-text:" + page_id)


def info_close_id(page_id):
    return _h("info-close:" + page_id)


def info_open_bm(page_id):
    return _h("info-open:" + page_id)


def info_close_bm(page_id):
    return _h("info-close-bm:" + page_id)


def page_of(mode, lang, dark):
    """Id of the page for (mode, language) belonging to dark Georgian page `dark`."""
    return dark if (mode, lang) == ("dark", "ka") else vid((mode, lang), dark)


# ---------------------------------------------------------------------------- json helpers
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


def P(props, sel=None):
    return {"properties": props, **({"selector": sel} if sel else {})}


# ---------------------------------------------------------------------------- visuals
def nav_button(name, x, link, tooltip, label=None, font=("Segoe UI Symbol", "12D")):
    """32x32 nav button (same look as reset/info). `link` is the visualLink properties (page or bookmark target)."""
    objects = {
        "icon": [P({"shapeType": text_lit("blank")}, {"id": "default"}), P({"show": lit("false")})],
        "text": [P({"show": lit("true")}),
                 P({"text": text_lit(label), "fontColor": color("#969696"), "fontSize": lit(font[1]),
                    "fontFamily": text_lit(font[0]), "horizontalAlignment": text_lit("center"),
                    "verticalAlignment": text_lit("middle"), "leftMargin": lit("0L"), "rightMargin": lit("0L"),
                    "topMargin": lit("0L"), "bottomMargin": lit("0L")}, {"id": "default"}),
                 P({"fontColor": color("#FFFFFF")}, {"id": "hover"})],
        "fill": [P({"show": lit("true")}), P({"fillColor": color("#222222"), "transparency": lit("0D")}, {"id": "default"}),
                 P({"fillColor": color("#303030"), "transparency": lit("0D")}, {"id": "hover"})],
        "outline": [P({"show": lit("true")}), P({"lineColor": color("#303030"), "weight": lit("1D")}, {"id": "default"})],
        "shape": [P({"tileShape": text_lit("rectangle"), "roundEdge": lit("4L")})],
    }
    return {
        "$schema": VC_SCHEMA, "name": name,
        "position": {"x": x, "y": 12, "z": 1032, "height": 32, "width": 32, "tabOrder": 1032},
        "visual": {
            "visualType": "actionButton",
            "objects": objects,
            # identical container to the reset/info buttons so all icons sit on the same grid
            "visualContainerObjects": {
                "background": [P({"show": lit("false")})],
                "border": [P({"show": lit("false"), "radius": lit("8D")})],
                "dropShadow": [P({"show": lit("false")})],
                "title": [P({"show": lit("false")})],
                "padding": [P({"top": lit("0D"), "bottom": lit("0D"), "left": lit("2D"), "right": lit("2D")})],
                "visualHeader": [P({"show": lit("false")})],
                "visualLink": [P({"show": lit("true"), **link, "tooltip": text_lit(tooltip), "showDefaultTooltip": lit("false")})],
            },
            "drillFilterOtherVisuals": True,
        },
    }


def page_link(page_id):
    return {"type": text_lit("PageNavigation"), "navigationSection": text_lit(page_id)}


def bookmark_link(bm_id):
    return {"type": text_lit("Bookmark"), "bookmark": text_lit(bm_id)}


def text_width(s, px):
    return sum((0.62 if GEORGIAN.match(ch) else 0.55) * px for ch in s)


def para_runs(par):
    """(list of (text, bold, italic, ink?, size pt), listType) for one INFO paragraph."""
    kind = par[0]
    if kind == "title":
        return [(par[1], True, False, True, 11)], None
    if kind == "blank":
        return [("", False, False, False, 6)], None
    if kind == "kv":
        return [(par[1], True, False, True, 9), (par[2], False, False, False, 9)], None
    if kind == "head":
        return [(par[1], True, False, True, 9)], None
    if kind == "bullet":
        return [(par[1], False, False, False, 9)], "bullet"
    if kind == "note":
        return [(par[1], False, True, False, 9)], None
    raise ValueError(kind)


def info_height(paras, width=PANEL["w"]):
    """Estimated panel height: wrapped lines per paragraph x font size x 1.6, plus vertical padding."""
    avail = width - PANEL["pad_l"] - PANEL["pad_r"]
    h = 2 * PANEL["pad_v"]
    for par in paras:
        runs, lt = para_runs(par)
        px = max(r[4] for r in runs) * 4 / 3
        w = sum(text_width(r[0], r[4] * 4 / 3) for r in runs)
        lines = max(1, math.ceil(w / (avail - (20 if lt else 0))))
        h += lines * px * 1.6
    return int(math.ceil(h / 4.0) * 4)


def info_textbox(name, dark_page, lang):
    paras = INFO[dark_page][lang]
    out = []
    for par in paras:
        runs, lt = para_runs(par)
        p = {"textRuns": [{"value": t, "textStyle": {
            "fontFamily": "Segoe UI", "fontSize": f"{size}pt", "color": "#FFFFFF" if ink else "#969696",
            **({"fontWeight": "bold"} if bold else {}), **({"fontStyle": "italic"} if ital else {})}}
            for t, bold, ital, ink, size in runs]}
        if lt:
            p["listType"] = lt
        out.append(p)
    return {
        "$schema": VC_SCHEMA, "name": name,
        "position": {"x": PANEL["x"], "y": PANEL["y"], "z": POPUP_Z, "height": info_height(paras), "width": PANEL["w"], "tabOrder": POPUP_Z},
        "visual": {
            "visualType": "textbox",
            "objects": {"general": [P({"paragraphs": out})]},
            "visualContainerObjects": {
                "title": [P({"show": lit("false")})],
                "background": [P({"show": lit("true"), "color": color("#222222"), "transparency": lit("0D")})],
                "border": [P({"show": lit("true"), "color": color("#303030"), "radius": lit("8D"), "width": lit("1D")})],
                "dropShadow": [P({"show": lit("false")})],
                "padding": [P({"top": lit(f"{PANEL['pad_v']}D"), "bottom": lit(f"{PANEL['pad_v']}D"),
                               "left": lit(f"{PANEL['pad_l']}D"), "right": lit(f"{PANEL['pad_r']}D")})],
                "visualHeader": [P({"show": lit("false")})],
            },
        },
        "isHidden": True,
    }


def info_close_button(name, bm_id, tooltip):
    v = nav_button(name, CLOSE["x"], bookmark_link(bm_id), tooltip, label="✕", font=("Segoe UI Symbol", "10D"))
    v["position"].update({"y": CLOSE["y"], "z": POPUP_Z + 1, "tabOrder": POPUP_Z + 1, "width": CLOSE["size"], "height": CLOSE["size"]})
    v["isHidden"] = True
    return v


def info_bookmark(name, display, page_id, text_id, close_id, show):
    def vc(vtype, hidden):
        return {"singleVisual": {"visualType": vtype, "objects": {}, **({"display": {"mode": "hidden"}} if hidden else {})}}
    containers = {text_id: vc("textbox", not show), close_id: vc("actionButton", not show)}
    return {
        "$schema": BM_SCHEMA, "displayName": display, "name": name,
        "options": {"targetVisualNames": list(containers), "suppressData": True},
        "explorationState": {
            "version": "1.3", "activeSection": page_id,
            "sections": {page_id: {"visualContainers": containers, "visualContainerGroups": {}}},
            "objects": {"merge": {"outspacePane": [{"properties": {"expanded": lit("false")}}]}},
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
            # lineColor/weight need the "default" selector; without it Desktop falls back to the theme's blue
            vis["objects"]["outline"] = [P({"show": lit("true")}),
                                         P({"lineColor": color(LIGHT_HAIRLINE.strip("'")), "weight": lit("1D")}, {"id": "default"})]
    return v


def is_nav_tab(v):
    vis = v.get("visual") or {}
    if vis.get("visualType") != "actionButton":
        return False
    link = (vis.get("visualContainerObjects", {}).get("visualLink") or [{}])[0].get("properties", {})
    has_text = any("text" in e.get("properties", {}) for e in vis.get("objects", {}).get("text", []))
    return link.get("type") == text_lit("PageNavigation") and has_text and v["position"]["width"] > 100


def is_info_button(v):
    vis = v.get("visual") or {}
    return vis.get("visualType") == "actionButton" and any(
        e.get("properties", {}).get("shapeType") == text_lit("information") for e in vis.get("objects", {}).get("icon", []))


# ---------------------------------------------------------------------------- English transform
def translate_core(c):
    if c in TEXT_EN:
        return TEXT_EN[c]
    m = re.fullmatch(r"([A-Z]{3}) (.+)", c)
    if m and m.group(2) in CURRENCY_EN:
        return m.group(1) + " " + CURRENCY_EN[m.group(2)]
    return CURRENCY_EN.get(c, c)


def to_english(o):
    """Translate every string leaf: static texts, currency names and the model fields that have an _En twin."""
    if isinstance(o, dict):
        return {k: to_english(v) for k, v in o.items()}
    if isinstance(o, list):
        return [to_english(v) for v in o]
    if isinstance(o, str):
        o = EN_FIELDS.sub(lambda m: m.group(1) + "_En", o)
        if GEORGIAN.search(o):
            q = len(o) > 1 and o[0] == "'" and o[-1] == "'"
            t = translate_core(o[1:-1] if q else o)
            o = "'" + t + "'" if q else t
    return o


# ---------------------------------------------------------------------------- build
def build_dark_sources():
    """Step 1: write the nav buttons, info panel and its bookmarks into the dark Georgian pages."""
    bdir = os.path.join(ROOT, "bookmarks")
    for dark in DARK_PAGES:
        vdir = os.path.join(ROOT, "pages", dark, "visuals")
        first_run = not os.path.exists(os.path.join(vdir, lang_id(dark)))
        for f in glob.glob(os.path.join(vdir, "*", "visual.json")):
            v = load(f)
            vis = v.get("visual") or {}
            changed = False
            if first_run and (is_nav_tab(v) or (vis.get("visualType") == "shape" and v["position"]["height"] == 2 and v["position"]["y"] == 54)):
                v["position"]["x"] -= 40   # make room for the language button
                changed = True
            if vis.get("visualType") == "slicer":
                vis["syncGroup"] = {"groupName": "sync_" + v["name"], "fieldChanges": True, "filterChanges": True}
                changed = True
            if is_info_button(v):
                vis["visualContainerObjects"]["visualLink"] = [P({"show": lit("true"), **bookmark_link(info_open_bm(dark)),
                                                                  "tooltip": text_lit(TOOLTIPS[("info", "ka")]), "showDefaultTooltip": lit("false")})]
                changed = True
            if changed:
                save(f, v)
        save(os.path.join(vdir, toggle_id(dark), "visual.json"),
             nav_button(toggle_id(dark), TOGGLE_X, page_link(page_of("light", "ka", dark)), TOOLTIPS[("light", "ka")], label="☀"))
        save(os.path.join(vdir, lang_id(dark), "visual.json"),
             nav_button(lang_id(dark), LANG_X, page_link(page_of("dark", "en", dark)), TOOLTIPS[("lang", "ka")], label="EN", font=("Segoe UI Semibold", "9D")))
        save(os.path.join(vdir, info_text_id(dark), "visual.json"), info_textbox(info_text_id(dark), dark, "ka"))
        save(os.path.join(vdir, info_close_id(dark), "visual.json"),
             info_close_button(info_close_id(dark), info_close_bm(dark), "✕"))
        n = DARK_PAGES.index(dark) + 1
        save(os.path.join(bdir, info_open_bm(dark) + ".bookmark.json"),
             info_bookmark(info_open_bm(dark), f"Info_Open_Page_{n}", dark, info_text_id(dark), info_close_id(dark), True))
        save(os.path.join(bdir, info_close_bm(dark) + ".bookmark.json"),
             info_bookmark(info_close_bm(dark), f"Info_Close_Page_{n}", dark, info_text_id(dark), info_close_id(dark), False))


def build_variant(dark, variant, maps, bdir):
    mode, lang = variant
    light = mode == "light"
    src = os.path.join(ROOT, "pages", dark)
    vp = vid(variant, dark)
    vmap, visuals = {}, []
    for f in glob.glob(os.path.join(src, "visuals", "*", "visual.json")):
        v = load(f)
        vmap[v["name"]] = vid(variant, v["name"])
        visuals.append(v)

    def recolor(obj):
        s = json.dumps(obj, ensure_ascii=False)
        if light:
            s = HEX.sub(lambda m: "#" + PALETTE.get(m.group(1).upper(), m.group(1)), s)
            s = s.replace('"Property": "Weekend_Font_Color"', '"Property": "Weekend_Font_Color_Light"')
        return json.loads(s)

    def retarget(obj):
        """Point page links and bookmark buttons at this variant's pages and bookmarks."""
        s = json.dumps(obj, ensure_ascii=False)
        for d, n in {**maps["pages"][variant], **maps["bookmarks"][variant]}.items():
            s = s.replace("'" + d + "'", "'" + n + "'")
        return json.loads(s)

    def prepare(obj):
        return retarget(recolor(to_english(obj) if lang == "en" else obj))

    other_mode = "dark" if light else "light"
    other_lang = "en" if lang == "ka" else "ka"
    for v in visuals:
        name = v["name"]
        if name == toggle_id(dark):
            lv = nav_button(vmap[name], TOGGLE_X, page_link(page_of(other_mode, lang, dark)), TOOLTIPS[(other_mode, lang)],
                            label=MOON if light else "☀")
            lv = recolor(lv)
        elif name == lang_id(dark):
            lv = nav_button(vmap[name], LANG_X, page_link(page_of(mode, other_lang, dark)), TOOLTIPS[("lang", lang)],
                            label="EN" if lang == "ka" else "ქა", font=("Segoe UI Semibold", "9D"))
            lv = recolor(lv)
        elif name == info_text_id(dark):
            lv = recolor(info_textbox(vmap[name], dark, lang))
        else:
            lv = prepare(v)
            lv["name"] = vmap[name]
            if lv.get("parentGroupName"):
                lv["parentGroupName"] = vmap.get(lv["parentGroupName"], lv["parentGroupName"])
            if is_info_button(v):
                lv["visual"]["visualContainerObjects"]["visualLink"][0]["properties"]["tooltip"] = text_lit(TOOLTIPS[("info", lang)])
            vis = lv.get("visual") or {}
            if lang == "en" and vis.get("visualType") == "slicer" and "Currency_Desc_En" in json.dumps(vis.get("query", {})):
                # a different field than the Georgian slicer, so it gets its own sync group
                vis["syncGroup"]["groupName"] += "_en"
        if light:
            soften(lv)
        save(os.path.join(ROOT, "pages", vp, "visuals", lv["name"], "visual.json"), lv)

    page = prepare(load(os.path.join(src, "page.json")))
    page["name"] = vp
    page["displayName"] = page["displayName"] + _SUFFIX[variant]
    page["visibility"] = "HiddenInViewMode"
    page["visualInteractions"] = [{**i, "source": vmap.get(i["source"], i["source"]), "target": vmap.get(i["target"], i["target"])}
                                  for i in page.get("visualInteractions", [])]
    save(os.path.join(ROOT, "pages", vp, "page.json"), page)

    # reset bookmark (a clone of the dark page's, with the variant's visual ids)
    b = load(os.path.join(bdir, HOME_BOOKMARK[dark] + ".bookmark.json"))
    lb = to_english(b) if lang == "en" else b
    s = json.dumps(lb, ensure_ascii=False).replace(dark, vp)
    for d, n in vmap.items():
        s = s.replace(d, n)
    if light:
        s = HEX.sub(lambda m: "#" + PALETTE.get(m.group(1).upper(), m.group(1)), s)
    lb = json.loads(s)
    lb["name"] = maps["bookmarks"][variant][HOME_BOOKMARK[dark]]
    lb["displayName"] = b.get("displayName", "Home") + _BM_SUFFIX[variant]
    save(os.path.join(bdir, lb["name"] + ".bookmark.json"), lb)

    # info bookmarks, written directly with the variant's ids
    n = DARK_PAGES.index(dark) + 1
    t, c = vmap[info_text_id(dark)], vmap[info_close_id(dark)]
    ob, cb = maps["bookmarks"][variant][info_open_bm(dark)], maps["bookmarks"][variant][info_close_bm(dark)]
    save(os.path.join(bdir, ob + ".bookmark.json"), info_bookmark(ob, f"Info_Open_Page_{n}{_BM_SUFFIX[variant]}", vp, t, c, True))
    save(os.path.join(bdir, cb + ".bookmark.json"), info_bookmark(cb, f"Info_Close_Page_{n}{_BM_SUFFIX[variant]}", vp, t, c, False))


def georgian_strings(o):
    if isinstance(o, dict):
        for v in o.values():
            yield from georgian_strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from georgian_strings(v)
    elif isinstance(o, str) and GEORGIAN.search(o):
        yield o


def georgian_leftovers(pages, bookmarks):
    """English pages may only contain the 'ქა' language label and its 'ქართული' tooltip."""
    allowed = {"ქა", "ქართული"}
    files = [f for p in pages for f in glob.glob(os.path.join(ROOT, "pages", p, "**", "*.json"), recursive=True)]
    files += [os.path.join(ROOT, "bookmarks", b + ".bookmark.json") for b in bookmarks]
    return [f"{os.path.relpath(f, ROOT)}: {s[:60]}" for f in files for s in georgian_strings(load(f)) if s.strip("'") not in allowed]


def main():
    build_dark_sources()
    bdir = os.path.join(ROOT, "bookmarks")
    dark_bms = {d: [HOME_BOOKMARK[d], info_open_bm(d), info_close_bm(d)] for d in DARK_PAGES}
    maps = {"pages": {v: {d: vid(v, d) for d in DARK_PAGES} for v in VARIANTS},
            "bookmarks": {v: {b: vid(v, b) for d in DARK_PAGES for b in dark_bms[d]} for v in VARIANTS}}
    generated_pages = [maps["pages"][v][d] for v in VARIANTS for d in DARK_PAGES]
    variant_bms = [maps["bookmarks"][v][b] for v in VARIANTS for d in DARK_PAGES for b in dark_bms[d]]
    generated_bms = [b for d in DARK_PAGES for b in dark_bms[d][1:]] + variant_bms

    # remove previous twins and their bookmarks (the dark info bookmarks were just rewritten above)
    for p in generated_pages:
        shutil.rmtree(os.path.join(ROOT, "pages", p), ignore_errors=True)
    for b in variant_bms:
        p = os.path.join(bdir, b + ".bookmark.json")
        if os.path.exists(p):
            os.remove(p)

    for dark in DARK_PAGES:
        for variant in VARIANTS:
            build_variant(dark, variant, maps, bdir)

    # register pages and bookmarks
    pj = os.path.join(ROOT, "pages", "pages.json")
    pages = load(pj)
    pages["pageOrder"] = [p for p in pages["pageOrder"] if p not in generated_pages] + generated_pages
    save(pj, pages)
    bj = os.path.join(bdir, "bookmarks.json")
    bm = load(bj)
    bm["items"] = [i for i in bm["items"] if i["name"] not in generated_bms] + [{"name": n} for n in generated_bms]
    save(bj, bm)

    en = [v for v in VARIANTS if v[1] == "en"]
    bad = georgian_leftovers([maps["pages"][v][d] for v in en for d in DARK_PAGES],
                             [maps["bookmarks"][v][b] for v in en for d in DARK_PAGES for b in dark_bms[d]])
    if bad:
        print("Georgian text left on English pages:\n  " + "\n  ".join(bad))
        sys.exit(1)
    print("twin pages:", {f"{m}-{l}": maps["pages"][(m, l)] for m, l in VARIANTS})


if __name__ == "__main__":
    main()

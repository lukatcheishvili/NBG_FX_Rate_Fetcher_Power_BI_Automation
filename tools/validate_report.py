"""Structural checks of the report definition: every JSON file parses (UTF-8, no BOM), no references to
NBG's original table names remain, and every bookmark, group, interaction and page reference resolves.

Usage:  python tools/validate_report.py   (exit code 1 on problems)
"""
import json, glob, os, re, sys
sys.stdout.reconfigure(encoding="utf-8")
REP = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "report", "Personal Portfolio - NBG Rates.Report")
D = os.path.join(REP, "definition")
problems = []
files = glob.glob(os.path.join(D, "**", "*.json"), recursive=True)
docs = {}
for f in files:
    raw = open(f, "rb").read()
    if raw.startswith(b"\xef\xbb\xbf"): problems.append(f"BOM: {f}")
    try: docs[f] = json.loads(raw.decode("utf-8"))
    except Exception as e: problems.append(f"bad JSON {f}: {e}")
alltext = {f: json.dumps(d, ensure_ascii=False) for f, d in docs.items()}
for f, t in alltext.items():
    if re.search(r"(?<![A-Za-z_])Calendar\.", t): problems.append(f"Calendar. left in {os.path.relpath(f, D)}")
    for pat in ('"RateDD"', '"CL_Cur"', '"Country_Flags"', '"_Measures"', '"Calendar"', "RateDD.", "CL_Cur.", "_Measures.", "Country_Flags.", "ResourcePackageItem", "c74257b018ab524a112e"):
        if pat in t: problems.append(f"{pat} left in {os.path.relpath(f, D)}")
# model fields used
model_fields = set()
for t in alltext.values():
    for e, p in re.findall(r'"SourceRef": \{"Entity": "([^"]+)"\}\}, "Property": "([^"]+)"', t): model_fields.add((e, p))
print("fields referenced by Entity:", sorted(model_fields))
visuals = {d["name"]: (f, d) for f, d in docs.items() if f.endswith("visual.json")}
pages = {d["name"]: d for f, d in docs.items() if f.endswith("page.json")}
bms = {d["name"]: d for f, d in docs.items() if f.endswith(".bookmark.json")}
meta = docs[os.path.join(D, "bookmarks", "bookmarks.json")]
if {i["name"] for i in meta["items"]} != set(bms): problems.append("bookmarks.json items != bookmark files")
for n, (f, v) in visuals.items():
    if v.get("parentGroupName") and v["parentGroupName"] not in visuals: problems.append(f"{n}: missing parent group")
    for b in re.findall(r'"bookmark": \{"expr": \{"Literal": \{"Value": "\'([^\']+)', alltext[f]):
        if b not in bms: problems.append(f"{n}: button points to missing bookmark {b}")
for pn, p in pages.items():
    for i in p.get("visualInteractions", []):
        for k in ("source", "target"):
            if i[k] not in visuals: problems.append(f"page {pn}: interaction to missing visual {i[k]}")
for bn, b in bms.items():
    for sec, s in b.get("explorationState", {}).get("sections", {}).items():
        if sec not in pages: problems.append(f"bookmark {bn}: unknown page {sec}")
        for vn in s.get("visualContainers", {}): 
            if vn not in visuals: problems.append(f"bookmark {bn}: unknown visual {vn}")
    for vn in b.get("options", {}).get("targetVisualNames", []):
        if vn not in visuals: problems.append(f"bookmark {bn}: unknown target {vn}")
pj = docs[os.path.join(D, "pages", "pages.json")]
if set(pj["pageOrder"]) != set(pages): problems.append("pages.json order mismatch")
# slicer defaults
for n, (f, v) in visuals.items():
    if v.get("visual", {}).get("visualType") == "slicer":
        t = json.dumps(v["visual"]["objects"].get("general", []), ensure_ascii=False)
        vals = re.findall(r'"Literal": \{"Value": "(\'[^\']*\'|[^"]*)"\}', t)
        field = re.findall(r'"Property": "([^"]+)"', json.dumps(v["visual"]["query"]))
        print("slicer", n[:8], field[:1], [x for x in vals if x not in ("false", "true", "0D")][:6])
print("pages:", {k: (p["displayName"], p.get("visibility")) for k, p in pages.items()}, "active:", pj["activePageName"])
print("visuals:", len(visuals), "bookmarks:", len(bms))
print("PROBLEMS:", problems if problems else "none")
sys.exit(1 if problems else 0)

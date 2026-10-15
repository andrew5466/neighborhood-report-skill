#!/usr/bin/env python3
"""Map Lite step 3: build the client's page, one self-contained fragment for a private Artifact. No network.

    python3 -I build.py "<client folder>"        # writes <client>/out/<slug>.html

Inlines the region base map (Neighborhood Report Tool/maps/<region>.osm.json), the client's layers, homes, points
of interest and the Leaflet CSS. Provenance stays in the data files. Refuses a page that would show internal
text, an email address or a phone number.
"""
import base64
import json
import re
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent
TOOL = KIT.parent.parent / "Neighborhood Report Tool"
BANNED = ["Brain/", "Obsidian", "Codex", "Astra", "harness", "(PDF", "tel:", "{{"]


def load_photos(root):
    # photos: data/photos.json {listing id: {"file": "photos/<id>.jpg", "credit": "Listing photo · <site>"}}
    pmeta = json.loads((root / "data/photos.json").read_text()) if (root / "data/photos.json").exists() else {}
    photos = {}
    for pid, pm in pmeta.items():
        f = root / "data" / pm["file"]
        if f.exists():
            mime = "image/png" if f.suffix == ".png" else "image/webp" if f.suffix == ".webp" else "image/jpeg"
            photos[pid] = {"src": "data:%s;base64,%s" % (mime, base64.b64encode(f.read_bytes()).decode()), "credit": pm["credit"]}
    return photos


def finish(root, cfg, data, homes, template, extra):
    """Fill the template, run the privacy scan, write out/<slug>.html."""
    page = (KIT / template).read_text(encoding="utf-8")
    esc = lambda s: s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    subs = {"TITLE": esc(cfg["title"]), "LEDE": esc(cfg["lede"].replace("{n}", NUM.get(len(homes), str(len(homes))))),
            "BYLINE": esc(cfg["byline"]), "SOURCES": esc(cfg["sources"])}
    subs.update({k: esc(v) for k, v in extra.items()})
    for k, v in subs.items():
        page = page.replace("{{%s}}" % k, v)
    page = page.replace("/*__LEAFLET_CSS__*/", (TOOL / "vendor/leaflet-1.9.4.min.css").read_text(encoding="utf-8"))
    page = page.replace("/*__DATA__*/null", json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/"))
    visible = re.sub(r"<script>.*?</script>", "", page, flags=re.S)
    text_data = json.dumps({k: v for k, v in data.items() if k not in ("layers", "base", "homes")}, ensure_ascii=False) + json.dumps([{k: v for k, v in h.items() if k not in ("photo", "r")} for h in homes], ensure_ascii=False)
    bad = [w for w in BANNED if w in visible or w in text_data]
    bad += re.findall(r"[\w.+-]+@[\w-]+\.\w+|\(?\d{3}\)?[ .-]\d{3}-\d{4}", visible + text_data)
    if bad:
        raise SystemExit("ERROR: internal or private text would reach the page: %s" % bad)
    out = root / "out" / (cfg["slug"] + ".html")
    out.parent.mkdir(exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print("Wrote %s (%.0f KB, %d homes)" % (out, out.stat().st_size / 1024, len(homes)))



def check_areas(cfg, homes):
    """Areas (the simplified bubble report): client.json "areas" = [{"name", "summary", "center": [lat, lon] (only for an
    area with no homes)}]; each listing's "area" must match one name. Area copy is scanned with the full tool's
    fair-housing rules: places only, never who lives there, never a school rating."""
    areas = cfg.get("areas") or []
    if not areas:
        return []
    import importlib.util
    spec = importlib.util.spec_from_file_location("nr_tool_build", TOOL / "build.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    errors, names = [], [a["name"] for a in areas]
    for a in areas:
        for field in ("name", "summary"):
            text = tool.PROPERTY_TYPES_RE.sub(" ", a.get(field, ""))
            hit = tool.PEOPLE_RE.search(text) or tool.SCHOOL_RATING_RE.search(text)
            if hit:
                errors.append("area %r %s says %r. Describe places, not people, and never rate schools (fair housing)." % (a["name"], field, hit.group(0)))
        if not any(h["area"] == a["name"] for h in homes) and not a.get("center"):
            errors.append("area %r has no homes and no center" % a["name"])
    for h in homes:
        if h["area"] not in names:
            errors.append("home %s has area %r, which is not in client.json areas" % (h["id"], h["area"]))
    if errors:
        raise SystemExit("ERROR:\n  " + "\n  ".join(errors))
    return [{"name": a["name"], "summary": a.get("summary", ""), "center": a.get("center")} for a in areas]


def main_anchors(root, cfg):
    """Anchors mode: the client's fixed places (school, work...) lead every card, with a route to each."""
    listings = json.loads((root / "data/listings.json").read_text())
    measures = json.loads((root / "data/measures.json").read_text())
    cards = json.loads((root / "data/cards.json").read_text())["homes"]
    base = json.loads((TOOL / cfg["basemap"]).with_suffix(".osm.json").read_text())
    exclude = set(cfg.get("exclude", []))
    routes = json.loads((root / "data/routes.json").read_text()) if (root / "data/routes.json").exists() else {}
    photos = load_photos(root)
    homes = []
    for L in listings:
        if L["id"] in exclude:
            continue
        c = cards[L["id"]]
        status = "miss" if any(f["l"] == "red" for f in c["flags"]) else "confirm" if c["flags"] else "fit"
        homes.append({
            "id": L["id"], "n": L["n"], "name": L["name"], "unit": L.get("unit", ""), "addr": L["addr"].rsplit(", FL", 1)[0],
            "area": L.get("area", ""), "kind": L.get("kind", ""), "kindLabel": L.get("kindLabel", ""), "lat": L["lat"], "lon": L["lon"], "rent": L["rent"], "status": status,
            "rentText": c["rentText"], "rentSub": c["rentSub"], "rentConfirm": c.get("rentConfirm", False),
            "prio": c.get("prio", []), "details": c["details"], "flags": c["flags"], "pros": c.get("pros", []), "cons": c.get("cons", []),
            "r": routes.get(L["id"]), "photo": photos.get(L["id"]), "to": measures[L["id"]]["to"],
        })
        # optional fields, only when the client uses them (older pages rebuild unchanged): "building" for one pin per
        # building, and each field a filter group filters on
        for k in ["building", "onehome"] + [g["field"] for g in cfg.get("filterGroups", [])]:
            if k in L:
                homes[-1][k] = L[k]
        if measures[L["id"]].get("point"):
            homes[-1]["pt"] = measures[L["id"]]["point"]
    anchors = [{k: a[k] for k in ("key", "label", "short", "letter", "lat", "lon", "pin") if k in a} | {"profile": a.get("profile", "car"), "sortLabel": a.get("sortLabel", a["short"])}
               | ({"shape": "area" if a["shape"].get("osm") == "beach" else "line"} if a.get("shape") else {})
               for a in cfg["anchors"]]
    data = {"slug": cfg["slug"], "title": cfg["title"], "homes": homes, "anchors": anchors,
            "waterLabels": cfg.get("waterLabels", []),
            "base": {k: base[k] for k in ("frame", "scale", "roadClasses", "sea", "islands", "water", "parks", "roads", "labels", "names")},
            "onehome": cfg["onehome"], "routeNote": cfg.get("routeNote", ""), "filters": cfg.get("filters", []),
            "areas": check_areas(cfg, homes)}
    layers = json.loads((root / "data/layers.json").read_text()) if (root / "data/layers.json").exists() else {}
    if layers.get("shapes"):
        data["shapes"] = layers["shapes"]
    if cfg.get("filterGroups"):
        data["filterGroups"] = check_filter_groups(cfg["filterGroups"], homes)
    if cfg.get("showLongWalks"):
        data["showLongWalks"] = True
    if cfg.get("noMover"):
        data["noMover"] = True
    if cfg.get("mapButton"):
        data["mapButton"] = True  # Kevin pattern: a card opens without moving the map; "Show on map" draws its routes
    if cfg.get("maxWalkMin"):
        data["maxWalkMin"] = int(cfg["maxWalkMin"])
    if cfg.get("notes"):
        data["notes"] = list(cfg["notes"])
    if cfg.get("sections"):
        data["sections"] = check_sections(cfg["sections"], homes)
    template = "template-anchors.html"
    if cfg.get("layout") == "buildings":
        # buildings layout: groups (sections) of buildings, each building's walks and facts once, its units underneath
        # client facts first; any building the client folder lacks comes from the shared store (db/buildings.json)
        shared = json.loads((KIT.parent / "db/buildings.json").read_text()) if (KIT.parent / "db/buildings.json").exists() else {}
        own = json.loads((root / "data/buildings.json").read_text()) if (root / "data/buildings.json").exists() else {}
        need = {h["building"] for h in homes}
        data["buildings"] = {k: own.get(k) or shared.get(k) for k in need if own.get(k) or shared.get(k)}
        missing = sorted({h["building"] for h in homes} - set(data["buildings"]))
        if missing or not cfg.get("sections"):
            raise SystemExit("ERROR: buildings layout needs data/buildings.json entries for %s and client.json sections" % (missing or "-"))
        for h in homes:
            h["spec"] = cards[h["id"]].get("spec", "")
            if cfg.get("noFlags"):
                # a market report: every option on equal footing, no red/gold judgement (Confirm tags on unverified facts stay)
                h["flags"], h["status"] = [], "info"
        template = "template-buildings.html"
    finish(root, cfg, data, homes, template, {})


def check_sections(sections, homes):
    """client.json "sections": [{"key", "title", "sub", "onehome": {"label", "url"}, "ids": [listing ids]}]. Every home
    shown must sit in exactly one section; the page lists each section with its own heading and OneHome link."""
    errors, seen = [], {}
    ids = {h["id"] for h in homes}
    for g in sections:
        for i in g.get("ids", []):
            if i in seen:
                errors.append("home %s is in sections %s and %s" % (i, seen[i], g["key"]))
            seen[i] = g["key"]
    for h in homes:
        if h["id"] not in seen:
            errors.append("home %s is in no section" % h["id"])
        else:
            h["section"] = seen[h["id"]]
    errors += ["section id %s is not a listing on the page" % i for i in seen if i not in ids]
    if errors:
        raise SystemExit("ERROR:\n  " + "\n  ".join(errors))
    return [{k: g[k] for k in ("key", "title", "sub", "onehome") if k in g} for g in sections]


def check_filter_groups(groups, homes):
    """client.json "filterGroups": [{"key", "label", "field", "options": [{"key", "label"}]} or {"key", "label", "field",
    "toggle": true}]. Every home must carry each group's field (an option group matches str(value) to the option key;
    a toggle matches value is True). Groups combine with AND, and with "filters" and "areas"."""
    errors = []
    for g in groups:
        missing = [h["id"] for h in homes if g["field"] not in h]
        if missing:
            errors.append("filter group %r: homes without %r: %s (add it to data/listings.json)" % (g["key"], g["field"], ", ".join(missing)))
        if not g.get("toggle") and not g.get("options"):
            errors.append("filter group %r needs options or toggle" % g["key"])
    if errors:
        raise SystemExit("ERROR:\n  " + "\n  ".join(errors))
    return [{k: g[k] for k in ("key", "label", "field", "options", "toggle") if k in g} for g in groups]


def main(root):
    cfg = json.loads((root / "client.json").read_text())
    if cfg.get("mode") == "anchors":
        return main_anchors(root, cfg)
    listings = json.loads((root / "data/listings.json").read_text())
    measures = json.loads((root / "data/measures.json").read_text())
    cards = json.loads((root / "data/cards.json").read_text())["homes"]
    pois = json.loads((root / "data/pois.json").read_text())
    layers = json.loads((root / "data/layers.json").read_text())
    base = json.loads((TOOL / cfg["basemap"]).with_suffix(".osm.json").read_text())
    exclude = set(cfg.get("exclude", []))
    routes = json.loads((root / "data/routes.json").read_text()) if (root / "data/routes.json").exists() else {}
    # photos: data/photos.json {listing id: {"file": "photos/<id>.jpg", "credit": "Listing photo · <site>"}}
    pmeta = json.loads((root / "data/photos.json").read_text()) if (root / "data/photos.json").exists() else {}
    photos = {}
    for pid, pm in pmeta.items():
        f = root / "data" / pm["file"]
        if f.exists():
            mime = "image/png" if f.suffix == ".png" else "image/webp" if f.suffix == ".webp" else "image/jpeg"
            photos[pid] = {"src": "data:%s;base64,%s" % (mime, base64.b64encode(f.read_bytes()).decode()), "credit": pm["credit"]}

    homes = []
    for L in listings:
        if L["id"] in exclude:
            continue
        c, m = cards[L["id"]], measures[L["id"]]
        homes.append({
            "id": L["id"], "n": L["n"], "name": L["name"], "unit": L["unit"],
            "addr": re.sub(r"\s*\(.*?\)", "", L["addr"]).rsplit(", FL", 1)[0],
            "lat": L["lat"], "lon": L["lon"], "rent": L["rent"],
            "status": "miss" if any(f["l"] == "red" for f in c["flags"]) else "confirm",
            "rentText": c["rentText"], "rentSub": c["rentSub"], "rentConfirm": c.get("rentConfirm", False),
            "beachText": c["beachText"], "privacy": c["privacy"], "details": c["details"], "flags": c["flags"],
            "pros": c["pros"], "cons": c["cons"],
            "r": routes.get(L["id"]), "photo": photos.get(L["id"]),
            "m": {k: m[k] for k in ("toBeachMi", "toBeachFt", "beachPoint", "toBeachwalkMi", "toBeachwalkFt", "beachwalkPoint",
                                    "beachwalkSegment", "beachwalkBicycle", "toBikeMi", "toBikeFt", "bikeName", "bikeKind",
                                    "pizza", "pizzaMi")},
        })
    data = {
        "slug": cfg["slug"], "title": cfg["title"],
        "homes": homes,
        # only the points of interest that are some home's nearest
        "pizza": [{"name": p["name"], "addr": p["addr"].rsplit(", FL", 1)[0].replace(", Miami Beach", ""), "lat": p["lat"], "lon": p["lon"]}
                  for p in pois if any(h["m"]["pizza"] == p["name"] for h in homes)],
        "poi": {"label": cfg["poi"]["label"], "letter": cfg["poi"]["letter"], "checked": len(pois)},
        "path": {"label": cfg["path"]["label"]},
        "waterLabels": cfg.get("waterLabels", []),
        "layers": {k: layers[k] for k in ("beachwalk", "bike", "beach")},
        "base": {k: base[k] for k in ("frame", "scale", "roadClasses", "sea", "islands", "water", "parks", "roads", "labels", "names")},
        "onehome": cfg["onehome"],
    }
    page = (KIT / "template.html").read_text(encoding="utf-8")
    esc = lambda s: s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    for k, v in {"TITLE": esc(cfg["title"]), "LEDE": esc(cfg["lede"].replace("{n}", NUM.get(len(homes), str(len(homes))))),
                 "BYLINE": esc(cfg["byline"]), "SOURCES": esc(cfg["sources"]), "PATH": esc(cfg["path"]["label"]),
                 "POI": esc(cfg["poi"]["label"])}.items():
        page = page.replace("{{%s}}" % k, v)
    page = page.replace("/*__LEAFLET_CSS__*/", (TOOL / "vendor/leaflet-1.9.4.min.css").read_text(encoding="utf-8"))
    page = page.replace("/*__DATA__*/null", json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/"))

    visible = re.sub(r"<script>.*?</script>", "", page, flags=re.S)
    text_data = json.dumps({k: v for k, v in data.items() if k not in ("layers", "base", "homes")}, ensure_ascii=False) + json.dumps([{k: v for k, v in h.items() if k not in ("photo", "r")} for h in homes], ensure_ascii=False)
    bad = [w for w in BANNED if w in visible or w in text_data]
    bad += re.findall(r"[\w.+-]+@[\w-]+\.\w+|\(?\d{3}\)?[ .-]\d{3}-\d{4}", visible + text_data)
    if bad:
        raise SystemExit("ERROR: internal or private text would reach the page: %s" % bad)
    out = root / "out" / (cfg["slug"] + ".html")
    out.parent.mkdir(exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print("Wrote %s (%.0f KB, %d homes)" % (out, out.stat().st_size / 1024, len(homes)))


NUM = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten", 11: "Eleven", 12: "Twelve"}

if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())

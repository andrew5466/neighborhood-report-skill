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
            "prio": c["prio"], "details": c["details"], "flags": c["flags"], "pros": c["pros"], "cons": c["cons"],
            "r": routes.get(L["id"]), "photo": photos.get(L["id"]), "to": measures[L["id"]]["to"],
        })
    anchors = [{k: a[k] for k in ("key", "label", "short", "letter", "lat", "lon", "pin") if k in a} | {"profile": a.get("profile", "car"), "sortLabel": a.get("sortLabel", a["short"])}
               for a in cfg["anchors"]]
    data = {"slug": cfg["slug"], "title": cfg["title"], "homes": homes, "anchors": anchors,
            "waterLabels": cfg.get("waterLabels", []),
            "base": {k: base[k] for k in ("frame", "scale", "roadClasses", "sea", "islands", "water", "parks", "roads", "labels", "names")},
            "onehome": cfg["onehome"], "routeNote": cfg.get("routeNote", ""), "filters": cfg.get("filters", [])}
    finish(root, cfg, data, homes, "template-anchors.html", {})


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

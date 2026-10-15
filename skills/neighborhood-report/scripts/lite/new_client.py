#!/usr/bin/env python3
"""Map Lite: start a client folder from MLS numbers, groups and place names. No network (run fetch_listings.py --mls
and ingest_matrix.py first so db/listings has the homes).

    python3 -I new_client.py "<client folder>" --title "Crash Pad Sobe" \
        --groups "South of Fifth · 2 bedrooms=A12087639,A12067140; Carillon · 2 bedrooms=A11996462,A11985233" \
        --places beach-miami-beach,lincoln-road,mila,catch --range 5000 6500 [--basemap maps/miami-beach.json]

Writes client.json (anchors mode, buildings layout, market report: noFlags, noMover, maxWalkMin 20; anchors from
db/places.json; a Bedrooms filter; one section per group) and data/listings.json (id, building key, name, unit,
address, beds, baths, sq ft, rent, MLS, coordinates, each from Matrix or the listing page). Copies the region's
OpenStreetMap layers (from a client on the same base map) when places include a street or the beach. Refuses to overwrite
an existing client.json. Edit the copy (lede, notes, sources, OneHome links) afterwards; nothing here is guessed.
"""
import json
import re
import shutil
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
DB = KIT / "db"
BUILDINGS = json.loads((DB / "buildings.json").read_text()) if (DB / "buildings.json").exists() else {}


def join_and(xs):
    return (xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]) if xs else ""


def slug(s):
    s = re.sub(r"(?i)\b(the|condo(minium)?|residences?|c|co|cond|at)\b", " ", s or "")
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:24] or "building"


def building_of(b, m, addr):
    """The db/buildings.json building whose street address matches the listing's (house number + street word), else a
    new key from the listing site's building name or the street address."""
    url_addr = re.search(r"/FL/[^/]+/([^/]+)/rental/", b.get("source", ""))
    street = (url_addr.group(1).replace("-", " ") if url_addr else addr).lower()
    mnum = re.match(r"\s*(\d+)\s+(\w+)", street)
    for k, v in BUILDINGS.items():
        dn = re.match(r"\s*(\d+)\s+(\w+)", (v.get("addr") or "").lower()) if isinstance(v, dict) else None
        if mnum and dn and dn.groups() == mnum.groups():
            return k, v.get("name", k)
    name = b.get("building") or (m.get("subdivision") or "").title()
    if not name or re.match(r"\d", name):
        name = " ".join(w.capitalize() for w in (mnum.group(0) if mnum else street).split()) or "Building"
    return slug(name), name


def arg(argv, name, n=1):
    if name not in argv:
        return None
    i = argv.index(name)
    return argv[i + 1] if n == 1 else argv[i + 1:i + 1 + n]


def main(argv):
    root = Path(argv[0]).resolve()
    if (root / "client.json").exists():
        raise SystemExit("ERROR: %s already has client.json; edit it instead" % root)
    title = arg(argv, "--title") or root.name
    groups = [g.split("=", 1) for g in (arg(argv, "--groups") or "").split(";") if "=" in g]
    places = [p.strip() for p in (arg(argv, "--places") or "").split(",") if p.strip()]
    lo, hi = (arg(argv, "--range", 2) or [None, None])
    basemap = arg(argv, "--basemap") or "maps/miami-beach.json"
    known = json.loads((DB / "places.json").read_text())
    anchors = []
    for i, k in enumerate(places):
        if k not in known:
            raise SystemExit("ERROR: place %s is not in db/places.json; add it (address checked on two sources) first" % k)
        p = known[k]
        bare = p["label"].replace("the ", "")
        short = p.get("short") or (bare[:1].upper() + bare[1:] if len(bare) <= 10 else bare.split()[0])
        a = {"key": k.split("-")[0], "label": p["label"], "short": short, "sortLabel": short, "letter": bare[:1].upper(), "profile": "foot"}
        a.update({"shape": p["shape"]} if p.get("shape") else {"lat": p["lat"], "lon": p["lon"], "addr": p["addr"]})
        anchors.append(a)
    listings, sections, n = [], [], 0
    for gi, (gtitle, mlss) in enumerate(groups):
        ids = []
        for mls in [m.strip() for m in mlss.split(",") if m.strip()]:
            rec_p = DB / "listings" / (mls + ".json")
            if not rec_p.exists():
                raise SystemExit("ERROR: %s not in db/listings; run fetch_listings.py --mls %s and the Matrix grid first" % (mls, mls))
            rec = json.loads(rec_p.read_text())
            m, b = rec.get("matrix", {}), rec.get("bex", {})
            addr = m.get("address") or b.get("address") or ""
            legal = (b.get("features") or {}).get("Legal Description", "")
            unit = (re.search(r"(?:Unit\s*#?|#)\s*([\w-]+)", addr) or re.search(r"(?i)\bUnit\s+([\w-]+)", legal)
                    or re.search(r"^\d+\s+\D+?\s(\w{1,5}),", addr) or [None, ""])[1]
            bkey, bname = building_of(b, m, addr)
            n += 1
            hid = "%s-%s" % (bkey, unit or n)
            listings.append({"id": hid, "n": n, "building": bkey, "name": bname, "unit": unit, "addr": addr,
                             "beds": int(m.get("beds") or b.get("beds") or 0) or None, "baths": b.get("baths"),
                             "sqft": m.get("sqft") or b.get("sqft"), "rent": m.get("listPrice") or b.get("price"), "mls": mls,
                             "lat": b.get("lat"), "lon": b.get("lon"),
                             "sources": ["db/listings/%s.json (Matrix grid %s, listing page %s)" % (mls, m.get("seen", "-"), b.get("seen", "-"))]})
            ids.append(hid)
        sections.append({"key": "g%d" % (gi + 1), "title": gtitle.strip(), "ids": ids})
    for L in listings:  # a unit page without coordinates takes its building's, from another unit there
        if L["lat"] is None:
            sib = next((x for x in listings if x["building"] == L["building"] and x["lat"] is not None), None)
            if sib:
                L["lat"], L["lon"] = sib["lat"], sib["lon"]
                L["sources"].append("coordinates from %s, same building" % sib["id"])
    missing = [L["id"] for L in listings if L["lat"] is None]
    cfg = {"_about": "Map Lite config for %s, started by new_client.py. Edit lede, notes, sources and OneHome links." % title,
           "mode": "anchors", "layout": "buildings", "noFlags": True, "noMover": True, "maxWalkMin": 20,
           "slug": slug(title) or root.name.lower(), "title": title,
           "lede": "{n} units in %d buildings. Each shows how far it is to %s." % (len({L["building"] for L in listings}),
                                                                                 join_and([a["label"] for a in anchors]) or "the places that matter to you"),
           "byline": "Prepared by Andrew Garcia · AMG Group at PMG Residential", "notes": [],
           "sources": "MLS and listing pages. Streets and beach: © OpenStreetMap contributors. Walking times: OpenStreetMap routing estimates from each building's address.",
           "basemap": basemap, "routeNote": "Walking times are OpenStreetMap routing estimates from each building's address.",
           "anchors": anchors,
           "filterGroups": [{"key": "beds", "label": "Bedrooms", "field": "beds", "options": [{"key": "all", "label": "All"}] +
                             [{"key": str(x), "label": "%d bed%s" % (x, "" if x == 1 else "s")} for x in sorted({L["beds"] for L in listings if L["beds"]})]}],
           "sections": sections, "waterLabels": [], "onehome": []}
    if lo:
        cfg["range"] = [int(lo), int(hi)]
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "client.json").write_text(json.dumps(cfg, indent=1, ensure_ascii=False), encoding="utf-8")
    (root / "data/listings.json").write_text(json.dumps(listings, indent=1, ensure_ascii=False), encoding="utf-8")
    region = Path(basemap).stem
    # street and beach shapes come from the OpenStreetMap layers of any client already built on the same base map
    if any(a.get("shape") for a in anchors):
        for other in sorted(KIT.parent.glob("*/client.json")):
            raw = other.parent / "data/osm-raw.json"
            if other.parent != root and raw.exists() and json.loads(other.read_text()).get("basemap") == basemap:
                shutil.copyfile(raw, root / "data/osm-raw.json")
                print("OpenStreetMap layers copied from %s" % other.parent.name)
                break
        else:
            print("NO OpenStreetMap layers for %s yet: run fetch_osm.py on this folder" % region)
    for L in listings:
        print("%-24s %-10s %-26.26s %s bd $%s" % (L["id"], L["mls"], L["name"], L["beds"], L["rent"]))
    print("client.json + data/listings.json written; %d homes, %d buildings, %d anchors%s" % (
        len(listings), len({L["building"] for L in listings}), len(anchors),
        ("; NO coordinates for " + ", ".join(missing)) if missing else ""))


if __name__ == "__main__":
    main(sys.argv[1:])

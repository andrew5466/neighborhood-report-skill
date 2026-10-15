#!/usr/bin/env python3
"""Map Lite step 2b: walking and biking routes for each home (network; main session, Andrew's OK).

    python3 -I fetch_routes.py "<client folder>"      # after process.py

For each building: a walking route to its nearest sand point and a biking route to its nearest point on the named
path (both from data/measures.json), from the OpenStreetMap routing service (routing.openstreetmap.de, OSRM foot
and bike profiles), 1 request/second, one pair per address. Writes data/routes.json:
{listing id: {"walk": {"min", "mi", "p"}, "bike": {...}}}, "p" in the base map's integer encoding.
Route times are the service's estimates for an average walker or rider. Map data © OpenStreetMap contributors.
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

UA = "AMG-map-lite/1.0 (andrew2000garcia@gmail.com)"
BASE = "https://routing.openstreetmap.de/routed-%s/route/v1/driving/%f,%f;%f,%f?overview=full&geometries=geojson"
SCALE = 1e5


def encode(pts):
    out, px, py = [], 0, 0
    for i, (la, lo) in enumerate(pts):
        x, y = round(la * SCALE), round(lo * SCALE)
        out += [x, y] if i == 0 else [x - px, y - py]
        px, py = x, y
    return out


def route(profile, a, b):
    req = urllib.request.Request(BASE % (profile, a[1], a[0], b[1], b[0]), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        res = json.loads(r.read().decode("utf-8"))
    if res.get("code") != "Ok" or not res.get("routes"):
        raise RuntimeError("%s route failed: %s" % (profile, res.get("code")))
    rt = res["routes"][0]
    pts = [a] + [(c[1], c[0]) for c in rt["geometry"]["coordinates"]] + [b]
    return {"min": max(1, round(rt["duration"] / 60)), "mi": round(rt["distance"] / 1609.344, 2), "p": encode(pts)}


def main_anchors(root, cfg, listings):
    """Anchors mode: one route per home per anchor, with the anchor's profile ("car", "bike" or "foot").
    Writes {listing id: {anchor key: {"min", "mi", "p", "profile"}}}. Car times are free-flow estimates (no traffic)."""
    exclude = set(cfg.get("exclude", []))
    # a shape anchor (a line such as Lincoln Road, or the beach) routes to the nearest point process.py stored per home
    measures = json.loads((root / "data/measures.json").read_text()) if any(a.get("shape") for a in cfg["anchors"]) else {}
    cache, out = {}, {}
    for L in listings:
        if L["id"] in exclude:
            continue
        home = (L["lat"], L["lon"])
        out[L["id"]] = {}
        for a in cfg["anchors"]:
            prof = a.get("profile", "car")
            key = "%f,%f,%s,%s" % (home[0], home[1], a["key"], prof)
            if key not in cache:
                dest = tuple(measures[L["id"]]["point"][a["key"]]) if a.get("shape") else (a["lat"], a["lon"])
                cache[key] = dict(route(prof, home, dest), profile=prof)
                time.sleep(1.1)
            out[L["id"]][a["key"]] = cache[key]
        print("%-34s %s" % (L["name"] + " " + L.get("unit", ""), " | ".join(
            "%s %2d min %s (%.2f mi)" % (a["short"], out[L["id"]][a["key"]]["min"], a.get("profile", "car"), out[L["id"]][a["key"]]["mi"]) for a in cfg["anchors"])))
    (root / "data/routes.json").write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")


def main(root):
    cfg = json.loads((root / "client.json").read_text())
    if cfg.get("mode") == "anchors":
        return main_anchors(root, cfg, json.loads((root / "data/listings.json").read_text()))
    listings = json.loads((root / "data/listings.json").read_text())
    measures = json.loads((root / "data/measures.json").read_text())
    exclude = set(cfg.get("exclude", []))
    cache, out = {}, {}
    for L in listings:
        if L["id"] in exclude:
            continue
        m, home = measures[L["id"]], (L["lat"], L["lon"])
        key = "%f,%f" % home
        if key not in cache:
            walk = route("foot", home, tuple(m["beachPoint"]))
            time.sleep(1.1)
            bike = route("bike", home, tuple(m["beachwalkPoint"]))
            time.sleep(1.1)
            cache[key] = {"walk": walk, "bike": bike}
        out[L["id"]] = cache[key]
        r = out[L["id"]]
        print("%-30s walk to sand %2d min (%.2f mi) | bike to %s %2d min (%.2f mi)" % (
            L["name"] + " " + L["unit"], r["walk"]["min"], r["walk"]["mi"], cfg["path"]["label"], r["bike"]["min"], r["bike"]["mi"]))
    (root / "data/routes.json").write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())

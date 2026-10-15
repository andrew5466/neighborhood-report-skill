#!/usr/bin/env python3
"""Map Lite step 2: the page's layers and every home's distances. No network.

    python3 -I process.py "<client folder>"

Reads client.json (homePlace, path.nameMatch, poi.names, beachMinLat), data/geocode.json, data/osm-raw.json
and data/listings.json. Writes data/layers.json (named path, bike lanes, beach sand; integer 1e-5 degree arrays,
first point absolute then deltas, the same encoding as the Neighborhood Report Tool's base map), data/pois.json
and data/measures.json. Distances are straight-line (haversine to the nearest point on a segment), never routes,
measured from each building's address point. Prints one line per home to compare with the shortlist.
"""
import json
import math
import sys
from pathlib import Path

SCALE = 1e5


def encode(pts):
    out, px, py = [], 0, 0
    for i, (la, lo) in enumerate(pts):
        x, y = round(la * SCALE), round(lo * SCALE)
        out += [x, y] if i == 0 else [x - px, y - py]
        px, py = x, y
    return out


def seg_nearest(p, a, b):
    """Nearest point to p on segment a-b, using a local flat projection around p."""
    k = 111320 * math.cos(math.radians(p[0]))  # metres per degree of longitude; 110540 per degree of latitude
    px, py, ax, ay, bx, by = p[1] * k, p[0] * 110540, a[1] * k, a[0] * 110540, b[1] * k, b[0] * 110540
    dx, dy = bx - ax, by - ay
    t = 0 if dx == dy == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))


def hav_m(a, b):
    r = math.pi / 180
    h = math.sin((b[0] - a[0]) * r / 2) ** 2 + math.cos(a[0] * r) * math.cos(b[0] * r) * math.sin((b[1] - a[1]) * r / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def nearest(p, lines):
    best = (1e18, None, None)
    for line in lines:
        for a, b in zip(line["pts"], line["pts"][1:]):
            q = seg_nearest(p, a, b)
            d = hav_m(p, q)
            if d < best[0]:
                best = (d, q, line)
    return best


def shape_lines(a, raw):
    """A shape anchor's geometry from data/osm-raw.json (fetch_osm.py):
    {"shape": {"osmName": "Lincoln Road"}} = every path/street way named exactly that (a line);
    {"shape": {"osm": "beach", "minLat": 25.763}} = the closed natural=beach polygons (an area; its outline is measured)."""
    sh, lines = a["shape"], []
    for e in raw["elements"]:
        if e["type"] != "way" or not e.get("geometry"):
            continue
        t = e.get("tags", {})
        pts = [(g["lat"], g["lon"]) for g in e["geometry"]]
        if sh.get("osm") == "beach":
            if t.get("natural") == "beach" and pts[0] == pts[-1] and min(p[0] for p in pts) >= sh.get("minLat", -90):
                lines.append({"pts": pts})
        elif sh.get("osmName") and t.get("name") == sh["osmName"]:
            lines.append({"pts": pts})
    if not lines:
        raise SystemExit("ERROR: anchor %s: no OpenStreetMap ways for %s in data/osm-raw.json (run fetch_osm.py with a bbox that covers it)"
                         % (a["key"], json.dumps(sh)))
    return lines


def main_anchors(root, cfg):
    """Anchors mode (client.json "mode": "anchors"). Each listing in data/listings.json carries its own lat/lon (with a
    source). A point anchor carries lat/lon in client.json; a shape anchor ("shape", see shape_lines) is a line or an area
    from data/osm-raw.json, measured to its nearest point, which is stored per home so fetch_routes.py can route there.
    Writes data/measures.json (straight-line miles to every anchor, plus "point" for shape anchors) and data/layers.json
    ("shapes": the encoded geometry per shape anchor, for the page)."""
    listings = json.loads((root / "data/listings.json").read_text())
    anchors = cfg["anchors"]
    shapes, raw = {}, None
    for a in anchors:
        if a.get("shape"):
            if raw is None:
                raw = json.loads((root / "data/osm-raw.json").read_text())
            shapes[a["key"]] = shape_lines(a, raw)
        elif not isinstance(a.get("lat"), (int, float)) or not isinstance(a.get("lon"), (int, float)):
            raise SystemExit("ERROR: anchor %s has no lat/lon in client.json" % a.get("key"))
    measures = {}
    for L in listings:
        if not isinstance(L.get("lat"), (int, float)) or not isinstance(L.get("lon"), (int, float)):
            raise SystemExit("ERROR: listing %s has no lat/lon in data/listings.json" % L.get("id"))
        p = (L["lat"], L["lon"])
        to, point = {}, {}
        for a in anchors:
            if a["key"] in shapes:
                d, q, _ = nearest(p, shapes[a["key"]])
                to[a["key"]], point[a["key"]] = round(d / 1609.344, 2), [round(q[0], 6), round(q[1], 6)]
            else:
                to[a["key"]] = round(hav_m(p, (a["lat"], a["lon"])) / 1609.344, 2)
        measures[L["id"]] = {"to": to, "basis": "straight-line from each address point"}
        if point:
            measures[L["id"]]["point"] = point
    (root / "data/measures.json").write_text(json.dumps(measures, indent=1), encoding="utf-8")
    layers = {"source": "none (anchors mode)"} if not shapes else {
        "source": "© OpenStreetMap contributors (ODbL)", "scale": SCALE,
        "shapes": {k: {"kind": "area" if next(a for a in anchors if a["key"] == k)["shape"].get("osm") == "beach" else "line",
                       "p": [encode(l["pts"]) for l in v]} for k, v in shapes.items()}}
    (root / "data/layers.json").write_text(json.dumps(layers, separators=(",", ":")), encoding="utf-8")
    (root / "data/pois.json").write_text("[]", encoding="utf-8")
    for L in listings:
        m, pt = measures[L["id"]]["to"], measures[L["id"]].get("point", {})
        print("%-34s %s" % (L["name"] + " " + L.get("unit", ""), " | ".join(
            "%s %.2f mi%s" % (a["short"], m[a["key"]], " @%.5f,%.5f" % tuple(pt[a["key"]]) if a["key"] in pt else "") for a in anchors)))


def main(root):
    cfg = json.loads((root / "client.json").read_text())
    if cfg.get("mode") == "anchors":
        return main_anchors(root, cfg)
    raw = json.loads((root / "data/osm-raw.json").read_text())
    geo = json.loads((root / "data/geocode.json").read_text())
    listings = json.loads((root / "data/listings.json").read_text())
    names = cfg["path"]["nameMatch"]
    min_lat = cfg.get("beachMinLat", -90)

    walk, bike, beach = [], [], []
    for e in raw["elements"]:
        if e["type"] != "way" or not e.get("geometry"):
            continue
        t, name = e.get("tags", {}), e.get("tags", {}).get("name", "")
        pts = [(g["lat"], g["lon"]) for g in e["geometry"]]
        if t.get("natural") == "beach":
            if pts[0] == pts[-1] and min(p[0] for p in pts) >= min_lat:
                beach.append({"pts": pts})
        elif t.get("highway") in ("footway", "path", "cycleway", "pedestrian") and any(k in name for k in names):
            walk.append({"pts": pts, "name": name, "bicycle": t.get("bicycle"), "surface": t.get("surface")})
        else:
            lanes = [t.get(k, "") for k in ("cycleway", "cycleway:right", "cycleway:left", "cycleway:both")]
            if t.get("highway") == "cycleway" or t.get("bicycle") == "designated" or any(v in ("lane", "track", "shared_lane", "share_busway") for v in lanes):
                kind = "bike path" if t.get("highway") in ("cycleway", "path", "footway", "pedestrian") else \
                    ("bike lane" if any(v in ("lane", "track") for v in lanes) else "shared lane")
                bike.append({"pts": pts, "name": name or "unnamed", "kind": kind})
    if not walk or not beach:
        raise SystemExit("ERROR: no %s ways or no beach polygons. Check path.nameMatch and bbox in client.json." % cfg["path"]["label"])

    place = {k: (v["hits"][0]["lat"], v["hits"][0]["lon"]) for k, v in geo.items() if v["hits"]}
    pois = [{"name": n, "addr": cfg["places"][n], "lat": place[n][0], "lon": place[n][1],
             "source": "client.json places; coordinates from OpenStreetMap Nominatim, " + raw.get("_fetched", "")} for n in cfg["poi"]["names"]]
    (root / "data/pois.json").write_text(json.dumps(pois, indent=1), encoding="utf-8")

    measures = {}
    for L in listings:
        key = cfg["homePlace"][L["id"]]
        p = place[key]
        L["lat"], L["lon"] = p
        L["geocodeNote"] = "OpenStreetMap Nominatim %s: %s" % (raw.get("_fetched", ""), geo[key]["hits"][0]["display"])
        db, qb, _ = nearest(p, beach)
        dw, qw, lw = nearest(p, walk)
        dk, _, lk = nearest(p, bike)
        pz = min(pois, key=lambda z: hav_m(p, (z["lat"], z["lon"])))
        measures[L["id"]] = {
            "toBeachMi": round(db / 1609.344, 2), "toBeachFt": round(db * 3.28084), "beachPoint": [round(qb[0], 6), round(qb[1], 6)],
            "toBeachwalkMi": round(dw / 1609.344, 2), "toBeachwalkFt": round(dw * 3.28084), "beachwalkPoint": [round(qw[0], 6), round(qw[1], 6)],
            "beachwalkSegment": lw["name"], "beachwalkSurface": lw["surface"], "beachwalkBicycle": lw["bicycle"],
            "toBikeMi": round(dk / 1609.344, 2), "toBikeFt": round(dk * 3.28084), "bikeName": lk["name"], "bikeKind": lk["kind"],
            "pizza": pz["name"], "pizzaMi": round(hav_m(p, (pz["lat"], pz["lon"])) / 1609.344, 2),
            "basis": "straight-line from OpenStreetMap data, " + raw.get("_fetched", ""),
        }
    (root / "data/listings.json").write_text(json.dumps(listings, indent=1, ensure_ascii=False), encoding="utf-8")
    (root / "data/measures.json").write_text(json.dumps(measures, indent=1), encoding="utf-8")
    layers = {"source": "© OpenStreetMap contributors (ODbL)", "fetched": raw.get("_fetched"), "scale": SCALE,
              "beachwalk": [{"n": w["name"], "s": w["surface"], "b": w["bicycle"], "p": encode(w["pts"])} for w in walk],
              "bike": [{"n": b["name"], "k": b["kind"], "p": encode(b["pts"])} for b in bike],
              "beach": [encode(b["pts"]) for b in beach]}
    (root / "data/layers.json").write_text(json.dumps(layers, separators=(",", ":")), encoding="utf-8")
    print("%s ways %d, bike ways %d, beach polygons %d" % (cfg["path"]["label"], len(walk), len(bike), len(beach)))
    for L in listings:
        m = measures[L["id"]]
        print("%-30s sand %5d ft | %s %5d ft (%s) | bike %s %.2f mi | %s %.2f mi | shortlist: %s" % (
            L["name"] + " " + L["unit"], m["toBeachFt"], cfg["path"]["label"], m["toBeachwalkFt"], m["beachwalkSegment"],
            m["bikeName"], m["toBikeMi"], m["pizza"], m["pizzaMi"], L.get("beachPdf", "")))


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())

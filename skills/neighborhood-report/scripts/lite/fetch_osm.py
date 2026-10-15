#!/usr/bin/env python3
"""Map Lite step 1: one OpenStreetMap pull for a client (needs Andrew's OK; run from the MAIN session,
helper agents cannot get the network prompt).

    python3 -I fetch_osm.py "<client folder>"

Reads <client>/client.json (places, bbox). Geocodes each place with Nominatim (1 request/second) and makes
one Overpass query for paths/footways/cycleways, roads with bike lanes, beach sand and coastline.
Writes <client>/data/geocode.json and <client>/data/osm-raw.json. Map data © OpenStreetMap contributors, ODbL.
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

UA = "AMG-map-lite/1.0 (andrew2000garcia@gmail.com)"


def get(url, data=None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode("utf-8"))


def geocode(places):
    out = {}
    for key, q in places.items():
        url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({"format": "jsonv2", "q": q, "limit": 3})
        hits = get(url)
        out[key] = {"query": q, "hits": [{"lat": float(h["lat"]), "lon": float(h["lon"]),
                                          "type": h.get("type"), "display": h.get("display_name")} for h in hits]}
        print("%-18s -> %s" % (key, hits[0]["display_name"] if hits else "NOT FOUND"))
        time.sleep(1.1)
    return out


def overpass(bbox):
    bb = "%f,%f,%f,%f" % tuple(bbox)
    q = ('[out:json][timeout:150];('
         'way["highway"~"^(footway|path|cycleway|pedestrian|bridleway)$"](%(b)s);'
         'way["cycleway"~"lane|track|shared_lane|share_busway"](%(b)s);'
         'way["cycleway:right"~"lane|track|shared_lane"](%(b)s);'
         'way["cycleway:left"~"lane|track|shared_lane"](%(b)s);'
         'way["cycleway:both"~"lane|track|shared_lane"](%(b)s);'
         'way["bicycle"="designated"](%(b)s);'
         'way["natural"="beach"](%(b)s);'
         'way["natural"="coastline"](%(b)s);'
         ');out geom;') % {"b": bb}
    data = urllib.parse.urlencode({"data": q}).encode()
    for url in ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"):
        try:
            res = get(url, data)
            res["_endpoint"], res["_query"] = url, q
            return res
        except Exception as ex:  # one fallback endpoint, then stop
            print("Overpass failed at", url, ex)
    raise SystemExit("Overpass unavailable")


if __name__ == "__main__":
    root = Path(sys.argv[1]).resolve()
    cfg = json.loads((root / "client.json").read_text())
    (root / "data").mkdir(exist_ok=True)
    g = geocode(cfg["places"])
    (root / "data/geocode.json").write_text(json.dumps(g, indent=1), encoding="utf-8")
    missing = [k for k, v in g.items() if not v["hits"]]
    raw = overpass(cfg["bbox"])
    raw["_fetched"] = time.strftime("%Y-%m-%d")
    (root / "data/osm-raw.json").write_text(json.dumps(raw), encoding="utf-8")
    print("Overpass elements:", len(raw.get("elements", [])))
    if missing:
        raise SystemExit("NOT FOUND: %s. Fix the address in client.json and rerun." % ", ".join(missing))

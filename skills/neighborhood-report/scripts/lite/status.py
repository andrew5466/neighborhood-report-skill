#!/usr/bin/env python3
"""Map Lite data retrieval: one screen on where a client folder stands. No network. Read this, not the data files.

    python3 -I status.py "<client folder>"

One line per home (MLS status/price/period from the Matrix grid, Bex facts, photo, routes, Confirm count) and a list
of what is missing or stale, with the command that fixes it. Facts older than 7 days are flagged for a recheck.
"""
import datetime
import json
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
DB = KIT / "db"


def load(p, default):
    return json.loads(p.read_text()) if p.exists() else default


def age(d):
    try:
        return (datetime.date.today() - datetime.date.fromisoformat(d)).days
    except (TypeError, ValueError):
        return None


def main(root):
    cfg = load(root / "client.json", {})
    L = load(root / "data/listings.json", [])
    cards = load(root / "data/cards.json", {}).get("homes", {})
    routes = load(root / "data/routes.json", {})
    photos = load(root / "data/photos.json", {})
    blds = load(root / "data/buildings.json", {})
    shared_b = load(DB / "buildings.json", {})
    excl = set(cfg.get("exclude", []))
    homes = [x for x in L if x["id"] not in excl]
    print("%s · %s%s · %d homes in %d buildings · %d anchors" % (
        cfg.get("title", root.name), cfg.get("mode", "beach"), " / " + cfg["layout"] if cfg.get("layout") else "",
        len(homes), len({x.get("building", x["id"]) for x in homes}), len(cfg.get("anchors", []))))
    todo = []
    print("%-20s %-10s %-8s %-7s %-6s %-6s %-5s %-6s %s" % ("home", "MLS", "status", "price", "per", "bex", "photo", "routes", "confirm"))
    for x in homes:
        rec = load(DB / "listings" / ((x.get("mls") or "-") + ".json"), {})
        m, b = rec.get("matrix", {}), rec.get("bex", {})
        conf = sum(1 for d in cards.get(x["id"], {}).get("details", []) if d.get("c"))
        print("%-20s %-10s %-8s %-7s %-6s %-6s %-5s %-6s %s" % (
            x["id"], x.get("mls") or "-", m.get("status", "?"), m.get("listPrice", "?"), m.get("per", "?"),
            ("%dd" % age(b["seen"])) if b.get("seen") else "-", "y" if x["id"] in photos else "-",
            "y" if x["id"] in routes else "-", conf))
        if m and m.get("listPrice") and m["listPrice"] != x.get("rent"):
            todo.append("%s: Matrix list price $%s vs page $%s; check (a rented unit shows its listed, not leased, price)" % (x["id"], m["listPrice"], x.get("rent")))
        if m.get("status") and m["status"] != "active":
            todo.append("%s: Matrix status %s" % (x["id"], m["status"]))
        if m.get("per") == "year":
            todo.append("%s: Matrix rent period is 'Year'; keep a Confirm on the card" % x["id"])
        if not m:
            todo.append("%s: no Matrix row; run matrix_grid.js + ingest_matrix.py" % x["id"])
        elif (age(m.get("seen")) or 0) > 7:
            todo.append("%s: Matrix data %d days old; rerun matrix_grid.js" % (x["id"], age(m["seen"])))
        if not b:
            todo.append("%s: no listing-page facts; run fetch_listings.py" % x["id"])
        if x["id"] not in photos:
            todo.append("%s: no photo; fetch_photos.py (or none exists online)" % x["id"])
        if cfg.get("anchors") and x["id"] not in routes:
            todo.append("%s: no routes; run fetch_routes.py" % x["id"])
        bk = x.get("building")
        if cfg.get("layout") == "buildings" and bk and bk not in blds and bk not in shared_b:
            todo.append("%s: building '%s' has no facts in data/buildings.json or db/buildings.json" % (x["id"], bk))
    places = load(DB / "places.json", {})
    for a in cfg.get("anchors", []):
        if not a.get("shape") and (a.get("lat") is None) and a["key"] not in places:
            todo.append("anchor %s: no coordinates (add to client.json or db/places.json)" % a["key"])
    print()
    print("\n".join("- " + t for t in todo) if todo else "Nothing missing.")


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())

#!/usr/bin/env python3
"""Map Lite data retrieval: draft every card from the shared listing store, so nobody hand-types facts. No network.

    python3 -I draft_cards.py "<client folder>" [--range 5000 6500] [--write]

Reads data/listings.json (ids, MLS, building) and <kit>/db/listings/<MLS>.json (the "matrix" grid row and the "bex"
listing page). Builds, per home: spec ("2 bed / 2 bath · 1,035 sq ft"), rentText, rentSub (where the rent sits against
the client's range), and details: Status, Lease (Matrix style code + the listing's own lease words), Rent period
(Confirm when Matrix says "Year"), Furnished, Floor (legal description), View, Available (listing words), Year built, MLS.
Matrix wins over the listing page; anything neither shows is left out (never guessed).
Without --write it prints one line per home and writes data/cards-draft.json. With --write it merges into
data/cards.json: drafted fields replace the same fields, and hand-written details with other labels (Split 2-bed,
Move-in, Note, building facts...) are kept.
"""
import json
import re
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent


def money(n):
    return "$" + format(int(n), ",")


def draft(L, rec, lo, hi):
    m, b = rec.get("matrix", {}), rec.get("bex", {})
    beds = m.get("beds") or b.get("beds")
    fb, hb = m.get("fullBaths"), m.get("halfBaths")
    baths = (str(fb) + (".5" if hb and str(hb) != "0" else "")) if fb else (b.get("baths") if b.get("baths") is not None else "?")
    sqft = m.get("sqft") or b.get("sqft")
    spec = "%s bed / %s bath%s" % (beds or "?", baths, (" · %s sq ft" % format(int(sqft), ",")) if sqft else "")
    rent = m.get("listPrice") or b.get("price") or L.get("rent")
    sub = ""
    if rent and lo and hi:
        sub = "Within the range." if lo <= rent <= hi else ("Above the %s-%s range; shown for market reference." % (money(lo), money(hi))
                                                          if rent > hi else "Below the range.")
    det = []
    if m.get("status") and m["status"] != "active":
        det.append({"k": "Status", "v": "%s in MLS (%s)" % (m["status"].capitalize(), m.get("seen", ""))})
        sub = "%s; shown for market reference." % m["status"].capitalize()
    hints = " ".join(b.get("leaseHints", []))
    lease_words = [s for s in b.get("leaseHints", []) if re.search(r"(?i)\b(lease|annual|short[- ]term|seasonal|minimum)\b", s)]
    if m.get("leaseKind") and m["leaseKind"] != "unknown":
        v = {"seasonal": "Listed as seasonal", "annual": "Listed as annual", "off-season": "Listed as off-season"}[m["leaseKind"]]
        if lease_words:
            v += "; the listing says: \"%s\"" % lease_words[0].rstrip(".")
        det.append({"k": "Lease", "v": v})
    elif lease_words:
        det.append({"k": "Lease", "v": "The listing says: \"%s\"" % lease_words[0].rstrip(".")})
    else:
        det.append({"k": "Lease", "v": "Not stated", "c": True})
    if m.get("per") == "year":
        det.append({"k": "Rent period", "v": "MLS lists the rent period as \"Year\"", "c": True})
    f = m.get("furnished") or (b.get("features") or {}).get("Furnished")
    if f:
        det.append({"k": "Furnished", "v": "Yes" if f.lower().startswith("furn") else "No" if f.lower().startswith("unf") else f})
    if b.get("floor"):
        det.append({"k": "Floor", "v": "%s (legal description)" % b["floor"]})
    view = (b.get("features") or {}).get("View")
    if view and view.lower() != "view":
        det.append({"k": "View", "v": view})
    av = re.search(r"(?i)\bavailable (now|immediately|\w+ \d{1,2}(?:st|nd|rd|th)?(?:,? \d{4})?)", hints)
    if av:
        det.append({"k": "Available", "v": av.group(1).capitalize()})
    yr = m.get("yearBuilt") or (b.get("features") or {}).get("Year Built")
    if yr:
        det.append({"k": "Year built", "v": str(yr)})
    det.append({"k": "MLS", "v": L["mls"]})
    return {"spec": spec, "rentText": "%s/mo" % money(rent) if rent else "Rent not listed", "rentSub": sub, "details": det}


def main(argv):
    root = Path(argv[0]).resolve()
    lo = hi = None
    if "--range" in argv:
        i = argv.index("--range")
        lo, hi = int(argv[i + 1]), int(argv[i + 2])
    listings = json.loads((root / "data/listings.json").read_text())
    out = {}
    for L in listings:
        if not L.get("mls"):
            continue
        rec_p = KIT / "db" / "listings" / (L["mls"] + ".json")
        rec = json.loads(rec_p.read_text()) if rec_p.exists() else {}
        if not rec:
            print("%-20s no data in db/listings: run matrix_grid.js + ingest_matrix.py and fetch_listings.py" % L["id"])
            continue
        out[L["id"]] = d = draft(L, rec, lo, hi)
        print("%-20s %-28s %-10s %d details, %d to confirm" % (L["id"], d["spec"], d["rentText"], len(d["details"]),
                                                               sum(1 for x in d["details"] if x.get("c"))))
    if "--write" in argv:
        p = root / "data/cards.json"
        cards = json.loads(p.read_text()) if p.exists() else {"homes": {}}
        for hid, d in out.items():
            c = cards["homes"].setdefault(hid, {"flags": [], "prio": [], "details": []})
            keep = [x for x in c.get("details", []) if x["k"] not in {y["k"] for y in d["details"]}]
            c.update({k: d[k] for k in ("spec", "rentText", "rentSub")})
            c["details"] = [x for x in d["details"] if x["k"] != "MLS"] + [x for x in keep if x["k"] != "MLS"] + [{"k": "MLS", "v": d["details"][-1]["v"]}]
            c.setdefault("flags", []); c.setdefault("prio", [])
        p.write_text(json.dumps(cards, indent=1, ensure_ascii=False), encoding="utf-8")
        print("merged into data/cards.json")
    else:
        (root / "data/cards-draft.json").write_text(json.dumps({"homes": out}, indent=1, ensure_ascii=False), encoding="utf-8")
        print("wrote data/cards-draft.json (add --write to merge into data/cards.json)")


if __name__ == "__main__":
    main(sys.argv[1:])

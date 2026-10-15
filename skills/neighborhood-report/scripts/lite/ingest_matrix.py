#!/usr/bin/env python3
"""Map Lite data retrieval: store the Matrix grid (from matrix_grid.js) in the shared listing store. No network.

    python3 -I ingest_matrix.py "<client folder>" grid.json      # also writes data/matrix-facts.json (id -> row)
    python3 -I ingest_matrix.py --print grid.json                # just store + print

Matrix is the source of truth for status, list price, rent period (PER), furnished (F$), beds/baths, size, style and
year. Each row lands in <kit>/db/listings/<MLS>.json under "matrix" with the date seen, next to the "bex" record from
fetch_listings.py. Style codes map to the lease kind used everywhere else: R61/R63/R65/R67/R71/R73 = seasonal,
R80-R85 = off-season, other R6x = annual (per the neighborhood-report skill). Prints one line per row.
"""
import json
import re
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
DB = KIT / "db" / "listings"
SEASONAL = {"R61", "R63", "R65", "R67", "R71", "R73"}
STATUS = {"A": "active", "R": "rented", "P": "pending", "C": "closed", "X": "expired", "W": "withdrawn", "B": "backup",
          "T": "temporarily off market", "CS": "coming soon"}


def money(s):
    s = (s or "").replace("$", "").replace(",", "").strip()
    return int(float(s)) if re.fullmatch(r"[\d.]+", s) else None


def norm(row, seen):
    style = row.get("Style", "")
    lease = "seasonal" if style in SEASONAL else "off-season" if re.fullmatch(r"R8[0-5]", style) else "annual" if style.startswith("R") else "unknown"
    return {"mls": row["ML #"], "status": STATUS.get(row.get("St", ""), row.get("St")), "address": row.get("Address"),
            "listPrice": money(row.get("LP$")), "per": (row.get("PER") or "").lower() or None, "furnished": row.get("F$"),
            "beds": row.get("#Beds"), "fullBaths": row.get("#FB"), "halfBaths": row.get("#HB"), "sqft": money(row.get("SqFt LA")) if (money(row.get("SqFt LA")) or 0) <= 20000 else None,
            "style": style, "leaseKind": lease, "sqftNote": "Matrix SqFt %s is a building total, not the unit; dropped" % row.get("SqFt LA") if (money(row.get("SqFt LA")) or 0) > 20000 else None, "yearBuilt": row.get("YR"), "subdivision": row.get("SN"),
            "soldPrice": money(row.get("SP$")), "seen": seen, "source": "Miami Realtors Matrix results grid"}


def main(argv):
    printing = argv[0] == "--print"
    text = Path(argv[1]).read_text()
    if text.lstrip().startswith("{"):
        grid = json.loads(text)
    else:  # the compact tab-separated form matrix_grid.js returns
        lines = [x for x in text.strip().splitlines() if x.strip() and not x.startswith("#more")]
        if lines[0].startswith("#error"):
            raise SystemExit("ERROR: " + lines[0][7:])
        seen = lines[0][6:].strip() if lines[0].startswith("#seen") else None
        body = lines[1:] if seen else lines
        head = body[0].split("\t")
        # compact columns from matrix_grid.js -> the grid's own header names
        alias = {"MLS": "ML #", "LP": "LP$", "F": "F$", "Beds": "#Beds", "FB": "#FB", "HB": "#HB", "SqFt": "SqFt LA"}
        head = [alias.get(h, h) for h in head]
        expand = {"PER": {"M": "Month", "Y": "Year"}, "F$": {"F": "Furnished", "U": "Unfurnished", "O": "Optional"}}
        rows = []
        for x in body[1:]:
            if x.startswith("MLS\t"):
                continue  # a repeated header from a later chunk
            r = dict(zip(head, x.split("\t")))
            for k, m in expand.items():
                if k in r:
                    r[k] = m.get(r[k], r[k])
            rows.append(r)
        grid = {"seen": seen, "rows": rows}
    if grid.get("error"):
        raise SystemExit("ERROR: " + grid["error"])
    DB.mkdir(parents=True, exist_ok=True)
    recs = {}
    for row in grid["rows"]:
        r = norm(row, grid.get("seen"))
        p = DB / (r["mls"] + ".json")
        old = json.loads(p.read_text()) if p.exists() else {}
        old["matrix"] = r
        p.write_text(json.dumps(old, indent=1, ensure_ascii=False), encoding="utf-8")
        recs[r["mls"]] = r
        print("%-10s %-8s $%-6s /%-5s %-11.11s %s bd %s/%s ba %5s sf %-4s %-8s %s" % (
            r["mls"], r["status"], r["listPrice"], r["per"], r["furnished"], r["beds"], r["fullBaths"], r["halfBaths"],
            r["sqft"], r["style"], r["leaseKind"], r["address"]))
    if not printing:
        root = Path(argv[0]).resolve()
        listings = json.loads((root / "data/listings.json").read_text())
        out = {L["id"]: recs[L["mls"]] for L in listings if L.get("mls") in recs}
        (root / "data/matrix-facts.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
        missing = [L["id"] for L in listings if L.get("mls") and L["mls"] not in recs]
        print("%d of %d client listings matched%s" % (len(out), len(listings), ("; not in this grid: " + ", ".join(missing)) if missing else ""))


if __name__ == "__main__":
    main(sys.argv[1:])

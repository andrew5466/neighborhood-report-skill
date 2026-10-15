#!/usr/bin/env python3
"""Map Lite data retrieval: building facts without a research agent (network; main session).

    python3 -I fetch_buildings.py "<client folder>"        # buildings of this client that db/buildings.json lacks
    python3 -I fetch_buildings.py "<client folder>" --all  # every building of this client

For each building, find its page on the listing site from any of its units (fetch_listings.py stores `buildingPage`),
read it (30-day cache) and keep only the sentences about what a client asks: amenities, gym, pool, spa, entrance
(doorman, concierge, security, valet, lobby), floors/stories/towers, year built, units, pets, beach or water access,
fees. Stores them in <kit>/db/buildings-raw/<slug>.json with source and date, and prints at most 6 per building.
A person (or Claude) then writes the building's facts in db/buildings.json from these few lines: no web search.
Each sentence is the listing site's marketing text: state facts plainly and keep a Confirm on anything it can't back.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetchcache import KIT, get_text, summary  # noqa: E402
from fetch_listings import lines_of  # noqa: E402

DB = KIT / "db"
KEY = re.compile(r"(?i)\b(amenit\w*|fitness|gym|pool|spa|sauna|concierge|doorman|door attendant|security|valet|lobby|"
                 r"stories|story|floors|towers?|built|constructed|units|residences|pets?|beach access|ocean frontage|"
                 r"oceanfront|marina|fees?|renovat\w*|elevators?)\b")
DROP = re.compile(r"(?i)(airport|alert|contact your BEX|price drops|for sale emerge|asking price|list-to-sell|days to sell|"
                  r"management fees in Miami-Dade|check the individual listing pages|This fee includes)")


def sentences(lines):
    text = " ".join(x for x in lines if len(x) > 40)
    for s in re.split(r"(?<=[.!?])\s+", text):
        s = s.strip()
        if 30 < len(s) < 420 and KEY.search(s) and not DROP.search(s):
            yield s


def main(argv):
    root = Path(argv[0]).resolve()
    every = "--all" in argv
    listings = json.loads((root / "data/listings.json").read_text())
    known = json.loads((DB / "buildings.json").read_text()) if (DB / "buildings.json").exists() else {}
    byb = {}
    for L in listings:
        if L.get("building") and L.get("mls"):
            byb.setdefault(L["building"], []).append(L["mls"])
    (DB / "buildings-raw").mkdir(parents=True, exist_ok=True)
    shown = {}
    for b, mlss in byb.items():
        if b in known and not every:
            print("%-18s in db/buildings.json (seen %s); skipped" % (b, known[b].get("seen", "?")))
            continue
        page = None
        for m in mlss:
            p = DB / "listings" / (m + ".json")
            if p.exists():
                page = json.loads(p.read_text()).get("bex", {}).get("buildingPage")
                if page:
                    break
        if not page:
            print("%-18s no building page found (run fetch_listings.py first, or the site has none)" % b)
            continue
        if page in shown:
            print("%-18s same building page as %s; see above" % (b, shown[page]))
            continue
        shown[page] = b
        html, final, date, hit = get_text(page, ttl_days=30, gap=1.5, headers={"User-Agent": "Mozilla/5.0 (Macintosh) AMG-map-lite/1.1"})
        hints = list(dict.fromkeys(sentences(lines_of(html))))
        slug = final.rstrip("/").split("/")[-1]
        (DB / "buildings-raw" / (slug + ".json")).write_text(json.dumps(
            {"building": b, "source": final, "seen": date, "hints": hints}, indent=1, ensure_ascii=False), encoding="utf-8")
        print("%-18s %s (%d lines; full list in db/buildings-raw/%s.json)" % (b, final, len(hints), slug))
        for s in hints[:6]:
            print("    - " + s[:240])
    print(summary())


if __name__ == "__main__":
    main(sys.argv[1:])

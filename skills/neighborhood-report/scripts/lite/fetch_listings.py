#!/usr/bin/env python3
"""Map Lite data retrieval: listing facts by MLS number, without a research agent (network; main session).

    python3 -I fetch_listings.py "<client folder>"          # every MLS in data/listings.json
    python3 -I fetch_listings.py --mls A12075680 A12060523   # any MLS numbers, printed only
    add --refresh to ignore the 2-day page cache

Reads the public Bex Realty page for each MLS (https://www.bexrealty.com/FL/<city>/x/rental/<MLS> redirects to the
listing), parses its structured data (JSON-LD) and its labelled features, and writes one shared record per listing to
<kit>/db/listings/<MLS>.json: price, beds, baths, sq ft, coordinates, building, floor (from the legal description),
furnished, view, waterfront, pets, year built, days on market, the listing remarks, lease/availability phrases found in
the remarks, and the full-size first photo. With a client folder it also writes data/listing-facts.json (id -> record)
and adds missing photos to data/photo-sources.json. Prints one line per listing; never prints the page.
Status (active / rented) is NOT on Bex: take it from the Matrix grid (matrix_grid.js + ingest_matrix.py).
Every value carries its source URL and date. A field the page doesn't show stays absent: nothing is guessed.
"""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetchcache import KIT, get_text, summary  # noqa: E402

DB = KIT / "db" / "listings"
FEATURES = ["View", "Furnished", "Pool Features", "Waterfront Features", "Year Built", "Pets Allowed", "Days On Market",
            "Community Name", "Legal Description", "Property Type", "Parking Features", "Laundry Features", "Lease Term"]
ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9,
       "tenth": 10, "eleventh": 11, "twelfth": 12, "thirteenth": 13, "fourteenth": 14, "fifteenth": 15, "sixteenth": 16,
       "seventeenth": 17, "eighteenth": 18, "nineteenth": 19, "twentieth": 20}
LEASE_RE = re.compile(r"[^.!?]*\b(annual|minimum|min\.?|short[- ]term|seasonal|month(?:ly)?|year(?:ly)?|lease|available|"
                      r"furnished|turn[- ]?key)\b[^.!?]*[.!?]", re.I)


def lines_of(html):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S)
    t = re.sub(r"<[^>]+>", "\n", t)
    return [re.sub(r"\s+", " ", x).strip() for x in t.split("\n") if x.strip()]


def parse(html, url, date):
    rec = {"source": url, "seen": date}
    for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            d = json.loads(m)
        except ValueError:
            continue
        if isinstance(d, dict) and (d.get("numberOfBedrooms") is not None or d.get("floorSize")):  # any listing type
            rec["beds"] = d.get("numberOfBedrooms")
            rec["baths"] = d.get("numberOfBathroomsTotal")
            rec["sqft"] = (d.get("floorSize") or {}).get("value")
            g = d.get("geo") or {}
            if g.get("latitude"):
                rec["lat"], rec["lon"] = g["latitude"], g["longitude"]
            rec["address"] = (d.get("address") or {}).get("streetAddress")
            img = d.get("image")
            if isinstance(img, str) and "nophoto" not in img:
                rec["photo"] = img.replace("-thumb.", "-full.")
            m2 = re.search(r" in (.+)$", d.get("name", ""))
            if m2:
                rec["building"] = m2.group(1)
    L = lines_of(html)
    # fallbacks when a page has no listing JSON-LD: the "Overview of ..." block and the og:image tag
    if rec.get("beds") is None:
        ov = next((i for i, x in enumerate(L) if x.startswith("Overview of ")), None)
        if ov is not None:
            for x in L[ov + 1:ov + 8]:
                if m := re.fullmatch(r"(\d+) Bedrooms?", x):
                    rec["beds"] = int(m.group(1))
                elif m := re.fullmatch(r"(\d+)(?:/(\d+))? Bathrooms?", x):
                    rec["baths"] = int(m.group(1)) + (0.5 * int(m.group(2)) if m.group(2) else 0)
                elif m := re.fullmatch(r"([\d,]+) Square Feet", x):
                    rec["sqft"] = int(m.group(1).replace(",", ""))
    if not rec.get("photo"):
        og = re.search(r'<meta property="og:image" content="([^"]+)"', html)
        if og and "nophoto" not in og.group(1):
            rec["photo"] = og.group(1).replace("-thumb.", "-full.")
    if not rec.get("building"):
        b = re.search(r"condo for rent in ([^!.]+)[!.]", html)
        if b:
            rec["building"] = b.group(1).strip()
    for i, x in enumerate(L[:40]):
        if re.fullmatch(r"\$[\d,]+", x):
            rec["price"] = int(x[1:].replace(",", ""))
            break
    for i, x in enumerate(L):
        if re.fullmatch(r"Listed For \d+ Days", x):
            # the remarks run over several lines (the page breaks them with tags) until Bex's own boilerplate
            parts = []
            for y in L[i + 1:i + 12]:
                if re.match(r"(This lovely|This (beautiful|stunning|spacious)? ?\w+ was built|Please contact your BEX|Features & Amenities)", y):
                    break
                parts.append(y)
            rec["remarks"] = " ".join(parts)
            break
    try:
        a = L.index("Features & Amenities")
    except ValueError:
        a = None
    if a is not None:
        feats, i = {}, a + 1
        while i < len(L) - 1 and not L[i].startswith("Recent "):
            if L[i] in FEATURES:
                feats[L[i]] = L[i + 1]
                i += 2
            else:
                i += 1
        rec["features"] = feats
        ld = feats.get("Legal Description", "")
        mf = re.search(r"\b(" + "|".join(ORD) + r")\s+Floor\b", ld, re.I)
        if mf:
            rec["floor"] = ORD[mf.group(1).lower()]
    if rec.get("remarks"):
        rec["leaseHints"] = [m.group(0).strip() for m in LEASE_RE.finditer(rec["remarks"])][:6]
    return rec


def fetch(mls, city="Miami-Beach", refresh=False):
    url = "https://www.bexrealty.com/FL/%s/x/rental/%s" % (city, mls)
    html = None
    for attempt in (1, 2):  # one retry: the site's CDN returns an occasional 5xx
        try:
            html, final, date, hit = get_text(url, ttl_days=0 if refresh else 2, gap=1.5,
                                              headers={"User-Agent": "Mozilla/5.0 (Macintosh) AMG-map-lite/1.1"})
            break
        except Exception as ex:  # noqa: BLE001 - report and keep going with the other listings
            err = str(ex)
            time.sleep(4)
    if html is None:
        return {"mls": mls, "error": "fetch failed (%s); rerun later" % err, "source": url, "seen": time.strftime("%Y-%m-%d")}
    if mls not in html:
        return {"mls": mls, "error": "listing page not found", "source": final, "seen": date}
    rec = parse(html, final, date)
    rec["mls"] = mls
    DB.mkdir(parents=True, exist_ok=True)
    old = json.loads((DB / (mls + ".json")).read_text()) if (DB / (mls + ".json")).exists() else {}
    old["bex"] = rec
    (DB / (mls + ".json")).write_text(json.dumps(old, indent=1, ensure_ascii=False), encoding="utf-8")
    return rec


def line(r):
    if r.get("error"):
        return "%-10s %s" % (r["mls"], r["error"])
    f = r.get("features", {})
    return "%-10s $%-6s %s/%s %5s sf fl%-3s %-24.24s furn:%-10.10s view:%-14.14s yr:%s dom:%s photo:%s hints:%d" % (
        r["mls"], r.get("price", "?"), r.get("beds", "?"), r.get("baths", "?"), r.get("sqft", "?"), r.get("floor", "?"),
        r.get("building", "?"), f.get("Furnished", "?"), f.get("View", "?"), f.get("Year Built", "?"), f.get("Days On Market", "?"),
        "y" if r.get("photo") else "n", len(r.get("leaseHints", [])))


def main(argv):
    refresh = "--refresh" in argv
    argv = [a for a in argv if a != "--refresh"]
    if argv and argv[0] == "--mls":
        for m in argv[1:]:
            print(line(fetch(m, refresh=refresh)))
        print(summary())
        return
    root = Path(argv[0]).resolve()
    listings = json.loads((root / "data/listings.json").read_text())
    facts, psrc_p = {}, root / "data/photo-sources.json"
    psrc = json.loads(psrc_p.read_text()) if psrc_p.exists() else {}
    for L in listings:
        if not L.get("mls"):
            continue
        r = fetch(L["mls"], refresh=refresh)
        facts[L["id"]] = r
        print("%-20s %s" % (L["id"], line(r)))
        if r.get("photo") and L["id"] not in psrc:
            psrc[L["id"]] = {"url": r["photo"], "page": r["source"], "site": "Bex Realty", "kind": "unit"}
    (root / "data/listing-facts.json").write_text(json.dumps(facts, indent=1, ensure_ascii=False), encoding="utf-8")
    psrc_p.write_text(json.dumps(psrc, indent=1), encoding="utf-8")
    print(summary(), "| lease/availability phrases are in data/listing-facts.json (leaseHints); read only those, not the pages")


if __name__ == "__main__":
    main(sys.argv[1:])

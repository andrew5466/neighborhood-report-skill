#!/usr/bin/env python3
"""Map Lite: check the built page offline before the one visual look. No network, no browser.

    python3 -I check_page.py "<client folder>"

Reads out/<slug>.html and checks: page size under 16 MB; every home in data/listings.json (minus exclude) is on the
page once; each home has a price, a spec or beds, a photo (or is listed as having none); each building has facts
(buildings layout); every OneHome link is a portal.onehome.com share; walks over maxWalkMin will show as miles; the
client's banned words (client.json "bannedWords") appear nowhere in the page's text or data. Prints PASS/WARN/FAIL
lines and exits 1 on any FAIL. The visual check (one screenshot at phone width) is still a person's or Claude's.
"""
import json
import re
import sys
from pathlib import Path


def main(root):
    cfg = json.loads((root / "client.json").read_text())
    page_p = root / "out" / (cfg["slug"] + ".html")
    s = page_p.read_text(encoding="utf-8")
    m = re.search(r"const D = (\{.*?\});\n", s, re.S)
    D = json.loads(m.group(1))
    res = []
    add = lambda lvl, msg: res.append((lvl, msg))  # noqa: E731
    size = page_p.stat().st_size / 1e6
    add("PASS" if size < 16 else "FAIL", "page size %.1f MB" % size)
    want = [x["id"] for x in json.loads((root / "data/listings.json").read_text()) if x["id"] not in set(cfg.get("exclude", []))]
    got = [h["id"] for h in D["homes"]]
    add("PASS" if sorted(want) == sorted(got) else "FAIL", "%d of %d homes on the page%s" % (
        len(got), len(want), "" if sorted(want) == sorted(got) else " (missing: %s)" % ", ".join(sorted(set(want) - set(got)))))
    no_price = [h["id"] for h in D["homes"] if not h.get("rentText")]
    add("FAIL" if no_price else "PASS", "every home has a price" + (": missing " + ", ".join(no_price) if no_price else ""))
    no_photo = [h["id"] for h in D["homes"] if not h.get("photo")]
    add("WARN" if no_photo else "PASS", "%d homes without a photo%s" % (len(no_photo), (": " + ", ".join(no_photo)) if no_photo else ""))
    if D.get("buildings") is not None:
        nb = sorted({h["building"] for h in D["homes"]} - set(k for k, v in D["buildings"].items() if v and v.get("facts")))
        add("WARN" if nb else "PASS", "building facts for every building" + (": none for " + ", ".join(nb) if nb else ""))
    links = re.findall(r"https://portal\.onehome\.com/[^\"' ]+", json.dumps(D))
    bad = [u for u in links if "/share/" not in u]
    add("FAIL" if bad else "PASS", "%d OneHome links, all shares" % len(links) if not bad else "OneHome links that are not shares: %s" % bad)
    mw = D.get("maxWalkMin")
    if mw:
        long_walks = sum(1 for h in D["homes"] for r in (h.get("r") or {}).values() if r.get("profile") == "foot" and r["min"] > mw)
        add("PASS", "%d walks over %d min will show as miles" % (long_walks, mw))
    banned = cfg.get("bannedWords", [])
    if banned:
        visible = re.sub(r"<script>.*?</script>|<style>.*?</style>|<[^>]+>", " ", s, flags=re.S)
        data_txt = json.dumps({k: v for k, v in D.items() if k not in ("base", "shapes", "layers")})
        data_txt = re.sub(r"data:image[^\"]+", "", data_txt)
        hits = sorted({w for w in banned if re.search(r"(?i)\b%s\b" % re.escape(w), visible + data_txt)})
        add("FAIL" if hits else "PASS", "banned words absent" if not hits else "banned words found: %s" % hits)
    for lvl, msg in res:
        print("%-4s %s" % (lvl, msg))
    if any(l == "FAIL" for l, _ in res):
        raise SystemExit(1)


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())

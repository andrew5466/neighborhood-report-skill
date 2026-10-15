#!/usr/bin/env python3
"""Map Lite: the whole data pipeline in one command, with the least output. Run from the MAIN session.

    python3 -I lite.py "<client folder>" [--range 5000 6500] [--offline] [--cards]

Order (each step is cached or skipped when its output is current, so a rerun costs seconds):
  1. fetch_listings.py   listing pages by MLS -> db/listings (network, 2-day cache)          [skipped with --offline]
  2. draft_cards.py      card drafts from Matrix + listing data (--cards, or no data/cards.json yet, merges them)
  3. process.py          anchors / shapes / straight-line distances (no network)
  4. fetch_routes.py     walking/driving routes (network, cached forever)                   [skipped with --offline]
  5. fetch_photos.py     first photos, only new or changed ones (network)                      [skipped with --offline]
  6. fetch_buildings.py  building-page facts for buildings db/buildings.json lacks (network)   [skipped with --offline]
  7. build.py            the page
  8. check_page.py       offline checks on the built page (homes, prices, links, banned words)
  9. status.py           one screen: what is done, missing or stale
The Matrix grid (status, price, rent period) needs the browser: run matrix_grid.js on the Matrix results page and
ingest_matrix.py before step 2. Each step prints at most one line per home; nothing dumps raw pages or JSON.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run(step, *args, quiet=False):
    t = time.time()
    p = subprocess.run([sys.executable, "-I", str(HERE / step), *args], capture_output=True, text=True)
    out = (p.stdout + p.stderr).strip().splitlines()
    tail = out[-1] if out else ""
    print("%-18s %5.1fs  %s" % (step, time.time() - t, "FAILED" if p.returncode else "ok"), ("· " + tail[:110]) if tail else "")
    if p.returncode:
        print("\n".join(out[-12:]))
        raise SystemExit(p.returncode)
    return out


def main(argv):
    root = Path(argv[0]).resolve()
    offline, cards = "--offline" in argv, "--cards" in argv
    rng = []
    if "--range" in argv:
        i = argv.index("--range")
        rng = ["--range", argv[i + 1], argv[i + 2]]
    cfg = json.loads((root / "client.json").read_text())
    t0 = time.time()
    if not offline:
        run("fetch_listings.py", str(root))
    run("draft_cards.py", str(root), *rng, *(["--write"] if cards or not (root / "data/cards.json").exists() else []))
    run("process.py", str(root))
    if not offline and cfg.get("anchors"):
        run("fetch_routes.py", str(root))
    if not offline and (root / "data/photo-sources.json").exists():
        run("fetch_photos.py", str(root))
    if not offline and cfg.get("layout") == "buildings":
        for line in run("fetch_buildings.py", str(root)):
            if line.startswith("    - ") or "no building page" in line or "lines; full list" in line:
                print("  " + line.strip())
    run("build.py", str(root))
    run("check_page.py", str(root))
    print("total %.1fs\n" % (time.time() - t0))
    print("\n".join(run("status.py", str(root), quiet=True)))


if __name__ == "__main__":
    main(sys.argv[1:])

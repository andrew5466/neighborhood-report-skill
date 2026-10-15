#!/usr/bin/env python3
"""Map Lite: download each home's first listing photo (network; main session, Andrew's OK for photo use).

    python3 -I fetch_photos.py "<client folder>"

Reads <client>/data/photo-sources.json:
  {listing id: {"url": "<direct image URL>", "page": "<listing page>", "site": "Bex Realty", "kind": "unit" | "building"}}
Downloads each image, shrinks it to 900 px wide JPEG with macOS `sips` (originals stay in a temp folder), and
writes <client>/data/photos/<id>.jpg plus data/photos.json, which build.py embeds. A building photo is labelled
as one on the page.
"""
import json
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

UA = "AMG-map-lite/1.0 (andrew2000garcia@gmail.com)"


def main(root):
    src = json.loads((root / "data/photo-sources.json").read_text())
    out_dir = root / "data/photos"
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = {}
    with tempfile.TemporaryDirectory() as tmp:
        for pid, s in src.items():
            raw = Path(tmp) / (pid + ".orig")
            try:
                req = urllib.request.Request(s["url"], headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=60) as r:
                    raw.write_bytes(r.read())
                dst = out_dir / (pid + ".jpg")
                subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "72", "--resampleWidth", "900", str(raw), "--out", str(dst)],
                               check=True, capture_output=True)
            except Exception as ex:
                print("%-20s FAILED: %s" % (pid, ex))
                continue
            label = "Building photo" if s.get("kind") == "building" else "Listing photo"
            meta[pid] = {"file": "photos/%s.jpg" % pid, "credit": "%s · %s" % (label, s["site"]), "page": s["page"], "url": s["url"]}
            print("%-20s %6d bytes  %s" % (pid, dst.stat().st_size, label))
    (root / "data/photos.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())

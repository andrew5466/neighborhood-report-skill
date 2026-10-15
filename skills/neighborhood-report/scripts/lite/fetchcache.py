#!/usr/bin/env python3
"""Map Lite data retrieval: one cached, polite HTTP layer for every script (stdlib only).

    from fetchcache import get_text, get_json

Every response is stored in <kit>/db/cache/<sha1 of url+body>.json with the date it was fetched, so a second client
(or a rerun) never pays for the same geocode, route or listing page twice. `ttl_days=None` keeps an answer forever
(addresses and walking routes don't change); listing pages use a short TTL because prices and status do.
Requests to the same host are spaced at least `gap` seconds apart (Nominatim and OSRM ask for 1/second).
Network calls run in the MAIN session only, after Andrew's OK; helper agents are denied by the security harness.
"""
import hashlib
import json
import time
import urllib.request
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
CACHE = KIT / "db" / "cache"
UA = "AMG-map-lite/1.1 (andrew2000garcia@gmail.com)"
_last = {}
stats = {"hit": 0, "miss": 0}


def _key(url, data):
    return hashlib.sha1((url + "\n" + (data.decode() if data else "")).encode()).hexdigest()


def _fetch(url, data, headers, gap):
    host = url.split("/")[2]
    wait = gap - (time.time() - _last.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.read().decode("utf-8", "replace"), r.geturl()
    finally:
        _last[host] = time.time()


def get_text(url, data=None, ttl_days=None, gap=1.1, headers=None):
    """Return (text, final_url, fetched_date, from_cache)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / (_key(url, data) + ".json")
    if f.exists():
        c = json.loads(f.read_text())
        if ttl_days is None or time.time() - c["t"] < ttl_days * 86400:
            stats["hit"] += 1
            return c["body"], c.get("final", url), c["date"], True
    body, final = _fetch(url, data, headers, gap)
    f.write_text(json.dumps({"url": url, "final": final, "t": time.time(), "date": time.strftime("%Y-%m-%d"), "body": body}))
    stats["miss"] += 1
    return body, final, time.strftime("%Y-%m-%d"), False


def get_json(url, data=None, ttl_days=None, gap=1.1, headers=None):
    body, final, date, hit = get_text(url, data, ttl_days, gap, headers)
    return json.loads(body), date, hit


def summary():
    return "cache: %d hit, %d fetched" % (stats["hit"], stats["miss"])

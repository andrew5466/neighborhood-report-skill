# Neighborhood Report Skill

A Claude Code skill that builds AMG Group's interactive, phone-first neighborhood reports for rental and buyer clients, from the shortlist to a private claude.ai page Andrew shares himself.

Private. Client data never goes in this repo; it lives in the vault.

## Formats

| Format | When | What the client sees |
|---|---|---|
| **Lite, beach mode** (default) | A shortlist exists, 10 homes or fewer, and the client named priorities (beach, a path, bike lanes) | One map with the priority layers (Beachwalk, bike lanes, beach sand, one place type), walk and bike routes with a bike icon riding the route, first listing photo, collapsed name-and-price cards, Beach / Bike / Privacy rows, red and gold flags, sort switch, compare up to 3, Interested / Pass, OneHome buttons |
| **Lite, anchors mode** | Same, but fixed places drive the choice (school, work, a gym) | The same page, with routes and minutes to each anchor instead of the beach |
| **Lite, anchors + areas** | The client is choosing between several neighborhoods (replaces the bubble report) | The anchors page with an Areas row: one card per neighborhood (homes, rent range, quickest time, places-only summary) that filters the map and list. Area copy passes the same fair-housing check as the bubble tool |
| **Full bubble report** (legacy) | Only to update a report already built with it | Area bubbles that burst into a map of every home; lives in the separate [`neighborhood-report-tool`](https://github.com/andrew5466/neighborhood-report-tool) repo, which `build.py` also reads for base maps, the Leaflet CSS and the fair-housing word list |

## Layout

```
.claude-plugin/
  marketplace.json            plugin manifest (Claude Code plugin marketplace format)
skills/
  neighborhood-report/
    SKILL.md                  the skill: format choice, Lite path, full path, gates
    reference/
      lite-kit.md             the Lite kit: page, files, client folder, commands, limits
      process-lessons.md      what the first runs taught (no client details)
      data-retrieval-review.md  the Algorithm Review behind the fast data path (tokens and time halved)
    scripts/
      lite/
        fetch_osm.py          network: geocodes + one Overpass pull (paths, bike lanes, beach, coastline)
        process.py            offline: layers + straight-line distances, one line per home to check
        fetch_routes.py       network: walk and bike routes (OSRM, routing.openstreetmap.de)
        fetch_photos.py       network: first listing photo per home, shrunk to 900 px
        build.py              offline: fills the template, inlines the base map, refuses private text
        fetchcache.py         the one HTTP layer: dated cache + polite spacing (routes/geocodes forever, pages 2 days)
        fetch_listings.py     network: listing facts, remarks, lease phrases, floor, view, photo by MLS (no agent)
        matrix_grid.js        run in the Matrix results page: the grid as compact rows, 12 per call
        ingest_matrix.py      offline: store the Matrix rows (status, price, rent period, style → lease kind)
        draft_cards.py        offline: card drafts from Matrix + listing data
        status.py             offline: one screen per client, what is done, missing or stale
        lite.py               the whole pipeline in one command (a rerun takes about 3 s)
        template.html         the beach-mode page
        template-anchors.html the anchors-mode page
    assets/
      client.example.json     a placeholder client config to copy
      db-places.json          verified places for anchors (Mila, Catch, Carbone, the Delano, Lincoln Road, the beach)
scripts/
  build_from_vault.py         refresh this repo from the live skill and the vault kit
  check_secrets.sh            scan before every push
install.sh                    install SKILL.md into ~/.claude/skills (with --dry-run)
```

## Install

```bash
bash install.sh --dry-run
bash install.sh
```

Or add the repo as a plugin marketplace in Claude Code (`/plugin marketplace add andrew5466/neighborhood-report-skill`).

The kit scripts run from the vault copy (`Brain/Real Estate/Market Intel/Neighborhood Map Lite/scripts`), next to the Neighborhood Report Tool, which supplies the region base maps (`maps/<region>.osm.json`) and the Leaflet CSS. This repo is the versioned copy.

## Update this repo

```bash
python3 -I scripts/build_from_vault.py     # copies the skill, kit scripts and kit README; never deletes
bash scripts/check_secrets.sh              # must print "Secret scan passed."
git add -A && git commit -m "..." && git push
```

Push over HTTPS (`gh` is the credential helper); this Mac has no GitHub SSH key.

## Gates the skill enforces

- **Truth:** every fact has a source; unknowns show as a gold Confirm; distances say straight-line or route.
- **Fair housing:** places only, never who lives somewhere; no school ratings; no safety claims.
- **Drafts only:** the agent never texts, emails or posts. Andrew shares every page.
- **Private:** no client contact details, family details or vault paths on a page; the build refuses them.
- **Network:** only in the main session, after Andrew's OK.

## Requirements

Python 3.11+ (standard library only), macOS `sips` for photos, Node for a syntax check, the claude.ai Artifact tool for publishing. Map data © OpenStreetMap contributors (ODbL). Leaflet 1.9.4 loads from cdnjs.

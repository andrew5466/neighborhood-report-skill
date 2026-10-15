# Neighborhood Map Lite

One map, a short list of homes, and the client's own top priorities measured for every home. It's the fast format of the neighborhood report. First client: Kevin Beach Map. Why it exists: Neighborhood Map Lite — Kevin Run Review (2026-10-14).

**Use Lite when:** the shortlist already exists (Andrew's PDF, a Matrix pull, a doc), there are 10 homes or fewer, and the client named what matters (beach, bike path, a commute, a park). **Use the full tool** (Neighborhood Report Tool) when the client is choosing between several neighborhoods and two fixed anchors drive the decision (school + work).

## The page

- A real OpenStreetMap street map (no tiles; vector, drawn with Leaflet), plus the client's priority layers: a named path (the Beachwalk), bike lanes, beach sand, and one kind of nearby place (pizza).
- Layer chips toggle each layer. **Show all homes** reframes.
- A sort switch: Beach (walk minutes), Rent, Ride (bike minutes). Each card is collapsed to number, name and price. A tap opens it (one at a time), shows it on the map, draws the walking route to the sand, and a bike icon rides the bike route to the path (tap the bike to ride again).
- An open card shows, in order: the first listing photo, Beach (walk minutes by route + straight-line), Bike (ride minutes), Privacy, then the flags (red = misses the brief, gold = to confirm), then **Interested / Pass / Compare**, then rent, lease, layout, the nearest place of interest, and pros and cons.
- **Interested / Pass** is kept on the client's device and, when the page is published with `{"comments": {"composer_only": true}}`, opens a comment pinned to that button so the client can write Andrew a note. Andrew sees it in the page's comments; Claude reads them with ArtifactComments and files them. **Copy my picks** copies a text summary for clients without a sign-in. Invite clients as Commenter, never Editor.
- **Compare** up to 3 homes in a side-by-side table (photo, rent, walk, ride, split, lease, size, privacy, misses, to confirm), scrolling sideways inside its own box on a phone.
- OneHome buttons at the end of the list. A short Sources note at the bottom.
- No agent opinions on the page ("Andrew's pick", "best building") and no restated brief. The client judges.

## Files

| Path | What it is |
|---|---|
| `scripts/fetch_osm.py` | One OpenStreetMap pull: Nominatim geocodes for `places`, one Overpass query (paths, bike lanes, beach, coastline) over `bbox`. **Network: run it in the main session** after Andrew's OK. Helper agents are denied by the security harness and can't ask. |
| `scripts/fetch_routes.py` | **Network, main session.** Walking route to the sand and bike route to the named path for each building (OSRM foot and bike profiles at routing.openstreetmap.de), into `data/routes.json`. Run after `process.py`. |
| `scripts/fetch_photos.py` | **Network, main session.** Downloads each home's first listing photo from `data/photo-sources.json` and shrinks it to 900 px (macOS `sips`), into `data/photos/` + `data/photos.json`. A building photo is labelled as one. |
| `scripts/process.py` | No network. Layers + straight-line distances from each building's address point to the nearest sand, the named path, the nearest bike lane and the nearest place of interest. Prints one line per home next to the shortlist's own beach text, to compare. |
| `scripts/build.py` | No network. Fills `template.html` from the client folder, inlines the region base map and the Leaflet CSS, writes `out/<slug>.html`. Refuses internal text, emails and phone numbers. |
| `scripts/template.html` | The page. Never edited per client: copy comes from `client.json`. |

The region base map comes from the Neighborhood Report Tool: `maps/miami-north.json` and `maps/miami-beach.json` (South Pointe to about 72nd St, made 2026-10-14) exist. A new area needs a frame and `basemap.py` once (tool README, "A new region").

## A client folder

```
<Client> Map/
  client.json            title, lede ({n} = number of homes), byline, sources, basemap, bbox, places,
                         homePlace (listing id -> place key), poi, path, beachMinLat, waterLabels, onehome, exclude
  data/listings.json     facts per home, each with its source (never shown)
  data/cards.json        what the client reads per home: rentText, rentSub, beachText, privacy[], details[], flags[], pros[], cons[]
                         ({"c": true} = Confirm tag; flags "l": "red" or "gold")
  <Client> — Listing Agent Texts (DRAFT).md
  <Client> Map.md        the record: link, OneHome links, open flags, clock
```

`process.py` writes `data/geocode.json`, `osm-raw.json`, `layers.json`, `measures.json`, `pois.json`; `build.py` writes `out/`.

## Run it

```bash
K="/Users/andrewgarcia/Obsidian-Vault/Brain/Real Estate/Market Intel/Neighborhood Map Lite/scripts"
C="/Users/andrewgarcia/Obsidian-Vault/Brain/Real Estate/Market Intel/<Client> Map"
python3 -I "$K/fetch_osm.py" "$C"     # network, main session, Andrew's OK
python3 -I "$K/process.py" "$C"       # read every printed line against the shortlist
python3 -I "$K/fetch_routes.py" "$C"  # network, main session
python3 -I "$K/fetch_photos.py" "$C"  # network, main session; needs data/photo-sources.json
python3 -I "$K/build.py" "$C"
```

Check once in the browser pane at Mobile width, light and dark: tap one card, confirm no sideways scroll. Publish `out/<slug>.html` as a private Artifact (icon `map`). Andrew's edits republish to the same file path; a copy-only edit doesn't need the browser check again.

## Anchors mode (school, work, any fixed place) — added 2026-10-14

For clients driven by fixed places rather than the beach. First client: Jensen Map. Set `"mode": "anchors"` in `client.json`; the beach mode is unchanged (Kevin's page rebuilds byte-identical).

- `client.json`: `anchors` = up to 3 of `{key, label, short, sortLabel, letter, profile ("car" | "bike" | "foot"), lat, lon, addr, source}` (the first anchor leads the sort and the car animation), `routeNote`, `onehome`, `basemap`, `waterLabels`. No `places`, `bbox`, `path` or `poi`, and no `fetch_osm.py`.
- `data/listings.json`: each home carries `lat`/`lon` with a source, plus `area` (shown after the address).
- `data/cards.json`: `rentText`, `rentSub`, `rentConfirm`, `prio` (the client's priorities after the anchors, e.g. Pool / Dog / Move-in: `{k, t, c}`), `details`, `flags`, `pros`, `cons`. Pin colors: green = no flags, gold = to confirm, red = a miss.
- Run: `process.py` (straight-line distance to each anchor) → `fetch_routes.py` (one OSRM route per home per anchor; car times are free-flow, no traffic, and the page says so) → `fetch_photos.py` → `build.py` (uses `template-anchors.html`).
- Optional `filters` in `client.json` (e.g. `[{"key":"all","label":"All"},{"key":"house","label":"House"},{"key":"apartment","label":"Apartment"}]`) plus `kind` / `kindLabel` per listing: a filter switch that hides cards and pins (Jensen, 2026-10-14). An anchor with `"pin": false` measures the same place by another mode (walk + drive to school) without a second pin.
- **Areas (the simplified bubble report, 2026-10-15):** add `areas` to `client.json` when the client is choosing between neighborhoods: `[{"name", "summary", "center": [lat, lon] only for an area with no homes}]`, and each listing's `area` must match a name. The page then opens with an Areas row: "All areas" plus one card per area (homes, rent range, quickest time to the first anchor, a places-only summary). A tap filters the list and the pins (together with `filters`) and frames the map; area names sit on the map. `build.py` refuses an area summary that describes people or rates schools (the full tool's fair-housing word list), a home whose area isn't listed, and an empty area without a center. No bubbles, no score rings. When the first anchor is a walk and the same place is also measured by car, a walk over 30 minutes falls back to the drive (area cards), is left off the home's card, and reads "Over 30 min walk" in Compare (Jensen, 2026-10-15).
- **Shape anchors (2026-10-15, Kevin v5):** an anchor can be a line or an area instead of a point. `{"shape": {"osmName": "Lincoln Road"}}` = every OSM way named exactly that (a street or pedestrian mall); `{"shape": {"osm": "beach", "minLat": 25.763}}` = the closed `natural=beach` polygons. Needs `data/osm-raw.json` (`fetch_osm.py` over a bbox that covers it). `process.py` measures each home to the nearest point and stores it (`measures[id].point[key]`); `fetch_routes.py` routes there; the page draws the line (anchor colour) or the sand instead of a pin. Up to 5 anchors have colours (`--a0`…`--a4`).
- **One pin per building:** give each listing a `building` key. The map then shows one pin per building with its name and the number of its units shown (names hide when zoomed out so nearby buildings don't cover each other); a building with several units opens a chooser. Without `building`, units keep the side-by-side pins.
- **Filter groups:** `"filterGroups": [{"key": "beds", "label": "Bedrooms", "field": "beds", "options": [{"key": "all", "label": "All"}, {"key": "1", "label": "1 bed"}, {"key": "2", "label": "2 beds"}]}, {"key": "sofi", "label": "South of Fifth", "field": "sofi", "toggle": true}]`. Every listing must carry each group's field (`build.py` refuses otherwise). Groups combine with each other, with `filters` and with `areas`; an option with no homes shows "(0)" disabled; each viewer's choice is remembered.
- **`"showLongWalks": true`** shows every walk in full ("1 h 45 min walk"); without it a walk over 30 min reads "Over 30 min walk" (Jensen's rule for the walk to school).
- **Buildings layout (2026-10-15, Kevin & James):** `"layout": "buildings"` (with `"mode": "anchors"`). The page is a market report: notes box, filters (bedrooms, area) and the home count on top; one section per group (`sections`, each with its own OneHome link); in each section, each building once (its walking tiles to every place, and its facts from `data/buildings.json`: gym, guest access, entrance, building, beach), with its units underneath as one-line rows (unit, beds/baths/sq ft, price) that open to the photo, details and Interested / Pass; the map with one bubble per building at the bottom (tap = routes + "See its homes"). Uses `template-buildings.html`. Cards need `spec`, `rentText`, `rentSub`, `details`.
- **`"noFlags": true`:** no red/gold judgement and neutral pins; every option on equal footing (Andrew: "we are basically giving him a market report"). Confirm tags on unverified facts stay. Homes above the range say so plainly in `rentSub` ("shown for market reference").
- **`"maxWalkMin": 20`:** a walk longer than that is shown as the distance in miles ("4.6 mi away by street"), never as a walking time (Andrew, 2026-10-15: a 2-hour walk "looks like the software is dumb"). Works in both templates.
- **`"noMover": true`:** no animated walker/car; routes still draw on tap. **`"notes"`:** a short notes box at the top (keep it to one paragraph so the first building shows on the first phone screen).
- The page: sort by each anchor and by rent; open card = photo, a time row per anchor, the `prio` rows, flags, Interested / Pass / Compare, then the details; tap = a route to every anchor (the first drawn on top) with a car driving the first; chips for each anchor and parks.

## Limits

- Photos are embedded in the page, so it grows to about 1 MB with 6 photos (limit 16 MB).
- Route times are the routing service's estimates for an average walker or rider, from the building's address point.
- Straight-line distances are so they come out shorter than the shortlist's routed figures (Costa Brava: 1.2 mi straight vs 1.7 mi by route). The page says so.
- The priority set is beach / path / bike / one place type. Another priority (a park, a gym, a train stop) needs a new layer in `process.py`, `build.py` and the template; that's a tool session, not a client run.
- Units in the same building share one address point, so their distances are the same.

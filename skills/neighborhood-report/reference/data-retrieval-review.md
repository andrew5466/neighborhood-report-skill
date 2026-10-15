# Data retrieval: Algorithm Review

Andrew (2026-10-15): "Let's create an optimized system for the data retrieval. Run it through the algorithm. What would it take to cut the time to launch and token usage in half?" Run through The Process Algorithm — Five Steps, measured on today's **Crash Pad Sobe** build (17 homes, 7 buildings, 5 OneHome groups).

## Baseline: how the data was gathered today (measured where a number exists)

| Step | How | Time | Tokens |
|---|---|---|---|
| Read 3 new OneHome links to learn the units | Browser, page text | ~1 min | ~6k (page text) |
| Unit facts for 11 homes + building facts + Catch address | Research helper agent (WebSearch/WebFetch, 58 tool calls) | **5.4 min** | **159k** (agent) |
| First photos (Kevin, 6 homes) | Research helper agent | **8.9 min** | **134k** (agent) |
| Geocode 4 places | Nominatim script | ~6 s | <1k |
| Walking routes, 28 | OSRM script, no cache | 42 s | <1k |
| Card facts for 17 homes | Hand-written into a data script by the main session | ~10 min | ~15-20k output (estimate) |
| Matrix recheck + 7 per-building OneHome links | ~40 browser actions, screenshots; one frozen tab | ~15 min | ~40-60k (estimate, screenshots) |
| Page checks | 6-8 browser rounds with screenshots | ~10 min | ~30-40k (estimate) |

The research agents alone were **293k tokens and 14 minutes**. The rest of the data work was roughly 100k tokens of browsing and hand-typing. Main-session figures are estimates; the agent figures are from their run reports.

## 1. Question every requirement

| "We need…" | Questioned | Verdict |
|---|---|---|
| A research agent to read listing pages | The pages carry structured data (JSON-LD), a features list and the remarks; one script can read them | ❌ Not needed for unit facts |
| A separate agent to find photo URLs | The listing page's JSON-LD / og:image is the first photo | ❌ Not needed |
| Read every OneHome link to learn the units | The units are MLS numbers; Matrix returns all of them in one grid | ❌ Only when Andrew sends links without MLS numbers |
| Geocode each home | The listing page has latitude/longitude | ❌ Geocode only places (restaurants) and homes without coordinates |
| Re-research buildings and places for every client | Carillon, the Presidential, Mila, Catch recur | ❌ Research once, store, reuse |
| Screenshots to check data | The data checks are counts and values | ❌ JavaScript assertions; one screenshot for looks |
| Matrix for status, price and rent period | Bex doesn't show rented/pending; Matrix does | ✅ Keep, in one grid read |

## 2. Delete

- The listing-research helper agent → `fetch_listings.py`.
- The photo-URL helper agent → `fetch_listings.py` writes `photo-sources.json`.
- Re-geocoding homes → listing-page coordinates.
- Repeat research of known buildings and places → `db/buildings.json`, `db/places.json`.
- Screenshot loops for data checks → `status.py` + JS assertions.

## 3. Speed up (cycle time)

- One cache for every network call (`fetchcache.py`): routes **42 s → 0.08 s** on a rerun; listing pages 31 s → 0.1 s within 2 days.
- Matrix grid in **2 calls** (~1k characters for 17 homes) instead of screenshots.
- Per-building OneHome shares: tick each row's checkbox (the "All" link doesn't always register), use the dialog's input value for the URL, one new tab if a dialog freezes.

## 4. Simplify

- One record per listing, shared across clients: `db/listings/<MLS>.json` with a `matrix` block (status, price, period, furnished, style→lease kind) and a `bex` block (page facts, remarks, lease phrases, photo, coordinates), each dated.
- The client folder holds only client choices: who, which homes, which places, groups, copy.
- Every script prints at most one line per home; nobody reads raw pages or JSON into the conversation.

## 5. Automate (last)

- `lite.py`: listings → card drafts → distances → routes → photos → build → status, in one command. **Measured rerun: 2.7 s**, and the page came out byte-identical to the published version.
- `draft_cards.py`: every card's facts drafted from Matrix + listing data (17 homes in 0.03 s). On its first run it surfaced a fact the hand-written cards missed: Presidential #903's remarks say "Short term rentals and subleases are strictly prohibited."

## What it takes to cut time to launch and tokens in half

**Data retrieval is more than halved.** For Crash Pad Sobe it falls from about 390k tokens and 45 minutes to about 10k tokens and 5 to 8 minutes.

| | Before (today) | With the new system |
|---|---|---|
| Unit facts + photos | 2 agents, 293k tokens, 14 min | `fetch_listings.py`: ~40 s first run, ~2k tokens of printed lines |
| Matrix status/price/period | screenshots, ~15k tokens | 2 grid calls, ~1.5k tokens |
| Card facts | hand-typed, ~15-20k output tokens, ~10 min | `draft_cards.py`, then edit only the exceptions (~2-4k tokens) |
| Routes | 42 s | cached: 0 s on reruns and for known buildings |
| Building facts / places | re-researched | reused from `db/` (research only new buildings, with a short, named list) |
| Data checks | screenshot rounds | `status.py` (one screen) + one visual check |

**For the whole launch to halve,** four things must hold. Each is now in the skill:
1. **Start from MLS numbers.** Ask Andrew for MLS numbers, or take them from one Matrix grid, rather than reading OneHome pages.
2. **One helper agent at most,** and only for buildings not in `db/buildings.json`, with the exact fields to find. Never for unit facts or photos.
3. **One look at the page.** JS assertions for counts and widths, then a single screenshot, not loops.
4. **Make OneHome shares only when asked,** using the row-checkbox procedure.

What stays manual: Andrew's choices (which homes, which places, the groups), wording he cares about, and anything sent to a client.

## What changed in the kit (2026-10-15)

`scripts/fetchcache.py`, `scripts/fetch_listings.py`, `scripts/matrix_grid.js`, `scripts/ingest_matrix.py`, `scripts/draft_cards.py`, `scripts/status.py`, `scripts/lite.py`; `fetch_routes.py` now cached; `db/places.json` (Mila, Catch, Carbone, the Delano, Lincoln Road, the beach) and `db/buildings.json` (7 buildings) seeded.

## Pass 2 (2026-10-15, later): what's left after the fast path

The process was saved as an SOP first (SOP — Client Neighborhood Map (Map Lite)), then run through the algorithm again. After pass 1, the remaining costs on Crash Pad Sobe were these (estimates, from this session):

| Remaining cost | Tokens | Time |
|---|---|---|
| Research agent for new buildings | 40-80k | 5-10 min |
| Per-building OneHome shares (7 buildings) | 15-25k | ~10 min |
| client.json written by hand | ~3k | 3-5 min |
| Page checks in the browser (JS assertions + screenshot) | ~3k | 1-2 min |
| Matrix grid | ~2.5k | 1 min |
| Card exceptions edited by hand | 3-5k | 2-4 min |

**1. Question.** Does a new building need research? Mostly no: the listing site already has a page for most buildings, linked from each unit page. Does the client file need writing by hand? Only the wording; everything else follows from the MLS numbers, the groups and the places.

**2. Delete.** The research agent for building facts goes when the listing site has a building page. Hand-typing listings.json and the client file both go.

**3. Speed up.** Photos are now kept when the URL hasn't changed (15 kept, 0 downloaded on a rerun). The page check moved from the browser to a script, so the browser is used for one look only.

**4. Simplify.** `lite.py` now also merges card drafts on a first run (no data/cards.json yet), fetches building facts and checks the page, so a new client takes one command after the starter.

**5. Automate.** The new scripts, all measured on Crash Pad Sobe:

| Script | Replaces | Measured |
|---|---|---|
| `fetch_buildings.py` | the building research agent (40-80k tokens) | 2.8 s first fetch, about 1.5k tokens of printed lines; 6 of 7 buildings found. 951 Jefferson has no building page, so a small building like it still needs a short look |
| `new_client.py` | client.json + listings.json by hand | 0.04 s. From the 17 MLS numbers, the 5 groups and 4 places it rebuilt the same 7 buildings (Carillon towers matched by street address), the same filters and the same lede as the hand-built file. Only the unit ids differ in style (`carillon-south-1106` vs `carillon-1106`) |
| `check_page.py` | browser JS assertions | 0.05 s, offline: homes on the page, prices, photos, building facts, OneHome links are shares, walks over 20 minutes, the client's banned words (`bannedWords` in client.json) |
| `fetch_photos.py` (reuse) | 15 downloads on every run | 0 downloads on a rerun |

**Result.** A rerun of Crash Pad Sobe now takes **0.8 s** (was 2.7 s). A new client, from scratch, ran: starter 0.04 s, then `lite.py` in about 45 s (routes are the only real wait: 42 s for 28 new walks, then cached). Its page passed `check_page.py` with nothing written by hand except the title and groups.

The new path for a client is: Andrew's MLS numbers, groups and places → `new_client.py` → Matrix grid (2 calls) → `lite.py` → edit the lede, notes and card exceptions → one look in the browser → publish.

**Still manual, on purpose:** Andrew's choices and wording, the Matrix grid (his signed-in browser), card exceptions that change the brief (e.g. Presidential #903's "Short term rentals and subleases are strictly prohibited"), and the one look at the page.

**Next candidates (not built):**
- Per-building OneHome shares from one results page: search all MLS numbers once and tick each building's rows in turn, instead of one search per building. Expected to save about half of the 10 minutes. It needs a careful Matrix test, because unticking has to register too.
- Building coordinates in `db/buildings.json`, so a new client's routes come from the cache when the building is already known (today they're keyed to the listing page's coordinates, so a new client re-fetches them).

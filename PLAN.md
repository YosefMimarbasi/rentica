# Rentaca — Website Plan

A planning document for the Rentaca web app. Grounded in the data we actually
have: **1,099 units across 499 buildings** (92 multi-unit), a building-centric
model with images, floorplans, ratings/reviews on 73 buildings, coordinates on
425 buildings, and monthly rent on 784 units (median $1,800; $998/person).

No implementation here — this is the product/architecture plan.

---

## 1. Positioning: why this beats CUAPTS

CUAPTS is a flat directory of building reviews. Our structural advantage is the
**building → units model** we already built. The pitch:
*"See every unit in every building — with real photos, floorplans, current
rent, and reviews — in one place."*

| CUAPTS lacks | Rentaca has |
|---|---|
| Units within a building | 92 multi-unit buildings with all units linked |
| Many photos / floorplans | 92% have photos, building galleries shared across units, 67 floorplans |
| Pricing | 784 rents (median $1,800; $998/person) with honest `price_basis` labels |
| Owner site / contact | landlord company + website + phone (where available) |
| Aggregation | 15 sources unified, deduped, geocoded |

---

## 2. Data model (the backbone)

Two JSON collections the pipeline already produces:

- **Building** = address, area (Collegetown / Downtown / North Campus / West
  Campus / Other), coordinates, contact/owner, aggregate rating + reviews,
  travel_times, images, `units[]`.
- **Unit** = beds, baths, sqft, price (+ `price_basis`), availability, source,
  url, images.

Everything keys off `building_id` — that is what makes "what else is in this
building?" possible, which CUAPTS cannot do.

---

## 3. Information architecture (pages)

1. **Home / Search** — map + filterable results (the primary surface).
2. **Building page** — the hero page: gallery, floorplans, all units table,
   rating + reviews, amenities, owner/contact, map with travel times to
   Cornell / Ithaca College, "similar nearby."
3. **Unit detail** (or expandable row within building) — unit photos,
   floorplan, rent, per-person, availability, link to original source listing.
4. **Map view** (full-screen) — pins colored by price/person, clustered by area.
5. **Compare** — side-by-side of 2–4 saved buildings/units.
6. **Saved / shortlist** — localStorage favorites (no login needed for MVP).
7. **About / methodology / data accuracy** — sources, freshness, what
   `price_basis` means.

---

## 4. Page-by-page features

### Home / Search
- Split layout: filters + result cards (left/top), live map (right).
- Filters tied to real fields: max price/person, total rent range,
  beds (Studio–6+), baths, distance to Cornell, area, amenities
  (parking / laundry / AC / furnished / pets), has-photos, has-floorplan,
  has-reviews, availability date.
- Sort: price/person ↑, total rent ↑, distance to Cornell, rating ↓, beds,
  newest.
- Each card: primary photo, $/person + total, beds/baths, area, distance,
  rating stars, "N units in building" badge.

### Building page (the differentiator)
- Photo gallery (own + building-shared images, deduped) + floorplan viewer.
- **Units table**: every unit with beds/baths/sqft/rent/$person/availability/
  source link — sortable. This is the "what's in this building" view CUAPTS
  can't show.
- Rating + full reviews (the 73 buildings with CUAPTS reviews).
- Amenities chips; owner / management company + website + phone.
- Map with travel times (we have travel_times on 254 buildings) to Cornell & IC.
- Trust row: data sources, last updated, `price_basis` note on any inferred
  rents.

### Map view
- Pins by $/person (color scale), Cornell / IC markers, area clustering,
  click → building preview card.

---

## 5. Trust & data-quality UX (our credibility)

- Badge each price: **"Listed"** (scraped) vs **"Est. from building"** (our
  `price_basis` fill) — never hide inference.
- "Last updated" per building; source attribution
  (Craigslist / AppFolio / CUAPTS / owner site) with a link to the original.
- Gracefully handle missing fields (no photo → placeholder; no rent →
  "Contact for price" with owner link) rather than blank.

---

## 6. Tech architecture (recommended)

The data is static JSON and deployment is already via GitHub:

- **MVP: static site.** The existing `index.html` is the seed. At build time,
  pre-generate per-building JSON + a slim search index; host on
  **GitHub Pages / Netlify / Vercel**. Zero backend, free, fast.
  Client-side filtering handles ~1,100 records easily.
- **Map**: Leaflet + free tiles (already in the prototype).
- **Search**: client-side (Fuse.js-style) over a generated index; no server
  needed at this scale.
- **Images**: hotlinked now; **Phase 2** → cache/proxy to our own storage
  (some source URLs are temporary/expiring — a real risk).
- **When to add a backend**: only for user accounts, cross-device saved
  searches, alerts, or write features (user reviews). Then a thin API + DB
  (e.g. Supabase / Postgres) over the same model.

---

## 7. Data pipeline / freshness

- Keep the existing build chain:
  scrapers → `apartments.json` → `unify.py` → `consolidate_images.py`.
- Schedule a **weekly re-scrape** — rent/availability go stale fast in a rental
  market. Surface "last updated" so users trust it.
- Re-run geocoding to close the coordinates gap (425/499 buildings) before
  launch — map quality depends on it.

---

## 8. Build phases

- **Phase 0 (pre-launch data):** finish geocoding; attach owner websites
  (0% → ~60%, from data already pulled); re-validate rents.
- **Phase 1 (MVP):** static Home + Map + Building pages, filters/sort,
  shortlist. Ship it.
- **Phase 2:** compare, image caching/proxy, floorplan viewer polish,
  "similar nearby," better mobile.
- **Phase 3:** accounts, saved searches, price-drop / availability alerts,
  user-submitted reviews & photos (become a CUAPTS replacement, not just an
  aggregator).

---

## 9. Risks to design around

- **Image link rot** — many source image URLs expire; cache them (Phase 2)
  before relying on them.
- **Price staleness** — rentals move weekly; freshness labeling + re-scrape
  cadence are essential.
- **Legal / ToS** — aggregating + linking to source is lower-risk; re-hosting
  others' photos and reviews carries IP/ToS exposure. Keep a clear "data from
  public sources, verify with landlord" disclaimer + source attribution.
- **Coverage honesty** — 71% rent / 14% reviews coverage; the UI should make
  partial data feel intentional, not broken.

---

## 10. First decisions before any build

1. **Static vs backend** — recommend static for MVP.
2. **Image hosting** — plan to cache early (link rot).
3. **Scope of "reviews"** — display CUAPTS reviews only (read), or accept user
   reviews (requires accounts + moderation).

---

## Current data snapshot (as of this plan)

- Units: **1,099** across **499 buildings** (92 multi-unit, 407 single).
- With photos: **~92%**; floorplans: **67**; building galleries shared to all
  units in a building.
- With monthly rent: **784** (median $1,800; $998/person), each tagged
  `price_basis` (listed vs building-derived).
- With coordinates: **425 buildings**; travel times: **254 buildings**.
- With ratings/reviews: **73 buildings** (from CUAPTS).
- Areas: Collegetown 150, Downtown 45, West Campus 25, North Campus 14,
  Other 20, unclassified 245.
- Sources (15): craigslist, cuapts, modernliving, ithacarenting, ppmhomes,
  travishyde, lambrou, csp, ithacaestates, strawberry, ridgetop, largebuildings,
  demosjohnny, ithacalivingsolutions, moll.

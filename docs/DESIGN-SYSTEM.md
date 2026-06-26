# Rentaca — Minimalist Design System & Handoff

A restrained, minimalist re-skin of the Rentaca Ithaca-rental site:
**white canvas · near-black ink · Cornell Red as the single primary accent**
(used sparingly). Generous whitespace, hairline borders, flat surfaces, quiet
motion. Applied directly to the production static site — the running pages are
the high-fidelity deliverable.

---

## 1. Page → template mapping

| Template | Page | Notes |
|---|---|---|
| **Homepage** | `index.html` | Quiet white hero (one red accent word), feature cards, hairline filter toolbar, Leaflet map, card grid, CTA, footer |
| **Article** | `about.html` | Editorial prose: red kicker, headline, stat grid, body, callout |
| **Program page** | `building.html` | Gallery, units table, reviews, sticky contact/price/map side panel |

---

## 2. Color tokens (Cornell palette, minimal use)

Source of truth: **`assets/css/tokens.css`** + **`assets/tokens.json`**.
`app.css` imports `tokens.css` first.

| Token | Hex | Role |
|---|---|---|
| `--cornell-red` | `#B31B1B` | **Single primary accent** — CTA, links, active state, price/rating, focus, brand dot |
| `--deep-maroon` | `#6E0F0F` | Red hover state only |
| `--ink` | `#1A1A1A` | Primary text (17:1 on white) |
| `--gray-70` | `#595959` | Muted text (AA, 7:1) |
| `--gray-50` | `#8A8A8A` | Secondary / large text |
| `--gray-30` | `#C9C9C9` | Borders |
| `--line-100` | `#ECECEC` | Hairlines |
| `--line-50` | `#F4F4F4` | Faint fills / hover wells |
| `--cornell-white` | `#FFFFFF` | Canvas + surfaces |

**Accent discipline:** Cornell Red is intentionally rare. It appears on the
primary CTA, text links, the active filter chip, price/rating figures, the focus
ring, and the brand `.`. Everything else is white / ink / neutral gray. No
secondary Cornell hues (gold/blue/maroon) in prominent use — that keeps the
minimalism honest.

---

## 3. Accessibility (WCAG 2.1 AA)

| Pairing | Ratio | Result |
|---|---|---|
| Ink on White (body/headings) | 17.4 | ✅ AAA |
| Gray-70 on White (muted) | 7.0 | ✅ AA |
| Cornell Red on White (links) | 6.8 | ✅ AA |
| White on Cornell Red (CTA) | 6.8 | ✅ AA |
| Gray-50 on White | 3.5 | AA-large only — used for secondary/large text + borders, never small body |

- Skip link → main content on every page (`#main` / `#root`).
- Semantic landmarks: `<nav aria-label="Primary">`, `<main>`, `<footer>`, map
  `<section aria-label>`, `aria-current="page"` on active nav item.
- `:focus-visible` = 2px Cornell-red outline, 2px offset, everywhere.
- Keyboard: native controls; Escape closes filter sheet; lightbox arrow/Escape.
- `prefers-reduced-motion` disables entrance and near-zeroes transitions.
- Auto dark mode: near-black canvas, white ink, lightened red accent.

---

## 4. Performance checklist

| Item | Status |
|---|---|
| CSS | ~31KB, no build; `tokens.css` + `app.css` only |
| Fonts | Single family (Plus Jakarta Sans), `display=swap`, preconnect |
| Images | All `loading="lazy"` + `onerror` placeholders |
| Card list | 48/page batched + IntersectionObserver infinite scroll |
| Map | Leaflet deferred to end of body; scroll-zoom off |
| **Prod TODO** | Drop the `cdn.tailwindcss.com` + Shoelace autoloader dev CDNs and self-host fonts; minify + inline critical CSS for the <2.5s/3G target |

---

## 5. Component notes (class contract preserved)

Restyled, never renamed — `home.js` / `building.js` render against these:
`.nav .btn .card .hero .searchbar .toolbar .chip .sheet .field .seg .units
.gallery .rating-big .catbar .panel .footer .lp-feature .prose .statcard`.

Minimal treatments: thin-border nav, white hero with one red accent word, flat
hairline-bordered cards with a single quiet hover lift (no colored/offset
shadows, no rotating accents), light-header units table, red-fill category bars,
quiet single-rule footer.

### Copy-ready primary button
```css
.btn--primary { background: var(--accent); color: #fff; border-radius: 980px; padding: 11px 22px; font-weight: 600; }
.btn--primary:hover { background: var(--accent-hover); transform: translateY(-1px); }
```

---

## 6. Dev guide

```bash
cd rentaca && python -m http.server 8000   # http://localhost:8000
```
Edit colors in `assets/css/tokens.css` only. Class names are a JS contract —
restyle freely, don't rename. JS-level colors live in `home.js ppColor()` +
Leaflet markers and `building.js initMap()`, all mapped to the minimal scale.

---

## 7. Acceptance checklist

- [x] White/black base with Cornell Red as the sole, sparing accent.
- [x] Responsive desktop/tablet/mobile (fluid clamp + 1024/900/760/640/380 breakpoints).
- [x] Token files (`tokens.css` + `tokens.json`) drive all components.
- [x] A11y: skip links, landmarks, focus rings, keyboard, reduced-motion; AA verified.
- [x] Minimalist aesthetic: whitespace, hairlines, flat surfaces, quiet motion.
- [x] Verified in-browser: 0 JS errors across homepage / program / article; data intact.
- [ ] Perf hardening for <2.5s/3G: drop Tailwind/Shoelace CDNs, self-host fonts, minify+inline critical CSS.

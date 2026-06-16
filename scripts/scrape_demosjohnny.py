"""DemosJohnny Collegetown Rentals scraper (Wix, via Playwright).

Wix lazy-loads images, so we render each property page. Property URLs are
linked from the home page (e.g. /105-eddy-street). Each page gives the
address (slug), bed/bath text, and a Wix image gallery.
"""
import json
import re
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "raw" / "demosjohnny_raw.json"
BASE = "https://www.demosjohnnycollegetownrentals.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

SLUG_RE = re.compile(r"^/(?:copy-of-)?\d{1,4}-[a-z0-9-]+(?:street|st|ave|avenue|"
                     r"road|rd|place|pl|drive|dr|lane|blair|eddy|linden|cook|"
                     r"hudson|college|dryden|highland|catherine|quarry)$", re.I)


def slug_to_address(slug):
    s = slug.strip("/").replace("copy-of-", "").replace("-", " ")
    return re.sub(r"\s+", " ", s).title().strip() + ", Ithaca, NY"


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(user_agent=UA, ignore_https_errors=True,
                            viewport={"width": 1366, "height": 1200})
        pg = ctx.new_page()
        pg.goto(BASE + "/", timeout=45000, wait_until="domcontentloaded")
        pg.wait_for_timeout(2500)
        hrefs = pg.eval_on_selector_all("a", "els => els.map(e => e.getAttribute('href')).filter(Boolean)")
        slugs = []
        seen = set()
        for h in hrefs:
            m = re.match(r"https?://[^/]+(/[^?#]+)", h) if h.startswith("http") else (h,)
            path = (m.group(1) if hasattr(m, "group") else h) if h else ""
            if path and SLUG_RE.match(path) and path not in seen:
                seen.add(path)
                slugs.append(path)
        print(f"found {len(slugs)} property pages")

        listings = []
        for i, slug in enumerate(slugs, 1):
            url = BASE + slug
            try:
                pg.goto(url, timeout=45000, wait_until="domcontentloaded")
                pg.wait_for_timeout(2500)
                # scroll to trigger lazy images
                for _ in range(4):
                    pg.mouse.wheel(0, 2000)
                    pg.wait_for_timeout(600)
                # Visible text only -- avoids the Wix nav menu's bedroom-category
                # links (A_4BED, H_13BED, ...) that poison a raw-HTML parse.
                text = pg.inner_text("body")
                bed_hits = [int(x) for x in re.findall(r"(\d+)\s*[- ]?\s*bedroom", text, re.I)]
                beds = bed_hits[0] if bed_hits else 0
                bath_hits = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*[- ]?\s*bath", text, re.I)]
                baths = bath_hits[0] if bath_hits else 0
                baths = int(baths) if float(baths).is_integer() else baths
                pm = re.search(r"\$\s*([\d,]{3,5})", text)
                price = int(pm.group(1).replace(",", "")) if pm else 0
                desc = ""
                dm = re.search(r"(This[^.]{20,200}\.)", text)
                if dm:
                    desc = dm.group(1).strip()
                imgs = pg.eval_on_selector_all(
                    "img", "els => els.map(e => e.src || e.getAttribute('data-src')).filter(Boolean)")
                imgs = [u for u in imgs if "wixstatic.com/media" in u and "logo" not in u.lower()]
                seen_i, ded = set(), []
                for u in imgs:
                    k = re.sub(r"/v1/.*$", "", re.sub(r"[?#].*$", "", u))
                    if k in seen_i:
                        continue
                    seen_i.add(k)
                    ded.append(u)
                listings.append({
                    "id": slug.strip("/"),
                    "title": slug_to_address(slug),
                    "url": url,
                    "description": desc,
                    "address": slug_to_address(slug),
                    "pricing": {"monthly_rent_total": price, "rent_period": "monthly"},
                    "housing": {"bedrooms": beds, "bathrooms": baths, "sqft": 0},
                    "amenities": {},
                    "coordinates": {},
                    "images": ded[:25],
                })
                print(f"  [{i}/{len(slugs)}] {slug_to_address(slug)[:40]:42} {beds}BR imgs={len(ded)}")
            except Exception as e:
                print(f"  ERR {slug}: {str(e)[:50]}")
        b.close()

    OUT.write_text(json.dumps(listings, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {len(listings)} listings -> {OUT}")


if __name__ == "__main__":
    main()

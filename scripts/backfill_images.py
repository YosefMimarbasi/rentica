"""Backfill full image galleries for sources that only captured 1 image.

- craigslist: detail pages embed the gallery as JSON ("url":"...600x450.jpg")
  in a <script>; the original scraper only saw the single visible <img>.
- lambrou: Squarespace gallery; images are in the page JSON / <img> srcset.

Resumable via a per-source cache. Polite delay. No API keys.
"""
import json
import re
import time
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "apartments.json"
CACHE = ROOT / "data" / "image_backfill_cache.json"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "ignore")


def craigslist_images(html):
    # Full-size gallery URLs from the embedded imgList JSON, deduped by image id.
    urls = re.findall(r'"url":"(https://images\.craigslist\.org/[^"]+)"', html)
    if not urls:
        urls = re.findall(r'https://images\.craigslist\.org/[^"\s\\]+\.jpg', html)
    seen, out = set(), []
    for u in urls:
        u = u.replace("\\/", "/")
        # prefer the 1200x900 if present, else keep as-is; dedupe by id
        key = re.sub(r"_\d+x\d+", "", u)
        if key in seen:
            continue
        seen.add(key)
        out.append(u)
    return out


def lambrou_images(html):
    urls = re.findall(r'https://images\.squarespace-cdn\.com/[^"\s\\)]+', html)
    seen, out = set(), []
    for u in urls:
        u = u.split("?")[0]
        if u in seen or u.endswith(".svg"):
            continue
        seen.add(u)
        out.append(u)
    return out[:30]


def ithacaestates_images(html):
    # Duda/cdn-website hosted; property photos are *-1920w.jpg under lirp.cdn-website.
    urls = re.findall(r'https://lirp\.cdn-website\.com/[^"\s\\)]+\.(?:jpg|jpeg|png)', html)
    seen, out = set(), []
    for u in urls:
        # keep the largest variant; dedupe by the photo stem (before -<width>w)
        stem = re.sub(r"-\d+w\.(jpg|jpeg|png)$", "", u)
        if any(k in u.lower() for k in ("logo", "icon", "favicon", "white")):
            continue
        if stem in seen:
            continue
        seen.add(stem)
        out.append(u)
    return out[:40]


EXTRACTORS = {
    "craigslist": craigslist_images,
    "lambrou": lambrou_images,
    "ithacaestates": ithacaestates_images,
}


def main(source, limit=None):
    db = json.load(open(DB, encoding="utf-8"))
    cache = json.load(open(CACHE, encoding="utf-8")) if CACHE.exists() else {}
    extract = EXTRACTORS[source]

    targets = [l for l in db if l["source"] == source
               and l.get("listing_info", {}).get("url")
               and len(l.get("listing_info", {}).get("images", []) or []) <= 1]
    if limit:
        targets = targets[:limit]
    print(f"{source}: backfilling {len(targets)} listings ({len(cache)} cached)")

    updated = 0
    for i, l in enumerate(targets):
        url = l["listing_info"]["url"]
        if url in cache:
            imgs = cache[url]
        else:
            try:
                imgs = extract(fetch(url))
            except Exception as e:
                imgs = []
                print(f"  fail {url}: {e}")
            cache[url] = imgs
            time.sleep(0.5)
            if (i + 1) % 25 == 0:
                print(f"  fetched {i + 1}/{len(targets)}")
                json.dump(cache, open(CACHE, "w", encoding="utf-8"), indent=2)
        if imgs and len(imgs) > len(l["listing_info"].get("images", []) or []):
            l["listing_info"]["images"] = imgs
            updated += 1

    json.dump(cache, open(CACHE, "w", encoding="utf-8"), indent=2)
    json.dump(db, open(DB, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    tot = sum(len(v) for v in cache.values())
    print(f"{source}: updated {updated} listings | {tot} images cached")


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "craigslist"
    lim = int(sys.argv[2]) if len(sys.argv) > 2 else None
    main(src, lim)

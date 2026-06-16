"""Consolidate and propagate images across the building model.

Goal (per user request): every listing should carry
  - its own matched room/unit images          -> listing_info.images
  - the rest of the building's shared gallery   -> listing_info.images_from_building
    (exterior, amenities, common areas, other units)
  - any floorplans available for the building   -> listing_info.floorplan_images

Handles source quirks:
  - RentManager (ithacarenting) serves the same photo at many URLs with a
    fresh encrypted FKey each request -> dedup by FKey and hard-cap.
  - AppFolio serves small/medium/large/original variants of one image -> dedup
    to a single variant.
  - Craigslist serves _600x450 / _1200x900 size suffixes -> dedup by image id.

Caps keep the DB and UI sane (no 300-image units).
"""
import json
import re
import urllib.parse as up
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "apartments.json"

OWN_CAP = 40            # max own images per listing
BUILDING_CAP = 40       # max shared building images added per listing
POOL_CAP = 60           # max images kept in a building's shared pool
RM_PER_UNIT_CAP = 12    # RentManager photos are low-variety; cap hard


def dedup_key(url: str) -> str:
    """Stable identity for an image across size/variant/token noise."""
    u = str(url)
    p = up.urlparse(u)
    host = p.netloc.lower()
    if "rentmanager.com" in host:
        # FKey is the per-image (per-request) token; it's the only id we have.
        q = up.parse_qs(p.query)
        fkey = (q.get("FKey") or q.get("fkey") or [""])[0]
        return "rm:" + fkey[:32]
    if "appfolio.com" in host:
        # .../images/<uuid>/large.png  -> key on the uuid
        m = re.search(r"/([0-9a-f-]{16,})/", u)
        if m:
            return "af:" + m.group(1)
    # craigslist + generic: strip size suffix and query
    base = re.sub(r"_\d+x\d+", "", u)
    base = re.sub(r"[?&].*$", "", base)
    return base


def dedup(urls, cap=None):
    out, seen = [], set()
    for u in urls:
        if not u:
            continue
        k = dedup_key(u)
        if k in seen:
            continue
        seen.add(k)
        out.append(u)
        if cap and len(out) >= cap:
            break
    return out


def li(l, key):
    return l.get("listing_info", {}).get(key, []) or []


def main():
    db = json.load(open(DB, encoding="utf-8"))

    # --- 1. clean each listing's own images (dedup + cap) ---
    for l in db:
        info = l.setdefault("listing_info", {})
        own = li(l, "images")
        cap = RM_PER_UNIT_CAP if l.get("source") == "ithacarenting" else OWN_CAP
        info["images"] = dedup(own, cap)

    # --- 2. build per-building shared pool + floorplans ---
    by_bld = defaultdict(list)
    for l in db:
        bid = l.get("building_id")
        if bid:
            by_bld[bid].append(l)

    pool_imgs, pool_fps = {}, {}
    for bid, units in by_bld.items():
        imgs, fps = [], []
        for u in units:
            imgs.extend(li(u, "images"))
            fps.extend(li(u, "floorplan_images"))
        pool_imgs[bid] = dedup(imgs, POOL_CAP)
        pool_fps[bid] = dedup(fps, 20)

    # --- 3. assign shared building images + floorplans to every unit ---
    stats = {"got_building_imgs": 0, "filled_from_zero": 0, "got_floorplans": 0}
    for l in db:
        info = l["listing_info"]
        bid = l.get("building_id")
        own = info["images"]
        own_keys = {dedup_key(u) for u in own}

        shared = [u for u in pool_imgs.get(bid, []) if dedup_key(u) not in own_keys]
        shared = shared[:BUILDING_CAP]
        info["images_from_building"] = shared
        if shared:
            stats["got_building_imgs"] += 1
        if not own and shared:
            stats["filled_from_zero"] += 1

        fps = [u for u in pool_fps.get(bid, []) if u not in info.get("floorplan_images", [])]
        if fps or li(l, "floorplan_images"):
            merged = dedup(li(l, "floorplan_images") + fps, 20)
            info["floorplan_images"] = merged
            if merged:
                stats["got_floorplans"] += 1

    # --- report ---
    def has_any(l):
        return bool(li(l, "images") or li(l, "images_from_building"))
    total = len(db)
    print(f"listings: {total}")
    print(f"  with own images:            {sum(1 for l in db if li(l,'images'))}")
    print(f"  with building images:       {stats['got_building_imgs']}")
    print(f"  with ANY image:             {sum(1 for l in db if has_any(l))}")
    print(f"  zero-image filled from bld: {stats['filled_from_zero']}")
    print(f"  with floorplans:            {stats['got_floorplans']}")
    print(f"  STILL zero image:           {sum(1 for l in db if not has_any(l))}")

    import sys
    if "--write" in sys.argv:
        json.dump(db, open(DB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print("WROTE", DB)
    else:
        print("(dry run -- pass --write to save)")


if __name__ == "__main__":
    main()

"""For any listing with 0 images, inherit images from building peers.

Many CUAPTS building records have no photos of their own, but other sources
(ithacarenting, modernliving, etc.) have photographed the same building.
Since unify.py groups everything by building_id, we can give an image-less
listing the union of its building-mates' images so every record shows rooms.
Inherited images are tagged separately so the UI can distinguish them.
"""
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "apartments.json"


def main():
    db = json.load(open(DB, encoding="utf-8"))
    by_building = defaultdict(list)
    for l in db:
        bid = l.get("building_id")
        if bid:
            by_building[bid].append(l)

    filled = 0
    for l in db:
        imgs = l.get("listing_info", {}).get("images", []) or []
        if imgs:
            continue
        bid = l.get("building_id")
        if not bid:
            continue
        pool, seen = [], set()
        for peer in by_building[bid]:
            if peer is l:
                continue
            for u in peer.get("listing_info", {}).get("images", []) or []:
                if u and u not in seen:
                    seen.add(u)
                    pool.append(u)
        if pool:
            l["listing_info"]["images"] = pool[:30]
            l["listing_info"]["images_from_building"] = True
            filled += 1

    json.dump(db, open(DB, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    withimg = sum(1 for l in db if l.get("listing_info", {}).get("images"))
    print(f"inherited images for {filled} listings | "
          f"{withimg}/{len(db)} now have images")


if __name__ == "__main__":
    main()

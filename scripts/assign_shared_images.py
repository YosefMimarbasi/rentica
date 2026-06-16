"""Assign property-level (shared) images to every listing in a building.

Within each building (grouped by building_id), an image is treated as a
SHARED / property-level image (gym, pool, exterior, lobby, garage, common
area, drone/aerial, amenities) when EITHER:
  * it appears in the galleries of 2+ distinct units, OR
  * its URL/filename matches an amenity keyword.

Every unit in the building then shows the union of shared images, so common
spaces appear on all listings in that building. Unit-specific photos and the
unit's own floorplan stay first/unique to that unit.

Per listing we write:
  listing_info.floorplan_images  - this unit's floorplan (kept first)
  listing_info.own_images        - photos unique to this unit
  listing_info.shared_images     - property-level images (building-wide)
  listing_info.images            - display gallery = floorplan + own + shared
We also drop the old messy `images_from_building` flag.

buildings.json gets a `shared_images` field per building.
"""
import json
import re
from collections import defaultdict, Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "apartments.json"
BUILDINGS = ROOT / "data" / "buildings.json"

AMENITY_RE = re.compile(
    r"(gym|fitness|pool|exterior|outside|outdoor|aerial|drone|lobby|"
    r"garage|parking|amenit|common|courtyard|patio|rooftop|roof-top|"
    r"clubhouse|club-house|lounge|study|laundry|elevator|entrance|"
    r"building|community|grounds|landscap|bbq|grill|terrace|balcony|"
    r"view|location|resident-center|resident_center)",
    re.I,
)
# floorplan filename hints
FLOOR_RE = re.compile(r"(floor.?plan|floorplan|/fp[-_/]|-fp\.|sitemap|sightmap|"
                      r"\d[bB]\d?[bB]|studio[a-z]?-?v?\d)", re.I)


def is_amenity(url):
    return bool(AMENITY_RE.search(url))


def main():
    db = json.load(open(DB, encoding="utf-8"))

    by_bid = defaultdict(list)
    for l in db:
        bid = l.get("building_id")
        if bid:
            by_bid[bid].append(l)

    building_shared = {}

    for bid, units in by_bid.items():
        # frequency of each image across units (count once per unit)
        freq = Counter()
        for u in units:
            li = u.get("listing_info", {})
            for img in set(li.get("images", []) or []):
                freq[img] += 1

        shared = set()
        for img, c in freq.items():
            if len(units) > 1 and c >= 2:
                shared.add(img)
            elif is_amenity(img):
                shared.add(img)
        building_shared[bid] = shared

        for u in units:
            li = u.setdefault("listing_info", {})
            cur = li.get("images", []) or []
            floor = li.get("floorplan_images", []) or []
            # own = current images that are not shared and not floorplans
            own = [x for x in cur if x not in shared and x not in floor]
            shared_for_unit = [x for x in cur if x in shared]
            # also add building-wide shared images this unit is missing
            for x in shared:
                if x not in shared_for_unit:
                    shared_for_unit.append(x)
            # rebuild display gallery: floorplan(s) -> own -> shared, deduped
            gallery, seen = [], set()
            for grp in (floor, own, shared_for_unit):
                for x in grp:
                    if x and x not in seen:
                        seen.add(x)
                        gallery.append(x)
            li["images"] = gallery
            li["own_images"] = own
            li["shared_images"] = shared_for_unit
            li.pop("images_from_building", None)

    # listings with no building still get clean fields
    for l in db:
        if not l.get("building_id"):
            li = l.setdefault("listing_info", {})
            imgs = li.get("images", []) or []
            floor = li.get("floorplan_images", []) or []
            own = [x for x in imgs if x not in floor]
            # display gallery = floorplan(s) first, then the rest
            gallery, seen = [], set()
            for grp in (floor, own):
                for x in grp:
                    if x and x not in seen:
                        seen.add(x)
                        gallery.append(x)
            li["images"] = gallery
            li["own_images"] = own
            li["shared_images"] = []
            li.pop("images_from_building", None)

    json.dump(db, open(DB, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    # update buildings.json with shared_images
    if BUILDINGS.exists():
        buildings = json.load(open(BUILDINGS, encoding="utf-8"))
        for b in buildings:
            bid = b.get("building_id")
            if bid in building_shared:
                b["shared_images"] = sorted(building_shared[bid])
        json.dump(buildings, open(BUILDINGS, "w", encoding="utf-8"),
                  indent=2, ensure_ascii=False)

    multi = {k: v for k, v in by_bid.items() if len(v) > 1}
    total_shared = sum(len(building_shared[k]) for k in multi)
    bld_with_shared = sum(1 for k in multi if building_shared[k])
    print(f"buildings: {len(by_bid)} | multi-unit: {len(multi)}")
    print(f"multi-unit buildings with shared images: {bld_with_shared}")
    print(f"total shared images across multi-unit buildings: {total_shared}")
    # sample
    for bid, units in sorted(multi.items(), key=lambda kv: -len(kv[1]))[:6]:
        sh = len(building_shared[bid])
        ex = units[0]["listing_info"]
        print(f"  {bid[:32]:34} units={len(units):2} shared={sh:3} "
              f"unit0: fp={len(ex.get('floorplan_images',[]))} "
              f"own={len(ex.get('own_images',[]))} "
              f"shared={len(ex.get('shared_images',[]))} "
              f"total={len(ex.get('images',[]))}")


if __name__ == "__main__":
    main()

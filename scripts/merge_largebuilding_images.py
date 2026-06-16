"""Merge large-building image sets into apartments.json.

luxlofts + ctt: matched by listing URL (those files are keyed per-unit-url).
cayuga + harolds: the image file has one entry per unit IN ORDER (all share
the same page url), so we match positionally within each building group.

For each listing: images = [own floorplan(s)] + [room/gallery photos],
floorplan first.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "apartments.json"
RAW = ROOT / "data" / "raw"


def load(name, default):
    p = RAW / name
    return json.load(open(p, encoding="utf-8")) if p.exists() else default


def by_url(arr):
    return {x["url"]: x for x in arr if x.get("url")}


def merge_unique(*lists):
    seen, out = set(), []
    for lst in lists:
        for u in lst or []:
            if u and u not in seen:
                seen.add(u)
                out.append(u)
    return out


def main():
    db = json.load(open(DB, encoding="utf-8"))
    lux = by_url(load("luxlofts_images.json", []))
    lux_gallery = load("luxlofts_gallery.json", [])
    ctt = by_url(load("ctt_images_partial.json", []))
    ch = load("cayuga_harolds_images.json", [])
    # split cayuga/harolds image entries by building, preserving order
    cay_imgs = [x for x in ch if "cayugaplace" in (x.get("url", "") + str(x.get("images")))
                or "cayugaplace.com" in x.get("url", "")]
    har_imgs = [x for x in ch if "haroldssquare" in x.get("url", "")]

    # collect DB units per building in file order
    cay_units = [l for l in db if l["id"].startswith("largebuildings-cayugaplace")]
    har_units = [l for l in db if l["id"].startswith("largebuildings-haroldssquare")]

    def apply(units, imgrecs):
        n = 0
        for i, l in enumerate(units):
            if i >= len(imgrecs):
                break
            rec = imgrecs[i]
            floor = rec.get("floorplan_images") or []
            rooms = rec.get("images") or []
            merged = merge_unique(floor, rooms, l["listing_info"].get("images", []))
            if merged:
                l["listing_info"]["images"] = merged
                if floor:
                    l["listing_info"]["floorplan_images"] = floor
                if rec.get("rent") and not l.get("pricing", {}).get("monthly_rent_total"):
                    l["pricing"]["monthly_rent_total"] = rec["rent"]
                    br = l.get("housing", {}).get("bedrooms") or 1
                    l["pricing"]["per_person_monthly"] = rec["rent"] // max(br, 1)
                n += 1
        return n

    updated = 0
    updated += apply(cay_units, cay_imgs)
    updated += apply(har_units, har_imgs)

    # luxlofts + ctt by url
    for l in db:
        pid = l["id"]
        url = l.get("listing_info", {}).get("url", "")
        if pid.startswith("largebuildings-luxlofts"):
            rec = lux.get(url, {})
            floor = rec.get("floorplan_images") or rec.get("images") or []
            merged = merge_unique(floor, lux_gallery, l["listing_info"].get("images", []))
            if merged:
                l["listing_info"]["images"] = merged
                if floor:
                    l["listing_info"]["floorplan_images"] = floor
                updated += 1
        elif pid.startswith("largebuildings-collegetownterrace"):
            rec = ctt.get(url, {})
            floor = rec.get("floorplan_images") or []
            rooms = rec.get("images") or []
            merged = merge_unique(floor, rooms, l["listing_info"].get("images", []))
            if merged:
                l["listing_info"]["images"] = merged
                if floor:
                    l["listing_info"]["floorplan_images"] = floor
                if rec.get("rent") and not l.get("pricing", {}).get("monthly_rent_total"):
                    l["pricing"]["monthly_rent_total"] = rec["rent"]
                updated += 1

    json.dump(db, open(DB, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    lb = [l for l in db if l["source"] == "largebuildings"]
    tot = sum(len(l["listing_info"].get("images", []) or []) for l in lb)
    withfp = sum(1 for l in lb if l["listing_info"].get("floorplan_images"))
    noimg = sum(1 for l in lb if not l["listing_info"].get("images"))
    print(f"largebuildings: updated {updated} | {len(lb)} listings, {tot} images, "
          f"{withfp} with floorplan, {noimg} still no-img")


if __name__ == "__main__":
    main()

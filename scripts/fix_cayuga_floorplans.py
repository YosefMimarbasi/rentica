"""Fix over-assigned floorplans for cayuga/harolds units.

The raw file data/raw/cayuga_harolds_images.json has exactly one floorplan
per unit, in unit order. Re-bind each unit's floorplan_images to that single
correct floorplan (positional match within each building group), then the
extra building floorplans become regular shared images instead of being
mislabeled as this unit's floorplan.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "apartments.json"
RAW = ROOT / "data" / "raw" / "cayuga_harolds_images.json"


def main():
    db = json.load(open(DB, encoding="utf-8"))
    raw = json.load(open(RAW, encoding="utf-8"))
    cay_raw = [x for x in raw if "cayugaplace.com" in x.get("url", "")]
    har_raw = [x for x in raw if "haroldssquare.com" in x.get("url", "")]

    cay_units = [l for l in db if l["id"].startswith("largebuildings-cayugaplace")]
    har_units = [l for l in db if l["id"].startswith("largebuildings-haroldssquare")]

    fixed = 0
    for units, recs in ((cay_units, cay_raw), (har_units, har_raw)):
        for i, u in enumerate(units):
            if i >= len(recs):
                break
            fp = recs[i].get("floorplan_images") or []
            li = u["listing_info"]
            if fp and li.get("floorplan_images") != fp:
                li["floorplan_images"] = fp
                fixed += 1

    json.dump(db, open(DB, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"re-bound floorplans for {fixed} cayuga/harolds units")


if __name__ == "__main__":
    main()

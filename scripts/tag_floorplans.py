"""Tag floorplans that weren't flagged, for largebuildings listings.

For CTT and luxlofts units whose floorplan_images is empty but whose first
image is clearly a floorplan (CTT: wp-content/uploads png with a bed/bath
code; luxlofts: the single floor-plan-page image), set floorplan_images.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "apartments.json"

CTT_FP = re.compile(r"collegetownterrace\.com/wp-content/uploads/.+\.(png|jpg|jpeg)$", re.I)
LUX_FP = re.compile(r"luxandlofts\.com/wp-content/uploads/.+\.(jpg|jpeg|png)$", re.I)


def main():
    db = json.load(open(DB, encoding="utf-8"))
    fixed = 0
    for l in db:
        if l["source"] != "largebuildings":
            continue
        li = l.get("listing_info", {})
        if li.get("floorplan_images"):
            continue
        imgs = li.get("images", []) or []
        if not imgs:
            continue
        first = imgs[0]
        pid = l["id"]
        if pid.startswith("largebuildings-collegetownterrace") and CTT_FP.search(first):
            li["floorplan_images"] = [first]
            fixed += 1
        elif pid.startswith("largebuildings-luxlofts") and LUX_FP.search(first):
            li["floorplan_images"] = [first]
            fixed += 1
    json.dump(db, open(DB, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    withfp = sum(1 for l in db if l["source"] == "largebuildings"
                 and l.get("listing_info", {}).get("floorplan_images"))
    print(f"tagged {fixed} more floorplans | largebuildings with floorplan: {withfp}/78")


if __name__ == "__main__":
    main()

"""Merge the three new raw sources into the main apartments.json by id,
preserving all prior enrichment. Then the caller runs unify.py.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from normalize_data import normalize_listing

DB = ROOT / "data" / "apartments.json"
RAW = ROOT / "data" / "raw"
NEW = {
    "ithacarenting": "ithacarenting_raw.json",
    "csp": "csp_raw.json",
    "largebuildings": "largebuildings_raw.json",
}


def main():
    db = json.load(open(DB, encoding="utf-8"))
    existing = {l.get("id") for l in db}
    added_total = 0
    for source, fname in NEW.items():
        raw = json.load(open(RAW / fname, encoding="utf-8"))
        norm = [normalize_listing(l, source) for l in raw]
        added = [l for l in norm if l["id"] not in existing]
        for l in added:
            existing.add(l["id"])
        db.extend(added)
        imgs = sum(len(l.get("listing_info", {}).get("images", [])) for l in added)
        print(f"{source}: +{len(added)} listings, {imgs} images")
        added_total += len(added)
    json.dump(db, open(DB, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"TOTAL added {added_total} | db now {len(db)}")


if __name__ == "__main__":
    main()

"""Merge normalized CUAPTS raw data into the main apartments.json database.

Adds CUAPTS buildings (with reviews, star ratings, owner website, travel
times) that aren't already present, keyed by id. Idempotent.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from normalize_data import normalize_listing

ROOT = Path(__file__).resolve().parent.parent
MAIN = ROOT / "data" / "apartments.json"
# Raw file was written relative to scripts/ cwd on first run; check both.
_candidates = [
    ROOT / "data" / "raw" / "cuapts_raw.json",
    ROOT / "scripts" / "data" / "raw" / "cuapts_raw.json",
]
RAW = next((p for p in _candidates if p.exists()), _candidates[0])


def main():
    main_db = json.load(open(MAIN, encoding="utf-8"))
    raw = json.load(open(RAW, encoding="utf-8"))

    existing = {l.get("id") for l in main_db}
    norm = [normalize_listing(l, "cuapts") for l in raw]
    added = [l for l in norm if l["id"] not in existing]

    main_db.extend(added)
    json.dump(main_db, open(MAIN, "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)

    withrev = sum(1 for l in added if l.get("ratings", {}).get("num_reviews"))
    withimg = sum(1 for l in added if l.get("listing_info", {}).get("images"))
    print(f"added {len(added)} cuapts listings | total now {len(main_db)} "
          f"| {withrev} w/reviews | {withimg} w/images")


if __name__ == "__main__":
    main()

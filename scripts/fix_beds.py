"""Fix bedroom-count misparses surfaced by audit_all.py.

Two classes:
  1. CUAPTS stored the street number as the bedroom count (304 Bryant Ave ->
     "304 beds"). Any implausible bed count whose price doesn't support it is
     reset to 0 (unknown).
  2. Single rooms scraped as high-bed units (222 S Geneva "10bd $595" =
     $60/bed). When a real total divided by beds is implausibly low, the bed
     count is wrong -> treat as a room (beds unknown, per_person = total).

Keeps legitimate large houses (e.g. 710 E State "10bd $10,750" = $1,075/bed).
Then recomputes per_person and nulls any still-implausible per_person.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "apartments.json"
PB_LO, PB_HI = 350, 3000   # plausible per-bed band for a real unit


def main():
    d = json.load(open(DB, encoding="utf-8"))
    big_zeroed = rooms = 0
    for a in d:
        h = a.get("housing", {})
        p = a.get("pricing", {})
        beds = h.get("bedrooms", 0) or 0
        total = p.get("monthly_rent_total", 0) or 0

        # 1. implausible high bed count -> keep only if price supports it
        if beds > 9:
            if total and PB_LO <= total / beds <= PB_HI:
                pass  # legit large house (priced per bed in band)
            else:
                h["bedrooms"] = 0
                big_zeroed += 1
                beds = 0

        # 2. room misparsed as multi-bed: real total but per-bed too low
        if beds > 0 and total and total / beds < PB_LO:
            h["bedrooms"] = 0   # unknown; it's effectively a room
            beds = 0
            rooms += 1

        # recompute per_person from (possibly updated) beds
        if total > 0:
            p["per_person_monthly"] = round(total / beds) if beds > 0 else total
        # null implausible per_person, keep total
        pp = p.get("per_person_monthly", 0) or 0
        if pp and not (PB_LO <= pp <= 3200):
            p["per_person_monthly"] = 0

    json.dump(d, open(DB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"high-bed misparses zeroed: {big_zeroed}")
    print(f"rooms (low per-bed) un-bedded: {rooms}")


if __name__ == "__main__":
    main()

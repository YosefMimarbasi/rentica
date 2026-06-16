"""Correct monthly rent + per-person across every listing.

Root cause found: ithacarenting.com quotes rent PER BED ("prices listed are
per bed"). The scraper stored that per-bed figure as monthly_rent_total and
then divided by bedrooms for per-person -- wrong twice. A 3-bed at $890/bed
was stored as $890 total / $296 person; it should be $2,670 total / $890
person.

Pricing semantics by source (verified against raw + plausibility):
  - ithacarenting        -> stored value is PER BED. total = perbed * beds.
  - everyone else        -> stored value is the unit TOTAL (verified:
                            AppFolio, craigslist, csp, largebuildings/Cayuga,
                            ithacaestates all give plausible total/bed).

Universal rule after fixing totals: per_person = round(total / beds)
(studio/0-bed -> per_person = total).

Also: clears the earlier building-median fills (they propagated the wrong
ithacarenting numbers) and re-derives them from corrected per-bed rates.
"""
import json
import collections
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "apartments.json"

PP_MIN, PP_MAX = 350, 3200   # plausible per-person band for a sanity gate
TOTAL_MIN = 400              # no real Ithaca unit rents below this


def beds_of(a):
    return a.get("housing", {}).get("bedrooms", 0) or 0


def main():
    d = json.load(open(DB, encoding="utf-8"))

    # --- 1. drop earlier derived fills; they used pre-fix numbers ---
    for a in d:
        p = a.get("pricing", {})
        if p.get("price_basis"):
            p["monthly_rent_total"] = 0
            p["per_person_monthly"] = 0
            p.pop("price_basis", None)

    # --- 2. fix ithacarenting: stored total is actually per-bed ---
    ir_fixed = 0
    for a in d:
        if a.get("source") != "ithacarenting":
            continue
        p = a.get("pricing", {})
        perbed = p.get("monthly_rent_total", 0)
        if not perbed:
            continue
        beds = max(beds_of(a), 1)
        p["per_person_monthly"] = perbed
        p["monthly_rent_total"] = perbed * beds
        ir_fixed += 1

    # --- 3. universal per-person = total / beds for all real totals ---
    for a in d:
        p = a.get("pricing", {})
        total = p.get("monthly_rent_total", 0)
        if total <= 0:
            continue
        beds = beds_of(a)
        p["per_person_monthly"] = round(total / beds) if beds > 0 else total

    # --- 4. sanity gate: nuke implausibly low totals (bad parses) ---
    nuked = 0
    for a in d:
        p = a.get("pricing", {})
        if 0 < p.get("monthly_rent_total", 0) < TOTAL_MIN:
            p["monthly_rent_total"] = 0
            p["per_person_monthly"] = 0
            nuked += 1

    # --- 5. re-fill zero-price units from building per-bed rate ---
    byb = collections.defaultdict(list)
    for a in d:
        if a.get("building_id"):
            byb[a["building_id"]].append(a)
    filled = 0
    for a in d:
        p = a.setdefault("pricing", {})
        if p.get("monthly_rent_total", 0):
            continue
        # per-bed rates from priced siblings, restricted to the plausible band
        rates = [s["pricing"]["per_person_monthly"]
                 for s in byb.get(a.get("building_id"), [])
                 if PP_MIN <= s.get("pricing", {}).get("per_person_monthly", 0) <= PP_MAX]
        if not rates:
            continue
        perbed = int(statistics.median(rates))
        beds = max(beds_of(a), 1)
        total = perbed * beds
        if total < TOTAL_MIN:
            continue
        p["per_person_monthly"] = perbed
        p["monthly_rent_total"] = total
        p["price_basis"] = "building per-bed rate"
        filled += 1

    json.dump(d, open(DB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    rents = [a["pricing"]["monthly_rent_total"] for a in d
             if a.get("pricing", {}).get("monthly_rent_total", 0)]
    pps = [a["pricing"]["per_person_monthly"] for a in d
           if a.get("pricing", {}).get("per_person_monthly", 0)]
    print(f"ithacarenting fixed: {ir_fixed}")
    print(f"nuked sub-${TOTAL_MIN} totals: {nuked}")
    print(f"building-fill (corrected): {filled}")
    print(f"TOTAL with rent: {len(rents)}/{len(d)}")
    print(f"  total  median ${int(statistics.median(rents))} range ${min(rents)}-${max(rents)}")
    print(f"  person median ${int(statistics.median(pps))} range ${min(pps)}-${max(pps)}")


if __name__ == "__main__":
    main()

"""Generate statistics and insights from the apartment database."""
import json
import argparse
from pathlib import Path
from collections import Counter


def load_database(filename='data/apartments.json'):
    path = Path(filename)
    if not path.exists():
        print(f"Database not found at {path}. Run build_database.py first.")
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def summarize(apts, neighborhood=None):
    if neighborhood:
        apts = [a for a in apts if neighborhood.lower() in (a.get('address', '') or '').lower()]
        print(f"\nFiltered to neighborhood containing '{neighborhood}': {len(apts)} listings")

    if not apts:
        print("No listings to analyze.")
        return

    print("\n" + "=" * 60)
    print(f"RENTACA DATABASE STATISTICS  ({len(apts)} listings)")
    print("=" * 60)

    # Pricing
    rents = [a['pricing']['monthly_rent_total'] for a in apts
             if a.get('pricing', {}).get('monthly_rent_total')]
    pps = [a['pricing']['per_person_monthly'] for a in apts
           if a.get('pricing', {}).get('per_person_monthly')]
    if rents:
        rents.sort()
        print(f"\nTotal rent:  ${min(rents):,} – ${max(rents):,}  "
              f"(median ${rents[len(rents)//2]:,}, avg ${sum(rents)//len(rents):,})")
    if pps:
        pps.sort()
        print(f"Per person:  ${min(pps):,} – ${max(pps):,}  "
              f"(median ${pps[len(pps)//2]:,}, avg ${sum(pps)//len(pps):,})")

    # Bedrooms distribution
    beds = Counter(a.get('housing', {}).get('bedrooms', 0) for a in apts)
    print("\nBedrooms:")
    for b in sorted(beds):
        label = 'Studio' if b == 0 else f'{b} BR'
        print(f"  {label:>8}: {beds[b]:>3}  {'█' * beds[b]}")

    # Amenities coverage
    def pct(key, val=True):
        n = sum(1 for a in apts if a.get('amenities', {}).get(key) not in (None, False, 'none', ''))
        return n, round(100 * n / len(apts))

    print("\nAmenities coverage:")
    for key, label in [('parking', 'Parking'), ('laundry', 'Laundry'),
                       ('air_conditioning', 'A/C'), ('cats_ok', 'Cats OK'),
                       ('dogs_ok', 'Dogs OK')]:
        n, p = pct(key)
        print(f"  {label:>10}: {n:>3} ({p}%)")

    # Geocoding coverage
    with_coords = sum(1 for a in apts if a.get('coordinates', {}).get('lat'))
    print(f"\nGeocoded:    {with_coords}/{len(apts)} "
          f"({round(100*with_coords/len(apts))}%)")

    # Distance buckets to Cornell
    dists = [a.get('distance_to_cornell_miles', 0) for a in apts
             if a.get('distance_to_cornell_miles')]
    if dists:
        buckets = Counter()
        for d in dists:
            if d <= 1: buckets['≤1 mi'] += 1
            elif d <= 2: buckets['1–2 mi'] += 1
            elif d <= 5: buckets['2–5 mi'] += 1
            else: buckets['>5 mi'] += 1
        print("\nDistance to Cornell:")
        for k in ['≤1 mi', '1–2 mi', '2–5 mi', '>5 mi']:
            if buckets[k]:
                print(f"  {k:>8}: {buckets[k]:>3}")

    # Sources
    sources = Counter(a.get('source', 'unknown') for a in apts)
    print("\nSources:")
    for s, n in sources.most_common():
        print(f"  {s:>12}: {n}")

    print("=" * 60)


def main():
    ap = argparse.ArgumentParser(description='Analyze the apartment database')
    ap.add_argument('--neighborhood', type=str, help='Filter to a neighborhood/area')
    ap.add_argument('--database', type=str, default='data/apartments.json')
    args = ap.parse_args()
    summarize(load_database(args.database), neighborhood=args.neighborhood)


if __name__ == '__main__':
    main()

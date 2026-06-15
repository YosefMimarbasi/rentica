"""Search and filter the apartment database."""
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any


def load_database(filename: str = 'data/apartments.json') -> List[Dict]:
    """Load apartment database."""
    filepath = Path(filename)
    if not filepath.exists():
        print(f"Error: Database not found at {filepath}")
        return []

    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def filter_apartments(
    apartments: List[Dict],
    max_price: int = None,
    min_price: int = None,
    bedrooms: int = None,
    bathrooms: int = None,
    parking: bool = None,
    furnished: bool = None,
    max_distance_cornell: float = None,
    neighborhood: str = None,
) -> List[Dict]:
    """Filter apartments by criteria."""
    results = apartments

    # Price filters
    if min_price:
        results = [a for a in results if a.get('pricing', {}).get('monthly_rent_total', 0) >= min_price]
    if max_price:
        results = [a for a in results if a.get('pricing', {}).get('monthly_rent_total', 0) <= max_price]

    # Bedroom filter
    if bedrooms:
        results = [a for a in results if a.get('housing', {}).get('bedrooms', 0) >= bedrooms]

    # Bathroom filter
    if bathrooms:
        results = [a for a in results if a.get('housing', {}).get('bathrooms', 0) >= bathrooms]

    # Parking filter
    if parking:
        results = [a for a in results if a.get('amenities', {}).get('parking') not in [None, False]]

    # Furnished filter
    if furnished is not None:
        results = [a for a in results if a.get('housing', {}).get('furnished') == furnished]

    # Distance to Cornell filter
    if max_distance_cornell:
        results = [a for a in results if a.get('distance_to_cornell_miles', 999) <= max_distance_cornell]

    # Neighborhood filter
    if neighborhood:
        results = [
            a for a in results
            if neighborhood.lower() in a.get('address', '').lower()
        ]

    return results


def print_apartments(apartments: List[Dict], limit: int = 20):
    """Print apartments in readable format."""
    if not apartments:
        print("No apartments found.")
        return

    print(f"\nFound {len(apartments)} apartments\n")
    print("=" * 100)

    for i, apt in enumerate(apartments[:limit], 1):
        print(f"\n{i}. {apt.get('title')}")
        print(f"   Price: ${apt.get('pricing', {}).get('monthly_rent_total', 'N/A'):,}/month " +
              f"(${apt.get('pricing', {}).get('per_person_monthly', 'N/A')}/person)")
        print(f"   Address: {apt.get('address')}")

        housing = apt.get('housing', {})
        bedrooms = housing.get('bedrooms', 0)
        bathrooms = housing.get('bathrooms', 0)
        if bedrooms or bathrooms:
            print(f"   Housing: {bedrooms}BR / {bathrooms}BA")

        distance_cornell = apt.get('distance_to_cornell_miles', 0)
        if distance_cornell:
            print(f"   Distance to Cornell: {distance_cornell} miles")

        url = apt.get('listing_info', {}).get('url')
        if url:
            print(f"   URL: {url}")

        amenities = apt.get('amenities', {})
        amenity_list = [k for k, v in amenities.items() if v]
        if amenity_list:
            print(f"   Amenities: {', '.join(amenity_list)}")

    if len(apartments) > limit:
        print(f"\n... and {len(apartments) - limit} more apartments")

    print("\n" + "=" * 100)


def main():
    parser = argparse.ArgumentParser(description='Search apartment database')
    parser.add_argument('--min-price', type=int, help='Minimum monthly rent')
    parser.add_argument('--max-price', type=int, help='Maximum monthly rent')
    parser.add_argument('--bedrooms', type=int, help='Minimum number of bedrooms')
    parser.add_argument('--bathrooms', type=int, help='Minimum number of bathrooms')
    parser.add_argument('--parking', action='store_true', help='Has parking')
    parser.add_argument('--furnished', action='store_true', help='Furnished only')
    parser.add_argument('--max-distance-cornell', type=float, help='Max distance to Cornell (miles)')
    parser.add_argument('--neighborhood', type=str, help='Neighborhood filter')
    parser.add_argument('--limit', type=int, default=20, help='Max results to show')
    parser.add_argument('--database', type=str, default='data/apartments.json', help='Database file')

    args = parser.parse_args()

    # Load database
    apartments = load_database(args.database)
    if not apartments:
        return

    # Filter
    results = filter_apartments(
        apartments,
        max_price=args.max_price,
        min_price=args.min_price,
        bedrooms=args.bedrooms,
        bathrooms=args.bathrooms,
        parking=args.parking,
        furnished=args.furnished,
        max_distance_cornell=args.max_distance_cornell,
        neighborhood=args.neighborhood,
    )

    # Print
    print_apartments(results, limit=args.limit)


if __name__ == '__main__':
    main()

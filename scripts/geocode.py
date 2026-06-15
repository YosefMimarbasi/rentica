"""Add geocoding (coordinates) and distances to apartments."""
import json
import logging
import re
import time
from pathlib import Path
from typing import List, Dict, Tuple
from geopy.geocoders import Nominatim
from math import radians, cos, sin, asin, sqrt

logger = logging.getLogger(__name__)

# Cornell University coordinates
CORNELL_LAT = 42.4534
CORNELL_LNG = -76.4735

# Ithaca College coordinates
ITHACA_COLLEGE_LAT = 42.6023
ITHACA_COLLEGE_LNG = -76.5031


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two points on Earth in miles.
    Uses Haversine formula.
    """
    # Convert to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 3959  # Radius of Earth in miles

    return c * r


def _strip_unit(address: str) -> str:
    """Drop a unit/apartment suffix so the street address geocodes cleanly.

    e.g. "319 Highland Road, 2A, Ithaca, NY" -> "319 Highland Road, Ithaca, NY"
         "401 College Avenue - 2a, Ithaca, NY" -> "401 College Avenue, Ithaca, NY"
    """
    # Remove "- <unit>" segments before the city.
    address = re.sub(r'\s*[-–]\s*[\w/]+\s*,', ',', address)
    # Remove a short alphanumeric unit token between commas (e.g. ", 2A,").
    address = re.sub(r',\s*[\w/]{1,5}\s*,', ',', address)
    return address


def geocode_address(address: str, geocoder) -> Tuple[float, float]:
    """Geocode an address to lat/lng coordinates, with a unit-stripped retry."""
    if 'ithaca' not in address.lower():
        address = f"{address}, Ithaca, NY"

    attempts = [address]
    stripped = _strip_unit(address)
    if stripped != address:
        attempts.append(stripped)

    for attempt in attempts:
        try:
            location = geocoder.geocode(attempt, timeout=10)
            if location:
                return location.latitude, location.longitude
        except Exception as e:
            logger.warning(f"Geocoding error for {attempt}: {e}")
        time.sleep(1.0)

    logger.warning(f"Could not geocode: {address}")
    return 0, 0


CACHE_PATH = Path('data/geocode_cache.json')


def _load_cache() -> dict:
    if CACHE_PATH.exists():
        try:
            with open(CACHE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_cache(cache: dict):
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, 'w', encoding='utf-8') as f:
        json.dump(cache, f)


def add_coordinates_and_distances(listings: List[Dict]) -> List[Dict]:
    """Add coordinates and distance calculations to all listings.

    Results are cached in data/geocode_cache.json so repeated builds do not
    re-hit Nominatim for addresses already resolved.
    """
    geocoder = Nominatim(user_agent="rentica_apartment_scraper")
    cache = _load_cache()
    dirty = 0

    processed = []
    for i, listing in enumerate(listings):
        address = listing.get('address', '')

        # Fast path: listing already carries coordinates (e.g. Craigslist
        # embeds lat/lng on each detail page). Skip the geocoding API call
        # and just compute distances.
        existing = listing.get('coordinates', {}) or {}
        if existing.get('lat') and existing.get('lng'):
            lat, lng = existing['lat'], existing['lng']
            listing['distance_to_cornell_miles'] = round(
                haversine_distance(lat, lng, CORNELL_LAT, CORNELL_LNG), 2)
            listing['distance_to_ithaca_college_miles'] = round(
                haversine_distance(lat, lng, ITHACA_COLLEGE_LAT, ITHACA_COLLEGE_LNG), 2)
            processed.append(listing)
            continue

        if not address:
            logger.warning(f"No address for listing {i}: {listing.get('title')}")
            processed.append(listing)
            continue

        # Cache hit: reuse previously resolved coordinates.
        if address in cache:
            lat, lng = cache[address]
        else:
            logger.info(f"Geocoding {i+1}/{len(listings)}: {address}")
            lat, lng = geocode_address(address, geocoder)
            cache[address] = [lat, lng]
            dirty += 1
            if dirty % 10 == 0:
                _save_cache(cache)
            time.sleep(1.5)  # Nominatim asks for <= 1 request per second

        if lat and lng:
            distance_to_cornell = haversine_distance(lat, lng, CORNELL_LAT, CORNELL_LNG)
            distance_to_college = haversine_distance(lat, lng, ITHACA_COLLEGE_LAT, ITHACA_COLLEGE_LNG)
            listing['coordinates'] = {'lat': round(lat, 6), 'lng': round(lng, 6)}
            listing['distance_to_cornell_miles'] = round(distance_to_cornell, 2)
            listing['distance_to_ithaca_college_miles'] = round(distance_to_college, 2)
        else:
            listing['coordinates'] = {}
            listing['distance_to_cornell_miles'] = 0
            listing['distance_to_ithaca_college_miles'] = 0

        processed.append(listing)

    _save_cache(cache)
    return processed


def process_database(input_file: str = 'data/apartments.json', output_file: str = 'data/apartments_geocoded.json'):
    """Load database, add geocoding, and save."""
    input_path = Path(input_file)

    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        return

    logger.info(f"Loading {input_path}...")
    with open(input_path, 'r', encoding='utf-8') as f:
        listings = json.load(f)

    logger.info(f"Geocoding {len(listings)} listings...")
    geocoded = add_coordinates_and_distances(listings)

    logger.info(f"Saving to {output_file}...")
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(geocoded, f, indent=2, ensure_ascii=False)

    logger.info(f"Complete! Geocoded {len(geocoded)} listings")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    process_database()

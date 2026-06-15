"""Normalize and standardize apartment data from all sources."""
import json
import logging
from pathlib import Path
from typing import List, Dict, Any
import re

logger = logging.getLogger(__name__)


def parse_price(price_str: str) -> int:
    """Extract numeric price from string."""
    try:
        # Remove common text patterns
        cleaned = re.sub(r'[^\d]', '', price_str)
        return int(cleaned) if cleaned else 0
    except:
        return 0


def parse_bedrooms_bathrooms(text: str) -> tuple:
    """Extract bedrooms and bathrooms from text."""
    br = 0
    ba = 0
    try:
        # Match patterns like "3BR/2BA" or "3 bed 2 bath"
        br_match = re.search(r'(\d+)\s*(?:br|bed|bedroom)', text, re.I)
        ba_match = re.search(r'(\d+)\s*(?:ba|bath|bathroom)', text, re.I)

        if br_match:
            br = int(br_match.group(1))
        if ba_match:
            ba = int(ba_match.group(1))
    except:
        pass

    return br, ba


def extract_amenities(text: str) -> Dict[str, bool]:
    """Extract amenities from description text."""
    amenities = {
        'ac': False,
        'dishwasher': False,
        'laundry': None,
        'parking': None,
        'patio': False,
    }

    text_lower = text.lower()

    # Check for AC
    if 'air' in text_lower or 'ac' in text_lower:
        amenities['ac'] = True

    # Check for dishwasher
    if 'dishwash' in text_lower:
        amenities['dishwasher'] = True

    # Check for laundry
    if 'in-unit' in text_lower or 'in unit' in text_lower:
        amenities['laundry'] = 'in-unit'
    elif 'in-building' in text_lower or 'in building' in text_lower:
        amenities['laundry'] = 'in-building'
    elif 'laundry' in text_lower:
        amenities['laundry'] = 'off-site'

    # Check for parking
    if 'no parking' in text_lower or 'no car' in text_lower:
        amenities['parking'] = False
    elif 'garage' in text_lower:
        amenities['parking'] = 'garage'
    elif 'driveway' in text_lower:
        amenities['parking'] = 'driveway'
    elif 'parking' in text_lower or 'lot' in text_lower:
        amenities['parking'] = 'lot'

    # Check for patio/balcony
    if 'patio' in text_lower or 'balcony' in text_lower or 'deck' in text_lower:
        amenities['patio'] = True

    return amenities


def normalize_listing(listing: Dict[str, Any], source: str) -> Dict[str, Any]:
    """Normalize listing to standard format."""
    description = listing.get('description', '') or listing.get('details', '') or ''
    title = listing.get('title', '')
    full_text = f"{title} {description}".lower()

    # Parse housing details
    br, ba = parse_bedrooms_bathrooms(title + ' ' + description)

    # Parse price
    price = listing.get('price', listing.get('monthly_rent', 0))
    if isinstance(price, str):
        price = parse_price(price)

    # Extract amenities
    amenities = extract_amenities(full_text)

    # Determine number of people sharing (from bedrooms)
    occupants = max(br, 1) if br > 0 else 0
    price_per_person = price // occupants if occupants > 0 else price

    normalized = {
        'id': f"{source}-{listing.get('id', '')}",
        'source': source,
        'title': title,
        'description': description,
        'address': listing.get('address', ''),
        'coordinates': listing.get('coordinates', {}),
        'housing': {
            'bedrooms': br,
            'bathrooms': ba,
            'sqft': listing.get('sqft', 0),
            'furnished': 'furnished' in full_text,
            'floor': 0,
        },
        'pricing': {
            'monthly_rent_total': price,
            'per_person_monthly': price_per_person,
            'security_deposit': listing.get('deposit', 0),
            'utilities_included': 'utilities' in full_text and 'included' in full_text,
            'internet_included': 'internet' in full_text and ('included' in full_text or 'free' in full_text),
        },
        'amenities': amenities,
        'requirements': listing.get('requirements', {}),
        'contact': listing.get('contact', {}),
        'listing_info': {
            'posted_date': listing.get('posted_date', ''),
            'last_updated': listing.get('last_updated', ''),
            'url': listing.get('url', ''),
            'images': listing.get('images', []),
        },
        'distance_to_cornell_miles': listing.get('distance_to_cornell', 0),
        'distance_to_ithaca_college_miles': listing.get('distance_to_college', 0),
    }

    return normalized


def process_all_raw_data() -> List[Dict[str, Any]]:
    """Load, normalize, and combine all raw data files."""
    raw_dir = Path('data/raw')
    all_listings = []

    if not raw_dir.exists():
        logger.warning(f"Raw data directory not found: {raw_dir}")
        return []

    for json_file in raw_dir.glob('*.json'):
        source = json_file.stem.replace('_raw', '')
        logger.info(f"Processing {json_file}...")

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                listings = json.load(f)

            normalized = [normalize_listing(listing, source) for listing in listings]
            all_listings.extend(normalized)
            logger.info(f"  Normalized {len(normalized)} listings from {source}")

        except Exception as e:
            logger.error(f"Error processing {json_file}: {e}")
            continue

    return all_listings


def deduplicate_listings(listings: List[Dict]) -> List[Dict]:
    """Remove duplicate listings based on address and price."""
    seen = {}
    unique = []

    for listing in listings:
        key = (
            listing.get('address', ''),
            listing.get('pricing', {}).get('monthly_rent_total', 0),
        )

        if key not in seen:
            seen[key] = listing
            unique.append(listing)

    logger.info(f"Removed {len(listings) - len(unique)} duplicate listings")
    return unique


def save_processed_data(listings: List[Dict], filename: str = 'apartments.json'):
    """Save processed listings to file."""
    output_dir = Path('data')
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / filename
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(listings, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved {len(listings)} listings to {output_path}")
    return output_path


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    logger.info("Processing all raw data...")
    listings = process_all_raw_data()

    logger.info("Deduplicating...")
    listings = deduplicate_listings(listings)

    logger.info("Saving processed data...")
    save_processed_data(listings)

    logger.info(f"Complete! Total listings: {len(listings)}")

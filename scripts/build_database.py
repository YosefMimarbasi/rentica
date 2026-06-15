"""Master script to build complete apartment database from all sources."""
import json
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from scrape_craigslist import CraigslistScraper
from scrape_lambrou import LambrouScraper
from scrape_ithacaestates import IthacaEstatesScraper
from scrape_strawberry import StrawberryScraper
from scrape_ridgetop import RidgetopScraper
from scrape_appfolio import AppFolioScraper, APPFOLIO_PORTALS
from scrape_cuapts import CuaptsScraper
from normalize_data import process_all_raw_data, deduplicate_listings, save_processed_data
from geocode import add_coordinates_and_distances

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def ensure_directories():
    """Create required directories."""
    directories = [
        Path('data'),
        Path('data/raw'),
        Path('data/processed'),
    ]
    for d in directories:
        d.mkdir(parents=True, exist_ok=True)
        logger.info(f"✓ Directory ready: {d}")


def scrape_all_sources():
    """Scrape apartments from all sources."""
    logger.info("\n" + "="*60)
    logger.info("SCRAPING ALL SOURCES")
    logger.info("="*60)

    sources = {
        'craigslist': CraigslistScraper(),
        'lambrou': LambrouScraper(),
        'ithacaestates': IthacaEstatesScraper(),
        'strawberry': StrawberryScraper(),
        'ridgetop': RidgetopScraper(),
        'cuapts': CuaptsScraper(),
    }
    # AppFolio-powered property managers (PPM Homes, Travis Hyde,
    # Modern Living Rentals, ...).
    for portal, name in APPFOLIO_PORTALS.items():
        sources[name] = AppFolioScraper(portal, name)
    # Sites blocking automated access (HTTP 403): apartments.com, zillow.com
    # Sites needing a headless browser / other platforms (not yet supported):
    #   Lux & Lofts (Entrata), Cayuga Place (RealPage), Harold's Square (Buildium),
    #   Collegetown Terrace (403), Heritage Park (greatcommunities portal)
    # Ithaca Renting Company: scraper exists (scrape_ithacarenting.py) but its
    #   HTML does not expose per-unit address/price reliably, so it is excluded
    #   to keep the database accurate. Eddygate & Seneca Way are covered via
    #   Travis Hyde (their manager).

    all_listings = []
    for source_name, scraper in sources.items():
        try:
            logger.info(f"\nScraping {source_name}...")
            listings = scraper.scrape()
            all_listings.extend(listings)
            logger.info(f"✓ Successfully scraped {len(listings)} listings from {source_name}")
        except Exception as e:
            logger.error(f"✗ Error scraping {source_name}: {e}")

    return all_listings


def build_database():
    """Build complete apartment database."""
    logger.info("\n" + "="*60)
    logger.info("BUILDING APARTMENT DATABASE")
    logger.info("="*60)

    # Step 1: Ensure directories
    logger.info("\nStep 1: Creating directories...")
    ensure_directories()

    # Step 2: Scrape all sources
    logger.info("\nStep 2: Scraping apartment sources...")
    try:
        scrape_all_sources()
        logger.info("✓ Scraping complete")
    except Exception as e:
        logger.error(f"Scraping failed: {e}")

    # Step 3: Normalize data
    logger.info("\nStep 3: Normalizing data...")
    try:
        listings = process_all_raw_data()
        logger.info(f"✓ Normalized {len(listings)} listings")
    except Exception as e:
        logger.error(f"Normalization failed: {e}")
        return

    # Step 4: Deduplicate
    logger.info("\nStep 4: Removing duplicates...")
    try:
        listings = deduplicate_listings(listings)
        logger.info(f"✓ Deduplication complete ({len(listings)} unique listings)")
    except Exception as e:
        logger.error(f"Deduplication failed: {e}")
        return

    # Step 5: Add geocoding
    logger.info("\nStep 5: Adding coordinates and distances...")
    try:
        listings = add_coordinates_and_distances(listings)
        logger.info(f"✓ Geocoding complete")
    except Exception as e:
        logger.warning(f"Geocoding failed (continuing without): {e}")

    # Step 6: Save final database
    logger.info("\nStep 6: Saving final database...")
    try:
        save_processed_data(listings, 'data/apartments.json')
        logger.info(f"✓ Saved {len(listings)} listings to data/apartments.json")
    except Exception as e:
        logger.error(f"Save failed: {e}")
        return

    # Summary
    logger.info("\n" + "="*60)
    logger.info("DATABASE BUILD COMPLETE!")
    logger.info("="*60)
    logger.info(f"Total listings: {len(listings)}")

    # Statistics
    if listings:
        prices = [l.get('pricing', {}).get('monthly_rent_total', 0) for l in listings if l.get('pricing', {}).get('monthly_rent_total')]
        if prices:
            logger.info(f"Price range: ${min(prices):,} - ${max(prices):,}")
            logger.info(f"Average price: ${sum(prices)//len(prices):,}")

        with_coords = len([l for l in listings if l.get('coordinates', {})])
        logger.info(f"Listings with coordinates: {with_coords}/{len(listings)}")

    logger.info("\nUsage:")
    logger.info("  python tools/search.py --max-price 800 --bedrooms 2")
    logger.info("  python tools/search.py --neighborhood Commons --parking")


if __name__ == '__main__':
    build_database()

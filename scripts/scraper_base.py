"""Base scraper class for all apartment data sources."""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import requests
from urllib.robotparser import RobotFileParser

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BaseScraper:
    """Base class for all scraping sources."""

    def __init__(self, source_name: str, base_url: str):
        self.source_name = source_name
        self.base_url = base_url
        self.listings = []
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) '
                           'Chrome/120.0.0.0 Safari/537.36'),
            'Accept': ('text/html,application/xhtml+xml,application/xml;q=0.9,'
                       'image/avif,image/webp,*/*;q=0.8'),
            'Accept-Language': 'en-US,en;q=0.9',
        })
        self._check_robots_txt()

    def _check_robots_txt(self):
        """Check robots.txt to ensure scraping is allowed."""
        try:
            rp = RobotFileParser()
            rp.set_url(self.base_url + '/robots.txt')
            rp.read()
            if not rp.can_fetch('*', self.base_url):
                logger.warning(f"robots.txt may restrict scraping of {self.base_url}")
        except Exception as e:
            logger.warning(f"Could not check robots.txt: {e}")

    def scrape(self) -> List[Dict[str, Any]]:
        """Main scraping method - override in subclasses."""
        raise NotImplementedError

    def normalize_listing(self, raw_listing: Dict) -> Dict[str, Any]:
        """
        Normalize listing to standard format.
        Override in subclasses for source-specific normalization.
        """
        return {
            "id": f"{self.source_name}-{raw_listing.get('id', '')}",
            "source": self.source_name,
            "title": raw_listing.get('title', ''),
            "description": raw_listing.get('description', ''),
            "address": raw_listing.get('address', ''),
            "coordinates": raw_listing.get('coordinates', {}),
            "housing": raw_listing.get('housing', {}),
            "pricing": raw_listing.get('pricing', {}),
            "amenities": raw_listing.get('amenities', {}),
            "requirements": raw_listing.get('requirements', {}),
            "contact": raw_listing.get('contact', {}),
            "listing_info": {
                "posted_date": raw_listing.get('posted_date', datetime.now().isoformat()),
                "last_updated": datetime.now().isoformat(),
                "url": raw_listing.get('url', ''),
                "images": raw_listing.get('images', [])
            }
        }

    def save_raw_data(self, data: List[Dict], filename: str = None):
        """Save raw scraped data."""
        if filename is None:
            filename = f"{self.source_name}.json"

        raw_dir = Path("data/raw")
        raw_dir.mkdir(parents=True, exist_ok=True)

        filepath = raw_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(data)} listings to {filepath}")
        return filepath

    def process_listings(self) -> List[Dict]:
        """Process and normalize all listings."""
        normalized = [self.normalize_listing(listing) for listing in self.listings]
        self.listings = normalized
        return normalized

    def get_listings(self) -> List[Dict]:
        """Get all listings."""
        return self.listings

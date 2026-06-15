"""Lambrou Real Estate scraper (Squarespace-backed).

Squarespace exposes any collection page as structured JSON via the
``?format=json-pretty`` query parameter, which sidesteps the client-side
rendering. Each apartment is an item carrying title (address), categories
(bedroom count), an excerpt (description with price), an image, and a URL.
"""
import re
import time
import logging
from datetime import datetime
from bs4 import BeautifulSoup
from scraper_base import BaseScraper

logger = logging.getLogger(__name__)


class LambrouScraper(BaseScraper):
    """Scrape apartments from Lambrou Real Estate."""

    def __init__(self):
        super().__init__('lambrou', 'https://www.lambrourealestate.com')
        self.listing_url = f'{self.base_url}/apartments?format=json-pretty'

    def scrape(self) -> list:
        logger.info("Starting Lambrou scrape...")
        try:
            resp = self.session.get(self.listing_url, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"Lambrou scrape failed: {e}")
            return []

        items = data.get('items', [])
        logger.info(f"Found {len(items)} Lambrou listings")

        for item in items:
            try:
                listing = self._parse_item(item)
                if listing:
                    self.listings.append(listing)
            except Exception as e:
                logger.warning(f"Error parsing Lambrou item: {e}")
            time.sleep(0.2)

        logger.info(f"Successfully scraped {len(self.listings)} Lambrou listings")
        self.save_raw_data(self.listings, 'lambrou_raw.json')
        return self.listings

    def _parse_item(self, item: dict) -> dict:
        title = item.get('title', '').strip()
        excerpt_html = item.get('body') or item.get('excerpt') or ''
        description = re.sub(r'<[^>]+>', ' ', excerpt_html)
        description = re.sub(r'\s+', ' ', description).replace('\xa0', ' ').strip()

        # Bedrooms from category labels like "3 Bedrooms".
        bedrooms = 0
        for cat in item.get('categories', []):
            m = re.search(r'(\d+)\s*bedroom', cat, re.I)
            if m:
                bedrooms = int(m.group(1))
                break
        if not bedrooms:
            m = re.search(r'(\d+)\s*bedroom', description, re.I)
            if m:
                bedrooms = int(m.group(1))

        # Bathrooms / sqft from description text.
        bathrooms = 0
        bam = re.search(r'(\d+(?:\.\d+)?)\s*bath', description, re.I)
        if bam:
            v = float(bam.group(1))
            bathrooms = int(v) if v.is_integer() else v
        sqft = 0
        sm = re.search(r'([\d,]{3,5})\s*(?:sq\.?\s*ft|square feet)', description, re.I)
        if sm:
            sqft = int(sm.group(1).replace(',', ''))

        # Price: Squarespace priceMoney, else a "$1,234" in the description.
        price = 0
        pm = item.get('priceMoney') or {}
        if isinstance(pm, dict) and pm.get('value'):
            try:
                price = int(float(pm['value']))
            except (ValueError, TypeError):
                price = 0
        if not price:
            mp = re.search(r'\$\s*([\d,]{3,6})', description)
            if mp:
                price = int(mp.group(1).replace(',', ''))

        # Amenities from description keywords.
        t = description.lower()
        amenities = {
            'laundry': 'in-unit' if 'in-unit laundry' in t or 'in unit laundry' in t
                       else ('in-building' if 'laundry' in t else None),
            'parking': 'off-street' if 'parking' in t else None,
            'air_conditioning': 'air conditioning' in t or 'a/c' in t or 'central air' in t,
            'furnished': 'furnished' in t,
            'dishwasher': 'dishwasher' in t,
        }

        url = item.get('fullUrl', '')
        if url and not url.startswith('http'):
            url = self.base_url + url

        images = []
        if item.get('assetUrl'):
            images.append(item['assetUrl'])

        added = item.get('addedOn')
        posted = ''
        if added:
            try:
                posted = datetime.fromtimestamp(added / 1000).isoformat()
            except Exception:
                posted = ''

        return {
            'id': item.get('id', ''),
            'title': title,
            'url': url,
            'description': description,
            'posted_date': posted or datetime.now().isoformat(),
            'pricing': {'monthly_rent_total': price, 'rent_period': 'monthly'},
            'housing': {'bedrooms': bedrooms, 'bathrooms': bathrooms, 'sqft': sqft},
            'amenities': amenities,
            'coordinates': {},
            'address': f"{title}, Ithaca, NY" if title else '',
            'images': images,
        }


if __name__ == '__main__':
    s = LambrouScraper()
    listings = s.scrape()
    print(f"\nScraped {len(listings)} Lambrou listings")
    for l in listings[:6]:
        h, p = l['housing'], l['pricing']
        print(f"  - {l['title'][:35]:37} ${p['monthly_rent_total']:>5}  "
              f"{h['bedrooms']}BR/{h['bathrooms']}BA  {l['address'][:30]}")

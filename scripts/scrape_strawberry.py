"""Strawberry Property scraper (WordPress).

Strawberry Property rents furnished houses to Cornell students. The
/listings index links to /listings/<slug> detail pages. Pricing and exact
bed counts are not published online (handled per-inquiry), so we capture the
address, description, parsed amenities, and photos for each house.
"""
import re
import time
import logging
from datetime import datetime
from bs4 import BeautifulSoup
from scraper_base import BaseScraper

logger = logging.getLogger(__name__)


class StrawberryScraper(BaseScraper):
    """Scrape houses from Strawberry Property."""

    def __init__(self):
        super().__init__('strawberry', 'https://strawberryproperty.com')
        self.index_url = f'{self.base_url}/listings'

    def scrape(self) -> list:
        logger.info("Starting Strawberry scrape...")
        try:
            r = self.session.get(self.index_url, timeout=15)
            r.raise_for_status()
        except Exception as e:
            logger.error(f"Strawberry scrape failed: {e}")
            return []

        urls = sorted(set(re.findall(
            r'https://strawberryproperty\.com/listings/[a-z0-9\-]+', r.text, re.I)))
        logger.info(f"Found {len(urls)} Strawberry listings")

        for url in urls:
            try:
                listing = self._scrape_detail(url)
                if listing:
                    self.listings.append(listing)
            except Exception as e:
                logger.warning(f"Error scraping {url}: {e}")
            time.sleep(0.6)

        logger.info(f"Successfully scraped {len(self.listings)} Strawberry listings")
        self.save_raw_data(self.listings, 'strawberry_raw.json')
        return self.listings

    def _scrape_detail(self, url: str) -> dict:
        r = self.session.get(url, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, 'html.parser')

        # Address from the URL slug (reliable), e.g. "117-stewart-avenue".
        slug = url.rstrip('/').split('/')[-1]
        address_name = slug.replace('-', ' ').title()
        # Normalize common abbreviations.
        address_name = re.sub(r'\bN\b', 'N', address_name)
        address = f"{address_name}, Ithaca, NY"

        text = soup.get_text(' ', strip=True)

        # Bedrooms if mentioned anywhere ("4 bedroom house").
        bedrooms = 0
        bm = re.search(r'(\d+)\s*[- ]?\s*bedroom', text, re.I)
        if bm:
            bedrooms = int(bm.group(1))
        bathrooms = 0
        bam = re.search(r'(\d+(?:\.\d+)?)\s*[- ]?\s*bath', text, re.I)
        if bam:
            v = float(bam.group(1))
            bathrooms = int(v) if v.is_integer() else v

        # Description: longest paragraph.
        paras = [p.get_text(' ', strip=True) for p in soup.find_all('p')
                 if len(p.get_text(strip=True)) > 50]
        description = max(paras, key=len) if paras else ''

        # Amenities from description.
        t = (description + ' ' + text).lower()
        amenities = {
            'laundry': 'in-unit' if 'free laundry' in t or 'in-unit laundry' in t
                       else ('on-site' if 'laundry' in t else None),
            'parking': 'street' if 'street parking' in t
                       else ('off-street' if 'parking' in t else None),
            'furnished': 'furnished' in t,
            'air_conditioning': 'air conditioning' in t or 'central air' in t,
            'dishwasher': 'dishwasher' in t,
            'hardwood': 'hardwood' in t,
            'porch_deck': 'porch' in t or 'deck' in t,
        }

        # Images (skip the logo and tiny assets).
        images, seen = [], set()
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src') or ''
            if 'wp-content/uploads' not in src or 'logo' in src.lower():
                continue
            key = re.sub(r'-\d+x\d+(?=\.\w+$)', '', src)
            if key in seen:
                continue
            seen.add(key)
            images.append(src)
        images = images[:10]

        return {
            'id': slug,
            'title': address_name,
            'url': url,
            'description': description[:1000],
            'posted_date': datetime.now().isoformat(),
            'pricing': {'monthly_rent_total': 0, 'rent_period': 'monthly'},
            'housing': {'bedrooms': bedrooms, 'bathrooms': bathrooms, 'sqft': 0},
            'amenities': amenities,
            'coordinates': {},
            'address': address,
            'images': images,
        }


if __name__ == '__main__':
    s = StrawberryScraper()
    listings = s.scrape()
    print(f"\nScraped {len(listings)} Strawberry listings")
    for l in listings:
        h = l['housing']
        print(f"  - {l['address'][:40]:42} {h['bedrooms']}BR  imgs={len(l['images'])}")

"""Ridgetop (Collegetown) scraper.

Ridgetop runs a Squarespace site with one page per building (Eddy St,
Dryden Rd). Each building page lists several unit types with bed/bath
counts but no public pricing. We capture one listing per building with the
bedroom range, parsed amenities, description, and photos.
"""
import re
import time
import logging
from datetime import datetime
from bs4 import BeautifulSoup
from scraper_base import BaseScraper

logger = logging.getLogger(__name__)


class RidgetopScraper(BaseScraper):
    """Scrape buildings from Ridgetop Ithaca."""

    def __init__(self):
        super().__init__('ridgetop', 'https://www.ridgetopithaca.com')

    def scrape(self) -> list:
        logger.info("Starting Ridgetop scrape...")
        try:
            home = self.session.get(self.base_url + '/', timeout=15)
        except Exception as e:
            logger.error(f"Ridgetop scrape failed: {e}")
            return []

        # Building pages look like /<addr>-apartments-ithaca.
        paths = sorted(set(re.findall(
            r'/[a-z0-9\-]+-apartments-ithaca', home.text, re.I)))
        logger.info(f"Found {len(paths)} Ridgetop buildings")

        for path in paths:
            url = self.base_url + path
            try:
                listing = self._scrape_detail(url, path)
                if listing:
                    self.listings.append(listing)
            except Exception as e:
                logger.warning(f"Error scraping {url}: {e}")
            time.sleep(0.6)

        logger.info(f"Successfully scraped {len(self.listings)} Ridgetop listings")
        self.save_raw_data(self.listings, 'ridgetop_raw.json')
        return self.listings

    def _scrape_detail(self, url: str, path: str) -> dict:
        r = self.session.get(url, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, 'html.parser')
        text = soup.get_text(' ', strip=True)

        # Address from the path: "/311-eddy-street-apartments-ithaca".
        slug = path.strip('/').replace('-apartments-ithaca', '')
        address_name = slug.replace('-', ' ').title()
        address = f"{address_name}, Ithaca, NY"

        # Bedroom options across unit types.
        beds = sorted({int(m) for m in re.findall(r'(\d+)\s*(?:bed|bedroom|br)\b', text, re.I)
                       if m.isdigit() and int(m) <= 10})
        bedrooms = beds[0] if beds else 0
        baths = sorted({float(m) for m in re.findall(r'(\d+(?:\.\d+)?)\s*(?:bath|ba)\b', text, re.I)
                        if float(m) <= 10})
        bathrooms = baths[0] if baths else 0
        if isinstance(bathrooms, float) and bathrooms.is_integer():
            bathrooms = int(bathrooms)

        paras = [p.get_text(' ', strip=True) for p in soup.find_all('p')
                 if len(p.get_text(strip=True)) > 50]
        description = max(paras, key=len) if paras else ''
        if beds:
            description = f"Bedroom options: {', '.join(map(str, beds))} BR. " + description

        t = text.lower()
        amenities = {
            'laundry': 'in-unit' if 'in-unit laundry' in t or 'in unit laundry' in t
                       else ('on-site' if 'laundry' in t else None),
            'parking': 'off-street' if 'parking' in t else None,
            'furnished': 'furnished' in t,
            'air_conditioning': 'air conditioning' in t or 'central air' in t,
            'dishwasher': 'dishwasher' in t,
            'heat_included': 'heat included' in t or 'utilities included' in t,
        }

        images, seen = [], set()
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src') or ''
            if 'squarespace-cdn' in src or 'images.squarespace' in src:
                key = re.sub(r'\?.*$', '', src)
                if key not in seen:
                    seen.add(key)
                    images.append(src)
        images = images[:8]

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
    s = RidgetopScraper()
    listings = s.scrape()
    print(f"\nScraped {len(listings)} Ridgetop listings")
    for l in listings:
        h = l['housing']
        print(f"  - {l['address'][:42]:44} {h['bedrooms']}BR/{h['bathrooms']}BA imgs={len(l['images'])}")

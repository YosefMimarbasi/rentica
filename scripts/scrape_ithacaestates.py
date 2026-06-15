"""Ithaca Estates Realty scraper.

The property index (/our-properties) links to individual /property/<slug>
detail pages whose HTML is server-rendered. Each detail page describes a
building that may contain several unit types, so we capture one listing per
building with its address, the bedroom options offered, the starting price,
description, and images.
"""
import re
import time
import logging
from datetime import datetime
from bs4 import BeautifulSoup
from scraper_base import BaseScraper

logger = logging.getLogger(__name__)


class IthacaEstatesScraper(BaseScraper):
    """Scrape buildings from Ithaca Estates Realty."""

    def __init__(self):
        super().__init__('ithacaestates', 'https://www.ithacaestatesrealty.com')
        self.index_url = f'{self.base_url}/our-properties'

    def scrape(self) -> list:
        logger.info("Starting Ithaca Estates scrape...")
        slugs = self._collect_slugs()
        logger.info(f"Found {len(slugs)} Ithaca Estates properties")

        for slug in slugs:
            url = f'{self.base_url}/property/{slug}'
            try:
                listing = self._scrape_detail(url)
                if listing:
                    self.listings.append(listing)
            except Exception as e:
                logger.warning(f"Error scraping {url}: {e}")
            time.sleep(0.8)

        logger.info(f"Successfully scraped {len(self.listings)} Ithaca Estates listings")
        self.save_raw_data(self.listings, 'ithacaestates_raw.json')
        return self.listings

    def _collect_slugs(self) -> list:
        slugs = set()
        for idx in [f'{self.base_url}/our-properties', f'{self.base_url}/vacancies']:
            try:
                r = self.session.get(idx, timeout=20)
                slugs.update(re.findall(r'/property/([a-z0-9-]+)', r.text, re.I))
            except Exception as e:
                logger.warning(f"Could not read index {idx}: {e}")
        return sorted(slugs)

    def _scrape_detail(self, url: str) -> dict:
        r = self.session.get(url, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, 'html.parser')
        text = soup.get_text(' ', strip=True)

        # Title / address
        title = ''
        if soup.title and soup.title.string:
            title = soup.title.string.split('-')[0].strip()
        # Require a street-number-led address to avoid capturing the domain
        # or other words that precede ", Ithaca, NY".
        addr_m = re.search(r'(\d+\s+[A-Za-z][\w .]+?,\s*Ithaca,?\s*NY(?:\s+\d{5})?)', text)
        address = addr_m.group(1).strip() if addr_m else (
            f"{title}, Ithaca, NY" if title else '')

        # Bedroom options -> take the max as the building's headline size,
        # but record the full range in the description.
        beds_found = sorted({int(m) for m in re.findall(r'(\d+)\s*bed', text, re.I) if m.isdigit()})
        bedrooms = beds_found[0] if beds_found else 0
        baths_found = sorted({float(m) for m in re.findall(r'(\d+(?:\.\d+)?)\s*bath', text, re.I)})
        bathrooms = baths_found[0] if baths_found else 0
        if isinstance(bathrooms, float) and bathrooms.is_integer():
            bathrooms = int(bathrooms)

        # Prices: take the minimum realistic monthly rent (>= $400 to skip fees).
        prices = [int(p.replace(',', '')) for p in re.findall(r'[$]([\d,]{3,6})', text)]
        rents = [p for p in prices if p >= 400]
        price = min(rents) if rents else 0

        # Square footage
        sqft = 0
        sm = re.search(r'([\d,]{3,5})\s*(?:sq\.?\s*ft|square feet)', text, re.I)
        if sm:
            sqft = int(sm.group(1).replace(',', ''))

        # Description: the longest paragraph on the page.
        paras = [p.get_text(' ', strip=True) for p in soup.find_all('p')]
        paras = [p for p in paras if len(p) > 60]
        description = max(paras, key=len) if paras else ''
        if beds_found:
            description = (f"Bedroom options: {', '.join(map(str, beds_found))} BR. "
                          + description)

        # Amenities from page text
        t = text.lower()
        amenities = {
            'laundry': 'in-unit' if 'in-unit laundry' in t or 'in unit laundry' in t
                       else ('in-building' if 'laundry' in t else None),
            'parking': 'off-street' if 'parking' in t else None,
            'air_conditioning': 'air conditioning' in t or 'central air' in t,
            'furnished': 'furnished' in t,
            'dishwasher': 'dishwasher' in t,
            'heat_included': 'heat included' in t or 'heat & hot water' in t,
        }

        # Images (Squarespace CDN)
        images = []
        seen = set()
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src') or ''
            if 'squarespace-cdn' in src or 'images.squarespace' in src:
                key = re.sub(r'\?.*$', '', src)
                if key not in seen:
                    seen.add(key)
                    images.append(src)
        images = images[:8]

        return {
            'id': url.rstrip('/').split('/')[-1],
            'title': title or address,
            'url': url,
            'description': description[:1000],
            'posted_date': datetime.now().isoformat(),
            'pricing': {'monthly_rent_total': price, 'rent_period': 'monthly'},
            'housing': {'bedrooms': bedrooms, 'bathrooms': bathrooms, 'sqft': sqft},
            'amenities': amenities,
            'coordinates': {},
            'address': address,
            'images': images,
        }


if __name__ == '__main__':
    s = IthacaEstatesScraper()
    listings = s.scrape()
    print(f"\nScraped {len(listings)} Ithaca Estates listings")
    for l in listings:
        h, p = l['housing'], l['pricing']
        print(f"  - {l['title'][:30]:32} ${p['monthly_rent_total']:>5}  "
              f"{h['bedrooms']}BR/{h['bathrooms']}BA  {l['address'][:35]}")

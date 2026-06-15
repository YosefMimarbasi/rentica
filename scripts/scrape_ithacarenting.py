"""Ithaca Renting Company scraper (RentManager-backed WordPress).

Ithaca Renting Company (IRC) is a major Cornell-area landlord. Its site
lists units under /collegetown/ and /downtown/, each linking to a
unit-details page (?uid=N).

LIMITATION: the detail-page H1 reliably gives the bed/bath count, but the
page body interleaves the unit's own address and per-bed pricing with a
roster of OTHER units at the same property, so address/price cannot be
attributed to a specific unit from the HTML. The underlying data lives in
the RentManager Tenant Web Access portal (irc.twa.rentmanager.com), which
is JS-rendered and has no public listings endpoint. For this reason IRC is
NOT included in the published database; this scraper is kept for the
reliable bed/bath/description/photo fields and as a starting point should
the RentManager API become available. See build_database.py.
"""
import re
import time
import logging
from datetime import datetime
from bs4 import BeautifulSoup
from scraper_base import BaseScraper

logger = logging.getLogger(__name__)

STREET_RE = re.compile(
    r'\d+[\w\- ]*?\b(?:St|Ave|Street|Avenue|Rd|Road|Place|Pl|Dr|Drive|'
    r'Lane|Ln|Way|Terrace|Ter|Court|Ct|Heights|Blvd|Boulevard)\b\.?',
    re.I)


class IthacaRentingScraper(BaseScraper):
    """Scrape units from Ithaca Renting Company."""

    def __init__(self):
        super().__init__('ithacarenting', 'https://ithacarenting.com')
        self.index_pages = ['collegetown', 'downtown']

    def scrape(self) -> list:
        logger.info("Starting Ithaca Renting Company scrape...")
        uids = {}
        for page in self.index_pages:
            try:
                r = self.session.get(f'{self.base_url}/{page}/', timeout=15)
                for uid in re.findall(r'uid=(\d+)', r.text):
                    uids.setdefault(uid, page)
            except Exception as e:
                logger.warning(f"Could not read /{page}/: {e}")
            time.sleep(0.4)

        logger.info(f"Found {len(uids)} Ithaca Renting units")
        for uid, area in uids.items():
            url = f'{self.base_url}/unit-details/?uid={uid}'
            try:
                listing = self._scrape_detail(url, uid, area)
                if listing:
                    self.listings.append(listing)
            except Exception as e:
                logger.warning(f"Error scraping uid={uid}: {e}")
            time.sleep(0.6)

        logger.info(f"Successfully scraped {len(self.listings)} Ithaca Renting listings")
        self.save_raw_data(self.listings, 'ithacarenting_raw.json')
        return self.listings

    def _scrape_detail(self, url: str, uid: str, area: str) -> dict:
        r = self.session.get(url, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, 'html.parser')

        # Scope to the main unit-details container to avoid sidebar/related
        # units polluting address and price extraction.
        main = soup.select_one('.unit-details') or soup.select_one('main') or soup
        page_text = main.get_text(' ', strip=True)

        # Bed / bath from the H1 (e.g. "Deluxe 6 Bedrooms 3 Bathrooms").
        h1 = soup.find(['h1', 'h2'])
        h1t = h1.get_text(' ', strip=True) if h1 else ''
        bedrooms, bathrooms = 0, 0
        bm = re.search(r'(\d+)\s*bedroom', h1t, re.I)
        if bm:
            bedrooms = int(bm.group(1))
        bam = re.search(r'(\d+)\s*bathroom', h1t, re.I)
        if bam:
            bathrooms = int(bam.group(1))
        # Clean unit-type label (e.g. "Deluxe 4 Bedrooms 1 Bathroom").
        unit_type = ''
        utm = re.search(r'((?:Standard|Deluxe|Premium|Economy|Studio)?\s*\d+\s*Bedrooms?\s*\d+\s*Bathrooms?)',
                        h1t, re.I)
        if utm:
            unit_type = utm.group(1).strip()

        # Address: first street-like token in the page.
        address = ''
        am = STREET_RE.search(page_text)
        if am:
            address = am.group(0).strip()
            if 'ithaca' not in address.lower():
                address = f"{address}, Ithaca, NY"

        # Pricing: values are per bed across lease terms; record the minimum
        # as the starting per-bed rate and derive an approximate total.
        prices = [int(p.replace(',', '')) for p in re.findall(r'[$]([\d,]{3,5})', page_text)]
        prices = [p for p in prices if 300 <= p <= 4000]
        per_bed = min(prices) if prices else 0
        total = per_bed * bedrooms if (per_bed and bedrooms) else per_bed

        # Description: the longest paragraph.
        paras = [p.get_text(' ', strip=True) for p in soup.find_all('p')
                 if len(p.get_text(strip=True)) > 50]
        description = max(paras, key=len) if paras else ''

        t = page_text.lower()
        amenities = {
            'laundry': 'in-unit' if 'in-unit laundry' in t or 'in unit laundry' in t
                       else ('on-site' if 'laundry' in t else None),
            'parking': 'off-street' if 'parking' in t else None,
            'furnished': 'furnished' in t,
            'air_conditioning': 'air conditioning' in t or 'central air' in t,
            'dishwasher': 'dishwasher' in t,
            'internet_included': 'high-speed internet' in t or 'internet included' in t,
            'no_smoking': 'non-smoking' in t or 'no smoking' in t,
        }

        images, seen = [], set()
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src') or ''
            if 'rentmanager' in src or 'uploads' in src:
                if 'logo' in src.lower():
                    continue
                key = re.sub(r'[?&].*$', '', src)
                if key not in seen:
                    seen.add(key)
                    images.append(src)
        images = images[:10]

        return {
            'id': uid,
            'title': (f"{address} ({unit_type})" if address and unit_type
                      else (address or unit_type or 'Ithaca Renting unit')),
            'url': url,
            'description': description[:1000],
            'posted_date': datetime.now().isoformat(),
            'pricing': {
                'monthly_rent_total': total,
                'per_person_monthly': per_bed,  # explicitly per-bed from IRC
                'rent_period': 'monthly',
            },
            'housing': {'bedrooms': bedrooms, 'bathrooms': bathrooms, 'sqft': 0},
            'amenities': amenities,
            'coordinates': {},
            'address': address,
            'images': images,
            'category': area,
        }


if __name__ == '__main__':
    s = IthacaRentingScraper()
    listings = s.scrape()
    print(f"\nScraped {len(listings)} Ithaca Renting listings")
    for l in listings[:8]:
        h, p = l['housing'], l['pricing']
        print(f"  - {l['address'][:32]:34} {h['bedrooms']}BR/{h['bathrooms']}BA  "
              f"${p['per_person_monthly']}/bed  imgs={len(l['images'])}")

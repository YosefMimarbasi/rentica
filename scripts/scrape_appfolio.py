"""Generic AppFolio listings scraper.

Many Ithaca property managers (PPM Homes, Travis Hyde, ...) embed an
AppFolio listings widget on their site. AppFolio serves a fully-rendered
public listings page at ``https://<portal>.appfolio.com/listings`` where
each unit carries its address (image alt text), rent, bed/bath, photo, and
a detail-page link. This scraper parses that index for any portal.
"""
import re
import time
import logging
from datetime import datetime
from bs4 import BeautifulSoup
from scraper_base import BaseScraper

logger = logging.getLogger(__name__)

# Known Ithaca-area AppFolio portals -> friendly source name.
APPFOLIO_PORTALS = {
    'ppmhomes': 'ppmhomes',
    'travishyde': 'travishyde',
    'mlr': 'modernliving',  # Modern Living Rentals (Collegetown)
    'mollprop': 'moll',  # Moll Properties
    'ithacalivingsolutions': 'ithacalivingsolutions',  # Ithaca Living Solutions
}


class AppFolioScraper(BaseScraper):
    """Scrape an AppFolio listings portal."""

    def __init__(self, portal: str, source_name: str = None):
        self.portal = portal
        super().__init__(source_name or f'appfolio_{portal}',
                         f'https://{portal}.appfolio.com')
        self.listing_url = f'{self.base_url}/listings'

    def scrape(self) -> list:
        logger.info(f"Starting AppFolio scrape ({self.portal})...")
        try:
            resp = self.session.get(self.listing_url, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"AppFolio scrape failed for {self.portal}: {e}")
            return []

        # lxml handles AppFolio's malformed markup far better than
        # html.parser (which silently stops after the first listing-item).
        try:
            soup = BeautifulSoup(resp.content, 'lxml')
        except Exception:
            soup = BeautifulSoup(resp.content, 'html.parser')

        # Dedupe by the listing's DOM id (AppFolio renders mobile + desktop
        # variants of each card).
        seen = set()
        items = soup.find_all('div', class_='listing-item')
        for item in items:
            lid = item.get('id', '')
            if lid and lid in seen:
                continue
            if lid:
                seen.add(lid)
            try:
                listing = self._parse_item(item)
                addr = (listing or {}).get('address', '')
                # Require a real street address (digit + street + Ithaca), not
                # leftover card text or a drop-box note.
                if listing and re.search(r'\d', addr) and 'ithaca' in addr.lower():
                    self.listings.append(listing)
            except Exception as e:
                logger.warning(f"Error parsing AppFolio item: {e}")

        logger.info(f"Successfully scraped {len(self.listings)} listings from {self.portal}")
        self.save_raw_data(self.listings, f'{self.source_name}_raw.json')
        return self.listings

    def _parse_item(self, item) -> dict:
        # --- Detail URL ---
        a = item.find('a', href=True)
        url = ''
        if a:
            href = a['href']
            url = href if href.startswith('http') else self.base_url + href

        # --- Address (from image alt) ---
        img = item.find('img')
        address = ''
        image = ''
        if img:
            address = (img.get('alt') or '').strip()
            # AppFolio uses alt="No photo" on image-less cards.
            if address.lower().startswith('no photo'):
                address = ''
            image = img.get('data-original') or img.get('data-src') or ''
            if image.startswith('//'):
                image = 'https:' + image
            if 'place_holder' in image or 'no_ph' in image:
                image = ''

        # Address fallback: pull "<street>, Ithaca, NY <zip>" from the card
        # text when there's no usable image alt.
        if not address:
            m = re.search(r'(\d{1,5}\s+[A-Z][\w .,#&/-]+?,\s*Ithaca,\s*NY\s*\d{5})',
                          item.get_text(' ', strip=True))
            if m:
                address = re.sub(r'\s*-\s*Drop Box', '', m.group(1)).strip()

        # --- Rent ---
        price = 0
        rent_el = item.find(class_=re.compile('js-listing-blurb-rent'))
        if not rent_el:
            rent_el = item.find(class_=re.compile('rent'))
        if rent_el:
            m = re.search(r'[\$]([\d,]+)', rent_el.get_text())
            if m:
                price = int(m.group(1).replace(',', ''))

        # --- Bed / Bath ---
        bedrooms, bathrooms = 0, 0
        bb_el = item.find(class_=re.compile('js-listing-blurb-bed-bath'))
        bb_text = bb_el.get_text(' ', strip=True) if bb_el else item.get_text(' ', strip=True)
        bm = re.search(r'(\d+)\s*bd', bb_text, re.I)
        if bm:
            bedrooms = int(bm.group(1))
        elif re.search(r'studio', bb_text, re.I):
            bedrooms = 0
        bam = re.search(r'(\d+(?:\.\d+)?)\s*ba', bb_text, re.I)
        if bam:
            v = float(bam.group(1))
            bathrooms = int(v) if v.is_integer() else v

        # --- Square footage (sometimes in quick facts) ---
        sqft = 0
        sm = re.search(r'([\d,]{3,5})\s*(?:sq\.?\s*ft|ft²)', item.get_text(' ', strip=True), re.I)
        if sm:
            sqft = int(sm.group(1).replace(',', ''))

        # --- Available date ---
        available = ''
        avm = re.search(r'available[:\s]+([A-Za-z0-9 ,/]+)', item.get_text(' ', strip=True), re.I)
        if avm:
            available = avm.group(1).strip()[:30]

        # Ensure address has city context for geocoding.
        if address and 'ithaca' not in address.lower() and ', NY' not in address:
            address = f"{address}, Ithaca, NY"

        return {
            'id': item.get('id', '').replace('listing_', ''),
            'title': address,
            'url': url,
            'description': '',
            'posted_date': datetime.now().isoformat(),
            'pricing': {'monthly_rent_total': price, 'rent_period': 'monthly'},
            'housing': {'bedrooms': bedrooms, 'bathrooms': bathrooms,
                        'sqft': sqft, 'available': available},
            'amenities': {},
            'coordinates': {},
            'address': address,
            'images': [image] if image else [],
        }


def scrape_all_appfolio() -> dict:
    """Convenience: scrape every known portal, return {source: listings}."""
    out = {}
    for portal, name in APPFOLIO_PORTALS.items():
        out[name] = AppFolioScraper(portal, name).scrape()
        time.sleep(1)
    return out


if __name__ == '__main__':
    for portal, name in APPFOLIO_PORTALS.items():
        s = AppFolioScraper(portal, name)
        listings = s.scrape()
        print(f"\n{name}: {len(listings)} listings")
        for l in listings[:5]:
            h, p = l['housing'], l['pricing']
            print(f"  - {l['address'][:40]:42} ${p['monthly_rent_total']:>5}  "
                  f"{h['bedrooms']}BR/{h['bathrooms']}BA")

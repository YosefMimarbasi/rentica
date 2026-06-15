"""Comprehensive Craigslist apartment scraper for Ithaca.

Scrapes the static search results to collect every listing URL across the
housing categories students care about (apartments, rooms/shared, sublets),
then visits each detail page to extract the full record: price, bed/bath,
square footage, structured amenities (laundry, parking, pets, A/C, etc.),
geo-coordinates, cross-street address, the full posting body, all photos,
and posting/updated timestamps.
"""
import re
import time
import logging
from datetime import datetime
from bs4 import BeautifulSoup
from scraper_base import BaseScraper

logger = logging.getLogger(__name__)

# Craigslist housing categories relevant to students.
#   apa = apartments / housing for rent
#   roo = rooms & shares
#   sub = sublets & temporary
CATEGORIES = ['apa', 'roo', 'sub']

# Polite delay between detail-page requests (seconds).
DETAIL_DELAY = 1.0


class CraigslistScraper(BaseScraper):
    """Scrape apartments from Craigslist Ithaca with full detail extraction."""

    def __init__(self, max_listings: int = None):
        super().__init__('craigslist', 'https://ithaca.craigslist.org')
        # Cap for testing / partial runs; None = scrape everything.
        self.max_listings = max_listings

    # ------------------------------------------------------------------ #
    # Phase 1: collect listing URLs from the static search pages
    # ------------------------------------------------------------------ #
    def _collect_listing_urls(self) -> list:
        """Gather unique listing URLs across all housing categories."""
        urls = {}  # url -> {category, location, list_price}

        for category in CATEGORIES:
            search_url = f'{self.base_url}/search/{category}'
            try:
                resp = self.session.get(search_url, timeout=15)
                resp.raise_for_status()
            except Exception as e:
                logger.warning(f"Could not fetch search page {search_url}: {e}")
                continue

            soup = BeautifulSoup(resp.content, 'html.parser')
            items = soup.find_all('li', class_='cl-static-search-result')
            logger.info(f"Category '{category}': found {len(items)} static results")

            for item in items:
                link = item.find('a')
                if not link:
                    continue
                href = link.get('href', '')
                if not href or href in urls:
                    continue

                price_el = item.find('div', class_='price')
                loc_el = item.find('div', class_='location')
                urls[href] = {
                    'category': category,
                    'list_location': loc_el.get_text(strip=True) if loc_el else '',
                    'list_price': price_el.get_text(strip=True) if price_el else '',
                }

            time.sleep(0.5)

        logger.info(f"Collected {len(urls)} unique listing URLs total")
        return [(u, meta) for u, meta in urls.items()]

    # ------------------------------------------------------------------ #
    # Phase 2: scrape each detail page
    # ------------------------------------------------------------------ #
    def scrape(self) -> list:
        """Scrape all listings (URLs + full detail pages)."""
        logger.info("Starting comprehensive Craigslist scrape...")

        url_list = self._collect_listing_urls()
        if self.max_listings:
            url_list = url_list[:self.max_listings]
            logger.info(f"Limiting to first {self.max_listings} listings")

        total = len(url_list)
        for i, (url, meta) in enumerate(url_list, 1):
            try:
                listing = self._scrape_detail(url, meta)
                if listing:
                    self.listings.append(listing)
                if i % 25 == 0 or i == total:
                    logger.info(f"  ...scraped {i}/{total} detail pages")
            except Exception as e:
                logger.warning(f"Error scraping {url}: {e}")
            time.sleep(DETAIL_DELAY)

        logger.info(f"Successfully scraped {len(self.listings)} full listings")
        self.save_raw_data(self.listings, 'craigslist_raw.json')
        return self.listings

    def _scrape_detail(self, url: str, meta: dict) -> dict:
        """Fetch a listing detail page and extract the complete record."""
        resp = self.session.get(url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, 'html.parser')

        # --- Title ---
        title_el = soup.find('span', id='titletextonly')
        title = title_el.get_text(strip=True) if title_el else meta.get('list_location', '')

        # --- Price ---
        price = 0
        price_el = soup.find('span', class_='price')
        if price_el:
            price = self._parse_price(price_el.get_text())
        elif meta.get('list_price'):
            price = self._parse_price(meta['list_price'])

        # --- Attributes (bed/bath/sqft/amenities/etc.) ---
        attr_texts = []
        for grp in soup.find_all('p', class_='attrgroup'):
            for el in grp.find_all(['span', 'div', 'b']):
                t = el.get_text(' ', strip=True)
                if t:
                    attr_texts.append(t)
            # also capture the group's own text in case of flat structure
            grp_txt = grp.get_text(' ', strip=True)
            if grp_txt:
                attr_texts.append(grp_txt)
        # BR/BA/sqft live in <span class="attr important"> and other
        # attributes in various tags carrying the "attr" class.
        for el in soup.find_all(class_='attr'):
            t = el.get_text(' ', strip=True)
            if t:
                attr_texts.append(t)
        # The compact housing span (e.g. "/ 2br - 1000ft2 -") is a reliable
        # fallback for bed count and square footage.
        housing_span = soup.find('span', class_='housing')
        if housing_span:
            attr_texts.append(housing_span.get_text(' ', strip=True))

        attr_blob = ' \n '.join(attr_texts)
        bedrooms, bathrooms = self._parse_beds_baths(attr_blob)
        sqft = self._parse_sqft(attr_blob)
        amenities = self._parse_amenities(attr_blob)
        available = self._parse_available(attr_blob)
        rent_period = self._parse_rent_period(attr_blob)

        # --- Geo coordinates + accuracy ---
        coordinates = {}
        map_el = soup.find('div', id='map')
        if map_el:
            try:
                lat = float(map_el.get('data-latitude'))
                lng = float(map_el.get('data-longitude'))
                coordinates = {
                    'lat': round(lat, 6),
                    'lng': round(lng, 6),
                    'accuracy': map_el.get('data-accuracy', ''),
                }
            except (TypeError, ValueError):
                pass

        # --- Address (cross-street) ---
        address = meta.get('list_location', '')
        addr_el = soup.find('div', class_='mapaddress')
        if addr_el:
            address = addr_el.get_text(strip=True)
        elif meta.get('list_location'):
            address = meta['list_location']

        # --- Full description body ---
        description = ''
        body_el = soup.find('section', id='postingbody')
        if body_el:
            # Remove the "QR Code Link to This Post" boilerplate node.
            for qr in body_el.find_all('div', class_='print-qrcode-container'):
                qr.decompose()
            description = body_el.get_text(' ', strip=True)
            description = description.replace('QR Code Link to This Post', '').strip()

        # --- Images (dedupe, prefer full-size 600x450) ---
        images = []
        seen_img = set()
        for img in soup.find_all('img'):
            src = img.get('src', '')
            if not src or 'craigslist.org' not in src:
                continue
            # Skip tiny thumbnails (50x50c).
            if '50x50c' in src:
                continue
            # Normalize key by image id to avoid dupes across sizes.
            key = re.sub(r'_\d+x\d+', '', src)
            if key in seen_img:
                continue
            seen_img.add(key)
            images.append(src)

        # --- Posting / updated timestamps + post id ---
        posted_date = ''
        updated_date = ''
        for t in soup.find_all('time'):
            dt = t.get('datetime', '')
            cls = ' '.join(t.get('class', []))
            if 'updated' in cls or 'timeago' in cls:
                updated_date = updated_date or dt
            posted_date = posted_date or dt
        post_id = ''
        m = re.search(r'/(\d+)\.html', url)
        if m:
            post_id = m.group(1)

        return {
            'id': post_id,
            'title': title,
            'url': url,
            'category': meta.get('category', ''),
            'description': description,
            'posted_date': posted_date or datetime.now().isoformat(),
            'updated_date': updated_date,
            'pricing': {
                'monthly_rent_total': price,
                'rent_period': rent_period,
            },
            'housing': {
                'bedrooms': bedrooms,
                'bathrooms': bathrooms,
                'sqft': sqft,
                'available': available,
            },
            'amenities': amenities,
            'coordinates': coordinates,
            'address': address,
            'images': images,
            'attributes_raw': attr_texts,
        }

    # ------------------------------------------------------------------ #
    # Parsing helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _parse_price(text: str) -> int:
        m = re.search(r'\$?\s*([\d,]+)', text or '')
        if m:
            try:
                return int(m.group(1).replace(',', ''))
            except ValueError:
                return 0
        return 0

    @staticmethod
    def _parse_beds_baths(text: str) -> tuple:
        beds, baths = 0, 0
        bm = re.search(r'(\d+)\s*BR', text, re.I)
        if bm:
            beds = int(bm.group(1))
        # Bathrooms may be "1Ba", "1.5Ba", or "shared".
        bam = re.search(r'(\d+(?:\.\d+)?)\s*Ba', text, re.I)
        if bam:
            baths = float(bam.group(1))
            baths = int(baths) if baths.is_integer() else baths
        return beds, baths

    @staticmethod
    def _parse_sqft(text: str) -> int:
        # Craigslist renders square footage as "1000ft2" but the trailing
        # "2" is a superscript, so the extracted text is often "1000ft 2".
        m = re.search(r'(\d{2,5})\s*ft\s*2', text, re.I)
        if m:
            return int(m.group(1))
        return 0

    @staticmethod
    def _parse_available(text: str) -> str:
        m = re.search(r'available\s+([a-z0-9 ,/-]+)', text, re.I)
        if m:
            return m.group(1).strip().split('\n')[0][:40]
        return ''

    @staticmethod
    def _parse_rent_period(text: str) -> str:
        m = re.search(r'rent period:\s*(\w+)', text, re.I)
        return m.group(1).lower() if m else 'monthly'

    @staticmethod
    def _parse_amenities(text: str) -> dict:
        t = text.lower()
        amenities = {}

        # Laundry
        if 'w/d in unit' in t or 'in-unit laundry' in t or 'laundry in unit' in t:
            amenities['laundry'] = 'in-unit'
        elif 'laundry in bldg' in t or 'laundry in building' in t:
            amenities['laundry'] = 'in-building'
        elif 'w/d hookups' in t:
            amenities['laundry'] = 'hookups'
        elif 'laundry on site' in t or 'laundry on-site' in t:
            amenities['laundry'] = 'on-site'
        elif 'no laundry' in t:
            amenities['laundry'] = 'none'

        # Parking
        if 'attached garage' in t:
            amenities['parking'] = 'attached-garage'
        elif 'detached garage' in t:
            amenities['parking'] = 'detached-garage'
        elif 'off-street parking' in t:
            amenities['parking'] = 'off-street'
        elif 'street parking' in t:
            amenities['parking'] = 'street'
        elif 'carport' in t:
            amenities['parking'] = 'carport'
        elif 'valet parking' in t:
            amenities['parking'] = 'valet'
        elif 'no parking' in t:
            amenities['parking'] = 'none'

        # Pets
        amenities['cats_ok'] = 'cats are ok' in t or 'cats ok' in t
        amenities['dogs_ok'] = 'dogs are ok' in t or 'dogs ok' in t

        # Other flags
        amenities['furnished'] = 'furnished' in t
        amenities['air_conditioning'] = ('air conditioning' in t or
                                         'a/c' in t or 'central air' in t)
        amenities['wheelchair_accessible'] = 'wheelchair accessible' in t
        amenities['ev_charging'] = 'ev charging' in t or 'electric vehicle' in t
        amenities['no_smoking'] = 'no smoking' in t

        # Housing type
        for htype in ['apartment', 'house', 'townhouse', 'condo', 'duplex',
                      'cottage', 'loft', 'flat', 'in-law']:
            if htype in t:
                amenities['housing_type'] = htype
                break

        return amenities


if __name__ == '__main__':
    import sys
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    scraper = CraigslistScraper(max_listings=limit)
    listings = scraper.scrape()
    print(f"\nScraped {len(listings)} listings from Craigslist")
    for listing in listings[:5]:
        h = listing.get('housing', {})
        p = listing.get('pricing', {})
        print(f"  - {listing.get('title', '')[:50]}")
        print(f"      ${p.get('monthly_rent_total')}  "
              f"{h.get('bedrooms')}BR/{h.get('bathrooms')}BA  "
              f"{h.get('sqft')}ft2  {listing.get('address', '')[:40]}")

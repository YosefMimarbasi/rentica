"""Craigslist apartment scraper for Ithaca."""
import time
import logging
from datetime import datetime
from bs4 import BeautifulSoup
from scraper_base import BaseScraper

logger = logging.getLogger(__name__)


class CraigslistScraper(BaseScraper):
    """Scrape apartments from Craigslist Ithaca."""

    def __init__(self):
        super().__init__('craigslist', 'https://ithaca.craigslist.org')
        self.search_url = 'https://ithaca.craigslist.org/search/apt'

    def scrape(self) -> list:
        """Scrape all apartment listings from Craigslist Ithaca."""
        logger.info("Starting Craigslist scrape...")

        try:
            # Get search results
            params = {
                'query': '',
                'sort': 'date',
                'min_price': '',
                'max_price': ''
            }

            response = self.session.get(self.search_url, params=params, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')
            listings_html = soup.find_all('li', class_='cl-static-search-result')

            logger.info(f"Found {len(listings_html)} listings on first page")

            for i, item in enumerate(listings_html):
                try:
                    listing = self._parse_listing(item)
                    if listing:
                        self.listings.append(listing)
                        logger.debug(f"Parsed listing {i+1}: {listing.get('title', 'Unknown')}")
                except Exception as e:
                    logger.warning(f"Error parsing listing {i+1}: {e}")
                    continue

                # Rate limiting
                time.sleep(0.5)

            logger.info(f"Successfully scraped {len(self.listings)} listings")

        except Exception as e:
            logger.error(f"Craigslist scrape failed: {e}")
            return []

        # Save raw data
        self.save_raw_data(self.listings, 'craigslist_raw.json')

        # Normalize and return
        return self.process_listings()

    def _parse_listing(self, item) -> dict:
        """Parse a single listing from HTML."""
        try:
            title_elem = item.find('span', class_='txt')
            title = title_elem.text.strip() if title_elem else 'Unknown'

            url_elem = item.find('a', class_='redd')
            url = url_elem.get('href', '') if url_elem else ''

            price_elem = item.find('span', class_='priceinfo')
            price_text = price_elem.text.strip() if price_elem else '$0'
            price = int(price_text.replace('$', '').split()[0])

            date_elem = item.find('time')
            posted_date = date_elem.get('datetime', '') if date_elem else datetime.now().isoformat()

            # Extract details from title (format: #BR/BA - size - location)
            details = title.split(' - ')

            bedrooms = 0
            bathrooms = 0
            if len(details) > 0:
                br_ba = details[0].strip()
                if '/' in br_ba:
                    parts = br_ba.split('/')
                    bedrooms = int(parts[0].replace('br', '').strip()) if 'br' in parts[0].lower() else 0
                    bathrooms = int(parts[1].replace('ba', '').strip()) if 'ba' in parts[1].lower() else 0

            location = details[-1].strip() if len(details) > 1 else 'Unknown'

            return {
                'id': url.split('/')[-1] if url else '',
                'title': title,
                'url': url,
                'description': '',  # Craigslist requires separate request for details
                'posted_date': posted_date,
                'pricing': {
                    'monthly_rent_total': price,
                },
                'housing': {
                    'bedrooms': bedrooms,
                    'bathrooms': bathrooms,
                },
                'address': location,
            }

        except Exception as e:
            logger.error(f"Error parsing listing: {e}")
            return None

    def scrape_listing_details(self, url: str) -> dict:
        """Scrape full listing details from URL."""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract full description
            description_elem = soup.find('section', id='postingbody')
            description = description_elem.text.strip() if description_elem else ''

            # Extract images
            images = []
            for img in soup.find_all('img', class_='thumb'):
                src = img.get('src', '')
                if src:
                    images.append(src)

            return {
                'description': description,
                'images': images,
            }

        except Exception as e:
            logger.warning(f"Could not scrape listing details from {url}: {e}")
            return {}


if __name__ == '__main__':
    scraper = CraigslistScraper()
    listings = scraper.scrape()
    print(f"Scraped {len(listings)} listings from Craigslist")
    for listing in listings[:5]:
        print(f"  - {listing.get('title')}: ${listing.get('pricing', {}).get('monthly_rent_total', 0)}")

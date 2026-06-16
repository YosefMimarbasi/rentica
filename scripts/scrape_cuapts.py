"""CUAPTS (cuapts.org) scraper — Cornell DTI apartment review platform.

CUAPTS exposes a clean, keyless public REST API on its own domain. We pull
every building plus the data layers Rentaca wants and that CUAPTS itself
surfaces: photos, per-building reviews with detailed star ratings, the
landlord/owner (name + website/contact), and travel times to campus.

Endpoints used (all GET, no auth, JSON):
  /api/page-data/1/<size>            -> all buildings + numReviews/avgRating/avgPrice/company
  /api/review/aptId/<id>/APPROVED    -> approved reviews for a building
  /api/landlord/<id>                 -> landlord name + contact (website)
  /api/travel-times-by-id/<id>       -> travel times to campus

This is the canonical "reviews/stars + owner info" source. Building photos
are Firebase-hosted CDN URLs returned inline.
"""
import time
import logging
from datetime import datetime
from scraper_base import BaseScraper

logger = logging.getLogger(__name__)

API = "https://www.cuapts.org/api"
AREA_MAP = {
    "COLLEGETOWN": "Collegetown", "WEST": "West Campus", "NORTH": "North Campus",
    "DOWNTOWN": "Downtown", "OTHER": "Other",
}


class CuaptsScraper(BaseScraper):
    """Scrape every building on cuapts.org with reviews + landlord + photos."""

    def __init__(self):
        super().__init__("cuapts", "https://www.cuapts.org")
        self._landlord_cache = {}

    def _get(self, path, default=None):
        try:
            r = self.session.get(f"{API}/{path}", timeout=25)
            if r.status_code == 200 and r.text.strip():
                return r.json()
        except Exception as e:
            logger.warning(f"GET {path} failed: {e}")
        return default

    def _landlord(self, lid):
        if not lid:
            return {}
        if lid not in self._landlord_cache:
            self._landlord_cache[lid] = self._get(f"landlord/{lid}", {}) or {}
            time.sleep(0.3)
        return self._landlord_cache[lid]

    def scrape(self) -> list:
        logger.info("Starting CUAPTS scrape...")
        page = self._get("page-data/1/5000", {})
        buildings = page.get("buildingData", []) if page else []
        logger.info(f"CUAPTS returned {len(buildings)} buildings")

        for i, entry in enumerate(buildings):
            try:
                self.listings.append(self._build(entry))
            except Exception as e:
                logger.warning(f"Error parsing CUAPTS building: {e}")
            if (i + 1) % 25 == 0:
                logger.info(f"  ...processed {i + 1}/{len(buildings)}")
            time.sleep(0.25)

        logger.info(f"Successfully scraped {len(self.listings)} CUAPTS listings")
        self.save_raw_data(self.listings, "cuapts_raw.json")
        return self.listings

    def _build(self, entry) -> dict:
        bd = entry.get("buildingData", {})
        bid = bd.get("id", "")
        lid = bd.get("landlordId", "")

        # Reviews + detailed star ratings
        reviews_raw = self._get(f"review/aptId/{bid}/APPROVED", []) or []
        time.sleep(0.25)
        reviews = []
        cat_totals, cat_counts = {}, {}
        review_photos = []
        for rv in reviews_raw:
            dr = rv.get("detailedRatings", {}) or {}
            for k, v in dr.items():
                if isinstance(v, (int, float)):
                    cat_totals[k] = cat_totals.get(k, 0) + v
                    cat_counts[k] = cat_counts.get(k, 0) + 1
            review_photos.extend(rv.get("photos", []) or [])
            reviews.append({
                "date": rv.get("date", ""),
                "overall_rating": rv.get("overallRating", 0),
                "detailed_ratings": dr,
                "text": rv.get("reviewText", ""),
                "likes": rv.get("likes", 0),
                "photos": rv.get("photos", []) or [],
            })
        cat_avgs = {k: round(cat_totals[k] / cat_counts[k], 2)
                    for k in cat_totals if cat_counts[k]}

        # Landlord / owner
        ll = self._landlord(lid)
        contact = {}
        if ll:
            contact = {
                "company": ll.get("name", "") or entry.get("company", ""),
                "owner_website": ll.get("contact", ""),
                "landlord_avg_rating": ll.get("avgRating", 0),
                "landlord_id": lid,
            }
        elif entry.get("company"):
            contact = {"company": entry["company"], "landlord_id": lid}

        # Travel times to campus
        travel = self._get(f"travel-times-by-id/{bid}", {}) or {}
        time.sleep(0.2)

        photos = list(bd.get("photos", []) or []) + review_photos
        area = AREA_MAP.get(bd.get("area", ""), bd.get("area", ""))
        addr = bd.get("address", "") or bd.get("name", "")
        if addr and "ithaca" not in addr.lower() and ", NY" not in addr:
            addr = f"{addr}, Ithaca, NY"

        return {
            "id": bid,
            "title": bd.get("name", "") or bd.get("address", ""),
            "description": "",
            "address": addr,
            "url": f"https://www.cuapts.org/apartment/{bid}",
            "posted_date": datetime.now().isoformat(),
            "coordinates": {"lat": bd.get("latitude"), "lng": bd.get("longitude")},
            "housing": {
                "bedrooms": bd.get("numBeds", 0),
                "bathrooms": bd.get("numBaths", 0),
                "area": area,
            },
            "pricing": {
                "monthly_rent_total": entry.get("avgPrice", 0) or 0,
                "rent_period": "monthly",
            },
            "amenities": {},
            "contact": contact,
            "images": photos,
            # CUAPTS-specific value: ratings + reviews
            "ratings": {
                "avg_rating": entry.get("avgRating", 0),
                "num_reviews": entry.get("numReviews", 0),
                "category_averages": cat_avgs,
            },
            "reviews": reviews,
            "travel_times": travel,
        }

    def normalize_listing(self, raw) -> dict:
        base = super().normalize_listing(raw)
        # Preserve CUAPTS-specific layers.
        base["ratings"] = raw.get("ratings", {})
        base["reviews"] = raw.get("reviews", [])
        base["travel_times"] = raw.get("travel_times", {})
        base["address"] = raw.get("address", "")
        base["coordinates"] = raw.get("coordinates", {})
        base["housing"] = raw.get("housing", {})
        base["pricing"] = raw.get("pricing", {})
        base["contact"] = raw.get("contact", {})
        base["title"] = raw.get("title", "")
        base["listing_info"]["url"] = raw.get("url", "")
        base["listing_info"]["images"] = raw.get("images", [])
        return base


if __name__ == "__main__":
    s = CuaptsScraper()
    listings = s.scrape()
    print(f"\ncuapts: {len(listings)} listings")
    withrev = sum(1 for l in listings if l["ratings"]["num_reviews"])
    withimg = sum(1 for l in listings if l["images"])
    print(f"  with reviews: {withrev}   with images: {withimg}")
    for l in listings[:5]:
        r = l["ratings"]
        print(f"  - {l['address'][:38]:40} {r['avg_rating']}\u2605 "
              f"({r['num_reviews']} rev)  {len(l['images'])} imgs")

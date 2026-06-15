# Rentica - Ithaca Apartment Database

A comprehensive, student-friendly apartment and housing database for Ithaca, NY. This project aggregates rental information from multiple sources to help students find housing that meets their needs.

## Project Goal

Create the most complete apartment database for Ithaca by scraping and aggregating data from all available online sources, including:

- Craigslist
- Facebook Marketplace
- Local Ithaca rental websites
- University housing resources
- Google Maps/Search data
- Local landlord directories

## Data Included

For each listing, we collect:

### Location & Building Info
- Full address with GPS coordinates
- Distance to Cornell/Ithaca College
- Neighborhood/area
- Building age and condition
- Property type (apartment, house, dorm, etc.)

### Housing Details
- Number of bedrooms
- Number of bathrooms
- Total square footage
- Floor level
- Furnished/unfurnished

### Pricing
- Monthly rent (total)
- Cost per person per month
- Lease term options
- Security deposit
- Pet deposits/fees
- Utility costs (if available)
- Internet included (yes/no)

### Amenities
- Parking (yes/no, type, cost)
- Laundry (in-unit, in-building, off-site)
- Air conditioning
- Heating type
- Kitchen appliances
- Dishwasher
- Balcony/patio
- Basement/storage
- Garden/outdoor space

### Tenant Requirements
- Lease length options
- Move-in date
- Pet policy (species, size limits, fees)
- Income requirements
- Credit score requirements
- Background check requirements
- Guarantor/co-signer requirements

### Logistics
- Listing posted date
- Last updated date
- Contact information (name, phone, email)
- Landlord/management company
- Application requirements
- Application fees
- Showing schedule

### Images & Virtual Tours
- Photo URLs
- Virtual tour links
- 3D maps
- Neighborhood photos

## Data Format

All data is stored in JSON format in the `/data` directory:
- `apartments.json` - Main comprehensive database
- Source-specific files for raw data before normalization

### Sample Entry

```json
{
  "id": "apt-12345",
  "source": "craigslist",
  "title": "3BR/2BA apartment near Commons",
  "description": "Spacious apartment with modern kitchen",
  "address": "123 Main St, Ithaca, NY 14850",
  "coordinates": {
    "lat": 42.4534,
    "lng": -76.4735
  },
  "housing": {
    "type": "apartment",
    "bedrooms": 3,
    "bathrooms": 2,
    "sqft": 1200,
    "furnished": false,
    "floor": 2
  },
  "pricing": {
    "monthly_rent_total": 2100,
    "per_person_monthly": 700,
    "security_deposit": 2100,
    "utilities_included": false,
    "internet_included": true
  },
  "amenities": {
    "parking": "street",
    "parking_cost": 0,
    "laundry": "in-building",
    "ac": true,
    "heating": "forced-air",
    "dishwasher": false,
    "balcony": false
  },
  "requirements": {
    "lease_length_months": 12,
    "move_in_date": "2024-08-15",
    "pets_allowed": true,
    "pet_types": ["dogs", "cats"],
    "pet_size_limit_lbs": 50,
    "min_income_multiplier": 40
  },
  "contact": {
    "landlord_name": "John Smith",
    "phone": "607-XXX-XXXX",
    "email": "john@example.com",
    "company": "Smith Properties"
  },
  "listing_info": {
    "posted_date": "2024-06-01",
    "last_updated": "2024-06-15",
    "url": "https://...",
    "images": ["url1", "url2"]
  },
  "distance_to_cornell_miles": 1.5,
  "distance_to_ithaca_college_miles": 2.0
}
```

## Directory Structure

```
rentica/
├── README.md                 # This file
├── data/
│   ├── apartments.json       # Main comprehensive database
│   ├── raw/                  # Raw data from each source
│   │   ├── craigslist.json
│   │   ├── facebook.json
│   │   ├── airbnb.json
│   │   └── ...
│   └── processed/            # Cleaned and normalized data
├── scripts/
│   ├── scrape_craigslist.py
│   ├── scrape_facebook.py
│   ├── scrape_airbnb.py
│   ├── normalize_data.py     # Standardize all data
│   ├── deduplicate.py        # Remove duplicate listings
│   ├── geocode.py            # Add coordinates
│   ├── calculate_distances.py # Add distances to universities
│   └── build_database.py     # Combine all sources
├── tools/
│   ├── search.py             # Query the database
│   └── analyze.py            # Generate statistics
└── .gitignore
```

## How to Use This Data

### Search by Filters
```
python tools/search.py --max-price 800 --bedrooms 2 --parking
```

### View Statistics
```
python tools/analyze.py --neighborhood commons
```

### Access the JSON
All data is available in structured JSON format for direct analysis.

## Data Sources

- **Craigslist**: Ithaca housing section
- **Facebook Marketplace**: Ithaca area
- **Airbnb**: Long-term stays
- **Google Maps**: Business listings, verified info
- **Direct landlord websites**: Local property management companies
- **University Resources**: Cornell/IC housing

## Contributing

Found a missing listing? Have data to add? Create an issue or submit a pull request.

## Data Accuracy

Last comprehensive scrape: [DATE]
- Total listings: [COUNT]
- Date range: [START] to [END]

Note: This data is aggregated from public sources. Always verify current information with landlords before applying.

## Legal

This project collects publicly available information. All data is provided as-is. Users should verify all information directly with landlords and conduct proper due diligence before signing leases.

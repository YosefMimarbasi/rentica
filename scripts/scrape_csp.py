#!/usr/bin/env python
"""Scrape CSP Management rentals (Buildium portal) -> data/raw/csp_raw.json"""
import re, json, time, html as ihtml
import urllib.request

BASE = "https://cspmgmt.managebuilding.com"
LIST_URL = BASE + "/Resident/public/rentals"
HDRS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
LOGO = "83dd0650d47a4f54868cfa99deb823ac"  # site logo, exclude


def fetch(url):
    req = urllib.request.Request(url, headers=HDRS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "ignore")


def clean(s):
    return ihtml.unescape(re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", s))).strip()


def get_listing_ids(html):
    ids = re.findall(r"/Resident/public/rentals/(\d+)", html)
    seen, out = set(), []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def parse_listing(lid, html):
    body = re.sub(r"<script.*?</script>", "", html, flags=re.S)
    body = re.sub(r"<style.*?</style>", "", body, flags=re.S)

    # Title + address from H tags
    htags = [clean(m) for m in re.findall(r"<h[1-4][^>]*>(.*?)</h[1-4]>", body, re.S)]
    htags = [h for h in htags if h]
    title = htags[0] if htags else ""
    # address line usually next h tag matching city/zip
    addr = ""
    for h in htags[1:4]:
        if re.search(r"\b(NY|Ithaca)\b|\d{5}", h):
            addr = h
            break
    street = title.split(" - ")[0].strip()
    if addr:
        address = f"{street}, {addr}"
    else:
        address = street
    # normalize -> ensure Ithaca, NY present
    if "ithaca" not in address.lower():
        address = address.rstrip(", ") + ", Ithaca, NY"
    elif "ny" not in address.lower():
        address = address.rstrip(", ") + ", NY"

    txt = clean(body)

    # price
    rent = 0
    price_range = ""
    mprice = re.search(r"\$([\d,]+(?:\.\d+)?)\s*/\s*month", txt)
    if mprice:
        rent = int(float(mprice.group(1).replace(",", "")))
        price_range = mprice.group(0)

    # availability
    avail = ""
    mav = re.search(r"Available(?:\s+(?:for\s+)?)([\w/\-,. ]{3,40}?)(?:\s{2,}|\d Bed|$)", txt)
    mav2 = re.search(r"Available\s+(\d{1,2}/\d{1,2}/\d{2,4})", txt)
    mav3 = re.search(r"Available\s+Now", txt, re.I)
    if mav2:
        avail = mav2.group(1)
    elif mav3:
        avail = "Now"

    # beds / baths
    beds = 0
    mb = re.search(r"(\d+)\s*Bed", txt)
    if mb:
        beds = int(mb.group(1))
    elif re.search(r"Studio", txt, re.I):
        beds = 0
    baths = 0
    mba = re.search(r"([\d.]+)\s*Bath", txt)
    if mba:
        baths = float(mba.group(1))
        if baths == int(baths):
            baths = int(baths)

    # sqft (often in unit-detail__unit-info list, e.g. "614 sqft")
    sqft = 0
    unitinfo = ""
    miu = re.search(r"unit-detail__unit-info\"[^>]*>(.*?)</ul>", body, re.S)
    if miu:
        unitinfo = clean(miu.group(1))
    msq = re.search(r"([\d,]+)\s*(?:sq\.?\s*ft|sqft|square feet)", unitinfo or txt, re.I)
    if msq:
        sqft = int(msq.group(1).replace(",", ""))

    # deposit
    deposit = 0
    mdep = re.search(r"\$([\d,]+(?:\.\d+)?)\s*security deposit", txt, re.I)
    if mdep:
        deposit = int(float(mdep.group(1).replace(",", "")))

    # description: <p class="unit-detail__description"> blocks (may be several)
    parts = [clean(x) for x in
             re.findall(r"<p class=\"unit-detail__description\">(.*?)</p>", body, re.S)]
    parts = [p for p in parts if p]
    desc = " ".join(parts)
    if not desc:
        md = re.search(r"Bath\s+(.*?)\s+Rental Features", txt)
        if md:
            desc = md.group(1).strip()

    # amenities: items under Rental Features
    amenities = {}
    mfeat = re.search(r"Rental Features(.*?)(Lease Terms|Request information|$)", body, re.S)
    if mfeat:
        block = mfeat.group(1)
        for li in re.findall(r"<li[^>]*>(.*?)</li>", block, re.S):
            label = clean(li)
            if label and len(label) < 60:
                amenities[label] = True
        if not amenities:
            # fallback split visible text
            seg = clean(mfeat.group(1))
            for part in re.split(r"\s{2,}", seg):
                p = part.strip()
                if p and len(p) < 50:
                    amenities[p] = True

    # images
    raw_imgs = re.findall(r"/Resident/api/public/files/download\?fileName=([A-Za-z0-9_.\-]+)", html)
    bases = []
    seen = set()
    for fn in raw_imgs:
        base = re.sub(r"_\d+x\d+(?=\.)", "", fn)  # strip size suffix
        key = re.sub(r"\.\w+$", "", base)
        if key == LOGO:
            continue
        if base not in seen:
            seen.add(base)
            bases.append(base)
    images = [f"{BASE}/Resident/api/public/files/download?fileName={b}" for b in bases]

    return {
        "id": lid,
        "title": title,
        "description": desc,
        "address": address,
        "url": f"{BASE}/Resident/public/rentals/{lid}",
        "posted_date": "",
        "coordinates": {},
        "housing": {"bedrooms": beds, "bathrooms": baths, "sqft": sqft, "available": avail},
        "pricing": {"monthly_rent_total": rent, "rent_period": "monthly",
                    "security_deposit": deposit, "price_range": price_range},
        "amenities": amenities,
        "contact": {"company": "CSP Management", "phone": "",
                    "owner_website": "https://cspmanagement.com"},
        "images": images,
    }


def main():
    idx = fetch(LIST_URL)
    ids = get_listing_ids(idx)
    print(f"Found {len(ids)} listing ids: {ids}")
    listings = []
    for lid in ids:
        url = f"{BASE}/Resident/public/rentals/{lid}"
        try:
            h = fetch(url)
            rec = parse_listing(lid, h)
            listings.append(rec)
            print(f"  {lid}: {rec['title']} | {rec['housing']['bedrooms']}bd/"
                  f"{rec['housing']['bathrooms']}ba ${rec['pricing']['monthly_rent_total']} "
                  f"| {len(rec['images'])} imgs")
        except Exception as e:
            print(f"  ERROR {lid}: {e}")
        time.sleep(1.0)
    with open("data/raw/csp_raw.json", "w", encoding="utf-8") as f:
        json.dump(listings, f, ensure_ascii=False, indent=2)
    total_imgs = sum(len(r["images"]) for r in listings)
    print(f"csp: {len(listings)} listings, {total_imgs} total images")


if __name__ == "__main__":
    main()

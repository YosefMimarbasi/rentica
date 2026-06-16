#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Scrape all Ithaca Renting Company unit-details pages into raw JSON.
Pages are server-rendered (curl works) and contain rm12filereader image URLs.
"""
import re, os, json, time, html as ihtml, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'raw', 'ithacarenting_raw.json')
TMP = os.path.join(ROOT, '.tmp_ithaca')
os.makedirs(TMP, exist_ok=True)
os.makedirs(os.path.dirname(OUT), exist_ok=True)

UIDS = [int(x) for x in open(os.path.join(ROOT,'scripts','ithaca_uids.txt')).read().replace('\n',',').split(',') if x.strip()]

def strip_tags(s):
    s = re.sub(r'<[^>]+>', '', s)
    s = ihtml.unescape(s)
    return re.sub(r'[ \t]+', ' ', s).strip()

def fetch(uid):
    path = os.path.join(TMP, f'u{uid}.html')
    if os.path.exists(path) and os.path.getsize(path) > 5000:
        return open(path, encoding='utf-8').read()
    url = f'https://ithacarenting.com/unit-details/?uid={uid}'
    for attempt in range(3):
        r = subprocess.run(['curl','-s','-A','Mozilla/5.0','--max-time','40',url],
                           capture_output=True, text=True, encoding='utf-8')
        if r.stdout and len(r.stdout) > 5000:
            open(path,'w',encoding='utf-8').write(r.stdout)
            return r.stdout
        time.sleep(1.5)
    return r.stdout or ''

def parse_beds_baths(title):
    beds = 0; baths = 0.0
    t = title.lower()
    if 'studio' in t:
        beds = 0
    mb = re.search(r'(\d+)\s*bedroom', t)
    if mb: beds = int(mb.group(1))
    mba = re.search(r'(\d+(?:\.\d+)?)\s*bath', t)
    if mba: baths = float(mba.group(1))
    return beds, baths

def parse_unit(uid, h):
    title_m = re.search(r'<h1[^>]*>(.*?)</h1>', h, re.S)
    title = strip_tags(title_m.group(1)) if title_m else ''

    # header price + availability
    hm = re.search(r'header-info"><span>(.*?)</span><span>(.*?)</span>', h, re.S)
    price_raw = strip_tags(hm.group(1)) if hm else ''
    avail = strip_tags(hm.group(2)) if hm else ''
    price_range = re.sub(r'\s*[\u2013\u2014-]\s*', ' - ', price_raw).strip() if price_raw else ''
    low = 0
    nums = re.findall(r'[\d,]+', price_raw.replace('$',''))
    if nums:
        try: low = int(nums[0].replace(',',''))
        except: low = 0

    # description paragraphs (exclude SMS consent / privacy boilerplate)
    paras = re.findall(r'<p[^>]*>(.*?)</p>', h, re.S)
    clean = []
    for p in paras:
        c = strip_tags(p)
        if len(c) < 40: continue
        if re.search(r'receive text messages|privacy policy|Message and data rates|opt-out', c, re.I):
            continue
        clean.append(c)
    description = '\n\n'.join(clean)

    # address: parse "..., 208 Dryden Road, was built" style
    address = ''
    am = re.search(r',\s*(\d+[\w\-]*\s+[A-Z][A-Za-z\.\' ]+?(?:Road|Rd|Street|St|Avenue|Ave|Place|Pl|Drive|Dr|Lane|Ln|Way|Boulevard|Blvd|Terrace|Court|Circle|Heights|Path|Square|Sq)),', description)
    if am:
        address = am.group(1).strip()
    else:
        # fallback: number + words before "was built" or first sentence
        am2 = re.search(r'(\d+\s+[A-Z][A-Za-z\.\' ]+?(?:Road|Rd|Street|St|Avenue|Ave|Place|Pl|Drive|Dr|Lane|Ln|Way|Boulevard|Blvd|Terrace|Court|Circle|Heights|Path|Square|Sq))\b', description)
        if am2: address = am2.group(1).strip()
    if address and 'ithaca' not in address.lower():
        address = address + ', Ithaca, NY'
    elif not address:
        address = ', Ithaca, NY'

    # building / property name: from "Other Available Rentals" heading or details heading
    building = ''
    bm = re.search(r'<h2[^>]*>\s*([A-Z][A-Za-z0-9&\'\- ]+?)\s*Details\s*</h2>', h)
    if bm:
        building = strip_tags(bm.group(1)).strip()
    if not building:
        # try start of description "Collegetown Court, 208 ..."
        bm2 = re.match(r'^([A-Z][A-Za-z0-9&\'\- ]+?),\s*\d+', description)
        if bm2: building = bm2.group(1).strip()

    beds, baths = parse_beds_baths(title)

    # amenities: first Amenities <h2> ... </ul> (unit-level amenities)
    amenities = {}
    am_block = re.search(r'Amenities\s*</h2>(.*?)</ul>', h, re.S)
    if am_block:
        lis = re.findall(r'<li[^>]*>(.*?)</li>', am_block.group(1), re.S)
        for li in lis:
            label = strip_tags(li)
            if label:
                amenities[label] = True

    # images: rm12filereader URLs before the "Other Available Rentals" section (those are this unit/property)
    oth = h.find('Other Available')
    scope = h[:oth] if oth > 0 else h
    raw_imgs = re.findall(r'https://rm12filereader\.rentmanager\.com/files/get/\?[^"\'\\ >]+', scope)
    # also any other img srcs in scope that are real photos (not plugin assets/logos)
    other_srcs = re.findall(r'<img[^>]+(?:src|data-src|data-lazy-src)="([^"]+)"', scope)
    for s in other_srcs:
        if s.startswith('http') and 'rm12filereader' in s:
            raw_imgs.append(s)
    images = []
    seen = set()
    for u in raw_imgs:
        u = ihtml.unescape(u).rstrip('\\')
        if u in seen: continue
        if re.search(r'logo|swirl|icon|sprite|favicon|placeholder|/lightbox/images/', u, re.I):
            continue
        seen.add(u); images.append(u)

    # other units uids (optional)
    others = sorted(set(re.findall(r'uid=(\d+)', h[oth:] if oth>0 else '')), key=lambda x:int(x))

    return {
        "id": str(uid),
        "title": title,
        "description": description,
        "address": address,
        "url": f"https://ithacarenting.com/unit-details/?uid={uid}",
        "posted_date": "",
        "coordinates": {},
        "housing": {"bedrooms": beds, "bathrooms": baths, "sqft": 0, "available": avail},
        "pricing": {"monthly_rent_total": low, "rent_period": "monthly",
                    "security_deposit": 0, "price_range": price_range},
        "amenities": amenities,
        "contact": {"company": "Ithaca Renting Company", "phone": "",
                    "owner_website": "https://ithacarenting.com"},
        "images": images,
    }

def main():
    results = []
    # resume support
    if os.path.exists(OUT):
        try:
            results = json.load(open(OUT, encoding='utf-8'))
        except: results = []
    done = {r['id'] for r in results}
    for i, uid in enumerate(UIDS):
        if str(uid) in done:
            continue
        h = fetch(uid)
        if not h or len(h) < 5000:
            print(f'  !! uid={uid} fetch failed (len={len(h)})')
            continue
        rec = parse_unit(uid, h)
        results.append(rec)
        print(f'[{i+1}/{len(UIDS)}] uid={uid} "{rec["title"]}" addr="{rec["address"]}" imgs={len(rec["images"])} amen={len(rec["amenities"])}')
        if (i+1) % 10 == 0:
            json.dump(results, open(OUT,'w',encoding='utf-8'), ensure_ascii=False, indent=2)
        time.sleep(0.4)
    # final sort by uid order
    order = {str(u): k for k,u in enumerate(UIDS)}
    results.sort(key=lambda r: order.get(r['id'], 999))
    json.dump(results, open(OUT,'w',encoding='utf-8'), ensure_ascii=False, indent=2)
    total_imgs = sum(len(r['images']) for r in results)
    print(f'\nithacarenting: {len(results)} listings, {total_imgs} total images')

if __name__ == '__main__':
    main()

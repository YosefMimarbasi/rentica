"""Reclassify every craigslist listing's price: property-total vs per-person.

Reads each post's description and decides which the scraped number is:
  - explicit total ("$2,595 per month total", "$1885 per month (...)",
    "or $3400/month total")             -> that is the unit total
  - per-room / per-person rent
    ("$815 per room", "$850/month/person", "rent is 900 per person")
                                         -> per-person; total = pp * beds
  - bare "$Y per month" / structured     -> total

Fee phrases (application / trash / recycling / utility / water / sewer /
NYSEG) carrying "per person" are ignored so they don't trigger per-person.

Also recovers the true bedroom count from "N bedroom" in the text when it
disagrees with the parsed beds, since per-person*beds needs correct beds.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "apartments.json"
RAW = ROOT / "data" / "raw" / "craigslist_raw.json"

MONEY = r"\$?\s*([\d,]{3,6})(?:\.\d+)?"
FEE_CTX = re.compile(r"(application|trash|recycl|util|water|sewer|nyseg|"
                     r"electric|internet|wifi|deposit|annual)", re.I)


def num(s):
    return int(s.replace(",", "")) if s else 0


def beds_from_text(desc, fallback):
    m = re.findall(r"(\d+)\s*[- ]?\s*bedroom", desc, re.I)
    cands = [int(x) for x in m if 1 <= int(x) <= 9]
    return max(cands) if cands else fallback


SINGLE_ROOM = re.compile(
    r"\b(one|single|a)\s+(furnished\s+)?room\s+(available|for rent|in)|"
    r"private room|room available|renting.{0,15}room\b|by the room", re.I)


def classify(desc, beds):
    """Return (total, per_person, beds_override) or (None,None,None)."""
    d = re.sub(r"\s+", " ", desc or "")

    # 1) explicit unit total stated -> trust it
    for pat in [r"or\s*" + MONEY + r"\s*/?\s*month\s*total",
                MONEY + r"\s*/?\s*month\s*total",
                MONEY + r"\s*(?:per month|/month|/mo)\s*\(",
                r"=\s*" + MONEY + r"\s*total"]:
        m = re.search(pat, d, re.I)
        if m:
            tot = num(m.group(1))
            if 500 <= tot <= 16000:
                return tot, (round(tot / beds) if beds > 0 else tot), None

    # 2) explicit per-room / per-person rate
    for m in re.finditer(MONEY + r"\s*(?:/|per)\s*(?:month\s*/\s*)?"
                         r"(?:room|person|bed(?:room)?)", d, re.I):
        if FEE_CTX.search(d[max(0, m.start() - 40):m.start()]):
            continue
        pp = num(m.group(1))
        if not (350 <= pp <= 3200):
            continue
        # single-room rental: you rent ONE room -> total == per-person
        if SINGLE_ROOM.search(d):
            return pp, pp, 1
        # whole unit priced per room -> total = pp * beds
        return pp * max(beds, 1), pp, None

    return None, None, None


def main():
    db = json.load(open(DB, encoding="utf-8"))
    raw = {f"craigslist-{r.get('id')}": r
           for r in json.load(open(RAW, encoding="utf-8"))}
    changed = 0
    for a in db:
        if a.get("source") != "craigslist":
            continue
        r = raw.get(a.get("id"))
        if not r:
            continue
        desc = str(r.get("description", "") or "") + " " + str(r.get("title", "") or "")
        cur_beds = a.get("housing", {}).get("bedrooms", 0) or 0
        beds = beds_from_text(desc, cur_beds)
        tot, pp, beds_override = classify(desc, beds)
        if tot is None:
            continue
        p = a.setdefault("pricing", {})
        old = p.get("monthly_rent_total", 0)
        final_beds = beds_override if beds_override is not None else beds
        if old == tot and p.get("per_person_monthly") == pp and final_beds == cur_beds:
            continue
        if final_beds:
            a["housing"]["bedrooms"] = final_beds
        p["monthly_rent_total"] = tot
        p["per_person_monthly"] = pp
        changed += 1
        print(f"  {a['id']} {final_beds}bd  ${old} -> total ${tot} / pp ${pp}")

    json.dump(db, open(DB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\ncraigslist price reclassified: {changed}")


if __name__ == "__main__":
    main()

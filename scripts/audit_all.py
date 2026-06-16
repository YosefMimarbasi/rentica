"""Audit EVERY listing against its raw scrape + plausibility rules.

For each unit: locate its raw record (id = source-rawid), recompute the
expected price using that source's known semantics, and flag any mismatch
or implausible value. Prints per-flag counts and writes a full line-by-line
report to data/_audit_report.txt covering all 1099 listings.

Source price semantics:
  ithacarenting                -> raw price is PER BED ; total = perbed*beds
  craigslist, csp, ithacaestates, largebuildings, AppFolio
  (modernliving/ppmhomes/travishyde/moll/ithacalivingsolutions)
                               -> raw price is unit TOTAL
  cuapts                       -> no real price (avgPrice is a 1-5 rating)
  lambrou/strawberry/ridgetop/demosjohnny -> usually no public price
"""
import json
import re
import collections
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "apartments.json"
RAW = ROOT / "data" / "raw"
REPORT = ROOT / "data" / "_audit_report.txt"

PERBED_SRC = {"ithacarenting"}
TOTAL_SRC = {"craigslist", "csp", "ithacaestates", "largebuildings",
             "modernliving", "ppmhomes", "travishyde", "moll",
             "ithacalivingsolutions"}
NOPRICE_SRC = {"cuapts", "lambrou", "strawberry", "ridgetop", "demosjohnny"}

RAW_FILES = {
    "craigslist": "craigslist_raw.json", "csp": "csp_raw.json",
    "ithacaestates": "ithacaestates_raw.json", "largebuildings": "largebuildings_raw.json",
    "modernliving": "modernliving_raw.json", "ppmhomes": "ppmhomes_raw.json",
    "travishyde": "travishyde_raw.json", "moll": "moll_raw.json",
    "ithacalivingsolutions": "ithacalivingsolutions_raw.json",
    "ithacarenting": "ithacarenting_raw.json", "cuapts": "cuapts_raw.json",
    "lambrou": "lambrou_raw.json", "strawberry": "strawberry_raw.json",
    "ridgetop": "ridgetop_raw.json", "demosjohnny": "demosjohnny_raw.json",
}


def load_raw():
    out = {}
    for src, fn in RAW_FILES.items():
        p = RAW / fn
        if not p.exists():
            continue
        for r in json.load(open(p, encoding="utf-8")):
            out[f"{src}-{r.get('id')}"] = r
    return out


def perbed_from_range(s):
    m = re.findall(r"\$?([\d,]{3,5})", s or "")
    return int(m[0].replace(",", "")) if m else 0


def main():
    db = json.load(open(DB, encoding="utf-8"))
    raw = load_raw()
    flags = collections.Counter()
    lines = []

    for a in db:
        src = a.get("source")
        p = a.get("pricing", {}) or {}
        h = a.get("housing", {}) or {}
        total = p.get("monthly_rent_total", 0) or 0
        pp = p.get("per_person_monthly", 0) or 0
        beds = h.get("bedrooms", 0) or 0
        baths = h.get("bathrooms", 0) or 0
        sqft = h.get("sqft", 0) or 0
        derived = bool(p.get("price_basis"))
        r = raw.get(a.get("id"), {})
        issues = []

        # --- address ---
        if not a.get("address") or not re.search(r"\d", a.get("address", "")):
            issues.append("no_street_address")

        # --- beds vs raw ---
        rbeds = (r.get("housing", {}) or {}).get("bedrooms")
        if r and rbeds is not None and rbeds != beds:
            issues.append(f"beds!=raw({beds}vs{rbeds})")
        if beds > 9:
            issues.append(f"beds_high({beds})")

        # --- price vs raw semantics (skip derived fills) ---
        if not derived and r:
            rp = (r.get("pricing", {}) or {})
            rprice = rp.get("monthly_rent_total", 0) or 0
            if src in PERBED_SRC:
                rb = perbed_from_range(rp.get("price_range", "")) or rprice
                exp = rb * max(beds, 1) if rb else 0
                if exp and abs(exp - total) > 2:
                    issues.append(f"IR_total({total}!=exp{exp})")
            elif src in TOTAL_SRC:
                if rprice and abs(rprice - total) > 2:
                    issues.append(f"total!=raw({total}vs{rprice})")

        # --- plausibility ---
        if total and total < 400:
            issues.append(f"total_low({total})")
        if total and beds > 0 and not (350 <= total / beds <= 3500):
            issues.append(f"perbed_oob({round(total/beds)})")
        if pp and not (350 <= pp <= 3200):
            issues.append(f"pp_oob({pp})")
        if total and pp and beds > 0 and abs(pp - round(total / beds)) > 2:
            issues.append(f"pp_inconsistent({pp}vs{round(total/beds)})")
        if src in NOPRICE_SRC and total and not derived:
            issues.append(f"unexpected_price({total})")
        if sqft and beds > 0 and sqft / beds < 80:
            issues.append(f"sqft/bed_low({round(sqft/beds)})")
        if baths and beds and baths > beds + 2:
            issues.append(f"baths>beds({baths}/{beds})")

        for i in issues:
            flags[re.sub(r"\(.*", "", i)] += 1
        status = "OK" if not issues else "FLAG"
        if issues:
            lines.append(f"{status} {a.get('id'):40} {beds}bd ${total:<6} pp${pp:<5} "
                         f"{a.get('address','')[:34]:36} | {'; '.join(issues)}")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"audited {len(db)} listings")
    print(f"flagged {len(lines)} | clean {len(db)-len(lines)}")
    print("\nflag counts:")
    for k, v in flags.most_common():
        print(f"  {k:22} {v}")
    print(f"\nfull report -> {REPORT}")


if __name__ == "__main__":
    main()

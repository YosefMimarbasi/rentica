"""Generate sitemap.xml from buildings.json.

Set BASE to the deployed origin (e.g. https://rentaca.vercel.app or a custom
domain). Emits the home/about pages plus one URL per building.
"""
import json
import os
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
BASE = os.environ.get("RENTACA_BASE", "https://rentaca.vercel.app").rstrip("/")


def main():
    b = json.load(open(ROOT / "data" / "buildings.json", encoding="utf-8"))
    urls = [f"{BASE}/index.html", f"{BASE}/about.html"]
    for x in b:
        bid = x.get("building_id")
        if bid:
            urls.append(f"{BASE}/building.html?id={escape(str(bid))}")
    body = "\n".join(
        f"  <url><loc>{u}</loc></url>" for u in urls)
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           f"{body}\n</urlset>\n")
    (ROOT / "sitemap.xml").write_text(xml, encoding="utf-8")
    print(f"sitemap.xml: {len(urls)} urls (base {BASE})")


if __name__ == "__main__":
    main()

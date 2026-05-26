#!/usr/bin/env python3
"""Probe IDX Channel RSS feed and /economics page."""
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import requests
from bs4 import BeautifulSoup
from xml.etree import ElementTree as ET

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8",
}

# 1. RSS feed
print("=== IDX Channel RSS — first 15 items ===")
try:
    r = requests.get("https://www.idxchannel.com/rss", headers=HEADERS, timeout=15)
    root = ET.fromstring(r.content)
    items = root.findall(".//item")
    print(f"  Total items in feed: {len(items)}")
    for item in items[:15]:
        title   = item.findtext("title", "").strip()
        link    = item.findtext("link",  "").strip()
        pubdate = item.findtext("pubDate", "").strip()
        source  = item.findtext("source", "").strip()
        category= item.findtext("category", "").strip()
        print(f"\n  [{pubdate}]")
        print(f"  Title: {title[:90]}")
        print(f"  Link:  {link[:90]}")
        if category:
            print(f"  Cat:   {category}")
except Exception as e:
    print(f"  ERROR: {e}")

# 2. Economics page links
print("\n\n=== IDX Channel /economics — article links ===")
try:
    r = requests.get("https://www.idxchannel.com/economics", headers={
        **HEADERS, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    }, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")
    seen = set()
    count = 0
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("http"):
            href = "https://www.idxchannel.com" + href
        from urllib.parse import urlparse
        path = urlparse(href).path
        if "/economics/" not in path:
            continue
        title = a.get_text(strip=True)
        if href in seen or len(title) < 10:
            continue
        seen.add(href)
        print(f"  {title[:85]}")
        print(f"  -> {path[:80]}")
        count += 1
        if count >= 15:
            break
    if count == 0:
        print("  No /economics/ links found — checking all links on the page:")
        for a in soup.find_all("a", href=True)[:30]:
            href = a["href"]
            title = a.get_text(strip=True)
            if len(title) > 10:
                print(f"    {title[:60]:60s} -> {href[:60]}")
except Exception as e:
    print(f"  ERROR: {e}")

# 3. Regulasi page
print("\n\n=== IDX Channel /regulasi — article links ===")
try:
    r = requests.get("https://www.idxchannel.com/regulasi", headers={
        **HEADERS, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    }, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")
    seen = set()
    count = 0
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("http"):
            href = "https://www.idxchannel.com" + href
        from urllib.parse import urlparse
        path = urlparse(href).path
        if "/regulasi/" not in path:
            continue
        title = a.get_text(strip=True)
        if href in seen or len(title) < 10:
            continue
        seen.add(href)
        print(f"  {title[:85]}")
        count += 1
        if count >= 10:
            break
    if count == 0:
        print("  No /regulasi/ links found")
except Exception as e:
    print(f"  ERROR: {e}")

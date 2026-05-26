#!/usr/bin/env python3
"""
Test IDX Channel scraper: what pages exist, what the scraper picks up,
and what's being dropped.
"""
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8",
}

CANDIDATE_URLS = [
    "https://www.idxchannel.com/market-news",
    "https://www.idxchannel.com/economics",
    "https://www.idxchannel.com/economy",
    "https://www.idxchannel.com/markets",
    "https://www.idxchannel.com/global",
    "https://www.idxchannel.com/macroeconomics",
    "https://www.idxchannel.com/commodity",
    "https://www.idxchannel.com/rss",
    "https://www.idxchannel.com/rss.xml",
    "https://www.idxchannel.com/feed",
]

print("=== Testing IDX Channel URLs ===\n")
for url in CANDIDATE_URLS:
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        print(f"  {r.status_code}  {url}")
        if r.status_code == 200 and "rss" in url.lower():
            # Check if it's actually RSS
            if b"<rss" in r.content[:500] or b"<feed" in r.content[:500]:
                print(f"         *** VALID RSS/ATOM FEED ***")
    except Exception as e:
        print(f"  ERR  {url}  ({e})")

# Now look at what links are on market-news
print("\n=== Links on /market-news — first 20 ===")
try:
    r = requests.get("https://www.idxchannel.com/market-news", headers=HEADERS, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")
    seen = set()
    count = 0
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("http"):
            href = "https://www.idxchannel.com" + href
        title = a.get_text(strip=True)
        if href in seen or len(title) < 10:
            continue
        seen.add(href)
        # Show path structure
        from urllib.parse import urlparse
        path = urlparse(href).path
        if path.count("/") >= 2:  # at least /section/slug
            print(f"  {path[:70]}")
            print(f"  >> {title[:80]}")
            count += 1
        if count >= 20:
            break
except Exception as e:
    print(f"  Error: {e}")

# Check homepage for nav links / sections
print("\n=== IDX Channel homepage nav sections ===")
try:
    r = requests.get("https://www.idxchannel.com", headers=HEADERS, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")
    seen = set()
    # Find nav / menu links
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("http"):
            href = "https://www.idxchannel.com" + href
        if "idxchannel.com" not in href:
            continue
        from urllib.parse import urlparse
        path = urlparse(href).path
        # Only top-level sections (one slash depth after domain)
        if path.count("/") == 1 and len(path) > 1:
            if path not in seen:
                seen.add(path)
                label = a.get_text(strip=True)
                print(f"  {path:30s}  {label[:50]}")
except Exception as e:
    print(f"  Error: {e}")

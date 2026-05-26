"""
Google News RSS per-ticker scraper.

Strategy:
  - For each ticker_tag_enabled ticker, query Google News RSS using the
    company's best short name (first alias → strip "Tbk" from official name).
  - Tag ALL results as `detected_ticker = <symbol>` — no cross-detection.
    Google News already ensures the results are about that company.
  - Resolve Google redirect URLs so the DB stores the real article URL.
  - Applies a polite inter-request delay (default 3s) to avoid rate limits.

Usage (standalone test):
    python -m backend.scrapers.google_news --ticker GOTO --limit 10

Integration:
    Called from backend/workers/ingest.py when --google-news flag is passed.
"""

import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus, urlparse
from xml.etree import ElementTree as ET

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8",
}

# Google News RSS endpoint (Indonesian edition)
_GN_RSS = "https://news.google.com/rss/search?q={query}&hl=id&gl=ID&ceid=ID%3Aid"

# Regex to extract the real URL from Google redirect
# Google News article URLs are like:
#   https://news.google.com/rss/articles/<base64> or
#   https://news.google.com/articles/<id>
# The real URL is obtained by following the redirect (HTTP 301/302).
_REDIRECT_TIMEOUT = 10   # seconds for URL resolution
_GN_STALE_DAYS    = 30


def _best_query_name(name: str, aliases: list[str]) -> str:
    """
    Pick the shortest, most search-friendly company name for the Google News
    query.  Priority:
      1. First alias (usually the shortest recognisable form)
      2. Official name stripped of " Tbk", " Tbk.", "(Persero)" etc.
    """
    if aliases:
        # Use the shortest alias that is ≥8 chars (avoid single-word aliases
        # like "Bank" or "Jasa" that are too generic)
        candidates = [a for a in aliases if len(a) >= 8]
        if candidates:
            return min(candidates, key=len)

    # Strip legal suffixes from official name
    cleaned = re.sub(
        r"\s*(Tbk\.?|Tbk|Persero|PT\.?)\s*",
        " ", name, flags=re.IGNORECASE
    ).strip()
    # Remove trailing period or comma
    cleaned = cleaned.rstrip(".,").strip()
    return cleaned


def _source_from_title(title: str, source_el: str | None) -> str:
    """
    Extract the publisher name.
    Google News titles end with " - PublisherName"; prefer the <source> element.
    """
    if source_el and source_el.strip():
        return source_el.strip()
    # Fall back: strip trailing " - Source" from title
    if " - " in title:
        return title.rsplit(" - ", 1)[-1].strip()
    return "Google News"


def fetch_google_news_ticker(
    symbol: str,
    name: str,
    aliases: list[str],
    max_articles: int = 10,
) -> list[dict]:
    """
    Fetch Google News RSS articles for *symbol* and return article dicts with
    `detected_ticker` pre-set to *symbol*.  No cross-detection is performed —
    every result is attributed exclusively to the queried ticker.

    Article URLs are Google News redirect URLs (news.google.com/rss/articles/…).
    These are stable identifiers used for deduplication and are clickable for
    end users (they redirect to the source article).  The publisher name is
    extracted from the <source> element or from the title's " - Publisher" suffix.

    Args:
        symbol:       IDX ticker symbol (e.g. "GOTO")
        name:         official company name (from tickers.name)
        aliases:      list of aliases (from tickers.aliases)
        max_articles: max results to return
    """
    query_name = _best_query_name(name, aliases)
    # Surround with quotes for exact-phrase search; add "saham" to bias toward
    # Indonesian stock market news vs. general company news
    query = f'"{query_name}" saham'
    url   = _GN_RSS.format(query=quote_plus(query))

    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as exc:
        print(f"  [google-news] {symbol} fetch failed: {exc}")
        return []

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as exc:
        print(f"  [google-news] {symbol} XML parse error: {exc}")
        return []

    cutoff  = datetime.now(timezone.utc).timestamp() - _GN_STALE_DAYS * 86_400
    results: list[dict] = []
    seen_urls: set[str] = set()

    for item in root.findall(".//item"):
        title      = (item.findtext("title")       or "").strip()
        link       = (item.findtext("link")        or "").strip()
        desc       = (item.findtext("description") or "").strip()
        pub_str    = (item.findtext("pubDate")     or "").strip()
        source_el  = (item.findtext("source")      or "").strip()

        if not title or not link:
            continue

        # Strip " - Publisher" suffix from title for cleaner display
        clean_title = title.rsplit(" - ", 1)[0].strip() if " - " in title else title

        # Publisher name
        publisher = _source_from_title(title, source_el)

        # Parse publication date
        pub: datetime | None = None
        for fmt in (
            "%a, %d %b %Y %H:%M:%S %Z",
            "%a, %d %b %Y %H:%M:%S %z",
        ):
            try:
                pub = datetime.strptime(pub_str, fmt)
                if pub.tzinfo is None:
                    pub = pub.replace(tzinfo=timezone.utc)
                break
            except ValueError:
                continue

        if pub is None:
            continue  # no date → skip
        if pub.timestamp() < cutoff:
            continue  # too old → skip

        if link in seen_urls:
            continue
        seen_urls.add(link)

        # Strip HTML from description snippet
        snippet = re.sub(r"<[^>]+>", "", desc).strip()[:500]

        results.append({
            "title":           clean_title,
            "url":             link,
            "source":          publisher,
            "snippet":         snippet,
            "published_at":    pub,
            "detected_ticker": symbol.upper(),
        })

        if len(results) >= max_articles:
            break

    return results


def fetch_all_google_news(
    ticker_rows: list[dict],   # list of {"symbol": str, "name": str, "aliases": list}
    delay_seconds: float = 3.0,
    max_per_ticker: int  = 10,
) -> list[dict]:
    """
    Iterate over ticker_rows and fetch Google News for each.
    Applies delay_seconds between each ticker to avoid rate-limiting.
    """
    all_articles: list[dict] = []
    for i, row in enumerate(ticker_rows):
        sym     = row["symbol"]
        name    = row["name"]
        aliases = row.get("aliases") or []
        arts    = fetch_google_news_ticker(
            sym, name, aliases,
            max_articles=max_per_ticker,
        )
        print(f"  [google-news] {sym} ({_best_query_name(name, aliases)!r}): {len(arts)} articles")
        all_articles.extend(arts)
        if i < len(ticker_rows) - 1:
            time.sleep(delay_seconds)
    return all_articles


# ---------------------------------------------------------------------------
# Standalone test (python -m backend.scrapers.google_news --ticker GOTO)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
    load_dotenv(PROJECT_ROOT / ".env.local", override=True)

    parser = argparse.ArgumentParser(description="Google News RSS per-ticker test")
    parser.add_argument("--ticker",   required=True, help="Ticker symbol, e.g. GOTO")
    parser.add_argument("--limit",    type=int, default=10)
    args = parser.parse_args()

    # Minimal DB lookup to get name & aliases
    import asyncio, os
    import asyncpg

    async def _get_ticker_info(sym: str):
        conn = await asyncpg.connect(os.environ["DATABASE_URL"])
        try:
            row = await conn.fetchrow(
                "SELECT symbol, name, aliases FROM tickers WHERE symbol = $1", sym.upper()
            )
            return row
        finally:
            await conn.close()

    row = asyncio.run(_get_ticker_info(args.ticker))
    if not row:
        print(f"Ticker {args.ticker!r} not found in DB")
        raise SystemExit(1)

    print(f"Testing: {row['symbol']} — {row['name']}")
    print(f"  Query name: {_best_query_name(row['name'], list(row['aliases'] or []))!r}")
    print()

    arts = fetch_google_news_ticker(
        row["symbol"], row["name"], list(row["aliases"] or []),
        max_articles=args.limit,
    )

    for a in arts:
        pub = a["published_at"].strftime("%Y-%m-%d %H:%M")
        print(f"  [{pub}] {a['title'][:80]}")
        print(f"    URL: {a['url'][:100]}")
    print(f"\n{len(arts)} articles found.")

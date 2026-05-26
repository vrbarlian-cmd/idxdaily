"""
Detik Finance per-ticker tag scraper.

Per-ticker strategy config controls which URL(s) to fetch:
  - symbol_only: /tag/<ticker> only (symbol is unambiguous)
  - name_only:   /tag/<name_slug> only (symbol is a common Indonesian word)
  - merge_both:  fetch both URLs, dedupe by article URL

Uses selectolax for fast HTML parsing.
Respects a 2-second inter-request delay between each ticker.
"""

import time
from datetime import datetime, timezone, timedelta

import requests
from selectolax.parser import HTMLParser


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8",
    "Referer": "https://www.google.com/",
}

# Per-ticker scraping strategy. Authoritative — no fallback logic.
TICKER_STRATEGIES: dict[str, dict] = {
    "BBCA": {"mode": "symbol_only"},
    "BBRI": {"mode": "symbol_only"},
    "BMRI": {"mode": "symbol_only"},
    "BBNI": {"mode": "symbol_only"},
    "GOTO": {"mode": "symbol_only"},
    "PTRO": {"mode": "merge_both", "name_slug": "petrosea"},
    "BUVA": {"mode": "merge_both", "name_slug": "bukit-uluwatu-villa"},
    "BUMI": {"mode": "name_only", "name_slug": "bumi-resources"},   # "bumi" = earth in Indonesian
    "DEWA": {"mode": "name_only", "name_slug": "darma-henwa"},       # "dewa" = god in Indonesian
    "BULL": {"mode": "name_only", "name_slug": "buana-lintas-lautan"},  # "bull" matches "dibully"
}

_MONTHS_ID = {
    "januari": 1, "februari": 2, "maret": 3, "april": 4,
    "mei": 5, "juni": 6, "juli": 7, "agustus": 8,
    "september": 9, "oktober": 10, "november": 11, "desember": 12,
}


def _parse_detik_date(text: str) -> datetime | None:
    """
    Parse an Indonesian-language date string from Detik pages.
    Returns a UTC-aware datetime, or None if the date cannot be reliably parsed.
    Never falls back to 'now' — a missing date is represented as None so the
    caller can decide to drop the article rather than store a wrong timestamp.
    """
    if not text or not text.strip():
        return None
    text = text.strip()
    lower = text.lower()

    # Try ISO 8601 first (datetime attribute on <time> elements)
    # e.g. "2024-06-12T10:04:00+07:00" or "2024-06-12T10:04:00Z"
    try:
        from datetime import datetime as _dt
        dt = _dt.fromisoformat(text.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        pass

    for prefix in ("detikfinance", "detiknews", "detikcom", "detik finance"):
        if lower.startswith(prefix):
            text = text[len(prefix):]
            lower = text.lower()
            break
    if "," in text:
        text = text.split(",", 1)[1].strip()
    for tz_suffix in (" wib", " wita", " wit"):
        if text.lower().endswith(tz_suffix):
            text = text[: -len(tz_suffix)].strip()
    text_lower = text.lower()
    for id_month, num in _MONTHS_ID.items():
        if id_month in text_lower:
            text = text_lower.replace(id_month, str(num))
            break
    for fmt in ("%d %m %Y %H:%M", "%d %m %Y", "%d %b %Y %H:%M", "%d %b %Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(text.strip(), fmt)
            return dt.replace(tzinfo=timezone.utc) - timedelta(hours=7)  # WIB → UTC
        except ValueError:
            pass
    # Could not parse — caller must drop this article
    return None


_STALE_CUTOFF_DAYS = 30


def _scrape_tag_url(url: str, ticker: str, max_articles: int) -> list[dict]:
    """Fetch a single /tag/ URL and return parsed article dicts.

    Articles are dropped if:
    - The publication date cannot be parsed (never fall back to 'now')
    - The article is older than _STALE_CUTOFF_DAYS days
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            print(f"  [WARN] {ticker} {url} → HTTP {resp.status_code}")
            return []
    except Exception as exc:
        print(f"  [WARN] {ticker} {url}: {exc}")
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=_STALE_CUTOFF_DAYS)
    tree    = HTMLParser(resp.text)
    results: list[dict] = []
    dropped_no_date = 0
    dropped_stale   = 0

    for article in tree.css("article"):
        heading = article.css_first("h1, h2, h3")
        link    = article.css_first("a[href]")
        if not heading or not link:
            continue

        time_el   = article.css_first("time")
        date_span = article.css_first(".date")   # Detik removed <time> from tag cards
        excerpt   = article.css_first("p")
        href      = link.attributes.get("href", "")
        if not href.startswith("http"):
            href = "https://www.detik.com" + href

        date_text = ""
        if time_el:
            date_text = time_el.attributes.get("datetime", "") or time_el.text(strip=True)
        elif date_span:
            date_text = date_span.text(strip=True)  # e.g. "detikFinanceSenin, 30 Mar 2026 15:37 WIB"

        pub = _parse_detik_date(date_text)
        if pub is None:
            dropped_no_date += 1
            continue
        if pub < cutoff:
            dropped_stale += 1
            continue

        results.append({
            "title":           heading.text(strip=True),
            "url":             href,
            "source":          "Detik Finance",
            "snippet":         excerpt.text(strip=True)[:500] if excerpt else "",
            "published_at":    pub,
            "detected_ticker": ticker.upper(),
        })

        if len(results) >= max_articles:
            break

    if dropped_no_date or dropped_stale:
        print(f"  [detik-tag] {ticker}: dropped {dropped_no_date} no-date, "
              f"{dropped_stale} stale (>{_STALE_CUTOFF_DAYS}d)")

    return results


def fetch_ticker_tag(ticker: str, max_articles: int = 15) -> list[dict]:
    """
    Fetch articles for *ticker* using the per-ticker strategy config.
    Returns deduped article dicts with a guaranteed 'detected_ticker' key.
    """
    sym = ticker.upper()
    strategy = TICKER_STRATEGIES.get(sym, {"mode": "symbol_only"})
    mode = strategy["mode"]

    seen_urls: set[str] = set()
    results: list[dict] = []

    def _add(articles: list[dict]) -> None:
        for a in articles:
            if a["url"] not in seen_urls:
                seen_urls.add(a["url"])
                results.append(a)

    if mode in ("symbol_only", "merge_both"):
        primary_url = f"https://www.detik.com/tag/{sym.lower()}"
        _add(_scrape_tag_url(primary_url, sym, max_articles))

    if mode in ("name_only", "merge_both"):
        name_slug = strategy.get("name_slug", "")
        if name_slug:
            if mode == "merge_both" and results:
                time.sleep(2)  # polite gap between the two requests
            name_url = f"https://www.detik.com/tag/{name_slug}"
            _add(_scrape_tag_url(name_url, sym, max_articles))

    return results[:max_articles]


def fetch_all_tickers(
    symbols: list[str],
    delay_seconds: float = 2.0,
    max_per_ticker: int = 15,
) -> list[dict]:
    """
    Fetch tag pages for every symbol using its configured strategy.
    Applies *delay_seconds* between each ticker (not between individual requests
    within a merge_both fetch — those use a fixed 2s gap internally).
    """
    all_articles: list[dict] = []
    for i, sym in enumerate(symbols):
        articles = fetch_ticker_tag(sym, max_articles=max_per_ticker)
        print(f"  [detik-tag] {sym}: {len(articles)} articles (mode={TICKER_STRATEGIES.get(sym.upper(), {}).get('mode','?')})")
        all_articles.extend(articles)
        if i < len(symbols) - 1:
            time.sleep(delay_seconds)
    return all_articles

#!/usr/bin/env python3
"""
fetch_bodies.py — Fetch full article body text for macro/sector/regulatory articles.

For articles where category IN ('MACRO','REGULATORY','SECTOR') and body IS NULL
(and body_fetched_at IS NULL), fetches the article URL and extracts the main text.
Stores up to MAX_BODY_CHARS characters in articles.body.

Source-specific CSS selectors:
  Detik:          div.detail__body-text  |  div.itp_bodycontent
  CNBC Indonesia: div.detail_text        |  div.detail-text
  Fallback:       <article> tag → largest text-dense <div>

Usage (from project root):
  python -m backend.workers.fetch_bodies --limit 50
  python -m backend.workers.fetch_bodies --limit 200 --all-categories
  python -m backend.workers.fetch_bodies --article-id <uuid>   # single article
"""

import argparse
import asyncio
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[2]

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env.local", override=True)

from ._db import get_conn

import re as _re
import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

HEADERS = {
    "User-Agent": "IDXDailyBot/0.1 (+https://idxdaily.id/bot)",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8",
    "Accept-Encoding": "gzip, deflate",
}

# Browser-like headers for resolving Google News redirect URLs
_GN_RESOLVE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

MAX_BODY_CHARS  = 4000   # truncate stored body to this length
DELAY_PER_HOST  = 3.0    # seconds between requests to the same host
REQUEST_TIMEOUT = 15     # seconds

# Source name fragment → CSS selector list (tried in order, first non-empty hit wins)
SOURCE_SELECTORS: dict[str, list[str]] = {
    "detik": [
        "div.detail__body-text",
        "div.itp_bodycontent",
        "div.detail__body",
        "div[class*='detail__body']",
    ],
    "cnbc": [
        "div.detail_text",
        "div.detail-text",
        "div.content-article",
        "div[class*='detail_text']",
    ],
    "kontan": [
        "div.tmpt-desk-kon",
        "div.col-md-12.col-sm-12.top-artikel",
        "div[class*='artikel']",
    ],
    "bisnis": [
        "div.col-content",
        "article",
    ],
}

# Tags whose content is always removed before extraction
_NOISE_TAGS = [
    "script", "style", "nav", "header", "footer",
    "aside", "figure", "noscript", "iframe", "form",
    "button", "svg", "ins",
]

# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def _resolve_google_news_url(gn_url: str) -> str:
    """
    Attempt to follow a Google News redirect URL to get the real article URL.
    Strategy:
      1. Try base64 decode of the article ID — many GN URLs encode the real URL
      2. Fall back to HTTP GET with browser headers + redirect following
    Returns the resolved URL, or the original GN URL if resolution fails.
    """
    if "news.google.com" not in gn_url:
        return gn_url

    # ── Strategy 1: base64 decode ────────────────────────────────────────────
    # GN URLs: https://news.google.com/rss/articles/CBMi<b64>?hl=...
    # The base64 payload encodes the real URL in a protobuf-like binary format.
    import base64
    try:
        for marker in ("/rss/articles/", "/articles/"):
            if marker in gn_url:
                encoded = gn_url.split(marker, 1)[1].split("?")[0]
                # Pad
                rem = len(encoded) % 4
                if rem:
                    encoded += "=" * (4 - rem)
                raw = base64.urlsafe_b64decode(encoded)
                text = raw.decode("latin-1", errors="replace")
                # Real URL is embedded after protobuf header bytes
                for prefix in ("https://", "http://"):
                    idx = text.find(prefix)
                    if idx != -1:
                        candidate_chars = []
                        for ch in text[idx:]:
                            if ord(ch) < 32:  # stop at control chars / null bytes
                                break
                            candidate_chars.append(ch)
                        candidate = "".join(candidate_chars).rstrip(".,;) ")
                        if "." in candidate and len(candidate) > 20 and "google.com" not in candidate:
                            return candidate
                break
    except Exception:
        pass

    # ── Strategy 2: HTTP GET with browser headers ────────────────────────────
    try:
        resp = requests.get(
            gn_url,
            headers=_GN_RESOLVE_HEADERS,
            allow_redirects=True,
            timeout=15,
        )
        # If we were redirected out of google.com, use the final URL
        if "google.com" not in urlparse(resp.url).netloc:
            return resp.url
        # Parse HTML for JS redirect or canonical
        soup = BeautifulSoup(resp.text, "html.parser")
        # meta refresh
        for meta in soup.find_all("meta"):
            if "refresh" in meta.get("http-equiv", "").lower():
                content = meta.get("content", "")
                m = _re.search(r"url=([^\s'\";]+)", content, _re.IGNORECASE)
                if m:
                    candidate = m.group(1).strip("'\"")
                    if candidate.startswith("http") and "google.com" not in candidate:
                        return candidate
        # canonical link
        canon = soup.find("link", rel="canonical")
        if canon and "google.com" not in (canon.get("href") or ""):
            href = canon.get("href", "")
            if href.startswith("http"):
                return href
    except Exception:
        pass

    return gn_url  # give up — use original GN URL


def _source_from_resolved_url(url: str) -> str:
    """Infer a source name from a resolved URL for selector matching."""
    host = urlparse(url).netloc.lower()
    for key in SOURCE_SELECTORS:
        if key in host:
            return key
    return url  # fallback: return URL itself (no matching selectors)


def _selectors_for(source: str) -> list[str]:
    """Return the CSS selector list for a given source name."""
    lower = source.lower()
    for key, selectors in SOURCE_SELECTORS.items():
        if key in lower:
            return selectors
    return []


def extract_body(html: str, source: str) -> str | None:
    """
    Extract main article text from raw HTML.
    Returns cleaned text up to MAX_BODY_CHARS, or None if nothing useful found.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Strip noise elements first
    for tag in soup.find_all(_NOISE_TAGS):
        tag.decompose()

    # ── 1. Source-specific CSS selectors ──────────────────────────────────────
    for selector in _selectors_for(source):
        el = soup.select_one(selector)
        if el:
            text = el.get_text(" ", strip=True)
            if len(text) > 200:
                return text[:MAX_BODY_CHARS]

    # ── 2. <article> tag fallback ─────────────────────────────────────────────
    article = soup.find("article")
    if article:
        text = article.get_text(" ", strip=True)
        if len(text) > 200:
            return text[:MAX_BODY_CHARS]

    # ── 3. Text-density fallback: largest <div> by character count ────────────
    best_text = ""
    for div in soup.find_all("div"):
        # Only consider divs that are leaf-ish (not wrappers with many children)
        child_divs = len(div.find_all("div", recursive=False))
        if child_divs > 8:
            continue
        text = div.get_text(" ", strip=True)
        if len(text) > len(best_text):
            best_text = text
    if len(best_text) > 200:
        return best_text[:MAX_BODY_CHARS]

    return None


# ---------------------------------------------------------------------------
# HTTP fetch
# ---------------------------------------------------------------------------

def fetch_body(url: str, source: str) -> tuple[str | None, str]:
    """
    Fetch one article URL and extract body text.
    Returns (body_text | None, status_note).

    For Google News redirect URLs, first resolves to the real article URL,
    then fetches with source-appropriate selectors.
    """
    if not url:
        return None, "no_url"

    fetch_url = url
    if "news.google.com" in url:
        resolved = _resolve_google_news_url(url)
        if resolved != url:
            fetch_url = resolved
            # Re-derive source name from the resolved domain for selector matching
            source = _source_from_resolved_url(resolved)
            print(f"    [GN->resolved] {urlparse(resolved).netloc}")
        else:
            print(f"    [GN->unresolved] using original GN URL")

    try:
        resp = requests.get(
            fetch_url, headers=HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=True
        )
        if resp.status_code == 404:
            return None, "http_404"
        if resp.status_code == 403:
            return None, "http_403_blocked"
        if resp.status_code != 200:
            return None, f"http_{resp.status_code}"

        body = extract_body(resp.text, source)
        if body:
            return body, "ok"
        return None, "no_content_found"

    except requests.exceptions.Timeout:
        return None, "timeout"
    except requests.exceptions.ConnectionError:
        return None, "connection_error"
    except Exception as exc:
        return None, f"error_{type(exc).__name__}"


# ---------------------------------------------------------------------------
# DB fetch + update
# ---------------------------------------------------------------------------

async def fetch_articles_needing_body(
    conn, limit: int, all_categories: bool, article_id: str | None
) -> list[dict]:
    if article_id:
        rows = await conn.fetch(
            "SELECT id, url, source, title, category FROM articles WHERE id = $1",
            article_id,
        )
    else:
        # Default: fetch bodies for macro/sector articles AND all Google News articles.
        # Google News articles are stored with the real publisher name (e.g. "Bareksa.com")
        # but their URL starts with news.google.com — detect by URL pattern.
        cat_filter = "" if all_categories else (
            "AND (a.category IN ('MACRO', 'REGULATORY', 'SECTOR') "
            "     OR a.url LIKE '%news.google.com%')"
        )
        rows = await conn.fetch(
            f"""
            SELECT a.id, a.url, a.source, a.title, a.category
            FROM articles a
            WHERE a.body IS NULL
              AND a.body_fetched_at IS NULL
              AND a.url IS NOT NULL
              {cat_filter}
            ORDER BY a.published_at DESC
            LIMIT $1
            """,
            limit,
        )
    return [dict(r) for r in rows]


async def save_body(conn, article_id: str, body: str | None) -> None:
    await conn.execute(
        """
        UPDATE articles
        SET body = $1, body_fetched_at = $2
        WHERE id = $3
        """,
        body,
        datetime.now(timezone.utc),
        article_id,
    )


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

async def run_fetch(
    limit: int,
    all_categories: bool = False,
    article_id: str | None = None,
) -> dict:
    """
    Fetch and store article bodies. Returns summary stats dict.
    """
    conn = await get_conn()
    try:
        rows = await fetch_articles_needing_body(conn, limit, all_categories, article_id)
        label = f"article {article_id[:8]}..." if article_id else (
            "all-category articles" if all_categories else "macro/sector/regulatory articles"
        )
        print(f"[fetch-bodies] {len(rows)} {label} need body")

        ok = 0
        status_counts: dict[str, int] = {}
        host_last_req:  dict[str, float] = {}

        for row in rows:
            url    = row["url"] or ""
            source = row["source"] or ""
            title  = row["title"][:60]

            # Per-host rate limiting
            host = urlparse(url).netloc if url else "unknown"
            now  = time.monotonic()
            gap  = now - host_last_req.get(host, 0)
            if gap < DELAY_PER_HOST:
                time.sleep(DELAY_PER_HOST - gap)
            host_last_req[host] = time.monotonic()

            body_text, status = fetch_body(url, source)
            await save_body(conn, row["id"], body_text)

            status_counts[status] = status_counts.get(status, 0) + 1
            if body_text:
                ok += 1
                print(f"  [OK {len(body_text):4}c] {title}...")
            else:
                print(f"  [{status:18s}] {title}...")

        blocked = [
            f"{s}:{c}" for s, c in status_counts.items()
            if s not in ("ok", "no_url")
        ]
        print(f"\n[fetch-bodies] Done - {ok}/{len(rows)} bodies fetched")
        if blocked:
            print(f"  Non-OK statuses: {', '.join(blocked)}")

        return {"ok": ok, "total": len(rows), "status_counts": status_counts}

    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch article bodies for macro enrichment")
    parser.add_argument("--limit", type=int, default=50,
                        help="Max articles to process (default: 50)")
    parser.add_argument("--all-categories", action="store_true",
                        help="Fetch bodies for all articles, not just macro/sector/regulatory")
    parser.add_argument("--article-id", default=None,
                        help="Process a single article by ID (ignores --limit and category filter)")
    args = parser.parse_args()
    asyncio.run(run_fetch(args.limit, args.all_categories, args.article_id))


if __name__ == "__main__":
    main()

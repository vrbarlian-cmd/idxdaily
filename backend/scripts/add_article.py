"""
Manually add one important news article by URL (e.g. a story seen on WhatsApp
from a source the collector does not read, or before the next collector run).

It saves the article exactly like the collector does (same ticker detection,
same IHSG-roundup rule, same table columns). The AI summary, sentiment and
impact score are added by the VM's enrich step on its next run (every 15 min
during market hours), after which the article shows on the website.

Works from any computer that has .env.local (home PC or laptop).

Usage (from project root):
    python -m backend.scripts.add_article --url https://insight.kontan.co.id/news/...
    python -m backend.scripts.add_article --url <link> --dry-run
    python -m backend.scripts.add_article --url <link> --title "Judul" --summary "Ringkasan singkat"
"""

import argparse
import asyncio
import html as _html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / ".env.local", override=True)

from backend.workers._db import get_conn  # noqa: E402
from backend.workers.ingest import (  # noqa: E402
    HEADERS, GLOBAL_SOURCES, load_alias_entries, _build_shared_aliases,
    detect_tickers, is_ihsg_roundup, insert_article, link_ticker_mention,
)

# Friendly source names for common domains (matches names the collector uses).
SOURCE_BY_HOST = {
    "insight.kontan.co.id": "Kontan Insight",
    "kontan.co.id": "Kontan",
    "cnbcindonesia.com": "CNBC Indonesia",
    "detik.com": "Detik Finance",
    "katadata.co.id": "Katadata",
    "bloombergtechnoz.com": "Bloomberg Technoz",
    "bisnis.com": "Bisnis.com",
    "idxchannel.com": "IDX Channel",
    "emitennews.com": "Emiten News",
    "investor.id": "Investor.id",
    "kompas.com": "Kompas",
    "cnnindonesia.com": "CNN Indonesia",
    "reuters.com": "Reuters",
    "bloomberg.com": "Bloomberg",
}


def source_for(url: str, site_name: str | None) -> str:
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    if host in SOURCE_BY_HOST:
        return SOURCE_BY_HOST[host]
    for dom, name in SOURCE_BY_HOST.items():
        if host.endswith("." + dom) or host == dom:
            return name
    return site_name or host or "Manual"


def _meta(soup: BeautifulSoup, *keys: str) -> str | None:
    for k in keys:
        tag = soup.find("meta", attrs={"property": k}) or soup.find("meta", attrs={"name": k})
        if tag and tag.get("content"):
            return tag["content"].strip()
    return None


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.strip()
    for fmt in (None, "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00")) if fmt is None else datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                # Indonesian sites publish in WIB when no zone is given.
                from datetime import timedelta
                dt = dt.replace(tzinfo=timezone(timedelta(hours=7)))
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def fetch_page(url: str) -> dict:
    """Best effort: title, description, published time, site name."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as exc:
        print(f"[warn] Could not open the page ({exc}). Use --title (and --summary) instead.")
        return {}
    soup = BeautifulSoup(resp.text, "html.parser")
    title = _meta(soup, "og:title", "twitter:title") or (soup.title.get_text(strip=True) if soup.title else None)
    desc  = _meta(soup, "og:description", "description", "twitter:description")
    pub   = _meta(soup, "article:published_time", "pubdate", "publishdate", "date",
                  "content_PublishedDate", "dtm.publishedDate")
    if not pub:
        # JSON-LD datePublished
        for s in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(s.string or "")
            except Exception:
                continue
            items = data if isinstance(data, list) else [data]
            for it in items:
                if isinstance(it, dict) and it.get("datePublished"):
                    pub = it["datePublished"]
                    break
            if pub:
                break
    return {
        "title": _html.unescape(title) if title else None,
        "desc":  _html.unescape(desc) if desc else None,
        "pub":   _parse_dt(pub),
        "site":  _meta(soup, "og:site_name"),
    }


async def main() -> int:
    ap = argparse.ArgumentParser(description="Manually add one news article by URL.")
    ap.add_argument("--url", required=True)
    ap.add_argument("--title", help="Override / provide the headline")
    ap.add_argument("--summary", help="Override / provide a short summary (used by the AI)")
    ap.add_argument("--source", help="Override the source name")
    ap.add_argument("--dry-run", action="store_true", help="Show what would be saved, save nothing")
    a = ap.parse_args()

    url = a.url.strip()
    if not url.startswith(("http://", "https://")):
        print("URL must start with http:// or https://"); return 1

    page = fetch_page(url)
    title   = (a.title or page.get("title") or "").strip()
    summary = (a.summary or page.get("desc") or "").strip()
    source  = a.source or source_for(url, page.get("site"))
    pub     = page.get("pub") or datetime.now(timezone.utc)

    if not title:
        print("No headline found. Run again with --title \"...\"."); return 1

    conn = await get_conn()
    try:
        # Same URL with http/https counts as the same article.
        alt = ("https://" + url[7:]) if url.startswith("http://") else ("http://" + url[8:])
        existing = await conn.fetchrow(
            "SELECT id, ai_summary IS NOT NULL AS enriched, category FROM articles WHERE url = $1 OR url = $2",
            url, alt,
        )
        if existing:
            state = "already analysed by AI" if existing["enriched"] else "waiting for the AI step"
            print(f"Already in the database ({state}, category {existing['category']}). Nothing to do.")
            return 0

        entries = await load_alias_entries(conn)
        shared  = _build_shared_aliases(entries)
        matched = [] if source in GLOBAL_SOURCES else detect_tickers(f"{title} {summary}", entries, shared)
        symbols = [next((s for s, i, _, _ in entries if i == tid), "?") + f"({conf})" for tid, conf in matched]
        as_macro = not matched or is_ihsg_roundup(title, matched_ticker_count=len(matched))

        print(f"Title    : {title}")
        print(f"Source   : {source}")
        print(f"Published: {pub.astimezone(timezone.utc):%Y-%m-%d %H:%M} UTC")
        print(f"Summary  : {summary[:200] or '(none)'}")
        print(f"Tickers  : {', '.join(symbols) if symbols else '(none)'}"
              f"{'  -> saved as market/macro news' if as_macro else ''}")

        if a.dry_run:
            print("Dry run: nothing saved."); return 0

        art = {"title": title, "url": url, "source": source, "snippet": summary[:500], "published_at": pub}
        if as_macro:
            await insert_article(conn, None, art)
        else:
            art_id = await insert_article(conn, matched[0][0], art)
            for tid, conf in matched:
                await link_ticker_mention(conn, art_id, tid, conf)
        print("Saved. The AI summary and impact score are added on the server's next run "
              "(every 15 min in market hours); then it shows on the website.")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

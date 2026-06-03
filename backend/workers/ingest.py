#!/usr/bin/env python3
"""
IDXDaily news ingest worker — all IDX tickers (~926 in DB).

Ticker detection uses aliases loaded from the `tickers` table (see
backend/scripts/sync_idx_tickers.py).  The hardcoded 10-ticker list is gone.

Sources:
  1. Per-ticker Detik tag pages — only for tickers where ticker_tag_enabled=TRUE
  2. Detik Finance general RSS  — matched against all DB tickers via aliases
  3. CNBC Indonesia market RSS  — matched against all DB tickers via aliases

Usage (from project root):
  python -m backend.workers.ingest --once
  python -m backend.workers.ingest --once --ticker-tags
  python -m backend.workers.ingest --once --limit 100
"""

import argparse
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

PROJECT_ROOT = Path(__file__).resolve().parents[2]

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env.local", override=True)

from ._db import get_conn
from ..scrapers.detik_ticker_tag import fetch_all_tickers
from ..scrapers.google_news import fetch_all_google_news

import requests
from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# RSS feed definitions
# ---------------------------------------------------------------------------

FEEDS = [
    {"name": "Detik Finance",  "url": "https://finance.detik.com/rss"},
    {"name": "CNBC Indonesia", "url": "https://www.cnbcindonesia.com/market/rss"},
    {"name": "Kontan",         "url": "https://investasi.kontan.co.id/rss"},
    {"name": "Katadata",       "url": "https://katadata.co.id/rss"},
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8",
}


# ---------------------------------------------------------------------------
# HTML listing scrapers (IDX Channel, Bisnis.com, Emiten News)
# ---------------------------------------------------------------------------

def _parse_relative_id(text: str) -> datetime | None:
    """Parse Indonesian relative time strings: 'X menit/jam/hari yang lalu'."""
    import re
    now = datetime.now(timezone.utc)
    text = text.strip().lower()
    m = re.match(r"(\d+)\s*(menit|jam|hari)", text)
    if not m:
        return now  # "baru saja" or unrecognized → treat as now
    n, unit = int(m.group(1)), m.group(2)
    if unit == "menit":
        return now - timedelta(minutes=n)
    if unit == "jam":
        return now - timedelta(hours=n)
    if unit == "hari":
        return now - timedelta(days=n)
    return now


def fetch_idxchannel(limit: int = 40) -> list[dict]:
    """Scrape IDX Channel market news listing."""
    try:
        resp = requests.get(
            "https://www.idxchannel.com/market-news",
            headers=HEADERS, timeout=20,
        )
        resp.raise_for_status()
    except Exception as exc:
        print(f"[WARN] IDX Channel fetch failed: {exc}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    now_wib = datetime.now(timezone(timedelta(hours=7)))
    results = []
    seen: set[str] = set()

    # Collect all /market-news/<slug> links, deduped
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if "/market-news/" not in href:
            continue
        if not href.startswith("http"):
            href = "https://www.idxchannel.com" + href
        if href in seen:
            continue

        title = a.get_text(strip=True)
        if not title or len(title) < 10:
            continue
        seen.add(href)

        # Try to find a date in the nearest ancestor card
        pub: datetime | None = None
        parent = a.find_parent(class_=lambda c: c and "bt-con" in c)
        if parent:
            date_el = parent.select_one("span.mh-clock")
            if date_el:
                raw = date_el.get_text(strip=True)
                try:
                    pub = datetime.strptime(raw.replace(" WIB", ""), "%d/%m/%Y %H:%M")
                    pub = pub.replace(tzinfo=timezone(timedelta(hours=7)))
                except ValueError:
                    pass
        # Listing page = today's news — default to now if no date found
        if pub is None:
            pub = now_wib

        results.append({
            "title": title, "url": href, "source": "IDX Channel",
            "snippet": "", "published_at": pub,
            "detected_ticker": None,
        })
        if len(results) >= limit:
            break

    return results


def fetch_bisnis(limit: int = 40) -> list[dict]:
    """Scrape Bisnis.com market news listing."""
    try:
        resp = requests.get(
            "https://market.bisnis.com",
            headers=HEADERS, timeout=20,
        )
        resp.raise_for_status()
    except Exception as exc:
        print(f"[WARN] Bisnis.com fetch failed: {exc}")
        return []

    import re as _re
    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    seen: set[str] = set()

    # Main grid cards
    for card in soup.select("div.artItem")[:limit]:
        a = card.select_one("div.artContent a.artLink")
        t = card.select_one("h4.artTitle")
        if not a or not t:
            continue
        url   = a.get("href", "")
        title = t.get_text(strip=True)
        if not url or url in seen:
            continue
        seen.add(url)

        # Extract date from URL: /read/20260522/
        pub: datetime | None = None
        m = _re.search(r"/read/(\d{8})/", url)
        if m:
            try:
                pub = datetime.strptime(m.group(1), "%Y%m%d").replace(
                    tzinfo=timezone(timedelta(hours=7))
                )
            except ValueError:
                pass

        results.append({
            "title": title, "url": url, "source": "Bisnis.com",
            "snippet": "", "published_at": pub,
            "detected_ticker": None,
        })

    # Also grab live-feed items
    for item in soup.select("li.liveItem")[:20]:
        a = item.select_one("a.liveLink")
        t = item.select_one("div.liveTitle")
        if not a or not t:
            continue
        url   = a.get("href", "")
        title = t.get_text(strip=True)
        if not url or url in seen:
            continue
        seen.add(url)

        pub = None
        m = _re.search(r"/read/(\d{8})/", url)
        if m:
            try:
                pub = datetime.strptime(m.group(1), "%Y%m%d").replace(
                    tzinfo=timezone(timedelta(hours=7))
                )
            except ValueError:
                pass

        results.append({
            "title": title, "url": url, "source": "Bisnis.com",
            "snippet": "", "published_at": pub,
            "detected_ticker": None,
        })

    return results[:limit]


def fetch_emitennews(limit: int = 40) -> list[dict]:
    """Scrape Emiten News listing — use all /news/ links on the homepage."""
    import re as _re2
    try:
        resp = requests.get(
            "https://emitennews.com",
            headers=HEADERS, timeout=20,
        )
        resp.raise_for_status()
    except Exception as exc:
        print(f"[WARN] Emiten News fetch failed: {exc}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    now_wib = datetime.now(timezone(timedelta(hours=7)))
    # Date suffixes that get concatenated into link text: "14 jam yang lalu", "20/05/2026, 12:34"
    _date_junk = _re2.compile(r"(\d+\s*(menit|jam|hari)\s*yang\s*lalu|\d{2}/\d{2}/\d{4},?\s*\d*:?\d*)", _re2.I)

    results = []
    seen: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if "/news/" not in href:
            continue
        if not href.startswith("http"):
            href = "https://emitennews.com" + href
        if href in seen:
            continue

        raw_text = a.get_text(" ", strip=True)
        # Extract date portion if present
        pub: datetime | None = None
        dm = _date_junk.search(raw_text)
        if dm:
            pub = _parse_relative_id(dm.group(0))
        if pub is None:
            pub = now_wib

        # Clean title: remove the date suffix
        title = _date_junk.sub("", raw_text).strip()
        if len(title) < 10:
            continue

        seen.add(href)
        results.append({
            "title": title, "url": href, "source": "Emiten News",
            "snippet": "", "published_at": pub,
            "detected_ticker": None,
        })
        if len(results) >= limit:
            break

    return results


# ---------------------------------------------------------------------------
# RSS fetcher
# ---------------------------------------------------------------------------

def fetch_rss(feed: dict, limit: int = 50) -> list[dict]:
    try:
        resp = requests.get(feed["url"], headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as exc:
        print(f"[WARN] {feed['name']} RSS failed: {exc}")
        return []
    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as exc:
        print(f"[WARN] {feed['name']} XML parse error: {exc}")
        return []

    results = []
    for item in root.findall(".//item")[:limit]:
        title = item.findtext("title", "").strip()
        link  = item.findtext("link",  "").strip()
        desc  = item.findtext("description", "").strip()
        if desc:
            desc = BeautifulSoup(desc, "html.parser").get_text(" ", strip=True)
        pub_str = item.findtext("pubDate", "")
        pub: datetime | None = None
        try:
            pub = datetime.strptime(pub_str, "%a, %d %b %Y %H:%M:%S %z")
        except ValueError:
            pass  # pub stays None — will be dropped below
        if not title or not link:
            continue
        results.append({
            "title": title, "url": link, "source": feed["name"],
            "snippet": desc[:500], "published_at": pub,
            "detected_ticker": None,
        })
    return results


# ---------------------------------------------------------------------------
# Ticker detection — loaded from DB
# ---------------------------------------------------------------------------

# AliasEntry: (symbol, ticker_id, skip_symbol_tag, aliases)
AliasEntry = tuple[str, str, bool, list[str]]


async def load_alias_entries(conn) -> list[AliasEntry]:
    """
    Load all tickers from DB with their aliases.
    Returns list of (symbol, ticker_id, skip_symbol_tag, aliases).
    skip_symbol_tag tickers are not matched by their 4-letter code — only by
    name aliases — to avoid false positives (e.g. BULL, DEWA, BUMI).
    """
    import json as _json
    overrides_file = PROJECT_ROOT / "backend" / "db" / "ticker_overrides.json"
    skip_symbols: set[str] = set()
    if overrides_file.exists():
        raw = _json.loads(overrides_file.read_text(encoding="utf-8"))
        skip_symbols = {k for k, v in raw.items()
                        if not k.startswith("_") and v.get("skip_symbol_tag")}

    rows = await conn.fetch(
        "SELECT id, symbol, aliases FROM tickers ORDER BY symbol"
    )
    result: list[AliasEntry] = []
    for r in rows:
        sym      = r["symbol"]
        tid      = r["id"]
        aliases  = list(r["aliases"] or [])
        skip_tag = sym in skip_symbols
        result.append((sym, tid, skip_tag, aliases))
    return result


def _build_shared_aliases(entries: list[AliasEntry]) -> set[str]:
    """Return the set of alias strings (lowercased) that appear in >1 ticker."""
    from collections import Counter
    counter: Counter[str] = Counter()
    for _sym, _tid, _skip, aliases in entries:
        for a in aliases:
            counter[a.lower()] += 1
    return {a for a, cnt in counter.items() if cnt > 1}


# Confidence tiers
#   'high'   — ticker 4-letter CODE found as a word in text (most reliable)
#   'medium' — unique alias match (alias belongs to exactly one ticker)
#   'low'    — shared alias match (alias belongs to multiple tickers)
#
# Low-confidence mentions are stored only when:
#   (a) the ticker's CODE also appears in the article text, OR
#   (b) no high/medium confidence match was found for any ticker

ConfidenceEntry = tuple[str, str]  # (ticker_id, confidence)


def detect_tickers(
    text: str,
    entries: list[AliasEntry],
    shared_aliases: set[str],
) -> list[ConfidenceEntry]:
    """
    Returns list of (ticker_id, confidence) matched in `text`.
    Each ticker is matched at most once; the highest confidence found wins.
    """
    padded = f" {text} "
    upper  = padded.upper()

    found: list[ConfidenceEntry] = []
    seen:  set[str]              = set()

    for symbol, tid, skip_tag, aliases in entries:
        if tid in seen:
            continue

        confidence: str | None = None

        # ── 1. High: symbol code appears as a word ─────────────────────────
        if not skip_tag:
            for sep_after in (" ", ",", ".", ":", ";", ")", "\n"):
                if f" {symbol}{sep_after}" in upper:
                    confidence = "high"
                    break

        # ── 2. Medium / Low: alias match ───────────────────────────────────
        if confidence is None:
            for alias in aliases:
                if alias.upper() in upper:
                    tier = "low" if alias.lower() in shared_aliases else "medium"
                    # Take the best tier found across all aliases
                    if confidence is None or tier == "medium":
                        confidence = tier
                    if confidence == "medium":
                        break  # can't do better at alias level

        if confidence is not None:
            found.append((tid, confidence))
            seen.add(tid)

    # ── Filter low-confidence matches ──────────────────────────────────────
    has_high_or_medium = any(c in ("high", "medium") for _, c in found)
    result: list[ConfidenceEntry] = []
    for tid, conf in found:
        if conf == "low":
            # Keep low-confidence only if the ticker CODE appears in text
            # AND there are no higher-confidence matches (avoid noise)
            sym = next((s for s, i, _, _ in entries if i == tid), "")
            code_present = any(
                f" {sym}{sep}" in upper
                for sep in (" ", ",", ".", ":", ";", ")", "\n")
            )
            if has_high_or_medium and not code_present:
                continue  # drop noisy low-confidence hit
        result.append((tid, conf))

    return result


# ---------------------------------------------------------------------------
# Async DB helpers
# ---------------------------------------------------------------------------

async def load_ticker_map(conn) -> dict[str, str]:
    rows = await conn.fetch("SELECT id, symbol FROM tickers")
    return {r["symbol"]: r["id"] for r in rows}


async def load_tag_enabled_symbols(conn) -> list[str]:
    rows = await conn.fetch(
        "SELECT symbol FROM tickers WHERE ticker_tag_enabled = TRUE ORDER BY symbol"
    )
    return [r["symbol"] for r in rows]


async def load_tag_enabled_ticker_rows(conn) -> list[dict]:
    """Return full ticker info (symbol, name, aliases) for all tag-enabled tickers."""
    rows = await conn.fetch(
        "SELECT symbol, name, aliases FROM tickers WHERE ticker_tag_enabled = TRUE ORDER BY symbol"
    )
    return [{"symbol": r["symbol"], "name": r["name"], "aliases": list(r["aliases"] or [])}
            for r in rows]


async def load_all_ticker_rows(conn, tier: str = "all") -> list[dict]:
    """
    Return full ticker info for Google News queries.

    tier:
      "big"   — tickers with market_cap IS NOT NULL, sorted largest first
                 (useful for frequent hourly runs on the most-traded stocks)
      "small" — tickers with market_cap IS NULL or zero (long-tail / no price data)
      "all"   — every ticker sorted by market_cap DESC NULLS LAST

    Tiers let the scheduler run big-caps every 2h and small-caps once daily
    without duplicating effort.
    """
    if tier == "big":
        rows = await conn.fetch(
            "SELECT symbol, name, aliases, market_cap FROM tickers "
            "WHERE market_cap IS NOT NULL AND market_cap > 0 "
            "ORDER BY market_cap DESC"
        )
    elif tier == "small":
        rows = await conn.fetch(
            "SELECT symbol, name, aliases, market_cap FROM tickers "
            "WHERE market_cap IS NULL OR market_cap = 0 "
            "ORDER BY symbol"
        )
    else:  # all
        rows = await conn.fetch(
            "SELECT symbol, name, aliases, market_cap FROM tickers "
            "ORDER BY market_cap DESC NULLS LAST, symbol"
        )
    return [
        {"symbol": r["symbol"], "name": r["name"], "aliases": list(r["aliases"] or [])}
        for r in rows
    ]


async def article_exists(conn, url: str) -> bool:
    row = await conn.fetchrow("SELECT 1 FROM articles WHERE url = $1", url)
    return row is not None


async def insert_article(conn, ticker_id: str | None, art: dict) -> str:
    art_id = str(uuid.uuid4())
    await conn.execute(
        """
        INSERT INTO articles
          (id, ticker_id, title, original_summary, url, source,
           published_at, sentiment, impact_score, category, is_early_signal)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
        ON CONFLICT DO NOTHING
        """,
        art_id, ticker_id,
        art["title"], art.get("snippet", ""), art["url"], art["source"],
        art["published_at"], "NEUTRAL", 5.0, "GENERAL", False,
    )
    return art_id


async def link_ticker_mention(
    conn, article_id: str, ticker_id: str, confidence: str = "medium"
) -> None:
    await conn.execute(
        """
        INSERT INTO ticker_mentions (article_id, ticker_id, match_confidence)
        VALUES ($1, $2, $3)
        ON CONFLICT DO NOTHING
        """,
        article_id, ticker_id, confidence,
    )


# ---------------------------------------------------------------------------
# Macro-relevance filter (Task 3)
# ---------------------------------------------------------------------------

# Keywords that mark an article as macro/sector news worth keeping even when
# no specific ticker is directly named.  These articles are stored with
# ticker_id = NULL and are later processed by the macro-impact enrichment step
# to identify AFFECTED tickers (BUMI, PTRO, ADRO, etc.).
MACRO_KEYWORDS: list[str] = [
    # Coal / mining (BUMI, PTRO, ADRO, ITMG, PTBA, DOID, HRUM)
    "batubara", "batu bara", "coal",
    "tambang batubara", "pertambangan",
    # Palm oil (AALI, SSMS, DSNG, SIMP, LSIP)
    "minyak sawit", "kelapa sawit", "cpo", "crude palm oil",
    # Oil & gas (MEDC, PGAS, ESSA, RELI)
    "minyak mentah", "minyak bumi", "gas alam", "lng",
    # Metals / nickel (INCO, ANTM, MBMA, NICL, MDKA)
    "nikel", "nickel", "tembaga", "copper", "timah",
    # Macro / rates — affects banks, property, leveraged sectors
    "bi rate", "suku bunga", "bank indonesia", "inflasi",
    "rupiah", "dolar as", "nilai tukar",
    "naikan suku bunga", "naikkan suku bunga", "kenaikan suku bunga",
    "turunkan suku bunga", "penurunan suku bunga",
    # Mortgage / property financing (BKSL, BSDE, CTRA, SMRA, PWON, LPKR)
    "kpr", "kredit pemilikan rumah", "kredit perumahan",
    "properti", "sektor properti", "pengembang properti",
    "apartemen", "perumahan",
    # Banking (BBCA, BBRI, BMRI, BBNI etc.)
    "nim", "net interest margin", "dana pihak ketiga", "dpk",
    "kredit bermasalah", "npf", "npl",
    # Regulation / export (very broad impact)
    "ekspor batubara", "larangan ekspor", "bea ekspor", "royalti",
    "dmob", "domestic market obligation",
    # Energy transition (affects coal / EV tickers)
    "energi terbarukan", "ets", "carbon", "emisi",
    # Government / economic policy
    "esdm", "kementerian pertambangan",
    "harga komoditas", "komoditas",
    # Consumer / retail (UNVR, ICBP, INDF, AMRT)
    "daya beli", "konsumsi rumah tangga",
    # Infrastructure / construction
    "infrastruktur", "konstruksi", "tender proyek",
]

_MACRO_KEYWORDS_LOWER = [kw.lower() for kw in MACRO_KEYWORDS]


def is_macro_relevant(text: str) -> bool:
    """Return True if the article looks like macro/sector news worth keeping."""
    lower = text.lower()
    return any(kw in lower for kw in _MACRO_KEYWORDS_LOWER)


# ---------------------------------------------------------------------------
# IHSG roundup / market-recap filter
# ---------------------------------------------------------------------------

# Titles matching these patterns are IHSG recap articles ("IHSG naik X%, saham
# BBCA BBRI TLKM kompak hijau") — they mention many tickers incidentally.
# Tagging those tickers as direct mentions would pollute individual ticker pages.
# These articles are reclassified as MACRO (ticker_id = NULL).

_IHSG_ROUNDUP_PATTERNS = [
    # IHSG direction headlines
    r"\bihsg\b.{0,40}\b(naik|turun|menguat|melemah|rebound|rally|merosot|melesat|anjlok)\b",
    r"\b(naik|turun|menguat|melemah|rebound|rally|merosot|melesat|anjlok)\b.{0,30}\bihsg\b",
    # "Top gainers/losers" recaps
    r"\btop\s+(gainer|loser|saham)\b",
    r"\bsaham[- ]saham\s+(yang\s+)?(naik|turun|melesat|merosot|menguat|melemah)\b",
    # Roundup framing: "Ini saham-saham pilihan hari ini"
    r"\bsaham[- ]saham\b.{0,30}\bhari\s+ini\b",
    # "Gerak saham BBCA BBRI hari ini" — multi-ticker day roundups
    r"\bgerak\s+saham\b",
    r"\bpergerakan\s+saham\b.{0,30}\bhari\s+ini\b",
    # Closing/opening recap
    r"\bpenutupan\s+(pasar|bursa|ihsg)\b",
    r"\bpembukaan\s+(pasar|bursa|ihsg)\b",
    # "Pilihan saham", "Rekomendasi saham" (multi-ticker recommendation blasts)
    r"\b(rekomendasi|pilihan|watchlist)\s+saham\b",
]

import re as _re_module

_IHSG_ROUNDUP_COMPILED = [
    _re_module.compile(p, _re_module.IGNORECASE) for p in _IHSG_ROUNDUP_PATTERNS
]


def is_ihsg_roundup(title: str, matched_ticker_count: int = 0) -> bool:
    """
    Return True if this article is an IHSG/market recap that should be stored
    as MACRO rather than creating direct ticker mentions.

    Triggers when:
      (a) The title matches a known roundup pattern, OR
      (b) More than 3 distinct tickers were detected (suggests a bulk roundup)
    """
    lower_title = title.lower()
    for pat in _IHSG_ROUNDUP_COMPILED:
        if pat.search(lower_title):
            return True
    if matched_ticker_count > 3:
        return True
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run_once(
    rss_limit: int,
    use_ticker_tags: bool,
    use_google_news: bool = False,
    gn_tier: str = "tag",  # "tag" | "big" | "small" | "all"
) -> None:
    # ── Phase 1: Load ticker metadata (quick DB round-trip) ──────────────────
    # Open and immediately close the connection so scraping (which can take
    # 5+ minutes for Google News across 94+ tickers) doesn't idle out the
    # connection.  We reopen a fresh connection before the insert phase.
    conn = await get_conn()
    try:
        alias_entries  = await load_alias_entries(conn)
        symbol_map     = {sym: tid for sym, tid, _, _ in alias_entries}
        tag_symbols    = await load_tag_enabled_symbols(conn)
        shared_aliases = _build_shared_aliases(alias_entries)

        if use_google_news:
            if gn_tier == "tag":
                ticker_rows_gn = await load_tag_enabled_ticker_rows(conn)
            else:
                ticker_rows_gn = await load_all_ticker_rows(conn, tier=gn_tier)
        else:
            ticker_rows_gn = []
    finally:
        await conn.close()

    print(f"[ingest] {len(alias_entries)} tickers loaded | "
          f"{len(tag_symbols)} ticker-tag enabled | "
          f"{len(shared_aliases)} shared alias strings")

    all_articles: list[dict] = []

    # ── Source 1: Per-ticker Detik tag pages (ticker_tag_enabled only) ──
    if use_ticker_tags:
        print(f"[ingest] Scraping {len(tag_symbols)} ticker tag pages (2s delay each) ...")
        tag_articles = fetch_all_tickers(tag_symbols, delay_seconds=2.0, max_per_ticker=15)
        print(f"[ingest] Ticker tags: {len(tag_articles)} articles")
        all_articles.extend(tag_articles)

    # ── Source 2: Google News RSS per-ticker ─────────────────────────────────
    if use_google_news:
        tier_label = f"tier={gn_tier}"
        print(f"[ingest] Google News: querying {len(ticker_rows_gn)} tickers "
              f"({tier_label}, 3s delay each) ...")
        gn_articles = fetch_all_google_news(
            ticker_rows_gn, delay_seconds=3.0, max_per_ticker=10,
        )
        print(f"[ingest] Google News: {len(gn_articles)} articles")
        all_articles.extend(gn_articles)

    # ── Sources 2+: General RSS feeds ────────────────────────────────────
    for feed in FEEDS:
        items = fetch_rss(feed, limit=rss_limit)
        print(f"[ingest] RSS {feed['name']}: {len(items)} fetched")
        all_articles.extend(items)

    # ── Sources: HTML scrapers (IDX Channel, Bisnis.com, Emiten News) ────
    for name, fn in [
        ("IDX Channel", fetch_idxchannel),
        ("Bisnis.com",  fetch_bisnis),
        ("Emiten News", fetch_emitennews),
    ]:
        items = fn(limit=rss_limit)
        print(f"[ingest] HTML {name}: {len(items)} fetched")
        all_articles.extend(items)

    # ── Dedup by URL ──────────────────────────────────────────────────────
    seen_urls: set[str] = set()
    unique: list[dict]  = []
    for art in all_articles:
        if art["url"] not in seen_urls:
            seen_urls.add(art["url"])
            unique.append(art)
    print(f"[ingest] {len(unique)} unique articles after URL dedup")

    # ── Semantic dedup — same story from multiple sources ──────────────────
    # Cross-source: Jaccard ≥ 0.80 within 6h window → keep highest-tier source
    # Same-source:  Jaccard ≥ 0.90 within 6h window → keep earliest
    from .dedup import dedup_batch, normalise as _normalise, \
                       word_set as _word_set, jaccard as _jaccard, \
                       normalize_source as _norm_src
    unique = dedup_batch(unique, ticker_key="detected_ticker")
    print(f"[ingest] {len(unique)} articles after semantic dedup")

    # ── Freshness filter — drop articles with no date or older than 30 days ──
    cutoff     = datetime.now(timezone.utc) - timedelta(days=30)
    fresh: list[dict] = []
    dropped_no_date = dropped_stale = 0
    for art in unique:
        pub = art.get("published_at")
        if pub is None:
            dropped_no_date += 1
        elif pub < cutoff:
            dropped_stale += 1
        else:
            fresh.append(art)
    if dropped_no_date or dropped_stale:
        print(f"[ingest] Dropped: {dropped_no_date} no-date, "
              f"{dropped_stale} stale (>30d) - {len(fresh)} remain")
    unique = fresh

    # ── Phase 2: Insert — fresh connection (old one was closed after ticker load) ──
    conn = await get_conn()
    try:
        inserted = skipped_dup = skipped_no_ticker = macro_stored = 0
        ticker_hit_counts: dict[str, int] = {}
        confidence_counts: dict[str, int] = {"high": 0, "medium": 0, "low": 0}

        # ── Inter-batch dedup: load recently-stored titles so articles that
        # arrived via RSS in run N are caught when GN brings the same story in
        # run N+1.  dedup_batch() only deduplicates within a single scrape
        # batch; this closes the cross-batch gap using the same Jaccard logic.
        _recent_rows = await conn.fetch(
            "SELECT title, source FROM articles "
            "WHERE published_at >= NOW() - INTERVAL '6 hours'"
        )
        _recent_norms: list[tuple] = [
            (_normalise(r["title"]), _word_set(_normalise(r["title"])), r["source"])
            for r in _recent_rows
        ]
        print(f"[ingest] Inter-batch dedup anchor: {len(_recent_norms)} articles in last 6h")

        for art in unique:
            # Inter-batch title similarity check against already-stored articles
            _art_norm  = _normalise(art["title"])
            _art_words = _word_set(_art_norm)
            _is_ibd    = False
            for _db_norm, _db_words, _db_src in _recent_norms:
                _same_src  = _norm_src(art.get("source")) == _norm_src(_db_src)
                _threshold = 0.90 if _same_src else 0.80
                if _art_norm == _db_norm or _jaccard(_art_words, _db_words) >= _threshold:
                    _is_ibd = True
                    break
            if _is_ibd:
                skipped_dup += 1
                continue

            if await article_exists(conn, art["url"]):
                skipped_dup += 1
                continue

            # Determine matching ticker IDs with confidence
            if art.get("detected_ticker"):
                # Articles from ticker-tag / Google News scraper: code is known
                sym = art["detected_ticker"]
                tid = symbol_map.get(sym)
                matched: list[tuple[str, str]] = [(tid, "high")] if tid else []
            else:
                search_text = f"{art['title']} {art['snippet']}"
                matched = detect_tickers(search_text, alias_entries, shared_aliases)

            if not matched:
                # No direct ticker match — check if macro/sector relevant
                search_text = f"{art['title']} {art.get('snippet', '')}"
                if is_macro_relevant(search_text):
                    # Store with NULL ticker_id for macro-impact enrichment later
                    await insert_article(conn, None, art)
                    macro_stored += 1
                else:
                    skipped_no_ticker += 1
                continue

            # ── IHSG roundup guard ────────────────────────────────────────────
            # If the title looks like a market-recap / bulk roundup, do NOT
            # create individual ticker mentions — store as MACRO instead so it
            # doesn't pollute individual ticker pages.
            if is_ihsg_roundup(art["title"], matched_ticker_count=len(matched)):
                await insert_article(conn, None, art)
                macro_stored += 1
                continue

            primary_id, primary_conf = matched[0]
            art_id = await insert_article(conn, primary_id, art)

            for tid, conf in matched:
                await link_ticker_mention(conn, art_id, tid, conf)
                sym = next((s for s, i, _, _ in alias_entries if i == tid), "?")
                ticker_hit_counts[sym] = ticker_hit_counts.get(sym, 0) + 1
                confidence_counts[conf] = confidence_counts.get(conf, 0) + 1

            inserted += 1

        # ── Summary ───────────────────────────────────────────────────────────
        total_in_db    = await conn.fetchval("SELECT count(*) FROM articles")
        unique_tickers = await conn.fetchval(
            "SELECT count(DISTINCT ticker_id) FROM ticker_mentions"
        )

        print(f"\n[ingest] Done: inserted={inserted} macro={macro_stored} "
              f"dup={skipped_dup} dropped={skipped_no_ticker}")
        print(f"[ingest] Confidence breakdown (new mentions): "
              f"high={confidence_counts['high']} "
              f"medium={confidence_counts['medium']} "
              f"low={confidence_counts['low']}")
        print(f"[ingest] DB total: {total_in_db} articles | "
              f"{unique_tickers} unique tickers mentioned")
        if ticker_hit_counts:
            print("[ingest] New articles per ticker:")
            for sym, cnt in sorted(ticker_hit_counts.items(), key=lambda x: -x[1])[:15]:
                print(f"  {sym}: {cnt}")
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Single-instance lock (prevents concurrent ingest runs)
# ---------------------------------------------------------------------------

import os as _os
import sys as _sys

_LOCKFILE = PROJECT_ROOT / "logs" / "ingest.lock"


def _acquire_lock() -> None:
    """
    Write a PID lockfile so a second ingest process can detect the first
    and exit cleanly instead of running concurrently.

    If the lockfile exists but the recorded PID is no longer alive (stale
    lock from a crash or sleep/shutdown), the old file is silently overwritten.

    Uses Windows tasklist instead of os.kill(pid, 0): on Windows, os.kill
    raises SystemError (not OSError) for dead PIDs in some Python builds,
    which bypassed the stale-lock handler and blocked all subsequent runs.
    """
    if _LOCKFILE.exists():
        try:
            pid = int(_LOCKFILE.read_text().strip())
        except (ValueError, OSError):
            pass  # unreadable — treat as stale
        else:
            try:
                import subprocess as _sp
                result = _sp.run(
                    ['tasklist', '/FI', f'PID eq {pid}', '/NH'],
                    capture_output=True, text=True, timeout=5,
                )
                if str(pid) in result.stdout:
                    print(f"[ingest] Already running (PID {pid}) — exiting to avoid concurrent run.")
                    _sys.exit(0)
                # PID absent from tasklist → process is dead → stale lock, proceed
            except Exception:
                pass  # tasklist unavailable or timed out — treat as stale, proceed
    _LOCKFILE.write_text(str(_os.getpid()))


def _release_lock() -> None:
    try:
        _LOCKFILE.unlink()
    except FileNotFoundError:
        pass


def main() -> None:
    _acquire_lock()
    try:
        parser = argparse.ArgumentParser(description="IDXDaily ingest worker")
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--limit", type=int, default=50,
                            help="Max items per RSS feed (default: 50)")
        parser.add_argument("--ticker-tags", action="store_true",
                            help="Also scrape per-ticker Detik pages (ticker_tag_enabled only)")
        parser.add_argument("--google-news", action="store_true",
                            help="Fetch Google News RSS per ticker (see --gn-tier for scope)")
        parser.add_argument(
            "--gn-tier",
            choices=["tag", "big", "small", "all"],
            default="tag",
            help=(
                "Which tickers to query for Google News. "
                "'tag' = tag-enabled only (~94 tickers, default); "
                "'big' = tickers with market_cap data, largest first; "
                "'small' = tickers with no market_cap (long-tail); "
                "'all' = every ticker in DB, sorted by market_cap DESC. "
                "Recommended schedule: --gn-tier big every 2h, --gn-tier small once daily."
            ),
        )
        args = parser.parse_args()
        asyncio.run(run_once(args.limit, args.ticker_tags, args.google_news, args.gn_tier))
    finally:
        _release_lock()


if __name__ == "__main__":
    main()

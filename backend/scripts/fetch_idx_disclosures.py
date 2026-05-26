#!/usr/bin/env python3
"""
IDX Keterbukaan Informasi (official disclosure) scraper.

Uses Playwright (headless Chromium) to bypass the Cloudflare protection on
idx.co.id and fetch the latest corporate disclosure filings.  These are
inserted as articles with source="IDX Disclosures" and tagged to the
relevant ticker via direct symbol detection.

Setup (one-time):
    pip install playwright
    playwright install chromium

Run manually:
    python -m backend.scripts.fetch_idx_disclosures --limit 50

Or call fetch_idx_disclosures() from the ingest worker with --idx-disclosures flag
after confirming Playwright is available.

What it does:
  1. Opens https://www.idx.co.id/id/perusahaan-tercatat/keterbukaan-informasi/
  2. Waits for the disclosure table to load
  3. Parses rows: Kode (symbol), Judul (title), Tanggal (date)
  4. For each, inserts an article linked to the matching ticker

Note: This script is intentionally separate from the main ingest worker because
Playwright is a heavy dependency.  The main ingest pipeline runs fine without it.
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env.local", override=True)


IDX_DISCLOSURE_URL = "https://www.idx.co.id/id/perusahaan-tercatat/keterbukaan-informasi/"
IDX_BASE_URL       = "https://www.idx.co.id"


async def scrape_idx_disclosures(limit: int = 50) -> list[dict]:
    """
    Use Playwright to load the IDX disclosure page and parse the table.
    Returns list of article-like dicts (title, url, source, published_at, detected_ticker).
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("[idx-disclosures] ERROR: Playwright not installed.")
        print("  Run: pip install playwright && playwright install chromium")
        return []

    results: list[dict] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page    = await browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="id-ID",
        )

        print(f"[idx-disclosures] Loading {IDX_DISCLOSURE_URL} ...")
        await page.goto(IDX_DISCLOSURE_URL, wait_until="networkidle", timeout=60_000)

        # Wait for the disclosure table — it loads dynamically via JS
        try:
            await page.wait_for_selector("table tbody tr", timeout=20_000)
        except Exception:
            print("[idx-disclosures] Timed out waiting for table. Dumping page title.")
            print(f"  Title: {await page.title()}")
            await browser.close()
            return []

        # Grab all table rows
        rows = await page.query_selector_all("table tbody tr")
        print(f"[idx-disclosures] Found {len(rows)} disclosure rows")

        cutoff = datetime.now(timezone.utc) - timedelta(days=7)

        for row in rows[:limit]:
            cells = await row.query_selector_all("td")
            if len(cells) < 4:
                continue

            # Typical columns: No | Kode | Jenis | Judul | Tanggal
            # Column positions vary — look for link in any cell
            code  = (await cells[1].inner_text()).strip().upper()
            title = (await cells[3].inner_text()).strip() if len(cells) > 3 else ""
            date_str = (await cells[4].inner_text()).strip() if len(cells) > 4 else ""

            if not code or not title:
                continue

            # Try to find the disclosure link
            link_el = await row.query_selector("a[href]")
            url = ""
            if link_el:
                href = await link_el.get_attribute("href")
                url = href if href and href.startswith("http") else IDX_BASE_URL + (href or "")

            if not url:
                # Construct a stable pseudo-URL so we can deduplicate
                slug = title.lower().replace(" ", "-")[:50]
                url = f"{IDX_BASE_URL}/disclosure/{code}/{slug}"

            # Parse date: "22/05/2026" or "22/05/2026 14:30"
            pub: datetime | None = None
            for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y"):
                try:
                    pub = datetime.strptime(date_str, fmt).replace(
                        tzinfo=timezone(timedelta(hours=7))  # WIB
                    )
                    break
                except ValueError:
                    continue

            if pub is None:
                pub = datetime.now(timezone.utc)

            if pub < cutoff:
                continue  # skip old disclosures

            results.append({
                "title":           f"[IDX] {code}: {title}",
                "url":             url,
                "source":          "IDX Disclosures",
                "snippet":         "",
                "published_at":    pub,
                "detected_ticker": code,
            })

        await browser.close()

    return results


async def run(limit: int) -> None:
    """Fetch disclosures and insert into DB."""
    # Inline DB helpers (avoid importing ingest to keep this self-contained)
    from backend.workers._db import get_conn

    articles = await scrape_idx_disclosures(limit=limit)
    if not articles:
        print("[idx-disclosures] No articles retrieved.")
        return

    print(f"[idx-disclosures] Inserting {len(articles)} disclosures ...")

    conn = await get_conn()
    try:
        # Load ticker map
        ticker_rows = await conn.fetch("SELECT id, symbol FROM tickers")
        symbol_map  = {r["symbol"]: r["id"] for r in ticker_rows}

        inserted = skipped_dup = skipped_no_ticker = 0
        for art in articles:
            # Check duplicate
            exists = await conn.fetchrow("SELECT 1 FROM articles WHERE url = $1", art["url"])
            if exists:
                skipped_dup += 1
                continue

            sym = art["detected_ticker"]
            tid = symbol_map.get(sym)
            if not tid:
                skipped_no_ticker += 1
                continue

            art_id = str(uuid.uuid4())
            await conn.execute(
                """
                INSERT INTO articles
                  (id, ticker_id, title, original_summary, url, source,
                   published_at, sentiment, impact_score, category, is_early_signal)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                ON CONFLICT DO NOTHING
                """,
                art_id, tid,
                art["title"], art.get("snippet", ""), art["url"], art["source"],
                art["published_at"], "NEUTRAL", 7.0,  # disclosures start high-impact
                "CORPORATE_DISCLOSURE", True,          # is_early_signal = True
            )
            await conn.execute(
                "INSERT INTO ticker_mentions (article_id, ticker_id, match_confidence) "
                "VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                art_id, tid, "high",
            )
            inserted += 1
            print(f"  [{sym}] {art['title'][:70]}")

        print(f"\n[idx-disclosures] Done: inserted={inserted} dup={skipped_dup} "
              f"no_ticker={skipped_no_ticker}")
    finally:
        await conn.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="IDX Keterbukaan Informasi scraper (requires Playwright)")
    parser.add_argument("--limit", type=int, default=50, help="Max rows to fetch (default: 50)")
    args = parser.parse_args()
    asyncio.run(run(args.limit))

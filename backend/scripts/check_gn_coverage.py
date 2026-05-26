#!/usr/bin/env python3
"""
check_gn_coverage.py — Coverage health-check for Google News ticker ingestion.

Detects the class of bug where a ticker is ticker_tag_enabled and Google News
returns results for it, but our DB has ZERO stored articles — meaning coverage
is silently missing.

Usage:
  python -m backend.scripts.check_gn_coverage          # check all tag-enabled
  python -m backend.scripts.check_gn_coverage --ticker PACK
  python -m backend.scripts.check_gn_coverage --days 7   # look-back window

Exit code 1 if any gap is found (useful for CI/cron alerting).
"""

import argparse
import asyncio
import sys
import time
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / '.env')
load_dotenv(PROJECT_ROOT / '.env.local', override=True)

from backend.scrapers.google_news import fetch_google_news_ticker, _best_query_name
from backend.workers._db import get_conn


async def run_check(specific_ticker: str | None = None, days: int = 30) -> bool:
    """
    Returns True if all checked tickers are OK, False if any coverage gap found.
    """
    conn = await get_conn()
    try:
        if specific_ticker:
            rows = await conn.fetch(
                "SELECT symbol, name, aliases FROM tickers WHERE symbol = $1",
                specific_ticker.upper()
            )
        else:
            rows = await conn.fetch("""
                SELECT t.symbol, t.name, t.aliases,
                       COUNT(a.id) FILTER (
                           WHERE a.published_at > NOW() - ($1 || ' days')::INTERVAL
                       ) AS recent_count
                FROM tickers t
                LEFT JOIN articles a ON a.ticker_id = t.id
                WHERE t.ticker_tag_enabled = TRUE
                GROUP BY t.id, t.symbol, t.name, t.aliases
                HAVING COUNT(a.id) FILTER (
                    WHERE a.published_at > NOW() - ($1 || ' days')::INTERVAL
                ) = 0
                ORDER BY t.symbol
            """, str(days))

        if not rows:
            if specific_ticker:
                print(f"[coverage-check] Ticker {specific_ticker} not found or not tag-enabled.")
            else:
                print(f"[coverage-check] All ticker_tag_enabled tickers have recent articles. OK.")
            return True

        if not specific_ticker:
            print(f"[coverage-check] {len(rows)} tag-enabled tickers with zero articles in last {days}d")
            print(f"[coverage-check] Checking Google News for each (3s delay per ticker)...")
    finally:
        await conn.close()

    gaps = []
    all_ok = True

    for i, row in enumerate(rows):
        sym     = row['symbol']
        name    = row['name']
        aliases = list(row['aliases'] or [])
        qname   = _best_query_name(name, aliases)

        arts = fetch_google_news_ticker(sym, name, aliases, max_articles=5)

        if arts:
            all_ok = False
            gaps.append((sym, qname, len(arts), arts[0]['title']))
            pub = arts[0]['published_at'].strftime('%Y-%m-%d')
            print(f"  GAP  {sym:8s} ({qname!r:30s}) — {len(arts)} GN result(s), latest [{pub}]: {arts[0]['title'][:55]}")
        else:
            print(f"  OK   {sym:8s} ({qname!r:30s}) — no GN results (no news, gap expected)")

        if i < len(rows) - 1:
            time.sleep(3.0)

    print()
    if gaps:
        print(f"[coverage-check] ALERT: {len(gaps)} ticker(s) have Google News coverage but ZERO stored articles:")
        for sym, qname, cnt, title in gaps:
            print(f"  {sym}: {cnt} GN result(s) — fix: ensure ticker_tag_enabled=TRUE and scheduler is running")
        print("[coverage-check] Run: python -m backend.workers.ingest --google-news --gn-tier tag")
    else:
        print("[coverage-check] All checked tickers: OK (no silent coverage gaps).")

    return all_ok


def main() -> None:
    parser = argparse.ArgumentParser(description="Google News coverage health-check")
    parser.add_argument("--ticker", help="Check a specific ticker only")
    parser.add_argument("--days", type=int, default=30,
                        help="Look-back window in days (default: 30)")
    args = parser.parse_args()

    ok = asyncio.run(run_check(args.ticker, args.days))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

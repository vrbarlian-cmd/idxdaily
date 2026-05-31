#!/usr/bin/env python3
"""
diagnose_coverage.py — Root-cause diagnosis for small-cap coverage gaps.

This script was written to investigate why BNBR, CUAN, and other active
small-caps show zero or near-zero news despite Google News having coverage.

It traces EVERY step of the pipeline for each ticker you specify:

  Step 1 — Is the ticker in the DB?  What are its aliases?
  Step 2 — Is ticker_tag_enabled?    (required for Google News scraping)
  Step 3 — What query name does Google News use?
  Step 4 — Does Google News actually return results for that query?
  Step 5 — How many articles are in DB for this ticker (last 7/30 days)?
  Step 6 — For RSS articles: simulate alias detection on sample titles
            to see if the ticker would have been matched.

Usage:
  python -m backend.scripts.diagnose_coverage
  python -m backend.scripts.diagnose_coverage --tickers BNBR CUAN PACK
  python -m backend.scripts.diagnose_coverage --all-gaps --days 7
        (checks every ticker with zero articles in last N days)

ROOT CAUSE SUMMARY printed at the end classifies each gap into one of:
  [NOT_TAG_ENABLED]   Google News not scraped — add ticker_tag_enabled=TRUE
  [BAD_ALIASES]       Alias detection fails on typical article titles
  [NO_GN_RESULTS]     No Google News results — maybe niche ticker, no coverage
  [DB_FILTER]         Articles fetched but dropped (freshness, no ticker match)
  [OK]                Coverage looks fine
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env.local", override=True)

from backend.scrapers.google_news import fetch_google_news_ticker, _best_query_name
from backend.workers._db import get_conn
from backend.workers.ingest import detect_tickers, load_alias_entries, _build_shared_aliases


# ── Default watchlist of active small-caps known to have coverage gaps ────────

DEFAULT_WATCHLIST = [
    "BNBR",  # Bakrie & Brothers — active right-issue news
    "CUAN",  # Petrindo Jaya Kreasi — skip_symbol_tag=true, limited aliases
    "PACK",  # Container / packaging sector
    "BRIS",  # Bank Syariah Indonesia
    "NICL",  # Nickel Ind
    "ITMG",  # Indo Tambangraya (coal)
]


async def diagnose_ticker(
    conn,
    alias_entries,
    shared_aliases,
    symbol: str,
    days: int = 7,
    delay: float = 2.0,
) -> dict:
    """Run full pipeline trace for one ticker. Returns a diagnosis dict."""
    result = {
        "symbol": symbol,
        "in_db": False,
        "tag_enabled": False,
        "aliases": [],
        "query_name": None,
        "gn_results": 0,
        "gn_latest_title": None,
        "db_articles_7d": 0,
        "db_articles_30d": 0,
        "skip_symbol_tag": False,
        "root_cause": "UNKNOWN",
        "recommendations": [],
    }

    # ── Step 1: Ticker in DB? ────────────────────────────────────────────────
    row = await conn.fetchrow(
        "SELECT id, name, aliases, ticker_tag_enabled, market_cap "
        "FROM tickers WHERE symbol = $1",
        symbol.upper(),
    )
    if not row:
        result["in_db"]       = False
        result["root_cause"]  = "NOT_IN_DB"
        result["recommendations"].append(
            f"Run sync_idx_tickers.py — {symbol} is not in the tickers table."
        )
        return result

    result["in_db"]       = True
    result["tag_enabled"] = bool(row["ticker_tag_enabled"])
    result["aliases"]     = list(row["aliases"] or [])
    result["name"]        = row["name"]
    result["market_cap"]  = row["market_cap"]

    # ── Step 2: skip_symbol_tag? ─────────────────────────────────────────────
    import json as _json
    overrides_file = PROJECT_ROOT / "backend" / "db" / "ticker_overrides.json"
    if overrides_file.exists():
        overrides = _json.loads(overrides_file.read_text(encoding="utf-8"))
        override  = overrides.get(symbol, {})
        result["skip_symbol_tag"] = bool(override.get("skip_symbol_tag", False))
        extra_slugs = override.get("name_slugs", [])
    else:
        extra_slugs = []

    # ── Step 3: Google News query name ───────────────────────────────────────
    result["query_name"] = _best_query_name(row["name"], result["aliases"])

    # ── Step 4: Live Google News results ─────────────────────────────────────
    time.sleep(delay)
    gn_arts = fetch_google_news_ticker(
        symbol, row["name"], result["aliases"], max_articles=5
    )
    result["gn_results"]      = len(gn_arts)
    result["gn_latest_title"] = gn_arts[0]["title"] if gn_arts else None

    # ── Step 5: DB article counts ────────────────────────────────────────────
    result["db_articles_7d"] = await conn.fetchval("""
        SELECT COUNT(DISTINCT a.id)
        FROM articles a
        JOIN ticker_mentions tm ON tm.article_id = a.id
        JOIN tickers t ON t.id = tm.ticker_id
        WHERE t.symbol = $1
          AND a.published_at >= NOW() - INTERVAL '7 days'
          AND tm.match_confidence IN ('high', 'medium')
    """, symbol)

    result["db_articles_30d"] = await conn.fetchval("""
        SELECT COUNT(DISTINCT a.id)
        FROM articles a
        JOIN ticker_mentions tm ON tm.article_id = a.id
        JOIN tickers t ON t.id = tm.ticker_id
        WHERE t.symbol = $1
          AND a.published_at >= NOW() - INTERVAL '30 days'
          AND tm.match_confidence IN ('high', 'medium')
    """, symbol)

    # ── Step 6: Alias detection simulation ───────────────────────────────────
    # Test sample titles that SHOULD match this ticker
    sample_titles = [
        f"Saham {symbol} Naik 10%, Investor Beli",
        f"{symbol} Rencana Rights Issue Senilai Rp500 Miliar",
        f"{row['name']} Cetak Laba Bersih Rp200 Miliar",
        f"Emiten {symbol} Targetkan Pendapatan Naik 20 Persen",
    ]
    detection_hits = 0
    for title in sample_titles:
        matches = detect_tickers(title, alias_entries, shared_aliases)
        if any(tid for tid, _ in matches
               if await _sym_from_tid(conn, tid) == symbol):
            detection_hits += 1

    result["detection_hits_4_samples"] = detection_hits

    # ── Root cause classification ─────────────────────────────────────────────
    recs = result["recommendations"]

    if result["db_articles_7d"] >= 3:
        result["root_cause"] = "OK"
        return result

    if not result["tag_enabled"]:
        result["root_cause"] = "NOT_TAG_ENABLED"
        recs.append(
            f"Run: UPDATE tickers SET ticker_tag_enabled=TRUE WHERE symbol='{symbol}'; "
            f"(or add to seed_tickers.py). "
            f"This enables Google News scraping for {symbol}."
        )
        if gn_arts:
            recs.append(
                f"Google News HAS {len(gn_arts)} results — enabling tag will immediately fix coverage."
            )

    elif result["skip_symbol_tag"] and detection_hits < 2:
        result["root_cause"] = "BAD_ALIASES"
        recs.append(
            f"{symbol} has skip_symbol_tag=true so its 4-letter code is NEVER matched in RSS feeds. "
            f"Current name_slugs: {extra_slugs}. "
            f"Add more recognisable aliases (e.g. short brand name) to ticker_overrides.json name_slugs."
        )
        recs.append(
            f"Also make sure ticker_tag_enabled=TRUE so Google News is queried directly."
        )

    elif result["gn_results"] == 0:
        result["root_cause"] = "NO_GN_RESULTS"
        recs.append(
            f"Google News query '{result['query_name']} saham' returned 0 results. "
            f"Try a shorter or more recognisable query name via ticker_overrides.json name_slugs."
        )

    elif detection_hits < 2:
        result["root_cause"] = "DB_FILTER_OR_ALIAS"
        recs.append(
            f"Google News has results but detection simulation only hits {detection_hits}/4 sample titles. "
            f"Check alias list and name_slugs in ticker_overrides.json."
        )

    else:
        result["root_cause"] = "SCHEDULER_NOT_RUNNING"
        recs.append(
            f"Detection looks correct ({detection_hits}/4 hits) but DB shows only "
            f"{result['db_articles_7d']} articles in 7d. "
            f"Check that ingest scheduler is running `--google-news --gn-tier big` (or all)."
        )

    return result


async def _sym_from_tid(conn, ticker_id: str) -> str | None:
    row = await conn.fetchrow("SELECT symbol FROM tickers WHERE id = $1", ticker_id)
    return row["symbol"] if row else None


async def run(tickers: list[str], days: int, all_gaps: bool, delay: float) -> None:
    conn = await get_conn()
    try:
        alias_entries  = await load_alias_entries(conn)
        shared_aliases = _build_shared_aliases(alias_entries)

        if all_gaps:
            rows = await conn.fetch(f"""
                SELECT t.symbol
                FROM tickers t
                WHERE NOT EXISTS (
                    SELECT 1 FROM ticker_mentions tm
                    JOIN articles a ON a.id = tm.article_id
                    WHERE tm.ticker_id = t.id
                      AND a.published_at >= NOW() - INTERVAL '{days} days'
                      AND tm.match_confidence IN ('high','medium')
                )
                ORDER BY t.market_cap DESC NULLS LAST, t.symbol
                LIMIT 50
            """)
            tickers = [r["symbol"] for r in rows]
            print(f"[diagnose] {len(tickers)} tickers with zero articles in last {days}d")

        if not tickers:
            print("[diagnose] No tickers to check.")
            return

        results = []
        for i, sym in enumerate(tickers):
            print(f"\n[diagnose] ({i+1}/{len(tickers)}) Checking {sym} ...")
            d = await diagnose_ticker(conn, alias_entries, shared_aliases, sym, days, delay)
            results.append(d)

    finally:
        await conn.close()

    # ── Print results ─────────────────────────────────────────────────────────
    print(f"\n{'='*80}")
    print("  COVERAGE DIAGNOSIS REPORT")
    print(f"{'='*80}\n")

    for r in results:
        sym   = r["symbol"]
        cause = r["root_cause"]
        icon  = {"OK": "✓", "NOT_TAG_ENABLED": "✗", "BAD_ALIASES": "!",
                 "NO_GN_RESULTS": "?", "NOT_IN_DB": "✗",
                 "DB_FILTER_OR_ALIAS": "!", "SCHEDULER_NOT_RUNNING": "!",
                 "UNKNOWN": "?"}.get(cause, "?")

        print(f"  {icon} {sym:8s}  [{cause}]")
        if not r.get("in_db"):
            print(f"           ↳ NOT in tickers table")
            continue
        print(f"           name: {r.get('name','?')[:50]}")
        print(f"           tag_enabled={r['tag_enabled']}  "
              f"skip_symbol_tag={r['skip_symbol_tag']}  "
              f"market_cap={r.get('market_cap','?')}")
        print(f"           aliases: {r['aliases'][:4]}")
        print(f"           gn_query: \"{r['query_name']} saham\"  "
              f"→ {r['gn_results']} results")
        if r["gn_latest_title"]:
            print(f"           gn_sample: {r['gn_latest_title'][:70]}")
        print(f"           db_articles: 7d={r['db_articles_7d']}  30d={r['db_articles_30d']}")
        print(f"           alias_detection: {r['detection_hits_4_samples']}/4 sample titles matched")
        for rec in r.get("recommendations", []):
            print(f"           → {rec}")
        print()

    # Summary
    ok_count   = sum(1 for r in results if r["root_cause"] == "OK")
    gap_count  = len(results) - ok_count
    print(f"[diagnose] {ok_count}/{len(results)} tickers OK | {gap_count} gaps found")

    if gap_count:
        print("\n[diagnose] Most common fixes needed:")
        from collections import Counter
        causes = Counter(r["root_cause"] for r in results if r["root_cause"] != "OK")
        for cause, cnt in causes.most_common():
            print(f"  {cause}: {cnt} ticker(s)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Coverage gap root-cause diagnosis")
    parser.add_argument(
        "--tickers", nargs="+", default=DEFAULT_WATCHLIST,
        help="Ticker symbols to check (default: known watchlist)"
    )
    parser.add_argument(
        "--all-gaps", action="store_true",
        help="Check ALL tickers with zero articles in last --days days (up to 50)"
    )
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--delay", type=float, default=2.0,
                        help="Seconds between Google News queries (default: 2)")
    args = parser.parse_args()
    asyncio.run(run(args.tickers, args.days, args.all_gaps, args.delay))


if __name__ == "__main__":
    main()

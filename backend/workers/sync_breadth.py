#!/usr/bin/env python3
"""
sync_breadth.py — Fetch daily close prices for LQ45 stocks.

Uses Yahoo Finance (ticker.JK suffix). Stores in stock_daily table.
Breadth = % of LQ45 stocks trading above their 20-day MA, computed
by compute_index.py from this data.

Usage (from project root):
  python -m backend.workers.sync_breadth          # 3-month history
  python -m backend.workers.sync_breadth --range 6mo
  python -m backend.workers.sync_breadth --range 1y
  python -m backend.workers.sync_breadth --dry-run
"""

import argparse
import asyncio
import sys
sys.stdout.reconfigure(encoding="utf-8")
import time
from datetime import datetime, timezone
from pathlib import Path

import aiohttp

PROJECT_ROOT = Path(__file__).resolve().parents[2]

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env.local", override=True)

from ._db import get_conn


# ---------------------------------------------------------------------------
# LQ45 constituent list (Feb–Jul 2026 period, stable core)
# ---------------------------------------------------------------------------
# Source: BEI LQ45 index — tickers that are consistently in the basket.
# Rebalanced every 6 months; update this list after each rebalancing.

LQ45_TICKERS = [
    "ADRO", "AKRA", "AMRT", "ANTM", "ARTO",
    "ASII", "BBCA", "BBNI", "BBRI", "BBTN",
    "BMRI", "BREN", "BRPT", "CPIN", "EMTK",
    "EXCL", "GOTO", "ICBP", "INCO", "INDF",
    "INKP", "ISAT", "ITMG", "KLBF", "MAPI",
    "MDKA", "MEDC", "PGEO", "PGAS", "PTBA",
    "TLKM", "TOWR", "TPIA", "UNTR", "UNVR",
]

YAHOO_HEADERS = {"User-Agent": "Mozilla/5.0"}
DELAY_BETWEEN = 0.3   # seconds between Yahoo requests (avoid rate-limit)


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

async def fetch_stock(
    session: aiohttp.ClientSession,
    ticker: str,
    range_: str,
) -> list[dict]:
    """
    Fetch daily bars for a single IDX stock from Yahoo Finance.
    Yahoo Finance uses the .JK suffix for Indonesian stocks.
    Returns list of {ticker, date, close} dicts.
    """
    yf_symbol = f"{ticker}.JK"
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{yf_symbol}?range={range_}&interval=1d"
    )
    try:
        async with session.get(
            url, headers=YAHOO_HEADERS, timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            if resp.status == 404:
                return []   # ticker not found on Yahoo
            if resp.status != 200:
                print(f"  [WARN] {ticker}: Yahoo HTTP {resp.status}")
                return []
            data = await resp.json(content_type=None)
    except Exception as exc:
        print(f"  [WARN] {ticker}: fetch failed — {exc}")
        return []

    result = data.get("chart", {}).get("result", [None])[0]
    if not result:
        return []

    timestamps: list[int]  = result.get("timestamp", [])
    closes: list[float]    = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])

    bars = []
    for i, ts in enumerate(timestamps):
        if i >= len(closes) or closes[i] is None or closes[i] != closes[i]:  # NaN check
            continue
        bars.append({
            "ticker": ticker,
            "date":   datetime.utcfromtimestamp(ts).date(),
            "close":  float(closes[i]),
        })
    return bars


# ---------------------------------------------------------------------------
# DB upsert
# ---------------------------------------------------------------------------

async def upsert_bars(conn, bars: list[dict]) -> int:
    count = 0
    for b in bars:
        await conn.execute(
            """
            INSERT INTO stock_daily (ticker, date, close, fetched_at)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (ticker, date) DO UPDATE
              SET close = EXCLUDED.close, fetched_at = NOW()
            """,
            b["ticker"], b["date"], b["close"],
        )
        count += 1
    return count


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

async def run_sync(range_: str = "3mo", dry_run: bool = False) -> None:
    tickers = LQ45_TICKERS
    print(f"[sync-breadth] Fetching {len(tickers)} LQ45 stocks from Yahoo Finance")
    print(f"[sync-breadth] Range: {range_}  dry_run={dry_run}")

    ok = failed = 0
    total_bars = 0

    conn = await get_conn() if not dry_run else None
    try:
        async with aiohttp.ClientSession() as session:
            for ticker in tickers:
                bars = await fetch_stock(session, ticker, range_)
                if bars:
                    ok += 1
                    total_bars += len(bars)
                    if not dry_run:
                        n = await upsert_bars(conn, bars)
                        print(f"  {ticker:6s}: {n} bars ({bars[0]['date']} → {bars[-1]['date']})")
                    else:
                        print(f"  [DRY] {ticker:6s}: {len(bars)} bars")
                else:
                    failed += 1
                    print(f"  {ticker:6s}: no data")
                await asyncio.sleep(DELAY_BETWEEN)

        # Summary
        print(f"\n[sync-breadth] Done: {ok}/{len(tickers)} stocks fetched, {total_bars} bars total")
        if failed:
            print(f"  {failed} tickers returned no data from Yahoo Finance.")
            print("  This may be normal for newly-listed or suspended stocks.")

        if not dry_run:
            n_rows  = await conn.fetchval("SELECT COUNT(*) FROM stock_daily")
            n_tix   = await conn.fetchval("SELECT COUNT(DISTINCT ticker) FROM stock_daily")
            latest  = await conn.fetchval("SELECT MAX(date) FROM stock_daily")
            print(f"  stock_daily: {n_rows} rows, {n_tix} tickers, latest date: {latest}")

    finally:
        if conn:
            await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync LQ45 daily closes for market breadth")
    parser.add_argument("--range", dest="range_", default="3mo",
                        help="Yahoo Finance range: 1mo 3mo 6mo 1y (default: 3mo)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch but don't write to DB")
    args = parser.parse_args()
    asyncio.run(run_sync(args.range_, args.dry_run))


if __name__ == "__main__":
    main()

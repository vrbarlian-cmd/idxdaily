#!/usr/bin/env python3
"""
Fetch and store IHSG + USD/IDR daily history from Yahoo Finance.

Seeds ihsg_daily and usdidr_daily tables with up to 1 year of data.
Safe to re-run (upserts on date).

Usage (from project root):
    python -m backend.workers.sync_market
    python -m backend.workers.sync_market --dry-run

Run after applying schema.sql, then schedule daily (e.g. cron @daily).
"""

import argparse
import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

import aiohttp

PROJECT_ROOT = Path(__file__).resolve().parents[2]

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env.local", override=True)

from ._db import get_conn


YAHOO_HEADERS = {"User-Agent": "Mozilla/5.0"}

SYMBOLS = {
    "ihsg":   "^JKSE",
    "usdidr": "IDR=X",
}


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

async def fetch_yahoo_history(session: aiohttp.ClientSession, ticker: str, range_: str = "1y") -> list[dict]:
    """
    Returns list of {date, close, volume} dicts sorted by date asc.
    Raises ValueError if Yahoo returns no usable data.
    """
    import urllib.parse
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{urllib.parse.quote(ticker)}?range={range_}&interval=1d"
    )
    async with session.get(url, headers=YAHOO_HEADERS, timeout=aiohttp.ClientTimeout(total=20)) as resp:
        if resp.status != 200:
            raise ValueError(f"Yahoo {ticker}: HTTP {resp.status}")
        data = await resp.json(content_type=None)

    result = data.get("chart", {}).get("result", [None])[0]
    if not result:
        raise ValueError(f"Yahoo {ticker}: no chart result in response")

    timestamps: list[int]   = result.get("timestamp", [])
    quotes                  = result.get("indicators", {}).get("quote", [{}])[0]
    closes: list[float]     = quotes.get("close", [])
    volumes: list[float]    = quotes.get("volume", [])

    if not timestamps or not closes:
        raise ValueError(f"Yahoo {ticker}: empty timestamp or close arrays")

    bars = []
    for i, ts in enumerate(timestamps):
        if i >= len(closes) or closes[i] is None:
            continue
        bars.append({
            "date":   datetime.utcfromtimestamp(ts).date(),
            "close":  float(closes[i]),
            "volume": float(volumes[i]) if i < len(volumes) and volumes[i] is not None else None,
        })

    if not bars:
        raise ValueError(f"Yahoo {ticker}: all bars filtered out (all closes null)")

    bars.sort(key=lambda b: b["date"])
    return bars


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------

async def upsert_ihsg(conn, bars: list[dict]) -> int:
    inserted = 0
    for b in bars:
        await conn.execute(
            """
            INSERT INTO ihsg_daily (date, close, volume, fetched_at)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (date) DO UPDATE
              SET close = EXCLUDED.close,
                  volume = EXCLUDED.volume,
                  fetched_at = NOW()
            """,
            b["date"], b["close"], b["volume"],
        )
        inserted += 1
    return inserted


async def upsert_usdidr(conn, bars: list[dict]) -> int:
    inserted = 0
    for b in bars:
        await conn.execute(
            """
            INSERT INTO usdidr_daily (date, close, fetched_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (date) DO UPDATE
              SET close = EXCLUDED.close,
                  fetched_at = NOW()
            """,
            b["date"], b["close"],
        )
        inserted += 1
    return inserted


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run(dry_run: bool = False) -> None:
    conn = await get_conn()
    try:
        async with aiohttp.ClientSession() as session:
            print("Fetching IHSG (^JKSE) 1y …")
            ihsg_bars = await fetch_yahoo_history(session, SYMBOLS["ihsg"], "1y")
            print(f"  Got {len(ihsg_bars)} bars: {ihsg_bars[0]['date']} to {ihsg_bars[-1]['date']}")

            print("Fetching USD/IDR (IDR=X) 1y …")
            usdidr_bars = await fetch_yahoo_history(session, SYMBOLS["usdidr"], "1y")
            print(f"  Got {len(usdidr_bars)} bars: {usdidr_bars[0]['date']} to {usdidr_bars[-1]['date']}")

        if dry_run:
            print("\n[DRY RUN] No data written to database.")
            return

        n_ihsg   = await upsert_ihsg(conn, ihsg_bars)
        n_usdidr = await upsert_usdidr(conn, usdidr_bars)

        print(f"\nUpserted {n_ihsg} IHSG rows, {n_usdidr} USD/IDR rows.")
        print("Done. Run compute_index.py next to update the Fear & Greed score.")

    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync IHSG + USD/IDR history from Yahoo Finance")
    parser.add_argument("--dry-run", action="store_true", help="Fetch but don't write to DB")
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()

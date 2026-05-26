"""
Pull 3 years of IHSG (^JKSE) and USD/IDR (IDR=X) from Yahoo Finance
and upsert into ihsg_daily / usdidr_daily.

ON CONFLICT DO UPDATE so existing rows are refreshed (close prices
are sometimes revised by Yahoo). Safe to re-run.

Run from project root:
    python -m backend.scripts.extend_market_history
"""
import asyncio
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(".env"))
load_dotenv(Path(".env.local"), override=True)

import aiohttp
import asyncpg

YAHOO_HEADERS = {"User-Agent": "Mozilla/5.0"}

async def fetch(session: aiohttp.ClientSession, ticker: str, range_: str = "3y") -> list[dict]:
    import urllib.parse
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{urllib.parse.quote(ticker)}?range={range_}&interval=1d"
    )
    async with session.get(url, headers=YAHOO_HEADERS,
                           timeout=aiohttp.ClientTimeout(total=30)) as resp:
        if resp.status != 200:
            raise ValueError(f"Yahoo {ticker}: HTTP {resp.status}")
        data = await resp.json(content_type=None)

    result = data.get("chart", {}).get("result", [None])[0]
    if not result:
        raise ValueError(f"Yahoo {ticker}: no chart result")

    timestamps = result.get("timestamp", [])
    quotes     = result.get("indicators", {}).get("quote", [{}])[0]
    closes     = quotes.get("close", [])
    volumes    = quotes.get("volume", [])

    bars = []
    for i, ts in enumerate(timestamps):
        if i >= len(closes) or closes[i] is None:
            continue
        bars.append({
            "date":   datetime.utcfromtimestamp(ts).date(),
            "close":  float(closes[i]),
            "volume": float(volumes[i]) if i < len(volumes) and volumes[i] is not None else None,
        })
    bars.sort(key=lambda b: b["date"])
    return bars


async def main():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        async with aiohttp.ClientSession() as session:
            print("Fetching ^JKSE 3y …")
            ihsg = await fetch(session, "^JKSE", "3y")
            print(f"  Got {len(ihsg)} bars: {ihsg[0]['date']} to {ihsg[-1]['date']}")

            print("Fetching IDR=X 3y ...")
            usdidr = await fetch(session, "IDR=X", "3y")
            print(f"  Got {len(usdidr)} bars: {usdidr[0]['date']} to {usdidr[-1]['date']}")

        # Upsert IHSG
        n_ihsg = 0
        for b in ihsg:
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
            n_ihsg += 1

        # Upsert USD/IDR
        n_usdidr = 0
        for b in usdidr:
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
            n_usdidr += 1

        # Report new coverage
        ihsg_min   = await conn.fetchval("SELECT MIN(date) FROM ihsg_daily")
        ihsg_max   = await conn.fetchval("SELECT MAX(date) FROM ihsg_daily")
        ihsg_count = await conn.fetchval("SELECT COUNT(*) FROM ihsg_daily")
        usd_min    = await conn.fetchval("SELECT MIN(date) FROM usdidr_daily")
        usd_max    = await conn.fetchval("SELECT MAX(date) FROM usdidr_daily")
        usd_count  = await conn.fetchval("SELECT COUNT(*) FROM usdidr_daily")

        print(f"\nUpserted: {n_ihsg} IHSG rows, {n_usdidr} USD/IDR rows")
        print(f"IHSG coverage  : {ihsg_count} rows  {ihsg_min} to {ihsg_max}")
        print(f"USDIDR coverage: {usd_count} rows  {usd_min} to {usd_max}")
        print("\nNext: python -m backend.scripts.backtest_aug_jan")
    finally:
        await conn.close()


asyncio.run(main())

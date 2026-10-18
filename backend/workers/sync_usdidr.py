"""
Daily USD/IDR sync (USD/IDR only).

Unlike sync_market.py this never touches ihsg_daily, so it cannot overwrite the
manually entered IHSG closes. Fetches the last month from Yahoo (IDR=X) and
upserts into usdidr_daily; re-running is safe (upsert by date).

Usage (from project root):
    python -m backend.workers.sync_usdidr
"""

import asyncio
from datetime import date

import aiohttp

from ._db import get_conn
from .sync_market import SYMBOLS, fetch_yahoo_history, upsert_usdidr


async def run() -> None:
    async with aiohttp.ClientSession() as session:
        bars = await fetch_yahoo_history(session, SYMBOLS["usdidr"], "1mo")
    bars = [b for b in bars if b["date"] < date.today()]
    conn = await get_conn()
    try:
        n = await upsert_usdidr(conn, bars)
    finally:
        await conn.close()
    print(f"usdidr_daily: upserted {n} rows, latest {bars[-1]['date']} close {bars[-1]['close']}")


if __name__ == "__main__":
    asyncio.run(run())

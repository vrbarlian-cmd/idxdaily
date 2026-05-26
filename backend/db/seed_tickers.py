#!/usr/bin/env python3
"""
Seed the tickers table from backend/db/tickers.json.

Deletes any tickers (and their cascaded articles/mentions) NOT in the JSON,
then upserts the listed tickers.

Usage (from project root):
  python -m backend.db.seed_tickers
"""
import asyncio
import json
import os
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env.local", override=True)

import asyncpg

TICKERS_FILE = Path(__file__).parent / "tickers.json"


async def main() -> None:
    url = os.environ.get("DATABASE_URL", "")
    if not url or url.startswith("file:"):
        raise RuntimeError("DATABASE_URL is not set or still points to SQLite.")

    tickers = json.loads(TICKERS_FILE.read_text(encoding="utf-8"))
    target_symbols = [t["symbol"] for t in tickers]

    conn = await asyncpg.connect(url)
    try:
        # Remove tickers not in the target list (cascades to articles + mentions)
        removed = await conn.fetch(
            "SELECT symbol FROM tickers WHERE symbol != ALL($1::text[])",
            target_symbols,
        )
        if removed:
            syms = [r["symbol"] for r in removed]
            await conn.execute(
                "DELETE FROM tickers WHERE symbol != ALL($1::text[])",
                target_symbols,
            )
            print(f"[seed] Removed {len(syms)} old tickers (cascade): {', '.join(syms)}")

        # Upsert the 10 target tickers
        inserted = updated = 0
        for t in tickers:
            existing = await conn.fetchrow(
                "SELECT id FROM tickers WHERE symbol = $1", t["symbol"]
            )
            if existing:
                await conn.execute(
                    """
                    UPDATE tickers SET name=$2, sector=$3, subsector=$4, updated_at=now()
                    WHERE symbol=$1
                    """,
                    t["symbol"], t["name"], t.get("sector"), t.get("subsector"),
                )
                updated += 1
                print(f"  [~] {t['symbol']} — updated")
            else:
                await conn.execute(
                    """
                    INSERT INTO tickers (id, symbol, name, sector, subsector)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    str(uuid.uuid4()), t["symbol"], t["name"],
                    t.get("sector"), t.get("subsector"),
                )
                inserted += 1
                print(f"  [+] {t['symbol']} — {t['name']}")

        count = await conn.fetchval("SELECT count(*) FROM tickers")
        art_count = await conn.fetchval("SELECT count(*) FROM articles")
        print(f"\n[seed] inserted={inserted} updated={updated} | tickers={count} articles_remaining={art_count}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())

"""Create domestic_flow_daily table (idempotent — safe to re-run)."""
import asyncio, asyncpg, os, sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(".env"))
load_dotenv(Path(".env.local"), override=True)


async def main():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS domestic_flow_daily (
              date          DATE PRIMARY KEY,
              buy_value_bn  REAL NOT NULL,
              sell_value_bn REAL NOT NULL,
              source        TEXT NOT NULL DEFAULT 'manual',
              created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        print("domestic_flow_daily: created (or already existed).")

        # Verify structure
        cols = await conn.fetch("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'domestic_flow_daily'
            ORDER BY ordinal_position
        """)
        print("Columns:")
        for c in cols:
            print(f"  {c['column_name']:20s} {c['data_type']}")

        n = await conn.fetchval("SELECT COUNT(*) FROM domestic_flow_daily")
        print(f"Current rows: {n}")
    finally:
        await conn.close()


asyncio.run(main())

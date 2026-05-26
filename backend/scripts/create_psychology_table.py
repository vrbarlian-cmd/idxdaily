"""
Create fear_greed_psychology table for Index B (Market Psychology / Retail).
Idempotent — safe to re-run.

Run from project root:
    python -m backend.scripts.create_psychology_table
"""
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
            CREATE TABLE IF NOT EXISTS fear_greed_psychology (
              date                      DATE PRIMARY KEY,
              score                     REAL,
              raw_score                 REAL,
              smoothed_score            REAL,
              label                     TEXT,
              active_components         INTEGER,
              components_json           JSONB,
              -- Retail participation detail
              retail_participation_score  REAL,
              retail_participation_ratio  REAL,
              retail_direction            REAL,   -- sign(domestic_net): +1 / -1 / 0
              domestic_net_bn             REAL,
              domestic_total_bn           REAL,
              domestic_ma20_bn            REAL,   -- MA of total_bn used for ratio
              -- Metadata
              has_retail_data           BOOLEAN NOT NULL DEFAULT FALSE,
              days_of_retail_data       INTEGER,
              updated_at                TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        print("fear_greed_psychology: created (or already existed).")

        cols = await conn.fetch("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'fear_greed_psychology'
            ORDER BY ordinal_position
        """)
        print("Columns:")
        for c in cols:
            print(f"  {c['column_name']:35s} {c['data_type']}")

        n = await conn.fetchval("SELECT COUNT(*) FROM fear_greed_psychology")
        print(f"\nCurrent rows: {n}")
    finally:
        await conn.close()


asyncio.run(main())

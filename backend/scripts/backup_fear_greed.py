"""
Backup fear_greed_index to fear_greed_index_bak_<YYYYMMDD_HHMMSS>.
Idempotent: safe to run multiple times (each run creates a new timestamped backup).

Run from project root:
    python -m backend.scripts.backup_fear_greed
"""
import asyncio, asyncpg, os, sys
sys.stdout.reconfigure(encoding="utf-8")
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(".env"))
load_dotenv(Path(".env.local"), override=True)


async def main():
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    bak = f"fear_greed_index_bak_{ts}"

    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        n_src = await conn.fetchval("SELECT COUNT(*) FROM fear_greed_index")
        print(f"Source rows: {n_src}")

        await conn.execute(f"CREATE TABLE {bak} AS SELECT * FROM fear_greed_index")

        n_bak = await conn.fetchval(f"SELECT COUNT(*) FROM {bak}")
        print(f"Backup table: {bak}  rows={n_bak}")

        first = await conn.fetchval(f"SELECT MIN(date) FROM {bak}")
        last  = await conn.fetchval(f"SELECT MAX(date) FROM {bak}")
        live  = await conn.fetchval(f"SELECT COUNT(*) FROM {bak} WHERE NOT is_backfilled")
        bf    = await conn.fetchval(f"SELECT COUNT(*) FROM {bak} WHERE is_backfilled")
        print(f"  Date range : {first} -> {last}")
        print(f"  Live rows  : {live}")
        print(f"  Backfilled : {bf}")
        print(f"\nRestore command if needed:")
        print(f"  TRUNCATE fear_greed_index;")
        print(f"  INSERT INTO fear_greed_index SELECT * FROM {bak};")
        print(f"\nBACKUP COMPLETE.")
    finally:
        await conn.close()


asyncio.run(main())

"""Exit 0 if >= 10 articles exist today (WIB date). Exit 1 if fewer — triggers last-resort ingest."""
import asyncio, datetime as dt, os, sys
from dotenv import load_dotenv

load_dotenv(".env")
load_dotenv(".env.local", override=True)
import asyncpg


async def main():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    count = await conn.fetchval(
        "SELECT COUNT(*) FROM articles WHERE created_at AT TIME ZONE 'Asia/Jakarta' >= CURRENT_DATE"
    )
    await conn.close()
    print(f"[last-resort] Articles today (WIB): {count}")
    sys.exit(0 if count >= 10 else 1)


asyncio.run(main())

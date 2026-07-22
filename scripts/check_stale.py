"""Exit 0 if most recent article is within 6 hours (data is fresh). Exit 1 if stale."""
import asyncio, datetime as dt, os, sys
from dotenv import load_dotenv

load_dotenv(".env")
load_dotenv(".env.local", override=True)
import asyncpg


async def main():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    v = await conn.fetchval("SELECT MAX(created_at) FROM articles")
    await conn.close()
    if v is None:
        sys.exit(1)
    age = (dt.datetime.now(dt.timezone.utc) - v.replace(tzinfo=dt.timezone.utc)).total_seconds()
    sys.exit(0 if age < 21600 else 1)


asyncio.run(main())

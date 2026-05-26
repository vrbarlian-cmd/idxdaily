#!/usr/bin/env python3
"""
Apply backend/db/schema.sql to the Neon Postgres database.

Usage (from project root):
  python -m backend.db.apply_schema

Or (from backend/):
  python -m db.apply_schema
"""
import asyncio
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env.local", override=True)

import asyncpg

SCHEMA_FILE = Path(__file__).parent / "schema.sql"


async def main() -> None:
    url = os.environ.get("DATABASE_URL", "")
    if not url or url.startswith("file:"):
        raise RuntimeError("DATABASE_URL is not set or still points to SQLite.")

    sql = SCHEMA_FILE.read_text(encoding="utf-8")
    conn = await asyncpg.connect(url)
    try:
        await conn.execute(sql)
        print("[apply_schema] Schema applied successfully.")

        tables = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
        )
        print(f"[apply_schema] Tables in public schema:")
        for row in tables:
            print(f"  {row['tablename']}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())

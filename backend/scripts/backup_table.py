"""
Back up a database table to a JSON file in logs/ before risky changes
(e.g. before a Fear & Greed backfill).

Usage (from project root):
    python -m backend.scripts.backup_table fear_greed_index
    python -m backend.scripts.backup_table usdidr_daily --tag pre_fix
"""

import argparse
import asyncio
import json
import re
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env.local")

from backend.workers._db import get_conn  # noqa: E402


async def main(table: str, tag: str) -> None:
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", table):
        raise SystemExit(f"Bad table name: {table}")
    conn = await get_conn()
    try:
        rows = await conn.fetch(f"SELECT * FROM {table} ORDER BY 1")
    finally:
        await conn.close()
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    out = ROOT / "logs" / f"{table}_backup_{stamp}{'_' + tag if tag else ''}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps([dict(r) for r in rows], default=str, indent=1), encoding="utf-8")
    print(f"Backed up {len(rows)} rows of {table} -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Back up a DB table to logs/*.json")
    ap.add_argument("table")
    ap.add_argument("--tag", default="", help="Optional label added to the file name")
    a = ap.parse_args()
    asyncio.run(main(a.table, a.tag))

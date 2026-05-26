"""Remove test data inserted during dual-flow build verification."""
import asyncio, asyncpg, os, sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(".env"))
load_dotenv(Path(".env.local"), override=True)

async def main():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])

    # Check what's there first
    ff = await conn.fetchrow(
        "SELECT date, net_idr_billions, source FROM foreign_flow_daily WHERE date='2026-05-25'"
    )
    df = await conn.fetchrow(
        "SELECT date, buy_value_bn, sell_value_bn, source FROM domestic_flow_daily WHERE date='2026-05-25'"
    )
    print(f"Foreign 2026-05-25: {ff}")
    print(f"Domestic 2026-05-25: {df}")

    # Delete by date only (test data — today had no real foreign flow entry before we started)
    d1 = await conn.execute("DELETE FROM foreign_flow_daily WHERE date='2026-05-25'")
    d2 = await conn.execute("DELETE FROM domestic_flow_daily WHERE date='2026-05-25'")
    print(f"\nDeleted: foreign_flow={d1}, domestic_flow={d2}")

    r = await conn.fetchrow(
        "SELECT date, net_idr_billions FROM foreign_flow_daily ORDER BY date DESC LIMIT 1"
    )
    print(f"Latest foreign flow now: {r['date']}  net={float(r['net_idr_billions']):+.2f}")
    await conn.close()

asyncio.run(main())

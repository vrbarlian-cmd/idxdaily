"""Quick check: is foreign_flow_daily in FOREIGN or INVERTED-DOMESTIC state?"""
import asyncio, asyncpg, os, sys
sys.stdout.reconfigure(encoding="utf-8")
from datetime import date
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(".env"))
load_dotenv(Path(".env.local"), override=True)

async def main():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])

    # ── Jan 28 ground-truth check ─────────────────────────────────────────
    jan28 = await conn.fetchrow(
        "SELECT date, net_idr_billions, source FROM foreign_flow_daily WHERE date = '2026-01-28'"
    )
    val = float(jan28["net_idr_billions"])
    state = "FOREIGN (correct — foreigners sold)" if val < 0 else "INVERTED/DOMESTIC (experiment still live!)"
    print(f"Jan 28 value : {val:+,.2f} Rp bn  [source={jan28['source']}]")
    print(f"Table state  : {state}")
    print()

    # ── Backup tables ─────────────────────────────────────────────────────
    for tbl in ("fear_greed_index_foreign_v", "foreign_flow_daily_foreign_v"):
        exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name=$1)", tbl
        )
        n = await conn.fetchval(f"SELECT COUNT(*) FROM {tbl}") if exists else "n/a"
        print(f"Backup {tbl}: exists={exists}  rows={n}")
    print()

    # ── Last 10 rows of foreign_flow_daily ───────────────────────────────
    rows = await conn.fetch(
        "SELECT date, net_idr_billions, source FROM foreign_flow_daily ORDER BY date DESC LIMIT 10"
    )
    print("Last 10 rows of foreign_flow_daily (newest first):")
    for r in rows:
        print(f"  {r['date']}  {float(r['net_idr_billions']):+10.2f}  [{r['source']}]")

    # ── Current index reading ─────────────────────────────────────────────
    print()
    latest_fg = await conn.fetchrow(
        "SELECT date, smoothed_score, label FROM fear_greed_index "
        "WHERE smoothed_score IS NOT NULL ORDER BY date DESC LIMIT 1"
    )
    if latest_fg:
        print(f"Latest F&G   : {latest_fg['date']}  score={float(latest_fg['smoothed_score']):.1f}  label={latest_fg['label']}")

    # Also spot-check a few key months in the index for Greed vs Fear
    spot = await conn.fetch("""
        SELECT date, smoothed_score, label FROM fear_greed_index
        WHERE date IN ('2025-08-01','2025-12-24','2026-01-28','2026-03-09')
        ORDER BY date
    """)
    print()
    print("Spot-check key dates in fear_greed_index:")
    for r in spot:
        print(f"  {r['date']}  score={float(r['smoothed_score']):.1f}  label={r['label']}")

    await conn.close()

asyncio.run(main())

"""Diagnose IHSG and USDIDR price data integrity."""
import asyncio, asyncpg, os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(".env"))
load_dotenv(Path(".env.local"), override=True)

async def main():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        # ── IHSG overview ────────────────────────────────────────────────────
        stats = await conn.fetchrow("""
            SELECT COUNT(*) AS n,
                   MIN(close) AS min_close, MAX(close) AS max_close,
                   AVG(close) AS avg_close,
                   MIN(date) AS min_date, MAX(date) AS max_date
            FROM ihsg_daily
        """)
        print(f"IHSG rows: {stats['n']}  dates: {stats['min_date']} to {stats['max_date']}")
        print(f"  close: min={stats['min_close']:,.0f}  max={stats['max_close']:,.0f}  avg={stats['avg_close']:,.0f}")

        # Corrupted rows (outside plausible IHSG range 3000-10000)
        bad = await conn.fetch("""
            SELECT date, close FROM ihsg_daily
            WHERE close < 3000 OR close > 10000
            ORDER BY date
        """)
        print(f"\nIHSG rows with close outside 3,000-10,000: {len(bad)}")
        for r in bad:
            print(f"  {r['date']}  close={r['close']:,.0f}")

        # Sample every ~60 rows across the full range
        sample = await conn.fetch("""
            SELECT date, close FROM ihsg_daily
            ORDER BY date
        """)
        print(f"\nIHSG sample (every 60th row + first/last 5):")
        all_rows = list(sample)
        indices = list(range(0, len(all_rows), 60)) + list(range(max(0,len(all_rows)-5), len(all_rows)))
        seen = set()
        for i in sorted(set(indices)):
            if i in seen or i >= len(all_rows): continue
            seen.add(i)
            r = all_rows[i]
            flag = " <<< CORRUPT" if r['close'] < 3000 or r['close'] > 10000 else ""
            print(f"  [{i:4d}] {r['date']}  {r['close']:>12,.0f}{flag}")

        # ── USDIDR overview ──────────────────────────────────────────────────
        print()
        usd_stats = await conn.fetchrow("""
            SELECT COUNT(*) AS n,
                   MIN(close) AS min_close, MAX(close) AS max_close,
                   AVG(close) AS avg_close,
                   MIN(date) AS min_date, MAX(date) AS max_date
            FROM usdidr_daily
        """)
        print(f"USDIDR rows: {usd_stats['n']}  dates: {usd_stats['min_date']} to {usd_stats['max_date']}")
        print(f"  close: min={usd_stats['min_close']:,.0f}  max={usd_stats['max_close']:,.0f}  avg={usd_stats['avg_close']:,.0f}")

        usd_bad = await conn.fetch("""
            SELECT date, close FROM usdidr_daily
            WHERE close < 10000 OR close > 20000
            ORDER BY date
        """)
        print(f"USDIDR rows with close outside 10,000-20,000: {len(usd_bad)}")
        for r in usd_bad[:20]:
            print(f"  {r['date']}  close={r['close']:,.4f}")

        # Check the specific dates mentioned (Feb-Mar 2026)
        print("\nSpot-check Feb-Mar 2026:")
        spot = await conn.fetch("""
            SELECT date, close, volume FROM ihsg_daily
            WHERE date >= '2026-02-01' AND date <= '2026-03-15'
            ORDER BY date
        """)
        for r in spot:
            flag = " <<< CORRUPT" if r['close'] < 3000 or r['close'] > 10000 else ""
            print(f"  {r['date']}  close={r['close']:>14,.2f}  vol={r['volume']}{flag}")

    finally:
        await conn.close()

asyncio.run(main())

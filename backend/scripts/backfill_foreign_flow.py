#!/usr/bin/env python3
"""
One-off script: backfill real historical foreign flow data into foreign_flow_daily.
Run once from project root:
    python -m backend.scripts.backfill_foreign_flow
"""
import asyncio
import statistics
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env.local", override=True)

from backend.workers._db import get_conn

# Real historical data — net foreign flow in IDR billions
# Negative = outflow (foreigners selling), Positive = inflow (foreigners buying)
HISTORICAL_DATA: list[tuple[str, float]] = [
    # March 2026
    ("2026-03-02", -631.18),
    ("2026-03-03",  3448.50),
    ("2026-03-04",  -118.08),
    ("2026-03-05",  -210.01),
    ("2026-03-06",  -263.00),
    ("2026-03-09",  1109.92),
    ("2026-03-10", -2626.39),
    ("2026-03-11",  -937.00),
    ("2026-03-12",  1001.19),
    ("2026-03-13",  -117.17),
    ("2026-03-16",  1022.82),
    ("2026-03-17",  -679.22),
    ("2026-03-25",   102.80),
    ("2026-03-26", -20711.63),   # *** OUTLIER — likely index rebalancing ***
    ("2026-03-27", -1764.30),
    ("2026-03-30",  -686.25),
    ("2026-03-31", -1280.96),
    # April 2026
    ("2026-04-01",  -165.48),
    ("2026-04-02",  -813.51),
    ("2026-04-06",  -623.02),
    ("2026-04-07", -1777.27),
    ("2026-04-08",   632.91),
    ("2026-04-09", -1739.39),
    ("2026-04-10",   193.87),
    ("2026-04-13",   396.77),
    ("2026-04-14",   -30.76),
    ("2026-04-15", -1163.98),
    ("2026-04-16",  -982.01),
    ("2026-04-17",  -931.61),
    ("2026-04-20",   380.74),
    ("2026-04-21",   473.88),
    ("2026-04-22",  -827.44),
    ("2026-04-23",  -978.73),
    ("2026-04-24", -2002.23),
    ("2026-04-27", -2039.61),
    ("2026-04-28", -2347.72),
    ("2026-04-29", -1191.80),
    ("2026-04-30", -1486.31),
    # May 2026
    ("2026-05-22",  8550.00),    # today — large inflow
]


async def run() -> None:
    conn = await get_conn()
    try:
        # Remove placeholder test data for May 21 (inserted during testing)
        await conn.execute(
            "DELETE FROM foreign_flow_daily WHERE date = '2026-05-21'"
        )
        print("[INFO] Removed test placeholder for 2026-05-21")

        # Upsert all real data
        inserted = updated = 0
        for date_str, value in HISTORICAL_DATA:
            existing = await conn.fetchrow(
                "SELECT net_idr_billions FROM foreign_flow_daily WHERE date = $1",
                date.fromisoformat(date_str)
            )
            await conn.execute(
                """
                INSERT INTO foreign_flow_daily (date, net_idr_billions, source, fetched_at)
                VALUES ($1, $2, 'manual', NOW())
                ON CONFLICT (date) DO UPDATE
                  SET net_idr_billions = EXCLUDED.net_idr_billions,
                      source           = 'manual',
                      fetched_at       = NOW()
                """,
                date.fromisoformat(date_str),
                value,
            )
            if existing:
                updated += 1
            else:
                inserted += 1

        print(f"\n[OK] {inserted} new rows inserted, {updated} rows updated")

        # Summary stats
        rows = await conn.fetch(
            "SELECT date, net_idr_billions FROM foreign_flow_daily ORDER BY date ASC"
        )
        nets = [float(r["net_idr_billions"]) for r in rows]

        print(f"\n{'='*60}")
        print(f"  FOREIGN FLOW SUMMARY")
        print(f"{'='*60}")
        print(f"  Total rows   : {len(rows)}")
        print(f"  Date range   : {rows[0]['date']} -> {rows[-1]['date']}")
        print(f"  Mean         : {statistics.mean(nets):.1f} Rp bn/day")
        print(f"  Median       : {statistics.median(nets):.1f} Rp bn/day")
        print(f"  Std dev      : {statistics.stdev(nets):.1f}")
        print(f"  Min          : {min(nets):.1f} (worst outflow)")
        print(f"  Max          : {max(nets):.1f} (best inflow)")
        print()

        # Outlier analysis
        sorted_nets = sorted(nets)
        n = len(sorted_nets)
        p5_idx  = max(0, int(n * 0.05))
        p95_idx = min(n - 1, int(n * 0.95))
        p5  = sorted_nets[p5_idx]
        p95 = sorted_nets[p95_idx]

        print(f"  OUTLIER ANALYSIS:")
        print(f"  5th  percentile: {p5:.1f} Rp bn")
        print(f"  95th percentile: {p95:.1f} Rp bn")
        print()

        outliers = [(date_str, v) for date_str, v in HISTORICAL_DATA
                    if v < p5 or v > p95]
        print(f"  Values outside 5th-95th band ({len(outliers)} rows):")
        for ds, v in outliers:
            pct_beyond = ((abs(v) - max(abs(p5), abs(p95))) / max(abs(p5), abs(p95))) * 100
            print(f"    {ds}  {v:>12.1f} Rp bn  ({pct_beyond:+.0f}% beyond band)")

        print()
        print(f"{'='*60}")
        print(f"  NOTE: 2026-03-26 (-20,711 Rp bn) is {abs(min(nets)/sorted(nets, key=abs)[-2]):.1f}x")
        print(f"  the next-largest absolute value. See outlier recommendation below.")
        print(f"{'='*60}\n")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run())

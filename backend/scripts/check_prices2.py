"""Check raw IHSG values and what JavaScript would see."""
import asyncio, asyncpg, os, struct
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(".env"))
load_dotenv(Path(".env.local"), override=True)

async def main():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        # Check the exact column type OID and raw float value
        rows = await conn.fetch("""
            SELECT date,
                   close,
                   close::double precision AS close_double,
                   close::text AS close_text,
                   volume,
                   volume::text AS volume_text
            FROM ihsg_daily
            WHERE date IN ('2026-02-25', '2026-03-03', '2026-02-27',
                           '2025-08-01', '2025-12-11', '2026-01-28')
            ORDER BY date
        """)
        print("Exact values for spot-check dates:")
        print(f"{'Date':<12} {'close (real)':>14} {'close (dbl)':>14} {'close (text)':>15} {'volume':>14}")
        for r in rows:
            print(f"{str(r['date']):<12} "
                  f"{float(r['close']):>14.4f} "
                  f"{float(r['close_double']):>14.4f} "
                  f"{str(r['close_text']):>15} "
                  f"{float(r['volume']):>14.0f}")

        # Check ALL rows in Feb-Mar 2026 with CAST to different types
        print("\nFull Feb-Mar 2026 close values (raw, double, text):")
        rows2 = await conn.fetch("""
            SELECT date, close,
                   close::double precision AS close_d,
                   close::numeric AS close_n
            FROM ihsg_daily
            WHERE date BETWEEN '2026-02-01' AND '2026-03-31'
            ORDER BY date
        """)
        for r in rows2:
            raw   = float(r['close'])
            dbl   = float(r['close_d'])
            num   = float(r['close_n'])
            flag  = " <<< MISMATCH" if abs(raw - dbl) > 1.0 else ""
            print(f"  {r['date']}  real={raw:>10.3f}  double={dbl:>10.3f}  numeric={num:>10.3f}{flag}")

        # Now check if there's anything weird in the fear_greed_index table
        # that might carry IHSG close in components_json
        print("\nF&G components_json for Feb 25 and Mar 3:")
        fg = await conn.fetch("""
            SELECT date, raw_score, smoothed_score, components_json
            FROM fear_greed_index
            WHERE date IN ('2026-02-25', '2026-03-03')
            ORDER BY date
        """)
        for r in fg:
            print(f"  {r['date']}  raw={r['raw_score']}  smooth={r['smoothed_score']}")
            print(f"    components: {r['components_json']}")

    finally:
        await conn.close()

asyncio.run(main())

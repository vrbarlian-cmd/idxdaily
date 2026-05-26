"""Check prerequisites before building domestic flow feature."""
import asyncio, asyncpg, os, sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(".env"))
load_dotenv(Path(".env.local"), override=True)

async def main():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])

    # Does domestic_flow_daily exist?
    exists = await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='domestic_flow_daily')"
    )
    print(f"domestic_flow_daily exists: {exists}")

    # Foreign flow absolute value percentiles (calibrate divergence threshold)
    r = await conn.fetchrow("""
        SELECT percentile_cont(0.60) WITHIN GROUP (ORDER BY ABS(net_idr_billions)) AS p60,
               percentile_cont(0.75) WITHIN GROUP (ORDER BY ABS(net_idr_billions)) AS p75,
               percentile_cont(0.50) WITHIN GROUP (ORDER BY ABS(net_idr_billions)) AS p50,
               COUNT(*) AS n,
               AVG(ABS(net_idr_billions)) AS avg_abs,
               MIN(net_idr_billions) AS min_v,
               MAX(net_idr_billions) AS max_v
        FROM foreign_flow_daily WHERE net_idr_billions IS NOT NULL
    """)
    print(f"Foreign |net| percentiles over {r['n']} days:")
    print(f"  p50={float(r['p50']):>8,.1f}  p60={float(r['p60']):>8,.1f}  p75={float(r['p75']):>8,.1f}")
    print(f"  avg={float(r['avg_abs']):>8,.1f}  min={float(r['min_v']):>8,.1f}  max={float(r['max_v']):>8,.1f}")

    # Env var check for admin secret
    import os as _os
    key = _os.environ.get("ADMIN_SECRET_KEY") or _os.environ.get("ADMIN_KEY")
    print(f"\nADMIN_SECRET_KEY/ADMIN_KEY in env: {'set (' + key[:4] + '...)' if key else 'NOT SET'}")

    await conn.close()

asyncio.run(main())

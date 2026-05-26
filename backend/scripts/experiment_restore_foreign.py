"""
RESTORE: Put the validated foreign-flow version back.

Copies fear_greed_index_foreign_v -> fear_greed_index  (backfilled rows only)
Copies foreign_flow_daily_foreign_v -> foreign_flow_daily

Run from project root:
    python -m backend.scripts.experiment_restore_foreign
"""
import asyncio, os, sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(".env"))
load_dotenv(Path(".env.local"), override=True)
import asyncpg


async def main():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        # ── Verify backup tables exist ────────────────────────────────────
        for tbl in ("fear_greed_index_foreign_v", "foreign_flow_daily_foreign_v"):
            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name=$1)", tbl
            )
            if not exists:
                print(f"ERROR: backup table {tbl} not found — cannot restore")
                return
            n = await conn.fetchval(f"SELECT COUNT(*) FROM {tbl}")
            print(f"{tbl}: {n} rows")

        # ── Restore foreign_flow_daily (backfilled rows only) ─────────────
        # Delete rows that were part of the experiment (source='domestic_experiment')
        deleted_ff = await conn.execute(
            "DELETE FROM foreign_flow_daily WHERE source = 'domestic_experiment'"
        )
        print(f"\nDeleted experimental flow rows: {deleted_ff}")

        # Restore from backup (upsert — restores original values for changed dates)
        restored_ff = await conn.execute("""
            INSERT INTO foreign_flow_daily
                (date, net_idr_billions, source, fetched_at)
            SELECT date, net_idr_billions, source, fetched_at
            FROM foreign_flow_daily_foreign_v
            ON CONFLICT (date) DO UPDATE
              SET net_idr_billions = EXCLUDED.net_idr_billions,
                  source           = EXCLUDED.source,
                  fetched_at       = EXCLUDED.fetched_at
        """)
        print(f"Restored flow rows: {restored_ff}")

        # Spot-check Jan 28
        jan28 = await conn.fetchrow(
            "SELECT net_idr_billions, source FROM foreign_flow_daily WHERE date='2026-01-28'"
        )
        print(f"Jan 28 flow after restore: {float(jan28['net_idr_billions']):+.2f}  "
              f"[source={jan28['source']}]  (expected ~-6173.42)")

        # ── Restore fear_greed_index (backfilled rows only) ───────────────
        # Delete current backfilled rows (live rows untouched)
        del_fg = await conn.execute(
            "DELETE FROM fear_greed_index WHERE is_backfilled = TRUE"
        )
        print(f"\nDeleted current backfilled F&G rows: {del_fg}")

        restored_fg = await conn.execute("""
            INSERT INTO fear_greed_index
            SELECT * FROM fear_greed_index_foreign_v
            WHERE is_backfilled = TRUE
            ON CONFLICT (date) DO UPDATE
              SET score             = EXCLUDED.score,
                  raw_score         = EXCLUDED.raw_score,
                  smoothed_score    = EXCLUDED.smoothed_score,
                  label             = EXCLUDED.label,
                  active_components = EXCLUDED.active_components,
                  components_json   = EXCLUDED.components_json,
                  is_backfilled     = TRUE,
                  updated_at        = NOW()
        """)
        print(f"Restored backfilled F&G rows: {restored_fg}")

        # Verify
        fg_now    = await conn.fetchval("SELECT COUNT(*) FROM fear_greed_index")
        fg_backup = await conn.fetchval(
            "SELECT COUNT(*) FROM fear_greed_index_foreign_v"
        )
        print(f"\nfear_greed_index now: {fg_now} rows  backup has: {fg_backup} rows")

        # Spot-check Jan 28 F&G
        jan28_fg = await conn.fetchrow(
            "SELECT smoothed_score, label FROM fear_greed_index WHERE date='2026-01-28'"
        )
        if jan28_fg:
            print(f"Jan 28 F&G: smooth={float(jan28_fg['smoothed_score']):.1f}  label={jan28_fg['label']}")

        print("\nRESTORE COMPLETE — validated foreign-flow version is active.")

    finally:
        await conn.close()


asyncio.run(main())

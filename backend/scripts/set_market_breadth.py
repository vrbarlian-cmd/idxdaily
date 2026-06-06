"""
Set a trading day's market breadth (advancing / declining stock counts).

Usage (run from project root):
    python -m backend.scripts.set_market_breadth --advance 651 --decline 116 --total 959
    python -m backend.scripts.set_market_breadth --advance 651 --decline 116 --total 959 --date 2026-06-05

  --advance  Number of stocks that closed UP (int, from IDX/Stockbit summary).
  --decline  Number of stocks that closed DOWN (int).
  --total    Total stocks traded (int). breadth_pct = advance / total * 100.
  --date     YYYY-MM-DD. Defaults to today (WIB, UTC+7).

Breadth feeds the Market Breadth component (10%) of the Fear & Greed index.
High breadth (many stocks advancing) = Greed; low breadth = Fear.
Run compute_index afterwards (or rely on set_foreign_flow's auto-run).
"""
import argparse, asyncio, asyncpg, os, re, sys
sys.stdout.reconfigure(encoding="utf-8")
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(".env"))
load_dotenv(Path(".env.local"), override=True)

WIB = timezone(timedelta(hours=7))


def today_wib() -> str:
    return datetime.now(WIB).strftime("%Y-%m-%d")


def parse_args():
    p = argparse.ArgumentParser(description="Set market breadth for a trading day.")
    p.add_argument("--advance", type=int, required=True,
                   help="Number of advancing stocks (closed up).")
    p.add_argument("--decline", type=int, required=True,
                   help="Number of declining stocks (closed down).")
    p.add_argument("--total", type=int, required=True,
                   help="Total stocks traded. breadth_pct = advance / total * 100.")
    p.add_argument("--date", default=today_wib(),
                   help="YYYY-MM-DD (default: today WIB)")
    return p.parse_args()


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS market_breadth_daily (
    date           DATE PRIMARY KEY,
    advance_count  INTEGER NOT NULL,
    decline_count  INTEGER NOT NULL,
    total_count    INTEGER NOT NULL,
    breadth_pct    REAL    NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""


async def main():
    args = parse_args()

    if not re.match(r"^\d{4}-\d{2}-\d{2}$", args.date):
        print(f"ERROR: date must be YYYY-MM-DD, got: {args.date}")
        sys.exit(1)
    if args.advance < 0 or args.decline < 0 or args.total <= 0:
        print("ERROR: --advance/--decline must be >= 0 and --total must be > 0.")
        sys.exit(1)

    breadth_pct = args.advance / args.total * 100.0

    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    entry_date = date.fromisoformat(args.date)
    try:
        await conn.execute(CREATE_TABLE_SQL)
        await conn.execute("""
            INSERT INTO market_breadth_daily
              (date, advance_count, decline_count, total_count, breadth_pct)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (date) DO UPDATE SET
              advance_count = EXCLUDED.advance_count,
              decline_count = EXCLUDED.decline_count,
              total_count   = EXCLUDED.total_count,
              breadth_pct   = EXCLUDED.breadth_pct
        """, entry_date, args.advance, args.decline, args.total, breadth_pct)

        print(
            f"\nBreadth saved: {args.advance} adv / {args.decline} dec / "
            f"{args.total} total = {breadth_pct:.1f}% advancing for {args.date}"
        )

        # Show last 10 entries
        rows = await conn.fetch("""
            SELECT date, advance_count, decline_count, total_count, breadth_pct
            FROM market_breadth_daily
            ORDER BY date DESC
            LIMIT 10
        """)
        print(f"\n  {'Tanggal':<12}  {'Adv':>5}  {'Dec':>5}  {'Total':>6}  {'Breadth%':>9}")
        print("  " + "-" * 48)
        for r in rows:
            marker = " <-- baru" if r["date"].isoformat() == args.date else ""
            print(f"  {r['date'].strftime('%Y-%m-%d')}  {r['advance_count']:>5}  "
                  f"{r['decline_count']:>5}  {r['total_count']:>6}  "
                  f"{float(r['breadth_pct']):>8.1f}%{marker}")
        print()
    finally:
        await conn.close()


asyncio.run(main())

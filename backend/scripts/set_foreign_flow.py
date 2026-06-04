"""
Set today's (or a specific date's) foreign net flow and recompute F&G indices.

Usage (run from project root):
    python -m backend.scripts.set_foreign_flow --value -1234.56
    python -m backend.scripts.set_foreign_flow --value -1234.56 --buy-total 3500 --sell-total 4734.56
    python -m backend.scripts.set_foreign_flow --value 789.0 --date 2026-05-23

  --value      Net flow in IDR miliar. NEGATIVE = net outflow (asing jual).
               POSITIVE = net inflow (asing beli).
  --buy-total  Total foreign BUY value in IDR miliar (optional, from Stockbit).
               Enables retail-share-of-total-market formula in Domestic Score.
  --sell-total Total foreign SELL value in IDR miliar (optional).
  --ihsg       IHSG close price (optional). Upserts ihsg_daily (source=manual_pdf)
               so the F&G score reflects today's close immediately. compute_index
               runs automatically at the end regardless.
  --date       YYYY-MM-DD. Defaults to today (WIB, UTC+7).

Note: net = buy_total - sell_total.  If --buy-total and --sell-total are given,
--value is still required (as a cross-check / primary source).
"""
import argparse, asyncio, asyncpg, os, re, subprocess, sys
sys.stdout.reconfigure(encoding="utf-8")
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
from backend.workers import compute_overall_score

load_dotenv(Path(".env"))
load_dotenv(Path(".env.local"), override=True)

WIB = timezone(timedelta(hours=7))


def today_wib() -> str:
    return datetime.now(WIB).strftime("%Y-%m-%d")


def parse_args():
    p = argparse.ArgumentParser(description="Set foreign net flow for a trading day.")
    p.add_argument("--value", type=float, required=True,
                   help="Net IDR miliar. Negative = outflow (asing jual).")
    p.add_argument("--buy-total", type=float, default=None,
                   help="Total foreign BUY value, IDR miliar (optional, from Stockbit).")
    p.add_argument("--sell-total", type=float, default=None,
                   help="Total foreign SELL value, IDR miliar (optional).")
    p.add_argument("--ihsg", type=float, default=None,
                   help="IHSG close price (optional). Upserts ihsg_daily so F&G "
                        "reflects today's close without waiting for sync_market.")
    p.add_argument("--date", default=today_wib(),
                   help="YYYY-MM-DD (default: today WIB)")
    return p.parse_args()


async def main():
    args = parse_args()

    if not re.match(r"^\d{4}-\d{2}-\d{2}$", args.date):
        print(f"ERROR: date must be YYYY-MM-DD, got: {args.date}")
        sys.exit(1)

    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    entry_date = date.fromisoformat(args.date)
    try:
        await conn.execute("""
            INSERT INTO foreign_flow_daily (date, net_idr_billions, buy_idr_billions, sell_idr_billions, source)
            VALUES ($1, $2, $3, $4, 'manual')
            ON CONFLICT (date) DO UPDATE SET
              net_idr_billions  = EXCLUDED.net_idr_billions,
              buy_idr_billions  = COALESCE(EXCLUDED.buy_idr_billions,  foreign_flow_daily.buy_idr_billions),
              sell_idr_billions = COALESCE(EXCLUDED.sell_idr_billions, foreign_flow_daily.sell_idr_billions),
              source            = 'manual',
              fetched_at        = NOW()
        """, entry_date, args.value, args.buy_total, args.sell_total)

        direction = "net JUAL asing (outflow)" if args.value < 0 else "net BELI asing (inflow)"
        print(f"\nForeign flow saved:")
        print(f"  Date       : {args.date}")
        print(f"  Net        : {args.value:+,.2f} IDR miliar  ({direction})")
        if args.buy_total is not None:
            print(f"  Buy total  : {args.buy_total:,.2f} IDR miliar")
            print(f"  Sell total : {args.sell_total:,.2f} IDR miliar")
            implied_net = args.buy_total - args.sell_total
            print(f"  Implied net: {implied_net:+,.2f}  (vs --value {args.value:+,.2f})")
        else:
            print(f"  Buy/sell total: not provided  (use --buy-total / --sell-total to enable market-share participation)")

        # ── Optional: upsert IHSG close so F&G reflects today's price ──
        if args.ihsg is not None:
            await conn.execute("""
                INSERT INTO ihsg_daily (date, close, source)
                VALUES ($1, $2, 'manual_pdf')
                ON CONFLICT (date) DO UPDATE SET
                  close  = EXCLUDED.close,
                  source = 'manual_pdf',
                  fetched_at = NOW()
            """, entry_date, args.ihsg)
            print(f"\nIHSG close saved: {args.ihsg:,.3f} for {args.date}")

        # Show last 5 entries
        rows = await conn.fetch("""
            SELECT date, net_idr_billions, buy_idr_billions, sell_idr_billions
            FROM foreign_flow_daily
            ORDER BY date DESC
            LIMIT 5
        """)
        print(f"\n  {'Tanggal':<12}  {'Net':>10}  {'Buy total':>10}  {'Sell total':>10}  Tipe")
        print("  " + "-" * 62)
        for r in rows:
            val  = float(r["net_idr_billions"])
            b    = f"{float(r['buy_idr_billions']):>10,.0f}"  if r["buy_idr_billions"]  else "         —"
            s    = f"{float(r['sell_idr_billions']):>10,.0f}" if r["sell_idr_billions"] else "         —"
            tipe = "Net Buy " if val >= 0 else "Net Jual"
            marker = " <-- baru" if r["date"].isoformat() == args.date else ""
            print(f"  {r['date'].strftime('%Y-%m-%d')}  {val:>+10,.0f}  {b}  {s}  {tipe}{marker}")
    finally:
        await conn.close()

    # Trigger compute_index (Foreign Score) and wait for it
    if args.ihsg is not None:
        print("\ncompute_index triggered automatically (IHSG close updated)")
    print("\nMemulai compute_index (Foreign Score)...")
    result = subprocess.run(
        [sys.executable, "-m", "backend.workers.compute_index"],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip())
    if result.returncode != 0:
        print(f"\nWARNING: compute_index exited with code {result.returncode}")

    # Trigger Overall Score (reads fresh Foreign + latest Domestic)
    print("\nMemulai compute_overall_score...")
    await compute_overall_score.run()
    print("Selesai.")


asyncio.run(main())

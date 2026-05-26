"""
Set today's (or a specific date's) domestic gross buy/sell flow,
then automatically recompute Index B (fear_greed_psychology).

Usage (run from project root):
    python -m backend.scripts.set_domestic_flow --buy 6240 --sell 5180
    python -m backend.scripts.set_domestic_flow --buy 6240 --sell 5180 --date 2026-05-23

  --buy    Gross domestic buy value, IDR miliar (positive, from Stockbit).
  --sell   Gross domestic sell value, IDR miliar (positive, from Stockbit).
  --date   YYYY-MM-DD. Defaults to today (WIB, UTC+7).

Net = buy - sell.  Positive net = domestik net beli.  Negative = domestik net jual.
"""
import argparse, asyncio, asyncpg, os, re, sys
sys.stdout.reconfigure(encoding="utf-8")
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
from backend.workers import compute_psychology_index, compute_overall_score

load_dotenv(Path(".env"))
load_dotenv(Path(".env.local"), override=True)

WIB = timezone(timedelta(hours=7))


def today_wib() -> str:
    return datetime.now(WIB).strftime("%Y-%m-%d")


def parse_args():
    p = argparse.ArgumentParser(description="Set domestic gross buy/sell flow for a trading day.")
    p.add_argument("--buy",  type=float, required=True,
                   help="Gross domestic buy, IDR miliar (positive).")
    p.add_argument("--sell", type=float, required=True,
                   help="Gross domestic sell, IDR miliar (positive).")
    p.add_argument("--date", default=today_wib(),
                   help="YYYY-MM-DD (default: today WIB)")
    return p.parse_args()


async def main():
    args = parse_args()

    if not re.match(r"^\d{4}-\d{2}-\d{2}$", args.date):
        print(f"ERROR: date must be YYYY-MM-DD, got: {args.date}")
        sys.exit(1)
    if args.buy < 0 or args.sell < 0:
        print("ERROR: --buy and --sell must be non-negative.")
        sys.exit(1)

    net = args.buy - args.sell
    direction = "net BELI domestik" if net >= 0 else "net JUAL domestik"

    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    entry_date = date.fromisoformat(args.date)
    try:
        await conn.execute("""
            INSERT INTO domestic_flow_daily (date, buy_value_bn, sell_value_bn, source, updated_at)
            VALUES ($1, $2, $3, 'manual', NOW())
            ON CONFLICT (date) DO UPDATE SET
              buy_value_bn  = EXCLUDED.buy_value_bn,
              sell_value_bn = EXCLUDED.sell_value_bn,
              source        = 'manual',
              updated_at    = NOW()
        """, entry_date, args.buy, args.sell)

        print(f"\nDomestic flow saved:")
        print(f"  Date  : {args.date}")
        print(f"  Buy   : {args.buy:>10,.0f} IDR miliar")
        print(f"  Sell  : {args.sell:>10,.0f} IDR miliar")
        print(f"  Net   : {net:>+10,.0f} IDR miliar  ({direction})")

        # Show last 10 entries
        rows = await conn.fetch("""
            SELECT date, buy_value_bn, sell_value_bn
            FROM domestic_flow_daily
            ORDER BY date DESC
            LIMIT 10
        """)
        print(f"\n  {'Tanggal':<12}  {'Buy':>10}  {'Sell':>10}  {'Net':>10}  Tipe")
        print("  " + "-" * 58)
        for r in rows:
            b = float(r["buy_value_bn"])
            s = float(r["sell_value_bn"])
            n = b - s
            tipe = "Net Beli" if n >= 0 else "Net Jual"
            marker = " <-- baru" if r["date"].isoformat() == args.date else ""
            print(f"  {r['date'].strftime('%Y-%m-%d')}  {b:>10,.0f}  {s:>10,.0f}  {n:>+10,.0f}  {tipe}{marker}")

        print()

    finally:
        await conn.close()

    # ── Trigger Domestic Score compute ────────────────────────────────────────
    print("Computing Domestic Score (Sentimen Ritel)...")
    await compute_psychology_index.run()

    # ── Trigger Overall Score compute ─────────────────────────────────────────
    print("Computing Overall Score...")
    await compute_overall_score.run()
    print("Selesai.")


asyncio.run(main())

"""Audit fear_greed_index for stale backfilled rows (momentum frozen at 0)."""
import asyncio, asyncpg, os, json, sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(".env")); load_dotenv(Path(".env.local"), override=True)

async def main():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    rows = await conn.fetch(
        "SELECT date, raw_score, smoothed_score, label, components_json, is_backfilled "
        "FROM fear_greed_index ORDER BY date ASC"
    )
    print(f"Total rows: {len(rows)}")

    backfill_dates, live_dates, stale = [], [], []
    for r in rows:
        try:
            raw_cj = json.loads(r["components_json"]) if r["components_json"] else {}
            # compute_index.py stores a list of component dicts; backtest stores a plain dict
            if isinstance(raw_cj, list):
                # list format: [{id: "ihsg_momentum", score: ...}, ...]
                cj = {item["id"]: item.get("score") for item in raw_cj if "id" in item}
            else:
                cj = raw_cj
        except Exception:
            cj = {}
        # backtest key is "momentum"; live key is "ihsg_momentum"
        mom = cj.get("momentum") if cj.get("momentum") is not None else cj.get("ihsg_momentum")
        bf  = r["is_backfilled"]
        if bf:
            backfill_dates.append(r["date"])
        else:
            live_dates.append(r["date"])
        if bf and (mom is None or mom == 0.0):
            stale.append((r["date"], mom, list(cj.keys()), r["raw_score"], r["smoothed_score"]))

    print(f"Backfilled rows : {len(backfill_dates)}  "
          f"{backfill_dates[0] if backfill_dates else 'n/a'} to "
          f"{backfill_dates[-1] if backfill_dates else 'n/a'}")
    print(f"Live rows       : {len(live_dates)}")
    print(f"Stale (bf, mom=0 or absent): {len(stale)}")
    if stale:
        print(f"  First stale: {stale[0][0]}   Last stale: {stale[-1][0]}")

    print("\nSample stale rows (every 5th):")
    for i in range(0, len(stale), 5):
        d, mom, keys, raw, smooth = stale[i]
        print(f"  {d}  mom={mom}  raw={raw:.1f}  smooth={smooth:.1f}  keys={keys}")

    # Show which backfill rows are NOT stale (already have correct momentum)
    stale_dates = {s[0] for s in stale}
    good_bf = [(r["date"], r["raw_score"]) for r in rows
               if r["is_backfilled"] and r["date"] not in stale_dates]
    print(f"\nBackfilled rows with non-zero momentum: {len(good_bf)}")
    if good_bf:
        print(f"  {good_bf[0][0]} to {good_bf[-1][0]}")

    await conn.close()

asyncio.run(main())

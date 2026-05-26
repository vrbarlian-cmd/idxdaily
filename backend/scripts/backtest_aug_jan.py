"""
F&G Backtest — Aug 2025 through Jan 2026.

No-lookahead: for each target date, only data with date <= target_date is used
for the percentile ranking. Winsorization bounds are pre-computed from the full
FF dataset (minor lookahead for clipping only — acceptable).

Components used (same weights as backfill_fear_greed.py):
  momentum     0.25  — MA30/MA125 ratio, percentile vs history
  volatility   0.20  — 20d realized vol, INVERTED percentile
  rupiah_stress 0.20 — 20d USD/IDR pct change, INVERTED percentile
  foreign_flow 0.20  — 5d rolling sum of net flow, winsorized, percentile
  (headline + breadth omitted — no historical data available)

Stores results to fear_greed_index with is_backfilled=TRUE.
Skips dates that already have valid live rows (is_backfilled=FALSE AND smoothed_score IS NOT NULL).

Run from project root:
    python -m backend.scripts.backtest_aug_jan
"""

import asyncio
import math
import json
import os
from datetime import date, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(".env"))
load_dotenv(Path(".env.local"), override=True)

import asyncpg

EMA_ALPHA   = 0.7
ROLL_WIN_FF = 5
MIN_MOM     = 126   # need MA125 + at least 2 history points
MIN_VOL     = 21    # need 20 log returns + 1 reference
MIN_RUP     = 21    # need 20 changes + 1 reference

W_MOM = 0.25
W_VOL = 0.20
W_RUP = 0.20
W_FF  = 0.20


def pct_rank(value: float, history: list[float]) -> float:
    if not history:
        return 50.0
    below = sum(1 for h in history if h < value)
    return (below / len(history)) * 100.0


def compute_momentum(prices: list[float]) -> float | None:
    if len(prices) < MIN_MOM:
        return None
    ratios = []
    for i in range(124, len(prices)):
        ma125 = sum(prices[i - 124: i + 1]) / 125
        ma30  = sum(prices[i - 29:  i + 1]) / 30
        ratios.append(ma30 / ma125)
    if len(ratios) < 2:
        return None
    return pct_rank(ratios[-1], ratios[:-1])


def compute_volatility(prices: list[float]) -> float | None:
    if len(prices) < MIN_VOL:
        return None
    vols = []
    for i in range(20, len(prices)):
        win = prices[i - 20: i + 1]
        lr  = [math.log(win[j] / win[j-1]) for j in range(1, len(win))]
        mean_r   = sum(lr) / len(lr)
        variance = sum((r - mean_r)**2 for r in lr) / len(lr)
        vols.append(math.sqrt(variance) * math.sqrt(252))
    if len(vols) < 2:
        return None
    return 100.0 - pct_rank(vols[-1], vols[:-1])   # inverted


def compute_rupiah(rates: list[float]) -> float | None:
    if len(rates) < MIN_RUP:
        return None
    changes = []
    for i in range(20, len(rates)):
        changes.append((rates[i] - rates[i-20]) / rates[i-20] * 100)
    if len(changes) < 2:
        return None
    return 100.0 - pct_rank(changes[-1], changes[:-1])  # inverted


def compute_ff(nets: list[float], winsor_lo: float, winsor_hi: float) -> float | None:
    if len(nets) < 2:
        return None
    sums = []
    for i in range(len(nets)):
        win = nets[max(0, i - ROLL_WIN_FF + 1): i + 1]
        sums.append(sum(win))
    sums_w = [max(winsor_lo, min(winsor_hi, s)) for s in sums]
    if len(sums_w) < 2:
        return 50.0
    return pct_rank(sums_w[-1], sums_w[:-1])


def score_to_label(score: float) -> str:
    if score >= 75: return "Extreme Greed"
    if score >= 55: return "Greed"
    if score >= 45: return "Neutral"
    if score >= 25: return "Fear"
    return "Extreme Fear"


async def main() -> None:
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        # Ensure is_backfilled column exists
        await conn.execute(
            "ALTER TABLE fear_greed_index ADD COLUMN IF NOT EXISTS is_backfilled BOOLEAN NOT NULL DEFAULT FALSE"
        )

        START = date(2025, 8, 1)
        END   = date(2026, 1, 30)

        # Load full datasets (no date restriction — needed for no-lookahead percentile history)
        ihsg_rows   = await conn.fetch("SELECT date, close FROM ihsg_daily ORDER BY date ASC")
        usdidr_rows = await conn.fetch("SELECT date, close FROM usdidr_daily ORDER BY date ASC")
        ff_rows     = await conn.fetch(
            "SELECT date, net_idr_billions FROM foreign_flow_daily "
            "WHERE net_idr_billions IS NOT NULL ORDER BY date ASC"
        )

        ihsg_by_date   = {r["date"]: float(r["close"]) for r in ihsg_rows}
        usdidr_by_date = {r["date"]: float(r["close"]) for r in usdidr_rows}
        ff_by_date     = {r["date"]: float(r["net_idr_billions"]) for r in ff_rows}

        ihsg_dates   = [r["date"] for r in ihsg_rows]
        usdidr_dates = [r["date"] for r in usdidr_rows]
        ff_dates     = [r["date"] for r in ff_rows]

        # IHSG trading days in backtest window
        backtest_dates = [d for d in ihsg_dates if START <= d <= END]
        print(f"[OK] Backtest dates: {len(backtest_dates)} IHSG trading days ({START} to {END})")

        # Skip valid live rows
        live_valid = await conn.fetch(
            "SELECT date FROM fear_greed_index WHERE is_backfilled=FALSE AND smoothed_score IS NOT NULL"
        )
        live_set = {r["date"] for r in live_valid}
        print(f"[OK] Live valid rows (will not overwrite): {len(live_set)}")

        # Pre-compute FF winsorization from the full dataset
        all_nets = [ff_by_date[d] for d in ff_dates]
        all_sums = []
        for i in range(len(all_nets)):
            win = all_nets[max(0, i - ROLL_WIN_FF + 1): i + 1]
            all_sums.append(sum(win))
        sorted_sums = sorted(all_sums)
        n_sums = len(sorted_sums)
        winsor_lo = sorted_sums[max(0, int(n_sums * 0.05))]
        winsor_hi = sorted_sums[min(n_sums - 1, int(n_sums * 0.95))]
        print(f"[OK] FF winsorization: p5={winsor_lo:.1f}, p95={winsor_hi:.1f} ({n_sums} sums)")

        # Compute raw scores
        records: list[dict] = []
        for target_date in backtest_dates:
            if target_date in live_set:
                continue  # don't overwrite live rows

            ihsg_prices = [ihsg_by_date[d] for d in ihsg_dates if d <= target_date]
            usd_rates   = [usdidr_by_date[d] for d in usdidr_dates if d <= target_date]
            ff_nets_td  = [ff_by_date[d] for d in ff_dates if d <= target_date]

            mom_s = compute_momentum(ihsg_prices)
            vol_s = compute_volatility(ihsg_prices)
            rup_s = compute_rupiah(usd_rates)
            ff_s  = compute_ff(ff_nets_td, winsor_lo, winsor_hi)

            comps = []
            total_w = 0.0
            if mom_s is not None: comps.append(("momentum",     W_MOM, mom_s)); total_w += W_MOM
            if vol_s is not None: comps.append(("volatility",   W_VOL, vol_s)); total_w += W_VOL
            if rup_s is not None: comps.append(("rupiah",       W_RUP, rup_s)); total_w += W_RUP
            if ff_s  is not None: comps.append(("foreign_flow", W_FF,  ff_s )); total_w += W_FF

            if not comps or total_w == 0:
                continue

            raw_score = sum(w / total_w * s for _, w, s in comps)
            records.append({
                "date":      target_date,
                "raw_score": round(raw_score, 2),
                "n_comps":   len(comps),
                "comps":     {name: round(s, 2) for name, _, s in comps},
                "ff_score":  ff_s,
                "mom_score": mom_s,
            })

        print(f"[OK] {len(records)} records computed")

        # Apply EMA smoothing chronologically
        records.sort(key=lambda r: r["date"])

        # Seed EMA from the most recent valid entry before our first record
        first_date = records[0]["date"] if records else None
        seed = await conn.fetchrow(
            "SELECT smoothed_score FROM fear_greed_index "
            "WHERE smoothed_score IS NOT NULL AND date < $1 ORDER BY date DESC LIMIT 1",
            first_date,
        ) if first_date else None
        smoothed: float | None = float(seed["smoothed_score"]) if seed else None
        if smoothed is not None:
            print(f"[OK] EMA seed: {smoothed:.2f} (from DB before {first_date})")
        else:
            print("[OK] No EMA seed found — starting cold from first raw score")

        for rec in records:
            raw = rec["raw_score"]
            if smoothed is None:
                smoothed = raw
            else:
                smoothed = EMA_ALPHA * raw + (1 - EMA_ALPHA) * smoothed
            rec["smoothed_score"] = round(smoothed, 2)

        # Upsert to fear_greed_index
        inserted = 0
        for rec in records:
            label    = score_to_label(rec["smoothed_score"])
            comp_str = json.dumps(rec["comps"])
            await conn.execute("""
                INSERT INTO fear_greed_index
                    (date, score, raw_score, smoothed_score, label,
                     active_components, components_json, is_backfilled, window_days, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, TRUE, 126, NOW())
                ON CONFLICT (date) DO UPDATE SET
                    score             = EXCLUDED.score,
                    raw_score         = EXCLUDED.raw_score,
                    smoothed_score    = EXCLUDED.smoothed_score,
                    label             = EXCLUDED.label,
                    active_components = EXCLUDED.active_components,
                    components_json   = EXCLUDED.components_json,
                    is_backfilled     = TRUE,
                    updated_at        = NOW()
                WHERE fear_greed_index.is_backfilled = TRUE
                   OR fear_greed_index.smoothed_score IS NULL
            """,
                rec["date"],
                rec["smoothed_score"],
                rec["raw_score"],
                rec["smoothed_score"],
                label,
                rec["n_comps"],
                comp_str,
            )
            inserted += 1

        print(f"[OK] {inserted} rows upserted to fear_greed_index")

        # ── Month-by-month report ─────────────────────────────────────────────
        print(f"\n{'='*80}")
        print(f"  F&G BACKTEST REPORT — Aug 2025 to Jan 2026")
        print(f"  (4 components: momentum, volatility, rupiah_stress, foreign_flow)")
        print(f"{'='*80}")

        all_rec = await conn.fetch(
            "SELECT date, raw_score, smoothed_score, label, components_json "
            "FROM fear_greed_index "
            "WHERE date >= $1 AND date <= $2 "
            "ORDER BY date ASC",
            START, END,
        )

        from collections import defaultdict
        by_month: dict[str, list] = defaultdict(list)
        for r in all_rec:
            key = str(r["date"])[:7]
            by_month[key].append(r)

        print(f"\n{'MONTH':<10} {'DAYS':>5} {'AVG RAW':>9} {'AVG SMOOTH':>11} "
              f"{'LABEL (end-of-month)':25} {'FF_SCORE range'}")
        print("-" * 80)
        for month in sorted(by_month):
            rows = by_month[month]
            avg_raw    = sum(r["raw_score"] for r in rows if r["raw_score"]) / len(rows)
            avg_smooth = sum(r["smoothed_score"] for r in rows if r["smoothed_score"]) / len(rows)
            last_label = rows[-1]["label"]
            # FF scores from components_json
            ff_scores = []
            for r in rows:
                try:
                    cj = json.loads(r["components_json"]) if r["components_json"] else {}
                    if isinstance(cj, dict) and "foreign_flow" in cj:
                        ff_scores.append(cj["foreign_flow"])
                except Exception:
                    pass
            ff_str = f"{min(ff_scores):.0f}–{max(ff_scores):.0f}" if ff_scores else "n/a"
            print(f"{month:<10} {len(rows):>5} {avg_raw:>9.1f} {avg_smooth:>11.1f} "
                  f"{last_label:25} {ff_str}")

        # Detailed day-by-day for Aug and Jan (critical months)
        for focus_month in ["2025-08", "2025-09", "2025-10", "2025-11", "2025-12", "2026-01"]:
            rows = by_month.get(focus_month, [])
            if not rows:
                continue
            print(f"\n  {focus_month} — daily detail:")
            print(f"  {'DATE':<12} {'RAW':>6} {'SMOOTH':>7} {'LABEL':<16} {'MOM':>5} {'VOL':>5} {'RUP':>5} {'FF':>5}")
            for r in rows:
                try:
                    cj = json.loads(r["components_json"]) if r["components_json"] else {}
                except Exception:
                    cj = {}
                mom = f"{cj.get('momentum', 0):.0f}"    if isinstance(cj, dict) else "?"
                vol = f"{cj.get('volatility', 0):.0f}"  if isinstance(cj, dict) else "?"
                rup = f"{cj.get('rupiah', 0):.0f}"      if isinstance(cj, dict) else "?"
                ff  = f"{cj.get('foreign_flow', 0):.0f}" if isinstance(cj, dict) else "?"
                raw_s    = f"{r['raw_score']:6.1f}"    if r["raw_score"]    else "   —  "
                smooth_s = f"{r['smoothed_score']:7.1f}" if r["smoothed_score"] else "     —"
                print(f"  {str(r['date']):<12} {raw_s} {smooth_s} {r['label']:<16} {mom:>5} {vol:>5} {rup:>5} {ff:>5}")

    finally:
        await conn.close()


asyncio.run(main())

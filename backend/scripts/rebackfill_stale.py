"""
Re-backfill stale fear_greed_index rows (Feb 23 – May 21, 2026).

These rows were computed before the 3-year IHSG history extension, leaving
momentum frozen at 0 because MA30/MA125 had insufficient calibration history.

Strategy
--------
- Re-compute raw scores for ALL backfilled rows in the stale window using the
  same no-lookahead backtest formula (identical to backtest_aug_jan.py).
- Seed EMA from the last correct smoothed_score immediately before the window.
- Re-apply EMA forward across the entire window (including any non-stale rows
  already in the window, so the EMA chain is consistent).
- Upsert ONLY is_backfilled=TRUE rows; live rows (is_backfilled=FALSE) are
  never touched.
- No formula or weight change.

Run from project root:
    python -m backend.scripts.rebackfill_stale
"""
import asyncio, math, json, os, sys
sys.stdout.reconfigure(encoding="utf-8")
from datetime import date
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(".env"))
load_dotenv(Path(".env.local"), override=True)
import asyncpg

# ── Formula constants (identical to backtest_aug_jan.py) ─────────────────────
EMA_ALPHA   = 0.7
ROLL_WIN_FF = 5
MIN_MOM     = 126
MIN_VOL     = 21
MIN_RUP     = 21

W_MOM = 0.25
W_VOL = 0.20
W_RUP = 0.20
W_FF  = 0.20

# Window to fix — confirmed stale via audit_stale.py
STALE_START = date(2026, 2, 23)
STALE_END   = date(2026, 5, 22)   # inclusive; covers May 21 + any same-day rerun


# ── Math helpers ──────────────────────────────────────────────────────────────

def pct_rank(value, history):
    if not history:
        return 50.0
    below = sum(1 for h in history if h < value)
    return (below / len(history)) * 100.0


def compute_momentum(prices):
    if len(prices) < MIN_MOM:
        return None, None, None, None
    ratios = []
    for i in range(124, len(prices)):
        ma125 = sum(prices[i - 124: i + 1]) / 125
        ma30  = sum(prices[i - 29:  i + 1]) / 30
        ratios.append(ma30 / ma125)
    if len(ratios) < 2:
        return None, None, None, None
    current = ratios[-1]
    score   = pct_rank(current, ratios[:-1])
    ma30    = sum(prices[-30:]) / 30
    ma125   = sum(prices[-125:]) / 125
    return round(score, 2), round(ma30, 2), round(ma125, 2), round((current - 1) * 100, 3)


def compute_volatility(prices):
    if len(prices) < MIN_VOL:
        return None, None
    vols = []
    for i in range(20, len(prices)):
        win  = prices[i - 20: i + 1]
        lr   = [math.log(win[j] / win[j-1]) for j in range(1, len(win))]
        mean_r   = sum(lr) / len(lr)
        variance = sum((r - mean_r)**2 for r in lr) / len(lr)
        vols.append(math.sqrt(variance) * math.sqrt(252))
    if len(vols) < 2:
        return None, None
    current = vols[-1]
    score   = 100.0 - pct_rank(current, vols[:-1])
    return round(score, 2), round(current * 100, 3)


def compute_rupiah(rates):
    if len(rates) < MIN_RUP:
        return None, None
    changes = []
    for i in range(20, len(rates)):
        changes.append((rates[i] - rates[i-20]) / rates[i-20] * 100)
    if len(changes) < 2:
        return None, None
    current = changes[-1]
    score   = 100.0 - pct_rank(current, changes[:-1])
    return round(score, 2), round(current, 4)


def compute_ff(nets, winsor_lo, winsor_hi):
    if len(nets) < 2:
        return None, None
    sums = []
    for i in range(len(nets)):
        win = nets[max(0, i - ROLL_WIN_FF + 1): i + 1]
        sums.append(sum(win))
    sums_w = [max(winsor_lo, min(winsor_hi, s)) for s in sums]
    current     = sums[-1]
    current_w   = sums_w[-1]
    score       = pct_rank(current_w, sums_w[:-1])
    return round(score, 2), round(current, 2)


def score_to_label(score):
    if score >= 75: return "Extreme Greed"
    if score >= 55: return "Greed"
    if score >= 45: return "Neutral"
    if score >= 25: return "Fear"
    return "Extreme Fear"


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        # ── Load full market datasets (no date cap — no-lookahead applied in loop)
        ihsg_rows = await conn.fetch(
            "SELECT date, close FROM ihsg_daily ORDER BY date ASC"
        )
        usd_rows = await conn.fetch(
            "SELECT date, close FROM usdidr_daily ORDER BY date ASC"
        )
        ff_rows = await conn.fetch(
            "SELECT date, net_idr_billions FROM foreign_flow_daily "
            "WHERE net_idr_billions IS NOT NULL ORDER BY date ASC"
        )

        ihsg_by_date = {r["date"]: float(r["close"]) for r in ihsg_rows}
        usd_by_date  = {r["date"]: float(r["close"]) for r in usd_rows}
        ff_by_date   = {r["date"]: float(r["net_idr_billions"]) for r in ff_rows}
        ihsg_dates   = [r["date"] for r in ihsg_rows]
        usd_dates    = [r["date"] for r in usd_rows]
        ff_dates     = [r["date"] for r in ff_rows]

        print(f"IHSG  : {len(ihsg_dates)} bars  {ihsg_dates[0]} to {ihsg_dates[-1]}")
        print(f"USD/IDR: {len(usd_dates)} bars  {usd_dates[0]} to {usd_dates[-1]}")
        print(f"FF    : {len(ff_dates)} bars  {ff_dates[0]} to {ff_dates[-1]}")

        # ── FF winsorisation from full dataset (same minor lookahead as backtest)
        all_nets = [ff_by_date[d] for d in ff_dates]
        all_sums = []
        for i in range(len(all_nets)):
            win = all_nets[max(0, i - ROLL_WIN_FF + 1): i + 1]
            all_sums.append(sum(win))
        sorted_sums = sorted(all_sums)
        n = len(sorted_sums)
        winsor_lo = sorted_sums[max(0, int(n * 0.05))]
        winsor_hi = sorted_sums[min(n - 1, int(n * 0.95))]
        print(f"FF winsorisation: lo={winsor_lo:.1f}  hi={winsor_hi:.1f}  ({n} rolling sums)")

        # ── Identify which backfilled rows are in the stale window
        existing = await conn.fetch(
            "SELECT date, raw_score, smoothed_score, is_backfilled, components_json "
            "FROM fear_greed_index ORDER BY date ASC"
        )
        # Dates in stale window that are backfilled (we will re-compute these)
        stale_window_bf = {
            r["date"] for r in existing
            if r["is_backfilled"] and STALE_START <= r["date"] <= STALE_END
        }
        # Live rows (never overwrite)
        live_set = {r["date"] for r in existing if not r["is_backfilled"]}

        print(f"\nRows in stale window (is_backfilled=TRUE): {len(stale_window_bf)}")
        if stale_window_bf:
            sl = sorted(stale_window_bf)
            print(f"  Dates: {sl[0]} to {sl[-1]}")

        # ── EMA seed: last smoothed_score from a correct row before STALE_START
        seed_row = await conn.fetchrow(
            "SELECT date, smoothed_score FROM fear_greed_index "
            "WHERE date < $1 AND smoothed_score IS NOT NULL "
            "ORDER BY date DESC LIMIT 1",
            STALE_START,
        )
        if seed_row:
            ema_seed = float(seed_row["smoothed_score"])
            print(f"\nEMA seed: {ema_seed:.2f}  (from {seed_row['date']})")
        else:
            ema_seed = None
            print("\nNo EMA seed found — will start cold")

        # ── Get all IHSG trading days in the stale window
        target_dates = sorted(
            d for d in ihsg_dates if STALE_START <= d <= STALE_END
        )
        print(f"IHSG trading days in window: {len(target_dates)}  "
              f"({target_dates[0]} to {target_dates[-1]})")

        # ── Compute raw scores for every date in the stale window ─────────────
        records = []
        for target in target_dates:
            # Skip live rows
            if target in live_set:
                continue

            # Only upsert if a backfilled row already exists for this date
            if target not in stale_window_bf:
                continue

            ihsg_seq = [ihsg_by_date[d] for d in ihsg_dates if d <= target]
            usd_seq  = [usd_by_date[d]  for d in usd_dates  if d <= target]
            ff_seq   = [ff_by_date[d]   for d in ff_dates   if d <= target]

            mom_s, ma30, ma125, ratio_pct = compute_momentum(ihsg_seq)
            vol_s, vol_pct                = compute_volatility(ihsg_seq)
            rup_s, chg_pct               = compute_rupiah(usd_seq)
            ff_s,  ff_5d_net             = compute_ff(ff_seq, winsor_lo, winsor_hi)

            comps      = []
            total_w    = 0.0
            comps_json = {}
            if mom_s is not None:
                comps.append((W_MOM, mom_s)); total_w += W_MOM; comps_json["momentum"]     = mom_s
            if vol_s is not None:
                comps.append((W_VOL, vol_s)); total_w += W_VOL; comps_json["volatility"]   = vol_s
            if rup_s is not None:
                comps.append((W_RUP, rup_s)); total_w += W_RUP; comps_json["rupiah"]       = rup_s
            if ff_s  is not None:
                comps.append((W_FF,  ff_s )); total_w += W_FF;  comps_json["foreign_flow"] = ff_s

            if not comps or total_w == 0:
                continue

            raw_score = sum(w / total_w * s for w, s in comps)

            records.append({
                "date":       target,
                "raw_score":  round(raw_score, 2),
                "n_comps":    len(comps),
                "comps_json": comps_json,
                "diag": {
                    "ma30": ma30, "ma125": ma125, "ratio_pct": ratio_pct,
                    "vol_pct": vol_pct, "chg_pct": chg_pct,
                    "ff_5d": ff_5d_net,
                },
            })

        print(f"Records to upsert: {len(records)}")

        # ── EMA smoothing — walk ALL backfilled dates chronologically
        # We re-apply EMA across the full stale window so the chain is consistent.
        # For dates with no record computed (shouldn't happen, but safety), carry forward.
        records.sort(key=lambda r: r["date"])
        records_by_date = {r["date"]: r for r in records}

        smoothed = ema_seed
        for target in target_dates:
            if target not in records_by_date:
                continue
            rec = records_by_date[target]
            raw = rec["raw_score"]
            if smoothed is None:
                smoothed = raw
            else:
                smoothed = EMA_ALPHA * raw + (1 - EMA_ALPHA) * smoothed
            rec["smoothed_score"] = round(smoothed, 2)

        # ── Upsert ────────────────────────────────────────────────────────────
        upserted = 0
        for rec in records:
            if "smoothed_score" not in rec:
                continue
            label    = score_to_label(rec["smoothed_score"])
            comp_str = json.dumps(rec["comps_json"])
            await conn.execute("""
                INSERT INTO fear_greed_index
                    (date, score, raw_score, smoothed_score, label,
                     active_components, components_json, is_backfilled,
                     window_days, updated_at)
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
            upserted += 1

        print(f"Upserted: {upserted} rows")

        # ── Verification report ───────────────────────────────────────────────
        print()
        print("=" * 78)
        print("  VERIFICATION: Feb-May 2026 after re-backfill")
        print("=" * 78)
        verify = await conn.fetch("""
            SELECT date, raw_score, smoothed_score, label, components_json, is_backfilled
            FROM fear_greed_index
            WHERE date BETWEEN '2026-02-01' AND '2026-05-22'
            ORDER BY date
        """)
        print(f"\n  {'DATE':<12} {'IHSG':>8} {'RAW':>7} {'SMOOTH':>8} "
              f"{'LABEL':<15} {'MOM':>6} {'VOL':>6} {'RUP':>6} {'FF':>6} BF")
        print(f"  {'-'*12} {'-'*8} {'-'*7} {'-'*8} {'-'*15} {'-'*6} {'-'*6} {'-'*6} {'-'*6} --")
        for r in verify:
            try:
                cj = json.loads(r["components_json"]) if r["components_json"] else {}
                if isinstance(cj, list):
                    cj = {item["id"]: item.get("score") for item in cj if "id" in item}
            except Exception:
                cj = {}
            ihsg_v = ihsg_by_date.get(r["date"])
            ihsg_s = f"{ihsg_v:,.0f}" if ihsg_v else "   ---"
            raw_s  = f"{r['raw_score']:7.1f}"    if r["raw_score"]    else "      -"
            smo_s  = f"{r['smoothed_score']:8.1f}" if r["smoothed_score"] else "       -"
            mom_s  = f"{cj.get('momentum', cj.get('ihsg_momentum', '?')):>6.0f}" if isinstance(cj.get('momentum', cj.get('ihsg_momentum')), (int, float)) else "     ?"
            vol_s  = f"{cj.get('volatility', cj.get('ihsg_volatility', '?')):>6.0f}" if isinstance(cj.get('volatility', cj.get('ihsg_volatility')), (int, float)) else "     ?"
            rup_s  = f"{cj.get('rupiah', cj.get('rupiah_stress', '?')):>6.0f}" if isinstance(cj.get('rupiah', cj.get('rupiah_stress')), (int, float)) else "     ?"
            ff_s   = f"{cj.get('foreign_flow', '?'):>6.0f}" if isinstance(cj.get('foreign_flow'), (int, float)) else "     ?"
            bf_s   = "BF" if r["is_backfilled"] else "LV"
            mark   = " <--" if r["date"] in (date(2026, 2, 25), date(2026, 3, 9)) else ""
            print(f"  {str(r['date']):<12} {ihsg_s:>8} {raw_s} {smo_s} "
                  f"{r['label']:<15} {mom_s} {vol_s} {rup_s} {ff_s} {bf_s}{mark}")

        # ── Spot-check: any remaining momentum=0 in backfilled rows?
        print()
        remaining_stale = await conn.fetch("""
            SELECT COUNT(*) AS n FROM fear_greed_index
            WHERE is_backfilled = TRUE
              AND components_json::text LIKE '%"momentum": 0.0%'
        """)
        n_still = remaining_stale[0]["n"]
        print(f"Remaining backfilled rows with momentum=0.0: {n_still}")
        if n_still == 0:
            print("  -> All clear. No stale momentum values remain.")
        else:
            stale_left = await conn.fetch("""
                SELECT date, components_json FROM fear_greed_index
                WHERE is_backfilled = TRUE
                  AND components_json::text LIKE '%"momentum": 0.0%'
                ORDER BY date
            """)
            for r in stale_left:
                print(f"  STILL STALE: {r['date']}")

    finally:
        await conn.close()


asyncio.run(main())

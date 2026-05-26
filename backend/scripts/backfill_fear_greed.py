"""
Backfill 90 days of historical Fear & Greed index.

For each IHSG trading day in the last 90 calendar days:
  - Compute momentum, volatility, rupiah stress, foreign flow
  - No lookahead: only data with date <= target_date is used
  - EMA smoothing applied chronologically (alpha=0.7)
  - Foreign flow rolling sums winsorized at p5/p95 of full dataset
  - Stored with is_backfilled=TRUE; live rows never overwritten

Run from project root:
    python -m backend.scripts.backfill_fear_greed
"""

import asyncio
import os
import math
import json
from datetime import date, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(".env"))
load_dotenv(Path(".env.local"), override=True)

EMA_ALPHA = 0.7
ROLL_WIN_FF = 5       # foreign flow rolling window
MIN_IHSG_FOR_VOL = 21 # need at least 21 rows for 20-day vol
MIN_IHSG_FOR_MOM = 126 # need MA30 + MA125

# Component nominal weights
W_MOM  = 0.25
W_VOL  = 0.20
W_RUP  = 0.20
W_FF   = 0.20
# headline (0.15) + breadth (0.10) always skipped


def percentile_rank(value: float, history: list[float]) -> float:
    """Fraction of history values strictly below value, scaled 0-100."""
    if not history:
        return 50.0
    below = sum(1 for h in history if h < value)
    return (below / len(history)) * 100.0


def compute_momentum(ihsg_rows: list[float]) -> float | None:
    """
    ihsg_rows: closing prices in chronological order, up to target date.
    Returns score 0-100 (higher = more bullish momentum).
    """
    if len(ihsg_rows) < MIN_IHSG_FOR_MOM:
        return None
    prices = ihsg_rows

    # Compute MA30/MA125 ratio for each day with enough history
    ratios = []
    for i in range(124, len(prices)):  # need 125 days
        window = prices[max(0, i - 124): i + 1]  # up to 125 prices
        ma125 = sum(window) / len(window)
        ma30_window = prices[i - 29: i + 1]  # last 30 prices
        ma30 = sum(ma30_window) / len(ma30_window)
        ratios.append(ma30 / ma125)

    if len(ratios) < 2:
        return None

    current = ratios[-1]
    history = ratios[:-1]
    return percentile_rank(current, history)


def compute_volatility(ihsg_rows: list[float]) -> float | None:
    """
    Returns score 0-100 (higher = calmer / less fearful, i.e. inverted vol).
    """
    if len(ihsg_rows) < MIN_IHSG_FOR_VOL:
        return None
    prices = ihsg_rows

    # Compute 20-day rolling realized vol at each point
    vols = []
    for i in range(20, len(prices)):
        window = prices[i - 20: i + 1]
        log_returns = [math.log(window[j] / window[j - 1]) for j in range(1, len(window))]
        mean_r = sum(log_returns) / len(log_returns)
        variance = sum((r - mean_r) ** 2 for r in log_returns) / len(log_returns)
        vols.append(math.sqrt(variance) * math.sqrt(252))  # annualised

    if len(vols) < 2:
        return None

    current = vols[-1]
    history = vols[:-1]
    # Inverted: high vol = fear = low score
    return 100.0 - percentile_rank(current, history)


def compute_rupiah_stress(usdidr_rows: list[float]) -> float | None:
    """
    usdidr_rows: USD/IDR rate in chronological order, up to target date.
    Returns score 0-100 (higher = stronger IDR / less stress = less fear).
    """
    if len(usdidr_rows) < 21:
        return None

    # 20-day percentage change in USD/IDR
    changes = []
    for i in range(20, len(usdidr_rows)):
        pct_change = (usdidr_rows[i] - usdidr_rows[i - 20]) / usdidr_rows[i - 20] * 100
        changes.append(pct_change)

    if len(changes) < 2:
        return None

    current = changes[-1]
    history = changes[:-1]
    # Inverted: high USD/IDR change (IDR weakening) = fear = low score
    return 100.0 - percentile_rank(current, history)


def compute_foreign_flow(
    ff_rows: list[float],  # net_idr_billions in chronological order, up to target date
    winsor_p5: float,
    winsor_p95: float,
) -> float | None:
    """
    5-day rolling sum, winsorized at global p5/p95.
    Returns score 0-100 (higher = more inflows = bullish).
    """
    MIN_ROWS = 2
    if len(ff_rows) < MIN_ROWS:
        return None

    # Compute rolling sums
    def roll_sums(nets: list[float]) -> list[float]:
        sums = []
        for i in range(len(nets)):
            win = nets[max(0, i - ROLL_WIN_FF + 1): i + 1]
            sums.append(sum(win))
        return sums

    sums = roll_sums(ff_rows)

    # Winsorize all sums
    sums_w = [max(winsor_p5, min(winsor_p95, s)) for s in sums]

    if len(sums_w) < 2:
        return 50.0

    current = sums_w[-1]
    history = sums_w[:-1]
    return percentile_rank(current, history)


def score_to_label(score: float) -> str:
    if score >= 75:
        return "Extreme Greed"
    if score >= 55:
        return "Greed"
    if score >= 45:
        return "Neutral"
    if score >= 25:
        return "Fear"
    return "Extreme Fear"


async def main() -> None:
    import asyncpg

    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        # ── Step 1: Add is_backfilled column if missing ──────────────────────
        await conn.execute("""
            ALTER TABLE fear_greed_index
            ADD COLUMN IF NOT EXISTS is_backfilled BOOLEAN NOT NULL DEFAULT FALSE
        """)
        print("[OK] is_backfilled column ensured")

        # ── Step 2: Load full datasets ────────────────────────────────────────
        cutoff_90 = date.today() - timedelta(days=90)

        ihsg_all = await conn.fetch(
            "SELECT date, close FROM ihsg_daily ORDER BY date ASC"
        )
        usdidr_all = await conn.fetch(
            "SELECT date, close FROM usdidr_daily ORDER BY date ASC"
        )
        ff_all = await conn.fetch(
            "SELECT date, net_idr_billions FROM foreign_flow_daily "
            "WHERE net_idr_billions IS NOT NULL ORDER BY date ASC"
        )

        # IHSG trading days in our backfill window
        backfill_dates = [
            r["date"] for r in ihsg_all
            if r["date"] >= cutoff_90
        ]
        print(f"[OK] Backfill target: {len(backfill_dates)} IHSG trading days "
              f"({backfill_dates[0]} -> {backfill_dates[-1]})")

        # Rows to skip: live rows that ALREADY HAVE a valid smoothed_score.
        # Live rows with smoothed_score IS NULL (failed compute runs) are included
        # in the backfill so we can patch their gaps rather than leave them blank.
        existing_valid = await conn.fetch(
            "SELECT date FROM fear_greed_index "
            "WHERE is_backfilled = FALSE AND smoothed_score IS NOT NULL"
        )
        live_dates = {r["date"] for r in existing_valid}
        print(f"[OK] Valid live rows (won't overwrite): {len(live_dates)}")

        # ── Step 3: Pre-compute foreign flow winsorization bounds ─────────────
        all_ff_nets = [float(r["net_idr_billions"]) for r in ff_all]
        # Compute all rolling sums from the full dataset
        all_ff_sums = []
        for i in range(len(all_ff_nets)):
            win = all_ff_nets[max(0, i - ROLL_WIN_FF + 1): i + 1]
            all_ff_sums.append(sum(win))

        sorted_sums = sorted(all_ff_sums)
        n = len(sorted_sums)
        winsor_p5  = sorted_sums[max(0, int(n * 0.05))]
        winsor_p95 = sorted_sums[min(n - 1, int(n * 0.95))]
        print(f"[OK] FF winsorization: p5={winsor_p5:.0f}, p95={winsor_p95:.0f} "
              f"(from {n} rolling sums)")

        # ── Step 4: Build lookup structures ───────────────────────────────────
        # Map date -> index in sorted list for fast slicing
        ihsg_by_date = {r["date"]: float(r["close"]) for r in ihsg_all}
        usdidr_by_date = {r["date"]: float(r["close"]) for r in usdidr_all}
        ff_by_date = {
            r["date"]: float(r["net_idr_billions"])
            for r in ff_all if r["net_idr_billions"] is not None
        }

        ihsg_dates_sorted = [r["date"] for r in ihsg_all]
        usdidr_dates_sorted = [r["date"] for r in usdidr_all]
        ff_dates_sorted = [r["date"] for r in ff_all]

        def ihsg_prices_up_to(d: date) -> list[float]:
            return [ihsg_by_date[dt] for dt in ihsg_dates_sorted if dt <= d]

        def usdidr_rates_up_to(d: date) -> list[float]:
            return [usdidr_by_date[dt] for dt in usdidr_dates_sorted if dt <= d]

        def ff_nets_up_to(d: date) -> list[float]:
            return [ff_by_date[dt] for dt in ff_dates_sorted if dt <= d]

        # ── Step 5: Compute raw scores for all backfill dates ─────────────────
        print("\nComputing raw scores...")
        records: list[dict] = []

        for target_date in backfill_dates:
            if target_date in live_dates:
                print(f"  {target_date} SKIP (live row exists)")
                continue

            ihsg_prices = ihsg_prices_up_to(target_date)
            usdidr_rates = usdidr_rates_up_to(target_date)
            ff_nets = ff_nets_up_to(target_date)

            # Compute each component
            mom_score = compute_momentum(ihsg_prices)
            vol_score = compute_volatility(ihsg_prices)
            rup_score = compute_rupiah_stress(usdidr_rates)
            ff_score  = compute_foreign_flow(ff_nets, winsor_p5, winsor_p95)

            # Build active component list and renormalize weights
            components = []
            total_w = 0.0

            if mom_score is not None:
                components.append(("momentum", W_MOM, mom_score))
                total_w += W_MOM
            if vol_score is not None:
                components.append(("volatility", W_VOL, vol_score))
                total_w += W_VOL
            if rup_score is not None:
                components.append(("rupiah", W_RUP, rup_score))
                total_w += W_RUP
            if ff_score is not None:
                components.append(("foreign_flow", W_FF, ff_score))
                total_w += W_FF

            if not components or total_w == 0:
                print(f"  {target_date} SKIP (no components available)")
                continue

            # Renormalized weighted average
            raw_score = sum(w / total_w * s for _, w, s in components)

            records.append({
                "date": target_date,
                "raw_score": round(raw_score, 2),
                "active_components": len(components),
                "comp_detail": {
                    name: round(s, 2)
                    for name, _, s in components
                },
            })

        print(f"\n[OK] {len(records)} records computed (before EMA smoothing)")

        # ── Step 6: Apply EMA smoothing chronologically ───────────────────────
        # Sort chronologically
        records.sort(key=lambda r: r["date"])

        # Seed EMA from the most recent valid smoothed_score in DB that is
        # BEFORE our first record's date — this anchors the backfill chain to
        # any previously computed live row (e.g. a valid row from an earlier run).
        first_date = records[0]["date"] if records else None
        seed_row = await conn.fetchrow(
            "SELECT smoothed_score FROM fear_greed_index "
            "WHERE smoothed_score IS NOT NULL AND date < $1 "
            "ORDER BY date DESC LIMIT 1",
            first_date
        ) if first_date else None
        smoothed_score: float | None = float(seed_row["smoothed_score"]) if seed_row else None
        if smoothed_score is not None:
            print(f"[OK] EMA seed from DB: {smoothed_score:.2f} (before {first_date})")

        for rec in records:
            raw = rec["raw_score"]
            if smoothed_score is None:
                smoothed_score = raw
            else:
                smoothed_score = EMA_ALPHA * raw + (1 - EMA_ALPHA) * smoothed_score
            rec["smoothed_score"] = round(smoothed_score, 2)

        # ── Step 7: Upsert to fear_greed_index ───────────────────────────────
        inserted = 0
        for rec in records:
            label = score_to_label(rec["smoothed_score"])
            comp_json = json.dumps(rec["comp_detail"])

            await conn.execute("""
                INSERT INTO fear_greed_index
                    (date, score, raw_score, smoothed_score, label,
                     active_components, components_json, is_backfilled,
                     window_days, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, TRUE, 90, NOW())
                ON CONFLICT (date) DO UPDATE SET
                    score          = EXCLUDED.score,
                    raw_score      = EXCLUDED.raw_score,
                    smoothed_score = EXCLUDED.smoothed_score,
                    label          = EXCLUDED.label,
                    active_components = EXCLUDED.active_components,
                    components_json = EXCLUDED.components_json,
                    is_backfilled  = TRUE,
                    updated_at     = NOW()
                WHERE fear_greed_index.is_backfilled = TRUE
                   OR fear_greed_index.smoothed_score IS NULL
            """,
                rec["date"],
                rec["smoothed_score"],   # score = smoothed
                rec["raw_score"],
                rec["smoothed_score"],
                label,
                rec["active_components"],
                comp_json,
            )
            inserted += 1

        print(f"[OK] {inserted} rows upserted to fear_greed_index (is_backfilled=TRUE)")

        # ── Step 8: Summary report ────────────────────────────────────────────
        all_rows = await conn.fetch(
            "SELECT date, raw_score, smoothed_score, label, is_backfilled, components_json "
            "FROM fear_greed_index ORDER BY date ASC"
        )
        print(f"\n{'DATE':<12} {'RAW':>6} {'SMOOTH':>7} {'LABEL':<16} {'TYPE':<12} COMPONENTS")
        print("-" * 75)
        for row in all_rows:
            raw_comp = json.loads(row["components_json"]) if row["components_json"] else {}
            if isinstance(raw_comp, dict):
                comp_str = " ".join(f"{k[:3]}={v:.0f}" for k, v in raw_comp.items())
            else:
                comp_str = str(raw_comp)[:40]  # live rows store a list
            row_type = "BACKFILL" if row["is_backfilled"] else "LIVE"
            raw_s = f"{row['raw_score']:6.1f}" if row['raw_score'] is not None else "   —  "
            smo_s = f"{row['smoothed_score']:7.1f}" if row['smoothed_score'] is not None else "     — "
            print(f"{str(row['date']):<12} {raw_s} {smo_s} "
                  f"{row['label']:<16} {row_type:<12} {comp_str}")

        scores = [row["smoothed_score"] for row in all_rows if row["smoothed_score"] is not None]
        if scores:
            print(f"\nRange: {min(scores):.1f} (Fear) -> {max(scores):.1f} (Greed)")
        print(f"Total rows: {len(all_rows)} "
              f"({sum(1 for r in all_rows if r['is_backfilled'])} backfilled, "
              f"{sum(1 for r in all_rows if not r['is_backfilled'])} live)")

    finally:
        await conn.close()


asyncio.run(main())

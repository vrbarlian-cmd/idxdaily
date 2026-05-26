#!/usr/bin/env python3
"""
IDX Fear & Greed — "Domestic Sentiment" Score (Index B).

Parallel to the validated Foreign Sentiment Index (fear_greed_index / Index A).
Stored in a SEPARATE table: fear_greed_psychology.
NEVER modifies fear_greed_index.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL DESIGN CONSTRAINT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Domestic NET flow is the arithmetic inverse of foreign net flow
(what foreigners sell, domestics absorb as counterparties).
Do NOT use domestic net direction as a signal — it would mirror
the Foreign Score and add no information.

Instead, use:
  1. RETAIL PARTICIPATION × MARKET DIRECTION (conviction multiplier)
     — How active is retail RELATIVE to their norm?
     — Is that engagement happening into an up or down market?
  2. MARKET VOLATILITY (context signal)
     — High volatility drives retail fear regardless of direction.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMPONENTS (weighted, 0-100 each)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  1. Retail Conviction    65%  — participation × market direction
  2. Market Volatility    35%  — same formula as Foreign Score

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RETAIL CONVICTION FORMULA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Participation signal (two modes):

  MODE A (preferred) — when foreign buy+sell total is available:
    dom_share          = dom_total / (dom_total + foreign_total)
    participation_ratio = dom_share / MA20(dom_share)
    "How active is retail relative to their typical MARKET SHARE?"

  MODE B (fallback) — when only domestic totals available:
    participation_ratio = dom_total / MA20(dom_total)
    "How active is retail relative to their own typical volume?"

Market direction (from IHSG MA125 momentum):
    ihsg_mom_score     = percentile_rank(ihsg/MA125 - 1, history) → 0-100
    market_direction   = (ihsg_mom_score - 50) / 50              → [-1, +1]

Conviction score:
    conviction_signal  = market_direction × participation_ratio
    conviction_score   = clamp(50 + conviction_signal × 25, 0, 100)

Examples:
  IHSG at 90th pct (mom=90), retail 2× typical share → clamp(50 + 0.8×2×25) = 90  Extreme Greed
  IHSG at 10th pct (mom=10), retail 2× typical share → clamp(50 - 0.8×2×25) = 10  Extreme Fear
  Any IHSG neutral (mom=50), any participation       → 50  Neutral
  Any IHSG, retail at 0 (market closed)              → 50  Neutral

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DATA AVAILABILITY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Domestic buy/sell: entered manually each day via set_domestic_flow.py
- Foreign total (buy+sell): entered via set_foreign_flow.py --buy-total --sell-total
- IHSG, volatility: fetched automatically, 700+ days of history
- Market breadth (A/D line): NO free reliable source confirmed → not included
- Domestic net direction: NOT USED (inverse of foreign, adds no info)
- Forward-only: no historical fabrication. Shows "data terbatas" until stable.

Usage (called by set_domestic_flow.py automatically):
    python -m backend.workers.compute_psychology_index
"""

import asyncio
import json
import math
import sys
sys.stdout.reconfigure(encoding="utf-8")
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env.local", override=True)

from ._db import get_conn


# ── Config ────────────────────────────────────────────────────────────────────

EMA_ALPHA      = 0.7
W_CONVICTION   = 0.65   # retail participation × market direction
W_VOLATILITY   = 0.35   # market volatility (high vol → fear)

# MA window for participation baseline
PARTICIPATION_MA = 20


# ── Math helpers ───────────────────────────────────────────────────────────────

def percentile_rank(value: float, history: list[float]) -> float:
    if not history:
        return 50.0
    return sum(1 for h in history if h < value) / len(history) * 100.0


def rolling_mean(arr: list[float], end: int, window: int) -> float | None:
    if end < window - 1:
        return None
    return sum(arr[end - window + 1 : end + 1]) / window


def rolling_stddev(arr: list[float], end: int, window: int) -> float | None:
    if end < window - 1:
        return None
    sl = arr[end - window + 1 : end + 1]
    mean = sum(sl) / len(sl)
    return math.sqrt(sum((v - mean) ** 2 for v in sl) / len(sl))


# ── IHSG Momentum (identical formula to compute_index.py) ──────────────────────

def compute_ihsg_momentum(bars: list[dict]) -> tuple[float | None, str]:
    """
    Percentile rank of (IHSG / MA125 - 1) over its own history.
    Returns (score_0_100, label).
    """
    MA_WIN = 125
    closes = [b["close"] for b in bars]
    if len(closes) < MA_WIN + 5:
        return None, "Insufficient IHSG data"
    devs = []
    for i in range(MA_WIN - 1, len(closes)):
        ma = rolling_mean(closes, i, MA_WIN)
        if ma:
            devs.append(closes[i] / ma - 1)
    if len(devs) < 2:
        return None, "Insufficient deviation history"
    current = devs[-1]
    score   = percentile_rank(current, devs[:-1])
    sign    = "+" if current >= 0 else ""
    return round(score, 1), f"IHSG {sign}{current*100:.2f}% vs MA{MA_WIN}"


# ── Market Volatility (identical formula to compute_index.py) ──────────────────

def compute_ihsg_volatility(bars: list[dict]) -> tuple[float | None, str]:
    """
    Inverted percentile rank of 20-day annualized vol.
    High vol = fear = low score.
    """
    closes = [b["close"] for b in bars]
    if len(closes) < 40:
        return None, "Insufficient IHSG data for volatility"
    log_rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
    vols = []
    for i in range(19, len(log_rets)):
        sd = rolling_stddev(log_rets, i, 20)
        if sd is not None:
            vols.append(sd * math.sqrt(252))
    if len(vols) < 2:
        return None, "Insufficient vol history"
    current = vols[-1]
    score   = 100.0 - percentile_rank(current, vols[:-1])
    return round(score, 1), f"Vol {current*100:.1f}% (ann.) → inverted"


# ── Retail Conviction ──────────────────────────────────────────────────────────

def compute_retail_conviction(
    domestic_rows: list[dict],   # [{date, buy, sell}] asc
    foreign_rows:  list[dict],   # [{date, buy, sell}] asc, may have None buy/sell
    ihsg_mom_score: float | None,
) -> tuple[float | None, str, dict]:
    """
    Retail conviction = participation_ratio × market_direction.

    participation_ratio:
      MODE A (preferred): dom_share / MA20(dom_share)
        dom_share = dom_total / (dom_total + foreign_total)
      MODE B (fallback):  dom_total / MA20(dom_total)

    market_direction = (ihsg_mom_score - 50) / 50  →  [-1, +1]

    Returns (score_0_100, label, detail_dict).
    """
    if not domestic_rows:
        return None, "No domestic data", {}

    if ihsg_mom_score is None:
        return None, "No IHSG momentum data", {}

    # Build participation series
    # Try MODE A first: need matching foreign_total for each domestic date
    foreign_by_date: dict[str, float] = {}
    for ff in foreign_rows:
        if ff.get("buy") is not None and ff.get("sell") is not None:
            foreign_by_date[str(ff["date"])] = ff["buy"] + ff["sell"]

    # Align domestic rows with available foreign totals
    dom_totals  : list[float] = []
    dom_shares  : list[float] = []   # dom / (dom + foreign)  — MODE A
    uses_mode_a : bool        = False

    for dr in domestic_rows:
        d_total  = dr["buy"] + dr["sell"]
        date_str = str(dr["date"])
        if date_str in foreign_by_date:
            f_total = foreign_by_date[date_str]
            market_total = d_total + f_total
            if market_total > 0:
                dom_shares.append(d_total / market_total)
        dom_totals.append(d_total)

    # Decide which mode to use: MODE A if at least 2 dom_share data points
    if len(dom_shares) >= 2:
        uses_mode_a = True
        series = dom_shares
    else:
        series = dom_totals

    # Today's values
    today_dr    = domestic_rows[-1]
    today_total = today_dr["buy"] + today_dr["sell"]
    today_str   = str(today_dr["date"])
    today_foreign_total: float | None = foreign_by_date.get(today_str)

    if uses_mode_a and today_foreign_total is not None:
        market_total  = today_total + today_foreign_total
        today_value   = today_total / market_total if market_total > 0 else 0.0
    else:
        today_value   = today_total

    # MA of the series (up to PARTICIPATION_MA days including today)
    ma_win    = min(PARTICIPATION_MA, len(series))
    ma_series = sum(series[-ma_win:]) / ma_win if ma_win > 0 else None

    if not ma_series:
        return None, "Participation MA unavailable", {}

    participation_ratio = today_value / ma_series if ma_series > 0 else 1.0

    # Market direction from IHSG momentum score
    market_direction = (ihsg_mom_score - 50.0) / 50.0   # [-1, +1]

    # Conviction signal and score
    conviction_signal = market_direction * participation_ratio
    conviction_score  = min(100.0, max(0.0, 50.0 + conviction_signal * 25.0))

    # Build label
    mode_label = "pasar total" if uses_mode_a else "volume sendiri"
    dir_str    = "↑ naik" if market_direction > 0.05 else ("↓ turun" if market_direction < -0.05 else "= flat")
    label = (
        f"IHSG {dir_str} × partisipasi {participation_ratio:.2f}× ({mode_label}) "
        f"→ skor {conviction_score:.0f}"
    )

    detail = {
        "retail_conviction_score":      round(conviction_score, 1),
        "retail_participation_ratio":   round(participation_ratio, 4),
        "retail_participation_score":   round(conviction_score, 1),   # legacy alias
        "market_direction_score":       round(ihsg_mom_score, 1),
        "domestic_total_bn":            round(today_total, 2),
        "domestic_ma20_bn":             round(ma_series, 2),
        "foreign_total_bn":             round(today_foreign_total, 2) if today_foreign_total else None,
        "dom_market_share":             round(today_value, 6) if uses_mode_a else None,
        "participation_uses_total_market": uses_mode_a,
        "days_of_retail_data":          len(domestic_rows),
        # Kept for UI compat but no longer used as direction signal
        "domestic_net_bn":              round(today_dr["buy"] - today_dr["sell"], 2),
        "retail_direction":             None,   # retired — was domestic net sign, now irrelevant
    }

    return round(conviction_score, 1), label, detail


# ── Label ──────────────────────────────────────────────────────────────────────

def classify(score: float | None) -> str:
    if score is None: return "Data Tidak Cukup"
    if score < 25:    return "Extreme Fear"
    if score < 45:    return "Fear"
    if score < 55:    return "Neutral"
    if score < 75:    return "Greed"
    return "Extreme Greed"


# ── Main ───────────────────────────────────────────────────────────────────────

async def run() -> None:
    conn = await get_conn()
    today = datetime.now(timezone.utc).date()

    try:
        # ── Fetch IHSG history ────────────────────────────────────────────────
        ihsg_bars = await conn.fetch(
            "SELECT date, close FROM ihsg_daily ORDER BY date ASC"
        )
        ihsg_bars = [{"date": r["date"], "close": float(r["close"])} for r in ihsg_bars]

        # ── Fetch domestic flow history ───────────────────────────────────────
        dom_rows = await conn.fetch(
            "SELECT date, buy_value_bn, sell_value_bn "
            "FROM domestic_flow_daily ORDER BY date ASC"
        )
        domestic_rows = [
            {"date": r["date"], "buy": float(r["buy_value_bn"]), "sell": float(r["sell_value_bn"])}
            for r in dom_rows
        ]

        if not domestic_rows:
            print("\n[Domestic Score] No domestic data yet — nothing to compute.")
            print("  Enter data: python -m backend.scripts.set_domestic_flow --buy N --sell M")
            return

        has_retail   = True
        days_of_retail = len(domestic_rows)

        # ── Fetch foreign flow (for total-market participation) ───────────────
        ff_rows = await conn.fetch(
            "SELECT date, buy_idr_billions, sell_idr_billions "
            "FROM foreign_flow_daily ORDER BY date ASC"
        )
        foreign_rows = [
            {
                "date": r["date"],
                "buy":  float(r["buy_idr_billions"])  if r["buy_idr_billions"]  is not None else None,
                "sell": float(r["sell_idr_billions"]) if r["sell_idr_billions"] is not None else None,
            }
            for r in ff_rows
        ]

        # ── Compute IHSG momentum (used by both conviction and as-is) ─────────
        mom_score, mom_label = compute_ihsg_momentum(ihsg_bars)

        # ── Compute volatility context ────────────────────────────────────────
        vol_score, vol_label = compute_ihsg_volatility(ihsg_bars)

        # ── Compute retail conviction ─────────────────────────────────────────
        conv_score, conv_label, conv_detail = compute_retail_conviction(
            domestic_rows, foreign_rows, mom_score
        )

        # ── Aggregate with fixed weights (renormalize if component missing) ───
        active = []
        if conv_score is not None: active.append(("retail_conviction", W_CONVICTION, conv_score, conv_label))
        if vol_score  is not None: active.append(("volatility",        W_VOLATILITY, vol_score,  vol_label))

        total_w   = sum(w for _, w, _, _ in active)
        raw_score = round(sum(w / total_w * s for _, w, s, _ in active), 1) if total_w > 0 else None

        # ── EMA smoothing (over previous domestic rows) ───────────────────────
        prev_row = await conn.fetchrow(
            "SELECT smoothed_score FROM fear_greed_psychology "
            "WHERE date < $1 ORDER BY date DESC LIMIT 1",
            today,
        )
        prev_smoothed = float(prev_row["smoothed_score"]) if prev_row and prev_row["smoothed_score"] else None

        if raw_score is not None:
            smoothed = (
                round(EMA_ALPHA * raw_score + (1 - EMA_ALPHA) * prev_smoothed, 1)
                if prev_smoothed is not None else raw_score
            )
        else:
            smoothed = prev_smoothed

        label = classify(smoothed)

        # ── Build components_json ─────────────────────────────────────────────
        comp_list = []
        for name, w, s, lbl in active:
            comp_list.append({"id": name, "weight": w, "score": s, "raw_label": lbl})
        if conv_score is None:
            comp_list.append({"id": "retail_conviction", "weight": W_CONVICTION, "score": None,
                              "note": "Belum ada data domestik"})
        if vol_score is None:
            comp_list.append({"id": "volatility", "weight": W_VOLATILITY, "score": None,
                              "note": "Insufficient IHSG history"})

        # ── Upsert to fear_greed_psychology ───────────────────────────────────
        await conn.execute("""
            INSERT INTO fear_greed_psychology (
              date, score, raw_score, smoothed_score, label,
              active_components, components_json,
              retail_participation_score, retail_participation_ratio,
              retail_direction, domestic_net_bn, domestic_total_bn, domestic_ma20_bn,
              has_retail_data, days_of_retail_data,
              foreign_total_bn, dom_market_share, participation_uses_total_market,
              market_direction_score, retail_conviction_score,
              updated_at
            ) VALUES (
              $1, $2, $3, $4, $5, $6, $7,
              $8, $9, $10, $11, $12, $13,
              $14, $15,
              $16, $17, $18,
              $19, $20,
              NOW()
            )
            ON CONFLICT (date) DO UPDATE SET
              score                       = EXCLUDED.score,
              raw_score                   = EXCLUDED.raw_score,
              smoothed_score              = EXCLUDED.smoothed_score,
              label                       = EXCLUDED.label,
              active_components           = EXCLUDED.active_components,
              components_json             = EXCLUDED.components_json,
              retail_participation_score  = EXCLUDED.retail_participation_score,
              retail_participation_ratio  = EXCLUDED.retail_participation_ratio,
              retail_direction            = EXCLUDED.retail_direction,
              domestic_net_bn             = EXCLUDED.domestic_net_bn,
              domestic_total_bn           = EXCLUDED.domestic_total_bn,
              domestic_ma20_bn            = EXCLUDED.domestic_ma20_bn,
              has_retail_data             = EXCLUDED.has_retail_data,
              days_of_retail_data         = EXCLUDED.days_of_retail_data,
              foreign_total_bn            = EXCLUDED.foreign_total_bn,
              dom_market_share            = EXCLUDED.dom_market_share,
              participation_uses_total_market = EXCLUDED.participation_uses_total_market,
              market_direction_score      = EXCLUDED.market_direction_score,
              retail_conviction_score     = EXCLUDED.retail_conviction_score,
              updated_at                  = NOW()
        """,
            today, smoothed, raw_score, smoothed, label,
            len(active), json.dumps(comp_list),
            # retail detail
            conv_detail.get("retail_participation_score"),
            conv_detail.get("retail_participation_ratio"),
            conv_detail.get("retail_direction"),
            conv_detail.get("domestic_net_bn"),
            conv_detail.get("domestic_total_bn"),
            conv_detail.get("domestic_ma20_bn"),
            has_retail, days_of_retail,
            # new columns
            conv_detail.get("foreign_total_bn"),
            conv_detail.get("dom_market_share"),
            conv_detail.get("participation_uses_total_market", False),
            conv_detail.get("market_direction_score"),
            conv_detail.get("retail_conviction_score"),
        )

        # ── Print report ──────────────────────────────────────────────────────
        uses_total = conv_detail.get("participation_uses_total_market", False)
        mode_str   = "MODE A (market share)" if uses_total else "MODE B (volume self-normalized)"
        print(f"\n{'='*62}")
        print(f"  IDX Sentimen Domestik (Domestic Score)")
        print(f"{'='*62}")
        print(f"  Participation mode  : {mode_str}")
        print(f"  IHSG momentum score : {mom_score} / 100")
        print(f"  Raw score           : {raw_score} / 100")
        print(f"  Smoothed score      : {smoothed} / 100")
        print(f"  Label               : {label}")
        print(f"  Active components   : {len(active)}/2")
        print(f"  Domestic data days  : {days_of_retail}")
        print()
        for name, w, s, lbl in active:
            wt = int(w * 100)
            print(f"  [OK] {name:<22} ({wt:2d}%)  {s:>5.1f}")
            if lbl: print(f"        {lbl}")
        print(f"\n  *** fear_greed_index (Foreign Score / Index A) NOT TOUCHED ***")
        print(f"{'='*62}\n")

    finally:
        await conn.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()

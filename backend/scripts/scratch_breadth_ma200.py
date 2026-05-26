#!/usr/bin/env python3
"""
SCRATCH EXPERIMENT: % above MA200 breadth measure.

Tests whether LQ45 % above MA200 improves the IDX F&G index without
breaking the Dec 24 2025 validation (must stay ≥ 75 Extreme Greed).

Does NOT write to fear_greed_index. Results go to stdout only.

Usage:
    python -m backend.scripts.scratch_breadth_ma200
"""
import asyncio
import math
import sys
sys.stdout.reconfigure(encoding="utf-8")
from datetime import date as Date

from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env.local", override=True)

from backend.workers._db import get_conn


# ── Config ────────────────────────────────────────────────────────────────────

EMA_ALPHA          = 0.7
MA200_WIN          = 200
MOM_MA_WIN         = 125
BACKTEST_START     = Date(2025, 8, 1)

# Nominal breadth weight: 0.14 → effective ~16.7% when renormalized
# with the 4 active components (nominal sum = 0.70)
W_MOM    = 0.20
W_VOL    = 0.15
W_FF     = 0.20
W_RUP    = 0.15
W_BREAD  = 0.14   # tune this constant

VALIDATION = {
    Date(2025, 12, 24): (76.1, "Extreme Greed", "DEC24 ATH — MUST stay ≥75"),
    Date(2026,  1, 28): (45.7, "Neutral",        "Jan28 correction"),
    Date(2026,  3,  9): (35.5, "Fear",            "Mar9 low"),
    Date(2026,  5, 23): (21.9, "Extreme Fear",    "May23 recent"),
}

REGIME_SAMPLES = [
    (Date(2025,  9,  1), "Sep 2025 — early bull"),
    (Date(2025, 10,  1), "Oct 2025 — bull mid"),
    (Date(2025, 11,  1), "Nov 2025 — bull late"),
    (Date(2025, 12, 24), "Dec 24   — ATH (VALIDATION)"),
    (Date(2026,  2,  1), "Feb 2026 — cooling"),
    (Date(2026,  4,  7), "Apr 2026 — tariff shock"),
    (Date(2026,  5, 23), "May 23   — recent low"),
]


# ── Math (identical to compute_index.py) ──────────────────────────────────────

def pct_rank(val: float, hist: list[float]) -> float:
    if not hist:
        return 50.0
    return sum(1 for h in hist if h < val) / len(hist) * 100.0


def roll_mean(arr: list[float], end: int, w: int) -> float | None:
    if end < w - 1:
        return None
    return sum(arr[end - w + 1 : end + 1]) / w


def roll_std(arr: list[float], end: int, w: int) -> float | None:
    if end < w - 1:
        return None
    sl = arr[end - w + 1 : end + 1]
    m  = sum(sl) / len(sl)
    return math.sqrt(sum((v - m) ** 2 for v in sl) / len(sl))


def score_momentum(closes: list[float]) -> float | None:
    if len(closes) < MOM_MA_WIN + 5:
        return None
    devs = []
    for i in range(MOM_MA_WIN - 1, len(closes)):
        ma = roll_mean(closes, i, MOM_MA_WIN)
        if ma:
            devs.append(closes[i] / ma - 1)
    return pct_rank(devs[-1], devs[:-1]) if len(devs) >= 2 else None


def score_volatility(closes: list[float]) -> float | None:
    if len(closes) < 40:
        return None
    lrs = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
    vols = []
    for i in range(19, len(lrs)):
        sd = roll_std(lrs, i, 20)
        if sd is not None:
            vols.append(sd * math.sqrt(252))
    return (100.0 - pct_rank(vols[-1], vols[:-1])) if len(vols) >= 2 else None


def score_rupiah(closes: list[float]) -> float | None:
    if len(closes) < 51:
        return None
    devs = []
    for i in range(49, len(closes)):
        ma = roll_mean(closes, i, 50)
        if ma:
            devs.append(closes[i] / ma - 1)
    return (100.0 - pct_rank(devs[-1], devs[:-1])) if len(devs) >= 2 else None


def score_foreign_flow(nets: list[float]) -> float | None:
    if len(nets) < 2:
        return None
    rolls = [sum(nets[max(0, i - 4) : i + 1]) for i in range(len(nets))]
    return pct_rank(rolls[-1], rolls[:-1])


def blend(score_weight_pairs: list[tuple[float | None, float]]) -> float | None:
    active = [(s, w) for s, w in score_weight_pairs if s is not None]
    if len(active) < 2:
        return None
    tw = sum(w for _, w in active)
    return round(sum(s * w for s, w in active) / tw, 1)


def classify(score: float | None) -> str:
    if score is None:  return "—"
    if score < 25:     return "Extreme Fear"
    if score < 45:     return "Fear"
    if score < 55:     return "Neutral"
    if score < 75:     return "Greed"
    return "Extreme Greed"


# ── Main backtest ──────────────────────────────────────────────────────────────

async def run() -> None:
    conn = await get_conn()
    try:
        ihsg_rows  = await conn.fetch("SELECT date, close FROM ihsg_daily ORDER BY date")
        usd_rows   = await conn.fetch("SELECT date, close FROM usdidr_daily ORDER BY date")
        ff_rows    = await conn.fetch(
            "SELECT date, net_idr_billions FROM foreign_flow_daily "
            "WHERE net_idr_billions IS NOT NULL ORDER BY date"
        )
        stk_rows   = await conn.fetch(
            "SELECT ticker, date, close FROM stock_daily ORDER BY ticker, date"
        )
        stored_rows = await conn.fetch(
            "SELECT date, smoothed_score, raw_score FROM fear_greed_index ORDER BY date"
        )
    finally:
        await conn.close()

    # ── Build lookup structures ───────────────────────────────────────────────

    ihsg_dates  = [r["date"] for r in ihsg_rows]
    ihsg_closes = [float(r["close"]) for r in ihsg_rows]

    usd_dates   = [r["date"] for r in usd_rows]
    usd_closes  = [float(r["close"]) for r in usd_rows]

    ff_by_date  = {r["date"]: float(r["net_idr_billions"]) for r in ff_rows}

    stk_by_ticker: dict[str, list[tuple[Date, float]]] = {}
    for r in stk_rows:
        t = r["ticker"]
        if t not in stk_by_ticker:
            stk_by_ticker[t] = []
        stk_by_ticker[t].append((r["date"], float(r["close"])))

    stored_by_date: dict[Date, tuple[float, float]] = {
        r["date"]: (float(r["smoothed_score"]), float(r["raw_score"]))
        for r in stored_rows
        if r["smoothed_score"] is not None and r["raw_score"] is not None
    }

    # ── Walk-forward simulation ───────────────────────────────────────────────

    results_4: dict[Date, tuple[float | None, float | None]] = {}  # raw, smoothed
    results_5: dict[Date, tuple[float | None, float | None]] = {}

    breadth_raw_by_date: dict[Date, float] = {}   # raw % above MA200 for display
    breadth_pct_series:  list[float]       = []   # growing history for percentile-rank

    prev_sm4: float | None = None
    prev_sm5: float | None = None

    # USD/IDR index pointer (avoid re-scanning from zero each time)
    usd_ptr = 0

    for idx, dt in enumerate(ihsg_dates):
        if dt < BACKTEST_START:
            continue

        # IHSG closes up to today (full history)
        ic = ihsg_closes[: idx + 1]

        # USD/IDR closes up to today
        while usd_ptr < len(usd_dates) - 1 and usd_dates[usd_ptr + 1] <= dt:
            usd_ptr += 1
        uc = usd_closes[: usd_ptr + 1]

        # Foreign flow nets in chronological order up to today
        ff_nets = [ff_by_date[d] for d in sorted(ff_by_date) if d <= dt]

        # ── Breadth: % of LQ45 stocks above MA200 ────────────────────────────
        above = 0
        eligible = 0
        for ticker, series in stk_by_ticker.items():
            tc = [c for d, c in series if d <= dt]
            if len(tc) < MA200_WIN:
                continue
            ma200 = sum(tc[-MA200_WIN:]) / MA200_WIN
            eligible += 1
            if tc[-1] > ma200:
                above += 1

        raw_breadth_pct: float | None = None
        if eligible >= 5:   # require at least 5 stocks with 200d history
            raw_breadth_pct = above / eligible * 100.0
            breadth_raw_by_date[dt] = raw_breadth_pct
            breadth_pct_series.append(raw_breadth_pct)

        s_breadth = (
            pct_rank(breadth_pct_series[-1], breadth_pct_series[:-1])
            if len(breadth_pct_series) >= 2 else None
        )

        # ── Component scores ──────────────────────────────────────────────────
        s_mom = score_momentum(ic)
        s_vol = score_volatility(ic)
        s_rup = score_rupiah(uc)
        s_ff  = score_foreign_flow(ff_nets)

        # 4-component (baseline — should match stored values)
        raw4 = blend([(s_mom, W_MOM), (s_vol, W_VOL), (s_ff, W_FF), (s_rup, W_RUP)])
        if raw4 is not None:
            sm4 = (
                round(EMA_ALPHA * raw4 + (1 - EMA_ALPHA) * prev_sm4, 1)
                if prev_sm4 is not None else raw4
            )
        else:
            sm4 = prev_sm4
        results_4[dt] = (raw4, sm4)
        prev_sm4 = sm4

        # 5-component (with breadth)
        raw5 = blend([(s_mom, W_MOM), (s_vol, W_VOL), (s_ff, W_FF), (s_rup, W_RUP), (s_breadth, W_BREAD)])
        if raw5 is not None:
            sm5 = (
                round(EMA_ALPHA * raw5 + (1 - EMA_ALPHA) * prev_sm5, 1)
                if prev_sm5 is not None else raw5
            )
        else:
            sm5 = prev_sm5
        results_5[dt] = (raw5, sm5)
        prev_sm5 = sm5

    # ── Report ────────────────────────────────────────────────────────────────

    print()
    print("=" * 74)
    print("  BREADTH EXPERIMENT: % of LQ45 Above MA200")
    print("  Scratch only — fear_greed_index NOT TOUCHED")
    print("=" * 74)

    # Stock coverage
    total_tickers = len(stk_by_ticker)
    last_dt = ihsg_dates[-1]
    tickers_at_last = sum(
        1 for s in stk_by_ticker.values()
        if len([c for d, c in s if d <= last_dt]) >= MA200_WIN
    )
    first_breadth_dt = min(breadth_raw_by_date.keys()) if breadth_raw_by_date else None

    print(f"\n  Stock coverage:")
    print(f"    LQ45 tickers in stock_daily   : {total_tickers}")
    print(f"    Tickers with 200d history now  : {tickers_at_last} / {total_tickers}")
    print(f"    First date breadth computable  : {first_breadth_dt}")

    eff_w = W_BREAD / (W_MOM + W_VOL + W_FF + W_RUP + W_BREAD)
    print(f"\n  Component weights (5-comp, renormalized):")
    total_nom = W_MOM + W_VOL + W_FF + W_RUP + W_BREAD
    for name, w in [("IHSG Momentum", W_MOM), ("Volatility", W_VOL),
                    ("Foreign Flow", W_FF), ("Rupiah Stress", W_RUP),
                    ("Breadth MA200", W_BREAD)]:
        print(f"    {name:<20}  nominal {w*100:.0f}%  →  effective {w/total_nom*100:.1f}%")

    # ── Validation checkpoints ────────────────────────────────────────────────
    print(f"\n{'─' * 74}")
    print(f"  VALIDATION CHECKPOINTS")
    print(f"  (4-comp must match stored; Dec24 5-comp must stay ≥ 75)")
    print(f"{'─' * 74}")
    print(f"  {'Date':<12}  {'Stored':>8}  {'4-comp':>8}  {'5-comp':>8}  "
          f"{'Δ (5-4)':>8}  {'Verdict'}")
    print(f"  {'─'*12}  {'─'*8}  {'─'*8}  {'─'*8}  {'─'*8}  {'─'*20}")

    all_pass = True
    for val_date, (exp, exp_label, note) in sorted(VALIDATION.items()):
        stored_sm = stored_by_date.get(val_date, (None, None))[0]
        _, sm4    = results_4.get(val_date, (None, None))
        _, sm5    = results_5.get(val_date, (None, None))
        delta     = round(sm5 - sm4, 1) if sm5 is not None and sm4 is not None else None

        if val_date == Date(2025, 12, 24):
            verdict = ("PASS ≥75 ✓" if sm5 is not None and sm5 >= 75.0
                       else f"FAIL {sm5}<75" if sm5 is not None
                       else "NO DATA")
            if sm5 is None or sm5 < 75.0:
                all_pass = False
        else:
            verdict = classify(sm5)

        sm4_s    = f"{sm4:.1f}"  if sm4    is not None else "—"
        sm5_s    = f"{sm5:.1f}"  if sm5    is not None else "—"
        delta_s  = f"{delta:+.1f}" if delta is not None else "—"
        stored_s = f"{stored_sm:.1f}" if stored_sm is not None else "—"

        print(f"  {val_date}  {stored_s:>8}  {sm4_s:>8}  {sm5_s:>8}  {delta_s:>8}  {verdict}")
        print(f"             ({note})")

    # ── Regime behavior ───────────────────────────────────────────────────────
    print(f"\n{'─' * 74}")
    print(f"  REGIME BEHAVIOR (does it read sensibly across market phases?)")
    print(f"{'─' * 74}")
    print(f"  {'Date':<12}  {'Stored':>8}  {'4-comp':>8}  {'5-comp':>8}  "
          f"{'Brd raw%':>8}  {'Brd score':>9}  Label")
    print(f"  {'─'*12}  {'─'*8}  {'─'*8}  {'─'*8}  {'─'*8}  {'─'*9}")

    # Recompute breadth scores at regime dates for display
    brd_score_by_date: dict[Date, float | None] = {}
    running_pcts: list[float] = []
    for dt in sorted(breadth_raw_by_date.keys()):
        running_pcts.append(breadth_raw_by_date[dt])
        brd_score_by_date[dt] = (
            pct_rank(running_pcts[-1], running_pcts[:-1])
            if len(running_pcts) >= 2 else None
        )

    for reg_date, desc in REGIME_SAMPLES:
        # Nearest IHSG date on or after reg_date
        near = next(
            (d for d in ihsg_dates if d >= reg_date and d >= BACKTEST_START),
            None
        )
        if near is None:
            continue
        stored_sm = stored_by_date.get(near, (None, None))[0]
        _, sm4    = results_4.get(near, (None, None))
        _, sm5    = results_5.get(near, (None, None))
        brd_raw   = breadth_raw_by_date.get(near)
        brd_sc    = brd_score_by_date.get(near)

        stored_s = f"{stored_sm:.1f}" if stored_sm is not None else "—"
        sm4_s    = f"{sm4:.1f}"       if sm4       is not None else "—"
        sm5_s    = f"{sm5:.1f}"       if sm5       is not None else "—"
        brd_r_s  = f"{brd_raw:.0f}%"  if brd_raw   is not None else "—"
        brd_sc_s = f"{brd_sc:.0f}"    if brd_sc    is not None else "—"

        print(f"  {near}  {stored_s:>8}  {sm4_s:>8}  {sm5_s:>8}  "
              f"{brd_r_s:>8}  {brd_sc_s:>9}  {desc}")

    # ── Verdict ───────────────────────────────────────────────────────────────
    print(f"\n{'─' * 74}")
    print(f"  FINAL VERDICT")
    print(f"{'─' * 74}")

    dec24_5 = results_5.get(Date(2025, 12, 24), (None, None))[1]

    if dec24_5 is None:
        print(f"  INCONCLUSIVE — no MA200 data at Dec 24 (insufficient stock history)")
        print(f"  Stock data starts too late to reach 200d MA by Dec 2025.")
        print(f"  Need data from at least Jun 2024 to compute MA200 in Dec 2025.")
        print(f"  => Re-fetch with --range max or load historical prices separately.")
    elif dec24_5 >= 75.0:
        print(f"  CANDIDATE PASS: Dec 24 smoothed = {dec24_5:.1f} ≥ 75 ✓")
        print(f"  => Breadth MA200 preserves the Dec 24 Extreme Greed validation.")
        print(f"  => Review regime table: does it rise in Aug-Dec bull and fall in Apr-May decline?")
        print(f"  => If YES: ready for consideration. If NO: directional accuracy problem.")
    else:
        print(f"  FAIL: Dec 24 smoothed = {dec24_5:.1f} < 75 — breaks Extreme Greed")
        print(f"  => Same cap-weighting problem as 52-week H/L version.")
        print(f"  => Skip MA200 breadth. Index stays at 4 validated components. FINAL.")

    print(f"\n  Bonds: FRED has Indonesia 10Y (IRLTLT01IDM156N) — monthly only.")
    print(f"  World Bank / BI: quarterly/annual only. No free daily source.")
    print(f"  => Safe Haven component: DROPPED PERMANENTLY.")
    print("=" * 74)
    print()


if __name__ == "__main__":
    asyncio.run(run())

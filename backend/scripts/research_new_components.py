"""
Research script for F&G component expansion.

Phase 1: Fetch LQ45 basket data from Yahoo Finance (.JK)
Phase 2: Probe Indonesian 10Y govt bond yield sources
Phase 3: Investigate Put/Call and junk bond data (confirm skip)
Phase 4: Compute Stock Price Strength component backtest Aug 2025-present

Run from project root:
    python -m backend.scripts.research_new_components
"""
import sys, math, time
sys.stdout.reconfigure(encoding="utf-8")
from datetime import date, timedelta
import yfinance as yf
import asyncio, asyncpg, os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(".env"))
load_dotenv(Path(".env.local"), override=True)

# ── LQ45 constituents (Feb-Jul 2026 period) ──────────────────────────────────
# Source: BEI official LQ45 list; .JK suffix for Yahoo Finance
LQ45_TICKERS = [
    "AALI", "ACES", "ADRO", "AKRA", "AMRT", "ANTM", "ASII",
    "BBCA", "BBNI", "BBRI", "BMRI", "BREN", "BRPT", "BSDE",
    "CPIN", "CTRA", "EMTK", "EXCL", "GOTO", "HEAL",
    "HMSP", "ICBP", "INCO", "INKP", "INTP", "ISAT", "ITMG",
    "JSMR", "JPFA", "KLBF", "MAPI", "MBMA", "MDKA", "MEDC", "MIKA",
    "MNCN", "MTEL", "PGEO", "PTBA", "SMGR", "SIDO", "TBIG",
    "TKIM", "TLKM", "TOWR", "TPIA", "UNTR", "UNVR",
]

# Need 52w window before Aug 2025 — fetch from June 2024
FETCH_START = "2024-06-01"
FETCH_END   = date.today().isoformat()

# Bond yield candidates on Yahoo Finance
BOND_TICKERS = {
    "GIDN10Y=X":     "IDR govt 10Y (Yahoo code 1)",
    "^IRUI10Y":      "IDR 10Y variant",
    "INDOGB10Y=X":   "IndoGB 10Y",
    "IDO10Y=X":      "IDR 10Y bond",
    "^INDOGB10":     "IndoGB variant",
    "IEF":           "US 7-10Y Treasury ETF (proxy check)",
    "EM-IDR=X":      "EM IDR",
}

def pct_rank(value, history):
    if not history:
        return 50.0
    below = sum(1 for h in history if h < value)
    return (below / len(history)) * 100.0


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1: Fetch LQ45 data
# ─────────────────────────────────────────────────────────────────────────────
print("=" * 70)
print("PHASE 1: Fetching LQ45 basket from Yahoo Finance (.JK)")
print(f"         {FETCH_START} -> {FETCH_END}  ({len(LQ45_TICKERS)} tickers)")
print("=" * 70)

success = {}   # ticker -> pd.Series of closes indexed by date
failed  = []

# Download in batches of 10 to avoid rate limits
BATCH = 10
for i in range(0, len(LQ45_TICKERS), BATCH):
    batch = LQ45_TICKERS[i: i + BATCH]
    yf_tickers = [f"{t}.JK" for t in batch]
    try:
        raw = yf.download(
            tickers=yf_tickers,
            start=FETCH_START,
            end=FETCH_END,
            auto_adjust=True,
            progress=False,
            threads=False,   # sequential — gentler on rate limits
        )
        # raw["Close"] is a DataFrame if multiple tickers, Series if single
        close_df = raw["Close"] if "Close" in raw.columns else raw.xs("Close", axis=1, level=0)
        for t, yt in zip(batch, yf_tickers):
            col = yt if yt in close_df.columns else (t if t in close_df.columns else None)
            if col is None:
                failed.append(t)
                continue
            s = close_df[col].dropna()
            if len(s) < 100:
                print(f"  {t:8s}: too few rows ({len(s)}) — skip")
                failed.append(t)
            else:
                success[t] = s
                print(f"  {t:8s}: {len(s)} rows  {s.index[0].date()} -> {s.index[-1].date()}")
    except Exception as ex:
        print(f"  Batch {batch}: ERROR — {ex}")
        failed.extend(batch)

    time.sleep(0.5)  # gentle pacing

print(f"\nResult: {len(success)} tickers OK, {len(failed)} failed")
if failed:
    print(f"  Failed: {failed}")

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2: Probe Indonesian bond yield sources
# ─────────────────────────────────────────────────────────────────────────────
print()
print("=" * 70)
print("PHASE 2: Probing Indonesian 10Y govt bond yield sources")
print("=" * 70)

bond_results = {}
for ticker, desc in BOND_TICKERS.items():
    try:
        raw = yf.download(
            tickers=ticker,
            start="2025-01-01",
            end=FETCH_END,
            auto_adjust=True,
            progress=False,
            threads=False,
        )
        if raw.empty:
            print(f"  {ticker:20s} [{desc}]: NO DATA")
            bond_results[ticker] = None
        else:
            close = raw["Close"].dropna() if "Close" in raw.columns else raw.iloc[:, 0].dropna()
            n = len(close)
            if n > 0:
                v_first = float(close.iloc[0])
                v_last  = float(close.iloc[-1])
                print(f"  {ticker:20s} [{desc}]: {n} rows  first={v_first:.4f}  last={v_last:.4f}")
                bond_results[ticker] = close
            else:
                print(f"  {ticker:20s} [{desc}]: empty after dropna")
                bond_results[ticker] = None
    except Exception as ex:
        print(f"  {ticker:20s} [{desc}]: ERROR — {ex}")
        bond_results[ticker] = None
    time.sleep(0.3)

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 3: Confirm Put/Call + junk bond are not viable
# ─────────────────────────────────────────────────────────────────────────────
print()
print("=" * 70)
print("PHASE 3: Put/Call + Junk bond viability (IDX)")
print("=" * 70)
print("""
  PUT/CALL RATIO:
  IDX does operate an options market (KOS/PUT warrants), but daily open
  interest and volume data are not available through any free public API.
  BEI publishes monthly summaries only; no daily time-series via Yahoo or
  other free feeds. Options volume is also extremely thin vs NYSE.
  VERDICT: SKIP — no reliable free daily data.

  JUNK BOND SPREAD (HY vs IG):
  Indonesia's corporate bond market (BEI Fixed Income) is small and
  illiquid. There is no free IDX HY index equivalent to ICE BofA US HY.
  CEIC and Bloomberg carry INDOGB sovereign curve data but no HY spread.
  Indonesian corporate bond prices are not quoted daily in free data.
  VERDICT: SKIP — no clean free source.
""")

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 4: Compute Stock Price Strength component backtest
# ─────────────────────────────────────────────────────────────────────────────
print()
print("=" * 70)
print("PHASE 4: Stock Price Strength (52-week H/L) — component backtest")
print("=" * 70)

if len(success) < 5:
    print("Too few tickers succeeded — cannot compute meaningful component.")
    sys.exit(1)

# Build per-date close price dict: date -> {ticker: close}
import pandas as pd
basket_tickers = sorted(success.keys())
print(f"Basket size: {len(basket_tickers)} tickers")
print(f"Tickers: {basket_tickers}")

# Combine into a DataFrame aligned by date
dfs = []
for t in basket_tickers:
    s = success[t].copy()
    s.name = t
    dfs.append(s)

combined = pd.concat(dfs, axis=1)
combined.index = pd.to_datetime(combined.index).date  # normalize to date objects

# We need 252 trading days of history before we can compute 52w window
# Compute the component for every date with enough history (252+ rows)
WIN_52W = 252
NEAR_PCT = 0.02  # within 2% of 52w high/low

component_series = {}  # date -> {raw_ratio, score_pct_ranked, highs, lows, n}

all_dates = sorted(combined.index)
closes_arr = {}  # ticker -> list of (date, close) sorted by date
for t in basket_tickers:
    closes_arr[t] = [(d, float(combined.loc[d, t])) for d in all_dates if not pd.isna(combined.loc[d, t])]

# For each date, compute the ratio
for idx, d in enumerate(all_dates):
    if idx < WIN_52W:
        continue  # not enough history yet

    window_dates = all_dates[idx - WIN_52W: idx + 1]  # 52-week window including today
    w_start = window_dates[0]
    w_end   = d

    highs_count = 0
    lows_count  = 0
    n_valid     = 0

    for t in basket_tickers:
        # Get window closes for this ticker
        w_closes = [c for dt, c in closes_arr[t] if w_start <= dt <= w_end]
        if len(w_closes) < 20:  # need enough data points
            continue
        high_52 = max(w_closes)
        low_52  = min(w_closes)
        today_close = dict(closes_arr[t]).get(d)
        if today_close is None:
            continue

        n_valid += 1
        if today_close >= (1 - NEAR_PCT) * high_52:
            highs_count += 1
        if today_close <= (1 + NEAR_PCT) * low_52:
            lows_count += 1

    if n_valid < 3:
        continue

    raw_ratio = highs_count / (highs_count + lows_count + 0.5)  # 0-1, add 0.5 to smooth 0/0
    component_series[d] = {
        "raw_ratio": raw_ratio,
        "highs": highs_count,
        "lows":  lows_count,
        "n":     n_valid,
    }

print(f"\nComponent computed for {len(component_series)} dates")
if not component_series:
    print("No dates computed — check data.")
    sys.exit(1)

# Percentile-rank the raw_ratio across history for a 0-100 score
sorted_comp_dates = sorted(component_series.keys())
ratios_so_far = []
for d in sorted_comp_dates:
    r = component_series[d]["raw_ratio"]
    score = pct_rank(r, ratios_so_far)
    component_series[d]["score"] = score
    ratios_so_far.append(r)

# ── Report backtest behavior at key dates ─────────────────────────────────────
print()
KEY_DATES = {
    date(2025, 8, 1):  "Aug 01 (bull start)",
    date(2025, 9, 1):  "Sep 01",
    date(2025, 10, 1): "Oct 01",
    date(2025, 11, 3): "Nov 03",
    date(2025, 12, 1): "Dec 01",
    date(2025, 12, 24):"Dec 24 (IHSG ATH)",
    date(2026, 1, 2):  "Jan 02",
    date(2026, 1, 28): "Jan 28 (sell-off)",
    date(2026, 2, 25): "Feb 25",
    date(2026, 3, 9):  "Mar 09 (Fear)",
    date(2026, 4, 7):  "Apr 07",
    date(2026, 5, 20): "May 20",
    date(2026, 5, 23): "May 23 (Ext.Fear)",
}

print(f"  {'Date':<12}  {'Highs':>5}  {'Lows':>5}  {'N':>4}  {'Ratio':>6}  {'Score':>6}  Note")
print("  " + "-" * 65)
for kd, note in sorted(KEY_DATES.items()):
    # Find closest available date
    candidates = [d for d in sorted_comp_dates if d >= kd]
    if not candidates:
        candidates = [d for d in sorted_comp_dates if d <= kd]
    if not candidates:
        print(f"  {kd}  NO DATA")
        continue
    closest = min(candidates, key=lambda d: abs((d - kd).days))
    c = component_series[closest]
    score = c["score"]
    label = "Extreme Greed" if score >= 75 else "Greed" if score >= 55 else "Neutral" if score >= 45 else "Fear" if score >= 25 else "Extreme Fear"
    star = " **" if abs((closest - kd).days) > 3 else ""
    print(f"  {closest}  {c['highs']:>5}  {c['lows']:>5}  {c['n']:>4}  {c['raw_ratio']:>6.3f}  {score:>6.1f}  {label} — {note}{star}")

# ── Monthly summary ────────────────────────────────────────────────────────────
print()
print(f"  Monthly averages of Stock Price Strength score:")
print(f"  {'Month':<10}  {'Avg Score':>10}  {'Min':>6}  {'Max':>6}  Label")
print("  " + "-" * 50)
months_seen = set()
for d in sorted_comp_dates:
    ym = (d.year, d.month)
    months_seen.add(ym)

for ym in sorted(months_seen):
    y, m = ym
    month_scores = [component_series[d]["score"] for d in sorted_comp_dates if d.year == y and d.month == m]
    if not month_scores:
        continue
    avg = sum(month_scores) / len(month_scores)
    label = "Extreme Greed" if avg >= 75 else "Greed" if avg >= 55 else "Neutral" if avg >= 45 else "Fear" if avg >= 25 else "Extreme Fear"
    print(f"  {y}-{m:02d}      {avg:>10.1f}  {min(month_scores):>6.1f}  {max(month_scores):>6.1f}  {label}")

# Save component series to a JSON for the next script
import json
save_data = {
    d.isoformat(): {
        "highs": v["highs"], "lows": v["lows"], "n": v["n"],
        "raw_ratio": v["raw_ratio"], "score": v["score"]
    }
    for d, v in component_series.items()
}
out_path = Path("backend/scripts/_stock_strength_cache.json")
with open(out_path, "w") as f:
    json.dump(save_data, f)
print(f"\nCache saved: {out_path}  ({len(save_data)} dates)")
print("\nDONE.")

"""
Before/After backtest comparison: add Stock Price Strength component.

Tests THREE approaches side-by-side:
  A = current validated index (4 components: MOM, VOL, RUP, FF)
  B = + Stock Strength via percentile-rank of H/L ratio
  C = + Stock Strength via raw ratio x 100 (no percentile rank — simpler)

Run from project root:
    python -m backend.scripts.backtest_expanded
"""
import asyncio, asyncpg, os, sys, math, json
sys.stdout.reconfigure(encoding="utf-8")
from datetime import date
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(".env"))
load_dotenv(Path(".env.local"), override=True)

EMA_ALPHA   = 0.7
ROLL_WIN_FF = 5
W_MOM = 0.25
W_VOL = 0.20
W_RUP = 0.20
W_FF  = 0.20
W_STR = 0.20   # stock price strength (when added)

def pct_rank(value, history):
    if not history: return 50.0
    return sum(1 for h in history if h < value) / len(history) * 100.0

def compute_momentum(prices):
    if len(prices) < 126: return None
    ratios = []
    for i in range(124, len(prices)):
        ma125 = sum(prices[i-124:i+1]) / 125
        ma30  = sum(prices[i-29:i+1]) / 30
        ratios.append(ma30 / ma125)
    if len(ratios) < 2: return None
    return pct_rank(ratios[-1], ratios[:-1])

def compute_volatility(prices):
    if len(prices) < 21: return None
    vols = []
    for i in range(20, len(prices)):
        w = prices[i-20:i+1]
        lr = [math.log(w[j]/w[j-1]) for j in range(1, len(w))]
        mr = sum(lr)/len(lr)
        vols.append(math.sqrt(sum((r-mr)**2 for r in lr)/len(lr)) * math.sqrt(252))
    if len(vols) < 2: return None
    return 100.0 - pct_rank(vols[-1], vols[:-1])

def compute_rupiah(rates):
    if len(rates) < 21: return None
    changes = [(rates[i]-rates[i-20])/rates[i-20]*100 for i in range(20, len(rates))]
    if len(changes) < 2: return None
    return 100.0 - pct_rank(changes[-1], changes[:-1])

def compute_ff(nets, wlo, whi):
    if len(nets) < 2: return None
    sums = [sum(nets[max(0,i-ROLL_WIN_FF+1):i+1]) for i in range(len(nets))]
    sw   = [max(wlo, min(whi, s)) for s in sums]
    return pct_rank(sw[-1], sw[:-1])

def weighted_avg(comps_w_scores):
    tw = sum(w for w, s in comps_w_scores)
    if tw == 0: return None
    return sum(w/tw * s for w, s in comps_w_scores)

def label(s):
    if s is None: return "N/A"
    if s >= 75: return "Extreme Greed"
    if s >= 55: return "Greed"
    if s >= 45: return "Neutral"
    if s >= 25: return "Fear"
    return "Extreme Fear"


async def main():
    # ── Load stock strength cache ─────────────────────────────────────────────
    cache_path = Path("backend/scripts/_stock_strength_cache.json")
    if not cache_path.exists():
        print("ERROR: Run research_new_components.py first to generate the cache.")
        return
    with open(cache_path) as f:
        raw_cache = json.load(f)
    strength_by_date = {
        date.fromisoformat(k): v for k, v in raw_cache.items()
    }
    print(f"Stock strength cache: {len(strength_by_date)} dates  "
          f"({min(strength_by_date)} -> {max(strength_by_date)})")

    # ── Load market data ──────────────────────────────────────────────────────
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        ihsg_rows = await conn.fetch("SELECT date, close FROM ihsg_daily ORDER BY date ASC")
        usd_rows  = await conn.fetch("SELECT date, close FROM usdidr_daily ORDER BY date ASC")
        ff_rows   = await conn.fetch(
            "SELECT date, net_idr_billions FROM foreign_flow_daily "
            "WHERE net_idr_billions IS NOT NULL ORDER BY date ASC"
        )
        existing  = await conn.fetch(
            "SELECT date, smoothed_score, raw_score, label, components_json "
            "FROM fear_greed_index ORDER BY date ASC"
        )
    finally:
        await conn.close()

    ihsg_by_date = {r["date"]: float(r["close"]) for r in ihsg_rows}
    usd_by_date  = {r["date"]: float(r["close"]) for r in usd_rows}
    ff_by_date   = {r["date"]: float(r["net_idr_billions"]) for r in ff_rows}
    ihsg_dates   = [r["date"] for r in ihsg_rows]
    usd_dates    = [r["date"] for r in usd_rows]
    ff_dates     = [r["date"] for r in ff_rows]

    # FF winsorisation from full dataset
    all_nets = [ff_by_date[d] for d in ff_dates]
    all_sums = [sum(all_nets[max(0,i-ROLL_WIN_FF+1):i+1]) for i in range(len(all_nets))]
    ss = sorted(all_sums)
    n  = len(ss)
    wlo = ss[max(0, int(n*0.05))]
    whi = ss[min(n-1, int(n*0.95))]

    # Stored ("before") scores
    stored = {r["date"]: float(r["smoothed_score"]) for r in existing if r["smoothed_score"] is not None}

    # ── Run backtest for all IHSG trading days ────────────────────────────────
    backfill_start = date(2025, 8, 1)
    target_dates = [d for d in ihsg_dates if d >= backfill_start and d in strength_by_date]

    records_a = []  # current 4-component
    records_b = []  # + strength pct-ranked
    records_c = []  # + strength raw ratio

    for d in target_dates:
        ihsg_seq = [ihsg_by_date[dt] for dt in ihsg_dates if dt <= d]
        usd_seq  = [usd_by_date[dt]  for dt in usd_dates  if dt <= d]
        ff_seq   = [ff_by_date[dt]   for dt in ff_dates   if dt <= d]

        mom = compute_momentum(ihsg_seq)
        vol = compute_volatility(ihsg_seq)
        rup = compute_rupiah(usd_seq)
        ff  = compute_ff(ff_seq, wlo, whi)

        # strength scores from cache
        sc = strength_by_date.get(d)
        str_pct = sc["score"]         if sc else None   # percentile-ranked
        str_raw = sc["raw_ratio"]*100 if sc else None   # raw ratio x100

        def build_comps(include_strength_pct=False, include_strength_raw=False):
            comps = []
            if mom is not None: comps.append((W_MOM, mom))
            if vol is not None: comps.append((W_VOL, vol))
            if rup is not None: comps.append((W_RUP, rup))
            if ff  is not None: comps.append((W_FF,  ff))
            if include_strength_pct and str_pct is not None:
                comps.append((W_STR, str_pct))
            if include_strength_raw and str_raw is not None:
                comps.append((W_STR, str_raw))
            return comps

        ra = weighted_avg(build_comps())
        rb = weighted_avg(build_comps(include_strength_pct=True))
        rc = weighted_avg(build_comps(include_strength_raw=True))

        if ra is not None: records_a.append({"date": d, "raw": round(ra, 2)})
        if rb is not None: records_b.append({"date": d, "raw": round(rb, 2)})
        if rc is not None: records_c.append({"date": d, "raw": round(rc, 2)})

    # ── Apply EMA ─────────────────────────────────────────────────────────────
    def apply_ema(records, seed=None):
        records.sort(key=lambda r: r["date"])
        s = seed
        for r in records:
            s = EMA_ALPHA * r["raw"] + (1-EMA_ALPHA)*s if s is not None else r["raw"]
            r["smooth"] = round(s, 2)
        return records

    # EMA seed from stored (the last computed smoothed before Aug 2025)
    pre_seed = None
    for r in existing:
        if r["date"] < backfill_start and r["smoothed_score"] is not None:
            pre_seed = float(r["smoothed_score"])

    records_a = apply_ema(records_a, pre_seed)
    records_b = apply_ema(records_b, pre_seed)
    records_c = apply_ema(records_c, pre_seed)

    by_date_a = {r["date"]: r for r in records_a}
    by_date_b = {r["date"]: r for r in records_b}
    by_date_c = {r["date"]: r for r in records_c}

    # ── KEY CHECKPOINT COMPARISON ─────────────────────────────────────────────
    CHECKPOINTS = [
        (date(2025, 8, 1),  "Aug 01 (bull start)"),
        (date(2025, 9, 1),  "Sep 01"),
        (date(2025, 10, 1), "Oct 01"),
        (date(2025, 11, 3), "Nov 03"),
        (date(2025, 12, 1), "Dec 01"),
        (date(2025, 12, 24),"Dec 24 (IHSG ATH) ***"),
        (date(2026, 1, 2),  "Jan 02"),
        (date(2026, 1, 28), "Jan 28 (sell-off) ***"),
        (date(2026, 2, 25), "Feb 25"),
        (date(2026, 3, 9),  "Mar 09 (Fear) ***"),
        (date(2026, 4, 7),  "Apr 07"),
        (date(2026, 5, 20), "May 20"),
        (date(2026, 5, 22), "May 23 (Ext.Fear) ***"),
    ]

    def nearest(by_date, target):
        if target in by_date: return by_date[target]
        fwd = [d for d in sorted(by_date) if d >= target]
        bwd = [d for d in sorted(by_date) if d <= target]
        c = fwd[0] if fwd else (bwd[-1] if bwd else None)
        return by_date[c] if c else None

    print()
    print("=" * 90)
    print("  KEY CHECKPOINT COMPARISON")
    print("  A = current validated  |  B = + Strength (pct-ranked)  |  C = + Strength (raw ratio)")
    print("=" * 90)
    print(f"  {'Date':<12}  {'Stored A':>9}  {'Stored A lbl':<16}  "
          f"{'B':>7} {'B lbl':<16}  {'C':>7} {'C lbl':<16}  Note")
    print("  " + "-" * 88)

    for d, note in CHECKPOINTS:
        ra = nearest(by_date_a, d)
        rb = nearest(by_date_b, d)
        rc = nearest(by_date_c, d)

        sa = stored.get(d) or (ra["smooth"] if ra else None)
        sb = rb["smooth"] if rb else None
        sc = rc["smooth"] if rc else None

        sa_s = f"{sa:7.1f}" if sa is not None else "      -"
        sb_s = f"{sb:7.1f}" if sb is not None else "      -"
        sc_s = f"{sc:7.1f}" if sc is not None else "      -"

        la = label(sa)
        lb = label(sb)
        lc = label(sc)

        # Flag regressions
        flag = ""
        if sa is not None and sb is not None:
            if abs(sb - sa) > 5: flag += f" B{'+' if sb>sa else '-'}{abs(sb-sa):.0f}"
        if sa is not None and sc is not None:
            if abs(sc - sa) > 5: flag += f" C{'+' if sc>sa else '-'}{abs(sc-sa):.0f}"

        print(f"  {d}  {sa_s}  {la:<16}  {sb_s} {lb:<16}  {sc_s} {lc:<16}  {note}{flag}")

    # ── MONTHLY AVERAGES ─────────────────────────────────────────────────────
    print()
    print("=" * 90)
    print("  MONTH-BY-MONTH AVERAGES")
    print("=" * 90)
    print(f"  {'Month':<8}  {'A(stored)':>10}  {'A label':<16}  "
          f"{'B':>8} {'B label':<16}  {'C':>8} {'C label':<16}")
    print("  " + "-" * 84)

    months = sorted({(d.year, d.month) for d in target_dates})
    for y, m in months:
        ds_a = [by_date_a[d]["smooth"] for d in target_dates if d.year==y and d.month==m and d in by_date_a]
        ds_b = [by_date_b[d]["smooth"] for d in target_dates if d.year==y and d.month==m and d in by_date_b]
        ds_c = [by_date_c[d]["smooth"] for d in target_dates if d.year==y and d.month==m and d in by_date_c]
        ds_stored = [stored[d] for d in target_dates if d.year==y and d.month==m and d in stored]

        avg_stored = sum(ds_stored)/len(ds_stored) if ds_stored else None
        avg_b = sum(ds_b)/len(ds_b) if ds_b else None
        avg_c = sum(ds_c)/len(ds_c) if ds_c else None

        s_stored = f"{avg_stored:10.1f}" if avg_stored else "          -"
        s_b = f"{avg_b:8.1f}" if avg_b else "        -"
        s_c = f"{avg_c:8.1f}" if avg_c else "        -"
        l_stored = label(avg_stored) if avg_stored else "—"
        l_b = label(avg_b) if avg_b else "—"
        l_c = label(avg_c) if avg_c else "—"

        print(f"  {y}-{m:02d}   {s_stored}  {l_stored:<16}  {s_b} {l_b:<16}  {s_c} {l_c:<16}")

    # ── DIAGNOSIS ─────────────────────────────────────────────────────────────
    print()
    print("=" * 90)
    print("  DIAGNOSIS: Stock Strength component scores at validation checkpoints")
    print("=" * 90)
    print(f"  {'Date':<12}  {'Str pct':>9}  {'Str raw':>9}  {'IHSG':>8}  "
          f"{'H':>5}  {'L':>5}  Note")
    print("  " + "-" * 65)
    for d, note in CHECKPOINTS:
        # find nearest in strength cache
        candidates = sorted(strength_by_date.keys())
        c = min(candidates, key=lambda x: abs((x-d).days))
        sc_data = strength_by_date[c]
        ihsg_v = ihsg_by_date.get(c, ihsg_by_date.get(d))
        str_pct_v = sc_data["score"]
        str_raw_v = sc_data["raw_ratio"] * 100
        print(f"  {c}  {str_pct_v:9.1f}  {str_raw_v:9.1f}  "
              f"{ihsg_v:>8,.0f}  {sc_data['highs']:>5}  {sc_data['lows']:>5}  {note}")

    print()
    print("=" * 90)
    print("  VERDICT")
    print("=" * 90)
    # Check if Dec 24 checkpoint passes (must be >= 55 Greed) for both B and C
    dec24 = date(2025, 12, 24)
    stored_dec24 = stored.get(dec24, 76.1)
    b_dec24 = nearest(by_date_b, dec24)
    c_dec24 = nearest(by_date_c, dec24)
    sb_dec24 = b_dec24["smooth"] if b_dec24 else None
    sc_dec24 = c_dec24["smooth"] if c_dec24 else None

    print(f"\n  Dec 24 checkpoint (was {stored_dec24:.1f} Extreme Greed, must stay >= 55):")
    print(f"    Version B (pct-ranked): {sb_dec24:.1f}  {label(sb_dec24)}"
          + (" PASS" if sb_dec24 and sb_dec24 >= 55 else " FAIL <-- REGRESSION"))
    print(f"    Version C (raw ratio):  {sc_dec24:.1f}  {label(sc_dec24)}"
          + (" PASS" if sc_dec24 and sc_dec24 >= 55 else " FAIL <-- REGRESSION"))

    mar9 = date(2026, 3, 9)
    stored_mar9 = stored.get(mar9, 35.5)
    b_mar9 = nearest(by_date_b, mar9)
    c_mar9 = nearest(by_date_c, mar9)
    sb_mar9 = b_mar9["smooth"] if b_mar9 else None
    sc_mar9 = c_mar9["smooth"] if c_mar9 else None

    print(f"\n  Mar 9 checkpoint (was {stored_mar9:.1f} Fear, should stay < 45):")
    print(f"    Version B (pct-ranked): {sb_mar9:.1f}  {label(sb_mar9)}"
          + (" PASS" if sb_mar9 and sb_mar9 < 45 else " FAIL"))
    print(f"    Version C (raw ratio):  {sc_mar9:.1f}  {label(sc_mar9)}"
          + (" PASS" if sc_mar9 and sc_mar9 < 45 else " FAIL"))

    may23 = date(2026, 5, 22)
    stored_may23 = stored.get(may23, 21.9)
    b_may23 = nearest(by_date_b, may23)
    c_may23 = nearest(by_date_c, may23)
    sb_may23 = b_may23["smooth"] if b_may23 else None
    sc_may23 = c_may23["smooth"] if c_may23 else None

    print(f"\n  May 23 checkpoint (was {stored_may23:.1f} Extreme Fear, must stay < 25):")
    print(f"    Version B (pct-ranked): {sb_may23:.1f}  {label(sb_may23)}"
          + (" PASS" if sb_may23 and sb_may23 < 25 else " FAIL"))
    print(f"    Version C (raw ratio):  {sc_may23:.1f}  {label(sc_may23)}"
          + (" PASS" if sc_may23 and sc_may23 < 25 else " FAIL"))

    print()

asyncio.run(main())

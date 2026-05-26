"""
Side-by-side component breakdown for 2026-02-25 vs 2026-03-09.

Re-derives every component from raw IHSG / USD-IDR / FF data using the
same no-lookahead backtest formula, then compares with what is stored in
fear_greed_index.  No data is written.

Formula used (matches backtest_aug_jan.py):
  Momentum     0.25  MA30/MA125 ratio, pct-ranked vs all prior ratios
  Volatility   0.20  20d log-return vol (ann.), INVERTED pct-rank
  Rupiah       0.20  20d USD/IDR % change, INVERTED pct-rank
  Foreign flow 0.20  5d rolling net (Rp bn), pct-ranked vs all prior sums
"""
import asyncio, math, json, os, sys
sys.stdout.reconfigure(encoding="utf-8")
from datetime import date
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(".env"))
load_dotenv(Path(".env.local"), override=True)
import asyncpg

TARGET_A = date(2026, 2, 25)
TARGET_B = date(2026, 3,  9)

ROLL_WIN_FF = 5
EMA_ALPHA   = 0.7

W_MOM = 0.25
W_VOL = 0.20
W_RUP = 0.20
W_FF  = 0.20


def pct_rank(value, history):
    if not history: return 50.0
    below = sum(1 for h in history if h < value)
    return (below / len(history)) * 100.0


def moving_average(prices, n):
    return sum(prices[-n:]) / n


def decompose(prices_up_to, usd_up_to, ff_nets_up_to, winsor_lo, winsor_hi):
    """
    Compute all four component scores using only data up to the target date.
    Returns a dict with scores, raw values, percentile inputs, and diagnostics.
    """
    result = {}

    # ── Momentum: MA30 / MA125 ratio ──────────────────────────────────────────
    # Need ≥ 126 prices so we can have at least 2 ratio samples.
    if len(prices_up_to) >= 126:
        ratios = []
        for i in range(124, len(prices_up_to)):          # i is the 0-based end index
            ma125 = sum(prices_up_to[i - 124: i + 1]) / 125
            ma30  = sum(prices_up_to[i - 29:  i + 1]) / 30
            ratios.append(ma30 / ma125)

        current_ratio = ratios[-1]
        history_ratios = ratios[:-1]
        mom_score = pct_rank(current_ratio, history_ratios)

        ma30_now  = sum(prices_up_to[-30:]) / 30
        ma125_now = sum(prices_up_to[-125:]) / 125

        result["momentum"] = {
            "score":          round(mom_score, 2),
            "ma30":           round(ma30_now, 2),
            "ma125":          round(ma125_now, 2),
            "ratio":          round(current_ratio, 6),
            "ratio_pct":      round((current_ratio - 1) * 100, 3),   # % above/below
            "history_len":    len(history_ratios),
            "history_min":    round(min(history_ratios), 6),
            "history_max":    round(max(history_ratios), 6),
            "history_p25":    round(sorted(history_ratios)[len(history_ratios)//4], 6),
            "history_median": round(sorted(history_ratios)[len(history_ratios)//2], 6),
        }
    else:
        result["momentum"] = {
            "score": None,
            "reason": f"only {len(prices_up_to)} prices (need 126)"
        }

    # ── Volatility: 20d log-return vol (annualised), inverted ─────────────────
    if len(prices_up_to) >= 21:
        log_rets = [math.log(prices_up_to[i] / prices_up_to[i-1])
                    for i in range(1, len(prices_up_to))]
        vols = []
        for i in range(19, len(log_rets)):
            win  = log_rets[i - 19: i + 1]
            mean = sum(win) / len(win)
            var  = sum((r - mean)**2 for r in win) / len(win)
            vols.append(math.sqrt(var) * math.sqrt(252))

        current_vol = vols[-1]
        history_vols = vols[:-1]
        pct = pct_rank(current_vol, history_vols)
        vol_score = 100.0 - pct    # inverted

        result["volatility"] = {
            "score":           round(vol_score, 2),
            "vol_20d_ann":     round(current_vol * 100, 3),   # in %
            "pct_rank_raw":    round(pct, 2),                  # before inversion
            "history_len":     len(history_vols),
            "history_min_pct": round(min(history_vols) * 100, 3),
            "history_max_pct": round(max(history_vols) * 100, 3),
            "history_p25_pct": round(sorted(history_vols)[len(history_vols)//4] * 100, 3),
            "history_med_pct": round(sorted(history_vols)[len(history_vols)//2] * 100, 3),
        }
    else:
        result["volatility"] = {"score": None, "reason": f"only {len(prices_up_to)} prices"}

    # ── Rupiah stress: 20d pct change, inverted ────────────────────────────────
    if len(usd_up_to) >= 21:
        changes = []
        for i in range(20, len(usd_up_to)):
            changes.append((usd_up_to[i] - usd_up_to[i-20]) / usd_up_to[i-20] * 100)

        current_chg = changes[-1]
        history_chg = changes[:-1]
        pct = pct_rank(current_chg, history_chg)
        rup_score = 100.0 - pct    # inverted

        result["rupiah"] = {
            "score":        round(rup_score, 2),
            "usd_idr_now":  round(usd_up_to[-1], 2),
            "usd_idr_20d_ago": round(usd_up_to[-21], 2),
            "chg_20d_pct":  round(current_chg, 4),   # + = IDR weaker = more stress
            "pct_rank_raw": round(pct, 2),             # before inversion
            "history_len":  len(history_chg),
            "history_min":  round(min(history_chg), 4),
            "history_max":  round(max(history_chg), 4),
        }
    else:
        result["rupiah"] = {"score": None, "reason": f"only {len(usd_up_to)} USD/IDR rows"}

    # ── Foreign flow: 5d rolling sum, pct-ranked ──────────────────────────────
    if len(ff_nets_up_to) >= 2:
        sums = []
        for i in range(len(ff_nets_up_to)):
            win = ff_nets_up_to[max(0, i - ROLL_WIN_FF + 1): i + 1]
            sums.append(sum(win))
        sums_w = [max(winsor_lo, min(winsor_hi, s)) for s in sums]
        current_sum  = sums[-1]
        current_sumw = sums_w[-1]
        history_sumw = sums_w[:-1]
        ff_score = pct_rank(current_sumw, history_sumw)

        result["foreign_flow"] = {
            "score":          round(ff_score, 2),
            "5d_net_raw":     round(current_sum, 2),
            "5d_net_winsor":  round(current_sumw, 2),
            "winsor_lo":      round(winsor_lo, 2),
            "winsor_hi":      round(winsor_hi, 2),
            "history_len":    len(history_sumw),
            "last_5d_nets":   [round(v, 2) for v in ff_nets_up_to[-5:]],
            "history_min":    round(min(history_sumw), 2),
            "history_max":    round(max(history_sumw), 2),
        }
    else:
        result["foreign_flow"] = {
            "score": None,
            "reason": f"only {len(ff_nets_up_to)} FF rows"
        }

    return result


def build_score(comps):
    active = [(k, v) for k, v in comps.items() if v.get("score") is not None]
    weights = {"momentum": W_MOM, "volatility": W_VOL,
               "rupiah": W_RUP, "foreign_flow": W_FF}
    total_w = sum(weights[k] for k, _ in active)
    if not active or total_w == 0:
        return None, 0
    raw = sum(weights[k] / total_w * v["score"] for k, v in active)
    return round(raw, 2), len(active)


def label_score(s):
    if s is None: return "n/a"
    if s >= 75: return "Extreme Greed"
    if s >= 55: return "Greed"
    if s >= 45: return "Neutral"
    if s >= 25: return "Fear"
    return "Extreme Fear"


async def main():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        # ── Load full time-series ──────────────────────────────────────────────
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

        ihsg_dates = [r["date"] for r in ihsg_rows]
        usd_dates  = [r["date"] for r in usd_rows]
        ff_dates   = [r["date"] for r in ff_rows]

        # Pre-compute FF winsorisation from full dataset
        all_nets = [ff_by_date[d] for d in ff_dates]
        all_sums = []
        for i in range(len(all_nets)):
            win = all_nets[max(0, i - ROLL_WIN_FF + 1): i + 1]
            all_sums.append(sum(win))
        sorted_sums = sorted(all_sums)
        n = len(sorted_sums)
        winsor_lo = sorted_sums[max(0, int(n * 0.05))]
        winsor_hi = sorted_sums[min(n - 1, int(n * 0.95))]

        print(f"IHSG rows  : {len(ihsg_dates)}  {ihsg_dates[0]} to {ihsg_dates[-1]}")
        print(f"USD/IDR rows: {len(usd_dates)}  {usd_dates[0]} to {usd_dates[-1]}")
        print(f"FF rows    : {len(ff_dates)}  {ff_dates[0]} to {ff_dates[-1]}")
        print(f"FF winsor  : lo={winsor_lo:.1f}  hi={winsor_hi:.1f}  (from {n} rolling sums)")

        # ── Fetch stored F&G rows ─────────────────────────────────────────────
        stored = await conn.fetch("""
            SELECT date, raw_score, smoothed_score, label, components_json, is_backfilled
            FROM fear_greed_index
            WHERE date IN ($1, $2)
            ORDER BY date
        """, TARGET_A, TARGET_B)
        stored_by_date = {r["date"]: r for r in stored}

        # Also fetch full Feb-Mar 2026 for context
        context = await conn.fetch("""
            SELECT date, raw_score, smoothed_score, label, components_json
            FROM fear_greed_index
            WHERE date BETWEEN '2026-02-01' AND '2026-03-15'
            ORDER BY date
        """)

        # ── Compute components for each target ────────────────────────────────
        results = {}
        for target in [TARGET_A, TARGET_B]:
            ihsg_seq = [ihsg_by_date[d] for d in ihsg_dates if d <= target]
            usd_seq  = [usd_by_date[d]  for d in usd_dates  if d <= target]
            ff_seq   = [ff_by_date[d]   for d in ff_dates   if d <= target]

            comps = decompose(ihsg_seq, usd_seq, ff_seq, winsor_lo, winsor_hi)
            raw, n_active = build_score(comps)
            results[target] = {
                "ihsg":     ihsg_by_date.get(target),
                "usd_idr":  usd_by_date.get(target),
                "ff_net_day": ff_by_date.get(target),
                "comps":    comps,
                "raw":      raw,
                "n_active": n_active,
                "n_ihsg":   len(ihsg_seq),
                "n_usd":    len(usd_seq),
                "n_ff":     len(ff_seq),
            }

        # ══ REPORT ════════════════════════════════════════════════════════════
        print()
        print("=" * 76)
        print("  COMPONENT BREAKDOWN — Feb 25 vs Mar 9, 2026")
        print("=" * 76)

        dates = [TARGET_A, TARGET_B]
        for target in dates:
            r   = results[target]
            st  = stored_by_date.get(target, {})
            try:
                stored_cj = json.loads(st["components_json"]) if st and st["components_json"] else {}
            except Exception:
                stored_cj = {}

            print(f"\n{'-'*76}")
            print(f"  Date : {target}")
            bf = "backfilled" if st and st.get("is_backfilled") else "live"
            print(f"  IHSG : {r['ihsg']:,.2f}    USD/IDR: {r['usd_idr']:,.2f}    FF today: "
                  f"{r['ff_net_day']:+.1f} Rp bn" if r['ff_net_day'] is not None
                  else f"  IHSG : {r['ihsg']:,.2f}    USD/IDR: {r['usd_idr']:,.2f}    FF today: n/a")
            print(f"  Data : {r['n_ihsg']} IHSG bars  {r['n_usd']} USD/IDR bars  {r['n_ff']} FF bars")
            print(f"  Stored: raw={st['raw_score'] if st else '—'}  "
                  f"smooth={st['smoothed_score'] if st else '—'}  "
                  f"label={st['label'] if st else '—'}  [{bf}]")
            print(f"  Stored components_json: {stored_cj}")
            print()
            print(f"  {'COMPONENT':<16} {'SCORE':>7} {'WEIGHT':>8} {'STORED':>8}  RAW VALUE / DETAIL")
            print(f"  {'-'*16} {'-'*7} {'-'*8} {'-'*8}  {'-'*35}")

            comp_order = ["momentum", "volatility", "rupiah", "foreign_flow"]
            nom_weights = {
                "momentum": W_MOM, "volatility": W_VOL,
                "rupiah": W_RUP, "foreign_flow": W_FF
            }
            active_w = sum(nom_weights[k] for k in comp_order
                           if r["comps"].get(k, {}).get("score") is not None)

            for k in comp_order:
                c = r["comps"].get(k, {})
                sc = c.get("score")
                nom_w = nom_weights[k]
                eff_w = (nom_w / active_w * 100) if active_w > 0 and sc is not None else 0
                stored_sc = stored_cj.get(k) if stored_cj else "—"
                score_str  = f"{sc:7.2f}" if sc is not None else "   INACTIVE"
                stored_str = f"{stored_sc:7.2f}" if isinstance(stored_sc, (int, float)) else f"{'—':>7}"
                eff_w_str  = f"({eff_w:.0f}%)" if sc is not None else "( — )"

                print(f"  {k:<16} {score_str} {eff_w_str:>8} {stored_str}  ", end="")

                if k == "momentum":
                    if sc is not None:
                        print(f"MA30={c['ma30']:,.2f}  MA125={c['ma125']:,.2f}  "
                              f"ratio={c['ratio_pct']:+.3f}%  "
                              f"pctile={sc:.1f}  hist={c['history_len']}pts")
                    else:
                        print(f"INACTIVE — {c.get('reason','')}")

                elif k == "volatility":
                    if sc is not None:
                        print(f"vol20d={c['vol_20d_ann']:.2f}%ann  "
                              f"raw_pctile={c['pct_rank_raw']:.1f}  "
                              f"→inv={sc:.1f}  hist={c['history_len']}pts  "
                              f"[min={c['history_min_pct']:.2f}% "
                              f"med={c['history_med_pct']:.2f}% "
                              f"max={c['history_max_pct']:.2f}%]")
                    else:
                        print(f"INACTIVE — {c.get('reason','')}")

                elif k == "rupiah":
                    if sc is not None:
                        print(f"USD/IDR {c['usd_idr_now']:,.2f}  20d_ago={c['usd_idr_20d_ago']:,.2f}  "
                              f"chg={c['chg_20d_pct']:+.3f}%  "
                              f"raw_pctile={c['pct_rank_raw']:.1f}  →inv={sc:.1f}  "
                              f"hist={c['history_len']}pts")
                    else:
                        print(f"INACTIVE — {c.get('reason','')}")

                elif k == "foreign_flow":
                    if sc is not None:
                        print(f"5d_net={c['5d_net_raw']:+.1f}Rp bn  "
                              f"last5d={c['last_5d_nets']}  "
                              f"pctile={sc:.1f}  hist={c['history_len']}pts  "
                              f"[min={c['history_min']:+.0f} max={c['history_max']:+.0f}]")
                    else:
                        print(f"INACTIVE — {c.get('reason','')}")

            raw_score = r["raw"]
            print(f"\n  Recomputed raw score : {raw_score:.2f} ({label_score(raw_score)})" if raw_score else
                  f"\n  Recomputed raw score : n/a")
            print(f"  Active components   : {r['n_active']}/4  effective total weight: {active_w:.2f}")

        # ══ DELTA ANALYSIS ════════════════════════════════════════════════════
        print()
        print("=" * 76)
        print("  DELTA: Feb 25 → Mar 9  (what changed?)")
        print("=" * 76)

        rA = results[TARGET_A]
        rB = results[TARGET_B]

        ihsg_chg = (rB["ihsg"] - rA["ihsg"]) / rA["ihsg"] * 100 if rA["ihsg"] and rB["ihsg"] else None
        print(f"\n  IHSG        : {rA['ihsg']:,.2f} → {rB['ihsg']:,.2f}  ({ihsg_chg:+.2f}%)")
        if rA["usd_idr"] and rB["usd_idr"]:
            usd_chg = (rB["usd_idr"] - rA["usd_idr"]) / rA["usd_idr"] * 100
            print(f"  USD/IDR     : {rA['usd_idr']:,.2f} → {rB['usd_idr']:,.2f}  ({usd_chg:+.2f}%  "
                  f"{'IDR weaker' if usd_chg > 0 else 'IDR stronger'})")

        print()
        for k in ["momentum", "volatility", "rupiah", "foreign_flow"]:
            sA = rA["comps"].get(k, {}).get("score")
            sB = rB["comps"].get(k, {}).get("score")
            if sA is None and sB is None:
                delta_str = "both inactive"
            elif sA is None:
                delta_str = f"INACTIVE → {sB:.1f}  (+{sB:.1f} from becoming active)"
            elif sB is None:
                delta_str = f"{sA:.1f} → INACTIVE"
            else:
                d = sB - sA
                arrow = "UP ↑" if d > 5 else "DOWN ↓" if d < -5 else "≈ flat"
                delta_str = f"{sA:.1f} → {sB:.1f}  ({d:+.1f}) — {arrow}"
            print(f"  {k:<16}: {delta_str}")

        stA = stored_by_date.get(TARGET_A)
        stB = stored_by_date.get(TARGET_B)
        print()
        print(f"  Stored raw_score    : {stA['raw_score'] if stA else '—'} → {stB['raw_score'] if stB else '—'}")
        print(f"  Stored smoothed     : {stA['smoothed_score'] if stA else '—'} → {stB['smoothed_score'] if stB else '—'}")
        print(f"  Stored label        : {stA['label'] if stA else '—'} → {stB['label'] if stB else '—'}")

        # ══ CONTEXT: Full Feb-Mar 2026 trend ══════════════════════════════════
        print()
        print("=" * 76)
        print("  CONTEXT: Full Feb–Mar 2026  (stored rows)")
        print("=" * 76)
        print(f"\n  {'DATE':<12} {'IHSG':>8} {'RAW':>7} {'SMOOTH':>8} {'LABEL':<16} STORED COMPONENTS")
        print(f"  {'-'*12} {'-'*8} {'-'*7} {'-'*8} {'-'*16} {'-'*30}")
        for r in context:
            dt = str(r["date"])
            ihsg_v = ihsg_by_date.get(r["date"])
            ihsg_s = f"{ihsg_v:,.0f}" if ihsg_v else "  —"
            raw_s  = f"{r['raw_score']:7.1f}" if r["raw_score"] else "    —  "
            smo_s  = f"{r['smoothed_score']:8.1f}" if r["smoothed_score"] else "    —   "
            try:
                cj = json.loads(r["components_json"]) if r["components_json"] else {}
            except Exception:
                cj = {}
            comp_str = "  ".join(f"{k}={v:.0f}" for k, v in cj.items()) if cj else "—"
            marker = " <<< TARGET" if r["date"] in (TARGET_A, TARGET_B) else ""
            print(f"  {dt:<12} {ihsg_s:>8} {raw_s} {smo_s} {r['label']:<16} {comp_str}{marker}")

    finally:
        await conn.close()


asyncio.run(main())

"""
EXPERIMENT: Invert foreign flow -> domestic flow proxy.

Phase 1  Back up fear_greed_index -> fear_greed_index_foreign_v
         Back up foreign_flow_daily -> foreign_flow_daily_foreign_v
Phase 2  Upsert inverted net_idr_billions into foreign_flow_daily
Phase 3  Re-run full backfill Aug 2025 -> present with inverted data
         (same formula, weights, winsorisation, EMA as rebackfill_stale.py)
Phase 4  Print side-by-side comparison (foreign backup vs domestic new)

Run from project root:
    python -m backend.scripts.experiment_domestic_flow

To RESTORE: run experiment_restore_foreign.py
"""
import asyncio, math, json, os, sys
sys.stdout.reconfigure(encoding="utf-8")
from datetime import date
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(".env"))
load_dotenv(Path(".env.local"), override=True)
import asyncpg

# ── Formula constants (unchanged) ────────────────────────────────────────────
EMA_ALPHA   = 0.7
ROLL_WIN_FF = 5
MIN_MOM     = 126
MIN_VOL     = 21
MIN_RUP     = 21
W_MOM = 0.25; W_VOL = 0.20; W_RUP = 0.20; W_FF = 0.20

BACKFILL_START = date(2025, 8, 1)

# ── Inverted flow data (domestic proxy = negative of original foreign flow) ──
INVERTED_FLOW = {
    date(2025, 8,  1):    73.66,
    date(2025, 8,  4):  1017.13,
    date(2025, 8,  5):  -552.40,
    date(2025, 8,  6):  -433.74,
    date(2025, 8,  7):  -666.13,
    date(2025, 8,  8):   510.92,
    date(2025, 8, 11):  -850.00,
    date(2025, 8, 12): -2206.74,
    date(2025, 8, 13): -1486.56,
    date(2025, 8, 14):  -827.17,
    date(2025, 8, 15): -1309.07,
    date(2025, 8, 19):  -863.34,
    date(2025, 8, 20):  -766.76,
    date(2025, 8, 21):  -681.55,
    date(2025, 8, 22):  -424.57,
    date(2025, 8, 25):  -731.36,
    date(2025, 8, 26): -2375.38,
    date(2025, 8, 27):   212.58,
    date(2025, 8, 28):   278.76,
    date(2025, 8, 29):  1123.23,
    date(2025, 9,  1):  2154.87,
    date(2025, 9,  2):   330.88,
    date(2025, 9,  3):  1387.64,
    date(2025, 9,  4):   305.18,
    date(2025, 9,  8):   526.17,
    date(2025, 9,  9):  4547.92,
    date(2025, 9, 10):  1301.55,
    date(2025, 9, 11):   192.43,
    date(2025, 9, 12):    31.59,
    date(2025, 9, 15): -1047.22,
    date(2025, 9, 16):   373.22,
    date(2025, 9, 17):   151.85,
    date(2025, 9, 18):   358.27,
    date(2025, 9, 19): -2867.06,
    date(2025, 9, 22):  -491.53,
    date(2025, 9, 23): -5549.07,
    date(2025, 9, 24):   524.55,
    date(2025, 9, 25):  1002.06,
    date(2025, 9, 26):  -583.10,
    date(2025, 9, 29):  -555.64,
    date(2025, 9, 30):  1702.91,
    date(2025,10,  1):   737.70,
    date(2025,10,  2):  1420.65,
    date(2025,10,  3):  -199.79,
    date(2025,10,  6): -2024.91,
    date(2025,10,  7):    89.41,
    date(2025,10,  8):   455.25,
    date(2025,10,  9): -1004.74,
    date(2025,10, 10):  -728.91,
    date(2025,10, 13): -2293.18,
    date(2025,10, 14):  1364.03,
    date(2025,10, 15):  1399.51,
    date(2025,10, 16):   620.90,
    date(2025,10, 17): -3034.98,
    date(2025,10, 20):  -529.77,
    date(2025,10, 21): -1342.39,
    date(2025,10, 22):  -120.10,
    date(2025,10, 23): -1084.74,
    date(2025,10, 24): -1153.15,
    date(2025,10, 27): -1197.24,
    date(2025,10, 28):  1370.70,
    date(2025,10, 29): -3786.49,
    date(2025,10, 30):  -784.69,
    date(2025,10, 31): -1134.57,
    date(2025,11,  3): -1035.12,
    date(2025,11,  4):  -304.59,
    date(2025,11,  5): -1311.64,
    date(2025,11,  6):   114.96,
    date(2025,11,  7):  -920.24,
    date(2025,11, 10):  -419.88,
    date(2025,11, 11):   648.43,
    date(2025,11, 12): -1231.74,
    date(2025,11, 13): -2916.77,
    date(2025,11, 14):    73.42,
    date(2025,11, 17):  -709.82,
    date(2025,11, 18):  -281.02,
    date(2025,11, 19): -1674.29,
    date(2025,11, 20): -1269.63,
    date(2025,11, 21):    26.32,
    date(2025,11, 24): -3155.20,
    date(2025,11, 25):   308.07,
    date(2025,11, 26):   550.31,
    date(2025,11, 27):   283.75,
    date(2025,11, 28):  1020.66,
    date(2025,12,  1):   120.64,
    date(2025,12,  2):  -453.84,
    date(2025,12,  3):   -70.41,
    date(2025,12,  4): -1702.64,
    date(2025,12,  5):  -381.18,
    date(2025,12,  8):   -52.74,
    date(2025,12,  9):   226.76,
    date(2025,12, 10):    43.27,
    date(2025,12, 11): -1357.94,
    date(2025,12, 12):  -282.27,
    date(2025,12, 15):  -247.52,
    date(2025,12, 16):   934.64,
    date(2025,12, 17):  -266.18,
    date(2025,12, 18): -1018.42,
    date(2025,12, 19): -2674.82,
    date(2025,12, 22): -1340.14,
    date(2025,12, 23):  -245.59,
    date(2025,12, 24): -2448.72,
    date(2025,12, 29): -1960.36,
    date(2025,12, 30):   938.13,
    date(2026, 1,  2): -1062.54,
    date(2026, 1,  5):   -38.88,
    date(2026, 1,  6):  -591.08,
    date(2026, 1,  7):  -200.81,
    date(2026, 1,  8):  -948.87,
    date(2026, 1,  9):  -256.88,
    date(2026, 1, 12):  -107.21,
    date(2026, 1, 13): -1986.10,
    date(2026, 1, 14): -1161.54,
    date(2026, 1, 15):  -947.45,
    date(2026, 1, 19):   708.61,
    date(2026, 1, 20):    91.67,
    date(2026, 1, 21):  1884.26,
    date(2026, 1, 22):  1326.46,
    date(2026, 1, 23):  -759.52,
    date(2026, 1, 26):   -24.25,
    date(2026, 1, 27):  1614.45,
    date(2026, 1, 28):  6173.42,
    date(2026, 1, 29):  4631.75,
    date(2026, 1, 30):  1530.52,
    date(2026, 2,  2):  -654.83,
    date(2026, 2,  3):   833.87,
    date(2026, 2,  4):  1434.82,
    date(2026, 2,  5):   469.81,
    date(2026, 2,  6):  -944.31,
    date(2026, 2,  9):   721.77,
    date(2026, 2, 10):   708.01,
    date(2026, 2, 11):   526.42,
    date(2026, 2, 12):  1489.98,
    date(2026, 2, 13):  2027.91,
    date(2026, 2, 18): -1443.08,
    date(2026, 2, 19):  -387.02,
    date(2026, 2, 20):  -240.57,
    date(2026, 2, 23): -1142.74,
    date(2026, 2, 24): -1376.92,
    date(2026, 2, 25): -2741.03,
    date(2026, 2, 26):  -340.42,
    date(2026, 2, 27):   694.22,
    date(2026, 5, 22):   309.45,
}


# ── Math helpers (identical to rebackfill_stale.py) ──────────────────────────

def pct_rank(value, history):
    if not history: return 50.0
    return sum(1 for h in history if h < value) / len(history) * 100.0

def compute_momentum(prices):
    if len(prices) < MIN_MOM: return None
    ratios = []
    for i in range(124, len(prices)):
        ma125 = sum(prices[i-124:i+1]) / 125
        ma30  = sum(prices[i-29: i+1]) / 30
        ratios.append(ma30 / ma125)
    if len(ratios) < 2: return None
    return round(pct_rank(ratios[-1], ratios[:-1]), 2)

def compute_volatility(prices):
    if len(prices) < MIN_VOL: return None
    vols = []
    for i in range(20, len(prices)):
        win = prices[i-20:i+1]
        lr  = [math.log(win[j]/win[j-1]) for j in range(1, len(win))]
        mean_r = sum(lr)/len(lr)
        vols.append(math.sqrt(sum((r-mean_r)**2 for r in lr)/len(lr)) * math.sqrt(252))
    if len(vols) < 2: return None
    return round(100.0 - pct_rank(vols[-1], vols[:-1]), 2)

def compute_rupiah(rates):
    if len(rates) < MIN_RUP: return None
    changes = []
    for i in range(20, len(rates)):
        changes.append((rates[i]-rates[i-20])/rates[i-20]*100)
    if len(changes) < 2: return None
    return round(100.0 - pct_rank(changes[-1], changes[:-1]), 2)

def compute_ff(nets, winsor_lo, winsor_hi):
    if len(nets) < 2: return None
    sums = []
    for i in range(len(nets)):
        sums.append(sum(nets[max(0,i-ROLL_WIN_FF+1):i+1]))
    sums_w = [max(winsor_lo, min(winsor_hi, s)) for s in sums]
    return round(pct_rank(sums_w[-1], sums_w[:-1]), 2)

def score_to_label(s):
    if s >= 75: return "Extreme Greed"
    if s >= 55: return "Greed"
    if s >= 45: return "Neutral"
    if s >= 25: return "Fear"
    return "Extreme Fear"


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:

        # ════════════════════════════════════════════════════════════════════
        # PHASE 1 — BACKUPS
        # ════════════════════════════════════════════════════════════════════
        print("=== PHASE 1: BACKUPS ===")

        # Backup fear_greed_index
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS fear_greed_index_foreign_v AS
            SELECT * FROM fear_greed_index WHERE FALSE
        """)
        # Truncate and repopulate (idempotent: re-running script won't double rows)
        await conn.execute("TRUNCATE fear_greed_index_foreign_v")
        await conn.execute("""
            INSERT INTO fear_greed_index_foreign_v
            SELECT * FROM fear_greed_index
        """)
        fg_orig  = await conn.fetchval("SELECT COUNT(*) FROM fear_greed_index")
        fg_backup= await conn.fetchval("SELECT COUNT(*) FROM fear_greed_index_foreign_v")
        print(f"fear_greed_index         : {fg_orig} rows")
        print(f"fear_greed_index_foreign_v: {fg_backup} rows  {'OK' if fg_orig==fg_backup else 'MISMATCH!'}")
        assert fg_orig == fg_backup, "Backup row count mismatch — aborting"

        # Backup foreign_flow_daily
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS foreign_flow_daily_foreign_v AS
            SELECT * FROM foreign_flow_daily WHERE FALSE
        """)
        await conn.execute("TRUNCATE foreign_flow_daily_foreign_v")
        await conn.execute("""
            INSERT INTO foreign_flow_daily_foreign_v
            SELECT * FROM foreign_flow_daily
        """)
        ff_orig   = await conn.fetchval("SELECT COUNT(*) FROM foreign_flow_daily")
        ff_backup = await conn.fetchval("SELECT COUNT(*) FROM foreign_flow_daily_foreign_v")
        print(f"foreign_flow_daily         : {ff_orig} rows")
        print(f"foreign_flow_daily_foreign_v: {ff_backup} rows  {'OK' if ff_orig==ff_backup else 'MISMATCH!'}")
        assert ff_orig == ff_backup, "Flow backup row count mismatch — aborting"
        print()

        # ════════════════════════════════════════════════════════════════════
        # PHASE 2 — UPSERT INVERTED FLOW VALUES
        # ════════════════════════════════════════════════════════════════════
        print("=== PHASE 2: UPSERT INVERTED FLOW DATA ===")
        upserted_ff = 0
        for d, val in sorted(INVERTED_FLOW.items()):
            await conn.execute("""
                INSERT INTO foreign_flow_daily (date, net_idr_billions, source, fetched_at)
                VALUES ($1, $2, 'domestic_experiment', NOW())
                ON CONFLICT (date) DO UPDATE
                  SET net_idr_billions = EXCLUDED.net_idr_billions,
                      source           = EXCLUDED.source,
                      fetched_at       = NOW()
            """, d, val)
            upserted_ff += 1
        print(f"Upserted {upserted_ff} inverted flow rows into foreign_flow_daily")

        # Spot-check Jan 28 (should now be +6173.42)
        jan28 = await conn.fetchrow(
            "SELECT net_idr_billions, source FROM foreign_flow_daily WHERE date = '2026-01-28'"
        )
        print(f"Jan 28 flow after upsert: {jan28['net_idr_billions']:+.2f} Rp bn "
              f"[source={jan28['source']}]  (expected +6173.42)")
        print()

        # ════════════════════════════════════════════════════════════════════
        # PHASE 3 — RE-RUN FULL BACKFILL
        # ════════════════════════════════════════════════════════════════════
        print("=== PHASE 3: FULL BACKFILL (Aug 2025 -> present) ===")

        # Load all market data
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

        # FF winsorisation from full dataset (with inverted values)
        all_nets = [ff_by_date[d] for d in ff_dates]
        all_sums = []
        for i in range(len(all_nets)):
            all_sums.append(sum(all_nets[max(0,i-ROLL_WIN_FF+1):i+1]))
        sorted_sums = sorted(all_sums)
        n = len(sorted_sums)
        winsor_lo = sorted_sums[max(0, int(n*0.05))]
        winsor_hi = sorted_sums[min(n-1, int(n*0.95))]
        print(f"FF winsorisation (domestic): lo={winsor_lo:.1f}  hi={winsor_hi:.1f}  ({n} sums)")

        # Which rows are live (never overwrite)
        live_rows = await conn.fetch(
            "SELECT date FROM fear_greed_index WHERE is_backfilled = FALSE"
        )
        live_set = {r["date"] for r in live_rows}
        print(f"Live rows (protected, won't overwrite): {len(live_set)}")

        # All backfilled dates to recompute
        bf_rows = await conn.fetch(
            "SELECT date FROM fear_greed_index WHERE is_backfilled = TRUE ORDER BY date ASC"
        )
        bf_dates = [r["date"] for r in bf_rows]
        print(f"Backfilled rows to recompute: {len(bf_dates)}  "
              f"({bf_dates[0]} to {bf_dates[-1]})")
        print()

        # Compute
        records = []
        for target in bf_dates:
            if target in live_set:
                continue

            ihsg_seq = [ihsg_by_date[d] for d in ihsg_dates if d <= target]
            usd_seq  = [usd_by_date[d]  for d in usd_dates  if d <= target]
            ff_seq   = [ff_by_date[d]   for d in ff_dates   if d <= target]

            mom_s = compute_momentum(ihsg_seq)
            vol_s = compute_volatility(ihsg_seq)
            rup_s = compute_rupiah(usd_seq)
            ff_s  = compute_ff(ff_seq, winsor_lo, winsor_hi)

            comps   = []
            total_w = 0.0
            cj      = {}
            if mom_s is not None: comps.append((W_MOM, mom_s)); total_w += W_MOM; cj["momentum"]     = mom_s
            if vol_s is not None: comps.append((W_VOL, vol_s)); total_w += W_VOL; cj["volatility"]   = vol_s
            if rup_s is not None: comps.append((W_RUP, rup_s)); total_w += W_RUP; cj["rupiah"]       = rup_s
            if ff_s  is not None: comps.append((W_FF,  ff_s )); total_w += W_FF;  cj["foreign_flow"] = ff_s

            if not comps or total_w == 0:
                continue

            raw = sum(w/total_w * s for w,s in comps)
            records.append({"date": target, "raw": round(raw,2), "n": len(comps),
                            "cj": cj, "total_w": total_w})

        print(f"Records computed: {len(records)}")

        # EMA smoothing — no seed before Aug 2025 (cold start)
        records.sort(key=lambda r: r["date"])
        smoothed = None
        for rec in records:
            raw = rec["raw"]
            smoothed = EMA_ALPHA * raw + (1-EMA_ALPHA) * smoothed if smoothed is not None else raw
            rec["smoothed"] = round(smoothed, 2)

        # Upsert
        upserted_fg = 0
        for rec in records:
            label = score_to_label(rec["smoothed"])
            await conn.execute("""
                INSERT INTO fear_greed_index
                    (date, score, raw_score, smoothed_score, label,
                     active_components, components_json, is_backfilled, window_days, updated_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,TRUE,126,NOW())
                ON CONFLICT (date) DO UPDATE SET
                    score=EXCLUDED.score, raw_score=EXCLUDED.raw_score,
                    smoothed_score=EXCLUDED.smoothed_score, label=EXCLUDED.label,
                    active_components=EXCLUDED.active_components,
                    components_json=EXCLUDED.components_json,
                    is_backfilled=TRUE, updated_at=NOW()
                WHERE fear_greed_index.is_backfilled=TRUE
                   OR fear_greed_index.smoothed_score IS NULL
            """,
                rec["date"], rec["smoothed"], rec["raw"], rec["smoothed"],
                label, rec["n"], json.dumps(rec["cj"]),
            )
            upserted_fg += 1
        print(f"Upserted {upserted_fg} rows to fear_greed_index (domestic version)")
        print()

        # ════════════════════════════════════════════════════════════════════
        # PHASE 4 — SIDE-BY-SIDE COMPARISON
        # ════════════════════════════════════════════════════════════════════
        print("=== PHASE 4: SIDE-BY-SIDE COMPARISON ===")
        print("(FOREIGN = backup  |  DOMESTIC = new inverted values)")
        print()

        # Load both versions
        foreign_rows = await conn.fetch(
            "SELECT date, smoothed_score, label, raw_score, components_json "
            "FROM fear_greed_index_foreign_v "
            "WHERE is_backfilled = TRUE ORDER BY date ASC"
        )
        domestic_rows = await conn.fetch(
            "SELECT date, smoothed_score, label, raw_score, components_json "
            "FROM fear_greed_index "
            "WHERE is_backfilled = TRUE ORDER BY date ASC"
        )

        foreign_by_date  = {r["date"]: r for r in foreign_rows}
        domestic_by_date = {r["date"]: r for r in domestic_rows}

        # ── Month-by-month summary ────────────────────────────────────────
        from collections import defaultdict
        months_f: dict = defaultdict(list)
        months_d: dict = defaultdict(list)
        for r in foreign_rows:
            months_f[str(r["date"])[:7]].append(float(r["smoothed_score"]) if r["smoothed_score"] else 0)
        for r in domestic_rows:
            months_d[str(r["date"])[:7]].append(float(r["smoothed_score"]) if r["smoothed_score"] else 0)

        all_months = sorted(set(list(months_f.keys()) + list(months_d.keys())))

        print(f"  {'MONTH':<8}  {'-- FOREIGN (validated) --':^28}  {'-- DOMESTIC (inverted) --':^28}  IHSG ctx")
        print(f"  {'':8}  {'avg':>6} {'low':>6} {'high':>6} {'end-label':<14}  "
              f"{'avg':>6} {'low':>6} {'high':>6} {'end-label':<14}")
        print(f"  {'-'*8}  {'-'*6} {'-'*6} {'-'*6} {'-'*14}  "
              f"{'-'*6} {'-'*6} {'-'*6} {'-'*14}")

        for mo in all_months:
            fv = months_f.get(mo, [])
            dv = months_d.get(mo, [])

            # Get end-of-month label for each version
            f_dates = sorted(d for d in foreign_by_date if str(d)[:7]==mo)
            d_dates = sorted(d for d in domestic_by_date if str(d)[:7]==mo)
            f_label = foreign_by_date[f_dates[-1]]["label"] if f_dates else "—"
            d_label = domestic_by_date[d_dates[-1]]["label"] if d_dates else "—"

            fa  = f"{sum(fv)/len(fv):6.1f}" if fv else "     -"
            flo = f"{min(fv):6.1f}" if fv else "     -"
            fhi = f"{max(fv):6.1f}" if fv else "     -"
            da  = f"{sum(dv)/len(dv):6.1f}" if dv else "     -"
            dlo = f"{min(dv):6.1f}" if dv else "     -"
            dhi = f"{max(dv):6.1f}" if dv else "     -"

            # Simple IHSG trend marker (compare first/last of month)
            ihsg_mo_dates = sorted(d for d in ihsg_by_date if str(d)[:7]==mo)
            if len(ihsg_mo_dates) >= 2:
                chg = (ihsg_by_date[ihsg_mo_dates[-1]]-ihsg_by_date[ihsg_mo_dates[0]])/ihsg_by_date[ihsg_mo_dates[0]]*100
                ihsg_ctx = f"IHSG {chg:+.1f}%"
            else:
                ihsg_ctx = ""

            print(f"  {mo:<8}  {fa} {flo} {fhi} {f_label:<14}  "
                  f"{da} {dlo} {dhi} {d_label:<14}  {ihsg_ctx}")

        # ── Spot: Jan 28 crash day ────────────────────────────────────────
        print()
        print("-" * 76)
        print("  SPOT CHECK: Jan 28, 2026 (tariff-crash day, IHSG approx -5%)")
        print("-" * 76)
        jan28_d = date(2026, 1, 28)
        def show_row(label_ver, row):
            if not row:
                print(f"  {label_ver:<12}: no data")
                return
            try:
                cj = json.loads(row["components_json"]) if row["components_json"] else {}
                if isinstance(cj, list):
                    cj = {item["id"]: item.get("score") for item in cj if "id" in item}
            except Exception:
                cj = {}
            ff_v = cj.get("foreign_flow", cj.get("ff"))
            mom_v= cj.get("momentum", cj.get("ihsg_momentum"))
            print(f"  {label_ver:<12}: smooth={float(row['smoothed_score']):5.1f}  "
                  f"raw={float(row['raw_score']):5.1f}  label={row['label']}  "
                  f"| mom={mom_v}  ff={ff_v}")
        show_row("FOREIGN", foreign_by_date.get(jan28_d))
        show_row("DOMESTIC", domestic_by_date.get(jan28_d))
        flow_jan28_orig = await conn.fetchrow(
            "SELECT net_idr_billions FROM foreign_flow_daily_foreign_v WHERE date='2026-01-28'"
        )
        print(f"  Flow Jan 28: FOREIGN original={float(flow_jan28_orig['net_idr_billions']):+.2f}  "
              f"DOMESTIC inverted={INVERTED_FLOW[jan28_d]:+.2f}")

        # ── Spot: Dec 2025 ATH window ─────────────────────────────────────
        print()
        print("-" * 76)
        print("  SPOT CHECK: Dec 2025 (ATH period, IHSG ~8,600)")
        print("-" * 76)
        dec_dates = sorted(d for d in foreign_by_date if str(d)[:7]=="2025-12")
        print(f"  {'DATE':<12} {'F-smooth':>9} {'F-label':<15} {'D-smooth':>9} {'D-label':<15} {'FF-inv':>10}")
        for d in dec_dates:
            fr = foreign_by_date.get(d)
            dr = domestic_by_date.get(d)
            inv_val = INVERTED_FLOW.get(d)
            fs = f"{float(fr['smoothed_score']):9.1f}" if fr else "        -"
            fl = fr["label"] if fr else "—"
            ds = f"{float(dr['smoothed_score']):9.1f}" if dr else "        -"
            dl = dr["label"] if dr else "—"
            iv = f"{inv_val:+10.2f}" if inv_val is not None else "         -"
            print(f"  {str(d):<12} {fs} {fl:<15} {ds} {dl:<15} {iv}")

        # ── Jan 2026 full month ────────────────────────────────────────────
        print()
        print("-" * 76)
        print("  SPOT CHECK: Jan 2026 full month (leading up to Jan 28 crash)")
        print("-" * 76)
        jan_dates = sorted(d for d in foreign_by_date if str(d)[:7]=="2026-01")
        print(f"  {'DATE':<12} {'IHSG':>8} {'F-smooth':>9} {'F-label':<14} "
              f"{'D-smooth':>9} {'D-label':<14} {'inv-flow':>10}")
        for d in jan_dates:
            fr  = foreign_by_date.get(d)
            dr  = domestic_by_date.get(d)
            ihsg_v = ihsg_by_date.get(d)
            inv_val = INVERTED_FLOW.get(d)
            ihsg_s = f"{ihsg_v:8,.0f}" if ihsg_v else "       -"
            fs = f"{float(fr['smoothed_score']):9.1f}" if fr else "        -"
            fl = fr["label"][:13] if fr else "—"
            ds = f"{float(dr['smoothed_score']):9.1f}" if dr else "        -"
            dl = dr["label"][:13] if dr else "—"
            iv = f"{inv_val:+10.2f}" if inv_val is not None else "         -"
            mark = " <<<<" if d == jan28_d else ""
            print(f"  {str(d):<12} {ihsg_s} {fs} {fl:<14} {ds} {dl:<14} {iv}{mark}")

        # ── Aug-Oct summary (key divergence test) ────────────────────────
        print()
        print("-" * 76)
        print("  SPOT CHECK: Aug-Oct 2025 (crash recovery — key divergence test)")
        print("-" * 76)
        early_dates = sorted(d for d in foreign_by_date
                             if date(2025,8,1) <= d <= date(2025,10,31))
        # Show every 4th to keep it readable
        print(f"  {'DATE':<12} {'IHSG':>8} {'F-smooth':>9} {'F-label':<14} "
              f"{'D-smooth':>9} {'D-label':<14}")
        for d in early_dates[::4]:
            fr  = foreign_by_date.get(d)
            dr  = domestic_by_date.get(d)
            ihsg_v = ihsg_by_date.get(d)
            ihsg_s = f"{ihsg_v:8,.0f}" if ihsg_v else "       -"
            fs = f"{float(fr['smoothed_score']):9.1f}" if fr else "        -"
            fl = fr["label"][:13] if fr else "—"
            ds = f"{float(dr['smoothed_score']):9.1f}" if dr else "        -"
            dl = dr["label"][:13] if dr else "—"
            print(f"  {str(d):<12} {ihsg_s} {fs} {fl:<14} {ds} {dl:<14}")

        print()
        print("=" * 76)
        print("BACKUP TABLES RETAINED:")
        print("  fear_greed_index_foreign_v    -- restore point for F&G index")
        print("  foreign_flow_daily_foreign_v  -- restore point for flow data")
        print()
        print("TO RESTORE: python -m backend.scripts.experiment_restore_foreign")
        print("=" * 76)

    finally:
        await conn.close()


asyncio.run(main())

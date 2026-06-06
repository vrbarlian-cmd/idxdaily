#!/usr/bin/env python3
"""
IDX Fear & Greed Index — percentile-rank formula.

Score 0–100, measured relative to recent history (not absolute thresholds):
  < 25   Extreme Fear
  25–45  Fear
  45–55  Neutral
  55–75  Greed
  > 75   Extreme Greed

Six components (weights are nominal; unavailable ones are excluded and
remaining weights are renormalized so they always sum to 1):

  1. IHSG Momentum           — 20%  price vs 125-day MA, percentile vs all history
  2. IHSG Volatility (20d)   — 15%  realized vol, INVERTED percentile vs 250d
  3. Foreign Net Flow        — 20%  manual entry via set_foreign_flow.py (5d rolling sum)
  4. Rupiah Stress           — 15%  USD/IDR vs 50-day MA, INVERTED percentile
  5. Headline Sentiment (1d) — 20%  enriched articles in last 24h
  6. Market Breadth          — 10%  DEPRIORITIZED — "segera hadir" (coming soon)

Requires ihsg_daily and usdidr_daily tables (see sync_market.py).
Stores result to fear_greed_index with full components_json.

Usage (from project root):
    python -m backend.workers.compute_index
    python -m backend.workers.compute_index --days 7

Cron (add to crontab -e):
    # Hourly — upserts today's row each run (DATE PRIMARY KEY)
    0 * * * * cd /path/to/project && python -m backend.workers.compute_index
    # Daily at midnight UTC
    0 0 * * * cd /path/to/project && python -m backend.workers.compute_index
"""

import argparse
import asyncio
import json
import math
import statistics
from datetime import datetime, timezone, timedelta, date
from pathlib import Path

import asyncpg

PROJECT_ROOT = Path(__file__).resolve().parents[2]

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env.local", override=True)

from ._db import get_conn


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

def classify(score: float | None) -> str:
    if score is None:
        return "Data Tidak Cukup"
    if score < 25:  return "Extreme Fear"
    if score < 45:  return "Fear"
    if score < 55:  return "Neutral"
    if score < 75:  return "Greed"
    return "Extreme Greed"


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------

def percentile_rank(value: float, history: list[float]) -> float:
    """
    Returns 0–100: fraction of history values strictly below `value`.
    Higher = value is near the top of its historical range.
    """
    if not history:
        return 50.0
    below = sum(1 for h in history if h < value)
    return (below / len(history)) * 100.0


def rolling_mean(arr: list[float], end: int, window: int) -> float | None:
    if end < window - 1:
        return None
    return sum(arr[end - window + 1: end + 1]) / window


def rolling_stddev(arr: list[float], end: int, window: int) -> float | None:
    if end < window - 1:
        return None
    sl = arr[end - window + 1: end + 1]
    mean = sum(sl) / len(sl)
    variance = sum((v - mean) ** 2 for v in sl) / len(sl)
    return math.sqrt(variance)


# ---------------------------------------------------------------------------
# DB fetchers
# ---------------------------------------------------------------------------

async def fetch_ihsg(conn) -> list[dict]:
    """Returns list of {date, close, volume} sorted by date asc."""
    rows = await conn.fetch("SELECT date, close, volume FROM ihsg_daily ORDER BY date ASC")
    return [{"date": r["date"], "close": float(r["close"]),
             "volume": float(r["volume"]) if r["volume"] is not None else None}
            for r in rows]


async def fetch_usdidr(conn) -> list[dict]:
    rows = await conn.fetch("SELECT date, close FROM usdidr_daily ORDER BY date ASC")
    return [{"date": r["date"], "close": float(r["close"])} for r in rows]


async def fetch_recent_articles(conn, hours: int = 48) -> list[dict]:
    """Fetch articles from the last N hours for headline sentiment (default 48h for smoothing)."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = await conn.fetch(
        """
        SELECT sentiment, impact_score, ai_summary, published_at
        FROM articles
        WHERE published_at >= $1
        """,
        cutoff,
    )
    return [{"sentiment": r["sentiment"],
             "impact_score": float(r["impact_score"]),
             "enriched": r["ai_summary"] is not None,
             "published_at": r["published_at"]}
            for r in rows]


async def fetch_stock_daily(conn, days: int = 25) -> dict[str, list[float]]:
    """Returns {ticker: [close_oldest, ..., close_latest]} for LQ45 breadth computation."""
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=days)
    rows = await conn.fetch(
        """
        SELECT ticker, date, close
        FROM stock_daily
        WHERE date >= $1
        ORDER BY ticker, date ASC
        """,
        cutoff,
    )
    result: dict[str, list[float]] = {}
    for r in rows:
        t = r["ticker"]
        if t not in result:
            result[t] = []
        result[t].append(float(r["close"]))
    return result


async def fetch_foreign_flow(conn, days: int = 90) -> list[dict]:
    """Returns last N days of foreign flow data, sorted date asc."""
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=days)
    rows = await conn.fetch(
        "SELECT date, net_idr_billions FROM foreign_flow_daily WHERE date >= $1 ORDER BY date ASC",
        cutoff,
    )
    return [{"date": r["date"], "net": float(r["net_idr_billions"])}
            for r in rows if r["net_idr_billions"] is not None]


async def fetch_market_breadth(conn, days: int = 90) -> list[dict]:
    """Returns last N days of market breadth (advance/total %), sorted date asc.
    Returns [] if the table doesn't exist yet (graceful for fresh environments)."""
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=days)
    try:
        rows = await conn.fetch(
            "SELECT date, breadth_pct FROM market_breadth_daily "
            "WHERE date >= $1 ORDER BY date ASC",
            cutoff,
        )
    except asyncpg.UndefinedTableError:
        return []
    return [{"date": r["date"], "breadth_pct": float(r["breadth_pct"])}
            for r in rows if r["breadth_pct"] is not None]


async def fetch_previous_smoothed(conn) -> float | None:
    """Return the most recent smoothed_score before today (for EMA carry-forward)."""
    row = await conn.fetchrow(
        "SELECT smoothed_score FROM fear_greed_index WHERE date < CURRENT_DATE ORDER BY date DESC LIMIT 1"
    )
    if row and row["smoothed_score"] is not None:
        return float(row["smoothed_score"])
    return None


async def fetch_all_articles(conn, days: int) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = await conn.fetch(
        "SELECT sentiment, impact_score FROM articles WHERE published_at >= $1",
        cutoff,
    )
    return [{"sentiment": r["sentiment"], "impact_score": float(r["impact_score"])} for r in rows]


# ---------------------------------------------------------------------------
# Component computers
# ---------------------------------------------------------------------------

Component = dict  # {id, label, weight, score, status, raw, raw_label, note}


def make_unavailable(id_: str, label: str, weight: float, note: str) -> Component:
    return {"id": id_, "label": label, "weight": weight,
            "score": None, "status": "unavailable", "raw": None, "raw_label": None, "note": note}


def compute_ihsg_momentum(bars: list[dict]) -> Component:
    MA_WIN = 125
    closes = [b["close"] for b in bars]

    if len(closes) < MA_WIN + 5:
        return make_unavailable(
            "ihsg_momentum", "IHSG Momentum", 0.20,
            f"Perlu ≥{MA_WIN + 5} hari data IHSG"
        )

    devs = []
    for i in range(MA_WIN - 1, len(closes)):
        ma = rolling_mean(closes, i, MA_WIN)
        devs.append(closes[i] / ma - 1)

    current = devs[-1]
    history = devs[:-1]
    score   = percentile_rank(current, history)
    sign    = "+" if current >= 0 else ""

    return {
        "id": "ihsg_momentum", "label": "IHSG Momentum", "weight": 0.20,
        "score": round(score, 1), "status": "active",
        "raw": current,
        "raw_label": f"IHSG {sign}{current * 100:.2f}% vs MA{MA_WIN}",
        "note": None,
    }


def compute_ihsg_volatility(bars: list[dict]) -> Component:
    VOL_WIN  = 20
    MIN_BARS = 40
    closes   = [b["close"] for b in bars]

    if len(closes) < MIN_BARS:
        return make_unavailable(
            "ihsg_volatility", "Volatilitas IHSG", 0.15,
            f"Perlu ≥{MIN_BARS} hari data"
        )

    log_rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]

    vols = []
    for i in range(VOL_WIN - 1, len(log_rets)):
        sd = rolling_stddev(log_rets, i, VOL_WIN)
        vols.append(sd * math.sqrt(252))

    current = vols[-1]
    history = vols[:-1]
    score   = 100.0 - percentile_rank(current, history)  # inverted

    return {
        "id": "ihsg_volatility", "label": "Volatilitas IHSG", "weight": 0.15,
        "score": round(score, 1), "status": "active",
        "raw": current,
        "raw_label": f"Vol {current * 100:.1f}% (ann.)",
        "note": None,
    }


def compute_rupiah_stress(bars: list[dict]) -> Component:
    MA_WIN = 50
    closes = [b["close"] for b in bars]

    if len(closes) < MA_WIN + 1:
        return make_unavailable(
            "rupiah_stress", "Tekanan Rupiah", 0.15,
            f"Perlu ≥{MA_WIN + 1} hari data USD/IDR"
        )

    devs = []
    for i in range(MA_WIN - 1, len(closes)):
        ma = rolling_mean(closes, i, MA_WIN)
        devs.append(closes[i] / ma - 1)

    current = devs[-1]
    history = devs[:-1]
    pct     = percentile_rank(current, history) if history else 50.0
    score   = 100.0 - pct  # inverted
    sign    = "+" if current >= 0 else ""
    status  = "active" if len(history) >= 30 else "stale"

    return {
        "id": "rupiah_stress", "label": "Tekanan Rupiah", "weight": 0.15,
        "score": round(score, 1), "status": status,
        "raw": closes[-1],
        "raw_label": (
            f"USD/IDR {closes[-1]:,.0f} ({sign}{current * 100:.2f}% vs MA{MA_WIN})"
        ),
        "note": "Riwayat terbatas — peringkat persentil kurang akurat" if status == "stale" else None,
    }


def compute_headline_sentiment(rows: list[dict]) -> Component:
    """
    3-day exponentially-weighted headline sentiment.
    Articles in last 24h: weight 1.0 | 24-48h ago: weight 0.4
    Requires ≥10 enriched articles in the last 24h to be active.
    """
    MIN_ENRICHED_24H = 10
    now_ts = datetime.now(timezone.utc)
    cutoff_24h = now_ts - timedelta(hours=24)
    cutoff_48h = now_ts - timedelta(hours=48)

    enriched_24h = [r for r in rows if r["enriched"] and r.get("published_at") and r["published_at"] >= cutoff_24h]
    total_24h    = [r for r in rows if r.get("published_at") and r["published_at"] >= cutoff_24h]
    n_24h        = len(enriched_24h)
    total_n_24h  = len(total_24h)

    if n_24h < MIN_ENRICHED_24H:
        return make_unavailable(
            "headline_sentiment", "Sentimen Headline", 0.20,
            f"Hanya {n_24h}/{total_n_24h} artikel terenrichment dalam 24h (min {MIN_ENRICHED_24H})"
        )

    # Weighted score: recent articles count more
    w_bull = w_bear = total_w = 0.0
    for r in rows:
        if not r["enriched"] or not r.get("published_at"):
            continue
        pub = r["published_at"]
        if pub >= cutoff_24h:
            w = 1.0
        elif pub >= cutoff_48h:
            w = 0.4
        else:
            continue
        if r["sentiment"] == "BULLISH":
            w_bull += w
        elif r["sentiment"] == "BEARISH":
            w_bear += w
        total_w += w

    if total_w == 0:
        return make_unavailable("headline_sentiment", "Sentimen Headline", 0.20,
                                "Tidak ada artikel dengan bobot")

    score = 50.0 + ((w_bull - w_bear) / total_w) * 50.0
    enrich_pct = round((n_24h / max(total_n_24h, 1)) * 100)
    status = "active" if enrich_pct >= 30 else "stale"

    # For raw_label: show 24h breakdown
    bull_24 = sum(1 for r in enriched_24h if r["sentiment"] == "BULLISH")
    bear_24 = sum(1 for r in enriched_24h if r["sentiment"] == "BEARISH")
    neut_24 = n_24h - bull_24 - bear_24

    return {
        "id": "headline_sentiment", "label": "Sentimen Headline", "weight": 0.20,
        "score": round(score, 1), "status": status,
        "raw": score,
        "raw_label": f"{bull_24}B / {bear_24}Be / {neut_24}N (24h, smoothed 48h)",
        "note": (
            f"Hanya {n_24h}/{total_n_24h} artikel terenrichment — sinyal kurang akurat"
            if status == "stale" else None
        ),
    }


def compute_breadth(breadth_rows: list[dict]) -> Component:
    """
    Market Breadth — % of stocks advancing (advance/total), manually entered
    daily via set_market_breadth.py. Percentile-ranked vs 90-day history.

    High breadth (many stocks up) = broad participation = Greed.
    Low breadth (few up) = narrow/weak market = Fear.
    Requires >= 30 data points to activate (percentile rank needs history depth).
    """
    MIN_ROWS = 30

    if len(breadth_rows) < MIN_ROWS:
        n = len(breadth_rows)
        note = (
            "Diperbarui manual setiap hari via set_market_breadth.py."
            if n == 0
            else f"Baru {n} hari data — butuh min {MIN_ROWS} untuk aktif"
        )
        return make_unavailable("breadth", "Market Breadth", 0.10, note)

    pcts    = [r["breadth_pct"] for r in breadth_rows]
    current = pcts[-1]
    history = pcts[:-1]
    score   = percentile_rank(current, history)

    return {
        "id": "breadth", "label": "Market Breadth", "weight": 0.10,
        "score": round(score, 1), "status": "active",
        "raw": current,
        "raw_label": (
            f"{current:.0f}% saham menguat "
            f"(p{score:.0f}, {len(breadth_rows)} hari data)"
        ),
        "note": None,
    }


def compute_foreign_flow(flow_rows: list[dict]) -> Component:
    """
    Foreign net flow — manually entered daily via set_foreign_flow.py.

    Uses a 5-day rolling sum (smooths single-day noise) percentile-ranked
    vs all historical rolling sums.  Requires ≥2 data points to activate.
    """
    ROLL_WIN = 5
    MIN_ROWS = 2   # need at least 2 data points for a percentile comparison

    if len(flow_rows) < MIN_ROWS:
        n = len(flow_rows)
        note = (
            "Diperbarui manual setiap hari setelah penutupan pasar."
            if n == 0
            else f"Baru {n} hari data — butuh min {MIN_ROWS} untuk aktif"
        )
        return make_unavailable("foreign_flow", "Aliran Asing", 0.20, note)

    # Compute rolling sum at each position
    nets = [r["net"] for r in flow_rows]
    roll_sums = []
    for i in range(len(nets)):
        window = nets[max(0, i - ROLL_WIN + 1): i + 1]
        roll_sums.append(sum(window))

    current = roll_sums[-1]
    history = roll_sums[:-1]

    # With small history percentile rank is coarse but valid
    score = percentile_rank(current, history) if history else 50.0
    sign  = "+" if current >= 0 else ""

    return {
        "id": "foreign_flow", "label": "Aliran Asing", "weight": 0.20,
        "score": round(score, 1), "status": "active",
        "raw": current,
        "raw_label": (
            f"5d net {sign}{current:.0f} Rp miliar "
            f"(p{score:.0f}, {len(flow_rows)} hari data)"
        ),
        "note": None,
    }


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def aggregate(components: list[Component]) -> tuple[float | None, str, int]:
    active     = [c for c in components if c["score"] is not None]
    active_cnt = len(active)

    if active_cnt < 2:
        return None, "Data Tidak Cukup", active_cnt

    total_w  = sum(c["weight"] for c in active)
    weighted = sum(c["score"] * c["weight"] for c in active)
    score    = round(weighted / total_w, 1)
    return score, classify(score), active_cnt


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------

async def save_index(
    conn,
    result: dict,
    all_articles: list[dict],
    days: int,
    smoothed_score: float | None,
) -> None:
    today = datetime.now(timezone.utc).date()
    n = len(all_articles)
    if n > 0:
        bull_n = sum(1 for r in all_articles if r["sentiment"] == "BULLISH")
        bear_n = sum(1 for r in all_articles if r["sentiment"] == "BEARISH")
        neut_n = n - bull_n - bear_n
        bull_pct = round(bull_n / n * 100, 1)
        bear_pct = round(bear_n / n * 100, 1)
        neut_pct = round(neut_n / n * 100, 1)
    else:
        bull_pct = bear_pct = neut_pct = 0.0

    await conn.execute(
        """
        INSERT INTO fear_greed_index
          (date, score, label, bullish_pct, bearish_pct, neutral_pct,
           total_articles, window_days, active_components, components_json,
           raw_score, smoothed_score)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
        ON CONFLICT (date) DO UPDATE
          SET score             = EXCLUDED.score,
              label             = EXCLUDED.label,
              bullish_pct       = EXCLUDED.bullish_pct,
              bearish_pct       = EXCLUDED.bearish_pct,
              neutral_pct       = EXCLUDED.neutral_pct,
              total_articles    = EXCLUDED.total_articles,
              window_days       = EXCLUDED.window_days,
              active_components = EXCLUDED.active_components,
              components_json   = EXCLUDED.components_json,
              raw_score         = EXCLUDED.raw_score,
              smoothed_score    = EXCLUDED.smoothed_score,
              updated_at        = NOW()
        """,
        today,
        smoothed_score,          # `score` column now stores the SMOOTHED value for display
        result["label"],
        bull_pct, bear_pct, neut_pct,
        n, days,
        result["active_components"],
        json.dumps(result["components"]),
        result["raw_score"],     # raw_score = unsmoothed weighted average
        smoothed_score,          # smoothed_score = EMA-smoothed display value
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run(days: int) -> None:
    conn = await get_conn()
    try:
        # Fetch all data sources sequentially (single asyncpg connection)
        ihsg_bars        = await fetch_ihsg(conn)
        usdidr_bars      = await fetch_usdidr(conn)
        article_rows_48h = await fetch_recent_articles(conn, hours=48)  # 48h for smoothed headline
        article_rows_nd  = await fetch_all_articles(conn, days=days)
        stock_prices     = await fetch_stock_daily(conn, days=35)       # 35 cal days ≈ 25 trading days for MA20
        flow_rows        = await fetch_foreign_flow(conn, days=90)
        breadth_rows     = await fetch_market_breadth(conn, days=90)
        prev_smoothed    = await fetch_previous_smoothed(conn)

        components = [
            compute_ihsg_momentum(ihsg_bars),
            compute_ihsg_volatility(ihsg_bars),
            compute_foreign_flow(flow_rows),
            compute_rupiah_stress(usdidr_bars),
            compute_headline_sentiment(article_rows_48h),
            compute_breadth(breadth_rows),
        ]

        raw_score, label, active_cnt = aggregate(components)

        # ── EMA Smoothing (A3): 70% today's raw + 30% yesterday's smoothed ──
        EMA_ALPHA = 0.7
        if raw_score is not None:
            if prev_smoothed is not None:
                smoothed_score = round(EMA_ALPHA * raw_score + (1 - EMA_ALPHA) * prev_smoothed, 1)
            else:
                smoothed_score = raw_score   # first ever run — no prior value
        else:
            smoothed_score = prev_smoothed   # carry forward if today has no score

        # Classify based on smoothed score for display
        display_score = smoothed_score
        display_label = label if raw_score is not None else "Data Tidak Cukup"
        if display_score is not None and raw_score is None:
            display_label = classify(display_score)  # re-classify from smoothed

        result = {
            "raw_score":         raw_score,
            "score":             display_score,
            "label":             display_label,
            "active_components": active_cnt,
            "components":        components,
        }

        await save_index(conn, result, article_rows_nd, days, smoothed_score)

        # ── Print report ──────────────────────────────────────────────────
        print(f"\n{'='*64}")
        print(f"  IDX Fear & Greed Index  (last {days}d)")
        print(f"{'='*64}")
        print(f"  Raw score      : {raw_score if raw_score is not None else 'N/A'} / 100")
        print(f"  Smoothed score : {smoothed_score if smoothed_score is not None else 'N/A'} / 100  (EMA a={EMA_ALPHA})")
        print(f"  Label          : {display_label}")
        print(f"  Active comps   : {active_cnt}/6")
        print()

        for c in components:
            s = f"{c['score']:.1f}" if c['score'] is not None else "  —"
            status_icon = {"active": "OK", "stale": "!!", "unavailable": "--"}.get(c["status"], "?")
            wt = int(c["weight"] * 100)
            print(f"  [{status_icon}] {c['label']:<25} ({wt:2d}%)  {s:>5}")
            if c.get("raw_label"):
                print(f"        {c['raw_label']}")
            if c.get("note"):
                print(f"        NOTE: {c['note']}")

        print(f"\n  Articles (48h)  : {len(article_rows_48h)}")
        print(f"  Articles ({days:2d}d)  : {len(article_rows_nd)}")
        print(f"  LQ45 stocks    : {len(stock_prices)}")
        print(f"  Foreign flow d : {len(flow_rows)}")
        print(f"  Breadth days   : {len(breadth_rows)}")
        print(f"{'='*64}\n")

    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="IDX Fear & Greed Index (percentile-rank formula)")
    parser.add_argument("--days", type=int, default=7, help="Window for article stats")
    args = parser.parse_args()
    asyncio.run(run(args.days))


if __name__ == "__main__":
    main()

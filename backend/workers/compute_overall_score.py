#!/usr/bin/env python3
"""
IDX Fear & Greed — Overall Score (blended index).

Reads today's Foreign Score and Domestic Score and produces a
weighted blend stored in overall_sentiment_daily.

NEVER modifies fear_greed_index (Foreign Score).
NEVER modifies fear_greed_psychology (Domestic Score).

Blend logic:
  When domestic data present:
    overall = W_FOREIGN × foreign_score + W_DOMESTIC × domestic_score
  When domestic data absent:
    overall = foreign_score  (graceful fallback — no fabrication)

Divergence:
  When |foreign - domestic| >= DIVERGENCE_THRESHOLD (default 20):
    A contextual signal is flagged in divergence_signal.
    OJK-safe framing: sinyal sentimen, NOT buy/sell advice.

Usage (called automatically by set_domestic_flow.py and set_foreign_flow.py):
    python -m backend.workers.compute_overall_score
"""

import asyncio
import sys
sys.stdout.reconfigure(encoding="utf-8")
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env.local", override=True)

from ._db import get_conn


# ── Config (tune these without code change) ────────────────────────────────────

W_FOREIGN           = 0.60   # Foreign Score weight in Overall
W_DOMESTIC          = 0.40   # Domestic Score weight in Overall
EMA_ALPHA           = 0.7
DIVERGENCE_THRESHOLD = 20    # point gap to flag divergence signal


# ── Label ──────────────────────────────────────────────────────────────────────

def classify(score: float | None) -> str:
    if score is None: return "Data Tidak Cukup"
    if score < 25:    return "Extreme Fear"
    if score < 45:    return "Fear"
    if score < 55:    return "Neutral"
    if score < 75:    return "Greed"
    return "Extreme Greed"


# ── Divergence interpretation ──────────────────────────────────────────────────

def divergence_signal(
    foreign_score: float,
    domestic_score: float,
) -> tuple[str | None, str | None]:
    """
    Returns (signal_key, message) or (None, None) if no divergence.

    Signal keys (machine-readable for UI):
      'ritel_euforia'   — retail greed vs foreign fear
      'asing_optimis'   — foreign greed vs retail fear
      'sejalan_optimis' — both greedy
      'sejalan_pesimis' — both fearful
      None              — no strong divergence
    """
    gap = domestic_score - foreign_score

    if gap >= DIVERGENCE_THRESHOLD:
        # Retail more optimistic than foreign
        return (
            "ritel_euforia",
            "Ritel aktif saat asing berhati-hati — waspadai potensi koreksi. "
            "Ini adalah sinyal sentimen, bukan rekomendasi jual/beli."
        )
    elif gap <= -DIVERGENCE_THRESHOLD:
        # Foreign more optimistic than retail
        return (
            "asing_optimis",
            "Asing lebih optimis daripada ritel — waspadai potensi pemulihan. "
            "Ini adalah sinyal sentimen, bukan rekomendasi jual/beli."
        )
    else:
        return None, None


# ── Main ───────────────────────────────────────────────────────────────────────

async def run() -> None:
    conn = await get_conn()
    today = datetime.now(timezone.utc).date()

    try:
        # ── Get today's Foreign Score ─────────────────────────────────────────
        fg_row = await conn.fetchrow(
            "SELECT smoothed_score, label FROM fear_greed_index "
            "WHERE date = $1",
            today,
        )
        # Fall back to latest if today not yet written
        if not fg_row:
            fg_row = await conn.fetchrow(
                "SELECT smoothed_score, label FROM fear_greed_index "
                "ORDER BY date DESC LIMIT 1"
            )

        if not fg_row or fg_row["smoothed_score"] is None:
            print("[Overall Score] Foreign Score not available - cannot compute.")
            return

        foreign_score = float(fg_row["smoothed_score"])

        # ── Get today's Domestic Score ────────────────────────────────────────
        dom_row = await conn.fetchrow(
            "SELECT smoothed_score, has_retail_data "
            "FROM fear_greed_psychology WHERE date = $1",
            today,
        )
        # Fall back to latest if today not computed yet
        if not dom_row:
            dom_row = await conn.fetchrow(
                "SELECT smoothed_score, has_retail_data "
                "FROM fear_greed_psychology ORDER BY date DESC LIMIT 1"
            )

        has_domestic    = bool(dom_row and dom_row["has_retail_data"])
        domestic_score  = float(dom_row["smoothed_score"]) if dom_row and dom_row["smoothed_score"] is not None else None

        # ── Compute Overall Score ─────────────────────────────────────────────
        if has_domestic and domestic_score is not None:
            raw_score = round(W_FOREIGN * foreign_score + W_DOMESTIC * domestic_score, 1)
        else:
            # Graceful fallback: Overall = Foreign when domestic absent
            raw_score = round(foreign_score, 1)

        # ── EMA smoothing ─────────────────────────────────────────────────────
        prev_row = await conn.fetchrow(
            "SELECT smoothed_score FROM overall_sentiment_daily "
            "WHERE date < $1 ORDER BY date DESC LIMIT 1",
            today,
        )
        prev_smoothed = float(prev_row["smoothed_score"]) if prev_row and prev_row["smoothed_score"] else None

        smoothed = (
            round(EMA_ALPHA * raw_score + (1 - EMA_ALPHA) * prev_smoothed, 1)
            if prev_smoothed is not None else raw_score
        )

        label = classify(smoothed)

        # ── Divergence signal ─────────────────────────────────────────────────
        div_magnitude: float | None = None
        div_signal:    str  | None  = None
        div_message:   str  | None  = None

        if has_domestic and domestic_score is not None:
            div_magnitude = round(abs(domestic_score - foreign_score), 1)
            div_signal, div_message = divergence_signal(foreign_score, domestic_score)

        # ── Upsert to overall_sentiment_daily ─────────────────────────────────
        await conn.execute("""
            INSERT INTO overall_sentiment_daily (
              date, score, raw_score, smoothed_score, label,
              foreign_score, domestic_score,
              foreign_weight, domestic_weight,
              has_domestic_data,
              divergence_magnitude, divergence_signal,
              updated_at
            ) VALUES (
              $1, $2, $3, $4, $5,
              $6, $7, $8, $9, $10,
              $11, $12,
              NOW()
            )
            ON CONFLICT (date) DO UPDATE SET
              score               = EXCLUDED.score,
              raw_score           = EXCLUDED.raw_score,
              smoothed_score      = EXCLUDED.smoothed_score,
              label               = EXCLUDED.label,
              foreign_score       = EXCLUDED.foreign_score,
              domestic_score      = EXCLUDED.domestic_score,
              foreign_weight      = EXCLUDED.foreign_weight,
              domestic_weight     = EXCLUDED.domestic_weight,
              has_domestic_data   = EXCLUDED.has_domestic_data,
              divergence_magnitude = EXCLUDED.divergence_magnitude,
              divergence_signal   = EXCLUDED.divergence_signal,
              updated_at          = NOW()
        """,
            today, smoothed, raw_score, smoothed, label,
            foreign_score, domestic_score,
            W_FOREIGN, W_DOMESTIC, has_domestic,
            div_magnitude, div_signal,
        )

        # ── Print report ──────────────────────────────────────────────────────
        print(f"\n{'='*62}")
        print(f"  IDX Overall Sentiment Score")
        print(f"{'='*62}")
        print(f"  Foreign Score  : {foreign_score:.1f}  (weight {int(W_FOREIGN*100)}%)")
        dom_str = f"{domestic_score:.1f}" if domestic_score is not None else "—"
        fallback_str = "  [fallback: Foreign]" if not has_domestic else ""
        print(f"  Domestic Score : {dom_str}  (weight {int(W_DOMESTIC*100)}%){fallback_str}")
        print(f"  Raw overall    : {raw_score:.1f} / 100")
        print(f"  Smoothed       : {smoothed:.1f} / 100")
        print(f"  Label          : {label}")
        if div_signal:
            print(f"\n  Divergence     : {div_magnitude:.0f}pt gap -> {div_signal}")
            print(f"  Message        : {div_message}")
        print(f"\n  *** fear_greed_index NOT TOUCHED ***")
        print(f"{'='*62}\n")

    finally:
        await conn.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()

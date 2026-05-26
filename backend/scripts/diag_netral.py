#!/usr/bin/env python3
"""
Diagnose the 'has summary but NEUTRAL+5.0' bug.
Run: python -m backend.scripts.diag_netral
"""
import asyncio
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env.local", override=True)

from backend.workers._db import get_conn


async def diag():
    conn = await get_conn()

    total      = await conn.fetchval("SELECT COUNT(*) FROM articles")
    enriched   = await conn.fetchval(
        "SELECT COUNT(*) FROM articles WHERE ai_summary IS NOT NULL AND ai_summary <> ''"
    )
    backlog    = await conn.fetchval(
        "SELECT COUNT(*) FROM articles WHERE ai_summary IS NULL"
    )
    empty_sum  = await conn.fetchval(
        "SELECT COUNT(*) FROM articles WHERE ai_summary = ''"
    )
    half_done  = await conn.fetchval(
        """SELECT COUNT(*) FROM articles
           WHERE ai_summary IS NOT NULL AND ai_summary <> ''
             AND sentiment = 'NEUTRAL' AND impact_score = 5.0"""
    )

    print(f"Total articles:                 {total}")
    print(f"Enriched (real summary):        {enriched}")
    print(f"Backlog (ai_summary IS NULL):   {backlog}")
    print(f"Empty summary (ai_summary=''):  {empty_sum}")
    print(f"Has summary BUT NEUTRAL+5.0:    {half_done}  <-- THE BUG")

    # Sample of the half-enriched
    samples = await conn.fetch(
        """SELECT title, ai_summary, sentiment, impact_score, category, published_at
           FROM articles
           WHERE ai_summary IS NOT NULL AND ai_summary <> ''
             AND sentiment = 'NEUTRAL' AND impact_score = 5.0
           ORDER BY published_at DESC
           LIMIT 8"""
    )
    print()
    print("=== SAMPLE: has summary, but NEUTRAL+5.0 ===")
    for s in samples:
        print(f"  [{s['published_at']}]")
        print(f"  title:   {s['title'][:80]}")
        print(f"  summary: {s['ai_summary'][:100]}")
        print(f"  sentiment={s['sentiment']}  impact={s['impact_score']}  category={s['category']}")
        print()

    # Check the three specific tickers
    for sym in ["GOTO", "BUMI", "SMGR"]:
        rows = await conn.fetch(
            """SELECT a.title, a.ai_summary, a.sentiment, a.impact_score, a.published_at
               FROM articles a
               JOIN tickers t ON t.id = a.ticker_id
               WHERE t.symbol = $1
               ORDER BY a.published_at DESC
               LIMIT 5""",
            sym,
        )
        print(f"=== {sym} (last 5 articles) ===")
        for r in rows:
            has_sum = bool(r["ai_summary"])
            print(f"  [{r['published_at']}] {r['title'][:60]}")
            print(f"    summary={has_sum}  sentiment={r['sentiment']}  impact={r['impact_score']}")
        print()

    # Check ticker_mentions for GOTO/BUMI/SMGR — maybe article.sentiment is fine
    # but the mentions table is what's being displayed
    for sym in ["GOTO", "BUMI", "SMGR"]:
        rows = await conn.fetch(
            """SELECT a.title, a.sentiment AS art_sent, a.impact_score AS art_imp,
                      tm.sentiment AS men_sent, tm.impact_score AS men_imp, tm.ai_summary AS men_sum
               FROM ticker_mentions tm
               JOIN articles a ON a.id = tm.article_id
               JOIN tickers t ON t.id = tm.ticker_id
               WHERE t.symbol = $1
               ORDER BY a.published_at DESC
               LIMIT 5""",
            sym,
        )
        print(f"=== {sym} ticker_mentions (last 5) ===")
        for r in rows:
            print(f"  {r['title'][:55]}")
            print(f"    article: sent={r['art_sent']}  imp={r['art_imp']}")
            print(f"    mention: sent={r['men_sent']}  imp={r['men_imp']}  "
                  f"sum={'YES' if r['men_sum'] else 'NULL'}")
        print()

    await conn.close()


if __name__ == "__main__":
    asyncio.run(diag())

#!/usr/bin/env python3
"""
Diagnose macro/market news classification.
Run: python -m backend.scripts.diag_macro
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

    # 1. Check MSCI/FTSE article specifically
    print("=== MSCI/FTSE/Russell articles ===")
    rows = await conn.fetch(
        """
        SELECT id, title, category, sentiment, impact_score, ai_summary,
               ticker_id, published_at, source
        FROM articles
        WHERE title ILIKE '%MSCI%'
           OR title ILIKE '%FTSE%'
           OR title ILIKE '%Russell%'
           OR title ILIKE '%indeks global%'
           OR title ILIKE '%bobot indeks%'
        ORDER BY published_at DESC
        LIMIT 10
        """
    )
    for r in rows:
        print(f"  [{r['published_at']}] {r['source']}")
        print(f"  title:    {r['title']}")
        print(f"  category={r['category']}  sentiment={r['sentiment']}  impact={r['impact_score']}")
        print(f"  ticker_id={'NULL' if not r['ticker_id'] else 'SET'}  summary={'YES' if r['ai_summary'] else 'NULL'}")
        if r['ai_summary']:
            print(f"  summary:  {r['ai_summary'][:120]}")
        print()

    # 2. Current macro articles in the DB (category=MACRO/REGULATORY/SECTOR, no ticker)
    print("=== NULL-ticker MACRO/REGULATORY articles (last 10) ===")
    rows2 = await conn.fetch(
        """
        SELECT title, category, sentiment, impact_score, published_at, source
        FROM articles
        WHERE ticker_id IS NULL
          AND category IN ('MACRO', 'REGULATORY', 'SECTOR')
          AND ai_summary IS NOT NULL
        ORDER BY published_at DESC
        LIMIT 10
        """
    )
    for r in rows2:
        print(f"  [{r['published_at']}] {r['source']}")
        print(f"  [{r['category']}] [{r['sentiment']}] [{r['impact_score']}] {r['title'][:80]}")
    print()

    # 3. All articles classified as MACRO/REGULATORY (including ticker-attached ones)
    print("=== All MACRO/REGULATORY articles, last 7d ===")
    rows3 = await conn.fetch(
        """
        SELECT title, category, sentiment, impact_score, ticker_id, published_at, source
        FROM articles
        WHERE category IN ('MACRO', 'REGULATORY')
          AND ai_summary IS NOT NULL
          AND published_at >= NOW() - INTERVAL '7 days'
        ORDER BY impact_score DESC, published_at DESC
        LIMIT 15
        """
    )
    for r in rows3:
        has_ticker = "ticker" if r['ticker_id'] else "NO-ticker"
        print(f"  [{r['sentiment']}] [{r['impact_score']}] [{has_ticker}] {r['title'][:75]}")
    print()

    # 4. High-impact SECTOR articles (these often contain index/market-level news)
    print("=== High-impact SECTOR articles, last 7d ===")
    rows4 = await conn.fetch(
        """
        SELECT title, category, sentiment, impact_score, ticker_id, published_at, source
        FROM articles
        WHERE category = 'SECTOR'
          AND impact_score >= 6.0
          AND ai_summary IS NOT NULL
          AND published_at >= NOW() - INTERVAL '7 days'
        ORDER BY impact_score DESC, published_at DESC
        LIMIT 10
        """
    )
    for r in rows4:
        has_ticker = "ticker" if r['ticker_id'] else "NO-ticker"
        print(f"  [{r['sentiment']}] [{r['impact_score']}] [{has_ticker}] {r['title'][:75]}")
    print()

    # 5. What categories/sentiments does our macro news look like overall?
    print("=== Category distribution (last 7d) ===")
    rows5 = await conn.fetch(
        """
        SELECT category, sentiment, COUNT(*) as cnt
        FROM articles
        WHERE ai_summary IS NOT NULL
          AND published_at >= NOW() - INTERVAL '7 days'
        GROUP BY category, sentiment
        ORDER BY category, cnt DESC
        """
    )
    for r in rows5:
        print(f"  {r['category']:15s} {r['sentiment']:10s} {r['cnt']}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(diag())

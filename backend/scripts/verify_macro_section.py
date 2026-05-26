#!/usr/bin/env python3
"""
Verify what MacroMarketNews component will show.
Mirrors the exact Prisma query from MacroMarketNews.tsx.
Run: python -m backend.scripts.verify_macro_section
"""
import asyncio
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env.local", override=True)

from backend.workers._db import get_conn


async def verify():
    conn = await get_conn()

    # Mirror MacroMarketNews.tsx query exactly
    rows = await conn.fetch(
        """
        SELECT id, title, category, sentiment, impact_score, ai_summary,
               ticker_id, published_at, source, url
        FROM articles
        WHERE ai_summary IS NOT NULL
          AND (
            -- Tier 1: pure market-level (NULL ticker), impact >= 5.5
            (ticker_id IS NULL
             AND category IN ('MACRO', 'REGULATORY', 'SECTOR')
             AND impact_score >= 5.5)
            OR
            -- Tier 2: MACRO/REGULATORY with ticker, very high impact only
            (ticker_id IS NOT NULL
             AND category IN ('MACRO', 'REGULATORY')
             AND impact_score >= 7.5)
          )
        ORDER BY published_at DESC, impact_score DESC
        LIMIT 6
        """
    )

    print(f"MacroMarketNews will show {len(rows)} articles:\n")
    for i, r in enumerate(rows, 1):
        has_ticker = "(ticker)" if r["ticker_id"] else "(market-level)"
        print(f"  {i}. [{r['category']}] [{r['sentiment']}] [{r['impact_score']}] {has_ticker}")
        print(f"     {r['published_at'].strftime('%Y-%m-%d %H:%M')} | {r['source']}")
        print(f"     {r['title'][:80]}")
        if r["ai_summary"]:
            print(f"     >> {r['ai_summary'][:100]}")
        print()

    # Check MSCI/FTSE articles specifically
    print("=== MSCI/FTSE articles that appear in this section ===")
    msci = [r for r in rows if any(
        kw in r["title"].upper()
        for kw in ["MSCI", "FTSE", "RUSSELL", "INDEKS GLOBAL", "BOBOT INDEKS"]
    )]
    if msci:
        for r in msci:
            print(f"  [{r['sentiment']}] [{r['impact_score']}] {r['title'][:80]}")
    else:
        print("  None in top-6. Checking broader DB for MSCI/FTSE macro articles...")
        all_msci = await conn.fetch(
            """
            SELECT title, category, sentiment, impact_score, ticker_id, published_at, source
            FROM articles
            WHERE (title ILIKE '%MSCI%' OR title ILIKE '%FTSE%' OR title ILIKE '%Russell%')
              AND ai_summary IS NOT NULL
              AND (
                  (ticker_id IS NULL AND impact_score >= 5.5)
                  OR (category IN ('MACRO','REGULATORY') AND impact_score >= 7.5)
              )
            ORDER BY published_at DESC
            LIMIT 5
            """
        )
        for r in all_msci:
            has_ticker = "(ticker)" if r["ticker_id"] else "(market-level)"
            print(f"  [{r['sentiment']}] [{r['impact_score']}] {has_ticker} {r['title'][:75]}")
            print(f"  -> Would appear? impact >= 5.5: {r['impact_score'] >= 5.5}")

    # Check the specific "BEI Siapkan Strategi Masukkan Saham RI ke MSCI/FTSE" article
    print("\n=== 'BEI Siapkan Strategi MSCI/FTSE' article search ===")
    bei = await conn.fetch(
        """
        SELECT title, category, sentiment, impact_score, ticker_id, published_at, source, ai_summary
        FROM articles
        WHERE (title ILIKE '%BEI%' AND (title ILIKE '%MSCI%' OR title ILIKE '%FTSE%'))
           OR title ILIKE '%masukkan saham%'
           OR title ILIKE '%strategi masuk%indeks%'
           OR (title ILIKE '%inklusi%' AND (title ILIKE '%MSCI%' OR title ILIKE '%FTSE%'))
        ORDER BY published_at DESC
        LIMIT 5
        """
    )
    if bei:
        for r in bei:
            print(f"  FOUND: [{r['sentiment']}] [{r['impact_score']}]")
            print(f"  {r['title']}")
            if r["ai_summary"]:
                print(f"  >> {r['ai_summary'][:120]}")
    else:
        print("  Not in DB yet — not scraped. Once ingested and enriched,")
        print("  it would be classified MACRO/REGULATORY, BULLISH, impact ~7.5-9.0,")
        print("  and appear at the TOP of this section (newest + high impact).")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(verify())

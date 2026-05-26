#!/usr/bin/env python3
"""Check IDX Channel scraper health and macro source distribution."""
import asyncio
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env.local", override=True)
from backend.workers._db import get_conn


async def run():
    conn = await get_conn()

    # 1. All sources last 24h
    rows = await conn.fetch("""
        SELECT source, COUNT(*) AS cnt
        FROM articles
        WHERE published_at >= NOW() - INTERVAL '24 hours'
        GROUP BY source
        ORDER BY cnt DESC
    """)
    print("=== All sources — last 24h ===")
    for r in rows:
        print(f"  {r['source']:35s} {r['cnt']:4d}")

    # 2. IDX Channel last 7 days by category
    idx7 = await conn.fetch("""
        SELECT category, COUNT(*) AS cnt
        FROM articles
        WHERE published_at >= NOW() - INTERVAL '7 days'
          AND source ILIKE '%idx%channel%'
        GROUP BY category
        ORDER BY cnt DESC
    """)
    print("\n=== IDX Channel — last 7 days by category ===")
    if idx7:
        for r in idx7:
            print(f"  [{r['category']}] {r['cnt']}")
    else:
        print("  0 articles — scraper may be broken or source name differs")

    # 3. Check exact source name variants containing 'idx'
    idx_names = await conn.fetch("""
        SELECT DISTINCT source
        FROM articles
        WHERE source ILIKE '%idx%'
        ORDER BY source
    """)
    print("\n=== Distinct source names containing 'idx' ===")
    for r in idx_names:
        print(f"  {r['source']}")

    # 4. MacroMarketNews section — per source last 7d
    macro = await conn.fetch("""
        SELECT source, COUNT(*) AS cnt
        FROM articles
        WHERE published_at >= NOW() - INTERVAL '7 days'
          AND ai_summary IS NOT NULL
          AND (
            (ticker_id IS NULL AND category = 'MACRO'      AND impact_score >= 7.0)
            OR (ticker_id IS NULL AND category = 'REGULATORY' AND impact_score >= 5.5)
            OR (ticker_id IS NOT NULL AND category IN ('MACRO','REGULATORY') AND impact_score >= 7.5)
          )
        GROUP BY source
        ORDER BY cnt DESC
    """)
    print("\n=== MacroMarketNews section — per source last 7d ===")
    if macro:
        for r in macro:
            print(f"  {r['source']:35s} {r['cnt']:4d}")
    else:
        print("  No macro articles in section yet")

    await conn.close()


asyncio.run(run())

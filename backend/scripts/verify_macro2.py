#!/usr/bin/env python3
import asyncio
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env.local", override=True)
from backend.workers._db import get_conn

async def run():
    conn = await get_conn()
    rows = await conn.fetch("""
        SELECT title, category, sentiment, impact_score, ticker_id, published_at, source
        FROM articles
        WHERE ai_summary IS NOT NULL
          AND (
            (ticker_id IS NULL AND category = 'MACRO' AND impact_score >= 7.0)
            OR (ticker_id IS NULL AND category = 'REGULATORY' AND impact_score >= 5.5)
            OR (ticker_id IS NOT NULL AND category IN ('MACRO','REGULATORY') AND impact_score >= 7.5)
          )
        ORDER BY published_at DESC, impact_score DESC
        LIMIT 6
    """)
    print(f"MacroMarketNews (improved filter) => {len(rows)} articles:\n")
    for i, r in enumerate(rows, 1):
        t = "(market-level)" if not r["ticker_id"] else "(with ticker)"
        print(f"  {i}. [{r['category']}][{r['sentiment']}][{r['impact_score']}] {t}")
        print(f"     {r['published_at'].strftime('%Y-%m-%d %H:%M')} | {r['source']}")
        print(f"     {r['title'][:80]}")
        print()
    await conn.close()

asyncio.run(run())

"""Check enrichment status and show PTRO examples."""
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(".env"))
load_dotenv(Path(".env.local"), override=True)

import asyncpg

async def check():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        total = await conn.fetchval("SELECT COUNT(*) FROM articles")
        unenriched = await conn.fetchval("SELECT COUNT(*) FROM articles WHERE ai_summary IS NULL")
        gn_url_unenriched = await conn.fetchval("SELECT COUNT(*) FROM articles WHERE url LIKE '%news.google.com%' AND ai_summary IS NULL")

        print(f"Total articles:             {total}")
        print(f"Unenriched:                 {unenriched}")
        print(f"GN-URL unenriched:          {gn_url_unenriched}")
        print()

        ptro_articles = await conn.fetch("""
            SELECT a.id, a.title, a.ai_summary, a.sentiment, a.impact_score, a.source, a.body, a.url, a.published_at
            FROM articles a
            JOIN ticker_mentions tm ON tm.article_id = a.id
            JOIN tickers t ON t.id = tm.ticker_id
            WHERE t.symbol = 'PTRO' AND a.ai_summary IS NOT NULL
            GROUP BY a.id, a.title, a.ai_summary, a.sentiment, a.impact_score, a.source, a.body, a.url, a.published_at
            ORDER BY a.published_at DESC
            LIMIT 5
        """)

        print(f"PTRO enriched articles ({len(ptro_articles)} shown):")
        for i, row in enumerate(ptro_articles, 1):
            is_gn = "[GN]" if "news.google.com" in (row["url"] or "") else "[direct]"
            print(f"\n  [{i}] {is_gn} {row['source']}")
            print(f"  Title: {row['title']}")
            print(f"  Sentiment: {row['sentiment']}  Impact: {row['impact_score']}")
            print(f"  Summary: {row['ai_summary'][:200]}")

    finally:
        await conn.close()

asyncio.run(check())

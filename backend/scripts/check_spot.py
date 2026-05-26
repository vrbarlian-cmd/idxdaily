"""Spot-check enrichment status for BJTM and SMGR."""
import asyncio, asyncpg, os
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(".env"))
load_dotenv(Path(".env.local"), override=True)

async def q():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    unrich = await conn.fetchval("SELECT COUNT(*) FROM articles WHERE ai_summary IS NULL")
    print(f"Unenriched total: {unrich}")

    for sym in ["BJTM", "SMGR"]:
        rows = await conn.fetch("""
            SELECT a.title, a.ai_summary, a.sentiment, a.impact_score
            FROM articles a
            JOIN ticker_mentions tm ON tm.article_id = a.id
            JOIN tickers t ON t.id = tm.ticker_id
            WHERE t.symbol = $1
            ORDER BY a.published_at DESC
            LIMIT 3
        """, sym)
        print(f"\n{sym}: {len(rows)} articles")
        for r in rows:
            has_sum = "YES" if r["ai_summary"] else "NO"
            summary_preview = (r["ai_summary"] or "")[:80]
            print(f"  [{has_sum}] {r['sentiment']} {r['impact_score']} {r['title'][:55]}")
            if summary_preview:
                print(f"    -> {summary_preview}")

asyncio.run(q())

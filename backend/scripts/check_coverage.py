"""Check ticker news coverage and BKSL status."""
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
        total_tickers = await conn.fetchval("SELECT COUNT(*) FROM tickers")
        tickers_with_news = await conn.fetchval("""
            SELECT COUNT(DISTINCT t.id)
            FROM tickers t
            JOIN ticker_mentions tm ON tm.ticker_id = t.id
            JOIN articles a ON a.id = tm.article_id
            WHERE a.published_at >= NOW() - INTERVAL '30 days'
        """)
        tickers_with_macro = await conn.fetchval("""
            SELECT COUNT(DISTINCT tm.ticker_id)
            FROM ticker_mentions tm
            JOIN articles a ON a.id = tm.article_id
            WHERE tm.match_type = 'macro_impact'
            AND a.published_at >= NOW() - INTERVAL '30 days'
        """)
        tickers_no_news = total_tickers - tickers_with_news
        print(f"Total tickers in DB:       {total_tickers}")
        print(f"With direct news (30d):    {tickers_with_news}")
        print(f"With macro_impact (30d):   {tickers_with_macro}")
        print(f"With NO news at all (30d): {tickers_no_news}")
        print(f"Coverage (direct):         {tickers_with_news/total_tickers*100:.1f}%")
        print()

        bksl_check = await conn.fetchrow(
            "SELECT symbol, name, market_cap FROM tickers WHERE symbol = 'BKSL'"
        )
        if bksl_check:
            print(f"BKSL in DB: {bksl_check['name']}  market_cap={bksl_check['market_cap']}")
        else:
            print("BKSL NOT in tickers DB")

        # BKSL macro_impact mentions
        bksl_macro = await conn.fetch("""
            SELECT a.title, tm.ai_summary, tm.sentiment, tm.impact_score
            FROM ticker_mentions tm
            JOIN articles a ON a.id = tm.article_id
            JOIN tickers t ON t.id = tm.ticker_id
            WHERE t.symbol = 'BKSL' AND tm.match_type = 'macro_impact'
            ORDER BY a.published_at DESC
            LIMIT 5
        """)
        if bksl_macro:
            print(f"\nBKSL macro_impact mentions ({len(bksl_macro)}):")
            for r in bksl_macro:
                print(f"  Article: {r['title'][:70]}")
                print(f"  Summary: {(r['ai_summary'] or '')[:120]}")
                print(f"  Sentiment={r['sentiment']}  Impact={r['impact_score']}")
        else:
            print("\nBKSL: no macro_impact mentions yet")

    finally:
        await conn.close()

asyncio.run(check())

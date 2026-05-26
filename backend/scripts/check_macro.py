"""Check BI rate articles and property macro_impact mentions."""
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
        # BI rate / suku bunga macro articles (no ticker_id)
        rows = await conn.fetch("""
            SELECT a.title, a.category, a.ai_summary, a.published_at
            FROM articles a
            WHERE a.ticker_id IS NULL
            AND (
              a.title ILIKE '%bi rate%' OR a.title ILIKE '%suku bunga%'
              OR a.title ILIKE '%bank indonesia%' OR a.title ILIKE '%kpr%'
              OR a.title ILIKE '%bunga acuan%'
            )
            ORDER BY a.published_at DESC
            LIMIT 10
        """)
        print(f"BI rate / suku bunga macro articles (no ticker): {len(rows)}")
        for r in rows:
            print(f"  [{r['category']}] {r['title'][:80]}")
            if r["ai_summary"]:
                print(f"    -> {r['ai_summary'][:100]}")

        print()

        # All macro articles (ticker_id IS NULL)
        total_macro = await conn.fetchval(
            "SELECT COUNT(*) FROM articles WHERE ticker_id IS NULL"
        )
        print(f"Total macro articles (ticker_id IS NULL): {total_macro}")

        # Property ticker macro_impact mentions
        prop_tickers = await conn.fetch("""
            SELECT t.symbol, COUNT(*) as cnt
            FROM ticker_mentions tm
            JOIN tickers t ON t.id = tm.ticker_id
            WHERE tm.match_type = 'macro_impact'
            AND t.symbol IN ('BKSL','BSDE','CTRA','SMRA','PWON','LPKR','APLN','MKPI')
            GROUP BY t.symbol
            ORDER BY cnt DESC
        """)
        print()
        print("Property tickers with macro_impact mentions:")
        if prop_tickers:
            for r in prop_tickers:
                print(f"  {r['symbol']}: {r['cnt']} macro mentions")
        else:
            print("  (none yet)")

        # Total macro_impact mentions
        total_macro_impact = await conn.fetchval(
            "SELECT COUNT(*) FROM ticker_mentions WHERE match_type = 'macro_impact'"
        )
        print(f"\nTotal macro_impact mentions across all tickers: {total_macro_impact}")

    finally:
        await conn.close()

asyncio.run(check())

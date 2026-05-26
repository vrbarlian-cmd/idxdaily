"""Check current DB state for overnight tasks."""
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
        unrich = await conn.fetchval("SELECT COUNT(*) FROM articles WHERE ai_summary IS NULL")
        print(f"Articles: {total}, Unenriched: {unrich}")

        ff_count = await conn.fetchval("SELECT COUNT(*) FROM foreign_flow_daily")
        ff_min = await conn.fetchval("SELECT MIN(date) FROM foreign_flow_daily")
        ff_max = await conn.fetchval("SELECT MAX(date) FROM foreign_flow_daily")
        print(f"FF data: {ff_count} rows, {ff_min} to {ff_max}")

        ihsg_count = await conn.fetchval("SELECT COUNT(*) FROM ihsg_daily")
        ihsg_min = await conn.fetchval("SELECT MIN(date) FROM ihsg_daily")
        ihsg_max = await conn.fetchval("SELECT MAX(date) FROM ihsg_daily")
        print(f"IHSG: {ihsg_count} rows, {ihsg_min} to {ihsg_max}")

        usd_count = await conn.fetchval("SELECT COUNT(*) FROM usdidr_daily")
        usd_min = await conn.fetchval("SELECT MIN(date) FROM usdidr_daily")
        usd_max = await conn.fetchval("SELECT MAX(date) FROM usdidr_daily")
        print(f"USDIDR: {usd_count} rows, {usd_min} to {usd_max}")

        # TLKM sort order check
        sample = await conn.fetch("""
            SELECT a.title, a.published_at
            FROM articles a
            JOIN ticker_mentions tm ON tm.article_id = a.id
            JOIN tickers t ON t.id = tm.ticker_id
            WHERE t.symbol = 'TLKM'
            ORDER BY a.published_at DESC
            LIMIT 3
        """)
        print("TLKM articles (should be newest first):")
        for r in sample:
            print(f"  {r['published_at'].date()} {r['title'][:60]}")

        # Check BRPT for duplicates
        brpt = await conn.fetch("""
            SELECT a.title, a.published_at, a.source, a.url
            FROM articles a
            JOIN ticker_mentions tm ON tm.article_id = a.id
            JOIN tickers t ON t.id = tm.ticker_id
            WHERE t.symbol = 'BRPT'
            ORDER BY a.published_at DESC
            LIMIT 10
        """)
        print(f"\nBRPT articles ({len(brpt)} shown):")
        for r in brpt:
            print(f"  {r['published_at'].date()} [{r['source'][:20]}] {r['title'][:55]}")

        # Fear greed history
        fg = await conn.fetch("""
            SELECT date, raw_score, smoothed_score, label, is_backfilled
            FROM fear_greed_index ORDER BY date DESC LIMIT 5
        """)
        print(f"\nFear & Greed recent ({len(fg)} rows):")
        for r in fg:
            print(f"  {r['date']} raw={r['raw_score']} smooth={r['smoothed_score']} {r['label']} backfill={r['is_backfilled']}")

    finally:
        await conn.close()

asyncio.run(check())

"""
Execute approved duplicate deletion.
26 article IDs approved for deletion on 2026-05-24.
Cascades to ticker_mentions automatically (FK with ON DELETE CASCADE expected;
if not, we delete mentions first).
"""
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(".env"))
load_dotenv(Path(".env.local"), override=True)
import asyncpg

APPROVED_DELETE_IDS = [
    # Cluster 24 — WSKT (Bloomberg Technoz dup of CNBC)
    "b737ee4d-b83c-49dc-83d8-06698a0007a5",
    # Cluster 22 — AKRA (kontan.co.id dup of TradingView)
    "a9d97b10-85e2-4991-9af9-5b7e30a5ba54",
    # Cluster 23 — BBCA (detikFinance capitalisation dup)
    "a159acb9-e53d-48ef-b876-66b213d0b337",
    # Cluster 21 — BJBR (investor.id dup of Infobanknews)
    "fd61cfca-6226-4613-a2e6-18442e799b0f",
    # Cluster 17 — LPPF (Pojok Papua Rp250/saham)
    "05d5fb1e-bb58-4b08-ac91-16a8cb7239df",
    # Cluster 18 — LPPF (Pojok Papua Rp556M truncated)
    "2d0e52f7-dedd-45ba-9d55-68345f30440e",
    # Cluster 19 — ARNA (Pojok Papua Rp330M truncated)
    "6d19d34b-e708-49ed-9904-d04716276242",
    # Cluster 20 — UNTR (Babel Insight "Sisa Dividen" dup)
    "c12d4a4d-c986-4172-97f5-55b56c4d8950",
    # Cluster 16 — SSMS (Babel Insight dup of Pojok Papua)
    "27a91366-289c-446e-98d0-79f9d0591bff",
    # Cluster 15 — BBCA+BBNI (TradingView dup of kontan)
    "e3de327e-bce5-45fd-bf6e-625738a3d0ce",
    # Cluster 12 — TLKM (CNBC exact dup)
    "f78cf8c8-fd65-4fa3-8b36-df41dcb8efac",
    # Cluster 14 — GGRM+HMSP (Batuah News dup)
    "ba76b775-9860-4bd2-80c6-16b9e72c5004",
    # Cluster 7 — MLPL (RCTI+ dup of IDX Channel)
    "07b89d0e-356f-4572-b1ef-3f45b5996d25",
    # Cluster 10 — CPIN (Inikata.co.id dup of Bisnis.com)
    "dce2c2a6-cfaa-4478-9109-471b919dc7a4",
    # Cluster 13 — BJTM (KlikJatim next-day dup)
    "b70b4a0f-601c-498b-a954-d41fbdfeb602",
    # Cluster 11 — BBCA+BBRI (CNBC exact dup)
    "f1058b29-dba6-4d82-9dbe-d1078462ee10",
    # Cluster 3 — BJTM (Antara News exact dup)
    "195f1048-f80e-4a00-9e1f-87c4313b4987",
    # Cluster 4 — BFIN (IDX Channel dup)
    "ad55bd6e-795b-4be5-8be3-dbe8118c69c6",
    # Cluster 4 — BFIN (RCTI+ dup)
    "c6fdc4b7-2361-49af-887a-cfa518436fc5",
    # Cluster 8 — Coal (Bisnis.com 1-day-later dup)
    "20e2caf6-4602-4380-8579-bc23169abd2e",
    # Cluster 9 — BRPT+TPIA (Bisnis.com penjaminan saham dup) ← key one
    "648b21c9-7052-4400-950c-9a8d0dd414ea",
    # Cluster 5 — SCMA (MSN dup)
    "832bcebe-d6c0-4240-99da-73fba566d3aa",
    # Cluster 5 — SCMA (Kontan dup)
    "f859b636-4c37-4525-b069-1e6cf227b42d",
    # Cluster 6 — macro (CNBC BI anti-scam exact dup)
    "984d1bbd-fe27-4bab-ae47-61b2f12107e0",
    # Cluster 1 — DSSA (Kontan capitalisation dup)
    "e020c6e9-2bfa-40bd-ab27-6676a6c2d325",
    # Cluster 2 — SCMA (kontan.co.id dup)
    "81f937c7-8052-4f45-b7c7-985fdff1bacb",
]

async def main():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        before = await conn.fetchval("SELECT COUNT(*) FROM articles")
        print(f"Articles before: {before}")

        # Delete mentions first (in case no CASCADE), then articles
        mention_tag = await conn.execute(
            "DELETE FROM ticker_mentions WHERE article_id = ANY($1::text[])",
            APPROVED_DELETE_IDS,
        )
        mentions_deleted = int(mention_tag.split()[-1])

        article_tag = await conn.execute(
            "DELETE FROM articles WHERE id = ANY($1::text[])",
            APPROVED_DELETE_IDS,
        )
        articles_deleted = int(article_tag.split()[-1])

        after = await conn.fetchval("SELECT COUNT(*) FROM articles")
        print(f"Mentions deleted : {mentions_deleted}")
        print(f"Articles deleted : {articles_deleted}")
        print(f"Articles after   : {after}")
        print(f"Expected IDs     : {len(APPROVED_DELETE_IDS)}")

        # Verify BRPT + TPIA no longer show the duplicate
        print("\nBRPT+TPIA 'penjaminan' articles now in DB:")
        rows = await conn.fetch("""
            SELECT a.id, a.title, a.published_at, a.source
            FROM articles a
            JOIN ticker_mentions tm ON tm.article_id = a.id
            JOIN tickers t ON t.id = tm.ticker_id
            WHERE t.symbol IN ('BRPT', 'TPIA')
              AND a.title ILIKE '%penjaminan%'
            ORDER BY a.published_at DESC
        """)
        if rows:
            for r in rows:
                print(f"  [{r['published_at'].date()}] [{r['source']}] {r['title'][:70]}")
        else:
            print("  (none — duplicate fully removed)")

        # Spot-check total article count
        unrich = await conn.fetchval("SELECT COUNT(*) FROM articles WHERE ai_summary IS NULL")
        print(f"\nUnenriched after dedup: {unrich}")

    finally:
        await conn.close()

asyncio.run(main())

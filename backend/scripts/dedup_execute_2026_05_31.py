"""
Execute approved duplicate deletion — 2026-05-31 cleanup run.
52 articles to delete across 49 clusters identified by dedup_dryrun.py.
"""
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(".env"))
load_dotenv(Path(".env.local"), override=True)
import asyncpg

APPROVED_DELETE_IDS = [
    # Cluster 49 — BBCA detikFinance capitalisation dup
    "cc153da4-401c-46bd-b080-f4398417d1e3",
    # Cluster 48 — ESSA RCTI+ dup of IDX Channel
    "af7b22d0-966a-4edc-a71f-3bee943df7ce",
    # Cluster 47 — BBCA detikFinance exact dup
    "be85916a-46ff-458c-926b-ea8505b7aee0",
    # Cluster 45 — AKRA IDX Channel exact dup
    "d6598075-f241-4723-ab75-bd53cd6fcc5e",
    # Cluster 46 — ISAT SinPo.id dup of ANTARA
    "f09ddd15-94c0-4542-892c-c4048d8a47db",
    # Cluster 44 — ISAT Ajaib exact dup
    "f047061a-28e6-4cf6-b800-ae58a9362239",
    # Cluster 43 — NICL RCTI+ dup of IDX Channel
    "8f528fab-f8ce-4001-b0ce-bc867df7116c",
    # Cluster 41 — WTON SINDOnews exact dup
    "bf7d0473-525b-4154-a53b-4af4a9c12265",
    # Cluster 42 — BMRI TradingView exact dup
    "595541f2-366d-4f67-b122-bac31d87f392",
    # Cluster 40 — AKRA MSN dup of kontan
    "8af87a8c-8a95-4bc7-96a0-d92f00d73ce1",
    # Cluster 38 — LPPF Pojok Papua dup of Babel Insight
    "bda4a9a7-9de1-43bc-9c56-41873705eea8",
    # Cluster 39 — ARNA Pojok Papua dup of Babel Insight
    "aa4d1fdd-46ec-4c9f-a0e8-c494c0be1846",
    # Cluster 36 — SSMS Babel Insight dup of Pojok Papua
    "05243292-c729-43cb-9fad-7ead286a940c",
    # Cluster 37 — EXCL BERNAS.id exact dup
    "d8165895-69f8-4d60-a496-aec9b66404c1",
    # Cluster 35 — SILO Kalamanthana dup
    "4af57c27-78b1-4680-83f7-3766beaba599",
    # Cluster 35 — SILO newshanter.com dup
    "cf494f26-3125-41c8-8a4b-b30ed41cfd01",
    # Cluster 33 — EXCL MSN exact dup
    "cf7e12a5-8d70-4dd2-8c74-98911590a357",
    # Cluster 34 — BBNI TradingView dup of kontan
    "871d555b-884a-41a9-9d8d-39252c7d6e61",
    # Cluster 32 — SIDO KONTAN exact dup
    "b950a0db-6d8a-481e-b42d-831851654deb",
    # Cluster 28 — INTP Emitennews.com exact dup
    "98cacc9a-39b8-4ca2-a948-1370c190317f",
    # Cluster 31 — ESSA MSN dup of kontan
    "4bba4547-ed75-4fe1-b4a0-8d333020c86a",
    # Cluster 29 — BFIN MSN exact dup
    "dd2f8abf-8193-4e53-a3b2-29a9924d276a",
    # Cluster 30 — GGRM Batuah News dup of Babel Insight
    "7c3512ee-d221-45c8-8c7b-1a7591c9fd20",
    # Cluster 20 — PTPP Malangtimes exact dup
    "9faf9430-8e2d-417d-9a9a-7758554af577",
    # Cluster 21 — INTP SINDOnews exact dup
    "39319894-c847-4f05-8ec1-87517faadcc8",
    # Cluster 22 — INTP Industry.co.id exact dup
    "68974fb9-29dc-4c67-bb60-5d59573e3b21",
    # Cluster 23 — MDKA Bareksa.com exact dup
    "841ba6d1-f81a-4068-934a-cc777cd442c3",
    # Cluster 24 — CPIN kontan.co.id exact dup
    "90cd1dc4-a09f-4430-901d-05a9e90b778b",
    # Cluster 25 — MLPL RCTI+ dup of IDX Channel
    "9654d63b-14fa-4dc1-8c7e-cf4b98a2822e",
    # Cluster 26 — CPIN Inikata.co.id dup of Bisnis.com
    "cb76078b-f71f-4000-b0d7-dfe471c20330",
    # Cluster 27 — HMSP Bareksa.com exact dup
    "c457c007-94b5-4b6e-b1f6-de07e115c439",
    # Cluster 12 — GOTO TradingView dup of kontan
    "b6f15605-b823-406a-a72c-67bc6a9fce7a",
    # Cluster 13 — BJTM Antara News jatim exact dup
    "ec8f2989-4009-446c-978b-efb9740b2205",
    # Cluster 14 — BFIN IDX Channel exact dup (x2) + RCTI+
    "10ad7066-0be0-41e6-bfd2-12606d222487",
    "52a9ef0f-6add-4bf3-a0fc-1c606bd1d310",
    "ccfa870f-9cc7-4c72-a2fb-d75c7b97cb62",
    # Cluster 15 — BUVA Emitennews.com same-source exact dup
    "3606560f-16e2-49c5-a4a5-3091eade2ee2",
    # Cluster 16 — SCMA pasardana.id exact dup
    "e606bdd6-bf21-47eb-bda3-9873e6b96ea1",
    # Cluster 17 — SCMA MSN dup of TradingView
    "63ad9b18-b9b4-4cbc-adef-ef8d43d70e33",
    # Cluster 18 — SCMA Bareksa.com exact dup
    "945477a5-3309-4655-a73b-b8aae1c5ee2a",
    # Cluster 19 — TOWR Bareksa.com exact dup
    "cfe2e312-8125-443c-b2c6-290d91809910",
    # Cluster 10 — SCMA kontan.co.id dup
    "dddf3cad-e902-493f-b28b-abc179b498c4",
    # Cluster 11 — macro MSN exact dup
    "b132efda-c6cf-4963-bc78-77bed855a666",
    # Cluster 4 — BMRI Bareksa.com exact dup
    "2c217ced-bf3c-439d-b7ad-6e2a1abea884",
    # Cluster 5 — BFIN Bareksa.com exact dup
    "2f21633c-98fd-445b-85dd-8bf2cf2b8b3f",
    # Cluster 6 — BFIN Ajaib exact dup
    "dca73902-7bd0-4d9e-b8f0-34d0d2cce780",
    # Cluster 7 — MDKA Kontan capitalisation dup
    "761e2fc1-2851-4146-8a32-caff98c8d8f9",
    # Cluster 8 — MDKA kontan.co.id dup
    "fb90a25c-f92f-4c9a-ba3f-1e99359bef6d",
    # Cluster 9 — DSSA CNBC Indonesia exact dup
    "a945b2cd-c60d-491f-a38d-26c17faaa34b",
    # Cluster 3 — SMGR CNBC Indonesia exact dup
    "e505ad2a-a5cd-4ef6-9167-571744898b77",
    # Cluster 1 — banking IDX Channel exact dup
    "af697b74-c3ef-4c99-9c78-bd1172045176",
    # Cluster 2 — ERAA kontan.co.id dup
    "f0f24669-22a4-4676-81ac-c148ba58ed80",
]


async def main():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        before = await conn.fetchval("SELECT COUNT(*) FROM articles")
        print(f"Articles before: {before}")
        print(f"IDs to delete  : {len(APPROVED_DELETE_IDS)}")

        # Delete mentions first (no CASCADE assumption), then articles
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

        # Verify BUVA no longer shows the duplicate
        print("\nBUVA divestasi articles now in DB:")
        rows = await conn.fetch("""
            SELECT a.id, a.title, a.published_at, a.source
            FROM articles a
            JOIN ticker_mentions tm ON tm.article_id = a.id
            JOIN tickers t ON t.id = tm.ticker_id
            WHERE t.symbol = 'BUVA'
              AND a.title ILIKE '%divestasi%'
            ORDER BY a.published_at DESC
        """)
        if rows:
            for r in rows:
                print(f"  [{r['published_at'].date()}] [{r['source']}] {r['title'][:70]}")
        else:
            print("  (none matching divestasi)")

        print("\nDone.")
    finally:
        await conn.close()


asyncio.run(main())

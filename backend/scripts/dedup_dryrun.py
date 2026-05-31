"""
DRY-RUN duplicate detection — headline similarity deduplication.

Algorithm:
  1. Normalize each article title via shared dedup module (same logic as ingest).
  2. Group by (ticker, 6-hour bucket) — mirrors the ingest-time window.
  3. Within each group compare normalised titles:
     a. Exact normalised title  → duplicate
     b. Long common prefix ≥ 60 chars → duplicate
     c. Jaccard word-set:
        - Cross-source ≥ 0.80
        - Same-source  ≥ 0.90   (BUVA emitennews same-domain case)
  4. Keeper = highest source tier → earliest date → has body → has summary
  5. Print FULL dry-run report. NO deletes.

Runs from project root:
    python -m backend.scripts.dedup_dryrun
"""
import asyncio
import sys
from collections import defaultdict
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(".env"))
load_dotenv(Path(".env.local"), override=True)

import asyncpg

# Import shared logic so dry-run and live ingest are IDENTICAL
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.workers.dedup import (
    normalise, word_set, are_duplicates, pick_keeper, source_tier, _time_bucket
)


async def main() -> None:
    import os
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        rows = await conn.fetch("""
            SELECT DISTINCT ON (a.id)
                a.id,
                a.title,
                a.source,
                a.url,
                a.published_at,
                a.ticker_id,
                a.ai_summary IS NOT NULL                        AS has_summary,
                a.body IS NOT NULL AND LENGTH(a.body) > 100    AS has_body,
                COALESCE(t.symbol, '_macro_')                  AS primary_symbol
            FROM articles a
            LEFT JOIN tickers t ON t.id = a.ticker_id
            ORDER BY a.id, a.published_at
        """)

        print(f"[dedup] Total articles in DB: {len(rows)}")

        tm_rows = await conn.fetch("""
            SELECT tm.article_id, t.symbol
            FROM ticker_mentions tm
            JOIN tickers t ON t.id = tm.ticker_id
            WHERE tm.match_confidence IN ('high','medium')
        """)
        art_tickers: dict[str, list[str]] = defaultdict(list)
        for tm in tm_rows:
            art_tickers[tm["article_id"]].append(tm["symbol"])

        articles = []
        for r in rows:
            art = dict(r)
            art["norm_title"] = normalise(r["title"])
            art["words"]      = word_set(art["norm_title"])
            # 6-hour bucket for windowed dedup (matches ingest-time logic)
            art["bucket"]     = _time_bucket(r["published_at"])
            art["pub_date"]   = r["published_at"].date() if r["published_at"] else None
            art["tickers"]    = [art["primary_symbol"]] + art_tickers.get(r["id"], [])
            articles.append(art)

        # ── Build clusters via 6-hour buckets ────────────────────────────────
        by_ticker_bucket: dict[tuple, list] = defaultdict(list)
        for art in articles:
            ticker = art["tickers"][0] if art["tickers"] else "_macro_"
            key    = (ticker, art["bucket"])
            by_ticker_bucket[key].append(art)

        parent: dict[str, str] = {a["id"]: a["id"] for a in articles}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x: str, y: str) -> None:
            parent[find(x)] = find(y)

        dup_pairs: list[dict] = []
        checked = 0
        visited: set[tuple[str, str]] = set()

        all_keys = list(by_ticker_bucket.keys())
        for ticker, bucket in all_keys:
            for offset in (0, 1):  # same + adjacent bucket (catches boundary splits)
                peer_key = (ticker, bucket + offset)
                if peer_key not in by_ticker_bucket:
                    continue
                a_list = by_ticker_bucket[(ticker, bucket)]
                b_list = by_ticker_bucket[peer_key]
                for a in a_list:
                    for b in b_list:
                        if a["id"] == b["id"]:
                            continue
                        pair_key = (min(a["id"], b["id"]), max(a["id"], b["id"]))
                        if pair_key in visited:
                            continue
                        visited.add(pair_key)
                        checked += 1
                        is_dup, reason = are_duplicates(
                            a["norm_title"], a["words"], a.get("source"),
                            b["norm_title"], b["words"], b.get("source"),
                        )
                        if is_dup:
                            union(a["id"], b["id"])
                            dup_pairs.append({
                                "id_a": a["id"], "title_a": a["title"],
                                "source_a": a["source"], "date_a": a["pub_date"],
                                "id_b": b["id"], "title_b": b["title"],
                                "source_b": b["source"], "date_b": b["pub_date"],
                                "reason": reason,
                            })

        clusters: dict[str, list] = defaultdict(list)
        for art in articles:
            clusters[find(art["id"])].append(art)

        dup_clusters = {k: v for k, v in clusters.items() if len(v) > 1}

        print(f"[dedup] Pairs checked: {checked}")
        print(f"[dedup] Duplicate pairs found: {len(dup_pairs)}")
        print(f"[dedup] Duplicate clusters: {len(dup_clusters)}")

        would_delete: list[dict] = []
        would_keep:   list[dict] = []

        for cluster_id, cluster in dup_clusters.items():
            # pick_keeper now uses source tier (Tier 1 > Tier 2 > Tier 3)
            keeper = pick_keeper(cluster)
            to_del = [a for a in cluster if a["id"] != keeper["id"]]
            would_keep.append(keeper)
            would_delete.extend(to_del)

        print(f"[dedup] Would DELETE: {len(would_delete)} articles")
        print(f"[dedup] Would KEEP:   {len(would_keep)} articles (one per cluster)")
        print(f"[dedup] Net reduction: {len(would_delete)} articles removed")

        # ── Full report ───────────────────────────────────────────────────────
        print(f"\n{'='*80}")
        print(f"  DRY-RUN REPORT — {len(dup_clusters)} duplicate clusters")
        print(f"  Keeper = highest-tier source (Tier1>Tier2>Tier3), then earliest date")
        print(f"  Cross-source threshold: Jaccard ≥ 0.80 | Same-source: ≥ 0.90")
        print(f"{'='*80}")

        for i, (cluster_id, cluster) in enumerate(sorted(
            dup_clusters.items(),
            key=lambda kv: min(
                (a["pub_date"] or __import__('datetime').date.max) for a in kv[1]
            ),
            reverse=True,
        ), 1):
            keeper = pick_keeper(cluster)
            to_del = [a for a in cluster if a["id"] != keeper["id"]]

            tickers_str = ", ".join(sorted({
                t for a in cluster for t in a["tickers"] if t != "_macro_"
            }))
            tier_k = source_tier(keeper.get("source"))
            print(f"\n  [{i}] Cluster — {len(cluster)} arts — tickers: {tickers_str or '(macro)'}")
            print(f"       KEEP [T{tier_k}]: [{keeper['pub_date']}] [{keeper['source'][:25]}] "
                  f"{keeper['title'][:65]}")
            if keeper.get("has_body"):    print(f"               has_body=YES")
            if keeper.get("has_summary"): print(f"               has_summary=YES")
            for d in to_del:
                tier_d = source_tier(d.get("source"))
                print(f"       DROP [T{tier_d}]: [{d['pub_date']}] [{d['source'][:25]}] {d['title'][:65]}")
                print(f"               id={d['id']}")

        print(f"\n{'='*80}")
        print(f"  ARTICLES TO DELETE (ids):")
        print(f"{'='*80}")
        for a in sorted(would_delete, key=lambda x: x["pub_date"] or __import__('datetime').date.max):
            print(f"  {a['id']}  [{a['pub_date']}] [{a['source'][:20]}] {a['title'][:60]}")

        print(f"\n{'='*80}")
        print(f"  DUPLICATE SUMMARY BY TICKER")
        print(f"{'='*80}")
        ticker_del: dict[str, int] = defaultdict(int)
        for a in would_delete:
            for t in a["tickers"]:
                if t != "_macro_":
                    ticker_del[t] += 1
        for ticker, cnt in sorted(ticker_del.items(), key=lambda x: -x[1]):
            print(f"  {ticker}: {cnt} articles would be removed")

        print(f"\n[dedup] DRY-RUN COMPLETE. No data was modified.")
        print(f"[dedup] Run dedup_execute.py after approval to apply deletes.")

    finally:
        await conn.close()


asyncio.run(main())

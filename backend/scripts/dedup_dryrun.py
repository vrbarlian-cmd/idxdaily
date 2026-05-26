"""
DRY-RUN duplicate detection — headline similarity deduplication.

Algorithm:
  1. Normalize each article title: lowercase, strip, collapse spaces,
     remove common source suffixes ("|Kompas", "- CNBC Indonesia", etc.)
  2. Group by (ticker_id OR ticker_mention ticker_id, published_at::date window)
  3. Within same ticker × same-day-or-adjacent-day window, compare normalized titles
  4. Flag pairs with:
     a. Exact normalized title match (same story)
     b. Long common prefix (>=60 chars) — same story, different ending
     c. Jaccard word-set similarity >= 0.75 (semantically identical)
  5. Within each duplicate cluster: keep the EARLIEST published_at
     (tiebreak: prefer article with body, then with ai_summary, then longest title)
  6. Print FULL dry-run report — what WOULD be deleted and what WOULD be kept.
     NO deletes.

Runs from project root:
    python -m backend.scripts.dedup_dryrun
"""
import asyncio
import os
import re
from collections import defaultdict
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(".env"))
load_dotenv(Path(".env.local"), override=True)

import asyncpg

# ── Normalisation ────────────────────────────────────────────────────────────

_SOURCE_SUFFIX_PATTERNS = re.compile(
    r"""
    \s*[|\-–—]\s*                        # separator: | or dash
    (?:
      Bisnis\.com|CNBC\s*Indonesia|Detik\s*Finance|Kompas|Tempo|
      Bloomberg\s*Technoz|Kontan|Investor\.id|Tribun|IDX\s*Channel|
      Bareksa|Katadata|Market\s*Bisnis|Okezone|JPNN|Suara\.com|
      Tirto\.id|Babel\s*Insight|IDNFinancials|pdiperjuanganbali\.id|
      CNN\s*Indonesia|VOI|MNC\s*Trijaya|[A-Za-z0-9 \.]+\.(?:com|id)
    )
    \s*$
    """,
    re.VERBOSE | re.IGNORECASE,
)

_TRAILING_PUNCT = re.compile(r'[\s\-–—|]+$')
_MULTI_SPACE    = re.compile(r'\s+')


def normalise(title: str) -> str:
    t = title.lower().strip()
    # Remove source suffixes (up to 2 passes — some titles have nested suffixes)
    for _ in range(2):
        t2 = _SOURCE_SUFFIX_PATTERNS.sub('', t).strip()
        t2 = _TRAILING_PUNCT.sub('', t2).strip()
        if t2 == t:
            break
        t = t2
    t = _MULTI_SPACE.sub(' ', t)
    return t


def word_set(title: str) -> set[str]:
    return set(re.findall(r'\w+', title))


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def are_duplicates(norm_a: str, norm_b: str) -> tuple[bool, str]:
    """Return (is_dup, reason)."""
    if norm_a == norm_b:
        return True, "exact_title"
    # Long common prefix
    pfx = os.path.commonprefix([norm_a, norm_b])
    if len(pfx) >= 60:
        return True, f"common_prefix_{len(pfx)}c"
    # Jaccard
    j = jaccard(word_set(norm_a), word_set(norm_b))
    if j >= 0.75:
        return True, f"jaccard_{j:.2f}"
    return False, ""


def pick_keeper(articles: list[dict]) -> dict:
    """
    From a cluster of duplicates, pick the one to KEEP.
    Priority: earliest published_at → has body → has ai_summary → longest title
    """
    return sorted(
        articles,
        key=lambda a: (
            a["published_at"] or "9999",   # earliest first
            0 if a["has_body"] else 1,      # prefer body
            0 if a["has_summary"] else 1,   # prefer summary
            -len(a["title"]),               # prefer longer (more complete) title
        )
    )[0]


async def main() -> None:
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        # Fetch all articles with their ticker associations
        # We join through ticker_mentions to get the ticker context
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

        # Also load ticker_mention associations for clustering
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
            art["pub_date"]   = r["published_at"].date() if r["published_at"] else None
            art["tickers"]    = [art["primary_symbol"]] + art_tickers.get(r["id"], [])
            articles.append(art)

        # ── Build clusters ────────────────────────────────────────────────────
        # Group by pub_date (±1 day window) and compare within group
        by_date: dict = defaultdict(list)
        for art in articles:
            d = art["pub_date"]
            if d:
                by_date[d].append(art)

        # Union-Find for clustering
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

        # Compare within same-day and adjacent-day buckets
        all_dates = sorted(by_date.keys())
        for i, d in enumerate(all_dates):
            # Build window: current date + next date (cover overnight splits)
            window_arts = list(by_date[d])
            if i + 1 < len(all_dates) and (all_dates[i+1] - d).days == 1:
                window_arts += by_date[all_dates[i+1]]

            for j in range(len(window_arts)):
                for k in range(j + 1, len(window_arts)):
                    a = window_arts[j]
                    b = window_arts[k]
                    checked += 1
                    is_dup, reason = are_duplicates(a["norm_title"], b["norm_title"])
                    if is_dup:
                        union(a["id"], b["id"])
                        dup_pairs.append({
                            "id_a": a["id"], "title_a": a["title"],
                            "source_a": a["source"], "date_a": a["pub_date"],
                            "id_b": b["id"], "title_b": b["title"],
                            "source_b": b["source"], "date_b": b["pub_date"],
                            "reason": reason,
                            "tickers_a": a["tickers"][:3],
                            "tickers_b": b["tickers"][:3],
                        })

        # Group articles into clusters
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
            keeper = pick_keeper(cluster)
            to_del = [a for a in cluster if a["id"] != keeper["id"]]
            would_keep.append(keeper)
            would_delete.extend(to_del)

        print(f"[dedup] Would DELETE: {len(would_delete)} articles")
        print(f"[dedup] Would KEEP:   {len(would_keep)} articles (one per cluster)")
        print(f"[dedup] Net reduction: {len(would_delete)} articles removed")

        # ── Full dry-run report ───────────────────────────────────────────────
        print(f"\n{'='*80}")
        print(f"  DRY-RUN REPORT — {len(dup_clusters)} duplicate clusters")
        print(f"  These {len(would_delete)} articles WOULD BE DELETED (awaiting approval)")
        print(f"{'='*80}")

        for i, (cluster_id, cluster) in enumerate(sorted(
            dup_clusters.items(),
            key=lambda kv: min(a["pub_date"] or "9999" for a in kv[1]),
            reverse=True,  # most recent first
        ), 1):
            keeper = pick_keeper(cluster)
            to_del = [a for a in cluster if a["id"] != keeper["id"]]

            tickers_str = ", ".join(sorted({t for a in cluster for t in a["tickers"] if t != "_macro_"}))
            print(f"\n  [{i}] Cluster — {len(cluster)} articles — tickers: {tickers_str or '(macro)'}")
            print(f"       KEEP:   [{keeper['pub_date']}] [{keeper['source'][:25]}] {keeper['title'][:70]}")
            if keeper["has_body"]:    print(f"               has_body=YES")
            if keeper["has_summary"]: print(f"               has_summary=YES")
            for d in to_del:
                print(f"       DELETE: [{d['pub_date']}] [{d['source'][:25]}] {d['title'][:70]}")
                print(f"               id={d['id']}")

        # Machine-readable delete list for morning approval
        print(f"\n{'='*80}")
        print(f"  ARTICLES TO DELETE (ids) — paste to approve:")
        print(f"{'='*80}")
        for a in sorted(would_delete, key=lambda x: x["pub_date"] or "9999"):
            print(f"  {a['id']}  [{a['pub_date']}] [{a['source'][:20]}] {a['title'][:60]}")

        # Per-ticker summary
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
        print(f"[dedup] Run dedup_execute.py after morning approval to apply deletes.")

    finally:
        await conn.close()


asyncio.run(main())

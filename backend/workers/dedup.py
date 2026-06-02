"""
Semantic dedup for IDXDaily news articles.

Used in two contexts:
  1. Ingest time (ingest.py)  — dedup_batch() filters a freshly-scraped batch
     before DB insertion so the same story is never stored twice.
  2. DB cleanup               — dedup_dryrun.py / dedup_execute.py import the
     same logic for periodic one-shot cleanup of accumulated duplicates.

Algorithm
---------
• Normalise title: lowercase, strip source suffixes, collapse whitespace.
• Group articles by (ticker, 6-hour bucket) — compare only within a bucket.
• Within a bucket, compare pairs using Jaccard word similarity:
    - Cross-source:  threshold 0.80  (different publishers, same story)
    - Same-source:   threshold 0.90  (same domain, slight rewrite)
• Keeper selection (highest priority first):
    1. Lowest tier number (Tier 1 beats Tier 2 beats Tier 3)
    2. Earliest published_at
    3. Has article body
    4. Has AI summary
    5. Longest title (most complete)

Source tiers
------------
Tier 1 — authoritative / high-reach IDX outlets
Tier 2 — specialist finance/emiten publishers
Tier 3 — everything else (aggregators, regional, unknown)
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Source tiers
# ---------------------------------------------------------------------------

TIER_1: frozenset[str] = frozenset({
    "Detik Finance", "detikFinance", "detik.com",
    "CNBC Indonesia",
    "Kontan", "kontan.co.id",
    "Bisnis.com", "bisnis.com",
    "Katadata",
    "IDX Channel", "idxchannel.com",
})

TIER_2: frozenset[str] = frozenset({
    "Emiten News", "emitennews.com",
    "Investor.id", "investor.id",
})

# Tier 3 = everything else  (score = 3)

_TIER_CACHE: dict[str, int] = {}


def source_tier(source: str | None) -> int:
    """Return tier number (1 = best, 3 = lowest) for a source string."""
    if source is None:
        return 3
    s = source.strip()
    if s in _TIER_CACHE:
        return _TIER_CACHE[s]
    s_lower = s.lower()
    for t1 in TIER_1:
        if t1.lower() in s_lower:
            _TIER_CACHE[s] = 1
            return 1
    for t2 in TIER_2:
        if t2.lower() in s_lower:
            _TIER_CACHE[s] = 2
            return 2
    _TIER_CACHE[s] = 3
    return 3


_NORM_SOURCE_CACHE: dict[str, str] = {}


def normalize_source(source: str | None) -> str:
    """
    Collapse publisher name variants to a canonical key for same-source detection.

    Handles cases like "Detik Finance" vs "detikFinance", "Katadata" vs
    "Katadata.co.id", "CNBC Indonesia" vs "cnbcindonesia.com", etc.
    Returns a lowercase canonical string; unknown sources return their own
    lowercased value so they can still match themselves.
    """
    if not source:
        return ""
    if source in _NORM_SOURCE_CACHE:
        return _NORM_SOURCE_CACHE[source]
    s = source.lower().strip()
    if "detik" in s:
        result = "detikfinance"
    elif "katadata" in s:
        result = "katadata"
    elif "cnbc" in s:
        result = "cnbcindonesia"
    elif "kontan" in s:
        result = "kontan"
    elif "bisnis" in s:
        result = "bisnis"
    elif "idx channel" in s or "idxchannel" in s:
        result = "idxchannel"
    elif "emiten" in s:
        result = "emitenews"
    else:
        result = s
    _NORM_SOURCE_CACHE[source] = result
    return result


# ---------------------------------------------------------------------------
# Title normalisation
# ---------------------------------------------------------------------------

_SOURCE_SUFFIX = re.compile(
    r"""
    \s*[|\-–—]\s*
    (?:
      Bisnis\.com|CNBC\s*Indonesia|Detik\s*Finance|detikFinance|Kompas|Tempo|
      Bloomberg\s*Technoz|Kontan|Investor\.id|Tribun|IDX\s*Channel|
      Bareksa|Katadata|Market\s*Bisnis|Okezone|JPNN|Suara\.com|
      Tirto\.id|Babel\s*Insight|IDNFinancials|CNN\s*Indonesia|VOI|
      MNC\s*Trijaya|Emiten\s*News|[A-Za-z0-9 \.]+\.(?:com|id|co\.id)
    )
    \s*$
    """,
    re.VERBOSE | re.IGNORECASE,
)
_TRAILING_PUNCT = re.compile(r'[\s\-–—|]+$')
_MULTI_SPACE    = re.compile(r'\s+')


def normalise(title: str) -> str:
    """Lowercase, strip source suffixes, collapse whitespace."""
    t = title.lower().strip()
    for _ in range(2):
        t2 = _SOURCE_SUFFIX.sub('', t).strip()
        t2 = _TRAILING_PUNCT.sub('', t2).strip()
        if t2 == t:
            break
        t = t2
    return _MULTI_SPACE.sub(' ', t)


def word_set(title: str) -> frozenset[str]:
    return frozenset(re.findall(r'\w+', title))


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

CROSS_SOURCE_THRESHOLD = 0.80
SAME_SOURCE_THRESHOLD  = 0.90


def are_duplicates(
    norm_a: str, words_a: frozenset[str], source_a: str | None,
    norm_b: str, words_b: frozenset[str], source_b: str | None,
) -> tuple[bool, str]:
    """
    Return (is_dup, reason).

    Uses stricter threshold for same-source comparisons so that slightly
    different articles from the same publisher (e.g. update vs. original) are
    not aggressively merged, while cross-publisher rewrites of the same story
    are caught at 80%.
    """
    # Exact normalised title → always a duplicate
    if norm_a == norm_b:
        return True, "exact_title"

    # Long common prefix (≥60 chars) → same story, different tail
    pfx = _common_prefix(norm_a, norm_b)
    if len(pfx) >= 60:
        return True, f"prefix_{len(pfx)}c"

    # Jaccard with threshold depending on same/cross source.
    # normalize_source() collapses variants like "Detik Finance" / "detikFinance"
    # so they are correctly identified as same-source (threshold 0.90 not 0.80).
    same_source = (
        source_a is not None
        and source_b is not None
        and normalize_source(source_a) == normalize_source(source_b)
    )
    threshold = SAME_SOURCE_THRESHOLD if same_source else CROSS_SOURCE_THRESHOLD
    j = jaccard(words_a, words_b)
    if j >= threshold:
        return True, f"jaccard_{j:.2f}{'_same_src' if same_source else ''}"

    return False, ""


def _common_prefix(a: str, b: str) -> str:
    i = 0
    for ca, cb in zip(a, b):
        if ca != cb:
            break
        i += 1
    return a[:i]


# ---------------------------------------------------------------------------
# Keeper selection
# ---------------------------------------------------------------------------

def pick_keeper(articles: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Given a cluster of duplicate articles, return the one to KEEP.

    Priority (ascending sort key → first element is keeper):
      1. Source tier (lower = better)
      2. Earliest published_at
      3. Has article body (has_body flag, or body key)
      4. Has AI summary (has_summary / ai_summary)
      5. Longest title
    """
    def sort_key(a: dict) -> tuple:
        tier = source_tier(a.get("source"))
        pub  = a.get("published_at") or datetime.max.replace(tzinfo=timezone.utc)
        if isinstance(pub, str):
            try:
                pub = datetime.fromisoformat(pub)
            except ValueError:
                pub = datetime.max.replace(tzinfo=timezone.utc)
        has_body    = bool(a.get("has_body") or (a.get("body") and len(a.get("body", "")) > 100))
        has_summary = bool(a.get("has_summary") or a.get("ai_summary"))
        return (
            tier,
            pub,
            0 if has_body else 1,
            0 if has_summary else 1,
            -len(a.get("title", "")),
        )

    return sorted(articles, key=sort_key)[0]


# ---------------------------------------------------------------------------
# Batch dedup
# ---------------------------------------------------------------------------

_BUCKET_HOURS = 6  # group articles within this time window


def _time_bucket(pub: datetime | None) -> int:
    """6-hour bucket index (seconds since epoch ÷ 21600)."""
    if pub is None:
        return -1
    ts = pub.timestamp() if pub.tzinfo else pub.replace(tzinfo=timezone.utc).timestamp()
    return int(ts // (_BUCKET_HOURS * 3600))


def dedup_batch(
    articles: list[dict[str, Any]],
    ticker_key: str = "detected_ticker",
) -> list[dict[str, Any]]:
    """
    Deduplicate a list of article dicts in-memory.

    Articles must have at minimum: 'title', 'url', 'source', 'published_at'.
    `ticker_key` names the field holding the associated ticker symbol (or None
    for macro articles).

    Returns a deduplicated list, keeping the best article per cluster.
    Removed duplicates are logged to stdout.
    """
    if not articles:
        return articles

    # Enrich each article with normalised fields
    enriched: list[dict] = []
    for a in articles:
        ec = dict(a)
        ec["_norm"]   = normalise(a.get("title", ""))
        ec["_words"]  = word_set(ec["_norm"])
        ec["_bucket"] = _time_bucket(a.get("published_at"))
        ec["_ticker"] = (a.get(ticker_key) or "").upper()
        enriched.append(ec)

    # Group by (ticker, bucket) — also include adjacent bucket for 6h window overlap
    # We compare every pair that shares a (ticker, bucket) OR (ticker, bucket±1)
    groups: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for a in enriched:
        key = (a["_ticker"], a["_bucket"])
        groups[key].append(a)

    # Union-Find
    id_map = {id(a): id(a) for a in enriched}

    def find(x: int) -> int:
        while id_map[x] != x:
            id_map[x] = id_map[id_map[x]]
            x = id_map[x]
        return x

    def union(x: int, y: int) -> None:
        id_map[find(x)] = find(y)

    checked = removed = 0

    # Compare within same bucket AND adjacent buckets (to catch 6h boundary splits).
    # Cross-ticker pass: for groups with a known ticker, also compare against the
    # unmatched group (ticker="") in the same time window. This catches the case
    # where the GN scraper sets detected_ticker="GOTO" but the RSS scraper leaves
    # detected_ticker=None for the same article — they would otherwise land in
    # different groups and never be compared.
    all_keys = list(groups.keys())
    visited_pairs: set[tuple[int, int]] = set()

    for ticker, bucket in all_keys:
        # Peer keys to compare against: same ticker (adjacent buckets) +
        # unmatched articles (ticker="") in same time window.
        peer_keys = [(ticker, bucket + offset) for offset in (0, 1)]
        if ticker:  # cross-compare against ticker-unassigned articles
            peer_keys += [("", bucket + offset) for offset in (0, 1)]

        a_list = groups[(ticker, bucket)]
        for peer_key in peer_keys:
            if peer_key not in groups:
                continue
            b_list = groups[peer_key]

            for a in a_list:
                for b in b_list:
                    if id(a) == id(b):
                        continue
                    pair = (min(id(a), id(b)), max(id(a), id(b)))
                    if pair in visited_pairs:
                        continue
                    visited_pairs.add(pair)
                    checked += 1

                    is_dup, reason = are_duplicates(
                        a["_norm"], a["_words"], a.get("source"),
                        b["_norm"], b["_words"], b.get("source"),
                    )
                    if is_dup:
                        union(id(a), id(b))

    # Build clusters
    clusters: dict[int, list[dict]] = defaultdict(list)
    for a in enriched:
        clusters[find(id(a))].append(a)

    # For each cluster, keep winner
    kept_ids: set[int] = set()
    for cluster in clusters.values():
        keeper = pick_keeper(cluster)
        kept_ids.add(id(keeper))
        dupes = [x for x in cluster if id(x) != id(keeper)]
        if dupes:
            removed += len(dupes)
            print(
                f"[dedup] CLUSTER ({len(cluster)} arts): "
                f"KEEP [{keeper.get('source','?')}] {keeper.get('title','')[:60]}"
            )
            for d in dupes:
                print(
                    f"[dedup]   DROP [{d.get('source','?')}] {d.get('title','')[:60]}"
                )

    if checked:
        print(f"[dedup] Checked {checked} pairs -> removed {removed} duplicates")

    # Strip internal fields and return
    result = []
    for a in enriched:
        if id(a) in kept_ids:
            clean = {k: v for k, v in a.items() if not k.startswith("_")}
            result.append(clean)
    return result

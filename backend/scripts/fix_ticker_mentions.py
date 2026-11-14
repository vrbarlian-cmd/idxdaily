"""
Remove ticker mentions created by the old (buggy) tagging rules.

Old bugs (fixed in ingest.py / google_news.py on 2026-11-14):
  1. Ticker codes were matched case-insensitively, so ordinary words and names
     tagged stocks: "Andi Amran" -> ANDI, "Chandra Asri" -> ASRI,
     "Yupi Indo" -> INDO, "Raja Roti" -> ROTI.
  2. A short alias inside a longer company name tagged the wrong stock:
     "Bumi Resources Minerals" (BRMS) -> BUMI.
  3. Google News queries matched the publisher's name or a generic phrase:
     every FORTUNE Indonesia article -> FORU, all life-insurance news -> JMAS.

A direct mention is removed only on positive evidence of one of these bugs;
mentions we cannot judge (e.g. Google News hits where the company is only in
the article body) are kept. Articles that lose their primary ticker are
re-pointed to a ticker they really mention (or NULL) and their AI summary is
reset so enrich.py rewrites it for the right stock.

Usage (from repo root):
    python -m backend.scripts.fix_ticker_mentions            # dry run
    python -m backend.scripts.fix_ticker_mentions --apply    # write changes
"""
import argparse, asyncio, json, os, re
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env.local", override=True)

import asyncpg

from backend.workers.ingest import (
    load_alias_entries, _build_shared_aliases, detect_tickers, _alias_only_inside_longer,
)

# Tickers whose Google News query matched a publisher name / generic phrase.
QUERY_COLLISION = {"FORU", "JMAS"}
# Corrected aliases (also in backend/db/ticker_overrides.json as exact_aliases).
ALIAS_FIXES = {
    "FORU": ["Fortune Indonesia Tbk"],
    "JMAS": ["Jasa Mitra Abadi", "Asuransi Jiwa Syariah Jasa Mitra Abadi"],
    # The brand is written "GoTo"; with case-sensitive codes it needs an alias.
    "GOTO": ["GoTo Gojek Tokopedia", "GoTo Gojek", "Gojek Tokopedia", "GoTo Group", "GoTo"],
}


def strip_publisher(text: str, source: str) -> str:
    if not source:
        return text
    return re.sub(re.escape(source), " ", text, flags=re.IGNORECASE)


def wrong_reason(sym: str, aliases: list[str], tid: str, text: str, entries) -> str | None:
    upper = f" {text} ".upper()
    # Bug 1: the code is in the text only in normal case (a word/name).
    if re.search(rf"\b{sym}\b", text, flags=re.IGNORECASE) and not re.search(rf"\b{sym}\b", text):
        if not any(a.upper() in upper for a in aliases):
            return "code-as-word"
    # Bug 2: alias only present inside a longer alias of another ticker.
    hits = [a for a in aliases if a.upper() in upper]
    if hits and all(_alias_only_inside_longer(a.upper(), upper, entries, tid) for a in hits):
        return "inside-longer-name"
    # Bug 3: Google News publisher / generic-phrase collisions.
    if sym in QUERY_COLLISION:
        return "query-collision"
    return None


async def main(apply: bool, days: int) -> None:
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])

    if apply:
        for sym, aliases in ALIAS_FIXES.items():
            await conn.execute("UPDATE tickers SET aliases = $2 WHERE symbol = $1", sym, aliases)
    entries = await load_alias_entries(conn)
    if not apply:  # dry run: evaluate with the corrected aliases in memory
        entries = [(s, t, k, ALIAS_FIXES.get(s, a)) for s, t, k, a in entries]
    shared = _build_shared_aliases(entries)
    by_tid = {t: (s, a) for s, t, _k, a in entries}

    rows = await conn.fetch(
        """
        SELECT m.article_id, m.ticker_id, m.match_type, m.match_confidence,
               a.title, coalesce(a.original_summary, '') snippet, a.source, a.ticker_id AS primary_id
        FROM ticker_mentions m JOIN articles a ON a.id = m.article_id
        WHERE m.match_type IS DISTINCT FROM 'macro_impact'
          AND a.published_at > now() - make_interval(days => $1)
        """, days)

    to_delete: list[dict] = []
    for r in rows:
        sym, aliases = by_tid.get(r["ticker_id"], ("?", []))
        text = strip_publisher(f"{r['title']} {r['snippet']}", r["source"])
        if r["ticker_id"] in {t for t, _ in detect_tickers(text, entries, shared)}:
            continue
        reason = wrong_reason(sym, aliases, r["ticker_id"], text, entries)
        if reason:
            to_delete.append({**dict(r), "symbol": sym, "reason": reason})

    from collections import Counter
    print(f"Checked {len(rows)} direct mentions (last {days} days); wrong: {len(to_delete)}")
    for (sym, reason), n in Counter((d["symbol"], d["reason"]) for d in to_delete).most_common(40):
        print(f"  {sym:5} {reason:20} {n}")
    for d in to_delete[:15]:
        print(f"    - {d['symbol']:5} {d['reason']:18} {d['title'][:90]}")

    # Articles whose PRIMARY ticker is among the deleted mentions.
    deleted_keys = {(d["article_id"], d["ticker_id"]) for d in to_delete}
    repoint = {d["article_id"] for d in to_delete if d["primary_id"] == d["ticker_id"]}
    print(f"Articles losing their primary ticker (summary will be rewritten): {len(repoint)}")

    if not apply:
        print("\nDry run only - nothing changed. Re-run with --apply.")
        await conn.close()
        return

    backup = PROJECT_ROOT / "logs" / f"ticker_mention_fix_backup_{datetime.now():%Y-%m-%d_%H%M}.json"
    backup.parent.mkdir(exist_ok=True)
    art_rows = await conn.fetch(
        "SELECT id, ticker_id, ai_summary, sentiment, impact_score, category FROM articles WHERE id = any($1::text[])",
        list(repoint))
    backup.write_text(json.dumps({"mentions": to_delete, "articles": [dict(a) for a in art_rows]},
                                 default=str, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Backup: {backup}")

    async with conn.transaction():
        for art_id, tid in deleted_keys:
            await conn.execute("DELETE FROM ticker_mentions WHERE article_id = $1 AND ticker_id = $2", art_id, tid)
        for art_id in repoint:
            a = await conn.fetchrow("SELECT title, coalesce(original_summary,'') s, source FROM articles WHERE id = $1", art_id)
            text = strip_publisher(f"{a['title']} {a['s']}", a["source"])
            matched = detect_tickers(text, entries, shared)
            for tid, conf in matched:
                await conn.execute(
                    """INSERT INTO ticker_mentions (article_id, ticker_id, match_confidence, match_type)
                       VALUES ($1, $2, $3, 'ticker_match') ON CONFLICT DO NOTHING""", art_id, tid, conf)
            new_primary = matched[0][0] if matched else None
            await conn.execute(
                """UPDATE articles SET ticker_id = $2, ai_summary = NULL, category = 'GENERAL',
                          sentiment = 'NEUTRAL', impact_score = 5.0, updated_at = now()
                   WHERE id = $1""", art_id, new_primary)
    print(f"Deleted {len(deleted_keys)} mentions, re-pointed {len(repoint)} articles (queued for re-enrichment).")
    await conn.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--days", type=int, default=45)
    args = p.parse_args()
    asyncio.run(main(args.apply, args.days))

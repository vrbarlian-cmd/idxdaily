#!/usr/bin/env python3
"""
Batch enrichment worker using the Gemini Batch API.

Submits up to 100 articles per batch job. Results arrive within ~24h at 50%
of the live API cost. Batch state is stored in `enrichment_batches` so you
can safely re-run --check at any time.

Usage (from project root):
  python -m backend.workers.enrich_batch --submit            # queue new articles
  python -m backend.workers.enrich_batch --submit --limit 20 # smaller batch
  python -m backend.workers.enrich_batch --check             # retrieve done batches
  python -m backend.workers.enrich_batch --submit --check    # both in one shot

Scheduling suggestion (Windows Task Scheduler or cron):
  Every hour:         enrich_batch.py --submit
  Every hour +30min:  enrich_batch.py --check
"""

import argparse
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env.local", override=True)

from ._db import get_conn
from .enrich import SYSTEM_PROMPT, USER_TEMPLATE, _EXAMPLE, save_enrichment

DEFAULT_MODEL = "gemini-2.5-flash-lite"
BATCH_SIZE    = 50   # Gemini allows up to 100; 50 keeps batches manageable

# Terminal states — don't re-check these
TERMINAL_STATES = {"JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED",
                   "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"}


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

async def fetch_unenriched(conn, limit: int) -> list[dict]:
    """Articles without AI enrichment, not already in a pending batch."""
    rows = await conn.fetch(
        """
        SELECT a.id, a.title, a.original_summary, a.source,
               a.ticker_id, t.symbol, t.name, t.sector
        FROM articles a
        JOIN tickers t ON t.id = a.ticker_id
        WHERE a.ai_summary IS NULL
        ORDER BY a.published_at DESC
        LIMIT $1
        """,
        limit,
    )
    return [dict(r) for r in rows]


async def store_batch(conn, batch_id: str, article_ids: list[str],
                      model: str, state: str) -> None:
    await conn.execute(
        """
        INSERT INTO enrichment_batches
          (batch_id, submitted_at, status, article_ids_json, model, article_count)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (batch_id) DO NOTHING
        """,
        batch_id,
        datetime.now(timezone.utc),
        state,
        json.dumps(article_ids),
        model,
        len(article_ids),
    )


async def update_batch_status(conn, batch_id: str, state: str,
                               completed: bool = False) -> None:
    completed_at = datetime.now(timezone.utc) if completed else None
    await conn.execute(
        """
        UPDATE enrichment_batches
        SET status = $1, checked_at = $2, completed_at = $3
        WHERE batch_id = $4
        """,
        state,
        datetime.now(timezone.utc),
        completed_at,
        batch_id,
    )


async def fetch_pending_batches(conn) -> list[dict]:
    rows = await conn.fetch(
        """
        SELECT batch_id, article_ids_json, model
        FROM enrichment_batches
        WHERE status NOT IN ('JOB_STATE_SUCCEEDED', 'JOB_STATE_FAILED',
                             'JOB_STATE_CANCELLED', 'JOB_STATE_EXPIRED')
        ORDER BY submitted_at ASC
        """,
    )
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Request builder
# ---------------------------------------------------------------------------

def _build_request(row: dict) -> dict:
    """Build a single Gemini Batch API inline request dict."""
    prompt = USER_TEMPLATE.format(
        example=_EXAMPLE,
        name=row["name"],
        symbol=row["symbol"],
        sector=row.get("sector") or "market",
        title=row["title"],
        snippet=(row.get("original_summary") or row["title"])[:800],
    )
    return {
        "contents": [{"parts": [{"text": prompt}], "role": "user"}],
        "config": {
            "system_instruction": SYSTEM_PROMPT,
            "temperature": 0.3,
            "response_mime_type": "application/json",
        },
    }


def _parse_response_text(text: str) -> dict:
    """Strip markdown fences and parse JSON from a Gemini response."""
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


# ---------------------------------------------------------------------------
# Submit
# ---------------------------------------------------------------------------

async def submit_batch(conn, api_key: str, model: str, limit: int) -> None:
    from google import genai

    rows = await fetch_unenriched(conn, limit)
    if not rows:
        print("[batch-submit] No unenriched articles found — nothing to submit.")
        return

    print(f"[batch-submit] {len(rows)} articles  [model={model}]")

    client = genai.Client(api_key=api_key)
    inline_requests = [_build_request(r) for r in rows]
    article_ids     = [r["id"] for r in rows]

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    batch_job = client.batches.create(
        model=model,
        src=inline_requests,
        config={"display_name": f"saham-enrich-{ts}"},
    )

    batch_id = batch_job.name
    state    = batch_job.state.name
    print(f"[batch-submit] Created: {batch_id}")
    print(f"[batch-submit] Initial state: {state}")
    print(f"[batch-submit] Run --check later to retrieve results.")

    await store_batch(conn, batch_id, article_ids, model, state)


# ---------------------------------------------------------------------------
# Check / retrieve
# ---------------------------------------------------------------------------

async def check_batches(conn, api_key: str) -> None:
    from google import genai

    pending = await fetch_pending_batches(conn)
    if not pending:
        print("[batch-check] No pending batches.")
        return

    client = genai.Client(api_key=api_key)

    for b in pending:
        batch_id    = b["batch_id"]
        article_ids = json.loads(b["article_ids_json"])

        print(f"\n[batch-check] {batch_id}")
        print(f"  Articles in batch: {len(article_ids)}")

        batch_job = client.batches.get(name=batch_id)
        state     = batch_job.state.name
        print(f"  State: {state}")

        if state not in TERMINAL_STATES:
            await update_batch_status(conn, batch_id, state)
            print("  (still running — check again later)")
            continue

        if state != "JOB_STATE_SUCCEEDED":
            await update_batch_status(conn, batch_id, state)
            print(f"  [WARN] Batch ended with state {state} — no results to apply.")
            continue

        # Retrieve inline responses
        responses = getattr(batch_job.dest, "inlined_responses", None) or []
        print(f"  Responses received: {len(responses)}")

        ok = fail = 0
        for i, resp in enumerate(responses):
            if i >= len(article_ids):
                break
            article_id = article_ids[i]
            try:
                text   = resp.response.candidates[0].content.parts[0].text
                result = _parse_response_text(text)
                await save_enrichment(conn, article_id, result)
                ok += 1
            except Exception as exc:
                print(f"  [WARN] article {article_id}: {exc}")
                fail += 1

        await update_batch_status(conn, batch_id, state, completed=True)
        print(f"  Applied: {ok} enriched, {fail} failed")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run(submit: bool, check: bool, limit: int, model: str) -> None:
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("[batch] GEMINI_API_KEY not set — add it to .env and retry.")
        return

    conn = await get_conn()
    try:
        if submit:
            await submit_batch(conn, api_key, model, limit)
        if check:
            await check_batches(conn, api_key)
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gemini Batch API enrichment — 50% cost, async results"
    )
    parser.add_argument("--submit", action="store_true",
                        help="Queue unenriched articles as a new batch job")
    parser.add_argument("--check",  action="store_true",
                        help="Poll pending batches and apply completed results")
    parser.add_argument("--limit",  type=int, default=BATCH_SIZE,
                        help=f"Max articles per batch (default {BATCH_SIZE})")
    parser.add_argument("--all",    action="store_true",
                        help="Submit ALL unenriched articles (overrides --limit)")
    parser.add_argument("--model",  default=DEFAULT_MODEL,
                        help=f"Gemini model (default: {DEFAULT_MODEL})")
    args = parser.parse_args()

    if not args.submit and not args.check:
        parser.error("Specify --submit and/or --check")

    limit = 10_000 if args.all else args.limit
    asyncio.run(run(args.submit, args.check, limit, args.model))


if __name__ == "__main__":
    main()

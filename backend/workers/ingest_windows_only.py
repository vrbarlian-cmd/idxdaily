"""
Windows-only fallback ingest — restricted to the 4 sources confirmed blocked
from the DigitalOcean VM's IP (Cloudflare/CloudFront edge WAF blocks for
CNBC Indonesia, Kontan, Bisnis.com; network-level connection block for Detik
Finance). See MIGRATION_LOG.md for the full diagnosis.

This is a thin wrapper around ingest.py's own run_once() — it does not
duplicate any scraping logic. It writes to the SAME Neon Postgres DB as the
VM; ingest.py's existing URL-based dedup (plus semantic dedup) means running
on two machines against one DB is safe — a story picked up by both the VM's
Google News tier and this script's direct RSS/HTML scrape will simply
dedup against whichever one landed first.

Intended to run ONLY on the Windows machine (replaces the old full-scrape
invocation in Task Scheduler's IDXDaily_Ingest task — see MIGRATION_LOG.md
Stage 11 for the updated scheduler config). The VM continues handling every
other source (Google News across all tiers, Katadata, Bloomberg, Investing.com,
Federal Reserve, IDX Channel, Emiten News) on its own independent cadence —
nothing here talks to or coordinates with the VM.

Usage:
    python -m backend.workers.ingest_windows_only [--limit 50]
"""
import argparse
import asyncio

from backend.workers.ingest import run_once, _acquire_lock, _release_lock

BLOCKED_ON_VM_SOURCES = {
    "Detik Finance",
    "CNBC Indonesia",
    "Kontan",
    "Bisnis.com",
}


def main() -> None:
    _acquire_lock()
    try:
        parser = argparse.ArgumentParser(
            description="Windows-only fallback ingest for the 4 sources blocked from the VM's IP"
        )
        parser.add_argument("--limit", type=int, default=50,
                             help="Max items per RSS feed (default: 50)")
        args = parser.parse_args()

        asyncio.run(run_once(
            rss_limit=args.limit,
            use_ticker_tags=False,
            use_google_news=False,
            only_sources=BLOCKED_ON_VM_SOURCES,
        ))
    finally:
        _release_lock()


if __name__ == "__main__":
    main()

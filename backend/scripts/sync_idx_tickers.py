#!/usr/bin/env python3
"""
Sync the full IDX ticker list (~940 tickers) from Wikipedia into the DB.

Data source: en.wikipedia.org/wiki/IDX_Composite
  Table 5: 820 rows (historical/delisted companies, used as supplement)
  Table 6: 643 rows (current IDX-listed companies, primary)

Both tables have columns: No | Code | Company Name

For each ticker, we auto-generate aliases used by ingest.py for text matching:
  1. Full cleaned name (stripped of "Tbk", "PT", "(Persero)")
  2. First 2 significant words of the cleaned name (if >= 4 chars total)
  3. Custom name_slugs from ticker_overrides.json
  Aliases shorter than 4 characters are discarded to avoid false positives.

New column:  tickers.ticker_tag_enabled
  TRUE  for LQ45 + IDX80 + our existing manually tracked tickers
  FALSE for the rest (general RSS will still catch mentions of any ticker)

Usage:
  python -m backend.scripts.sync_idx_tickers
  python -m backend.scripts.sync_idx_tickers --dry-run   # print without saving
  python -m backend.scripts.sync_idx_tickers --no-web    # skip Wikipedia, update aliases only
"""

import argparse
import asyncio
import json
import re
import sys
import time
import uuid
from pathlib import Path

import requests
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env.local", override=True)

import asyncpg, os

OVERRIDES_FILE = PROJECT_ROOT / "backend" / "db" / "ticker_overrides.json"

HEADERS = {
    "User-Agent": "IDXDailyBot/0.1 (educational research)",
    "Accept": "text/html,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

# ---------------------------------------------------------------------------
# Tickers where ticker_tag_enabled = TRUE
# (LQ45 Feb 2025 + IDX80 + our existing manual set)
# ---------------------------------------------------------------------------
TICKER_TAG_ENABLED: set[str] = {
    # LQ45 (Feb 2025)
    "AALI", "ACES", "ADHI", "ADRO", "AMRT", "ANTM", "ASII",
    "BBCA", "BBNI", "BBRI", "BMRI", "BRIS", "BRPT",
    "CPIN", "EMTK", "ERAA", "EXCL",
    "GGRM", "GOTO",
    "HRUM",
    "ICBP", "INDF", "INTP", "ISAT",
    "JSMR",
    "KLBF",
    "MAPI", "MBMA", "MDKA", "MEDC", "MNCN", "MPMX",
    "PGAS", "PGEO", "PTBA", "PTPP",
    "SIDO", "SMGR", "SMRA",
    "TLKM", "TOWR",
    "UNTR", "UNVR",
    "WSKT", "WTON",
    # IDX80 additions
    "AKRA", "AMII", "ARNA", "AUTO",
    "BBTN", "BFIN", "BJBR", "BJTM", "BMTR", "BNII", "BSDE", "BTPN",
    "CLEO", "CTRA",
    "DOID", "DSNG", "DSSA",
    "ESSA",
    "FASW",
    "HEAL", "HERO", "HMSP", "HRTA",
    "IBST", "INCO", "INKP",
    "JPFA",
    "KBIG", "KKGI",
    "LPPF",
    "MAPA", "MIKA", "MLPL", "MPPA",
    "NICL",
    "PANI", "PNLF",
    "SCMA", "SILO", "SSMS",
    "TBIG", "TKIM", "TPMA", "TRIM",
    "ULTJ",
    "WIFI",
    # Manually tracked (our original 10)
    "BUMI", "PTRO", "BUVA", "DEWA", "BULL",
    # Small-caps added after root-cause diagnosis (2026-05-31)
    # tag_enabled=False was the sole reason these had zero GN coverage
    "BNBR", "CUAN", "ARTO", "MSIN",
    # High-news-flow tickers enabled after 2026-06-03 audit:
    # TPIA  — Chandra Asri Petrochemical (Prajogo group); JP Morgan + MSCI coverage
    # AMMN  — Amman Mineral; major copper/gold producer, LQ45-tier news flow
    # DATA  — Remala Abadi; 14 articles/30d arriving via RSS text-match
    # AMAN  — Makmur Berkah Amanda; 12 articles/30d arriving via RSS text-match
    "TPIA", "AMMN", "DATA", "AMAN",
}

# Common words to skip when generating 2-word aliases (too generic to match)
_SKIP_WORDS = {
    "dan", "dan", "the", "and", "of", "indonesia", "tbk", "tbk.", "pt",
    "persero", "group", "international", "global", "asia", "nusantara",
}


# ---------------------------------------------------------------------------
# Name cleaning & alias generation
# ---------------------------------------------------------------------------

def _clean_name(raw: str) -> str:
    """Strip legal suffixes and normalize whitespace."""
    name = raw
    for suffix in [
        " (Persero) Tbk", " (persero) Tbk", " Persero Tbk",
        " (Persero)", " (persero)",
        " Tbk.", " Tbk", " tbk.", " tbk",
    ]:
        name = name.replace(suffix, "")
    # Strip leading "PT " (case-sensitive)
    name = re.sub(r"^PT\s+", "", name)
    return re.sub(r"\s+", " ", name).strip()


def generate_aliases(symbol: str, name: str, overrides: dict) -> list[str]:
    """Return a deduplicated list of alias strings for this ticker.

    If the override entry has an ``exact_aliases`` key, that list is used
    verbatim (replacing all auto-generated aliases).  This is used for tickers
    where the auto-generated name collides with another ticker (e.g. 'Duta
    Pertiwi' is shared by DPNS and DUTI — DPNS gets only 'Duta Pertiwi
    Nusantara').
    """
    override  = overrides.get(symbol, {})

    # ── exact_aliases: bypass all auto-generation ───────────────────────────
    if "exact_aliases" in override:
        seen: set[str] = set()
        result: list[str] = []
        for s in override["exact_aliases"]:
            s = s.strip()
            if len(s) >= 4 and s not in seen:
                result.append(s)
                seen.add(s)
        return result

    aliases: list[str] = []
    seen = set()

    def add(s: str) -> None:
        s = s.strip()
        if len(s) >= 4 and s not in seen:
            aliases.append(s)
            seen.add(s)

    # 1. Cleaned full name
    clean = _clean_name(name)
    add(clean)

    # 2. First two significant words
    words = [w for w in clean.split() if w.lower() not in _SKIP_WORDS and len(w) >= 3]
    if len(words) >= 2:
        add(" ".join(words[:2]))

    # 3. Custom slugs from overrides
    for slug in override.get("name_slugs", []):
        if slug:
            add(slug)

    return aliases


# ---------------------------------------------------------------------------
# Wikipedia scraper
# ---------------------------------------------------------------------------

def scrape_wikipedia() -> dict[str, str]:
    """
    Returns {symbol: company_name} from both IDX component tables on the
    IDX Composite Wikipedia page.  Active companies (Table 6) take priority.
    """
    url = "https://en.wikipedia.org/wiki/IDX_Composite"
    print(f"[sync] Fetching {url} ...")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as exc:
        raise RuntimeError(f"Wikipedia fetch failed: {exc}")

    soup   = BeautifulSoup(resp.text, "html.parser")
    tables = soup.find_all("table", class_="wikitable")

    if len(tables) < 7:
        raise RuntimeError(f"Expected 7+ wikitables, got {len(tables)}")

    tickers: dict[str, str] = {}

    # Parse both constituent tables; Table 6 (active) is added last so it
    # overwrites any stale names from Table 5 (historical).
    for tbl_idx in [5, 6]:
        tbl  = tables[tbl_idx]
        rows = tbl.find_all("tr")
        count = 0
        for row in rows[1:]:  # skip header row
            cells = [td.get_text(" ", strip=True) for td in row.find_all("td")]
            if len(cells) < 3:
                continue
            # Structure: [row_num, code, company_name, ...]
            code = cells[1].strip()
            name = cells[2].strip()
            # Validate: must be 3-5 uppercase letters
            if not re.fullmatch(r"[A-Z]{3,5}", code):
                continue
            tickers[code] = name
            count += 1
        print(f"[sync]   Table {tbl_idx}: {count} valid tickers parsed")

    return tickers


# ---------------------------------------------------------------------------
# DB upsert
# ---------------------------------------------------------------------------

async def upsert_tickers(
    raw: dict[str, str],
    overrides: dict,
    dry_run: bool,
) -> None:
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url or db_url.startswith("file:"):
        raise RuntimeError("DATABASE_URL is not set or points to SQLite.")

    conn = await asyncpg.connect(db_url)
    try:
        # Fetch existing tickers so we can avoid cascade-deleting articles
        existing = await conn.fetch("SELECT id, symbol FROM tickers")
        existing_map: dict[str, str] = {r["symbol"]: r["id"] for r in existing}

        inserted = updated = skipped = 0

        for symbol, raw_name in raw.items():
            aliases     = generate_aliases(symbol, raw_name, overrides)
            tag_enabled = symbol in TICKER_TAG_ENABLED
            override    = overrides.get(symbol, {})

            # Skip symbols explicitly suppressed via a blank name_slugs + skip_symbol_tag
            # (BANK is in overrides with an empty name_slug — we still upsert it)

            if dry_run:
                print(f"  {'[NEW]' if symbol not in existing_map else '[UPD]'} "
                      f"{symbol:<6} tag={tag_enabled!s:<5} aliases={aliases[:3]}")
                continue

            if symbol in existing_map:
                await conn.execute(
                    """
                    UPDATE tickers
                    SET name=$2, aliases=$3, ticker_tag_enabled=$4, updated_at=now()
                    WHERE symbol=$1
                    """,
                    symbol, raw_name, aliases, tag_enabled,
                )
                updated += 1
            else:
                await conn.execute(
                    """
                    INSERT INTO tickers (id, symbol, name, aliases, ticker_tag_enabled)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    str(uuid.uuid4()), symbol, raw_name, aliases, tag_enabled,
                )
                inserted += 1

        if not dry_run:
            total = await conn.fetchval("SELECT count(*) FROM tickers")
            tag_n = await conn.fetchval(
                "SELECT count(*) FROM tickers WHERE ticker_tag_enabled = TRUE"
            )
            print(f"\n[sync] Done: {inserted} inserted, {updated} updated")
            print(f"[sync] Total tickers in DB: {total}")
            print(f"[sync] ticker_tag_enabled=TRUE: {tag_n}")
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Alias-only refresh (--no-web mode)
# ---------------------------------------------------------------------------

async def refresh_aliases_only(overrides: dict, dry_run: bool) -> None:
    """Recompute aliases for all existing tickers without scraping Wikipedia."""
    db_url = os.environ.get("DATABASE_URL", "")
    conn = await asyncpg.connect(db_url)
    try:
        rows = await conn.fetch("SELECT symbol, name FROM tickers ORDER BY symbol")
        print(f"[sync] Refreshing aliases for {len(rows)} existing tickers ...")
        for row in rows:
            aliases     = generate_aliases(row["symbol"], row["name"], overrides)
            tag_enabled = row["symbol"] in TICKER_TAG_ENABLED
            if not dry_run:
                await conn.execute(
                    """
                    UPDATE tickers
                    SET aliases=$2, ticker_tag_enabled=$3, updated_at=now()
                    WHERE symbol=$1
                    """,
                    row["symbol"], aliases, tag_enabled,
                )
            else:
                print(f"  {row['symbol']:<6} aliases={aliases[:3]}")
        if not dry_run:
            print(f"[sync] Aliases refreshed for {len(rows)} tickers.")
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync full IDX ticker list from Wikipedia into the tickers table"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Print actions without writing to DB")
    parser.add_argument("--no-web", action="store_true",
                        help="Skip Wikipedia scrape; only refresh aliases for existing tickers")
    args = parser.parse_args()

    overrides = {}
    if OVERRIDES_FILE.exists():
        raw_ov = json.loads(OVERRIDES_FILE.read_text(encoding="utf-8"))
        overrides = {k: v for k, v in raw_ov.items() if not k.startswith("_")}
        print(f"[sync] Loaded {len(overrides)} ticker overrides from {OVERRIDES_FILE.name}")

    if args.no_web:
        asyncio.run(refresh_aliases_only(overrides, args.dry_run))
        return

    raw = scrape_wikipedia()
    print(f"[sync] Total unique tickers from Wikipedia: {len(raw)}")

    # Show 5 random examples
    import random
    sample = random.sample(list(raw.items()), min(5, len(raw)))
    print("[sync] Sample tickers:")
    for sym, name in sorted(sample):
        aliases = generate_aliases(sym, name, overrides)
        print(f"  {sym:<6} | {name:<50} | aliases: {aliases}")

    if args.dry_run:
        print("\n[sync] DRY RUN — upsert preview (first 20):")
        asyncio.run(upsert_tickers(dict(list(raw.items())[:20]), overrides, dry_run=True))
        return

    asyncio.run(upsert_tickers(raw, overrides, dry_run=False))


if __name__ == "__main__":
    main()

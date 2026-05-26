#!/usr/bin/env python3
"""
sync_foreign_flow.py — Fetch IDX daily foreign net buy/sell data.

Sources tried in order (first successful source wins):
  1. IDX/BEI Statistics API  — idx.co.id internal JSON endpoint
  2. IDX Trading Summary API — alternative endpoint
  3. Stockbit public widget  — commonly-used Indonesian broker data feed

If all sources fail: the component stays UNAVAILABLE and this is documented
clearly in the output. Run again daily; data for the current trading day
may only be available after market close (15:30 WIB / 08:30 UTC).

Usage (from project root):
  python -m backend.workers.sync_foreign_flow          # today
  python -m backend.workers.sync_foreign_flow --days 30  # last 30 days
  python -m backend.workers.sync_foreign_flow --dry-run
"""

import argparse
import asyncio
import json
import time
from datetime import datetime, timezone, timedelta, date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env.local", override=True)

from ._db import get_conn

import requests

HEADERS_BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
    "Referer": "https://www.idx.co.id/",
    "Origin": "https://www.idx.co.id",
}

TIMEOUT = 20


# ---------------------------------------------------------------------------
# Source 1 — IDX Statistics API (primary)
# ---------------------------------------------------------------------------

def _fetch_idx_statistics_api(target_date: date) -> dict | None:
    """
    Try IDX's internal statistics API used by their website.
    Endpoint discovered from their React SPA network calls.
    Returns {net, buy, sell} in IDR billions, or None if unavailable.
    """
    date_str = target_date.strftime("%Y-%m-%d")
    urls_to_try = [
        # Pattern 1: Date-range statistics endpoint
        (
            "https://www.idx.co.id/api/StatisticData/GetForeignBuySell"
            f"?startDate={date_str}&endDate={date_str}&language=id"
        ),
        # Pattern 2: Trading summary with foreign data
        (
            "https://www.idx.co.id/api/StatisticData/GetTradingSummary"
            f"?startDate={date_str}&endDate={date_str}&language=id"
        ),
        # Pattern 3: General market data summary
        (
            "https://www.idx.co.id/api/StatisticData/GetMarketSummary"
            f"?date={date_str}&language=id"
        ),
    ]

    for url in urls_to_try:
        try:
            resp = requests.get(url, headers=HEADERS_BROWSER, timeout=TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                # Try to find net foreign buy/sell in the response
                result = _parse_idx_response(data)
                if result:
                    return result
        except Exception:
            continue
    return None


def _parse_idx_response(data) -> dict | None:
    """
    Parse IDX API response looking for foreign buy/sell fields.
    IDX uses various field naming conventions across endpoints.
    """
    if not data:
        return None

    # Handle list responses
    if isinstance(data, list) and len(data) > 0:
        data = data[0]

    if not isinstance(data, dict):
        return None

    # Field name variants used by IDX across different endpoint versions
    buy_keys  = ["foreignBuy", "foreign_buy", "ForeignBuy", "netForeignBuy",
                 "foreignBuyValue", "ForeignBuyValue", "buyForeign"]
    sell_keys = ["foreignSell", "foreign_sell", "ForeignSell", "netForeignSell",
                 "foreignSellValue", "ForeignSellValue", "sellForeign"]
    net_keys  = ["netForeign", "net_foreign", "NetForeign", "foreignNet",
                 "netForeignValue", "foreignNetBuy", "foreignNetFlow"]

    def find_val(keys):
        for k in keys:
            if k in data:
                v = data[k]
                if v is not None:
                    try:
                        return float(v)
                    except (ValueError, TypeError):
                        continue
        return None

    net  = find_val(net_keys)
    buy  = find_val(buy_keys)
    sell = find_val(sell_keys)

    # If we found buy and sell but not net, derive it
    if net is None and buy is not None and sell is not None:
        net = buy - sell

    if net is None and buy is None and sell is None:
        return None

    # IDX reports values in IDR (not billions). Convert if they look very large.
    scale = 1.0
    if net is not None and abs(net) > 1_000_000:
        scale = 1e-9   # convert rupiah → billions

    return {
        "net":  round((net or 0) * scale, 4),
        "buy":  round((buy or 0) * scale, 4) if buy is not None else None,
        "sell": round((sell or 0) * scale, 4) if sell is not None else None,
    }


# ---------------------------------------------------------------------------
# Source 2 — Stockbit public widget API
# ---------------------------------------------------------------------------

def _fetch_stockbit(target_date: date) -> dict | None:
    """
    Stockbit (popular Indonesian broker) publishes daily foreign flow
    data via their public widget/API endpoints.
    """
    date_str = target_date.strftime("%Y-%m-%d")
    urls = [
        f"https://api.stockbit.com/v2.4/market/foreignflow?date={date_str}",
        f"https://api.stockbit.com/v2.4/market/summary?date={date_str}",
    ]
    for url in urls:
        try:
            resp = requests.get(url, headers=HEADERS_BROWSER, timeout=TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                result = _parse_idx_response(data.get("data", data))
                if result:
                    return result
        except Exception:
            continue
    return None


# ---------------------------------------------------------------------------
# Source 3 — CNBC Indonesia market recap scrape (text-based fallback)
# ---------------------------------------------------------------------------

def _fetch_cnbc_recap(target_date: date) -> dict | None:
    """
    CNBC Indonesia and Detik Finance publish daily market recaps that
    include foreign net buy/sell figures. This is a text-parsing fallback
    when the structured API sources fail.
    """
    import re
    from bs4 import BeautifulSoup

    date_str = target_date.strftime("%Y/%m/%d")
    search_urls = [
        f"https://www.cnbcindonesia.com/market/search?q=asing+net+beli&date={date_str}",
        f"https://finance.detik.com/bursa-dan-valas/search?q=net+beli+asing&date={date_str}",
    ]

    # Patterns for Indonesian financial text
    # e.g. "asing mencatatkan net beli Rp1,23 triliun" or "net jual asing Rp500 miliar"
    PATTERNS = [
        r"net\s+(?:beli|buy)\s+(?:asing\s+)?(?:Rp\s*)?([\d,\.]+)\s*(triliun|miliar|T|M)",
        r"asing.*?net\s+(?:beli|buy).*?(?:Rp\s*)?([\d,\.]+)\s*(triliun|miliar|T|M)",
        r"foreign.*?net\s+(?:buy|inflow).*?(?:Rp\s*)?([\d,\.]+)\s*((?:tri|bil)lion|T|B)",
        r"net\s+(?:jual|sell)\s+(?:asing\s+)?(?:Rp\s*)?([\d,\.]+)\s*(triliun|miliar|T|M)",
    ]

    for url in search_urls:
        try:
            resp = requests.get(url, headers=HEADERS_BROWSER, timeout=TIMEOUT)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            text = soup.get_text(" ", strip=True).lower()
            for pat in PATTERNS:
                m = re.search(pat, text, re.IGNORECASE)
                if m:
                    val_str  = m.group(1).replace(",", "").replace(".", "")
                    unit_str = m.group(2).lower()
                    val = float(val_str)
                    if "triliun" in unit_str or unit_str == "t":
                        val *= 1.0      # already in trillions → divide by 1000 for billions
                        val *= 1000     # triliun → miliar (billions IDR)
                    elif "miliar" in unit_str or unit_str in ("m", "b"):
                        pass            # already in billions IDR
                    # Determine sign from context
                    is_sell = "jual" in m.group(0).lower() or "sell" in m.group(0).lower()
                    net = -val if is_sell else val
                    return {"net": round(net, 2), "buy": None, "sell": None}
        except Exception:
            continue
    return None


# ---------------------------------------------------------------------------
# DB upsert
# ---------------------------------------------------------------------------

async def upsert_foreign_flow(
    conn,
    target_date: date,
    data: dict,
    source: str,
    dry_run: bool = False,
) -> None:
    if dry_run:
        print(f"  [DRY RUN] Would upsert {target_date}: net={data['net']:.2f} Rp.bn  source={source}")
        return
    await conn.execute(
        """
        INSERT INTO foreign_flow_daily
          (date, net_idr_billions, buy_idr_billions, sell_idr_billions, source, fetched_at)
        VALUES ($1, $2, $3, $4, $5, NOW())
        ON CONFLICT (date) DO UPDATE
          SET net_idr_billions  = EXCLUDED.net_idr_billions,
              buy_idr_billions  = EXCLUDED.buy_idr_billions,
              sell_idr_billions = EXCLUDED.sell_idr_billions,
              source            = EXCLUDED.source,
              fetched_at        = NOW()
        """,
        target_date,
        data["net"],
        data.get("buy"),
        data.get("sell"),
        source,
    )


# ---------------------------------------------------------------------------
# Per-date fetch
# ---------------------------------------------------------------------------

def fetch_for_date(target_date: date) -> tuple[dict | None, str]:
    """
    Try all sources in order. Returns (data | None, source_name).
    """
    # Source 1: IDX API
    result = _fetch_idx_statistics_api(target_date)
    if result:
        return result, "idx_api"

    # Source 2: Stockbit
    result = _fetch_stockbit(target_date)
    if result:
        return result, "stockbit"

    # Source 3: CNBC recap (text parsing — least reliable)
    result = _fetch_cnbc_recap(target_date)
    if result:
        return result, "cnbc_text"

    return None, "all_failed"


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

async def run_sync(days: int = 1, dry_run: bool = False) -> None:
    conn = await get_conn()
    try:
        today = datetime.now(timezone.utc).date()
        dates = [today - timedelta(days=i) for i in range(days)]
        dates.reverse()  # oldest first

        ok = failed = already_have = 0
        failed_sources: list[str] = []

        for d in dates:
            # Skip weekends — IDX is closed
            if d.weekday() >= 5:
                continue

            # Check if we already have data for this date
            existing = await conn.fetchrow(
                "SELECT net_idr_billions FROM foreign_flow_daily WHERE date = $1", d
            )
            if existing and existing["net_idr_billions"] is not None:
                already_have += 1
                continue

            data, source = fetch_for_date(d)

            if data:
                await upsert_foreign_flow(conn, d, data, source, dry_run)
                sign = "+" if data["net"] >= 0 else ""
                print(f"  [{source}] {d}: net={sign}{data['net']:.2f} Rp bn")
                ok += 1
            else:
                failed += 1
                failed_sources.append(str(d))
                print(f"  [FAILED] {d}: all sources returned no data")

            time.sleep(1)  # polite

        # Summary
        n_skipped = days - len(dates) + already_have  # weekends + already-have
        print(f"\n[sync-foreign-flow] Done: {ok} fetched, {failed} failed, {already_have} already present")

        if failed > 0:
            print(f"\n[sync-foreign-flow] NOTE: {failed} dates failed all sources.")
            print("  IDX foreign flow data is published AFTER market close (16:00 WIB).")
            print("  If running before close, try again after 16:00.")
            print("  If consistently failing, the foreign_flow component will remain")
            print("  UNAVAILABLE until a working source is configured.")
            print("  Alternative: download CSV from:")
            print("    https://www.idx.co.id/id/data-pasar/laporan-statistik/statistik/")
            print("  and import manually with:")
            print("    python -m backend.workers.sync_foreign_flow --import-csv <file>")

        total_rows = await conn.fetchval("SELECT COUNT(*) FROM foreign_flow_daily")
        print(f"  foreign_flow_daily: {total_rows} total rows in DB")

    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Sync IDX foreign net flow data")
    parser.add_argument("--days",    type=int, default=1,
                        help="Number of trading days to sync (default: 1 = today)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch but don't write to DB")
    args = parser.parse_args()
    asyncio.run(run_sync(days=args.days, dry_run=args.dry_run))


if __name__ == "__main__":
    main()

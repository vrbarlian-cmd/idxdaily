"""
Daily USD/IDR sync (USD/IDR only).

Unlike sync_market.py this never touches ihsg_daily, so it cannot overwrite the
manually entered IHSG closes. Re-running is safe (upsert by date).

Source: European Central Bank daily reference rates via the free Frankfurter
API (no key). Yahoo IDR=X is only a fallback for weekdays the ECB has no rate
(ECB holidays), because Yahoo's daily IDR=X close is often corrupt: on many
days it prints ~3-4% below the day's own LOW (e.g. 2026-11-12 low 18,140,
close 17,490), which made the Rupiah Stress component swing wildly.
Yahoo bars are only used when the close sits inside that day's high-low range
and within 1.5% of the nearest ECB rate.

Usage (from project root):
    python -m backend.workers.sync_usdidr            # last ~35 days
    python -m backend.workers.sync_usdidr --days 400 # longer repair window
"""

import argparse
import asyncio
import urllib.parse
from datetime import date, datetime, timedelta

import aiohttp

from ._db import get_conn
from .sync_market import SYMBOLS, YAHOO_HEADERS, upsert_usdidr

ECB_URLS = (
    "https://api.frankfurter.app/{start}..{end}?from=USD&to=IDR",
    "https://api.frankfurter.dev/v1/{start}..{end}?base=USD&symbols=IDR",
)
MAX_FALLBACK_GAP = 0.015  # Yahoo close must be within 1.5% of nearest ECB rate


async def fetch_ecb(session: aiohttp.ClientSession, start: date, end: date) -> dict[date, float]:
    last_err: Exception | None = None
    for tpl in ECB_URLS:
        url = tpl.format(start=start.isoformat(), end=end.isoformat())
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    raise ValueError(f"HTTP {resp.status}")
                data = await resp.json(content_type=None)
            rates = data.get("rates") or {}
            out = {date.fromisoformat(k): float(v["IDR"]) for k, v in rates.items() if v.get("IDR")}
            if out:
                return out
            raise ValueError("no IDR rates in response")
        except Exception as e:  # try the next mirror
            last_err = e
    raise ValueError(f"ECB/Frankfurter fetch failed: {last_err}")


async def fetch_yahoo_ohlc(session: aiohttp.ClientSession, range_: str) -> list[dict]:
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{urllib.parse.quote(SYMBOLS['usdidr'])}?range={range_}&interval=1d"
    )
    async with session.get(url, headers=YAHOO_HEADERS, timeout=aiohttp.ClientTimeout(total=20)) as resp:
        if resp.status != 200:
            raise ValueError(f"Yahoo HTTP {resp.status}")
        data = await resp.json(content_type=None)
    result = (data.get("chart", {}).get("result") or [None])[0] or {}
    q = (result.get("indicators", {}).get("quote") or [{}])[0]
    bars = []
    for i, ts in enumerate(result.get("timestamp", [])):
        try:
            c, h, l = q["close"][i], q["high"][i], q["low"][i]
        except (KeyError, IndexError):
            continue
        if None in (c, h, l):
            continue
        bars.append({"date": datetime.utcfromtimestamp(ts).date(),
                     "close": float(c), "high": float(h), "low": float(l)})
    return bars


def nearest_rate(ecb: dict[date, float], d: date) -> float | None:
    if not ecb:
        return None
    k = min(ecb, key=lambda x: abs((x - d).days))
    return ecb[k] if abs((k - d).days) <= 5 else None


async def run(days: int = 35) -> None:
    today = date.today()
    start = today - timedelta(days=days)

    async with aiohttp.ClientSession() as session:
        ecb = await fetch_ecb(session, start, today)
        try:
            yahoo = await fetch_yahoo_ohlc(session, "1mo" if days <= 31 else ("3mo" if days <= 90 else "2y"))
        except Exception as e:
            print(f"Yahoo fallback unavailable: {e}")
            yahoo = []

    bars = [{"date": d, "close": v} for d, v in ecb.items() if d < today]

    used_fallback, rejected = [], []
    for b in yahoo:
        d = b["date"]
        if d in ecb or d >= today or d < start or d.weekday() >= 5:
            continue
        ref = nearest_rate(ecb, d)
        in_range = b["low"] <= b["close"] <= b["high"]
        near = ref is not None and abs(b["close"] / ref - 1) <= MAX_FALLBACK_GAP
        if in_range and near:
            bars.append({"date": d, "close": b["close"]})
            used_fallback.append(d)
        else:
            rejected.append(d)

    bars.sort(key=lambda b: b["date"])
    if not bars:
        raise SystemExit("No USD/IDR bars to write")

    conn = await get_conn()
    try:
        n = await upsert_usdidr(conn, bars)
    finally:
        await conn.close()

    print(f"usdidr_daily: upserted {n} rows (ECB {len(bars) - len(used_fallback)}, "
          f"Yahoo fallback {len(used_fallback)}, Yahoo rejected {len(rejected)}), "
          f"latest {bars[-1]['date']} close {bars[-1]['close']:,.1f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Sync USD/IDR daily closes (ECB primary).")
    ap.add_argument("--days", type=int, default=35, help="How many days back to refresh (default 35)")
    args = ap.parse_args()
    asyncio.run(run(args.days))

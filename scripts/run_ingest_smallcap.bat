@echo off
REM Daily full-universe Google News sweep — runs ALL tickers (~926 tickers, ~46 min).
REM Called by Windows Task Scheduler once daily at 02:00 WIB (off-hours).
REM Catches small-cap tickers (e.g. PACK) that are not ticker_tag_enabled and
REM have no market_cap data, which are skipped by the 2-hour ingest run.

set PROJECT=C:\Users\Vito\OneDrive\Documents\AI News
cd /d "%PROJECT%"

echo [%DATE% %TIME%] Starting small-cap full sweep... >> logs\ingest_smallcap.log

python -m backend.workers.ingest --google-news --gn-tier all >> logs\ingest_smallcap.log 2>&1
python -m backend.workers.enrich --drain --batch 200 --drain-timeout 45 >> logs\ingest_smallcap.log 2>&1

echo [%DATE% %TIME%] Small-cap sweep finished. >> logs\ingest_smallcap.log

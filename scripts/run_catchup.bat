@echo off
REM IDXDaily Catch-up Run
REM Fires on: workstation unlock, or when scheduled tasks were missed while asleep.
REM Runs ONE full pass — does NOT loop or replay missed 15-min slots.
REM Safe to re-run: ingest deduplicates, enrich is idempotent, compute_index overwrites.

set PROJECT=C:\Users\Vito\OneDrive\Documents\AI News
set LOGFILE=%PROJECT%\logs\catchup.log

cd /d "%PROJECT%"

echo [%DATE% %TIME%] === Catch-up started (unlock/resume) === >> "%LOGFILE%"

REM Belt-and-suspenders: clear any stale ingest.lock left by sleep/crash.
REM The tasklist fix in ingest.py is the real solution, but this ensures
REM catchup can always run ingest cleanly on every PC wake regardless.
if exist logs\ingest.lock (
    echo [CATCHUP] Removing stale lock file on wake... >> "%LOGFILE%"
    del logs\ingest.lock
)

REM Full ingest — Google News + RSS + HTML, no market-hours gate
echo [%DATE% %TIME%] Step 1: Ingest... >> "%LOGFILE%"
python -m backend.workers.ingest --google-news --gn-tier tag >> "%LOGFILE%" 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Ingest failed with exit code %ERRORLEVEL% — check ingest.lock and ingest.py >> "%LOGFILE%"
)

REM Drain all unenriched articles (higher batch + longer timeout for a big backlog)
echo [%DATE% %TIME%] Step 2: Enrich... >> "%LOGFILE%"
python -m backend.workers.enrich --drain --batch 150 --drain-timeout 20 >> "%LOGFILE%" 2>&1

REM Sync IHSG + USD/IDR from Yahoo Finance (keeps chart data current)
echo [%DATE% %TIME%] Step 3: Sync market data... >> "%LOGFILE%"
python -m backend.workers.sync_market >> "%LOGFILE%" 2>&1

REM Recompute Fear & Greed so the site shows fresh data
echo [%DATE% %TIME%] Step 4: Compute index... >> "%LOGFILE%"
python -m backend.workers.compute_index >> "%LOGFILE%" 2>&1

echo [%DATE% %TIME%] === Catch-up finished === >> "%LOGFILE%"
echo. >> "%LOGFILE%"

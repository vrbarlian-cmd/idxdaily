@echo off
REM SmallcapSweep — thin wrapper for run_ingest_smallcap.ps1
REM Logic: 06:00-08:00 WIB window check, once-per-day stamp, ~795 disabled tickers.
REM Triggered every 15 min by IDXDaily_SmallcapSweep scheduled task.
cd /d "C:\Users\Vito\OneDrive\Documents\AI News"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\run_ingest_smallcap.ps1"

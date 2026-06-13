@echo off
REM WeekendScrape — thin wrapper for run_ingest_weekend.ps1
REM Logic: Sat/Sun only, 10:00-18:00 WIB window, once-per-day stamp, RSS+HTML only.
REM Triggered every 15 min by DailyIHSG_WeekendScrape scheduled task.
cd /d "C:\Users\Vito\OneDrive\Documents\AI News"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\run_ingest_weekend.ps1"

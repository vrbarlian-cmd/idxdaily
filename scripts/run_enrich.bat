@echo off
REM Run enrichment on any new unenriched articles.
REM Called by Windows Task Scheduler every 30 minutes.
REM Designed to be idempotent — if 0 articles need enrichment it exits quickly.

set PROJECT=C:\Users\Vito\OneDrive\Documents\AI News
cd /d "%PROJECT%"

REM Write timestamped log entry
echo [%DATE% %TIME%] Starting enrich run... >> logs\enrich_scheduler.log

python -m backend.workers.enrich --batch 100 >> logs\enrich_scheduler.log 2>&1

echo [%DATE% %TIME%] Enrich run finished. >> logs\enrich_scheduler.log

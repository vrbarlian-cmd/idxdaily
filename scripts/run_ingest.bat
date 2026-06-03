@echo off
REM IDXDaily Smart Ingest
REM Task Scheduler runs this every 15 minutes, 24/7.
REM The bat enforces the right cadence internally:
REM
REM   Market hours (Mon-Fri 09:00-15:59 WIB):
REM     Full run — Google News (94 tickers, 3s delay) + RSS + HTML + Enrich
REM     Expected duration: ~6-7 min. Leaves ~8-9 min gap. Very polite.
REM
REM   Off-hours / weekends:
REM     RSS + HTML + Enrich only (no Google News).
REM     Runs at most once every 30 minutes (enforced via timestamp file).
REM     Skips silently if < 30min since last off-hours run.

set PROJECT=C:\Users\Vito\OneDrive\Documents\AI News
set LOGFILE=%PROJECT%\logs\ingest_scheduler.log
set STAMP=%PROJECT%\logs\.last_offhours_run

cd /d "%PROJECT%"

REM ── Detect WIB time and day (WIB = UTC+7) ─────────────────────────────────
for /f %%d in ('powershell -NoProfile -Command "(Get-Date).DayOfWeek.value__"') do set DOW=%%d
for /f %%h in ('powershell -NoProfile -Command "(Get-Date).ToUniversalTime().AddHours(7).Hour"') do set HOUR=%%h

REM DayOfWeek: 0=Sun 1=Mon 2=Tue 3=Wed 4=Thu 5=Fri 6=Sat
set MARKET=0
if %DOW% GEQ 1 if %DOW% LEQ 5 (
    if %HOUR% GEQ 9 if %HOUR% LEQ 15 set MARKET=1
)

if "%MARKET%"=="1" goto :market_run

REM ── OFF-HOURS: skip if < 2h since last off-hours run ──────────────────────
if exist "%STAMP%" (
    powershell -NoProfile -Command ^
        "$last = (Get-Item '%STAMP%').LastWriteTime; ^
         $mins = (New-TimeSpan -Start $last -End (Get-Date)).TotalMinutes; ^
         if ($mins -lt 30) { exit 1 } else { exit 0 }"
    if %ERRORLEVEL% NEQ 0 (
        exit /b 0
    )
)

:offhours_run
echo [%DATE% %TIME%] Off-hours ingest (RSS+HTML, no Google News)... >> "%LOGFILE%"
python -m backend.workers.ingest >> "%LOGFILE%" 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Ingest failed with exit code %ERRORLEVEL% — check ingest.lock and ingest.py >> "%LOGFILE%"
)
python -m backend.workers.enrich --drain --batch 100 --drain-timeout 10 >> "%LOGFILE%" 2>&1
python -m backend.workers.compute_index >> "%LOGFILE%" 2>&1
echo [%DATE% %TIME%] Off-hours run finished. >> "%LOGFILE%"
echo. > "%STAMP%"
exit /b 0

:market_run
echo [%DATE% %TIME%] Market-hours ingest (GN+RSS+HTML)... >> "%LOGFILE%"
python -m backend.workers.ingest --google-news --gn-tier tag >> "%LOGFILE%" 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Ingest failed with exit code %ERRORLEVEL% — check ingest.lock and ingest.py >> "%LOGFILE%"
)
python -m backend.workers.enrich --drain --batch 150 --drain-timeout 8 >> "%LOGFILE%" 2>&1
python -m backend.workers.compute_index >> "%LOGFILE%" 2>&1
echo [%DATE% %TIME%] Market-hours run finished. >> "%LOGFILE%"
exit /b 0

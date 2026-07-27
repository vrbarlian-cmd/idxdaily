@echo off
REM IDXDaily Catch-up Run
REM Fires on: workstation unlock
REM Two gates before ingest runs:
REM   1. 6-hour staleness gate (check_stale.py) -- skip if data fresh
REM   2. Last-resort daily gate (check_today_count.py) -- run if <10 articles today

set PROJECT=C:\Users\Vito\OneDrive\Documents\AI News
set LOGFILE=C:\ProgramData\IDXDaily\logs\catchup.log

pushd "%PROJECT%"

echo [%DATE% %TIME%] === Catch-up started === >> "%LOGFILE%"

REM Gate 1: skip if ingest ran recently (< 6h ago)
python scripts\check_stale.py >> "%LOGFILE%" 2>&1
if %ERRORLEVEL% equ 0 goto :check_today

REM Data is stale -- run full catchup
goto :run_ingest

:check_today
REM Gate 2: last-resort daily guarantee -- run if <10 articles today
echo [%DATE% %TIME%] Data fresh (< 6h). Checking today article count... >> "%LOGFILE%"
python scripts\check_today_count.py >> "%LOGFILE%" 2>&1
if %ERRORLEVEL% equ 1 goto :last_resort
echo [%DATE% %TIME%] Sufficient articles today, skipping catch-up. >> "%LOGFILE%"
goto :end

:last_resort
echo [%DATE% %TIME%] LAST RESORT: < 10 articles today -- running ingest. >> "%LOGFILE%"

:run_ingest
echo [%DATE% %TIME%] Step 1: Ingest... >> "%LOGFILE%"
python -m backend.workers.ingest --google-news --gn-tier tag >> "%LOGFILE%" 2>&1

echo [%DATE% %TIME%] Step 2: Enrich... >> "%LOGFILE%"
python -m backend.workers.enrich --drain --batch 150 --drain-timeout 20 >> "%LOGFILE%" 2>&1

echo [%DATE% %TIME%] Step 3: Sync market... >> "%LOGFILE%"
python -m backend.workers.sync_market >> "%LOGFILE%" 2>&1

echo [%DATE% %TIME%] Step 4: Compute index... >> "%LOGFILE%"
python -m backend.workers.compute_index >> "%LOGFILE%" 2>&1

echo [%DATE% %TIME%] === Catch-up finished === >> "%LOGFILE%"

:end
echo. >> "%LOGFILE%"
popd

@echo off
REM IDXDaily Catch-up Run
REM Fires on: workstation unlock

set PROJECT=C:\Users\Vito\OneDrive\Documents\AI News
set LOGFILE=C:\ProgramData\IDXDaily\logs\catchup.log

pushd "%PROJECT%"

echo [%DATE% %TIME%] === Catch-up started === >> "%LOGFILE%"

REM 6-hour staleness gate: skip if ingest ran recently
python scripts\check_stale.py >> "%LOGFILE%" 2>&1
if %ERRORLEVEL% equ 0 goto :skip

echo [%DATE% %TIME%] Step 1: Ingest... >> "%LOGFILE%"
python -m backend.workers.ingest --google-news --gn-tier tag >> "%LOGFILE%" 2>&1

echo [%DATE% %TIME%] Step 2: Enrich... >> "%LOGFILE%"
python -m backend.workers.enrich --drain --batch 150 --drain-timeout 20 >> "%LOGFILE%" 2>&1

echo [%DATE% %TIME%] Step 3: Sync market... >> "%LOGFILE%"
python -m backend.workers.sync_market >> "%LOGFILE%" 2>&1

echo [%DATE% %TIME%] Step 4: Compute index... >> "%LOGFILE%"
python -m backend.workers.compute_index >> "%LOGFILE%" 2>&1

echo [%DATE% %TIME%] === Catch-up finished === >> "%LOGFILE%"
goto :end

:skip
echo [%DATE% %TIME%] Data fresh (< 6h), skipping catch-up. >> "%LOGFILE%"

:end
echo. >> "%LOGFILE%"
popd

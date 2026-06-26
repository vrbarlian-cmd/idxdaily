@echo off
REM IDXDaily Smart Ingest
REM Task Scheduler runs this every 15 minutes, 24/7.
REM The bat enforces the right cadence internally:
REM
REM   Market hours (Mon-Fri 09:00-15:59 WIB):
REM     Full run - Google News (94 tickers, 3s delay) + RSS + HTML + Enrich
REM     Expected duration: ~6-7 min. Leaves ~8-9 min gap. Very polite.
REM
REM   Off-hours (weekdays):
REM     RSS + HTML + Enrich only (no Google News).
REM     Runs at most once every 30 minutes (enforced via .last_offhours_run stamp).
REM
REM   Weekends (Sat/Sun):
REM     RSS + HTML + Enrich only (no Google News).
REM     Runs at most ONCE PER DAY (enforced via ProgramData logs stamp).

set PROJECT=C:\Users\Vito\OneDrive\Documents\AI News
set LOGFILE=C:\ProgramData\IDXDaily\logs\ingest_scheduler.log
set STAMP=C:\ProgramData\IDXDaily\logs\.last_offhours_run
set LOCK=C:\ProgramData\IDXDaily\logs\ingest.lock
set LOGDIR=C:\ProgramData\IDXDaily\logs

cd /d "%PROJECT%"

REM -- Concurrency guard --
REM Using goto instead of if/block to avoid CMD paren-counting issues in PowerShell args.
if not exist "%LOCK%" goto lock_clear
powershell -NoProfile -Command "$age=(New-TimeSpan -Start (Get-Item '%LOCK%').LastWriteTime -End (Get-Date)).TotalMinutes; if ($age -gt 60) { Remove-Item '%LOCK%' -Force; exit 0 } else { exit 1 }"
if %ERRORLEVEL% NEQ 0 goto lock_skip
echo [%DATE% %TIME%] Removed stale lock, continuing. >> "%LOGFILE%"
:lock_clear
echo. > "%LOCK%"
goto detect_time

:lock_skip
echo [%DATE% %TIME%] Lock exists and is fresh, skipping. >> "%LOGFILE%"
exit /b 0

:detect_time
REM -- Detect WIB time and day (WIB = UTC+7) --
for /f %%d in ('powershell -NoProfile -Command "(Get-Date).DayOfWeek.value__"') do set DOW=%%d
for /f %%h in ('powershell -NoProfile -Command "(Get-Date).ToUniversalTime().AddHours(7).Hour"') do set HOUR=%%h

REM DayOfWeek: 0=Sun 1=Mon 2=Tue 3=Wed 4=Thu 5=Fri 6=Sat
set MARKET=0
if %DOW% GEQ 1 if %DOW% LEQ 5 if %HOUR% GEQ 9 if %HOUR% LEQ 15 set MARKET=1

if "%MARKET%"=="1" goto market_run

REM -- OFF-HOURS --
set WEEKEND=0
if %DOW% EQU 0 set WEEKEND=1
if %DOW% EQU 6 set WEEKEND=1

REM Weekend guard: run at most once per day
if not "%WEEKEND%"=="1" goto check_stamp
powershell -NoProfile -Command "$d=(Get-Date).ToString('yyyyMMdd'); $s='%LOGDIR%\weekend_ingest_'+$d+'.stamp'; if (Test-Path $s) { exit 1 } else { exit 0 }"
if %ERRORLEVEL% NEQ 0 goto weekend_skip
goto offhours_run

:weekend_skip
echo [%DATE% %TIME%] Weekend ingest already ran today, skipping. >> "%LOGFILE%"
del "%LOCK%" 2>nul
exit /b 0

:check_stamp
REM Weekday evening cutoff: no ingest after 18:00 WIB (saves Gemini credits)
if "%WEEKEND%"=="0" if %HOUR% GEQ 18 goto evening_skip
REM Weekday off-hours: skip if < 30 min since last run
if not exist "%STAMP%" goto offhours_run
powershell -NoProfile -Command "$last=(Get-Item '%STAMP%').LastWriteTime; $mins=(New-TimeSpan -Start $last -End (Get-Date)).TotalMinutes; if ($mins -lt 30) { exit 1 } else { exit 0 }"
if %ERRORLEVEL% NEQ 0 goto stamp_skip
goto offhours_run

:stamp_skip
del "%LOCK%" 2>nul
exit /b 0

:evening_skip
del "%LOCK%" 2>nul
exit /b 0

:offhours_run
echo [%DATE% %TIME%] Off-hours ingest (RSS+HTML, no Google News)... >> "%LOGFILE%"
python -m backend.workers.ingest >> "%LOGFILE%" 2>&1
if %ERRORLEVEL% neq 0 echo [ERROR] Ingest failed with exit code %ERRORLEVEL% >> "%LOGFILE%"
python -m backend.workers.enrich --drain --batch 100 --drain-timeout 10 >> "%LOGFILE%" 2>&1
python -m backend.workers.compute_index >> "%LOGFILE%" 2>&1
echo [%DATE% %TIME%] Off-hours run finished. >> "%LOGFILE%"
if not "%WEEKEND%"=="1" goto offhours_done
powershell -NoProfile -Command "$d=(Get-Date).ToString('yyyyMMdd'); (Get-Date) | Out-File ('%LOGDIR%\weekend_ingest_'+$d+'.stamp') -Encoding utf8"
echo [%DATE% %TIME%] Weekend stamp written - won't run again today. >> "%LOGFILE%"
:offhours_done
echo. > "%STAMP%"
del "%LOCK%" 2>nul
exit /b 0

:market_run
echo [%DATE% %TIME%] Market-hours ingest (GN+RSS+HTML)... >> "%LOGFILE%"
python -m backend.workers.ingest --google-news --gn-tier tag >> "%LOGFILE%" 2>&1
if %ERRORLEVEL% neq 0 echo [ERROR] Ingest failed with exit code %ERRORLEVEL% >> "%LOGFILE%"
python -m backend.workers.enrich --drain --batch 150 --drain-timeout 8 >> "%LOGFILE%" 2>&1
python -m backend.workers.compute_index >> "%LOGFILE%" 2>&1
echo [%DATE% %TIME%] Market-hours run finished. >> "%LOGFILE%"
del "%LOCK%" 2>nul
exit /b 0

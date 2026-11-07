@echo off
REM IDXDaily Windows Fallback Ingest - SUPPLEMENTARY to the VM
REM Task Scheduler still fires this every 15 minutes, but it now only
REM actually ingests up to 3 times/weekday - NOT at fixed clock hours,
REM but "whenever the PC happens to be on", gated by a minimum 2-hour gap
REM since the last run. Never runs on weekends. This machine covers only
REM the 4 sources confirmed IP/WAF blocked from the VM's IP - see
REM backend/workers/ingest_windows_only.py.
REM
REM Why session-based instead of fixed hours (Stage 14b): fixed hours
REM (e.g. 08:00/13:00/18:00) meant a short on/off usage pattern could miss
REM every slot and get zero ingests that day - Task Scheduler's
REM StartWhenAvailable catches up a MISSED trigger, but the catch-up run
REM executes at the CURRENT wall-clock hour, not the originally-scheduled
REM one, so a missed fixed-hour slot was simply lost, not caught up.
REM
REM This design instead asks "has it been >=2 hours since our last actual
REM run?" on every tick - so the very first tick after you turn the PC on
REM (StartWhenAvailable fires it promptly) almost always qualifies, since
REM the last run was hours/a day ago. Guarantees at least one ingest per
REM usage session, while the 3/day cap and 2-hour spacing keep total cost
REM the same as the fixed-hour design.
REM
REM Still fired via the same 15-min Task Scheduler trigger (unchanged, no
REM need to touch Task Scheduler config) - the daily-count + gap-timer
REM stamp files below do the actual gating.
REM
REM Stage 15: weekends now also get 1 any-time run/day (whenever the PC is
REM on), separate from the weekday 3-slot/gap system - just a single daily
REM stamp, no 2-hour gap required since it's already capped at 1/day. This
REM is on top of the VM's own weekend 3-slot schedule, not a replacement.

set PROJECT=C:\Users\Vito\OneDrive\Documents\AI News
set LOGFILE=C:\ProgramData\IDXDaily\logs\ingest_scheduler.log
set PYTHONIOENCODING=utf-8
set LOCK=C:\ProgramData\IDXDaily\logs\ingest.lock
set LOGDIR=C:\ProgramData\IDXDaily\logs
set LASTRUN=C:\ProgramData\IDXDaily\logs\windows_last_run.stamp
set MAX_RUNS_PER_DAY=3
set MIN_GAP_MINUTES=120

cd /d "%PROJECT%"

REM -- Concurrency guard --
REM Using goto instead of if/block to avoid CMD paren-counting issues in PowerShell args.
if not exist "%LOCK%" goto lock_clear
powershell -NoProfile -Command "$age=(New-TimeSpan -Start (Get-Item '%LOCK%').LastWriteTime -End (Get-Date)).TotalMinutes; if ($age -gt 60) { Remove-Item '%LOCK%' -Force; exit 0 } else { exit 1 }"
if %ERRORLEVEL% NEQ 0 goto lock_skip
echo [%DATE% %TIME%] Removed stale lock, continuing. >> "%LOGFILE%"
:lock_clear
goto detect_time

:lock_skip
echo [%DATE% %TIME%] Lock exists and is fresh, skipping. >> "%LOGFILE%"
exit /b 0

:detect_time
for /f %%d in ('powershell -NoProfile -Command "(Get-Date).DayOfWeek.value__"') do set DOW=%%d
for /f %%t in ('powershell -NoProfile -Command "(Get-Date).ToString('yyyyMMdd')"') do set TODAY=%%t

REM DayOfWeek: 0=Sun 1=Mon 2=Tue 3=Wed 4=Thu 5=Fri 6=Sat
REM Weekends: 1 any-time run/day (Stage 15), on top of the VM's own weekend
REM 3-slot schedule - separate cap, no 2-hour gap requirement since it's
REM already limited to 1/day.
if %DOW% EQU 0 goto weekend_check
if %DOW% EQU 6 goto weekend_check

REM -- Find the next available run-slot (1, 2, or 3) for today --
REM Avoiding nested if/else blocks (same paren-counting caution as above).
if exist "%LOGDIR%\windows_run1_%TODAY%.stamp" goto try_slot2
set SLOT=1
goto slot_found

:try_slot2
if exist "%LOGDIR%\windows_run2_%TODAY%.stamp" goto try_slot3
set SLOT=2
goto slot_found

:try_slot3
if exist "%LOGDIR%\windows_run3_%TODAY%.stamp" goto daily_cap_reached
set SLOT=3

:slot_found
set STAMPFILE=%LOGDIR%\windows_run%SLOT%_%TODAY%.stamp
REM -- Enforce minimum gap since the last actual run (any slot, any day) --
if not exist "%LASTRUN%" goto run_ingest
powershell -NoProfile -Command "$last=(Get-Item '%LASTRUN%').LastWriteTime; $mins=(New-TimeSpan -Start $last -End (Get-Date)).TotalMinutes; if ($mins -lt %MIN_GAP_MINUTES%) { exit 1 } else { exit 0 }"
if %ERRORLEVEL% NEQ 0 goto gap_not_elapsed
goto run_ingest

:weekend_check
if exist "%LOGDIR%\windows_weekend_%TODAY%.stamp" goto weekend_skip
set SLOT=W
set STAMPFILE=%LOGDIR%\windows_weekend_%TODAY%.stamp
goto run_ingest

:weekend_skip
exit /b 0

:daily_cap_reached
exit /b 0

:gap_not_elapsed
exit /b 0

:run_ingest
echo. > "%LOCK%"
echo [%DATE% %TIME%] Windows fallback ingest (session run %SLOT% of max %MAX_RUNS_PER_DAY% today)... >> "%LOGFILE%"
python -m backend.workers.ingest_windows_only >> "%LOGFILE%" 2>&1
if %ERRORLEVEL% neq 0 echo [ERROR] Ingest failed with exit code %ERRORLEVEL% >> "%LOGFILE%"
echo [%DATE% %TIME%] Session run %SLOT% finished. >> "%LOGFILE%"
echo. > "%STAMPFILE%"
echo. > "%LASTRUN%"
del "%LOCK%" 2>nul
exit /b 0

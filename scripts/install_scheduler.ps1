# Install Windows Task Scheduler tasks for IDXDaily
# Run as Administrator once:
#   powershell -ExecutionPolicy Bypass -File scripts\install_scheduler.ps1

$project = "C:\Users\Vito\OneDrive\Documents\AI News"

# Ensure logs directory exists
New-Item -ItemType Directory -Force -Path "$project\logs" | Out-Null

# ── Task 1: Enrich new articles every 30 minutes ─────────────────────────────
$action1 = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$project\scripts\run_enrich.bat`"" `
    -WorkingDirectory $project

$trigger1 = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Minutes 30) -Once -At "00:00"

Register-ScheduledTask `
    -TaskName "IDXDaily_Enrich" `
    -Action $action1 `
    -Trigger $trigger1 `
    -Description "Enrich new unenriched articles with Gemini AI (every 30 min)" `
    -RunLevel Highest `
    -Force | Out-Null
Write-Host "[OK] Registered: IDXDaily_Enrich (every 30 min)"

# ── Task 2: Ingest big-cap Google News every 2 hours ─────────────────────────
$action2 = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$project\scripts\run_ingest.bat`"" `
    -WorkingDirectory $project

$trigger2 = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Hours 2) -Once -At "00:00"

Register-ScheduledTask `
    -TaskName "IDXDaily_Ingest" `
    -Action $action2 `
    -Trigger $trigger2 `
    -Description "Ingest big-cap Google News and enrichment every 2 hours" `
    -RunLevel Highest `
    -Force | Out-Null
Write-Host "[OK] Registered: IDXDaily_Ingest (every 2 hours)"

# ── Task 3: Sync market data (IHSG/USD) daily at 6 AM ───────────────────────
$action3 = New-ScheduledTaskAction `
    -Execute "python.exe" `
    -Argument "-m backend.workers.sync_market" `
    -WorkingDirectory $project

$trigger3 = New-ScheduledTaskTrigger -Daily -At "06:00"

Register-ScheduledTask `
    -TaskName "IDXDaily_SyncMarket" `
    -Action $action3 `
    -Trigger $trigger3 `
    -Description "Sync IHSG + USD/IDR daily price data from Yahoo Finance" `
    -RunLevel Highest `
    -Force | Out-Null
Write-Host "[OK] Registered: IDXDaily_SyncMarket (daily 06:00)"

# ── Task 4: Compute Fear & Greed index daily at 6:10 AM ─────────────────────
$action4 = New-ScheduledTaskAction `
    -Execute "python.exe" `
    -Argument "-m backend.workers.compute_index" `
    -WorkingDirectory $project

$trigger4 = New-ScheduledTaskTrigger -Daily -At "06:10"

Register-ScheduledTask `
    -TaskName "IDXDaily_ComputeIndex" `
    -Action $action4 `
    -Trigger $trigger4 `
    -Description "Compute Fear & Greed index after market data sync" `
    -RunLevel Highest `
    -Force | Out-Null
Write-Host "[OK] Registered: IDXDaily_ComputeIndex (daily 06:10)"

Write-Host ""
Write-Host "All tasks registered. View in Task Scheduler > IDXDaily_*"
Write-Host "Logs are written to: $project\logs\"

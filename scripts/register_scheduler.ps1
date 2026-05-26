# IDXDaily Scheduler Registration
# Run this ONCE as Administrator:
#   Right-click PowerShell → "Run as administrator"
#   cd "C:\Users\Vito\OneDrive\Documents\AI News\scripts"
#   .\register_scheduler.ps1
#
# Tasks registered:
#   IDXDaily_Ingest        — every 15 min, 24/7
#                               run_ingest.bat enforces the real cadence internally:
#                               • Market hours (Mon-Fri 09:00-15:59 WIB): full run (GN+RSS+HTML+enrich)
#                               • Off-hours/weekends: RSS+HTML+enrich at most once every 2 hours
#   IDXDaily_SmallcapSweep — daily at 02:00, Google News for ALL tickers (catches PACK etc.)
#
# IDXDaily_Enrich is intentionally NOT registered: enrich now runs inside run_ingest.bat.

$projectRoot = "C:\Users\Vito\OneDrive\Documents\AI News"
$scriptsDir  = "$projectRoot\scripts"

# Ensure logs directory exists
New-Item -ItemType Directory -Force -Path "$projectRoot\logs" | Out-Null

function Register-BatTask {
    param($Name, $BatFile, $Trigger, $Description)
    $action   = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$BatFile`"" -WorkingDirectory $projectRoot
    $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 3) -StartWhenAvailable $true -WakeToRun $false
    $principal= New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
    Unregister-ScheduledTask -TaskName $Name -Confirm:$false -ErrorAction SilentlyContinue
    $task = Register-ScheduledTask -TaskName $Name -Description $Description `
                -Action $action -Trigger $Trigger -Settings $settings -Principal $principal -Force
    if ($task) {
        Write-Host "  OK: $Name  (State=$($task.State))" -ForegroundColor Green
    } else {
        Write-Host "  FAIL: $Name" -ForegroundColor Red
    }
}

Write-Host "`nRegistering IDXDaily scheduled tasks..." -ForegroundColor Cyan

# Remove stale Enrich task if it exists from a previous registration
Unregister-ScheduledTask -TaskName "IDXDaily_Enrich" -Confirm:$false -ErrorAction SilentlyContinue

# 1. Main ingest: every 15 minutes, 24/7
#    The bat itself enforces market-hours vs off-hours cadence — Task Scheduler just wakes it up.
$t1 = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Minutes 15) -Once -At (Get-Date).ToString("HH:mm")
Register-BatTask "IDXDaily_Ingest" "$scriptsDir\run_ingest.bat" $t1 `
    "Smart ingest: market hours=GN+RSS+HTML+enrich every 15min; off-hours=RSS+HTML+enrich at most every 2h"

# 2. Small-cap full sweep: once daily at 02:00 WIB (UTC+7 = 19:00 UTC previous day)
#    Covers ALL 926 tickers via Google News, catching small-caps not in ticker_tag_enabled
$t2 = New-ScheduledTaskTrigger -Daily -At "02:00"
Register-BatTask "IDXDaily_SmallcapSweep" "$scriptsDir\run_ingest_smallcap.bat" $t2 `
    "Full Google News sweep for ALL 926 tickers (catches PACK and other small-caps), daily at 02:00"

Write-Host "`nVerifying:" -ForegroundColor Cyan
Get-ScheduledTask | Where-Object { $_.TaskName -like "IDXDaily_*" } |
    Select-Object TaskName, State |
    Format-Table -AutoSize

Write-Host "Done. Tasks will fire on their next scheduled time." -ForegroundColor Green
Write-Host "To run immediately: schtasks /run /tn IDXDaily_Ingest" -ForegroundColor Yellow

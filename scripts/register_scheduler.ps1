# IDXDaily Scheduler Registration
# Run ONCE as Administrator:
#   Right-click PowerShell -> "Run as administrator"
#   cd "C:\Users\Vito\OneDrive\Documents\AI News\scripts"
#   .\register_scheduler.ps1
#
# Tasks registered:
#   IDXDaily_Ingest        - every 15 min, StartWhenAvailable (catches up on missed runs after sleep)
#   IDXDaily_Catchup       - on workstation UNLOCK
#                            Runs: ingest -> enrich -> compute_index (one pass, no loop)
#   IDXDaily_SmallcapSweep - daily at 02:00, Google News for ALL tickers
#
# All tasks run HIDDEN (no CMD window) via wscript.exe + run_hidden.vbs.
# Output is still written to logs\ as defined in each .bat file.

$projectRoot = "C:\Users\Vito\OneDrive\Documents\AI News"
$scriptsDir  = "$projectRoot\scripts"
$vbsPath     = "$scriptsDir\run_hidden.vbs"

New-Item -ItemType Directory -Force -Path "$projectRoot\logs" | Out-Null

# Sanity check — VBScript wrapper must exist
if (-not (Test-Path $vbsPath)) {
    Write-Host "ERROR: run_hidden.vbs not found at $vbsPath" -ForegroundColor Red
    exit 1
}

# =============================================================================
# STEP 0 — Nuke ALL existing IDXDaily_* tasks before re-registering.
# This prevents stale cmd.exe-based tasks from surviving alongside new ones.
# =============================================================================
Write-Host "`nRemoving all existing IDXDaily_* tasks..." -ForegroundColor Yellow
Get-ScheduledTask -TaskName "IDXDaily_*" -ErrorAction SilentlyContinue |
    Unregister-ScheduledTask -Confirm:$false -ErrorAction SilentlyContinue
# Also clean up the old installer's task names (IDXDaily_Enrich, SahamSinyal_*)
foreach ($old in @("IDXDaily_Enrich", "IDXDaily_SyncMarket", "IDXDaily_ComputeIndex")) {
    Unregister-ScheduledTask -TaskName $old -Confirm:$false -ErrorAction SilentlyContinue
}
Get-ScheduledTask -TaskName "SahamSinyal_*" -ErrorAction SilentlyContinue |
    Unregister-ScheduledTask -Confirm:$false -ErrorAction SilentlyContinue
Write-Host "  Done — slate is clean." -ForegroundColor Green

# =============================================================================
# Helper: register a task from a .bat file.
# Action is ALWAYS wscript.exe + run_hidden.vbs so NO console window appears.
# bWaitOnReturn=True in run_hidden.vbs means Task Scheduler tracks the task
# as Running until the .bat exits — MultipleInstances=IgnoreNew works correctly
# and LastTaskResult reflects the real bat exit code.
# =============================================================================
function Register-BatTask {
    param($Name, $BatFile, $Trigger, $Description)
    $action   = New-ScheduledTaskAction `
                    -Execute "wscript.exe" `
                    -Argument "`"$vbsPath`" `"$BatFile`"" `
                    -WorkingDirectory $projectRoot
    $settings = New-ScheduledTaskSettingsSet `
                    -ExecutionTimeLimit (New-TimeSpan -Hours 3) `
                    -StartWhenAvailable `
                    -WakeToRun:$false `
                    -MultipleInstances IgnoreNew
    $principal = New-ScheduledTaskPrincipal `
                    -UserId $env:USERNAME `
                    -LogonType Interactive `
                    -RunLevel Highest
    $task = Register-ScheduledTask `
                -TaskName $Name -Description $Description `
                -Action $action -Trigger $Trigger `
                -Settings $settings -Principal $principal -Force
    if ($task) {
        Write-Host "  OK: $Name — Execute=$($task.Actions[0].Execute)" -ForegroundColor Green
    } else {
        Write-Host "  FAIL: $Name" -ForegroundColor Red
    }
}

Write-Host "`nRegistering IDXDaily tasks (hidden via wscript.exe + run_hidden.vbs)..." -ForegroundColor Cyan

# =============================================================================
# Task 1 — IDXDaily_Ingest: every 15 min
# =============================================================================
$t1 = New-ScheduledTaskTrigger -Once -At (Get-Date).ToString("HH:mm") `
          -RepetitionInterval (New-TimeSpan -Minutes 15)
Register-BatTask "IDXDaily_Ingest" "$scriptsDir\run_ingest.bat" $t1 `
    "Smart ingest every 15min; market hours=GN+RSS+enrich; off-hours=RSS+enrich at most every 2h. StartWhenAvailable catches up after sleep. Hidden via run_hidden.vbs."

# =============================================================================
# Task 2 — IDXDaily_Catchup: fires on workstation UNLOCK (COM trigger)
# =============================================================================
Write-Host "  Registering IDXDaily_Catchup (unlock trigger via COM)..." -ForegroundColor Yellow

try {
    $svc = New-Object -ComObject "Schedule.Service"
    $svc.Connect()
    $folder  = $svc.GetFolder("\")
    $taskDef = $svc.NewTask(0)

    $taskDef.Principal.UserId    = $env:USERNAME
    $taskDef.Principal.LogonType = 3   # TASK_LOGON_INTERACTIVE_TOKEN
    $taskDef.Principal.RunLevel  = 1   # TASK_RUNLEVEL_HIGHEST

    $taskDef.Settings.ExecutionTimeLimit = "PT3H"
    $taskDef.Settings.StartWhenAvailable = $true
    $taskDef.Settings.WakeToRun          = $false
    $taskDef.Settings.MultipleInstances  = 3       # TASK_INSTANCES_IGNORE_NEW
    $taskDef.Settings.Enabled            = $true
    $taskDef.RegistrationInfo.Description = "Full catch-up pass (ingest+enrich+compute_index) on unlock. Hidden via run_hidden.vbs."

    $trigger             = $taskDef.Triggers.Create(11)  # TASK_TRIGGER_SESSION_STATE_CHANGE
    $trigger.StateChange = 8                              # TASK_SESSION_UNLOCK
    $trigger.Enabled     = $true

    # Action: wscript.exe -> run_hidden.vbs -> run_catchup.bat (no window)
    $action                  = $taskDef.Actions.Create(0)  # TASK_ACTION_EXEC
    $action.Path             = "wscript.exe"
    $action.Arguments        = "`"$vbsPath`" `"$scriptsDir\run_catchup.bat`""
    $action.WorkingDirectory = $projectRoot

    # 6 = TASK_CREATE_OR_UPDATE, 3 = TASK_LOGON_INTERACTIVE_TOKEN
    $folder.RegisterTaskDefinition("IDXDaily_Catchup", $taskDef, 6, $null, $null, 3) | Out-Null
    Write-Host "  OK: IDXDaily_Catchup (unlock trigger, hidden)" -ForegroundColor Green

} catch {
    Write-Host "  FAIL: IDXDaily_Catchup (COM) - $_" -ForegroundColor Red
    Write-Host "  Fallback: AtLogon trigger..." -ForegroundColor Yellow
    $t2fb = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    Register-BatTask "IDXDaily_Catchup" "$scriptsDir\run_catchup.bat" $t2fb `
        "Catch-up on login/unlock (fallback trigger): ingest+enrich+compute_index. Hidden via run_hidden.vbs."
}

# =============================================================================
# Task 3 — IDXDaily_SmallcapSweep: daily at 02:00
# =============================================================================
$t3 = New-ScheduledTaskTrigger -Daily -At "02:00"
Register-BatTask "IDXDaily_SmallcapSweep" "$scriptsDir\run_ingest_smallcap.bat" $t3 `
    "Full Google News sweep for ALL tickers, daily at 02:00. Hidden via run_hidden.vbs."

# =============================================================================
# Verify — confirm Execute column shows wscript.exe, NOT cmd.exe
# =============================================================================
Write-Host "`n=== Verification ===" -ForegroundColor Cyan
Get-ScheduledTask | Where-Object { $_.TaskName -like "IDXDaily_*" } |
    Select-Object TaskName, State,
        @{N="Execute";   E={ $_.Actions[0].Execute }},
        @{N="Arguments"; E={ $_.Actions[0].Arguments }} |
    Format-Table -AutoSize

# Flag any task still using cmd.exe (should be zero)
$badTasks = Get-ScheduledTask | Where-Object {
    $_.TaskName -like "IDXDaily_*" -and $_.Actions[0].Execute -like "*cmd.exe*"
}
if ($badTasks) {
    Write-Host "WARNING: these tasks still use cmd.exe:" -ForegroundColor Red
    $badTasks | Select-Object TaskName | Format-Table -AutoSize
} else {
    Write-Host "All IDXDaily_* tasks use wscript.exe. No cmd.exe tasks remain." -ForegroundColor Green
}

Write-Host "`nDone." -ForegroundColor Green
Write-Host ""
Write-Host "To smoke-test immediately:" -ForegroundColor Yellow
Write-Host "  Start-ScheduledTask -TaskName 'IDXDaily_Ingest'" -ForegroundColor White
Write-Host "  Start-Sleep 15" -ForegroundColor White
Write-Host "  (Get-ScheduledTaskInfo -TaskName 'IDXDaily_Ingest').LastTaskResult" -ForegroundColor White
Write-Host "  Get-Content '$projectRoot\logs\ingest_scheduler.log' -Tail 5" -ForegroundColor White
Write-Host ""
Write-Host "Success criteria: no CMD popup AND fresh log line within 30 seconds." -ForegroundColor Yellow

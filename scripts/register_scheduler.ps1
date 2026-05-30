# IDXDaily Scheduler Registration
# Run ONCE as Administrator:
#   Right-click PowerShell -> "Run as administrator"
#   cd "C:\Users\Vito\OneDrive\Documents\AI News\scripts"
#   .\register_scheduler.ps1
#
# Tasks registered:
#   IDXDaily_Ingest        - every 15 min, StartWhenAvailable (catches up on missed runs after sleep)
#   IDXDaily_Catchup       - on workstation UNLOCK + on any missed IDXDaily_Ingest trigger
#                            Runs: ingest -> enrich -> compute_index (one pass, no loop)
#   IDXDaily_SmallcapSweep - daily at 02:00, Google News for ALL tickers

$projectRoot = "C:\Users\Vito\OneDrive\Documents\AI News"
$scriptsDir  = "$projectRoot\scripts"

New-Item -ItemType Directory -Force -Path "$projectRoot\logs" | Out-Null

# --- Helper: register a task from a .bat file with a standard trigger ---
function Register-BatTask {
    param($Name, $BatFile, $Trigger, $Description)
    $action    = New-ScheduledTaskAction -Execute "cmd.exe" `
                     -Argument "/c `"$BatFile`"" -WorkingDirectory $projectRoot
    $settings  = New-ScheduledTaskSettingsSet `
                     -ExecutionTimeLimit  (New-TimeSpan -Hours 3) `
                     -StartWhenAvailable  $true `
                     -WakeToRun           $false `
                     -MultipleInstances   IgnoreNew
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME `
                     -LogonType Interactive -RunLevel Highest
    Unregister-ScheduledTask -TaskName $Name -Confirm:$false -ErrorAction SilentlyContinue
    $task = Register-ScheduledTask -TaskName $Name -Description $Description `
                -Action $action -Trigger $Trigger `
                -Settings $settings -Principal $principal -Force
    if ($task) {
        Write-Host "  OK: $Name  (State=$($task.State))" -ForegroundColor Green
    } else {
        Write-Host "  FAIL: $Name" -ForegroundColor Red
    }
}

Write-Host "`nRegistering IDXDaily scheduled tasks..." -ForegroundColor Cyan

# Remove stale tasks from previous registrations
foreach ($old in @("IDXDaily_Enrich", "IDXDaily_Catchup")) {
    Unregister-ScheduledTask -TaskName $old -Confirm:$false -ErrorAction SilentlyContinue
}

# --- 1. Main ingest - every 15 min, indefinite repetition ---
# -RepetitionDuration ([TimeSpan]::MaxValue) keeps repeating forever.
# StartWhenAvailable=true means: if the laptop slept through a 15-min slot,
# fire once when it wakes - NOT all the missed runs, just one catch-up.
$t1 = New-ScheduledTaskTrigger -Once -At (Get-Date).ToString("HH:mm") `
          -RepetitionInterval (New-TimeSpan -Minutes 15) `
          -RepetitionDuration ([TimeSpan]::MaxValue)
Register-BatTask "IDXDaily_Ingest" "$scriptsDir\run_ingest.bat" $t1 `
    "Smart ingest every 15min; market hours=GN+RSS+enrich; off-hours=RSS+enrich at most every 2h. StartWhenAvailable catches up after sleep."

# --- 2. Catch-up on workstation UNLOCK ---
# Windows Task Scheduler supports session-state-change triggers only via COM.
# We build the task definition manually using the Schedule.Service COM object.
Write-Host "  Registering IDXDaily_Catchup (unlock trigger via COM)..." -ForegroundColor Yellow

try {
    $svc = New-Object -ComObject "Schedule.Service"
    $svc.Connect()
    $folder  = $svc.GetFolder("\")
    $taskDef = $svc.NewTask(0)

    # Principal - run as current user, highest privileges, interactive logon
    $taskDef.Principal.UserId    = $env:USERNAME
    $taskDef.Principal.LogonType = 3   # TASK_LOGON_INTERACTIVE_TOKEN
    $taskDef.Principal.RunLevel  = 1   # TASK_RUNLEVEL_HIGHEST

    # Settings
    $taskDef.Settings.ExecutionTimeLimit  = "PT3H"
    $taskDef.Settings.StartWhenAvailable  = $true   # also fires after missed scheduled run
    $taskDef.Settings.WakeToRun           = $false
    $taskDef.Settings.MultipleInstances   = 3       # TASK_INSTANCES_IGNORE_NEW
    $taskDef.Settings.Enabled             = $true
    $taskDef.RegistrationInfo.Description = "One full catch-up pass (ingest+enrich+compute_index) on workstation unlock. Safe to re-run."

    # Trigger: workstation unlock (StateChange = 8)
    $trigger             = $taskDef.Triggers.Create(11)  # TASK_TRIGGER_SESSION_STATE_CHANGE
    $trigger.StateChange = 8                              # TASK_SESSION_UNLOCK
    $trigger.Enabled     = $true

    # Action
    $action                  = $taskDef.Actions.Create(0)   # TASK_ACTION_EXEC
    $action.Path             = "cmd.exe"
    $action.Arguments        = "/c `"$scriptsDir\run_catchup.bat`""
    $action.WorkingDirectory = $projectRoot

    # Register (6 = TASK_CREATE_OR_UPDATE, 3 = TASK_LOGON_INTERACTIVE_TOKEN)
    $folder.RegisterTaskDefinition("IDXDaily_Catchup", $taskDef, 6, $null, $null, 3) | Out-Null
    Write-Host "  OK: IDXDaily_Catchup  (unlock trigger)" -ForegroundColor Green
} catch {
    Write-Host "  FAIL: IDXDaily_Catchup - $_" -ForegroundColor Red
    Write-Host "  Fallback: registering IDXDaily_Catchup with AtLogon trigger instead..." -ForegroundColor Yellow
    # Fallback: AtLogon fires on both login AND unlock on most Windows configs
    $t2fallback = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    Register-BatTask "IDXDaily_Catchup" "$scriptsDir\run_catchup.bat" $t2fallback `
        "Catch-up on login/unlock: ingest+enrich+compute_index (one pass)"
}

# --- 3. Small-cap full sweep - daily at 02:00 ---
$t3 = New-ScheduledTaskTrigger -Daily -At "02:00"
Register-BatTask "IDXDaily_SmallcapSweep" "$scriptsDir\run_ingest_smallcap.bat" $t3 `
    "Full Google News sweep for ALL 926 tickers, daily at 02:00"

# --- Verify ---
Write-Host "`nVerifying registered tasks:" -ForegroundColor Cyan
Get-ScheduledTask | Where-Object { $_.TaskName -like "IDXDaily_*" } |
    Select-Object TaskName, State |
    Format-Table -AutoSize

Write-Host "Checking StartWhenAvailable setting on IDXDaily_Ingest:" -ForegroundColor Cyan
(Get-ScheduledTask -TaskName "IDXDaily_Ingest").Settings.StartWhenAvailable

Write-Host "`nDone." -ForegroundColor Green
Write-Host "Next: lock and unlock your workstation to test IDXDaily_Catchup fires." -ForegroundColor Yellow
Write-Host "Or run immediately: schtasks /run /tn IDXDaily_Catchup" -ForegroundColor Yellow

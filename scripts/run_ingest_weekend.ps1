# run_ingest_weekend.ps1
# RSS ingest for Saturdays and Sundays, 08:00-22:00 WIB window, 3 slots per day.
# Triggered every 15 min by DailyIHSG_WeekendScrape scheduled task.
#
# SLOT DEFINITIONS (WIB, UTC+7):
#   Slot 1: 08:00-12:29
#   Slot 2: 12:30-16:59
#   Slot 3: 17:00-22:00
# Each slot runs once (stamp-gated). Max 3 runs/day.

$PROJECT = "C:\Users\Vito\OneDrive\Documents\AI News"
Set-Location $PROJECT

$now     = Get-Date
$dow     = [int]$now.DayOfWeek
$dateStr = $now.ToString("yyyyMMdd")
$hour    = $now.Hour
$minute  = $now.Minute

# Only run on Saturday (6) or Sunday (0) — weekday behavior completely untouched
if ($dow -ne 0 -and $dow -ne 6) {
    Write-Output "[$now] Not a weekend, skipping."
    exit 0
}

# Outside 08:00-22:00 WIB window — do nothing
if ($hour -lt 8 -or $hour -ge 22) {
    Write-Output "[$now] Outside 08:00-22:00 window, skipping."
    exit 0
}

# Determine current slot
if ($hour -lt 12 -or ($hour -eq 12 -and $minute -lt 30)) {
    $slot = 1
} elseif ($hour -lt 17) {
    $slot = 2
} else {
    $slot = 3
}

$stampFile = "logs\weekend_slot${slot}_$dateStr.stamp"

# Skip if this slot already ran
if (Test-Path $stampFile) {
    Write-Output "[$now] Weekend slot $slot already ran today, skipping."
    exit 0
}

Write-Output "[$now] Weekend scrape starting (slot $slot of 3)..."
Add-Content "logs\ingest_scheduler.log" "[$now] Weekend scrape starting (slot $slot of 3)..."

# Capture ingest output so we can detect a blocked-lock exit (exits 0 but did nothing)
$ingestOut = python -m backend.workers.ingest 2>&1
$ingestExit = $LASTEXITCODE
$ingestOut | Tee-Object -FilePath "logs\ingest_scheduler.log" -Append

if ($ingestExit -ne 0) {
    Add-Content "logs\ingest_scheduler.log" "[$now] Weekend slot $slot FAILED (exit $ingestExit). Will retry next fire."
    Write-Output "[$now] Weekend slot $slot FAILED — not stamping."
    exit 1
}

# ingest exits 0 even when blocked by a concurrent run — detect and skip stamping
if ($ingestOut -match "Already running") {
    Add-Content "logs\ingest_scheduler.log" "[$now] Weekend slot $slot BLOCKED by concurrent ingest. Will retry next fire."
    Write-Output "[$now] Weekend slot $slot BLOCKED — not stamping."
    exit 0
}

python -m backend.workers.enrich --drain --batch 20 2>&1 |
    Tee-Object -FilePath "logs\ingest_scheduler.log" -Append

if ($LASTEXITCODE -ne 0) {
    Add-Content "logs\ingest_scheduler.log" "[$now] Weekend slot $slot enrich FAILED (exit $LASTEXITCODE). Will retry next fire."
    Write-Output "[$now] Weekend slot $slot enrich FAILED — not stamping."
    exit 1
}

# Only stamp after confirmed success
$now | Out-File $stampFile -Encoding utf8
Write-Output "[$now] Weekend slot $slot complete."
Add-Content "logs\ingest_scheduler.log" "[$now] Weekend slot $slot complete."

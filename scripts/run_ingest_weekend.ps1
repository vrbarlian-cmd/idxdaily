# run_ingest_weekend.ps1
# RSS-only ingest for Saturdays and Sundays, 10:00-18:00 WIB window, once per day.
# Triggered every 15 min by DailyIHSG_WeekendScrape scheduled task.
# No Google News — market is closed, per-ticker scrape not needed.

$PROJECT = "C:\Users\Vito\OneDrive\Documents\AI News"
Set-Location $PROJECT

$now       = Get-Date
$hour      = $now.Hour
$dateStr   = $now.ToString("yyyyMMdd")
$stampFile = "logs\weekend_scrape_$dateStr.stamp"

# Skip if already ran today
if (Test-Path $stampFile) {
    Write-Output "[$now] Weekend scrape already ran today, skipping."
    exit 0
}

# Only run on Saturday (6) or Sunday (0)
$dow = [int]$now.DayOfWeek
if ($dow -ne 0 -and $dow -ne 6) {
    Write-Output "[$now] Not a weekend, skipping."
    exit 0
}

# Only run between 10:00 and 18:00 WIB
if ($hour -lt 10 -or $hour -ge 18) {
    Write-Output "[$now] Outside 10:00-18:00 window, skipping."
    exit 0
}

Write-Output "[$now] Weekend scrape starting (RSS only)..."
Add-Content "logs\ingest_scheduler.log" "[$now] Weekend scrape starting (RSS only)..."

# RSS + HTML only — no --google-news (market closed, GN is opt-in and off by default)
python -m backend.workers.ingest 2>&1 |
    Tee-Object -FilePath "logs\ingest_scheduler.log" -Append

if ($LASTEXITCODE -ne 0) {
    Add-Content "logs\ingest_scheduler.log" "[ERROR] Weekend scrape failed (exit $LASTEXITCODE)"
    Write-Output "[ERROR] Weekend scrape failed"
    exit 1
}

# Enrich what was ingested
python -m backend.workers.enrich --drain --batch 20 2>&1 |
    Tee-Object -FilePath "logs\ingest_scheduler.log" -Append

if ($LASTEXITCODE -ne 0) {
    Add-Content "logs\ingest_scheduler.log" "[ERROR] Weekend enrich failed (exit $LASTEXITCODE)"
    Write-Output "[ERROR] Weekend enrich failed"
    exit 1
}

# Stamp — prevents double run today
$now | Out-File $stampFile -Encoding utf8
Write-Output "[$now] Weekend scrape complete."
Add-Content "logs\ingest_scheduler.log" "[$now] Weekend scrape complete."

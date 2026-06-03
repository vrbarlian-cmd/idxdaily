# run_ingest_smallcap.ps1
# Sweeps the ~795 ticker_tag_enabled=FALSE tickers via Google News.
# Runs during 06:00-08:00 WIB window only; stamps a file so it runs once per day.
# Triggered every 15 min by Windows Task Scheduler (IDXDaily_SmallcapSweep).

$PROJECT = "C:\Users\Vito\OneDrive\Documents\AI News"
Set-Location $PROJECT

$now       = Get-Date
$hour      = $now.Hour
$dateStr   = $now.ToString("yyyyMMdd")
$stampFile = "logs\smallcap_sweep_$dateStr.stamp"

if (Test-Path $stampFile) {
    Write-Output "[$now] Already ran today, skipping."
    exit 0
}

if ($hour -lt 6 -or $hour -ge 8) {
    Write-Output "[$now] Outside 06:00-08:00 window, skipping."
    exit 0
}

Write-Output "[$now] Sweeping ~795 disabled tickers via Google News..."
Add-Content "logs\ingest_smallcap.log" "[$now] SmallcapSweep starting..."

python -m backend.workers.ingest --google-news --skip-enabled 2>&1 |
    Tee-Object -FilePath "logs\ingest_smallcap.log" -Append

if ($LASTEXITCODE -ne 0) {
    Add-Content "logs\ingest_smallcap.log" "[ERROR] SmallcapSweep failed (exit $LASTEXITCODE)"
    Write-Output "[ERROR] SmallcapSweep failed"
    exit 1
}

$now | Out-File $stampFile -Encoding utf8
Write-Output "[$now] SmallcapSweep complete."
Add-Content "logs\ingest_smallcap.log" "[$now] SmallcapSweep complete."

# Feature Engineering Pipeline Status Monitor
# Run this periodically to check progress

Write-Host "`n=== FEATURE ENGINEERING PIPELINE STATUS ===" -ForegroundColor Cyan
Write-Host "Timestamp: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')`n" -ForegroundColor Yellow

# Check Spark application status
Write-Host "1. Spark Application Status:" -ForegroundColor Green
docker logs spark-master 2>&1 | Select-String -Pattern "ShuffleMapStage|ResultStage|Job \d+ finished|Job \d+ failed" | Select-Object -Last 10

# Check HDFS output directory
Write-Host "`n2. HDFS Output Directory:" -ForegroundColor Green
docker exec namenode hadoop fs -ls /traffic-data/ml-features 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Output directory exists" -ForegroundColor Green
    docker exec namenode hadoop fs -du -h /traffic-data/ml-features | Select-Object -Last 5
} else {
    Write-Host "⏳ Output directory not yet created (pipeline still processing)" -ForegroundColor Yellow
}

# Check for completion markers
Write-Host "`n3. Completion Status:" -ForegroundColor Green
$completionCheck = docker logs spark-master 2>&1 | Select-String -Pattern "FEATURE ENGINEERING|PIPELINE COMPLETED|Features generated" | Select-Object -Last 5
if ($completionCheck) {
    $completionCheck
} else {
    Write-Host "⏳ Pipeline still running..." -ForegroundColor Yellow
}

Write-Host "`n=== END STATUS CHECK ===" -ForegroundColor Cyan
Write-Host "`nTo monitor live: docker logs -f spark-master" -ForegroundColor Gray

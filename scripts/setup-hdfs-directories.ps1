# Setup HDFS Directory Structure

Write-Host "`n=== Setting up HDFS Directory Structure ===" -ForegroundColor Cyan

$directories = @(
    "/traffic-data",
    "/traffic-data/raw/metr-la",
    "/traffic-data/processed/aggregates",
    "/traffic-data/ml-features",
    "/traffic-data/models/random_forest",
    "/traffic-data/models/gradient_boosted_trees",
    "/traffic-data/models/linear_regression",
    "/traffic-data/models/preprocessing",
    "/traffic-data/predictions",
    "/traffic-data/checkpoints/feature-engineering",
    "/traffic-data/checkpoints/prediction-service",
    "/traffic-data/checkpoints/stream-processor"
)

$successCount = 0
foreach ($dir in $directories) {
    Write-Host "Creating $dir..." -NoNewline
    docker exec namenode hadoop fs -mkdir -p $dir 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host " OK" -ForegroundColor Green
        $successCount++
    } else {
        Write-Host " FAIL" -ForegroundColor Red
    }
}

Write-Host "`nSetting permissions..." -NoNewline
docker exec namenode hadoop fs -chmod -R 777 /traffic-data 2>&1 | Out-Null
Write-Host " OK" -ForegroundColor Green

Write-Host "`nVerifying structure..."
docker exec namenode hadoop fs -ls -R /traffic-data

Write-Host "`nCreated $successCount directories successfully" -ForegroundColor Green

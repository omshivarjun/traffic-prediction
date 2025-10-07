# Run Feature Engineering in Spark
# This script executes the PySpark feature engineering job

Write-Host "🚀 Starting Traffic Feature Engineering with Spark" -ForegroundColor Green
Write-Host "=" * 60

# Check if Spark container is running
Write-Host "`n📊 Checking Spark containers..." -ForegroundColor Cyan
$sparkMaster = docker ps --filter "name=spark-master" --format "{{.Names}}"
if (-not $sparkMaster) {
    Write-Host "❌ Spark master container not running!" -ForegroundColor Red
    Write-Host "   Run: docker-compose up -d spark-master" -ForegroundColor Yellow
    exit 1
}
Write-Host "✅ Spark master is running: $sparkMaster" -ForegroundColor Green

# Check if HDFS is running
Write-Host "`n📂 Checking HDFS..." -ForegroundColor Cyan
$namenode = docker ps --filter "name=namenode" --format "{{.Names}}"
if (-not $namenode) {
    Write-Host "❌ HDFS namenode not running!" -ForegroundColor Red
    exit 1
}
Write-Host "✅ HDFS namenode is running: $namenode" -ForegroundColor Green

# Copy Python script to Spark container
Write-Host "`n📦 Copying feature engineering script to Spark container..." -ForegroundColor Cyan
docker cp src/batch-processing/spark_feature_engineering.py spark-master:/opt/spark-apps/
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to copy script!" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Script copied successfully" -ForegroundColor Green

# Run the PySpark job
Write-Host "`n🎯 Executing PySpark feature engineering job..." -ForegroundColor Cyan
Write-Host "   This may take several minutes depending on data size..." -ForegroundColor Yellow
Write-Host ""

docker exec spark-master spark-submit `
    --master local[*] `
    --driver-memory 2g `
    --executor-memory 2g `
    --conf spark.sql.adaptive.enabled=true `
    /opt/spark-apps/spark_feature_engineering.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "`n❌ Feature engineering failed!" -ForegroundColor Red
    exit 1
}

Write-Host "`n✅ Feature engineering completed successfully!" -ForegroundColor Green

# Verify output in HDFS
Write-Host "`n📂 Verifying output in HDFS..." -ForegroundColor Cyan
docker exec namenode hdfs dfs -ls /traffic-data/features

Write-Host "`n" + ("=" * 60)
Write-Host "✅ FEATURE ENGINEERING COMPLETE!" -ForegroundColor Green
Write-Host ("=" * 60)
Write-Host "`nNext step: Run ML model training with:" -ForegroundColor Cyan
Write-Host "   .\scripts\run-ml-training.ps1" -ForegroundColor Yellow

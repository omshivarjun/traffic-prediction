# PowerShell script to initialize HDFS for Hadoop 3.3.6 (Task 2.3)

Write-Host "=== Initializing HDFS for Hadoop 3.3.6 (Task 2.3) ===" -ForegroundColor Green
Write-Host ""

# Check if NameNode container is running
$nameNodeStatus = docker ps --filter "name=hadoop-namenode-336" --format "{{.Status}}" | Select-String "Up"
if (-not $nameNodeStatus) {
    Write-Host "❌ NameNode is not running. Please start Hadoop first with .\start-hadoop-336.ps1" -ForegroundColor Red
    exit 1
}

Write-Host "✅ NameNode is running" -ForegroundColor Green

# Format NameNode (Task 2.3 requirement)
Write-Host ""
Write-Host "Formatting NameNode..." -ForegroundColor Cyan
docker exec hadoop-namenode-336 hdfs namenode -format -force -clusterId traffic-prediction-336

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ NameNode formatted successfully" -ForegroundColor Green
} else {
    Write-Host "❌ NameNode formatting failed" -ForegroundColor Red
    exit 1
}

# Wait for HDFS to be fully ready
Write-Host ""
Write-Host "Waiting for HDFS to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

# Verify HDFS is accessible
Write-Host ""
Write-Host "Verifying HDFS accessibility..." -ForegroundColor Cyan
docker exec hadoop-namenode-336 hdfs dfs -ls / 2>$null

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ HDFS is accessible" -ForegroundColor Green
} else {
    Write-Host "⚠️  HDFS not yet ready, retrying..." -ForegroundColor Yellow
    Start-Sleep -Seconds 10
    docker exec hadoop-namenode-336 hdfs dfs -ls / 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ HDFS is now accessible" -ForegroundColor Green
    } else {
        Write-Host "❌ HDFS verification failed" -ForegroundColor Red
    }
}

# Create required directories for traffic data (Task 2.3 requirement)
Write-Host ""
Write-Host "Creating HDFS directories for traffic data..." -ForegroundColor Cyan

$directories = @(
    "/user",
    "/user/traffic",
    "/user/traffic/raw",
    "/user/traffic/processed", 
    "/user/traffic/models",
    "/app-logs",
    "/tmp"
)

foreach ($dir in $directories) {
    Write-Host "Creating directory: $dir" -ForegroundColor White
    docker exec hadoop-namenode-336 hdfs dfs -mkdir -p $dir
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Created: $dir" -ForegroundColor Green
    } else {
        Write-Host "❌ Failed to create: $dir" -ForegroundColor Red
    }
}

# Set permissions for development
Write-Host ""
Write-Host "Setting permissions for development..." -ForegroundColor Cyan
docker exec hadoop-namenode-336 hdfs dfs -chmod -R 755 /user
docker exec hadoop-namenode-336 hdfs dfs -chmod -R 777 /tmp

# Verify directory structure
Write-Host ""
Write-Host "Verifying HDFS directory structure..." -ForegroundColor Cyan
docker exec hadoop-namenode-336 hdfs dfs -ls -R /user

Write-Host ""
Write-Host "🎉 HDFS initialization completed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "=== HDFS Status ===" -ForegroundColor Cyan
Write-Host "📊 NameNode Web UI: http://localhost:9870" -ForegroundColor White
Write-Host "🔍 Check HDFS health in the web UI" -ForegroundColor White
Write-Host ""
Write-Host "=== Created Directories ===" -ForegroundColor Yellow
foreach ($dir in $directories) {
    Write-Host "📁 $dir" -ForegroundColor White
}
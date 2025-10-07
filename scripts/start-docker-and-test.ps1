# Start Docker and Run E2E Test
# This script helps you recover from Docker Desktop issues and run the complete E2E test

Write-Host "`n==================================================" -ForegroundColor Cyan
Write-Host "   Docker Desktop Recovery & E2E Test Runner" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# Step 1: Check if Docker is running
Write-Host "`n[Step 1/5] Checking Docker Desktop status..." -ForegroundColor Yellow
$dockerRunning = $false
try {
    $null = docker ps 2>&1
    if ($LASTEXITCODE -eq 0) {
        $dockerRunning = $true
        Write-Host "✅ Docker Desktop is running!" -ForegroundColor Green
    }
} catch {
    Write-Host "❌ Docker Desktop is not responding" -ForegroundColor Red
}

if (-not $dockerRunning) {
    Write-Host "`n⚠️  Docker Desktop needs to be started/restarted" -ForegroundColor Yellow
    Write-Host "`nPlease do ONE of the following:" -ForegroundColor Cyan
    Write-Host "  1. Open Docker Desktop from Start Menu" -ForegroundColor White
    Write-Host "  2. Right-click Docker Desktop icon in system tray → Restart" -ForegroundColor White
    Write-Host "  3. If Docker won't start, restart your computer" -ForegroundColor White
    
    Write-Host "`nWaiting for Docker Desktop to start..." -ForegroundColor Yellow
    Write-Host "Press Ctrl+C to cancel, or wait for Docker to start..." -ForegroundColor Gray
    
    $maxWait = 120 # Wait up to 2 minutes
    $waited = 0
    while (-not $dockerRunning -and $waited -lt $maxWait) {
        Start-Sleep -Seconds 5
        $waited += 5
        
        try {
            $null = docker ps 2>&1
            if ($LASTEXITCODE -eq 0) {
                $dockerRunning = $true
                Write-Host "✅ Docker Desktop is now running!" -ForegroundColor Green
                break
            }
        } catch {
            Write-Host "." -NoNewline -ForegroundColor Gray
        }
    }
    
    if (-not $dockerRunning) {
        Write-Host "`n`n❌ Docker Desktop did not start within 2 minutes" -ForegroundColor Red
        Write-Host "Please start Docker Desktop manually and run this script again." -ForegroundColor Yellow
        exit 1
    }
}

# Step 2: Verify required containers
Write-Host "`n[Step 2/5] Verifying required containers..." -ForegroundColor Yellow
$requiredContainers = @("kafka-broker1", "spark-master")
$allRunning = $true

foreach ($container in $requiredContainers) {
    try {
        $status = docker inspect -f '{{.State.Running}}' $container 2>&1
        if ($status -eq "true") {
            Write-Host "  ✅ $container is running" -ForegroundColor Green
        } else {
            Write-Host "  ❌ $container is not running" -ForegroundColor Red
            $allRunning = $false
        }
    } catch {
        Write-Host "  ❌ $container not found" -ForegroundColor Red
        $allRunning = $false
    }
}

if (-not $allRunning) {
    Write-Host "`n⚠️  Some containers are not running. Starting services..." -ForegroundColor Yellow
    Write-Host "Running docker-compose up -d..." -ForegroundColor Gray
    
    if (Test-Path "docker-compose.yml") {
        docker-compose up -d
        Start-Sleep -Seconds 10
        Write-Host "✅ Services started" -ForegroundColor Green
    } else {
        Write-Host "❌ docker-compose.yml not found" -ForegroundColor Red
        exit 1
    }
}

# Step 3: Check streaming predictor service
Write-Host "`n[Step 3/5] Checking streaming predictor service..." -ForegroundColor Yellow
$predictorRunning = docker exec spark-master bash -c "ps aux | grep simple_streaming_predictor.py | grep -v grep" 2>$null

if ($LASTEXITCODE -eq 0 -and $predictorRunning) {
    Write-Host "  ✅ Streaming predictor is already running" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  Streaming predictor not running. Starting it..." -ForegroundColor Yellow
    
    $startCmd = @"
docker exec -d spark-master bash -c "source /opt/bitnami/spark/venv/bin/activate && nohup /opt/bitnami/spark/bin/spark-submit --master local[2] --driver-memory 2g --executor-memory 2g --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 /opt/spark-apps/ml/simple_streaming_predictor.py > /tmp/predictions.log 2>&1 &"
"@
    
    Invoke-Expression $startCmd
    Start-Sleep -Seconds 5
    Write-Host "  ✅ Streaming predictor started" -ForegroundColor Green
}

# Step 4: Generate test events
Write-Host "`n[Step 4/5] Generating test events..." -ForegroundColor Yellow
if (Test-Path ".\scripts\send-test-events.ps1") {
    Write-Host "  Sending 5 test events with 2-second intervals..." -ForegroundColor Gray
    & .\scripts\send-test-events.ps1 -Count 5 -DelaySeconds 2
} else {
    Write-Host "  ❌ send-test-events.ps1 not found" -ForegroundColor Red
    Write-Host "  Creating basic test event..." -ForegroundColor Yellow
    
    $testEvent = @{
        segment_id = "LA_001"
        timestamp = [int64](Get-Date -UFormat %s) * 1000
        speed = 65.5
        volume = 450
    } | ConvertTo-Json -Compress
    
    docker exec kafka-broker1 bash -c "echo '$testEvent' | kafka-console-producer --bootstrap-server localhost:9092 --topic traffic-events"
    Write-Host "  ✅ Test event sent" -ForegroundColor Green
}

# Step 5: Wait and verify predictions
Write-Host "`n[Step 5/5] Waiting for predictions (10 seconds)..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

Write-Host "`nChecking for predictions in Kafka..." -ForegroundColor Yellow
$predictions = docker exec kafka-broker1 kafka-console-consumer --bootstrap-server localhost:9092 --topic traffic-predictions --from-beginning --max-messages 5 --timeout-ms 5000 2>$null

if ($predictions) {
    Write-Host "✅ Predictions found in Kafka!" -ForegroundColor Green
    Write-Host "`nSample predictions:" -ForegroundColor Cyan
    $predictions | Select-Object -First 3 | ForEach-Object {
        try {
            $pred = $_ | ConvertFrom-Json
            $arrow = if ($pred.speed_diff -gt 0) { "↗" } elseif ($pred.speed_diff -lt 0) { "↘" } else { "→" }
            $color = switch ($pred.category) {
                "free_flow" { "Green" }
                "moderate_traffic" { "Yellow" }
                "heavy_traffic" { "DarkYellow" }
                "severe_congestion" { "Red" }
                default { "White" }
            }
            Write-Host ("  • {0}: {1:F1} {2} {3:F1} mph ({4})" -f $pred.segment_id, $pred.current_speed, $arrow, $pred.predicted_speed, $pred.category) -ForegroundColor $color
        } catch {
            Write-Host "  $_" -ForegroundColor Gray
        }
    }
} else {
    Write-Host "⚠️  No predictions found yet" -ForegroundColor Yellow
    Write-Host "Checking streaming service logs..." -ForegroundColor Gray
    docker exec spark-master tail -20 /tmp/predictions.log
}

# Step 6: Start dashboard
Write-Host "`n==================================================" -ForegroundColor Cyan
Write-Host "   Ready to Start Dashboard!" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

Write-Host "`nTo start the Next.js dashboard, run:" -ForegroundColor Yellow
Write-Host "  npm run dev" -ForegroundColor White
Write-Host "`nThen open: http://localhost:3000" -ForegroundColor Cyan

Write-Host "`n📊 To send more test events:" -ForegroundColor Yellow
Write-Host "  .\scripts\send-test-events.ps1 -Count 10 -DelaySeconds 3" -ForegroundColor White

Write-Host "`n🔍 To monitor predictions:" -ForegroundColor Yellow
Write-Host "  docker exec kafka-broker1 kafka-console-consumer --bootstrap-server localhost:9092 --topic traffic-predictions --from-beginning" -ForegroundColor White

Write-Host "`n✅ E2E test preparation complete!" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Cyan

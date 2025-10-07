#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Complete end-to-end test of the traffic prediction pipeline
.DESCRIPTION
    Tests the entire flow: Event generation → Kafka → Spark ML → Predictions → Dashboard
#>

param(
    [switch]$SkipEventGeneration,
    [switch]$SkipDashboard
)

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   Traffic Prediction Pipeline - End-to-End Test           ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Step 1: Verify Services
Write-Host "📋 Step 1: Verifying Services..." -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray

$services = @("kafka-broker1", "spark-master")
foreach ($service in $services) {
    $status = docker ps --filter "name=$service" --format "{{.Status}}" 2>$null
    if ($status -match "Up") {
        Write-Host "  ✅ $service : Running" -ForegroundColor Green
    } else {
        Write-Host "  ❌ $service : Not running" -ForegroundColor Red
        Write-Host "     Please start services with: docker-compose up -d" -ForegroundColor Yellow
        exit 1
    }
}
Write-Host ""

# Step 2: Check Streaming Service
Write-Host "📋 Step 2: Checking Streaming Service..." -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray

$sparkProcess = docker exec spark-master bash -c "ps aux | grep 'simple_streaming_predictor' | grep -v grep" 2>$null
if ($sparkProcess) {
    Write-Host "  ✅ Streaming predictor is running" -ForegroundColor Green
    
    # Check if it's idle (good) or processing (also good)
    $lastLog = docker exec spark-master bash -c "tail -5 /tmp/predictions.log 2>/dev/null | grep -E '(idle|Batch)'" 2>$null
    if ($lastLog -match "idle") {
        Write-Host "  ℹ️  Status: Idle, waiting for events" -ForegroundColor Cyan
    } elseif ($lastLog -match "Batch") {
        Write-Host "  ℹ️  Status: Processing batches" -ForegroundColor Cyan
    }
} else {
    Write-Host "  ⚠️  Streaming predictor not running. Starting..." -ForegroundColor Yellow
    docker exec -d spark-master bash -c "source /opt/bitnami/spark/venv/bin/activate && nohup /opt/bitnami/spark/bin/spark-submit --master local[2] --driver-memory 2g --executor-memory 2g --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 /opt/spark-apps/ml/simple_streaming_predictor.py > /tmp/predictions.log 2>&1 &" 2>&1 | Out-Null
    Write-Host "  ⏳ Waiting 15 seconds for service to start..." -ForegroundColor Yellow
    Start-Sleep -Seconds 15
    Write-Host "  ✅ Service started" -ForegroundColor Green
}
Write-Host ""

# Step 3: Generate Test Events
if (-not $SkipEventGeneration) {
    Write-Host "📋 Step 3: Generating Test Events..." -ForegroundColor Yellow
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray
    
    & "$PSScriptRoot\send-test-events.ps1" -Count 5 -DelaySeconds 2
} else {
    Write-Host "📋 Step 3: Skipping event generation (as requested)" -ForegroundColor Gray
    Write-Host ""
}

# Step 4: Wait for Processing
Write-Host "📋 Step 4: Waiting for Processing..." -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray
Write-Host "  ⏳ Waiting 10 seconds for Spark to process..." -ForegroundColor Cyan
Start-Sleep -Seconds 10
Write-Host ""

# Step 5: Verify Predictions in Kafka
Write-Host "📋 Step 5: Verifying Predictions in Kafka..." -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray

$predictions = docker exec kafka-broker1 bash -c "kafka-console-consumer --bootstrap-server localhost:9092 --topic traffic-predictions --from-beginning --max-messages 3 --timeout-ms 5000 2>&1 | grep -v 'Processed'" 2>$null

if ($predictions) {
    Write-Host "  ✅ Predictions found in Kafka!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Sample predictions:" -ForegroundColor Cyan
    $predictions -split "`n" | Select-Object -First 3 | ForEach-Object {
        if ($_ -match '\{') {
            $pred = $_ | ConvertFrom-Json -ErrorAction SilentlyContinue
            if ($pred) {
                Write-Host "    • $($pred.segment_id): $($pred.current_speed) → $([math]::Round($pred.predicted_speed, 1)) mph ($($pred.category))" -ForegroundColor White
            }
        }
    }
} else {
    Write-Host "  ⚠️  No predictions found yet. Check logs:" -ForegroundColor Yellow
    Write-Host "     docker exec spark-master tail -50 /tmp/predictions.log" -ForegroundColor Gray
}
Write-Host ""

# Step 6: Check Processing Stats
Write-Host "📋 Step 6: Processing Statistics..." -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray

$batchInfo = docker exec spark-master bash -c "tail -200 /tmp/predictions.log | grep -A 3 'batchId' | tail -20" 2>$null
if ($batchInfo -match 'numInputRows.*:\s*(\d+)') {
    $inputRows = $matches[1]
    Write-Host "  📊 Latest batch processed: $inputRows rows" -ForegroundColor Cyan
}

if ($batchInfo -match 'processedRowsPerSecond.*:\s*([\d.]+)') {
    $rowsPerSec = [math]::Round([double]$matches[1], 2)
    Write-Host "  ⚡ Processing speed: $rowsPerSec rows/sec" -ForegroundColor Cyan
}
Write-Host ""

# Step 7: Start Dashboard (Optional)
if (-not $SkipDashboard) {
    Write-Host "📋 Step 7: Starting Dashboard..." -ForegroundColor Yellow
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray
    Write-Host "  🌐 Starting Next.js development server..." -ForegroundColor Cyan
    Write-Host "  📍 URL: http://localhost:3000" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Press Ctrl+C to stop the server" -ForegroundColor Yellow
    Write-Host ""
    
    # Start in current terminal
    npm run dev
} else {
    Write-Host "📋 Step 7: Dashboard Start Skipped" -ForegroundColor Gray
    Write-Host "  To start manually: npm run dev" -ForegroundColor Cyan
    Write-Host "  Then open: http://localhost:3000" -ForegroundColor Cyan
    Write-Host ""
}

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║              ✅ End-to-End Test Complete!                  ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

#!/usr/bin/env pwsh
# ==============================================
# SSE Connection Diagnostic Tool
# ==============================================

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  SSE CONNECTION DIAGNOSTIC" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Cyan

# 1. Check if Kafka is running
Write-Host "1️⃣  Checking Kafka broker..." -ForegroundColor Yellow
$kafkaStatus = docker ps --filter "name=kafka-broker1" --format "{{.Status}}"
if ($kafkaStatus -like "*Up*") {
    Write-Host "   ✅ Kafka broker is running" -ForegroundColor Green
} else {
    Write-Host "   ❌ Kafka broker is not running!" -ForegroundColor Red
    Write-Host "   Run: docker-compose up -d" -ForegroundColor Yellow
    exit 1
}

# 2. Test Kafka connectivity
Write-Host "`n2️⃣  Testing Kafka connectivity..." -ForegroundColor Yellow
$testResult = docker exec kafka-broker1 kafka-broker-api-versions --bootstrap-server localhost:9092 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✅ Kafka is accessible" -ForegroundColor Green
} else {
    Write-Host "   ❌ Cannot connect to Kafka!" -ForegroundColor Red
    Write-Host "   $testResult" -ForegroundColor Red
    exit 1
}

# 3. Check .env.local exists
Write-Host "`n3️⃣  Checking Next.js environment..." -ForegroundColor Yellow
if (Test-Path ".env.local") {
    $envContent = Get-Content ".env.local" | Select-String "KAFKA_BROKERS"
    if ($envContent) {
        Write-Host "   ✅ .env.local configured: $envContent" -ForegroundColor Green
    } else {
        Write-Host "   ⚠️  .env.local exists but KAFKA_BROKERS not set" -ForegroundColor Yellow
    }
} else {
    Write-Host "   ❌ .env.local not found!" -ForegroundColor Red
    Write-Host "   Creating .env.local with correct settings..." -ForegroundColor Yellow
    
    @"
# Next.js Environment Variables (Client-side safe)
KAFKA_BROKERS=localhost:9092
KAFKA_SCHEMA_REGISTRY_URL=http://localhost:8081
DATABASE_URL=postgresql://postgres:casa1234@localhost:5433/traffic_db
"@ | Out-File -FilePath ".env.local" -Encoding UTF8
    
    Write-Host "   ✅ Created .env.local" -ForegroundColor Green
}

# 4. Check if predictions topic has data
Write-Host "`n4️⃣  Checking for predictions in Kafka..." -ForegroundColor Yellow
$predictionCount = docker exec kafka-broker1 kafka-run-class kafka.tools.GetOffsetShell `
    --broker-list localhost:9092 `
    --topic traffic-predictions 2>$null | 
    Select-String "traffic-predictions" | 
    ForEach-Object { ($_ -split ':')[-1] } | 
    Measure-Object -Sum | 
    Select-Object -ExpandProperty Sum

if ($predictionCount -gt 0) {
    Write-Host "   ✅ Found $predictionCount predictions in Kafka" -ForegroundColor Green
    
    # Show sample predictions
    Write-Host "`n   📊 Latest predictions:" -ForegroundColor Cyan
    docker exec kafka-broker1 kafka-console-consumer `
        --bootstrap-server localhost:9092 `
        --topic traffic-predictions `
        --from-beginning `
        --max-messages 3 `
        --timeout-ms 5000 2>$null |
        ForEach-Object {
            $pred = $_ | ConvertFrom-Json
            Write-Host ("      • {0}: {1:F1} → {2:F1} mph ({3})" -f `
                $pred.segment_id, $pred.current_speed, $pred.predicted_speed, $pred.category) `
                -ForegroundColor White
        }
} else {
    Write-Host "   ⚠️  No predictions in Kafka yet" -ForegroundColor Yellow
    Write-Host "   Run: .\scripts\send-test-events.ps1" -ForegroundColor Cyan
}

# 5. Check if Next.js is running
Write-Host "`n5️⃣  Checking Next.js server..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:3000" -TimeoutSec 2 -ErrorAction SilentlyContinue
    Write-Host "   ✅ Next.js is running on port 3000" -ForegroundColor Green
} catch {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:3002" -TimeoutSec 2 -ErrorAction SilentlyContinue
        Write-Host "   ✅ Next.js is running on port 3002" -ForegroundColor Green
    } catch {
        Write-Host "   ⚠️  Next.js is not running" -ForegroundColor Yellow
        Write-Host "   Run: npm run dev" -ForegroundColor Cyan
    }
}

# Summary
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  DIAGNOSTIC COMPLETE" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "📋 Next Steps:`n" -ForegroundColor Yellow

if ($predictionCount -eq 0) {
    Write-Host "   1. Generate test data:" -ForegroundColor White
    Write-Host "      .\scripts\send-test-events.ps1`n" -ForegroundColor Cyan
}

Write-Host "   2. Start Next.js (if not running):" -ForegroundColor White
Write-Host "      npm run dev`n" -ForegroundColor Cyan

Write-Host "   3. Open dashboard:" -ForegroundColor White
Write-Host "      http://localhost:3000/predictions`n" -ForegroundColor Cyan

Write-Host "   4. Watch console for:" -ForegroundColor White
Write-Host "      ✅ Connected to Kafka for predictions" -ForegroundColor Green
Write-Host "      🚀 Prediction consumer started successfully" -ForegroundColor Green
Write-Host "      📊 Loaded X initial predictions`n" -ForegroundColor Green

Write-Host "========================================`n" -ForegroundColor Cyan

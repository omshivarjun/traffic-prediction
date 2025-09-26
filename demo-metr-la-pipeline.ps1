#!/usr/bin/env powershell
<#
.SYNOPSIS
    Simple METR-LA Pipeline Demo
    
.DESCRIPTION
    Demonstrates the working end-to-end pipeline:
    CSV to Kafka to Next.js Dashboard with Heatmaps
    
.EXAMPLE
    .\demo-metr-la-pipeline.ps1
#>

# Colors for output
$Green = "`e[32m"
$Yellow = "`e[33m"
$Blue = "`e[34m"
$Reset = "`e[0m"

function Write-Step {
    param([string]$Message, [string]$Color = $Green)
    Write-Host "${Color}[$(Get-Date -Format 'HH:mm:ss')] $Message${Reset}"
}

Write-Host "${Blue}======================================================================${Reset}"
Write-Host "${Blue}                    METR-LA Pipeline Demo                             ${Reset}"
Write-Host "${Blue}             CSV to Kafka to Dashboard + Heatmaps                    ${Reset}"
Write-Host "${Blue}======================================================================${Reset}"
Write-Host ""

# Step 1: Check services
Write-Step "Step 1: Checking Docker Services..."
$services = @("kafka-broker1", "namenode", "spark-master")
foreach ($service in $services) {
    $status = docker ps --filter "name=$service" --format "table {{.Names}}\t{{.Status}}" | Select-String $service
    if ($status) {
        Write-Host "   OK ${service}: Running" -ForegroundColor Green
    } else {
        Write-Host "   ERROR ${service}: Not running" -ForegroundColor Red
        exit 1
    }
}

# Step 2: Test Kafka connection
Write-Step "Step 2: Testing Kafka Connection..."
python scripts\metr_la_docker_producer.py --test-connection
if ($LASTEXITCODE -eq 0) {
    Write-Host "   OK Kafka connection successful" -ForegroundColor Green
} else {
    Write-Host "   ERROR Kafka connection failed" -ForegroundColor Red
    exit 1
}

# Step 3: Send sample data to Kafka
Write-Step "Step 3: Sending Sample Traffic Data to Kafka..."
python scripts\metr_la_docker_producer.py --csv-file "data\processed\metr_la_sample.csv" --max-records 100 --batch-size 20
if ($LASTEXITCODE -eq 0) {
    Write-Host "   OK Sample data sent successfully" -ForegroundColor Green
} else {
    Write-Host "   ERROR Failed to send data" -ForegroundColor Red
    exit 1
}

# Step 4: Verify data in Kafka
Write-Step "Step 4: Verifying Data in Kafka..."
Write-Host "   Latest messages in traffic-events topic:" -ForegroundColor Yellow
docker exec kafka-broker1 kafka-console-consumer --bootstrap-server localhost:9092 --topic traffic-events --timeout-ms 3000 --max-messages 3

# Step 5: Start Next.js Dashboard
Write-Step "Step 5: Starting Next.js Dashboard..."
Write-Host "   Dashboard will be available at: ${Yellow}http://localhost:3000${Reset}"
Write-Host "   Traffic Heatmap at: ${Yellow}http://localhost:3000/dashboard${Reset}"
Write-Host ""
Write-Host "   ${Blue}Features available:${Reset}"
Write-Host "   - Real-time traffic data visualization"
Write-Host "   - Interactive heatmap with speed color coding"
Write-Host "   - Traffic sensors positioned on Los Angeles map"
Write-Host "   - Popup details for each sensor reading"
Write-Host ""
Write-Host "   ${Yellow}Press Ctrl+C to stop the dashboard${Reset}"
Write-Host ""

npm run dev --turbopack

Write-Host ""
Write-Step "Pipeline Demo Completed!" $Green
Write-Host ""
Write-Host "${Green}Summary of what was demonstrated:${Reset}"
Write-Host "- Docker services health check"
Write-Host "- Kafka connectivity validation"
Write-Host "- METR-LA CSV data processing and streaming"
Write-Host "- Kafka topic data verification"
Write-Host "- Next.js dashboard with React Leaflet heatmaps"
Write-Host ""
Write-Host "${Blue}Next steps to extend the pipeline:${Reset}"
Write-Host "- Add Spark Structured Streaming for real-time processing"
Write-Host "- Implement ML training on historical data"
Write-Host "- Add prediction generation and publishing"
Write-Host "- Enhance dashboard with more visualization types"
Write-Host ""
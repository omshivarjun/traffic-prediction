# Traffic Prediction System - Dashboard Startup Script
# Starts all required services and opens the unified dashboard

Write-Host "Traffic Prediction System - Dashboard Startup" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
Write-Host "[1/7] Checking Docker status..." -ForegroundColor Yellow
$dockerRunning = docker ps 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker is not running! Please start Docker Desktop first." -ForegroundColor Red
    exit 1
}
Write-Host "SUCCESS: Docker is running" -ForegroundColor Green
Write-Host ""

# Start Docker services
Write-Host "[2/7] Starting Docker services (Kafka, HDFS, YARN)..." -ForegroundColor Yellow
docker compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to start Docker services" -ForegroundColor Red
    exit 1
}
Write-Host "SUCCESS: Docker services started" -ForegroundColor Green
Write-Host ""

# Wait for services to initialize
Write-Host "[3/7] Waiting 15 seconds for services to initialize..." -ForegroundColor Yellow
Start-Sleep -Seconds 15
Write-Host "SUCCESS: Services should be ready" -ForegroundColor Green
Write-Host ""

# Kill any existing Next.js processes
Write-Host "[4/7] Cleaning up old Next.js processes..." -ForegroundColor Yellow
Get-Process -Name node -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*traffic-prediction*" } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Write-Host "SUCCESS: Cleanup complete" -ForegroundColor Green
Write-Host ""

# Start Next.js dashboard in background
Write-Host "[5/7] Starting Next.js Dashboard..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "npm run dev" -WindowStyle Minimized
Write-Host "SUCCESS: Dashboard starting (check minimized window for logs)" -ForegroundColor Green
Write-Host ""

# Wait for Next.js to start
Write-Host "[6/7] Waiting 10 seconds for Next.js to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Open browser
Write-Host "[7/7] Opening dashboard in browser..." -ForegroundColor Yellow
Start-Process "http://localhost:3000"
Write-Host "SUCCESS: Dashboard opened" -ForegroundColor Green
Write-Host ""

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "SYSTEM STARTED SUCCESSFULLY!" -ForegroundColor Green
Write-Host ""
Write-Host "Available Services:" -ForegroundColor Cyan
Write-Host "  - Main Dashboard:    http://localhost:3000" -ForegroundColor White
Write-Host "  - Kafka UI:          http://localhost:8085" -ForegroundColor White
Write-Host "  - HDFS NameNode:     http://localhost:9871" -ForegroundColor White
Write-Host "  - YARN ResourceMgr:  http://localhost:8089" -ForegroundColor White
Write-Host "  - Spark Master:      http://localhost:8086" -ForegroundColor White
Write-Host ""
Write-Host "Test the system:" -ForegroundColor Cyan
Write-Host "  .\scripts\send-test-events.ps1 -Count 10" -ForegroundColor Yellow
Write-Host ""
Write-Host "To stop all services:" -ForegroundColor Cyan
Write-Host "  docker compose down" -ForegroundColor Yellow
Write-Host "  Get-Process -Name node | Stop-Process -Force" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press any key to exit this window..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

# FastAPI Backend Startup Script for Traffic Prediction System
# Task 14 Implementation - Start FastAPI REST API Backend

param(
    [string]$Environment = "development",
    [int]$Port = 8000,
    [string]$HostIP = "127.0.0.1",
    [switch]$InstallDeps,
    [switch]$HealthCheck,
    [switch]$Background
)

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "FastAPI Traffic Prediction Backend" -ForegroundColor Cyan
Write-Host "Task 14 Implementation" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# Set paths
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ProjectRoot
$ApiRoot = Join-Path $ProjectRoot "src\api"

Write-Host "Project Root: $ProjectRoot" -ForegroundColor Gray
Write-Host "API Root: $ApiRoot" -ForegroundColor Gray

# Change to project root
Set-Location $ProjectRoot

# Check if Python is available
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python not found. Please install Python 3.9+ and add to PATH." -ForegroundColor Red
    exit 1
}

# Check if virtual environment exists
$VenvPath = Join-Path $ProjectRoot "traffic_env"
if (Test-Path $VenvPath) {
    Write-Host "✅ Virtual environment found: $VenvPath" -ForegroundColor Green
    
    # Activate virtual environment
    $ActivateScript = Join-Path $VenvPath "Scripts\Activate.ps1"
    if (Test-Path $ActivateScript) {
        Write-Host "Activating virtual environment..." -ForegroundColor Yellow
        & $ActivateScript
    }
} else {
    Write-Host "⚠️ Virtual environment not found. Using system Python." -ForegroundColor Yellow
}

# Install dependencies if requested
if ($InstallDeps) {
    Write-Host "Installing FastAPI dependencies..." -ForegroundColor Yellow
    
    $RequirementsFile = Join-Path $ProjectRoot "requirements-fastapi.txt"
    if (Test-Path $RequirementsFile) {
        pip install -r $RequirementsFile
        if ($LASTEXITCODE -ne 0) {
            Write-Host "❌ Failed to install dependencies" -ForegroundColor Red
            exit 1
        }
        Write-Host "✅ Dependencies installed successfully" -ForegroundColor Green
    } else {
        Write-Host "❌ requirements-fastapi.txt not found" -ForegroundColor Red
        exit 1
    }
}

# Set environment variables for FastAPI
$env:PYTHONPATH = $ApiRoot
$env:FASTAPI_ENV = $Environment
$env:API_HOST = $HostIP
$env:API_PORT = $Port.ToString()

# Database configuration (using defaults, can be overridden)
if (-not $env:DB_HOST) { $env:DB_HOST = "localhost" }
if (-not $env:DB_PORT) { $env:DB_PORT = "5433" }
if (-not $env:DB_NAME) { $env:DB_NAME = "traffic_db" }
if (-not $env:DB_USER) { $env:DB_USER = "postgres" }
if (-not $env:DB_PASSWORD) { $env:DB_PASSWORD = "password" }

# Kafka configuration (using defaults, can be overridden)
if (-not $env:KAFKA_BOOTSTRAP_SERVERS) { $env:KAFKA_BOOTSTRAP_SERVERS = "localhost:9092" }
if (-not $env:KAFKA_TOPIC_TRAFFIC_EVENTS) { $env:KAFKA_TOPIC_TRAFFIC_EVENTS = "traffic-events" }
if (-not $env:KAFKA_TOPIC_PREDICTIONS) { $env:KAFKA_TOPIC_PREDICTIONS = "traffic-predictions" }

Write-Host "Environment Configuration:" -ForegroundColor Cyan
Write-Host "  Environment: $Environment" -ForegroundColor White
Write-Host "  Host: $HostIP" -ForegroundColor White
Write-Host "  Port: $Port" -ForegroundColor White
Write-Host "  Database: $($env:DB_HOST):$($env:DB_PORT)/$($env:DB_NAME)" -ForegroundColor White
Write-Host "  Kafka: $env:KAFKA_BOOTSTRAP_SERVERS" -ForegroundColor White

# Run health checks if requested
if ($HealthCheck) {
    Write-Host "Running health checks..." -ForegroundColor Yellow
    
    # Check if required packages are available
    try {
        python -c "import fastapi, uvicorn, sqlalchemy, psycopg2" 2>$null
        Write-Host "✅ Core dependencies available" -ForegroundColor Green
    } catch {
        Write-Host "❌ Missing core dependencies. Run with -InstallDeps" -ForegroundColor Red
        exit 1
    }
    
    # Check database connection (basic test)
    try {
        python -c "import psycopg2; psycopg2.connect(host='$env:DB_HOST', port='$env:DB_PORT', database='$env:DB_NAME', user='$env:DB_USER', password='$env:DB_PASSWORD').close()" 2>$null
        Write-Host "✅ Database connection successful" -ForegroundColor Green
    } catch {
        Write-Host "⚠️ Database connection failed. Server will handle gracefully." -ForegroundColor Yellow
    }
    
    Write-Host "Health checks completed." -ForegroundColor Green
}

# Check if port is already in use
$PortInUse = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
if ($PortInUse) {
    Write-Host "⚠️ Port $Port is already in use. The server may fail to start." -ForegroundColor Yellow
    Write-Host "Current process using port ${Port}:" -ForegroundColor Yellow
    Get-Process -Id $PortInUse.OwningProcess -ErrorAction SilentlyContinue | Select-Object Name, Id | Format-Table
}

# Build uvicorn command based on environment
$UvicornArgs = @(
    "-m", "uvicorn",
    "src.api.main:app",
    "--host", $HostIP,
    "--port", $Port.ToString()
)

if ($Environment -eq "development") {
    $UvicornArgs += "--reload"
    $UvicornArgs += "--log-level", "debug"
    Write-Host "🔥 Development mode: Hot reload enabled" -ForegroundColor Yellow
} elseif ($Environment -eq "production") {
    $UvicornArgs += "--workers", "4"
    $UvicornArgs += "--log-level", "info"
    $UvicornArgs += "--access-log"
    Write-Host "🚀 Production mode: Multi-worker setup" -ForegroundColor Green
} else {
    $UvicornArgs += "--log-level", "info"
}

Write-Host ""
Write-Host "Starting FastAPI server..." -ForegroundColor Green
Write-Host "Command: python $($UvicornArgs -join ' ')" -ForegroundColor Gray
Write-Host ""
Write-Host "📡 API will be available at:" -ForegroundColor Cyan
Write-Host "   • API Documentation: http://${HostAddress}:${Port}/docs" -ForegroundColor White
Write-Host "   • Redoc Documentation: http://${HostAddress}:${Port}/redoc" -ForegroundColor White
Write-Host "   • Health Check: http://${HostAddress}:${Port}/health" -ForegroundColor White
Write-Host "   • WebSocket: ws://${HostAddress}:${Port}/ws/real-time" -ForegroundColor White
Write-Host ""

if ($Background) {
    Write-Host "Starting server in background..." -ForegroundColor Yellow
    $Process = Start-Process python -ArgumentList $UvicornArgs -PassThru -WindowStyle Hidden
    Write-Host "✅ Server started in background (PID: $($Process.Id))" -ForegroundColor Green
    Write-Host "Use 'taskkill /PID $($Process.Id) /F' to stop the server" -ForegroundColor Gray
} else {
    Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Gray
    Write-Host "=========================================" -ForegroundColor Cyan
    
    # Start the server
    python @UvicornArgs
}

Write-Host ""
Write-Host "FastAPI backend stopped." -ForegroundColor Yellow
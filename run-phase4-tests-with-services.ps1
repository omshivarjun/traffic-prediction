#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Phase 4 Test Execution with Service Management
    
.DESCRIPTION
    Comprehensive script to:
    1. Check Docker status
    2. Start required services
    3. Wait for services to be ready
    4. Execute Phase 4 security tests
    5. Display results
    
.EXAMPLE
    .\run-phase4-tests-with-services.ps1
    
.NOTES
    Author: Traffic Prediction Security Team
    Date: 2025-01-06
#>

param(
    [switch]$SkipServiceStart,
    [switch]$StopServicesAfter,
    [int]$WaitSeconds = 30
)

# Color functions
function Write-Success { param($msg) Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Warning { param($msg) Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Error-Custom { param($msg) Write-Host "[ERROR] $msg" -ForegroundColor Red }
function Write-Info { param($msg) Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Step { param($msg) Write-Host "`n=== $msg ===" -ForegroundColor Magenta }

# Header
Write-Host @"

╔══════════════════════════════════════════════════════════════╗
║  PHASE 4 COMPREHENSIVE SECURITY TEST SUITE                   ║
║  WITH SERVICE MANAGEMENT                                     ║
╚══════════════════════════════════════════════════════════════╝

"@ -ForegroundColor Cyan

# Step 1: Prerequisites Check
Write-Step "Step 1: Checking Prerequisites"

# Check Docker
if (Get-Command docker -ErrorAction SilentlyContinue) {
    Write-Success "Docker installed: $(docker --version)"
} else {
    Write-Error-Custom "Docker not found. Please install Docker Desktop."
    exit 1
}

# Check if Docker is running
try {
    docker ps | Out-Null
    Write-Success "Docker daemon is running"
} catch {
    Write-Error-Custom "Docker daemon not running. Please start Docker Desktop."
    exit 1
}

# Check Python
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonVersion = python --version
    Write-Success "Python installed: $pythonVersion"
} else {
    Write-Error-Custom "Python not found. Please install Python 3.8+."
    exit 1
}

# Step 2: Start Services
if (-not $SkipServiceStart) {
    Write-Step "Step 2: Starting Docker Compose Services"
    
    Write-Info "Stopping any existing services..."
    docker-compose down 2>&1 | Out-Null
    
    Write-Info "Starting services with security configuration..."
    docker-compose up -d
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error-Custom "Failed to start Docker services"
        exit 1
    }
    
    Write-Success "Services started successfully"
    
    # Step 3: Wait for Services
    Write-Step "Step 3: Waiting for Services to be Ready"
    
    Write-Info "Waiting $WaitSeconds seconds for services to initialize..."
    for ($i = $WaitSeconds; $i -gt 0; $i--) {
        Write-Host -NoNewline "`rTime remaining: $i seconds " -ForegroundColor Yellow
        Start-Sleep -Seconds 1
    }
    Write-Host "" # New line
    
    # Check backend service
    Write-Info "Checking backend service (http://localhost:8001)..."
    $maxRetries = 5
    $retryCount = 0
    $backendReady = $false
    
    while ($retryCount -lt $maxRetries -and -not $backendReady) {
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:8001/data/traffic-events" -TimeoutSec 5 -ErrorAction Stop
            Write-Success "Backend service is accessible (Status: $($response.StatusCode))"
            $backendReady = $true
        } catch {
            $retryCount++
            if ($retryCount -lt $maxRetries) {
                Write-Warning "Backend not ready yet, retrying in 5 seconds... ($retryCount/$maxRetries)"
                Start-Sleep -Seconds 5
            }
        }
    }
    
    if (-not $backendReady) {
        Write-Warning "Backend service not accessible. API tests may fail."
        Write-Info "Checking backend logs..."
        docker-compose logs --tail=20 backend
    }
    
    # Check Docker containers
    Write-Info "Checking Docker containers..."
    $containers = docker ps --format "{{.Names}}" | Where-Object { $_ -like "*traffic*" }
    Write-Success "Running containers: $($containers.Count)"
    $containers | ForEach-Object { Write-Info "  - $_" }
    
} else {
    Write-Warning "Skipping service start (--SkipServiceStart flag set)"
}

# Step 4: Install Test Dependencies
Write-Step "Step 4: Installing Test Dependencies"

Write-Info "Upgrading pip..."
python -m pip install --upgrade pip --quiet

Write-Info "Installing test requirements..."
if (Test-Path "tests\security\requirements-testing.txt") {
    python -m pip install -r tests\security\requirements-testing.txt --quiet
    Write-Success "Test dependencies installed"
} else {
    Write-Warning "requirements-testing.txt not found, installing manually..."
    python -m pip install pytest pytest-asyncio httpx docker psutil --quiet
}

# Step 5: Run Tests
Write-Step "Step 5: Running Phase 4 Security Tests"

# Set Python path
$env:PYTHONPATH = $PWD.Path

# Create report directory
$reportDir = "docs\security\test-reports"
if (-not (Test-Path $reportDir)) {
    New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
}

# Generate timestamp
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$reportFile = "$reportDir\phase4_test_report_$timestamp.txt"
$summaryFile = "$reportDir\phase4_test_summary.json"

Write-Info "Executing pytest with comprehensive reporting..."
Write-Info "Report will be saved to: $reportFile"

# Run tests
python -m pytest tests\security\test_phase4_comprehensive.py `
    -v `
    --tb=short `
    --color=yes `
    --asyncio-mode=auto `
    --capture=no `
    --json-report `
    --json-report-file="$summaryFile" `
    | Tee-Object -FilePath $reportFile

$testExitCode = $LASTEXITCODE

# Step 6: Display Results
Write-Step "Step 6: Test Results Summary"

if (Test-Path $summaryFile) {
    $summary = Get-Content $summaryFile | ConvertFrom-Json
    
    Write-Host "`n╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║  TEST EXECUTION SUMMARY                                      ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════════════════════╝`n" -ForegroundColor Cyan
    
    Write-Host "Duration: $($summary.duration) seconds" -ForegroundColor White
    Write-Host "Total Tests: $($summary.summary.total)" -ForegroundColor White
    
    if ($summary.summary.passed -gt 0) {
        Write-Host "Passed: $($summary.summary.passed)" -ForegroundColor Green
    }
    if ($summary.summary.failed -gt 0) {
        Write-Host "Failed: $($summary.summary.failed)" -ForegroundColor Red
    }
    if ($summary.summary.error -gt 0) {
        Write-Host "Errors: $($summary.summary.error)" -ForegroundColor Red
    }
    if ($summary.summary.skipped -gt 0) {
        Write-Host "Skipped: $($summary.summary.skipped)" -ForegroundColor Yellow
    }
}

Write-Host "`nDetailed Report: $reportFile" -ForegroundColor Cyan
Write-Host "JSON Summary: $summaryFile" -ForegroundColor Cyan

# Step 7: Cleanup
if ($StopServicesAfter) {
    Write-Step "Step 7: Stopping Services"
    docker-compose down
    Write-Success "Services stopped"
}

# Final Status
Write-Host "`n╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
if ($testExitCode -eq 0) {
    Write-Host "║  " -NoNewline -ForegroundColor Cyan
    Write-Host "ALL TESTS PASSED!" -NoNewline -ForegroundColor Green
    Write-Host "                                        ║" -ForegroundColor Cyan
} else {
    Write-Host "║  " -NoNewline -ForegroundColor Cyan
    Write-Host "SOME TESTS FAILED" -NoNewline -ForegroundColor Red
    Write-Host "                                        ║" -ForegroundColor Cyan
}
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan

Write-Host "`nNext Steps:" -ForegroundColor Yellow
if ($testExitCode -eq 0) {
    Write-Host "  1. Review the detailed test report above" -ForegroundColor White
    Write-Host "  2. Proceed with production deployment validation" -ForegroundColor White
    Write-Host "  3. See: docs\security\PRODUCTION_DEPLOYMENT_GUIDE.md" -ForegroundColor White
} else {
    Write-Host "  1. Review test report: $reportFile" -ForegroundColor White
    Write-Host "  2. Check service logs: docker-compose logs" -ForegroundColor White
    Write-Host "  3. Fix failing tests and re-run" -ForegroundColor White
    Write-Host "  4. See: docs\security\PHASE4_TEST_RESULTS.md" -ForegroundColor White
}

Write-Host ""

exit $testExitCode

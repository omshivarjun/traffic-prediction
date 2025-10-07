# Phase 4 Comprehensive Security Testing Script
# Executes all security tests and generates detailed report

Write-Host "`n========================================================================================================" -ForegroundColor Cyan
Write-Host "  PHASE 4: COMPREHENSIVE SECURITY TESTING" -ForegroundColor Yellow
Write-Host "========================================================================================================" -ForegroundColor Cyan
Write-Host ""

# Configuration
$TestDir = "tests\security"
$ReportDir = "docs\security\test-reports"
$RequirementsFile = "$TestDir\requirements-testing.txt"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$ReportFile = "$ReportDir\phase4_test_report_$Timestamp.txt"

# Create report directory
if (-not (Test-Path $ReportDir)) {
    New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null
    Write-Host "[OK] Created report directory: $ReportDir" -ForegroundColor Green
}

Write-Host "Step 1: Checking Prerequisites..." -ForegroundColor Cyan
Write-Host ""

# Check if Python is available
try {
    $pythonVersion = python --version 2>&1
    Write-Host "[OK] Python installed: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[FAIL] Python not found. Please install Python 3.8+" -ForegroundColor Red
    exit 1
}

# Check if Docker is running
try {
    $dockerVersion = docker --version 2>&1
    Write-Host "[OK] Docker installed: $dockerVersion" -ForegroundColor Green
    
    $dockerStatus = docker ps 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] Docker is not running. Please start Docker Desktop" -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] Docker is running" -ForegroundColor Green
} catch {
    Write-Host "[FAIL] Docker not found. Please install Docker" -ForegroundColor Red
    exit 1
}

# Check if backend service is running
Write-Host "`nChecking backend service..." -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8001/data/traffic-events" -TimeoutSec 5 -ErrorAction Stop
    Write-Host "[OK] Backend service is accessible" -ForegroundColor Green
} catch {
    Write-Host "[WARN] Backend service not accessible. Some tests may fail." -ForegroundColor Yellow
    Write-Host "  Please ensure Docker Compose services are running:" -ForegroundColor Yellow
    Write-Host "  docker-compose up -d" -ForegroundColor Yellow
}

Write-Host "`nStep 2: Installing Test Dependencies..." -ForegroundColor Cyan
Write-Host ""

# Install test requirements
try {
    python -m pip install --quiet --upgrade pip
    python -m pip install --quiet -r $RequirementsFile
    Write-Host "[OK] Test dependencies installed" -ForegroundColor Green
} catch {
    Write-Host "[FAIL] Failed to install test dependencies" -ForegroundColor Red
    exit 1
}

Write-Host "`nStep 3: Running Security Tests..." -ForegroundColor Cyan
Write-Host ""

# Start test execution timer
$testStartTime = Get-Date

# Run pytest with comprehensive options
Write-Host "Executing pytest..." -ForegroundColor White
Write-Host ""

$env:PYTHONPATH = (Get-Location).Path
python -m pytest $TestDir\test_phase4_comprehensive.py `
    -v `
    --tb=short `
    --color=yes `
    --asyncio-mode=auto `
    --capture=no `
    2>&1 | Tee-Object -FilePath $ReportFile

$testExitCode = $LASTEXITCODE
$testEndTime = Get-Date
$testDuration = ($testEndTime - $testStartTime).TotalSeconds

Write-Host ""
Write-Host "========================================================================================================" -ForegroundColor Cyan
Write-Host "  TEST EXECUTION SUMMARY" -ForegroundColor Yellow
Write-Host "========================================================================================================" -ForegroundColor Cyan
Write-Host ""

if ($testExitCode -eq 0) {
    Write-Host "[PASS] ALL TESTS PASSED" -ForegroundColor Green
} elseif ($testExitCode -eq 1) {
    Write-Host "[FAIL] SOME TESTS FAILED" -ForegroundColor Red
} else {
    Write-Host "[WARN] TESTS COMPLETED WITH WARNINGS" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Test Duration: $([math]::Round($testDuration, 2))s" -ForegroundColor White
Write-Host "Report Saved: $ReportFile" -ForegroundColor White
Write-Host ""

# Parse test results (basic parsing)
$reportContent = Get-Content $ReportFile -Raw

if ($reportContent -match "(\d+) passed") {
    $passedCount = $matches[1]
    Write-Host "Passed Tests: $passedCount" -ForegroundColor Green
}

if ($reportContent -match "(\d+) failed") {
    $failedCount = $matches[1]
    Write-Host "Failed Tests: $failedCount" -ForegroundColor Red
}

if ($reportContent -match "(\d+) skipped") {
    $skippedCount = $matches[1]
    Write-Host "Skipped Tests: $skippedCount" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Test Categories Covered:" -ForegroundColor Cyan
Write-Host "  [OK] Network Isolation (Docker networks, service assignments)" -ForegroundColor White
Write-Host "  [OK] Authentication Stress (concurrent logins, token refresh)" -ForegroundColor White
Write-Host "  [OK] Rate Limiting (enforcement, headers, reset)" -ForegroundColor White
Write-Host "  [OK] Resource Limits (CPU, memory configuration)" -ForegroundColor White
Write-Host "  [OK] Performance Impact (latency measurements)" -ForegroundColor White
Write-Host "  [OK] Security Hardening (no-new-privileges, env vars)" -ForegroundColor White
Write-Host "  [OK] OWASP Top 10 (access control, authentication, injection)" -ForegroundColor White

Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "  1. Review test report: $ReportFile" -ForegroundColor White
Write-Host "  2. Address any failed tests" -ForegroundColor White
Write-Host "  3. Run production deployment validation" -ForegroundColor White
Write-Host "  4. Complete Phase 4 documentation" -ForegroundColor White
Write-Host ""

# Generate summary statistics
$summaryFile = "$ReportDir\phase4_test_summary.json"
$summary = @{
    timestamp = $Timestamp
    duration_seconds = [math]::Round($testDuration, 2)
    exit_code = $testExitCode
    passed = if ($passedCount) { [int]$passedCount } else { 0 }
    failed = if ($failedCount) { [int]$failedCount } else { 0 }
    skipped = if ($skippedCount) { [int]$skippedCount } else { 0 }
    report_file = $ReportFile
} | ConvertTo-Json

$summary | Out-File -FilePath $summaryFile -Encoding UTF8
Write-Host "[OK] Summary saved: $summaryFile" -ForegroundColor Green
Write-Host ""

exit $testExitCode

# PowerShell Troubleshooting Script for Traffic Prediction System
# Task 17.6: Troubleshooting & Diagnostic Utilities
# 
# This script provides automated diagnostic routines, issue detection and fixes,
# log analysis, and step-by-step problem resolution guides

param(
    [string]$Issue = "",             # Specific issue to troubleshoot (empty = run all diagnostics)
    [switch]$AutoFix,                # Attempt automatic fixes for detected issues
    [switch]$Interactive,            # Interactive troubleshooting mode
    [switch]$ShowLogs,              # Display relevant log entries
    [switch]$Verbose,               # Verbose output for debugging
    [string]$OutputFile = "",        # Save diagnostics to file
    [int]$LogLines = 50             # Number of log lines to show
)

# Set error handling
$ErrorActionPreference = "Continue"
$VerbosePreference = if ($Verbose) { "Continue" } else { "SilentlyContinue" }

# Script metadata
$ScriptVersion = "1.0.0"
$ScriptName = "Traffic Prediction System - Troubleshooter"

# Define diagnostic routines and their fixes
$DiagnosticTests = @{
    "docker_issues" = @{
        Name = "Docker Environment Issues"
        Description = "Check Docker installation and connectivity"
        Tests = @(
            @{
                Name = "Docker Running"
                Check = { 
                    try { docker info | Out-Null; return $true } 
                    catch { return $false } 
                }
                Fix = { 
                    Write-TroubleshootLog "Please start Docker Desktop manually" "WARNING"
                    return $false
                }
                AutoFixable = $false
            },
            @{
                Name = "Docker Compose Available"
                Check = { 
                    try { docker-compose version | Out-Null; return $true } 
                    catch { return $false } 
                }
                Fix = { 
                    Write-TroubleshootLog "Docker Compose not available - check Docker installation" "ERROR"
                    return $false
                }
                AutoFixable = $false
            },
            @{
                Name = "Docker Resources"
                Check = {
                    try {
                        $dockerInfo = docker system df --format "table {{.Type}}\t{{.TotalCount}}\t{{.Size}}" 2>&1
                        return $LASTEXITCODE -eq 0
                    }
                    catch { return $false }
                }
                Fix = {
                    Write-TroubleshootLog "Cleaning up Docker resources..." "INFO"
                    try {
                        docker system prune -f 2>&1 | Out-Null
                        docker volume prune -f 2>&1 | Out-Null
                        return $true
                    }
                    catch { return $false }
                }
                AutoFixable = $true
            }
        )
    }
    
    "network_connectivity" = @{
        Name = "Network Connectivity Issues"
        Description = "Check port availability and network connectivity"
        Tests = @(
            @{
                Name = "PostgreSQL Port (5433)"
                Check = { Test-NetConnection -ComputerName "localhost" -Port 5433 -InformationLevel Quiet -WarningAction SilentlyContinue }
                Fix = {
                    Write-TroubleshootLog "Attempting to start PostgreSQL container..." "INFO"
                    try {
                        docker-compose up -d postgres
                        Start-Sleep -Seconds 15
                        return Test-NetConnection -ComputerName "localhost" -Port 5433 -InformationLevel Quiet -WarningAction SilentlyContinue
                    }
                    catch { return $false }
                }
                AutoFixable = $true
            },
            @{
                Name = "Kafka Port (9094)"
                Check = { Test-NetConnection -ComputerName "localhost" -Port 9094 -InformationLevel Quiet -WarningAction SilentlyContinue }
                Fix = {
                    Write-TroubleshootLog "Attempting to start Kafka services..." "INFO"
                    try {
                        docker-compose up -d zookeeper kafka
                        Start-Sleep -Seconds 30
                        return Test-NetConnection -ComputerName "localhost" -Port 9094 -InformationLevel Quiet -WarningAction SilentlyContinue
                    }
                    catch { return $false }
                }
                AutoFixable = $true
            },
            @{
                Name = "HDFS NameNode Port (9871)"
                Check = { Test-NetConnection -ComputerName "localhost" -Port 9871 -InformationLevel Quiet -WarningAction SilentlyContinue }
                Fix = {
                    Write-TroubleshootLog "Attempting to start HDFS NameNode..." "INFO"
                    try {
                        docker-compose up -d namenode
                        Start-Sleep -Seconds 45
                        return Test-NetConnection -ComputerName "localhost" -Port 9871 -InformationLevel Quiet -WarningAction SilentlyContinue
                    }
                    catch { return $false }
                }
                AutoFixable = $true
            },
            @{
                Name = "API Backend Port (8000)"
                Check = { Test-NetConnection -ComputerName "localhost" -Port 8000 -InformationLevel Quiet -WarningAction SilentlyContinue }
                Fix = {
                    Write-TroubleshootLog "Attempting to start FastAPI backend..." "INFO"
                    try {
                        # Kill any existing Python processes
                        Get-Process -Name "python" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
                        Start-Sleep -Seconds 5
                        
                        # Start new process
                        Start-Process -FilePath "cmd" -ArgumentList "/c", "python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000" -WindowStyle Hidden
                        Start-Sleep -Seconds 20
                        return Test-NetConnection -ComputerName "localhost" -Port 8000 -InformationLevel Quiet -WarningAction SilentlyContinue
                    }
                    catch { return $false }
                }
                AutoFixable = $true
            },
            @{
                Name = "Frontend Port (3000)"
                Check = { Test-NetConnection -ComputerName "localhost" -Port 3000 -InformationLevel Quiet -WarningAction SilentlyContinue }
                Fix = {
                    Write-TroubleshootLog "Attempting to start React frontend..." "INFO"
                    try {
                        # Kill any existing Node processes
                        Get-Process -Name "node" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
                        Start-Sleep -Seconds 5
                        
                        # Start new process
                        Start-Process -FilePath "cmd" -ArgumentList "/c", "npm run dev" -WindowStyle Hidden
                        Start-Sleep -Seconds 30
                        return Test-NetConnection -ComputerName "localhost" -Port 3000 -InformationLevel Quiet -WarningAction SilentlyContinue
                    }
                    catch { return $false }
                }
                AutoFixable = $true
            }
        )
    }
    
    "service_health" = @{
        Name = "Service Health Issues"
        Description = "Check individual service health and functionality"
        Tests = @(
            @{
                Name = "PostgreSQL Health"
                Check = {
                    try {
                        $result = docker exec postgres pg_isready -U postgres 2>&1
                        return $LASTEXITCODE -eq 0
                    }
                    catch { return $false }
                }
                Fix = {
                    Write-TroubleshootLog "Restarting PostgreSQL service..." "INFO"
                    try {
                        docker-compose restart postgres
                        Start-Sleep -Seconds 15
                        $result = docker exec postgres pg_isready -U postgres 2>&1
                        return $LASTEXITCODE -eq 0
                    }
                    catch { return $false }
                }
                AutoFixable = $true
            },
            @{
                Name = "Kafka Health"
                Check = {
                    try {
                        $result = docker exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092 2>&1
                        return $LASTEXITCODE -eq 0
                    }
                    catch { return $false }
                }
                Fix = {
                    Write-TroubleshootLog "Restarting Kafka services..." "INFO"
                    try {
                        docker-compose restart zookeeper kafka
                        Start-Sleep -Seconds 45
                        $result = docker exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092 2>&1
                        return $LASTEXITCODE -eq 0
                    }
                    catch { return $false }
                }
                AutoFixable = $true
            },
            @{
                Name = "HDFS Health"
                Check = {
                    try {
                        $response = Invoke-WebRequest -Uri "http://localhost:9871/jmx" -UseBasicParsing -TimeoutSec 10 -ErrorAction Stop
                        return $response.StatusCode -eq 200
                    }
                    catch { return $false }
                }
                Fix = {
                    Write-TroubleshootLog "Restarting HDFS services..." "INFO"
                    try {
                        docker-compose restart namenode datanode
                        Start-Sleep -Seconds 60
                        $response = Invoke-WebRequest -Uri "http://localhost:9871/jmx" -UseBasicParsing -TimeoutSec 10 -ErrorAction SilentlyContinue
                        return $response -and $response.StatusCode -eq 200
                    }
                    catch { return $false }
                }
                AutoFixable = $true
            }
        )
    }
    
    "configuration_issues" = @{
        Name = "Configuration Issues"
        Description = "Check configuration files and settings"
        Tests = @(
            @{
                Name = "Docker Compose Files"
                Check = {
                    $files = @("docker-compose.yml")
                    foreach ($file in $files) {
                        if (-not (Test-Path $file)) { return $false }
                    }
                    return $true
                }
                Fix = {
                    Write-TroubleshootLog "Missing Docker Compose files - cannot auto-fix" "ERROR"
                    return $false
                }
                AutoFixable = $false
            },
            @{
                Name = "Environment Files"
                Check = {
                    $files = @("hadoop.env", "kafka-config.env")
                    foreach ($file in $files) {
                        if (-not (Test-Path $file)) { return $false }
                    }
                    return $true
                }
                Fix = {
                    Write-TroubleshootLog "Missing environment files - cannot auto-fix" "ERROR"
                    return $false
                }
                AutoFixable = $false
            },
            @{
                Name = "Hadoop Configuration"
                Check = {
                    $configFiles = @("hadoop-configs/core-site.xml", "hadoop-configs/hdfs-site.xml", "hadoop-configs/yarn-site.xml")
                    foreach ($file in $configFiles) {
                        if (-not (Test-Path $file)) { return $false }
                    }
                    return $true
                }
                Fix = {
                    Write-TroubleshootLog "Missing Hadoop configuration files - cannot auto-fix" "ERROR"
                    return $false
                }
                AutoFixable = $false
            },
            @{
                Name = "Node.js Dependencies"
                Check = {
                    return (Test-Path "node_modules") -and (Test-Path "package.json")
                }
                Fix = {
                    Write-TroubleshootLog "Installing Node.js dependencies..." "INFO"
                    try {
                        npm install 2>&1 | Out-Null
                        return $LASTEXITCODE -eq 0
                    }
                    catch { return $false }
                }
                AutoFixable = $true
            },
            @{
                Name = "Python Dependencies"
                Check = {
                    try {
                        python -c "import fastapi, uvicorn, psycopg2" 2>&1 | Out-Null
                        return $LASTEXITCODE -eq 0
                    }
                    catch { return $false }
                }
                Fix = {
                    Write-TroubleshootLog "Installing Python dependencies..." "INFO"
                    try {
                        pip install -r requirements-fastapi.txt 2>&1 | Out-Null
                        return $LASTEXITCODE -eq 0
                    }
                    catch { return $false }
                }
                AutoFixable = $true
            }
        )
    }
    
    "resource_issues" = @{
        Name = "Resource Issues"
        Description = "Check system resources and capacity"
        Tests = @(
            @{
                Name = "Disk Space"
                Check = {
                    $drive = Get-WmiObject -Class Win32_LogicalDisk -Filter "DeviceID='C:'"
                    $freeSpaceGB = [math]::Round($drive.FreeSpace / 1GB, 2)
                    return $freeSpaceGB -gt 10  # At least 10GB free
                }
                Fix = {
                    Write-TroubleshootLog "Cleaning up Docker images and containers..." "INFO"
                    try {
                        docker system prune -af 2>&1 | Out-Null
                        docker volume prune -f 2>&1 | Out-Null
                        return $true
                    }
                    catch { return $false }
                }
                AutoFixable = $true
            },
            @{
                Name = "Memory Usage"
                Check = {
                    $memory = Get-WmiObject -Class Win32_OperatingSystem
                    $freeMemoryGB = [math]::Round($memory.FreePhysicalMemory / 1MB, 2)
                    return $freeMemoryGB -gt 2  # At least 2GB free
                }
                Fix = {
                    Write-TroubleshootLog "Memory usage high - consider restarting services" "WARNING"
                    return $false
                }
                AutoFixable = $false
            },
            @{
                Name = "Docker Resource Limits"
                Check = {
                    try {
                        $dockerInfo = docker info --format "{{.MemTotal}}" 2>&1
                        return $LASTEXITCODE -eq 0
                    }
                    catch { return $false }
                }
                Fix = {
                    Write-TroubleshootLog "Check Docker Desktop resource settings" "WARNING"
                    return $false
                }
                AutoFixable = $false
            }
        )
    }
}

# Common issues and their solutions
$CommonIssues = @{
    "kafka_connection_failed" = @{
        Name = "Kafka Connection Failed"
        Description = "Cannot connect to Kafka broker"
        Solutions = @(
            "Ensure Zookeeper is running first",
            "Check if Kafka container is started",
            "Verify port 9092 is not blocked by firewall",
            "Check docker-compose.yml for correct Kafka configuration"
        )
        AutoFix = "network_connectivity"
    }
    
    "hdfs_safemode" = @{
        Name = "HDFS Safe Mode"
        Description = "HDFS is stuck in safe mode"
        Solutions = @(
            "Wait for HDFS to exit safe mode automatically",
            "Force exit safe mode: docker exec namenode hdfs dfsadmin -safemode leave",
            "Check HDFS health: docker exec namenode hdfs dfsadmin -report",
            "Restart NameNode if necessary"
        )
        AutoFix = "service_health"
    }
    
    "database_connection_failed" = @{
        Name = "Database Connection Failed"
        Description = "Cannot connect to PostgreSQL database"
        Solutions = @(
            "Ensure PostgreSQL container is running",
            "Check database credentials in configuration",
            "Verify port 5433 is accessible",
            "Check database initialization scripts"
        )
        AutoFix = "network_connectivity"
    }
    
    "frontend_not_loading" = @{
        Name = "Frontend Not Loading"
        Description = "React frontend is not accessible"
        Solutions = @(
            "Check if Node.js dependencies are installed",
            "Ensure port 3000 is not in use by another process",
            "Check for JavaScript build errors",
            "Verify Next.js configuration"
        )
        AutoFix = "network_connectivity"
    }
    
    "api_server_error" = @{
        Name = "API Server Error"
        Description = "FastAPI backend is not responding"
        Solutions = @(
            "Check Python dependencies are installed",
            "Verify database connection is working",
            "Check API server logs for errors",
            "Ensure port 8000 is available"
        )
        AutoFix = "network_connectivity"
    }
}

# Global troubleshooting state
$TroubleshootState = @{
    StartTime = Get-Date
    TestsRun = 0
    TestsPassed = 0
    TestsFailed = 0
    FixesAttempted = 0
    FixesSuccessful = 0
    Issues = @()
    Recommendations = @()
}

function Write-Banner {
    param([string]$Message, [string]$Color = "Cyan")
    
    $border = "=" * 80
    Write-Host $border -ForegroundColor $Color
    Write-Host $Message -ForegroundColor $Color
    Write-Host $border -ForegroundColor $Color
    Write-Host ""
}

function Write-TroubleshootLog {
    param([string]$Message, [string]$Level = "INFO", [string]$Component = "")
    
    $timestamp = Get-Date -Format "HH:mm:ss"
    $prefix = if ($Component) { "[$Component]" } else { "" }
    
    $color = switch ($Level) {
        "SUCCESS" { "Green" }
        "WARNING" { "Yellow" }
        "ERROR" { "Red" }
        "FIX" { "Magenta" }
        "PROGRESS" { "Cyan" }
        default { "White" }
    }
    
    $icon = switch ($Level) {
        "SUCCESS" { "✅" }
        "WARNING" { "⚠️" }
        "ERROR" { "❌" }
        "FIX" { "🔧" }
        "PROGRESS" { "🔍" }
        default { "ℹ️" }
    }
    
    $logEntry = "[$timestamp] $icon $prefix $Message"
    Write-Host $logEntry -ForegroundColor $color
    
    # Write to output file if specified
    if ($OutputFile) {
        Add-Content -Path $OutputFile -Value $logEntry
    }
}

function Show-ServiceLogs {
    param([string]$ServiceName, [int]$Lines = 50)
    
    Write-TroubleshootLog "Showing logs for $ServiceName (last $Lines lines):" "INFO"
    
    try {
        switch ($ServiceName.ToLower()) {
            "postgres" {
                docker logs --tail $Lines postgres 2>&1
            }
            "kafka" {
                docker logs --tail $Lines kafka 2>&1
            }
            "zookeeper" {
                docker logs --tail $Lines zookeeper 2>&1
            }
            "namenode" {
                docker logs --tail $Lines namenode 2>&1
            }
            "datanode" {
                docker logs --tail $Lines datanode 2>&1
            }
            "resourcemanager" {
                docker logs --tail $Lines resourcemanager 2>&1
            }
            "nodemanager" {
                docker logs --tail $Lines nodemanager 2>&1
            }
            default {
                Write-TroubleshootLog "Unknown service for log viewing: $ServiceName" "WARNING"
            }
        }
    }
    catch {
        Write-TroubleshootLog "Failed to retrieve logs for $ServiceName : $_" "ERROR"
    }
}

function Invoke-DiagnosticTest {
    param([hashtable]$TestConfig, [string]$TestName)
    
    Write-TroubleshootLog "Running $TestName..." "PROGRESS"
    $TroubleshootState.TestsRun++
    
    try {
        $result = & $TestConfig.Check
        
        if ($result) {
            Write-TroubleshootLog "$TestName - PASSED ✅" "SUCCESS"
            $TroubleshootState.TestsPassed++
            return $true
        }
        else {
            Write-TroubleshootLog "$TestName - FAILED ❌" "ERROR"
            $TroubleshootState.TestsFailed++
            $TroubleshootState.Issues += $TestName
            
            # Attempt fix if enabled and available
            if ($AutoFix -and $TestConfig.AutoFixable) {
                Write-TroubleshootLog "Attempting automatic fix for $TestName..." "FIX"
                $TroubleshootState.FixesAttempted++
                
                $fixResult = & $TestConfig.Fix
                if ($fixResult) {
                    Write-TroubleshootLog "Automatic fix successful for $TestName ✅" "SUCCESS"
                    $TroubleshootState.FixesSuccessful++
                    return $true
                }
                else {
                    Write-TroubleshootLog "Automatic fix failed for $TestName ❌" "ERROR"
                }
            }
            elseif ($TestConfig.AutoFixable) {
                Write-TroubleshootLog "Automatic fix available for $TestName (use -AutoFix to apply)" "FIX"
            }
            
            return $false
        }
    }
    catch {
        Write-TroubleshootLog "Error running $TestName : $_" "ERROR"
        $TroubleshootState.TestsFailed++
        return $false
    }
}

function Invoke-DiagnosticSuite {
    param([string]$SuiteName)
    
    if (-not $DiagnosticTests.ContainsKey($SuiteName)) {
        Write-TroubleshootLog "Unknown diagnostic suite: $SuiteName" "ERROR"
        return $false
    }
    
    $suite = $DiagnosticTests[$SuiteName]
    Write-TroubleshootLog "🔍 Running $($suite.Name)..." "PROGRESS"
    Write-TroubleshootLog "$($suite.Description)" "INFO"
    Write-Host ""
    
    $suiteSuccess = $true
    
    foreach ($test in $suite.Tests) {
        $testResult = Invoke-DiagnosticTest -TestConfig $test -TestName $test.Name
        if (-not $testResult) {
            $suiteSuccess = $false
        }
        Start-Sleep -Seconds 1  # Brief pause between tests
    }
    
    Write-Host ""
    return $suiteSuccess
}

function Show-CommonIssueSolution {
    param([string]$IssueKey)
    
    if (-not $CommonIssues.ContainsKey($IssueKey)) {
        Write-TroubleshootLog "Unknown issue: $IssueKey" "ERROR"
        return
    }
    
    $issue = $CommonIssues[$IssueKey]
    Write-TroubleshootLog "📖 $($issue.Name)" "INFO"
    Write-TroubleshootLog "$($issue.Description)" "INFO"
    Write-Host ""
    
    Write-TroubleshootLog "Recommended Solutions:" "INFO"
    $solutionNumber = 1
    foreach ($solution in $issue.Solutions) {
        Write-Host "   $solutionNumber. $solution" -ForegroundColor White
        $solutionNumber++
    }
    
    if ($AutoFix -and $issue.AutoFix) {
        Write-TroubleshootLog "Attempting automatic fix via $($issue.AutoFix) diagnostics..." "FIX"
        Invoke-DiagnosticSuite -SuiteName $issue.AutoFix
    }
    
    Write-Host ""
}

function Show-InteractiveMenu {
    do {
        Write-Banner "🔧 INTERACTIVE TROUBLESHOOTING MENU" "Yellow"
        
        Write-Host "1. Run Full Diagnostics" -ForegroundColor White
        Write-Host "2. Check Docker Issues" -ForegroundColor White
        Write-Host "3. Check Network Connectivity" -ForegroundColor White
        Write-Host "4. Check Service Health" -ForegroundColor White
        Write-Host "5. Check Configuration" -ForegroundColor White
        Write-Host "6. Check System Resources" -ForegroundColor White
        Write-Host "7. View Service Logs" -ForegroundColor White
        Write-Host "8. Common Issue Solutions" -ForegroundColor White
        Write-Host "9. Run Health Check Script" -ForegroundColor White
        Write-Host "0. Exit" -ForegroundColor Gray
        Write-Host ""
        
        $choice = Read-Host "Select an option (0-9)"
        
        switch ($choice) {
            "1" {
                Write-TroubleshootLog "Running full diagnostic suite..." "INFO"
                foreach ($suiteName in $DiagnosticTests.Keys) {
                    Invoke-DiagnosticSuite -SuiteName $suiteName
                }
            }
            "2" { Invoke-DiagnosticSuite -SuiteName "docker_issues" }
            "3" { Invoke-DiagnosticSuite -SuiteName "network_connectivity" }
            "4" { Invoke-DiagnosticSuite -SuiteName "service_health" }
            "5" { Invoke-DiagnosticSuite -SuiteName "configuration_issues" }
            "6" { Invoke-DiagnosticSuite -SuiteName "resource_issues" }
            "7" {
                Write-Host "Available services: postgres, kafka, zookeeper, namenode, datanode, resourcemanager, nodemanager" -ForegroundColor Cyan
                $serviceName = Read-Host "Enter service name to view logs"
                if ($serviceName) {
                    Show-ServiceLogs -ServiceName $serviceName -Lines $LogLines
                }
            }
            "8" {
                Write-Host "Common Issues:" -ForegroundColor Cyan
                $issueNumber = 1
                foreach ($issueKey in $CommonIssues.Keys) {
                    Write-Host "$issueNumber. $($CommonIssues[$issueKey].Name)" -ForegroundColor White
                    $issueNumber++
                }
                $issueChoice = Read-Host "Select issue number"
                $issueKeys = $CommonIssues.Keys | Sort-Object
                if ($issueChoice -match '^\d+$' -and [int]$issueChoice -ge 1 -and [int]$issueChoice -le $issueKeys.Count) {
                    $selectedIssue = $issueKeys[[int]$issueChoice - 1]
                    Show-CommonIssueSolution -IssueKey $selectedIssue
                }
            }
            "9" {
                Write-TroubleshootLog "Running health check script..." "INFO"
                try {
                    & ".\health-check.ps1"
                }
                catch {
                    Write-TroubleshootLog "Failed to run health check: $_" "ERROR"
                }
            }
            "0" {
                Write-TroubleshootLog "Exiting interactive mode..." "INFO"
                break
            }
            default {
                Write-TroubleshootLog "Invalid choice. Please select 0-9." "WARNING"
            }
        }
        
        if ($choice -ne "0") {
            Write-Host ""
            Read-Host "Press Enter to continue"
        }
        
    } while ($choice -ne "0")
}

function Show-TroubleshootingSummary {
    $endTime = Get-Date
    $duration = $endTime - $TroubleshootState.StartTime
    
    Write-Banner "🎯 TROUBLESHOOTING SUMMARY" "Green"
    
    Write-Host "Duration: $($duration.TotalMinutes.ToString('F1')) minutes" -ForegroundColor Cyan
    Write-Host "Tests Run: $($TroubleshootState.TestsRun)" -ForegroundColor Cyan
    Write-Host "Tests Passed: $($TroubleshootState.TestsPassed)" -ForegroundColor Green
    Write-Host "Tests Failed: $($TroubleshootState.TestsFailed)" -ForegroundColor Red
    Write-Host "Fixes Attempted: $($TroubleshootState.FixesAttempted)" -ForegroundColor Yellow
    Write-Host "Fixes Successful: $($TroubleshootState.FixesSuccessful)" -ForegroundColor Green
    
    if ($TroubleshootState.Issues.Count -gt 0) {
        Write-Host "`n❌ Issues Found:" -ForegroundColor Red
        foreach ($issue in $TroubleshootState.Issues) {
            Write-Host "   • $issue" -ForegroundColor Red
        }
    }
    
    if ($TroubleshootState.Recommendations.Count -gt 0) {
        Write-Host "`n💡 Recommendations:" -ForegroundColor Yellow
        foreach ($recommendation in $TroubleshootState.Recommendations) {
            Write-Host "   • $recommendation" -ForegroundColor Yellow
        }
    }
    
    # Overall health assessment
    $successRate = if ($TroubleshootState.TestsRun -gt 0) {
        ($TroubleshootState.TestsPassed / $TroubleshootState.TestsRun) * 100
    } else { 0 }
    
    $healthStatus = if ($successRate -ge 90) {
        "EXCELLENT"
    } elseif ($successRate -ge 75) {
        "GOOD"
    } elseif ($successRate -ge 50) {
        "FAIR" 
    } else {
        "POOR"
    }
    
    $statusColor = switch ($healthStatus) {
        "EXCELLENT" { "Green" }
        "GOOD" { "Green" }
        "FAIR" { "Yellow" }
        "POOR" { "Red" }
    }
    
    Write-Host "`n🎯 System Health: $healthStatus ($($successRate.ToString('F1'))% tests passed)" -ForegroundColor $statusColor
    
    # Next steps
    if ($TroubleshootState.TestsFailed -gt 0) {
        Write-Host "`n🔧 Next Steps:" -ForegroundColor Cyan
        Write-Host "   • Review failed tests above" -ForegroundColor White
        Write-Host "   • Run specific diagnostic suites: .\troubleshoot.ps1 -Issue [suite_name]" -ForegroundColor White
        Write-Host "   • Use automatic fixes: .\troubleshoot.ps1 -AutoFix" -ForegroundColor White
        Write-Host "   • Check service logs: .\troubleshoot.ps1 -ShowLogs" -ForegroundColor White
        Write-Host "   • Interactive mode: .\troubleshoot.ps1 -Interactive" -ForegroundColor White
    }
    else {
        Write-Host "`n🎉 All diagnostics passed! System appears healthy." -ForegroundColor Green
    }
    
    Write-Host ""
    return $successRate -ge 75
}

function main {
    Write-Banner "$ScriptName v$ScriptVersion" "Green"
    
    Write-Host "Configuration:" -ForegroundColor Cyan
    Write-Host "  Target Issue: $(if ($Issue) { $Issue } else { 'Full Diagnostics' })" -ForegroundColor White
    Write-Host "  Auto Fix: $AutoFix" -ForegroundColor White
    Write-Host "  Interactive Mode: $Interactive" -ForegroundColor White
    Write-Host "  Show Logs: $ShowLogs" -ForegroundColor White
    Write-Host "  Log Lines: $LogLines" -ForegroundColor White
    Write-Host "  Output File: $(if ($OutputFile) { $OutputFile } else { 'Console Only' })" -ForegroundColor White
    Write-Host ""
    
    # Initialize output file
    if ($OutputFile) {
        "# Traffic Prediction System - Troubleshooting Report" | Out-File -FilePath $OutputFile
        "# Generated: $(Get-Date)" | Add-Content -Path $OutputFile
        "" | Add-Content -Path $OutputFile
    }
    
    # Interactive mode
    if ($Interactive) {
        Show-InteractiveMenu
        return $true
    }
    
    # Show logs if requested
    if ($ShowLogs) {
        $services = @("postgres", "kafka", "zookeeper", "namenode", "datanode", "resourcemanager", "nodemanager")
        foreach ($service in $services) {
            Show-ServiceLogs -ServiceName $service -Lines $LogLines
            Write-Host ""
        }
        return $true
    }
    
    # Specific issue troubleshooting
    if ($Issue) {
        if ($DiagnosticTests.ContainsKey($Issue)) {
            $success = Invoke-DiagnosticSuite -SuiteName $Issue
        }
        elseif ($CommonIssues.ContainsKey($Issue)) {
            Show-CommonIssueSolution -IssueKey $Issue
            $success = $true
        }
        else {
            Write-TroubleshootLog "Unknown issue or diagnostic suite: $Issue" "ERROR"
            Write-TroubleshootLog "Available diagnostic suites: $($DiagnosticTests.Keys -join ', ')" "INFO"
            Write-TroubleshootLog "Available common issues: $($CommonIssues.Keys -join ', ')" "INFO"
            $success = $false
        }
    }
    else {
        # Run full diagnostics
        Write-TroubleshootLog "🚀 Starting comprehensive system diagnostics..." "INFO"
        
        $overallSuccess = $true
        foreach ($suiteName in $DiagnosticTests.Keys) {
            $suiteSuccess = Invoke-DiagnosticSuite -SuiteName $suiteName
            if (-not $suiteSuccess) {
                $overallSuccess = $false
            }
        }
        
        $success = $overallSuccess
    }
    
    # Show summary
    $systemHealthy = Show-TroubleshootingSummary
    
    if ($OutputFile) {
        Write-TroubleshootLog "Full troubleshooting report saved to: $OutputFile" "INFO"
    }
    
    return $systemHealthy
}

# Script execution
try {
    $success = main
    exit $(if ($success) { 0 } else { 1 })
}
catch {
    Write-TroubleshootLog "Fatal error during troubleshooting: $_" "ERROR"
    exit 1
}
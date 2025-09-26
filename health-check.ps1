# PowerShell Health Check Script for Traffic Prediction System
# Task 17.2: Service Health Check Framework
# 
# This script validates all system services, tests connectivity, and provides diagnostic information

param(
    [switch]$Verbose,
    [switch]$Quick,
    [switch]$ShowDetails,
    [string]$Service = "",
    [string]$OutputFormat = "console"  # Options: console, json, html
)

# Set error handling
$ErrorActionPreference = "Continue"
$VerbosePreference = if ($Verbose) { "Continue" } else { "SilentlyContinue" }

# Script metadata
$ScriptVersion = "1.0.0"
$ScriptName = "Traffic Prediction System - Health Check"

# Define comprehensive service health checks
$HealthChecks = @{
    "Infrastructure" = @{
        "PostgreSQL" = @{
            DockerService = "postgres"
            Port = 5433
            HealthEndpoint = $null
            Command = "docker exec postgres pg_isready -U traffic_user"
            DatabaseTest = "docker exec postgres psql -U traffic_user -d traffic_prediction -c 'SELECT 1'"
            ExpectedProcesses = @("postgres")
            ConfigFiles = @("database/init/init.sql")
            Description = "PostgreSQL Database Server"
        }
    }
    "MessageBroker" = @{
        "Zookeeper" = @{
            DockerService = "zookeeper"
            Port = 2181
            HealthEndpoint = $null
            Command = "docker exec zookeeper zkServer.sh status"
            AlternativeCommand = "echo stat | nc localhost 2181"
            ExpectedProcesses = @("QuorumPeerMain")
            ConfigFiles = @("config/kafka.properties")
            Description = "Apache Zookeeper Coordination Service"
        }
        "Kafka" = @{
            DockerService = "kafka"
            Port = 9092
            HealthEndpoint = $null
            Command = "docker exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092"
            TopicListCommand = "docker exec kafka kafka-topics --list --bootstrap-server localhost:9092"
            ExpectedProcesses = @("Kafka")
            ConfigFiles = @("config/kafka.properties")
            ExpectedTopics = @("traffic-events", "processed-traffic-aggregates", "traffic-predictions")
            Description = "Apache Kafka Message Broker"
        }
    }
    "KafkaEcosystem" = @{
        "Schema Registry" = @{
            DockerService = "schema-registry"
            Port = 8081
            HealthEndpoint = "http://localhost:8081/subjects"
            Command = "curl -f http://localhost:8081/subjects"
            ConfigTest = "curl -f http://localhost:8081/config"
            ExpectedProcesses = @("SchemaRegistryMain")
            ConfigFiles = @("schemas/traffic-event.avsc", "schemas/processed-traffic-aggregate.avsc")
            Description = "Confluent Schema Registry"
        }
        "Kafka Connect" = @{
            DockerService = "kafka-connect"
            Port = 8083
            HealthEndpoint = "http://localhost:8083/connectors"
            Command = "curl -f http://localhost:8083/connectors"
            StatusCommand = "curl -f http://localhost:8083/connector-plugins"
            ExpectedProcesses = @("ConnectDistributed")
            ConfigFiles = @("connectors/hdfs-sink-connector.json")
            Description = "Kafka Connect Distributed"
        }
    }
    "BigData" = @{
        "HDFS NameNode" = @{
            DockerService = "namenode"
            Port = 9871
            HealthEndpoint = "http://localhost:9871/jmx"
            Command = "curl -f http://localhost:9871/jmx"
            HDFSCommand = "docker exec namenode hdfs dfsadmin -report"
            WebUITest = "http://localhost:9871/explorer.html"
            ExpectedProcesses = @("NameNode")
            ConfigFiles = @("hadoop-configs/hdfs-site.xml", "hadoop-configs/core-site.xml")
            Description = "Hadoop HDFS NameNode"
        }
        "HDFS DataNode" = @{
            DockerService = "datanode"
            Port = 9864
            HealthEndpoint = "http://localhost:9864/jmx"
            Command = "curl -f http://localhost:9864/jmx"
            DataNodeInfo = "curl -f http://localhost:9864/datanode"
            ExpectedProcesses = @("DataNode")
            ConfigFiles = @("hadoop-configs/hdfs-site.xml")
            Description = "Hadoop HDFS DataNode"
        }
    }
    "ComputeEngine" = @{
        "YARN ResourceManager" = @{
            DockerService = "resourcemanager"
            Port = 8088
            HealthEndpoint = "http://localhost:8088/ws/v1/cluster/info"
            Command = "curl -f http://localhost:8088/ws/v1/cluster/info"
            NodesCommand = "curl -f http://localhost:8088/ws/v1/cluster/nodes"
            AppsCommand = "curl -f http://localhost:8088/ws/v1/cluster/apps"
            ExpectedProcesses = @("ResourceManager")
            ConfigFiles = @("hadoop-configs/yarn-site.xml")
            Description = "YARN Resource Manager"
        }
        "YARN NodeManager" = @{
            DockerService = "nodemanager"
            Port = 8042
            HealthEndpoint = "http://localhost:8042/ws/v1/node/info"
            Command = "curl -f http://localhost:8042/ws/v1/node/info"
            ContainersCommand = "curl -f http://localhost:8042/ws/v1/node/containers"
            ExpectedProcesses = @("NodeManager")
            ConfigFiles = @("hadoop-configs/yarn-site.xml")
            Description = "YARN Node Manager"
        }
    }
    "Application" = @{
        "FastAPI Backend" = @{
            ProcessBased = $true
            Port = 8000
            HealthEndpoint = "http://localhost:8000/health"
            Command = "curl -f http://localhost:8000/health"
            APIDocsTest = "curl -f http://localhost:8000/docs"
            VersionTest = "curl -f http://localhost:8000/api/v1/system/version"
            ExpectedProcesses = @("python", "uvicorn")
            ConfigFiles = @("src/api/main.py", "requirements-fastapi.txt")
            Description = "FastAPI Application Server"
        }
        "React Frontend" = @{
            ProcessBased = $true
            Port = 3000
            HealthEndpoint = "http://localhost:3000"
            Command = "curl -f http://localhost:3000"
            BuildTest = "npm run build --dry-run"
            ExpectedProcesses = @("node", "next")
            ConfigFiles = @("package.json", "next.config.ts")
            Description = "React Frontend Application"
        }
    }
}

# Global health status
$HealthStatus = @{
    CheckTime = Get-Date
    TotalServices = 0
    HealthyServices = 0
    UnhealthyServices = 0
    SkippedServices = 0
    ServiceResults = @{}
    SystemHealth = "Unknown"
    Warnings = @()
    Errors = @()
}

function Write-Banner {
    param([string]$Message, [string]$Color = "Cyan")
    
    $border = "=" * 80
    Write-Host $border -ForegroundColor $Color
    Write-Host $Message -ForegroundColor $Color
    Write-Host $border -ForegroundColor $Color
    Write-Host ""
}

function Write-HealthStatus {
    param([string]$Message, [string]$Status = "INFO", [string]$Service = "")
    
    $timestamp = Get-Date -Format "HH:mm:ss"
    $prefix = if ($Service) { "[$Service]" } else { "" }
    
    $color = switch ($Status) {
        "PASS" { "Green" }
        "FAIL" { "Red" }
        "WARN" { "Yellow" }
        "SKIP" { "Gray" }
        default { "White" }
    }
    
    $icon = switch ($Status) {
        "PASS" { "✅" }
        "FAIL" { "❌" }
        "WARN" { "⚠️" }
        "SKIP" { "⏭️" }
        default { "ℹ️" }
    }
    
    Write-Host "[$timestamp] $icon $prefix $Message" -ForegroundColor $color
}

function Test-Port {
    param([int]$Port, [string]$ServiceName, [int]$TimeoutSeconds = 5)
    
    try {
        $connection = Test-NetConnection -ComputerName "localhost" -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue
        return $connection
    }
    catch {
        Write-Verbose "Port test failed for $ServiceName on port $Port : $_"
        return $false
    }
}

function Test-DockerContainer {
    param([string]$ContainerName)
    
    try {
        $containerStatus = docker ps --filter "name=$ContainerName" --format "{{.Status}}"
        if ($containerStatus -and $containerStatus -like "*Up*") {
            return @{
                Running = $true
                Status = $containerStatus
                Health = "healthy"
            }
        }
        else {
            $containerExists = docker ps -a --filter "name=$ContainerName" --format "{{.Status}}"
            return @{
                Running = $false
                Status = $containerExists
                Health = "unhealthy"
            }
        }
    }
    catch {
        return @{
            Running = $false
            Status = "Error checking container"
            Health = "unknown"
        }
    }
}

function Test-HTTPEndpoint {
    param([string]$Url, [int]$TimeoutSeconds = 10)
    
    try {
        $response = Invoke-WebRequest -Uri $Url -TimeoutSec $TimeoutSeconds -UseBasicParsing -ErrorAction Stop
        return @{
            Success = $true
            StatusCode = $response.StatusCode
            ResponseTime = 0  # Could implement timing if needed
            Content = $response.Content
        }
    }
    catch {
        return @{
            Success = $false
            StatusCode = $null
            Error = $_.Exception.Message
        }
    }
}

function Test-ProcessRunning {
    param([string[]]$ProcessNames, [string]$ServiceName)
    
    $runningProcesses = @()
    foreach ($processName in $ProcessNames) {
        $processes = Get-Process -Name $processName -ErrorAction SilentlyContinue
        if ($processes) {
            $runningProcesses += $processes
        }
    }
    
    return @{
        Found = $runningProcesses.Count -gt 0
        Processes = $runningProcesses
        Count = $runningProcesses.Count
    }
}

function Test-ConfigFile {
    param([string]$FilePath)
    
    if (Test-Path $FilePath) {
        try {
            $fileInfo = Get-Item $FilePath
            return @{
                Exists = $true
                Size = $fileInfo.Length
                LastModified = $fileInfo.LastWriteTime
                Readable = $true
            }
        }
        catch {
            return @{
                Exists = $true
                Size = 0
                Error = $_.Exception.Message
                Readable = $false
            }
        }
    }
    else {
        return @{
            Exists = $false
            Size = 0
            Readable = $false
        }
    }
}

function Test-ServiceHealth {
    param(
        [string]$ServiceName,
        [hashtable]$ServiceConfig,
        [switch]$QuickCheck
    )
    
    Write-HealthStatus "Testing $ServiceName..." "INFO" $ServiceName
    
    $result = @{
        ServiceName = $ServiceName
        Description = $ServiceConfig.Description
        Overall = "UNKNOWN"
        Tests = @{}
        Warnings = @()
        Errors = @()
        Details = @{}
    }
    
    $testsPassed = 0
    $totalTests = 0
    
    # Docker Container Check (if not process-based)
    if (-not $ServiceConfig.ProcessBased -and $ServiceConfig.DockerService) {
        $totalTests++
        Write-Verbose "Checking Docker container: $($ServiceConfig.DockerService)"
        
        $containerTest = Test-DockerContainer -ContainerName $ServiceConfig.DockerService
        $result.Tests["Docker Container"] = $containerTest
        $result.Details["Container Status"] = $containerTest.Status
        
        if ($containerTest.Running) {
            $testsPassed++
            Write-HealthStatus "Docker container is running" "PASS" $ServiceName
        }
        else {
            Write-HealthStatus "Docker container is not running: $($containerTest.Status)" "FAIL" $ServiceName
            $result.Errors += "Docker container not running"
        }
    }
    
    # Process Check (for process-based services)
    if ($ServiceConfig.ProcessBased -and $ServiceConfig.ExpectedProcesses) {
        $totalTests++
        Write-Verbose "Checking processes: $($ServiceConfig.ExpectedProcesses -join ', ')"
        
        $processTest = Test-ProcessRunning -ProcessNames $ServiceConfig.ExpectedProcesses -ServiceName $ServiceName
        $result.Tests["Process Check"] = $processTest
        $result.Details["Running Processes"] = $processTest.Count
        
        if ($processTest.Found) {
            $testsPassed++
            Write-HealthStatus "$($processTest.Count) expected processes running" "PASS" $ServiceName
        }
        else {
            Write-HealthStatus "No expected processes found" "FAIL" $ServiceName  
            $result.Errors += "Expected processes not running"
        }
    }
    
    # Port Connectivity Check
    if ($ServiceConfig.Port) {
        $totalTests++
        Write-Verbose "Testing port: $($ServiceConfig.Port)"
        
        $portTest = Test-Port -Port $ServiceConfig.Port -ServiceName $ServiceName
        $result.Tests["Port Connectivity"] = @{ Available = $portTest }
        
        if ($portTest) {
            $testsPassed++
            Write-HealthStatus "Port $($ServiceConfig.Port) is accessible" "PASS" $ServiceName
        }
        else {
            Write-HealthStatus "Port $($ServiceConfig.Port) is not accessible" "FAIL" $ServiceName
            $result.Errors += "Port not accessible"
        }
    }
    
    # HTTP Health Endpoint Check
    if ($ServiceConfig.HealthEndpoint) {
        $totalTests++
        Write-Verbose "Testing HTTP endpoint: $($ServiceConfig.HealthEndpoint)"
        
        $httpTest = Test-HTTPEndpoint -Url $ServiceConfig.HealthEndpoint
        $result.Tests["HTTP Health Check"] = $httpTest
        
        if ($httpTest.Success) {
            $testsPassed++
            Write-HealthStatus "HTTP health endpoint responding (Status: $($httpTest.StatusCode))" "PASS" $ServiceName
            $result.Details["HTTP Status"] = $httpTest.StatusCode
        }
        else {
            Write-HealthStatus "HTTP health endpoint failed: $($httpTest.Error)" "FAIL" $ServiceName
            $result.Errors += "HTTP endpoint unreachable"
        }
    }
    
    # Quick check mode - skip detailed tests
    if ($QuickCheck) {
        Write-Verbose "Quick check mode - skipping detailed tests"
    }
    else {
        # Command-based Health Check
        if ($ServiceConfig.Command) {
            $totalTests++
            Write-Verbose "Running health command: $($ServiceConfig.Command)"
            
            try {
                $commandResult = Invoke-Expression $ServiceConfig.Command 2>&1
                $commandSuccess = $LASTEXITCODE -eq 0
                
                $result.Tests["Service Command"] = @{
                    Success = $commandSuccess
                    Output = $commandResult
                    ExitCode = $LASTEXITCODE
                }
                
                if ($commandSuccess) {
                    $testsPassed++
                    Write-HealthStatus "Service command executed successfully" "PASS" $ServiceName
                }
                else {
                    Write-HealthStatus "Service command failed (Exit: $LASTEXITCODE)" "FAIL" $ServiceName
                    $result.Errors += "Service command failed"
                }
            }
            catch {
                Write-HealthStatus "Service command error: $_" "FAIL" $ServiceName
                $result.Errors += "Service command error: $_"
                $result.Tests["Service Command"] = @{
                    Success = $false
                    Error = $_.Exception.Message
                }
            }
        }
        
        # Configuration Files Check
        if ($ServiceConfig.ConfigFiles) {
            $configResults = @()
            foreach ($configFile in $ServiceConfig.ConfigFiles) {
                $configTest = Test-ConfigFile -FilePath $configFile
                $configResults += @{
                    File = $configFile
                    Test = $configTest
                }
                
                if (-not $configTest.Exists) {
                    $result.Warnings += "Config file missing: $configFile"
                    Write-HealthStatus "Config file missing: $configFile" "WARN" $ServiceName
                }
                elseif (-not $configTest.Readable) {
                    $result.Warnings += "Config file unreadable: $configFile"
                    Write-HealthStatus "Config file unreadable: $configFile" "WARN" $ServiceName
                }
            }
            $result.Tests["Configuration Files"] = $configResults
        }
        
        # Service-Specific Tests
        switch ($ServiceName) {
            "Kafka" {
                if ($ServiceConfig.ExpectedTopics -and $ServiceConfig.TopicListCommand) {
                    try {
                        $topics = Invoke-Expression $ServiceConfig.TopicListCommand 2>&1
                        $topicsList = $topics -split "`n" | Where-Object { $_ }
                        
                        $missingTopics = @()
                        foreach ($expectedTopic in $ServiceConfig.ExpectedTopics) {
                            if ($expectedTopic -notin $topicsList) {
                                $missingTopics += $expectedTopic
                            }
                        }
                        
                        if ($missingTopics.Count -eq 0) {
                            Write-HealthStatus "All expected Kafka topics exist" "PASS" $ServiceName
                        }
                        else {
                            Write-HealthStatus "Missing Kafka topics: $($missingTopics -join ', ')" "WARN" $ServiceName
                            $result.Warnings += "Missing topics: $($missingTopics -join ', ')"
                        }
                        
                        $result.Details["Topics"] = $topicsList
                    }
                    catch {
                        $result.Warnings += "Could not list Kafka topics"
                    }
                }
            }
            "PostgreSQL" {
                if ($ServiceConfig.DatabaseTest) {
                    try {
                        $dbResult = Invoke-Expression $ServiceConfig.DatabaseTest 2>&1
                        if ($LASTEXITCODE -eq 0) {
                            Write-HealthStatus "Database connectivity test passed" "PASS" $ServiceName
                        }
                        else {
                            Write-HealthStatus "Database connectivity test failed" "WARN" $ServiceName  
                            $result.Warnings += "Database connectivity issue"
                        }
                    }
                    catch {
                        $result.Warnings += "Could not test database connectivity"
                    }
                }
            }
        }
    }
    
    # Calculate overall health
    if ($totalTests -eq 0) {
        $result.Overall = "SKIP"
        Write-HealthStatus "No tests configured for $ServiceName" "SKIP" $ServiceName
    }
    elseif ($testsPassed -eq $totalTests) {
        $result.Overall = "PASS"
        Write-HealthStatus "$ServiceName is healthy ✅" "PASS" $ServiceName
    }
    elseif ($testsPassed -gt 0) {
        $result.Overall = "WARN"
        Write-HealthStatus "$ServiceName has issues ($testsPassed/$totalTests tests passed) ⚠️" "WARN" $ServiceName
    }
    else {
        $result.Overall = "FAIL"
        Write-HealthStatus "$ServiceName is unhealthy (0/$totalTests tests passed) ❌" "FAIL" $ServiceName
    }
    
    $result.Details["Tests Passed"] = $testsPassed
    $result.Details["Total Tests"] = $totalTests
    
    return $result
}

function Show-HealthSummary {
    param([hashtable]$Results)
    
    Write-Banner "🏥 HEALTH CHECK SUMMARY" "Green"
    
    $endTime = Get-Date
    $duration = $endTime - $HealthStatus.CheckTime
    
    Write-Host "Check Duration: $($duration.TotalSeconds.ToString('F1')) seconds" -ForegroundColor Cyan
    Write-Host "Total Services: $($HealthStatus.TotalServices)" -ForegroundColor Cyan
    Write-Host "Healthy: $($HealthStatus.HealthyServices)" -ForegroundColor Green
    Write-Host "Unhealthy: $($HealthStatus.UnhealthyServices)" -ForegroundColor Red
    Write-Host "Warnings: $($HealthStatus.Warnings.Count)" -ForegroundColor Yellow
    Write-Host "Skipped: $($HealthStatus.SkippedServices)" -ForegroundColor Gray
    
    # Service breakdown by category
    Write-Host "`n📊 Service Status by Category:" -ForegroundColor Cyan
    foreach ($category in $HealthChecks.Keys) {
        $categoryServices = $HealthChecks[$category]
        $categoryResults = @()
        
        foreach ($serviceName in $categoryServices.Keys) {
            if ($Results.ContainsKey($serviceName)) {
                $categoryResults += $Results[$serviceName]
            }
        }
        
        if ($categoryResults.Count -gt 0) {
            $healthy = ($categoryResults | Where-Object { $_.Overall -eq "PASS" }).Count
            $total = $categoryResults.Count
            $status = if ($healthy -eq $total) { "✅" } elseif ($healthy -gt 0) { "⚠️" } else { "❌" }
            
            Write-Host "   $category`: $status $healthy/$total services healthy" -ForegroundColor White
        }
    }
    
    # Failed services
    if ($HealthStatus.UnhealthyServices -gt 0) {
        Write-Host "`n❌ Unhealthy Services:" -ForegroundColor Red
        foreach ($serviceName in $Results.Keys) {
            $result = $Results[$serviceName]
            if ($result.Overall -eq "FAIL") {
                Write-Host "   • $serviceName - $($result.Errors -join ', ')" -ForegroundColor Red
            }
        }
    }
    
    # Services with warnings
    if ($HealthStatus.Warnings.Count -gt 0) {
        Write-Host "`n⚠️ Services with Warnings:" -ForegroundColor Yellow
        foreach ($serviceName in $Results.Keys) {
            $result = $Results[$serviceName]
            if ($result.Overall -eq "WARN" -or $result.Warnings.Count -gt 0) {
                Write-Host "   • $serviceName - $($result.Warnings -join ', ')" -ForegroundColor Yellow
            }
        }
    }
    
    # Overall system health
    $systemHealth = if ($HealthStatus.UnhealthyServices -eq 0) {
        if ($HealthStatus.Warnings.Count -eq 0) { "EXCELLENT" } else { "GOOD" }
    }
    elseif ($HealthStatus.HealthyServices -gt $HealthStatus.UnhealthyServices) {
        "DEGRADED"
    }
    else {
        "CRITICAL"
    }
    
    $HealthStatus.SystemHealth = $systemHealth
    
    $healthColor = switch ($systemHealth) {
        "EXCELLENT" { "Green" }
        "GOOD" { "Green" }
        "DEGRADED" { "Yellow" }
        "CRITICAL" { "Red" }
    }
    
    Write-Host "`n🎯 System Health: $systemHealth" -ForegroundColor $healthColor
    
    if ($systemHealth -eq "EXCELLENT") {
        Write-Host "`n🎉 All systems are healthy and operating normally!" -ForegroundColor Green
    }
    elseif ($systemHealth -eq "CRITICAL") {
        Write-Host "`n🚨 System is in critical state. Immediate attention required!" -ForegroundColor Red
        Write-Host "   Run: .\troubleshoot.ps1 for automated diagnostics" -ForegroundColor Yellow
    }
    
    Write-Host ""
    return $systemHealth -in @("EXCELLENT", "GOOD")
}

function Export-HealthReport {
    param(
        [hashtable]$Results,
        [string]$Format,
        [string]$OutputPath
    )
    
    switch ($Format.ToLower()) {
        "json" {
            $report = @{
                CheckTime = $HealthStatus.CheckTime
                SystemHealth = $HealthStatus.SystemHealth
                Summary = @{
                    TotalServices = $HealthStatus.TotalServices
                    HealthyServices = $HealthStatus.HealthyServices
                    UnhealthyServices = $HealthStatus.UnhealthyServices
                    SkippedServices = $HealthStatus.SkippedServices
                }
                Services = $Results
            }
            
            $jsonReport = $report | ConvertTo-Json -Depth 10
            if ($OutputPath) {
                $jsonReport | Out-File -FilePath $OutputPath -Encoding UTF8
                Write-HealthStatus "Health report exported to: $OutputPath" "INFO"
            }
            else {
                return $jsonReport
            }
        }
        "html" {
            # HTML report implementation would go here
            Write-HealthStatus "HTML export not yet implemented" "WARN"
        }
    }
}

function main {
    Write-Banner "$ScriptName v$ScriptVersion" "Green"
    
    Write-Host "Configuration:" -ForegroundColor Cyan
    Write-Host "  Quick Check: $Quick" -ForegroundColor White
    Write-Host "  Show Details: $ShowDetails" -ForegroundColor White
    Write-Host "  Specific Service: $(if ($Service) { $Service } else { 'All Services' })" -ForegroundColor White
    Write-Host "  Output Format: $OutputFormat" -ForegroundColor White
    Write-Host ""
    
    # Pre-flight checks
    Write-HealthStatus "🔍 Running pre-flight checks..." "INFO"
    
    try {
        docker info | Out-Null
        Write-HealthStatus "Docker is running ✅" "PASS"
    }
    catch {
        Write-HealthStatus "Docker is not running ❌" "FAIL"
        $HealthStatus.Errors += "Docker not running"
    }
    
    Write-Host ""
    
    # Run health checks
    $results = @{}
    
    foreach ($category in $HealthChecks.Keys) {
        $categoryServices = $HealthChecks[$category]
        
        foreach ($serviceName in $categoryServices.Keys) {
            # Skip if specific service requested and this isn't it
            if ($Service -and $serviceName -ne $Service) {
                continue
            }
            
            $HealthStatus.TotalServices++
            $serviceConfig = $categoryServices[$serviceName]
            
            try {
                $serviceResult = Test-ServiceHealth -ServiceName $serviceName -ServiceConfig $serviceConfig -QuickCheck:$Quick
                $results[$serviceName] = $serviceResult
                
                # Update counters
                switch ($serviceResult.Overall) {
                    "PASS" { $HealthStatus.HealthyServices++ }
                    "FAIL" { $HealthStatus.UnhealthyServices++ }
                    "WARN" { 
                        $HealthStatus.HealthyServices++  # Still functional
                        $HealthStatus.Warnings += $serviceResult.Warnings
                    }
                    "SKIP" { $HealthStatus.SkippedServices++ }
                }
                
                $HealthStatus.ServiceResults[$serviceName] = $serviceResult
            }
            catch {
                Write-HealthStatus "Error checking $serviceName : $_" "FAIL"
                $HealthStatus.UnhealthyServices++
                $HealthStatus.Errors += "Error checking $serviceName : $_"
            }
            
            Write-Host ""  # Space between services
        }
    }
    
    # Show summary
    $systemHealthy = Show-HealthSummary -Results $results
    
    # Export results if requested
    if ($OutputFormat -ne "console") {
        Export-HealthReport -Results $results -Format $OutputFormat
    }
    
    # Show detailed results if requested
    if ($ShowDetails) {
        Write-Banner "📋 DETAILED RESULTS" "Cyan"
        foreach ($serviceName in $results.Keys) {
            $result = $results[$serviceName]
            Write-Host "=== $serviceName ===" -ForegroundColor Cyan
            Write-Host "Description: $($result.Description)" -ForegroundColor White
            Write-Host "Overall Status: $($result.Overall)" -ForegroundColor $(
                switch ($result.Overall) {
                    "PASS" { "Green" }
                    "FAIL" { "Red" }
                    "WARN" { "Yellow" }
                    default { "White" }
                }
            )
            
            if ($result.Tests.Count -gt 0) {
                Write-Host "Tests:" -ForegroundColor White
                foreach ($testName in $result.Tests.Keys) {
                    $test = $result.Tests[$testName]
                    Write-Host "  • $testName`: $($test | ConvertTo-Json -Compress)" -ForegroundColor Gray
                }
            }
            
            if ($result.Details.Count -gt 0) {
                Write-Host "Details:" -ForegroundColor White
                foreach ($key in $result.Details.Keys) {
                    Write-Host "  • $key`: $($result.Details[$key])" -ForegroundColor Gray
                }
            }
            
            Write-Host ""
        }
    }
    
    return $systemHealthy
}

# Script execution
try {
    $success = main
    exit $(if ($success) { 0 } else { 1 })
}
catch {
    Write-HealthStatus "Fatal error during health check: $_" "FAIL"
    exit 2
}
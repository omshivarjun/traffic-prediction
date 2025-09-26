# PowerShell Service Restart Script for Traffic Prediction System
# Task 17.5: Service Restart & Recovery Scripts
# 
# This script provides intelligent service restart capabilities with dependency management,
# rolling restarts, and automated recovery procedures

param(
    [string]$Service = "",           # Specific service to restart (empty = all services)
    [switch]$Rolling,                # Perform rolling restart to maintain availability
    [switch]$Force,                  # Force restart even if service appears healthy
    [switch]$HealthCheck,            # Perform health check before and after restart
    [switch]$Dependencies,           # Also restart dependent services
    [int]$RestartDelay = 5,         # Seconds to wait between service restarts
    [int]$HealthTimeout = 120,      # Seconds to wait for service to become healthy
    [string]$RestartReason = "Manual restart"
)

# Set error handling
$ErrorActionPreference = "Continue"

# Script metadata
$ScriptVersion = "1.0.0"
$ScriptName = "Traffic Prediction System - Service Restart"

# Define service restart configuration with dependencies
$RestartConfig = @{
    "PostgreSQL" = @{
        DockerService = "postgres"
        ComposeFile = "docker-compose.yml"
        Port = 5433
        HealthCheck = @{
            Command = "docker exec postgres-traffic pg_isready -U postgres"
            Port = 5433
            MaxRetries = 15
            RetryDelay = 5
        }
        Dependencies = @()  # No dependencies
        Dependents = @("FastAPI Backend")  # Services that depend on this
        RestartType = "Docker"
        Priority = 1
        RestartTimeout = 60
        PreRestartChecks = @("database_backup_check")
    }
    "Zookeeper" = @{
        DockerService = "zookeeper"
        ComposeFile = "docker-compose.yml"
        Port = 2181
        HealthCheck = @{
            Command = "echo stat | nc localhost 2181"
            Port = 2181
            MaxRetries = 10
            RetryDelay = 3
        }
        Dependencies = @()
        Dependents = @("Kafka")
        RestartType = "Docker"
        Priority = 2
        RestartTimeout = 45
    }
    "Kafka" = @{
        DockerService = "kafka"
        ComposeFile = "docker-compose.yml"
        Port = 9092
        HealthCheck = @{
            Command = "docker exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092"
            Port = 9092
            MaxRetries = 15
            RetryDelay = 5
        }
        Dependencies = @("Zookeeper")
        Dependents = @("Schema Registry", "Kafka Connect")
        RestartType = "Docker"
        Priority = 3
        RestartTimeout = 60
        PreRestartChecks = @("kafka_topics_check")
    }
    "Schema Registry" = @{
        DockerService = "schema-registry"
        ComposeFile = "docker-compose.yml"
        Port = 8081
        HealthCheck = @{
            Command = "curl -f http://localhost:8081/subjects"
            Port = 8081
            MaxRetries = 10
            RetryDelay = 5
        }
        Dependencies = @("Kafka")
        Dependents = @()
        RestartType = "Docker"
        Priority = 4
        RestartTimeout = 30
    }
    "Kafka Connect" = @{
        DockerService = "kafka-connect"
        ComposeFile = "docker-compose.yml"
        Port = 8083
        HealthCheck = @{
            Command = "curl -f http://localhost:8083/connectors"
            Port = 8083
            MaxRetries = 10
            RetryDelay = 5
        }
        Dependencies = @("Kafka", "Schema Registry")
        Dependents = @()
        RestartType = "Docker"
        Priority = 5
        RestartTimeout = 45
        PostRestartActions = @("reconnect_hdfs_sink")
    }
    "HDFS NameNode" = @{
        DockerService = "namenode"
        ComposeFile = "docker-compose.yml"
        Port = 9871
        HealthCheck = @{
            Command = "curl -f http://localhost:9871/jmx"
            Port = 9871
            MaxRetries = 15
            RetryDelay = 10
        }
        Dependencies = @()
        Dependents = @("HDFS DataNode")
        RestartType = "Docker"
        Priority = 6
        RestartTimeout = 90
        PreRestartChecks = @("hdfs_safemode_check")
    }
    "HDFS DataNode" = @{
        DockerService = "datanode"
        ComposeFile = "docker-compose.yml"
        Port = 9865
        HealthCheck = @{
            Command = "curl -f http://localhost:9865/jmx"
            Port = 9865
            MaxRetries = 10
            RetryDelay = 5
        }
        Dependencies = @("HDFS NameNode")
        Dependents = @("YARN ResourceManager")
        RestartType = "Docker"
        Priority = 7
        RestartTimeout = 60
    }
    "YARN ResourceManager" = @{
        DockerService = "resourcemanager"
        ComposeFile = "docker-compose.yml"
        Port = 8089
        HealthCheck = @{
            Command = "curl -f http://localhost:8089/ws/v1/cluster/info"
            Port = 8089
            MaxRetries = 15
            RetryDelay = 10
        }
        Dependencies = @("HDFS NameNode", "HDFS DataNode")
        Dependents = @("YARN NodeManager")
        RestartType = "Docker"
        Priority = 8
        RestartTimeout = 90
    }
    "YARN NodeManager" = @{
        DockerService = "nodemanager"
        ComposeFile = "docker-compose.yml"
        Port = 8043
        HealthCheck = @{
            Command = "curl -f http://localhost:8043/ws/v1/node/info"
            Port = 8043
            MaxRetries = 10
            RetryDelay = 5
        }
        Dependencies = @("YARN ResourceManager")
        Dependents = @()
        RestartType = "Docker"
        Priority = 9
        RestartTimeout = 60
    }
    "FastAPI Backend" = @{
        ProcessBased = $true
        Port = 8000
        HealthCheck = @{
            Command = "curl -f http://localhost:8000/health"
            Port = 8000
            MaxRetries = 10
            RetryDelay = 5
        }
        Dependencies = @("PostgreSQL", "Kafka")
        Dependents = @("React Frontend")
        RestartType = "Process"
        Priority = 10
        RestartTimeout = 45
        StartCommand = "python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000"
        ProcessNames = @("python", "uvicorn")
    }
    "React Frontend" = @{
        ProcessBased = $true
        Port = 3000
        HealthCheck = @{
            Command = "curl -f http://localhost:3000"
            Port = 3000
            MaxRetries = 10
            RetryDelay = 5
        }
        Dependencies = @("FastAPI Backend")
        Dependents = @()
        RestartType = "Process"
        Priority = 11
        RestartTimeout = 60
        StartCommand = "npm run dev"
        ProcessNames = @("node", "next")
    }
}

# Global restart state
$RestartState = @{
    StartTime = Get-Date
    ServicesRestarted = @()
    ServicesFailed = @()
    TotalServices = 0
    RestartPlan = @()
    RollbackPlan = @()
}

function Write-Banner {
    param([string]$Message, [string]$Color = "Cyan")
    
    $border = "=" * 80
    Write-Host $border -ForegroundColor $Color
    Write-Host $Message -ForegroundColor $Color
    Write-Host $border -ForegroundColor $Color
    Write-Host ""
}

function Write-RestartLog {
    param([string]$Message, [string]$Level = "INFO", [string]$Service = "")
    
    $timestamp = Get-Date -Format "HH:mm:ss"
    $prefix = if ($Service) { "[$Service]" } else { "" }
    
    $color = switch ($Level) {
        "SUCCESS" { "Green" }
        "WARNING" { "Yellow" }
        "ERROR" { "Red" }
        "PROGRESS" { "Cyan" }
        default { "White" }
    }
    
    $icon = switch ($Level) {
        "SUCCESS" { "✅" }
        "WARNING" { "⚠️" }
        "ERROR" { "❌" }
        "PROGRESS" { "🔄" }
        default { "ℹ️" }
    }
    
    Write-Host "[$timestamp] $icon $prefix $Message" -ForegroundColor $color
}

function Test-ServiceHealth {
    param([string]$ServiceName, [hashtable]$Config, [int]$TimeoutSeconds = 60)
    
    $healthCheck = $Config.HealthCheck
    $maxRetries = $healthCheck.MaxRetries
    $retryDelay = $healthCheck.RetryDelay
    
    Write-RestartLog "Checking health of $ServiceName..." "PROGRESS" $ServiceName
    
    $attempt = 1
    $startTime = Get-Date
    
    while ($attempt -le $maxRetries) {
        $elapsed = ((Get-Date) - $startTime).TotalSeconds
        if ($elapsed -gt $TimeoutSeconds) {
            Write-RestartLog "Health check timeout after $TimeoutSeconds seconds" "ERROR" $ServiceName
            return $false
        }
        
        # Test port connectivity
        if ($healthCheck.Port) {
            $portTest = Test-NetConnection -ComputerName "localhost" -Port $healthCheck.Port -InformationLevel Quiet -WarningAction SilentlyContinue
            if ($portTest) {
                # Run health check command
                if ($healthCheck.Command) {
                    try {
                        $null = Invoke-Expression $healthCheck.Command 2>&1
                        if ($LASTEXITCODE -eq 0) {
                            Write-RestartLog "$ServiceName is healthy ✅" "SUCCESS" $ServiceName
                            return $true
                        }
                    }
                    catch {
                        # Command failed, continue retrying
                    }
                }
                else {
                    # Port test only
                    Write-RestartLog "$ServiceName is healthy ✅" "SUCCESS" $ServiceName
                    return $true
                }
            }
        }
        
        Start-Sleep -Seconds $retryDelay
        $attempt++
    }
    
    Write-RestartLog "$ServiceName health check failed after $maxRetries attempts" "ERROR" $ServiceName
    return $false
}

function Stop-ServiceSafely {
    param([string]$ServiceName, [hashtable]$Config)
    
    Write-RestartLog "Stopping $ServiceName..." "PROGRESS" $ServiceName
    
    if ($Config.ProcessBased) {
        # Stop process-based service
        $processNames = $Config.ProcessNames
        $stopped = $false
        
        foreach ($processName in $processNames) {
            $processes = Get-Process -Name $processName -ErrorAction SilentlyContinue
            if ($processes) {
                foreach ($process in $processes) {
                    try {
                        $process.CloseMainWindow()
                        Start-Sleep -Seconds 5
                        
                        if (-not $process.HasExited) {
                            $process.Kill()
                        }
                        
                        $stopped = $true
                        Write-RestartLog "Stopped $processName process (PID: $($process.Id))" "SUCCESS" $ServiceName
                    }
                    catch {
                        Write-RestartLog "Failed to stop $processName process: $_" "ERROR" $ServiceName
                    }
                }
            }
        }
        
        return $stopped
    }
    else {
        # Stop Docker service
        $dockerService = $Config.DockerService
        $composeFile = $Config.ComposeFile
        
        try {
            $stopCmd = if ($composeFile) {
                "docker-compose -f $composeFile stop $dockerService"
            } else {
                "docker-compose stop $dockerService"
            }
            
            Invoke-Expression $stopCmd
            
            if ($LASTEXITCODE -eq 0) {
                Write-RestartLog "$ServiceName stopped successfully" "SUCCESS" $ServiceName
                return $true
            }
            else {
                Write-RestartLog "$ServiceName failed to stop (Exit: $LASTEXITCODE)" "ERROR" $ServiceName
                return $false
            }
        }
        catch {
            Write-RestartLog "Error stopping $ServiceName : $_" "ERROR" $ServiceName
            return $false
        }
    }
}

function Start-ServiceSafely {
    param([string]$ServiceName, [hashtable]$Config)
    
    Write-RestartLog "Starting $ServiceName..." "PROGRESS" $ServiceName
    
    if ($Config.ProcessBased) {
        # Start process-based service
        $startCommand = $Config.StartCommand
        
        try {
            # Check if already running
            if ($Config.Port) {
                $portTest = Test-NetConnection -ComputerName "localhost" -Port $Config.Port -InformationLevel Quiet -WarningAction SilentlyContinue
                if ($portTest) {
                    Write-RestartLog "$ServiceName appears to already be running" "WARNING" $ServiceName
                    return $true
                }
            }
            
            # Start the process
            Start-Process -FilePath "cmd" -ArgumentList "/c", $startCommand -WindowStyle Hidden
            
            # Wait a moment for startup
            Start-Sleep -Seconds 10
            
            Write-RestartLog "$ServiceName startup initiated" "SUCCESS" $ServiceName
            return $true
        }
        catch {
            Write-RestartLog "Error starting $ServiceName : $_" "ERROR" $ServiceName
            return $false
        }
    }
    else {
        # Start Docker service
        $dockerService = $Config.DockerService
        $composeFile = $Config.ComposeFile
        
        try {
            $startCmd = if ($composeFile) {
                "docker-compose -f $composeFile up -d $dockerService"
            } else {
                "docker-compose up -d $dockerService"
            }
            
            Invoke-Expression $startCmd
            
            if ($LASTEXITCODE -eq 0) {
                Write-RestartLog "$ServiceName started successfully" "SUCCESS" $ServiceName
                return $true
            }
            else {
                Write-RestartLog "$ServiceName failed to start (Exit: $LASTEXITCODE)" "ERROR" $ServiceName
                return $false
            }
        }
        catch {
            Write-RestartLog "Error starting $ServiceName : $_" "ERROR" $ServiceName
            return $false
        }
    }
}

function Invoke-PreRestartChecks {
    param([string]$ServiceName, [hashtable]$Config)
    
    if (-not $Config.PreRestartChecks) {
        return $true
    }
    
    Write-RestartLog "Running pre-restart checks for $ServiceName..." "PROGRESS" $ServiceName
    
    foreach ($checkName in $Config.PreRestartChecks) {
        $checkPassed = $false
        
        switch ($checkName) {
            "database_backup_check" {
                # Verify database can be backed up
                try {
                    $null = docker exec postgres pg_dump -U traffic_user -t pg_stat_activity traffic_prediction --schema-only 2>&1
                    if ($LASTEXITCODE -eq 0) {
                        $checkPassed = $true
                        Write-RestartLog "Database backup check passed" "SUCCESS" $ServiceName
                    }
                }
                catch {
                    Write-RestartLog "Database backup check failed: $_" "ERROR" $ServiceName
                }
            }
            "kafka_topics_check" {
                # Verify Kafka topics exist
                try {
                    $topics = docker exec kafka kafka-topics --list --bootstrap-server localhost:9092 2>&1
                    if ($LASTEXITCODE -eq 0 -and $topics) {
                        $checkPassed = $true
                        Write-RestartLog "Kafka topics check passed" "SUCCESS" $ServiceName
                    }
                }
                catch {
                    Write-RestartLog "Kafka topics check failed: $_" "ERROR" $ServiceName
                }
            }
            "hdfs_safemode_check" {
                # Check HDFS is not in safe mode
                try {
                    $safeModeStatus = docker exec namenode hdfs dfsadmin -safemode get 2>&1
                    if ($safeModeStatus -like "*OFF*") {
                        $checkPassed = $true
                        Write-RestartLog "HDFS safe mode check passed" "SUCCESS" $ServiceName
                    }
                    else {
                        Write-RestartLog "HDFS is in safe mode - attempting to leave" "WARNING" $ServiceName
                        docker exec namenode hdfs dfsadmin -safemode leave 2>&1
                        Start-Sleep -Seconds 10
                        $checkPassed = $true
                    }
                }
                catch {
                    Write-RestartLog "HDFS safe mode check failed: $_" "ERROR" $ServiceName
                }
            }
        }
        
        if (-not $checkPassed -and -not $Force) {
            Write-RestartLog "Pre-restart check '$checkName' failed - aborting restart (use -Force to override)" "ERROR" $ServiceName
            return $false
        }
    }
    
    return $true
}

function Invoke-PostRestartActions {
    param([string]$ServiceName, [hashtable]$Config)
    
    if (-not $Config.PostRestartActions) {
        return $true
    }
    
    Write-RestartLog "Running post-restart actions for $ServiceName..." "PROGRESS" $ServiceName
    
    foreach ($actionName in $Config.PostRestartActions) {
        switch ($actionName) {
            "reconnect_hdfs_sink" {
                # Reconnect HDFS sink connector
                try {
                    Start-Sleep -Seconds 15  # Wait for Kafka Connect to be ready
                    
                    # Check if connector exists and restart it
                    $response = Invoke-WebRequest -Uri "http://localhost:8083/connectors/hdfs-sink/status" -Method GET -UseBasicParsing -ErrorAction SilentlyContinue
                    if ($response -and $response.StatusCode -eq 200) {
                        $null = Invoke-WebRequest -Uri "http://localhost:8083/connectors/hdfs-sink/restart" -Method POST -UseBasicParsing -ErrorAction SilentlyContinue
                        Write-RestartLog "HDFS sink connector restarted" "SUCCESS" $ServiceName
                    }
                    else {
                        Write-RestartLog "HDFS sink connector not found - may need manual configuration" "WARNING" $ServiceName
                    }
                }
                catch {
                    Write-RestartLog "Failed to restart HDFS sink connector: $_" "WARNING" $ServiceName
                }
            }
        }
    }
    
    return $true
}

function Get-RestartOrder {
    param([string[]]$ServiceNames)
    
    # Get services sorted by priority
    $orderedServices = @()
    
    foreach ($serviceName in $ServiceNames) {
        if ($RestartConfig.ContainsKey($serviceName)) {
            $config = $RestartConfig[$serviceName]
            $orderedServices += @{
                Name = $serviceName
                Priority = $config.Priority
                Config = $config
            }
        }
    }
    
    return $orderedServices | Sort-Object Priority
}

function Get-ServiceDependents {
    param([string]$ServiceName)
    
    $dependents = @()
    
    foreach ($checkServiceName in $RestartConfig.Keys) {
        $config = $RestartConfig[$checkServiceName]
        if ($config.Dependencies -contains $ServiceName) {
            $dependents += $checkServiceName
        }
    }
    
    return $dependents
}

function Restart-Service {
    param([string]$ServiceName, [hashtable]$Config)
    
    Write-RestartLog "🔄 Restarting $ServiceName..." "PROGRESS" $ServiceName
    
    # Pre-restart health check
    if ($HealthCheck) {
        $initialHealth = Test-ServiceHealth -ServiceName $ServiceName -Config $Config -TimeoutSeconds 30
        if ($initialHealth -and -not $Force) {
            Write-RestartLog "$ServiceName is already healthy - skipping restart (use -Force to restart anyway)" "SUCCESS" $ServiceName
            return $true
        }
    }
    
    # Pre-restart checks
    if (-not (Invoke-PreRestartChecks -ServiceName $ServiceName -Config $Config)) {
        return $false
    }
    
    # Stop service
    $stopped = Stop-ServiceSafely -ServiceName $ServiceName -Config $Config
    if (-not $stopped -and -not $Force) {
        Write-RestartLog "Failed to stop $ServiceName - aborting restart" "ERROR" $ServiceName
        return $false
    }
    
    # Wait for graceful shutdown
    Start-Sleep -Seconds $RestartDelay
    
    # Start service
    $started = Start-ServiceSafely -ServiceName $ServiceName -Config $Config
    if (-not $started) {
        Write-RestartLog "Failed to start $ServiceName" "ERROR" $ServiceName
        return $false
    }
    
    # Wait for service initialization
    Start-Sleep -Seconds 15
    
    # Post-restart health check
    if ($HealthCheck) {
        $healthy = Test-ServiceHealth -ServiceName $ServiceName -Config $Config -TimeoutSeconds $HealthTimeout
        if (-not $healthy) {
            Write-RestartLog "$ServiceName failed post-restart health check" "ERROR" $ServiceName
            return $false
        }
    }
    
    # Post-restart actions
    Invoke-PostRestartActions -ServiceName $ServiceName -Config $Config
    
    Write-RestartLog "$ServiceName restarted successfully ✅" "SUCCESS" $ServiceName
    return $true
}

function Show-RestartPlan {
    param([string[]]$ServiceNames)
    
    Write-RestartLog "📋 Restart Plan:" "INFO"
    
    $orderedServices = Get-RestartOrder -ServiceNames $ServiceNames
    
    foreach ($serviceInfo in $orderedServices) {
        $serviceName = $serviceInfo.Name
        $config = $serviceInfo.Config
        
        $dependencyList = if ($config.Dependencies.Count -gt 0) { 
            "Dependencies: " + ($config.Dependencies -join ", ") 
        } else { 
            "No dependencies" 
        }
        
        Write-Host "   $($serviceInfo.Priority). $serviceName ($dependencyList)" -ForegroundColor White
    }
    
    Write-Host ""
}

function Show-RestartSummary {
    $endTime = Get-Date
    $duration = $endTime - $RestartState.StartTime
    
    Write-Banner "🎯 RESTART SUMMARY" "Green"
    
    Write-Host "Duration: $($duration.TotalMinutes.ToString('F1')) minutes" -ForegroundColor Cyan
    Write-Host "Services Processed: $($RestartState.TotalServices)" -ForegroundColor Cyan
    Write-Host "Successfully Restarted: $($RestartState.ServicesRestarted.Count)" -ForegroundColor Green
    Write-Host "Failed: $($RestartState.ServicesFailed.Count)" -ForegroundColor $(if ($RestartState.ServicesFailed.Count -gt 0) { "Red" } else { "Green" })
    
    if ($RestartState.ServicesRestarted.Count -gt 0) {
        Write-Host "`n✅ Successfully Restarted:" -ForegroundColor Green
        foreach ($service in $RestartState.ServicesRestarted) {
            Write-Host "   • $service" -ForegroundColor Green
        }
    }
    
    if ($RestartState.ServicesFailed.Count -gt 0) {
        Write-Host "`n❌ Failed Restarts:" -ForegroundColor Red
        foreach ($service in $RestartState.ServicesFailed) {
            Write-Host "   • $service" -ForegroundColor Red
        }
        
        Write-Host "`n🔧 Troubleshooting:" -ForegroundColor Yellow
        Write-Host "   • Run: .\health-check.ps1 to diagnose issues" -ForegroundColor Yellow
        Write-Host "   • Run: .\troubleshoot.ps1 for automated fixes" -ForegroundColor Yellow
        Write-Host "   • Check logs: docker-compose logs [service-name]" -ForegroundColor Yellow
    }
    
    $overallSuccess = $RestartState.ServicesFailed.Count -eq 0
    $status = if ($overallSuccess) { "SUCCESS" } else { "PARTIAL" }
    $statusColor = if ($overallSuccess) { "Green" } else { "Yellow" }
    
    Write-Host "`n🎯 Overall Status: $status" -ForegroundColor $statusColor
    
    return $overallSuccess
}

function main {
    Write-Banner "$ScriptName v$ScriptVersion" "Green"
    
    Write-Host "Configuration:" -ForegroundColor Cyan
    Write-Host "  Target Service: $(if ($Service) { $Service } else { 'All Services' })" -ForegroundColor White
    Write-Host "  Rolling Restart: $Rolling" -ForegroundColor White
    Write-Host "  Force Restart: $Force" -ForegroundColor White
    Write-Host "  Health Check: $HealthCheck" -ForegroundColor White
    Write-Host "  Include Dependencies: $Dependencies" -ForegroundColor White
    Write-Host "  Restart Delay: $RestartDelay seconds" -ForegroundColor White
    Write-Host "  Health Timeout: $HealthTimeout seconds" -ForegroundColor White
    Write-Host "  Reason: $RestartReason" -ForegroundColor White
    Write-Host ""
    
    # Determine services to restart
    $servicesToRestart = @()
    
    if ($Service) {
        if (-not $RestartConfig.ContainsKey($Service)) {
            Write-RestartLog "Service '$Service' not found in configuration" "ERROR"
            return $false
        }
        
        $servicesToRestart += $Service
        
        # Add dependents if requested
        if ($Dependencies) {
            $dependents = Get-ServiceDependents -ServiceName $Service
            $servicesToRestart += $dependents
            
            if ($dependents.Count -gt 0) {
                Write-RestartLog "Including dependent services: $($dependents -join ', ')" "INFO"
            }
        }
    }
    else {
        # Restart all services
        $servicesToRestart = $RestartConfig.Keys
    }
    
    $RestartState.TotalServices = $servicesToRestart.Count
    
    # Show restart plan
    Show-RestartPlan -ServiceNames $servicesToRestart
    
    # Get restart order
    $orderedServices = Get-RestartOrder -ServiceNames $servicesToRestart
    
    Write-RestartLog "🚀 Starting restart procedure for $($RestartState.TotalServices) services..." "INFO"
    
    # Execute restarts
    foreach ($serviceInfo in $orderedServices) {
        $serviceName = $serviceInfo.Name
        $config = $serviceInfo.Config
        
        try {
            $success = Restart-Service -ServiceName $serviceName -Config $config
            
            if ($success) {
                $RestartState.ServicesRestarted += $serviceName
            }
            else {
                $RestartState.ServicesFailed += $serviceName
                
                if (-not $Force) {
                    Write-RestartLog "Stopping restart procedure due to failure (use -Force to continue)" "ERROR"
                    break
                }
            }
            
            # Rolling restart delay
            if ($Rolling -and $serviceInfo -ne $orderedServices[-1]) {
                Write-RestartLog "Rolling restart delay..." "PROGRESS"
                Start-Sleep -Seconds ($RestartDelay * 2)
            }
        }
        catch {
            Write-RestartLog "Unexpected error restarting $serviceName : $_" "ERROR"
            $RestartState.ServicesFailed += $serviceName
        }
    }
    
    # Show summary
    $success = Show-RestartSummary
    
    if ($success) {
        Write-RestartLog "🎉 Service restart completed successfully!" "SUCCESS"
    }
    else {
        Write-RestartLog "⚠️ Service restart completed with issues" "WARNING"
    }
    
    return $success
}

# Script execution
try {
    $success = main
    exit $(if ($success) { 0 } else { 1 })
}
catch {
    Write-RestartLog "Fatal error during restart: $_" "ERROR"
    exit 1
}
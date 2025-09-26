# PowerShell Master Startup Script for Traffic Prediction System
# Task 17.1: Service Startup & Management Scripts - Master Start Script
# 
# This script starts all system services in the correct dependency order:
# PostgreSQL → Zookeeper → Kafka → Schema Registry → Hadoop → YARN → Spark → API → Frontend

param(
    [switch]$SkipHealthChecks,
    [switch]$Verbose,
    [switch]$Force,
    [int]$TimeoutSeconds = 300,
    [string]$StartupProfile = "full"  # Options: full, minimal, development
)

# Set error handling
$ErrorActionPreference = "Continue"
$VerbosePreference = if ($Verbose) { "Continue" } else { "SilentlyContinue" }

# Script metadata
$ScriptVersion = "1.0.0"
$ScriptName = "Traffic Prediction System - Master Startup"

# Define service startup order and configurations
$ServiceGroups = @{
    "Infrastructure" = @{
        Order = 1
        Services = @(
            @{
                Name = "PostgreSQL"
                DockerService = "postgres"
                ComposeFile = "docker-compose.yml"
                HealthCheck = @{
                    Port = 5433
                    Command = "docker exec postgres-traffic pg_isready -U postgres -d traffic_db"
                    MaxRetries = 15
                    RetryDelay = 5
                }
                WaitTime = 10
            }
        )
    }
    "MessageBroker" = @{
        Order = 2
        Services = @(
            @{
                Name = "Zookeeper"
                DockerService = "zookeeper"
                ComposeFile = "docker-compose.yml"
                HealthCheck = @{
                    Port = 2185
                    Command = "docker exec zookeeper zkServer.sh status"
                    MaxRetries = 10
                    RetryDelay = 3
                }
                WaitTime = 15
            },
            @{
                Name = "Kafka"
                DockerService = "kafka-broker1"
                ComposeFile = "docker-compose.yml"
                HealthCheck = @{
                    Port = 9094
                    Command = "docker exec kafka-broker1 kafka-broker-api-versions --bootstrap-server localhost:9092"
                    MaxRetries = 15
                    RetryDelay = 5
                }
                WaitTime = 20
                DependsOn = @("Zookeeper")
            }
        )
    }
    "KafkaEcosystem" = @{
        Order = 3
        Services = @(
            @{
                Name = "Schema Registry"
                DockerService = "schema-registry"
                ComposeFile = "docker-compose.yml"
                HealthCheck = @{
                    Port = 8082
                    Command = "curl -f http://localhost:8082/subjects"
                    MaxRetries = 10
                    RetryDelay = 5
                }
                WaitTime = 10
                DependsOn = @("Kafka")
            },
            @{
                Name = "Kafka Connect"
                DockerService = "kafka-connect"
                ComposeFile = "docker-compose.yml"
                HealthCheck = @{
                    Port = 8084
                    Command = "curl -f http://localhost:8084/connectors"
                    MaxRetries = 10
                    RetryDelay = 5
                }
                WaitTime = 15
                DependsOn = @("Schema Registry")
            }
        )
    }
    "BigData" = @{
        Order = 4
        Services = @(
            @{
                Name = "HDFS NameNode"
                DockerService = "namenode"
                ComposeFile = "docker-compose.yml"
                HealthCheck = @{
                    Port = 9871
                    Command = "curl -f http://localhost:9871/jmx"
                    MaxRetries = 15
                    RetryDelay = 10
                }
                WaitTime = 30
            },
            @{
                Name = "HDFS DataNode"
                DockerService = "datanode"
                ComposeFile = "docker-compose.yml"
                HealthCheck = @{
                    Port = 9865
                    Command = "curl -f http://localhost:9865/jmx"
                    MaxRetries = 10
                    RetryDelay = 5
                }
                WaitTime = 20
                DependsOn = @("HDFS NameNode")
            }
        )
    }
    "ComputeEngine" = @{
        Order = 5
        Services = @(
            @{
                Name = "YARN ResourceManager"
                DockerService = "resourcemanager"
                ComposeFile = "docker-compose.yml"
                HealthCheck = @{
                    Port = 8089
                    Command = "curl -f http://localhost:8089/ws/v1/cluster/info"
                    MaxRetries = 15
                    RetryDelay = 10
                }
                WaitTime = 25
                DependsOn = @("HDFS NameNode", "HDFS DataNode")
            },
            @{
                Name = "YARN NodeManager"
                DockerService = "nodemanager"
                ComposeFile = "docker-compose.yml"
                HealthCheck = @{
                    Port = 8043
                    Command = "curl -f http://localhost:8043/ws/v1/node/info"
                    MaxRetries = 10
                    RetryDelay = 5
                }
                WaitTime = 15
                DependsOn = @("YARN ResourceManager")
            }
        )
    }
    "Application" = @{
        Order = 6
        Services = @(
            @{
                Name = "FastAPI Backend"
                DockerService = "fastapi"
                ComposeFile = "docker-compose.yml"
                HealthCheck = @{
                    Port = 8000
                    Command = "curl -f http://localhost:8000/health"
                    MaxRetries = 10
                    RetryDelay = 5
                }
                WaitTime = 15
                StartCommand = "python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000"
                ProcessBased = $true
            },
            @{
                Name = "React Frontend"
                DockerService = "frontend"
                ComposeFile = "docker-compose.yml"
                HealthCheck = @{
                    Port = 3000
                    Command = "curl -f http://localhost:3000"
                    MaxRetries = 10
                    RetryDelay = 5
                }
                WaitTime = 20
                StartCommand = "npm run dev"
                ProcessBased = $true
                DependsOn = @("FastAPI Backend")
            }
        )
    }
}

# Profile configurations
$StartupProfiles = @{
    "minimal" = @("Infrastructure", "MessageBroker")
    "development" = @("Infrastructure", "MessageBroker", "KafkaEcosystem", "Application")
    "full" = @("Infrastructure", "MessageBroker", "KafkaEcosystem", "BigData", "ComputeEngine", "Application")
}

# Global state tracking
$StartupStatus = @{
    StartTime = Get-Date
    ServicesStarted = @()
    ServicesFailed = @()
    CurrentPhase = ""
    TotalServices = 0
    CompletedServices = 0
}

function Write-Banner {
    param([string]$Message, [string]$Color = "Cyan")

    $border = "=" * 80
    Write-Host $border -ForegroundColor $Color
    Write-Host $Message -ForegroundColor $Color
    Write-Host $border -ForegroundColor $Color
    Write-Host ""
}

function Write-Progress {
    param([string]$Message, [string]$Color = "Green")
    
    $timestamp = Get-Date -Format "HH:mm:ss"
    Write-Host "[$timestamp] $Message" -ForegroundColor $Color
}

function Test-Port {
    param([int]$Port, [string]$ServiceName)
    
    try {
        $connection = Test-NetConnection -ComputerName "localhost" -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue
        return $connection
    }
    catch {
        Write-Verbose "Port test failed for $ServiceName on port $Port : $_"
        return $false
    }
}

function Test-DockerRunning {
    try {
        docker info | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

function Wait-ForService {
    param(
        [hashtable]$Service,
        [int]$TimeoutSeconds = 120
    )
    
    $serviceName = $Service.Name
    $healthCheck = $Service.HealthCheck
    $maxRetries = $healthCheck.MaxRetries
    $retryDelay = $healthCheck.RetryDelay
    
    Write-Progress "Waiting for $serviceName to become healthy..."
    
    $attempt = 1
    $startTime = Get-Date
    
    while ($attempt -le $maxRetries) {
        $elapsed = ((Get-Date) - $startTime).TotalSeconds
        if ($elapsed -gt $TimeoutSeconds) {
            Write-Progress "Timeout waiting for $serviceName after $TimeoutSeconds seconds" "Red"
            return $false
        }
        
        # Test port first
        if ($healthCheck.Port) {
            if (Test-Port -Port $healthCheck.Port -ServiceName $serviceName) {
                Write-Verbose "Port $($healthCheck.Port) is accessible for $serviceName"
                
                # Run health check command
                if ($healthCheck.Command) {
                    try {
                        # Ensure Windows PowerShell uses curl.exe, not the alias to Invoke-WebRequest
                        $commandToRun = $healthCheck.Command -replace "\bcurl\b","curl.exe"
                        $result = Invoke-Expression $commandToRun 2>&1
                        if ($LASTEXITCODE -eq 0) {
                            Write-Progress "$serviceName is healthy!" "Green"
                            return $true
                        }
                        else {
                            Write-Verbose "Health check failed for $serviceName (attempt $attempt/$maxRetries): $result"
                        }
                    }
                    catch {
                        Write-Verbose "Health check command failed for $serviceName : $_"
                    }
                }
                else {
                    # Port test only
                    Write-Progress "$serviceName is healthy!" "Green"
                    return $true
                }
            }
            else {
                Write-Verbose "Port $($healthCheck.Port) not accessible for $serviceName (attempt $attempt/$maxRetries)"
            }
        }
        
        Start-Sleep -Seconds $retryDelay
        $attempt++
    }
    
    Write-Progress "Health check failed for $serviceName after $maxRetries attempts" "Red"
    return $false
}

function Start-DockerService {
    param(
        [hashtable]$Service
    )
    
    $serviceName = $Service.Name
    $dockerService = $Service.DockerService
    $composeFile = $Service.ComposeFile
    
    Write-Progress "Starting Docker service: $serviceName ($dockerService)"
    
    try {
        if ($composeFile) {
            $composeCmd = "docker compose -f $composeFile up -d $dockerService"
            Write-Verbose "Executing: $composeCmd"
            Invoke-Expression $composeCmd
        }
        else {
            $dockerCmd = "docker compose up -d $dockerService"
            Write-Verbose "Executing: $dockerCmd"
            Invoke-Expression $dockerCmd
        }
        
        if ($LASTEXITCODE -eq 0) {
            Write-Progress "Docker service $serviceName started successfully" "Green"
            
            # Wait for the service to initialize
            if ($Service.WaitTime) {
                Write-Progress "Waiting $($Service.WaitTime) seconds for $serviceName to initialize..."
                Start-Sleep -Seconds $Service.WaitTime
            }
            
            return $true
        }
        else {
            Write-Progress "Failed to start Docker service $serviceName" "Red"
            return $false
        }
    }
    catch {
        Write-Progress "Exception starting Docker service $serviceName : $_" "Red"
        return $false
    }
}

function Start-ProcessService {
    param(
        [hashtable]$Service
    )
    
    $serviceName = $Service.Name
    $startCommand = $Service.StartCommand
    
    Write-Progress "Starting process-based service: $serviceName"
    
    try {
        # Check if already running by testing port
        if ($Service.HealthCheck.Port -and (Test-Port -Port $Service.HealthCheck.Port -ServiceName $serviceName)) {
            Write-Progress "$serviceName appears to already be running" "Yellow"
            return $true
        }
        
        # Start the process in background
        Write-Verbose "Executing: $startCommand"
        Start-Process -FilePath "cmd" -ArgumentList "/c", $startCommand -WindowStyle Hidden
        
        # Wait for initialization
        if ($Service.WaitTime) {
            Write-Progress "Waiting $($Service.WaitTime) seconds for $serviceName to initialize..."
            Start-Sleep -Seconds $Service.WaitTime
        }
        
        return $true
    }
    catch {
        Write-Progress "Exception starting process service $serviceName : $_" "Red"
        return $false
    }
}

function Start-ServiceGroup {
    param(
        [hashtable]$Group,
        [string]$GroupName
    )
    
    Write-Progress "Starting $GroupName services..." "Cyan"
    $StartupStatus.CurrentPhase = $GroupName
    
    $groupSuccess = $true
    
    foreach ($service in $Group.Services) {
        $serviceName = $service.Name
        Write-Progress "Starting $serviceName..."
        
        # Check dependencies
        if ($service.DependsOn) {
            foreach ($dependency in $service.DependsOn) {
                if ($dependency -notin $StartupStatus.ServicesStarted) {
                    Write-Progress "Dependency not met: $dependency required for $serviceName" "Red"
                    $StartupStatus.ServicesFailed += $serviceName
                    $groupSuccess = $false
                    continue
                }
            }
        }
        
        # Start the service
        $started = $false
        
        if ($service.ProcessBased) {
            $started = Start-ProcessService -Service $service
        }
        else {
            $started = Start-DockerService -Service $service
        }
        
        if ($started) {
            # Health check
            if (-not $SkipHealthChecks) {
                $healthy = Wait-ForService -Service $service -TimeoutSeconds $TimeoutSeconds
                if ($healthy) {
                    $StartupStatus.ServicesStarted += $serviceName
                    $StartupStatus.CompletedServices++
                    Write-Progress "$serviceName started successfully" "Green"
                }
                else {
                    $StartupStatus.ServicesFailed += $serviceName
                    $groupSuccess = $false
                    Write-Progress "$serviceName failed health check" "Red"
                    
                    if (-not $Force) {
                        Write-Progress "Stopping startup due to failed service (use -Force to continue)" "Red"
                        return $false
                    }
                }
            }
            else {
                $StartupStatus.ServicesStarted += $serviceName
                $StartupStatus.CompletedServices++
                Write-Progress "$serviceName started (health checks skipped)" "Yellow"
            }
        }
        else {
            $StartupStatus.ServicesFailed += $serviceName
            $groupSuccess = $false
            Write-Progress "$serviceName failed to start" "Red"
            
            if (-not $Force) {
                Write-Progress "Stopping startup due to failed service (use -Force to continue)" "Red"
                return $false
            }
        }
        
        # Brief pause between services
        Start-Sleep -Seconds 2
    }
    
    if ($groupSuccess) {
        Write-Progress "$GroupName services started successfully" "Green"
    }
    else {
        Write-Progress "$GroupName services completed with some failures" "Yellow"
    }
    
    Write-Host ""
    return $groupSuccess
}

function Show-StartupSummary {
    $endTime = Get-Date
    $duration = $endTime - $StartupStatus.StartTime
    
    Write-Banner "STARTUP SUMMARY" "Green"
    
    Write-Host "Profile: $StartupProfile" -ForegroundColor Cyan
    Write-Host "Duration: $($duration.TotalMinutes.ToString('F1')) minutes" -ForegroundColor Cyan
    Write-Host "Total Services: $($StartupStatus.TotalServices)" -ForegroundColor Cyan
    Write-Host "Started Successfully: $($StartupStatus.ServicesStarted.Count)" -ForegroundColor Green
    Write-Host "Failed: $($StartupStatus.ServicesFailed.Count)" -ForegroundColor $(if ($StartupStatus.ServicesFailed.Count -gt 0) { "Red" } else { "Green" })
    
    if ($StartupStatus.ServicesStarted.Count -gt 0) {
        Write-Host "`nSuccessfully Started Services:" -ForegroundColor Green
        foreach ($service in $StartupStatus.ServicesStarted) {
            Write-Host "   - $service" -ForegroundColor Green
        }
    }
    
    if ($StartupStatus.ServicesFailed.Count -gt 0) {
        Write-Host "`nFailed Services:" -ForegroundColor Red
        foreach ($service in $StartupStatus.ServicesFailed) {
            Write-Host "   - $service" -ForegroundColor Red
        }
        
        Write-Host "`nTroubleshooting:" -ForegroundColor Yellow
        Write-Host "   • Run: .\health-check.ps1 to diagnose issues" -ForegroundColor Yellow
        Write-Host "   • Run: .\troubleshoot.ps1 for automated fixes" -ForegroundColor Yellow
        Write-Host "   • Check logs: docker compose logs [service-name]" -ForegroundColor Yellow
    }
    
    # Overall status
    $overallSuccess = $StartupStatus.ServicesFailed.Count -eq 0
    $status = if ($overallSuccess) { "SUCCESS" } else { "PARTIAL" }
    $statusColor = if ($overallSuccess) { "Green" } else { "Yellow" }
    
    Write-Host "`nOverall Status: $status" -ForegroundColor $statusColor
    
    if ($overallSuccess) {
        Write-Host "`nAll services are running! Access points:" -ForegroundColor Green
        Write-Host "   - Frontend Dashboard: http://localhost:3000" -ForegroundColor Cyan
        Write-Host "   - API Documentation: http://localhost:8000/docs" -ForegroundColor Cyan
        Write-Host "   - HDFS Web UI: http://localhost:9871" -ForegroundColor Cyan
        Write-Host "   - YARN Resource Manager: http://localhost:8089" -ForegroundColor Cyan
        Write-Host "   - Kafka UI: http://localhost:8085" -ForegroundColor Cyan
    }
    
    Write-Host ""
    return $overallSuccess
}

function main {
    Write-Banner "$ScriptName v$ScriptVersion" "Green"
    
    Write-Host "Configuration:" -ForegroundColor Cyan
    Write-Host "  Profile: $StartupProfile" -ForegroundColor White
    Write-Host "  Skip Health Checks: $SkipHealthChecks" -ForegroundColor White
    Write-Host "  Force Continue: $Force" -ForegroundColor White
    Write-Host "  Timeout: $TimeoutSeconds seconds" -ForegroundColor White
    Write-Host ""
    
    # Validate profile
    if ($StartupProfile -notin $StartupProfiles.Keys) {
        Write-Progress "Invalid profile '$StartupProfile'. Available profiles: $($StartupProfiles.Keys -join ', ')" "Red"
        return $false
    }
    
    # Pre-flight checks
    Write-Progress "Running pre-flight checks..."
    
    if (-not (Test-DockerRunning)) {
        Write-Progress "Docker is not running. Please start Docker Desktop and try again." "Red"
        return $false
    }
    Write-Progress "Docker is running" "Green"
    
    # Check for required files
    $requiredFiles = @("docker-compose.yml")
    foreach ($file in $requiredFiles) {
        if (-not (Test-Path $file)) {
            Write-Progress "Required file missing: $file" "Red"
            return $false
        }
    }
    Write-Progress "Required files present" "Green"
    
    Write-Host ""
    
    # Calculate total services for progress tracking
    $profileGroups = $StartupProfiles[$StartupProfile]
    foreach ($groupName in $profileGroups) {
        $group = $ServiceGroups[$groupName]
        $StartupStatus.TotalServices += $group.Services.Count
    }
    
    Write-Progress "Starting $($StartupStatus.TotalServices) services in $StartupProfile profile..."
    Write-Host ""
    
    # Start service groups in order
    $sortedGroups = $ServiceGroups.GetEnumerator() | Where-Object { $_.Key -in $profileGroups } | Sort-Object { $_.Value.Order }
    
    foreach ($groupEntry in $sortedGroups) {
        $groupName = $groupEntry.Key
        $group = $groupEntry.Value
        
        $groupSuccess = Start-ServiceGroup -Group $group -GroupName $groupName
        if (-not $groupSuccess -and -not $Force) {
            break
        }
    }
    
    # Show summary
    $success = Show-StartupSummary
    
    if ($success) {
        Write-Progress "Traffic Prediction System startup completed successfully!" "Green"
        return $true
    }
    else {
        Write-Progress "Traffic Prediction System startup completed with issues" "Yellow"
        return $false
    }
}

# Script execution
try {
    $success = main
    exit $(if ($success) { 0 } else { 1 })
}
catch {
    $errMsg = "Fatal error during startup: " + $_
    Write-Progress $errMsg "Red"
    exit 1
}
# PowerShell Master Stop Script for Traffic Prediction System
# Task 17.3: Service Stop & Cleanup Scripts
# 
# This script stops all system services in reverse dependency order:
# Frontend → API → Spark → YARN → Hadoop → Kafka Connect → Schema Registry → Kafka → Zookeeper → PostgreSQL

param(
    [switch]$Force,
    [switch]$Verbose,
    [switch]$SkipCleanup,
    [switch]$PreserveLogs,
    [int]$TimeoutSeconds = 60,
    [string]$Service = ""  # Stop specific service and its dependencies
)

# Set error handling
$ErrorActionPreference = "Continue"
$VerbosePreference = if ($Verbose) { "Continue" } else { "SilentlyContinue" }

# Script metadata
$ScriptVersion = "1.0.0"
$ScriptName = "Traffic Prediction System - Master Stop"

# Define service shutdown order (reverse of startup)
$ShutdownGroups = @{
    "Application" = @{
        Order = 1
        Services = @(
            @{
                Name = "React Frontend"
                DockerService = "frontend"
                ComposeFile = "docker-compose.yml"
                ProcessBased = $true
                ProcessNames = @("node", "next")
                Port = 3000
                GracefulShutdown = $true
                StopTimeout = 15
            },
            @{
                Name = "FastAPI Backend"
                DockerService = "fastapi" 
                ComposeFile = "docker-compose.yml"
                ProcessBased = $true
                ProcessNames = @("python", "uvicorn")
                Port = 8000
                GracefulShutdown = $true
                StopTimeout = 30
            }
        )
    }
    "ComputeEngine" = @{
        Order = 2
        Services = @(
            @{
                Name = "YARN NodeManager"
                DockerService = "nodemanager"
                ComposeFile = "docker-compose.yml"
                Port = 8043
                GracefulShutdown = $true
                StopTimeout = 45
                CleanupPaths = @("logs/yarn/nodemanager")
            },
            @{
                Name = "YARN ResourceManager"
                DockerService = "resourcemanager"
                ComposeFile = "docker-compose.yml"
                Port = 8089
                GracefulShutdown = $true
                StopTimeout = 60
                CleanupPaths = @("logs/yarn/resourcemanager")
            }
        )
    }
    "BigData" = @{
        Order = 3
        Services = @(
            @{
                Name = "HDFS DataNode"
                DockerService = "datanode"
                ComposeFile = "docker-compose.yml"
                Port = 9865
                GracefulShutdown = $true
                StopTimeout = 30
                CleanupPaths = @("logs/hadoop/datanode")
            },
            @{
                Name = "HDFS NameNode"
                DockerService = "namenode"
                ComposeFile = "docker-compose.yml"
                Port = 9871
                GracefulShutdown = $true
                StopTimeout = 45
                CleanupPaths = @("logs/hadoop/namenode")
                PreStopCommand = "docker exec namenode hdfs dfsadmin -safemode enter"
            }
        )
    }
    "KafkaEcosystem" = @{
        Order = 4
        Services = @(
            @{
                Name = "Kafka Connect"
                DockerService = "kafka-connect"
                ComposeFile = "docker-compose.yml"
                Port = 8083
                GracefulShutdown = $true
                StopTimeout = 30
                PreStopCommand = "curl -X DELETE http://localhost:8083/connectors/hdfs-sink"
            },
            @{
                Name = "Schema Registry"
                DockerService = "schema-registry"
                ComposeFile = "docker-compose.yml"
                Port = 8081
                GracefulShutdown = $true
                StopTimeout = 20
            }
        )
    }
    "MessageBroker" = @{
        Order = 5
        Services = @(
            @{
                Name = "Kafka"
                DockerService = "kafka"
                ComposeFile = "docker-compose.yml"
                Port = 9092
                GracefulShutdown = $true
                StopTimeout = 45
                CleanupPaths = @("logs/kafka")
                PreStopCommand = "docker exec kafka kafka-server-stop"
            },
            @{
                Name = "Zookeeper"
                DockerService = "zookeeper"
                ComposeFile = "docker-compose.yml"
                Port = 2181
                GracefulShutdown = $true
                StopTimeout = 30
                CleanupPaths = @("logs/zookeeper")
                PreStopCommand = "docker exec zookeeper zkServer.sh stop"
            }
        )
    }
    "Infrastructure" = @{
        Order = 6
        Services = @(
            @{
                Name = "PostgreSQL"
                DockerService = "postgres"
                ComposeFile = "docker-compose.yml"
                Port = 5433
                GracefulShutdown = $true
                StopTimeout = 30
                CleanupPaths = @("logs/postgres")
                PreStopCommand = "docker exec postgres pg_ctl stop -D /var/lib/postgresql/data -m smart"
            }
        )
    }
}

# Global shutdown status
$ShutdownStatus = @{
    StartTime = Get-Date
    ServicesStopped = @()
    ServicesFailed = @()
    CurrentPhase = ""
    TotalServices = 0
    CompletedServices = 0
    CleanupErrors = @()
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

function Stop-ProcessService {
    param(
        [hashtable]$Service
    )
    
    $serviceName = $Service.Name
    $processNames = $Service.ProcessNames
    $graceful = $Service.GracefulShutdown
    $timeout = $Service.StopTimeout
    
    Write-Progress "Stopping process-based service: $serviceName"
    
    if (-not $processNames) {
        Write-Progress "No process names defined for $serviceName, skipping" "Yellow"
        return $true
    }
    
    $stoppedAny = $false
    
    foreach ($processName in $processNames) {
        $processes = Get-Process -Name $processName -ErrorAction SilentlyContinue
        
        if ($processes) {
            Write-Progress "Found $($processes.Count) $processName processes for $serviceName"
            
            foreach ($process in $processes) {
                try {
                    if ($graceful -and -not $Force) {
                        Write-Verbose "Attempting graceful shutdown of process $($process.Id)"
                        $process.CloseMainWindow()
                        
                        # Wait for graceful shutdown
                        $waited = 0
                        while (-not $process.HasExited -and $waited -lt $timeout) {
                            Start-Sleep -Seconds 2
                            $waited += 2
                            Write-Verbose "Waiting for graceful shutdown... ($waited/$timeout seconds)"
                        }
                        
                        if (-not $process.HasExited) {
                            Write-Progress "Graceful shutdown timeout, forcing kill" "Yellow"
                            $process.Kill()
                        }
                    }
                    else {
                        Write-Verbose "Force stopping process $($process.Id)"
                        $process.Kill()
                    }
                    
                    $stoppedAny = $true
                    Write-Progress "Stopped $processName process (PID: $($process.Id))" "Green"
                }
                catch {
                    Write-Progress "Failed to stop $processName process (PID: $($process.Id)): $_" "Red"
                }
            }
        }
        else {
            Write-Verbose "No $processName processes found"
        }
    }
    
    # Verify port is no longer in use
    if ($Service.Port) {
        $portStillOpen = Test-Port -Port $Service.Port -ServiceName $serviceName
        if ($portStillOpen) {
            Write-Progress "Warning: Port $($Service.Port) still in use after stopping $serviceName" "Yellow"
            return $false
        }
    }
    
    return $stoppedAny
}

function Stop-DockerService {
    param(
        [hashtable]$Service
    )
    
    $serviceName = $Service.Name
    $dockerService = $Service.DockerService
    $composeFile = $Service.ComposeFile
    $graceful = $Service.GracefulShutdown
    $timeout = $Service.StopTimeout
    $preStopCommand = $Service.PreStopCommand
    
    Write-Progress "Stopping Docker service: $serviceName ($dockerService)"
    
    # Execute pre-stop command if defined
    if ($preStopCommand) {
        Write-Progress "Executing pre-stop command for $serviceName..."
        try {
            Write-Verbose "Running: $preStopCommand"
            Invoke-Expression $preStopCommand 2>&1 | Out-Null
            Write-Progress "Pre-stop command completed for $serviceName" "Green"
        }
        catch {
            Write-Progress "Pre-stop command failed for $serviceName (continuing): $_" "Yellow"
        }
    }
    
    # Stop the Docker container
    try {
        if ($graceful -and -not $Force) {
            # Graceful stop with timeout
            $stopCmd = if ($composeFile) {
                "docker-compose -f $composeFile stop -t $timeout $dockerService"
            } else {
                "docker-compose stop -t $timeout $dockerService"
            }
        }
        else {
            # Force stop
            $stopCmd = if ($composeFile) {
                "docker-compose -f $composeFile kill $dockerService"
            } else {
                "docker-compose kill $dockerService"
            }
        }
        
        Write-Verbose "Executing: $stopCmd"
        Invoke-Expression $stopCmd
        
        if ($LASTEXITCODE -eq 0) {
            Write-Progress "Docker service $serviceName stopped successfully" "Green"
            
            # Verify container is stopped
            $containerStatus = docker ps --filter "name=$dockerService" --format "{{.Names}}"
            if (-not $containerStatus) {
                Write-Progress "Confirmed $serviceName container is stopped" "Green"
                return $true
            }
            else {
                Write-Progress "Warning: $serviceName container may still be running" "Yellow"
                
                if ($Force) {
                    Write-Progress "Force removing container..." "Yellow"
                    docker rm -f $dockerService 2>&1 | Out-Null
                    return $true
                }
                return $false
            }
        }
        else {
            Write-Progress "Failed to stop Docker service $serviceName (Exit code: $LASTEXITCODE)" "Red"
            return $false
        }
    }
    catch {
        Write-Progress "Exception stopping Docker service $serviceName : $_" "Red"
        return $false
    }
}

function Clear-ServiceArtifacts {
    param(
        [hashtable]$Service
    )
    
    if ($SkipCleanup) {
        Write-Verbose "Skipping cleanup for $($Service.Name)"
        return $true
    }
    
    $serviceName = $Service.Name
    Write-Progress "Cleaning up artifacts for $serviceName..."
    
    $cleanupSuccess = $true
    
    # Clean up log directories
    if ($Service.CleanupPaths -and -not $PreserveLogs) {
        foreach ($path in $Service.CleanupPaths) {
            if (Test-Path $path) {
                try {
                    Write-Verbose "Cleaning up path: $path"
                    Remove-Item -Path $path -Recurse -Force -ErrorAction Stop
                    Write-Progress "Cleaned up: $path" "Green"
                }
                catch {
                    Write-Progress "Failed to clean up $path : $_" "Yellow"
                    $ShutdownStatus.CleanupErrors += "Failed to clean up $path : $_"
                    $cleanupSuccess = $false
                }
            }
        }
    }
    
    # Service-specific cleanup
    switch ($serviceName) {
        "PostgreSQL" {
            # Clean up any temporary database files
            $tempDbFiles = @("*.tmp", "*.lock")
            foreach ($pattern in $tempDbFiles) {
                $files = Get-ChildItem -Path "database" -Filter $pattern -Recurse -ErrorAction SilentlyContinue
                foreach ($file in $files) {
                    try {
                        Remove-Item -Path $file.FullName -Force
                        Write-Verbose "Removed temp file: $($file.Name)"
                    }
                    catch {
                        Write-Verbose "Could not remove temp file: $($file.Name)"
                    }
                }
            }
        }
        "Kafka" {
            # Clean up Kafka temporary directories
            if (-not $PreserveLogs) {
                $kafkaTempDirs = @("kafka-logs-*", "zookeeper-*")
                foreach ($pattern in $kafkaTempDirs) {
                    $dirs = Get-ChildItem -Path "." -Directory -Filter $pattern -ErrorAction SilentlyContinue
                    foreach ($dir in $dirs) {
                        try {
                            Remove-Item -Path $dir.FullName -Recurse -Force
                            Write-Verbose "Removed Kafka temp dir: $($dir.Name)"
                        }
                        catch {
                            Write-Verbose "Could not remove Kafka temp dir: $($dir.Name)"
                        }
                    }
                }
            }
        }
        "HDFS NameNode" {
            # Clean up HDFS metadata if not preserving data
            if ($Force -and -not $PreserveLogs) {
                Write-Progress "Warning: Force cleanup would remove HDFS metadata" "Yellow"
                # Actual cleanup would be dangerous, so just warn
            }
        }
    }
    
    return $cleanupSuccess
}

function Stop-ServiceGroup {
    param(
        [hashtable]$Group,
        [string]$GroupName
    )
    
    Write-Progress "🛑 Stopping $GroupName services..." "Cyan"
    $ShutdownStatus.CurrentPhase = $GroupName
    
    $groupSuccess = $true
    
    foreach ($service in $Group.Services) {
        $serviceName = $service.Name
        
        # Skip if specific service requested and this service isn't dependent
        if ($Service -and $serviceName -ne $Service) {
            # TODO: Implement dependency checking to stop dependents
            continue
        }
        
        Write-Progress "Stopping $serviceName..."
        
        # Stop the service
        $stopped = $false
        
        if ($service.ProcessBased) {
            $stopped = Stop-ProcessService -Service $service
        }
        else {
            $stopped = Stop-DockerService -Service $service
        }
        
        if ($stopped) {
            $ShutdownStatus.ServicesStopped += $serviceName
            $ShutdownStatus.CompletedServices++
            Write-Progress "$serviceName stopped successfully ✅" "Green"
            
            # Cleanup service artifacts
            $cleanupSuccess = Clear-ServiceArtifacts -Service $service
            if (-not $cleanupSuccess) {
                Write-Progress "$serviceName cleanup had issues ⚠️" "Yellow"
            }
        }
        else {
            $ShutdownStatus.ServicesFailed += $serviceName
            $groupSuccess = $false
            Write-Progress "$serviceName failed to stop ❌" "Red"
            
            if (-not $Force) {
                Write-Progress "Stopping shutdown due to failed service (use -Force to continue)" "Red"
                return $false
            }
        }
        
        # Brief pause between services
        Start-Sleep -Seconds 2
    }
    
    if ($groupSuccess) {
        Write-Progress "$GroupName services stopped successfully ✅" "Green"
    }
    else {
        Write-Progress "$GroupName services completed with some failures ⚠️" "Yellow"
    }
    
    Write-Host ""
    return $groupSuccess
}

function Show-ShutdownSummary {
    $endTime = Get-Date
    $duration = $endTime - $ShutdownStatus.StartTime
    
    Write-Banner "🎯 SHUTDOWN SUMMARY" "Green"
    
    Write-Host "Duration: $($duration.TotalMinutes.ToString('F1')) minutes" -ForegroundColor Cyan
    Write-Host "Total Services: $($ShutdownStatus.TotalServices)" -ForegroundColor Cyan
    Write-Host "Stopped Successfully: $($ShutdownStatus.ServicesStopped.Count)" -ForegroundColor Green
    Write-Host "Failed to Stop: $($ShutdownStatus.ServicesFailed.Count)" -ForegroundColor $(if ($ShutdownStatus.ServicesFailed.Count -gt 0) { "Red" } else { "Green" })
    Write-Host "Cleanup Errors: $($ShutdownStatus.CleanupErrors.Count)" -ForegroundColor $(if ($ShutdownStatus.CleanupErrors.Count -gt 0) { "Yellow" } else { "Green" })
    
    if ($ShutdownStatus.ServicesStopped.Count -gt 0) {
        Write-Host "`n✅ Successfully Stopped Services:" -ForegroundColor Green
        foreach ($service in $ShutdownStatus.ServicesStopped) {
            Write-Host "   • $service" -ForegroundColor Green
        }
    }
    
    if ($ShutdownStatus.ServicesFailed.Count -gt 0) {
        Write-Host "`n❌ Failed to Stop:" -ForegroundColor Red
        foreach ($service in $ShutdownStatus.ServicesFailed) {
            Write-Host "   • $service" -ForegroundColor Red
        }
        
        Write-Host "`n🔧 Manual Cleanup May Be Required:" -ForegroundColor Yellow
        Write-Host "   • Check running containers: docker ps" -ForegroundColor Yellow
        Write-Host "   • Force remove containers: docker rm -f [container-name]" -ForegroundColor Yellow
        Write-Host "   • Kill remaining processes: Get-Process | Where-Object {`$_.Name -match 'java|python|node'}" -ForegroundColor Yellow
    }
    
    if ($ShutdownStatus.CleanupErrors.Count -gt 0) {
        Write-Host "`n⚠️ Cleanup Issues:" -ForegroundColor Yellow
        foreach ($cleanupError in $ShutdownStatus.CleanupErrors) {
            Write-Host "   • $cleanupError" -ForegroundColor Yellow
        }
    }
    
    # Overall status
    $overallSuccess = $ShutdownStatus.ServicesFailed.Count -eq 0
    $status = if ($overallSuccess) { "SUCCESS" } else { "PARTIAL" }
    $statusColor = if ($overallSuccess) { "Green" } else { "Yellow" }
    
    Write-Host "`n🎯 Overall Status: $status" -ForegroundColor $statusColor
    
    if ($overallSuccess) {
        Write-Host "`n🎉 All services stopped successfully!" -ForegroundColor Green
        Write-Host "   • System is ready for maintenance or restart" -ForegroundColor Green
        Write-Host "   • Run .\start-all.ps1 to restart services" -ForegroundColor Cyan
    }
    else {
        Write-Host "`n⚠️ Some services failed to stop properly" -ForegroundColor Yellow
        Write-Host "   • Manual intervention may be required" -ForegroundColor Yellow
        Write-Host "   • Check Docker containers and processes" -ForegroundColor Yellow
    }
    
    Write-Host ""
    return $overallSuccess
}

function main {
    Write-Banner "$ScriptName v$ScriptVersion" "Green"
    
    Write-Host "Configuration:" -ForegroundColor Cyan
    Write-Host "  Force Stop: $Force" -ForegroundColor White
    Write-Host "  Skip Cleanup: $SkipCleanup" -ForegroundColor White
    Write-Host "  Preserve Logs: $PreserveLogs" -ForegroundColor White
    Write-Host "  Timeout: $TimeoutSeconds seconds" -ForegroundColor White
    Write-Host "  Specific Service: $(if ($Service) { $Service } else { 'All Services' })" -ForegroundColor White
    Write-Host ""
    
    # Pre-flight checks
    Write-Progress "🔍 Running pre-flight checks..."
    
    if (-not (Test-DockerRunning)) {
        Write-Progress "Docker is not running - will only stop process-based services" "Yellow"
    }
    else {
        Write-Progress "Docker is running ✅" "Green"
    }
    
    Write-Host ""
    
    # Calculate total services for progress tracking
    foreach ($groupName in $ShutdownGroups.Keys) {
        $group = $ShutdownGroups[$groupName]
        $ShutdownStatus.TotalServices += $group.Services.Count
    }
    
    Write-Progress "🛑 Stopping $($ShutdownStatus.TotalServices) services..."
    Write-Host ""
    
    # Stop service groups in shutdown order
    $sortedGroups = $ShutdownGroups.GetEnumerator() | Sort-Object { $_.Value.Order }
    
    foreach ($groupEntry in $sortedGroups) {
        $groupName = $groupEntry.Key
        $group = $groupEntry.Value
        
        $groupSuccess = Stop-ServiceGroup -Group $group -GroupName $groupName
        if (-not $groupSuccess -and -not $Force) {
            break
        }
    }
    
    # Additional cleanup
    if (-not $SkipCleanup) {
        Write-Progress "🧹 Running final cleanup..."
        
        # Clean up Docker networks
        try {
            $networks = docker network ls --filter "name=traffic-prediction" --format "{{.Name}}"
            if ($networks) {
                Write-Progress "Cleaning up Docker networks..."
                docker network rm $networks 2>&1 | Out-Null
            }
        }
        catch {
            Write-Progress "Could not clean up Docker networks: $_" "Yellow"
        }
        
        # Clean up any remaining containers
        if ($Force) {
            try {
                $containers = docker ps -a --filter "label=com.docker.compose.project=traffic-prediction" --format "{{.Names}}"
                if ($containers) {
                    Write-Progress "Force removing remaining containers..."
                    docker rm -f $containers 2>&1 | Out-Null
                }
            }
            catch {
                Write-Progress "Could not force remove containers: $_" "Yellow"
            }
        }
    }
    
    # Show summary
    $success = Show-ShutdownSummary
    
    if ($success) {
        Write-Progress "🎉 Traffic Prediction System shutdown completed successfully!" "Green"
        return $true
    }
    else {
        Write-Progress "⚠️ Traffic Prediction System shutdown completed with issues" "Yellow"
        return $false
    }
}

# Script execution
try {
    $success = main
    exit $(if ($success) { 0 } else { 1 })
}
catch {
    Write-Progress "Fatal error during shutdown: $_" "Red"
    exit 1
}
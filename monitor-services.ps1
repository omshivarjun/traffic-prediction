# PowerShell Service Monitoring Script for Traffic Prediction System
# Task 17.4: Service Monitoring System
# 
# This script provides continuous monitoring, alerting, and performance tracking for all services

param(
    [switch]$Continuous,
    [int]$IntervalSeconds = 30,
    [switch]$ShowMetrics,
    [switch]$AlertMode,
    [string]$OutputFile = "",
    [string]$AlertEmail = "",
    [int]$MaxRunTime = 0,  # 0 = run indefinitely
    [switch]$Dashboard
)

# Set error handling
$ErrorActionPreference = "Continue"

# Script metadata
$ScriptVersion = "1.0.0"
$ScriptName = "Traffic Prediction System - Service Monitor"

# Define monitoring configuration
$MonitoringConfig = @{
    Services = @{
        "PostgreSQL" = @{
            Port = 5433
            HealthEndpoint = $null
            Command = "docker exec postgres pg_isready -U traffic_user"
            Metrics = @{
                Connections = "docker exec postgres psql -U traffic_user -c 'SELECT count(*) FROM pg_stat_activity;'"
                DatabaseSize = "docker exec postgres psql -U traffic_user -c 'SELECT pg_size_pretty(pg_database_size(''traffic_prediction''));'"
            }
            Thresholds = @{
                ResponseTime = 5000  # ms
                Connections = 100
                DiskUsage = 80  # percentage
            }
            Alerts = @("connection_failure", "high_connections", "slow_response")
        }
        "Zookeeper" = @{
            Port = 2181
            Command = "echo stat | nc localhost 2181"
            Metrics = @{
                Mode = "echo stat | nc localhost 2181 | grep Mode"
                Connections = "echo stat | nc localhost 2181 | grep Connections"
            }
            Thresholds = @{
                ResponseTime = 3000
            }
            Alerts = @("connection_failure", "not_leader")
        }
        "Kafka" = @{
            Port = 9092
            Command = "docker exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092"
            Metrics = @{
                Topics = "docker exec kafka kafka-topics --list --bootstrap-server localhost:9092 | wc -l"
                Partitions = "docker exec kafka kafka-log-dirs --bootstrap-server localhost:9092 --describe --json"
            }
            Thresholds = @{
                ResponseTime = 5000
                TopicCount = 3  # Minimum expected topics
            }
            Alerts = @("connection_failure", "missing_topics", "partition_issues")
        }
        "Schema Registry" = @{
            Port = 8081
            HealthEndpoint = "http://localhost:8081/subjects"
            Metrics = @{
                Subjects = "curl -s http://localhost:8081/subjects | jq '. | length'"
                Config = "curl -s http://localhost:8081/config"
            }
            Thresholds = @{
                ResponseTime = 3000
                SubjectCount = 2  # Minimum expected schemas
            }
            Alerts = @("connection_failure", "missing_schemas")
        }
        "Kafka Connect" = @{
            Port = 8083
            HealthEndpoint = "http://localhost:8083/connectors"
            Metrics = @{
                Connectors = "curl -s http://localhost:8083/connectors | jq '. | length'"
                Status = "curl -s http://localhost:8083/connectors/hdfs-sink/status"
            }
            Thresholds = @{
                ResponseTime = 3000
                ConnectorCount = 1
            }
            Alerts = @("connection_failure", "connector_failed")
        }
        "HDFS NameNode" = @{
            Port = 9871
            HealthEndpoint = "http://localhost:9871/jmx"
            Metrics = @{
                Storage = "curl -s http://localhost:9871/jmx?qry=Hadoop:service=NameNode,name=FSNamesystemState"
                DataNodes = "curl -s http://localhost:9871/jmx?qry=Hadoop:service=NameNode,name=FSNamesystem"
            }
            Thresholds = @{
                ResponseTime = 5000
                StorageUsage = 85
                DataNodeCount = 1
            }
            Alerts = @("connection_failure", "storage_full", "datanode_down")
        }
        "HDFS DataNode" = @{
            Port = 9864
            HealthEndpoint = "http://localhost:9864/jmx"
            Metrics = @{
                Storage = "curl -s http://localhost:9864/jmx?qry=Hadoop:service=DataNode,name=FSDatasetState-*"
                Blocks = "curl -s http://localhost:9864/jmx?qry=Hadoop:service=DataNode,name=DataNodeActivity-*"
            }
            Thresholds = @{
                ResponseTime = 3000
                StorageUsage = 85
            }
            Alerts = @("connection_failure", "storage_full")
        }
        "YARN ResourceManager" = @{
            Port = 8088
            HealthEndpoint = "http://localhost:8088/ws/v1/cluster/info"
            Metrics = @{
                ClusterInfo = "curl -s http://localhost:8088/ws/v1/cluster/info"
                Nodes = "curl -s http://localhost:8088/ws/v1/cluster/nodes"
                Apps = "curl -s http://localhost:8088/ws/v1/cluster/apps"
            }
            Thresholds = @{
                ResponseTime = 5000
                NodeCount = 1
                MemoryUsage = 80
            }
            Alerts = @("connection_failure", "node_down", "high_memory_usage")
        }
        "YARN NodeManager" = @{
            Port = 8042
            HealthEndpoint = "http://localhost:8042/ws/v1/node/info"
            Metrics = @{
                NodeInfo = "curl -s http://localhost:8042/ws/v1/node/info"
                Containers = "curl -s http://localhost:8042/ws/v1/node/containers"
            }
            Thresholds = @{
                ResponseTime = 3000
                ContainerCount = 10
            }
            Alerts = @("connection_failure", "too_many_containers")
        }
        "FastAPI Backend" = @{
            Port = 8000
            HealthEndpoint = "http://localhost:8000/health"
            Metrics = @{
                Version = "curl -s http://localhost:8000/api/v1/system/version"
                Stats = "curl -s http://localhost:8000/api/v1/system/stats"
            }
            Thresholds = @{
                ResponseTime = 2000
                ErrorRate = 5  # percentage
            }
            Alerts = @("connection_failure", "high_error_rate", "slow_response")
        }
        "React Frontend" = @{
            Port = 3000
            HealthEndpoint = "http://localhost:3000"
            Metrics = @{}
            Thresholds = @{
                ResponseTime = 3000
            }
            Alerts = @("connection_failure", "slow_response")
        }
    }
    
    AlertThresholds = @{
        ConsecutiveFailures = 3
        ResponseTimeMultiplier = 2.0
        MetricDeviationPercent = 50
    }
    
    Dashboard = @{
        RefreshInterval = 5
        HistoryMinutes = 60
        ShowGraphs = $true
    }
}

# Global monitoring state
$MonitoringState = @{
    StartTime = Get-Date
    CheckCount = 0
    ServiceStates = @{}
    AlertHistory = @()
    MetricHistory = @{}
    LastAlertTime = @{}
    RunTime = 0
}

function Write-Banner {
    param([string]$Message, [string]$Color = "Cyan")
    
    $border = "=" * 80
    Write-Host $border -ForegroundColor $Color
    Write-Host $Message -ForegroundColor $Color
    Write-Host $border -ForegroundColor $Color
    Write-Host ""
}

function Write-MonitorLog {
    param([string]$Message, [string]$Level = "INFO", [string]$Service = "")
    
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $prefix = if ($Service) { "[$Service]" } else { "" }
    
    $color = switch ($Level) {
        "OK" { "Green" }
        "WARNING" { "Yellow" }
        "ERROR" { "Red" }
        "ALERT" { "Magenta" }
        default { "White" }
    }
    
    $icon = switch ($Level) {
        "OK" { "✅" }
        "WARNING" { "⚠️" }
        "ERROR" { "❌" }
        "ALERT" { "🚨" }
        default { "ℹ️" }
    }
    
    $logEntry = "[$timestamp] $icon $prefix $Message"
    Write-Host $logEntry -ForegroundColor $color
    
    # Write to output file if specified
    if ($OutputFile) {
        Add-Content -Path $OutputFile -Value $logEntry
    }
}

function Test-ServiceHealth {
    param([string]$ServiceName, [hashtable]$Config)
    
    $result = @{
        Service = $ServiceName
        Timestamp = Get-Date
        Healthy = $false
        ResponseTime = 0
        Metrics = @{}
        Errors = @()
        Warnings = @()
    }
    
    $startTime = Get-Date
    
    try {
        # Port connectivity test
        if ($Config.Port) {
            $portTest = Test-NetConnection -ComputerName "localhost" -Port $Config.Port -InformationLevel Quiet -WarningAction SilentlyContinue
            if (-not $portTest) {
                $result.Errors += "Port $($Config.Port) not accessible"
                return $result
            }
        }
        
        # HTTP health endpoint test
        if ($Config.HealthEndpoint) {
            try {
                $response = Invoke-WebRequest -Uri $Config.HealthEndpoint -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop
                $result.ResponseTime = ((Get-Date) - $startTime).TotalMilliseconds
                
                if ($response.StatusCode -eq 200) {
                    $result.Healthy = $true
                }
                else {
                    $result.Errors += "HTTP endpoint returned status $($response.StatusCode)"
                }
            }
            catch {
                $result.Errors += "HTTP endpoint failed: $($_.Exception.Message)"
                return $result
            }
        }
        
        # Command-based health check
        elseif ($Config.Command) {
            try {
                $null = Invoke-Expression $Config.Command 2>&1
                $result.ResponseTime = ((Get-Date) - $startTime).TotalMilliseconds
                
                if ($LASTEXITCODE -eq 0) {
                    $result.Healthy = $true
                }
                else {
                    $result.Errors += "Health command failed with exit code $LASTEXITCODE"
                }
            }
            catch {
                $result.Errors += "Health command error: $($_.Exception.Message)"
                return $result
            }
        }
        
        # Collect metrics if service is healthy
        if ($result.Healthy -and $ShowMetrics -and $Config.Metrics) {
            foreach ($metricName in $Config.Metrics.Keys) {
                try {
                    $metricCommand = $Config.Metrics[$metricName]
                    $metricResult = Invoke-Expression $metricCommand 2>&1
                    
                    if ($LASTEXITCODE -eq 0) {
                        $result.Metrics[$metricName] = $metricResult
                    }
                    else {
                        $result.Warnings += "Failed to collect metric: $metricName"
                    }
                }
                catch {
                    $result.Warnings += "Metric collection error for $metricName : $($_.Exception.Message)"
                }
            }
        }
        
        # Check thresholds and generate alerts
        if ($AlertMode -and $Config.Thresholds) {
            $thresholds = $Config.Thresholds
            
            # Response time check
            if ($thresholds.ResponseTime -and $result.ResponseTime -gt $thresholds.ResponseTime) {
                $alert = @{
                    Service = $ServiceName
                    Type = "slow_response"
                    Message = "Response time $($result.ResponseTime)ms exceeds threshold $($thresholds.ResponseTime)ms"
                    Timestamp = Get-Date
                    Severity = "WARNING"
                }
                Send-Alert -Alert $alert
            }
            
            # Service-specific threshold checks would go here based on metrics
        }
    }
    catch {
        $result.Errors += "Unexpected error: $($_.Exception.Message)"
    }
    
    return $result
}

function Update-ServiceState {
    param([hashtable]$HealthResult)
    
    $serviceName = $HealthResult.Service
    
    if (-not $MonitoringState.ServiceStates.ContainsKey($serviceName)) {
        $MonitoringState.ServiceStates[$serviceName] = @{
            CurrentState = "UNKNOWN"
            LastHealthy = $null
            ConsecutiveFailures = 0
            ConsecutiveSuccesses = 0
            TotalChecks = 0
            HealthyChecks = 0
            LastResponseTime = 0
            AverageResponseTime = 0
        }
    }
    
    $serviceState = $MonitoringState.ServiceStates[$serviceName]
    $serviceState.TotalChecks++
    $serviceState.LastResponseTime = $HealthResult.ResponseTime
    
    if ($HealthResult.Healthy) {
        $serviceState.CurrentState = "HEALTHY"
        $serviceState.LastHealthy = $HealthResult.Timestamp
        $serviceState.ConsecutiveFailures = 0
        $serviceState.ConsecutiveSuccesses++
        $serviceState.HealthyChecks++
        
        # Update average response time
        $serviceState.AverageResponseTime = (($serviceState.AverageResponseTime * ($serviceState.HealthyChecks - 1)) + $HealthResult.ResponseTime) / $serviceState.HealthyChecks
    }
    else {
        $serviceState.CurrentState = "UNHEALTHY"
        $serviceState.ConsecutiveFailures++
        $serviceState.ConsecutiveSuccesses = 0
        
        # Generate alert for consecutive failures
        if ($AlertMode -and $serviceState.ConsecutiveFailures -ge $MonitoringConfig.AlertThresholds.ConsecutiveFailures) {
            $alert = @{
                Service = $serviceName
                Type = "consecutive_failures"
                Message = "$($serviceState.ConsecutiveFailures) consecutive failures detected"
                Timestamp = Get-Date
                Severity = "ERROR"
                Errors = $HealthResult.Errors
            }
            Send-Alert -Alert $alert
        }
    }
    
    # Store metric history for trending
    if ($HealthResult.Metrics.Count -gt 0) {
        if (-not $MonitoringState.MetricHistory.ContainsKey($serviceName)) {
            $MonitoringState.MetricHistory[$serviceName] = @{}
        }
        
        foreach ($metricName in $HealthResult.Metrics.Keys) {
            if (-not $MonitoringState.MetricHistory[$serviceName].ContainsKey($metricName)) {
                $MonitoringState.MetricHistory[$serviceName][$metricName] = @()
            }
            
            $MonitoringState.MetricHistory[$serviceName][$metricName] += @{
                Timestamp = $HealthResult.Timestamp
                Value = $HealthResult.Metrics[$metricName]
            }
            
            # Keep only recent history
            $maxHistory = [math]::Max(1, ($MonitoringConfig.Dashboard.HistoryMinutes * 60) / $IntervalSeconds)
            if ($MonitoringState.MetricHistory[$serviceName][$metricName].Count -gt $maxHistory) {
                $MonitoringState.MetricHistory[$serviceName][$metricName] = $MonitoringState.MetricHistory[$serviceName][$metricName] | Select-Object -Last $maxHistory
            }
        }
    }
}

function Send-Alert {
    param([hashtable]$Alert)
    
    $serviceName = $Alert.Service
    $alertType = $Alert.Type
    
    # Check if we've already sent this alert recently (avoid spam)
    $alertKey = "$serviceName-$alertType"
    $now = Get-Date
    
    if ($MonitoringState.LastAlertTime.ContainsKey($alertKey)) {
        $lastAlert = $MonitoringState.LastAlertTime[$alertKey]
        $timeSinceLastAlert = ($now - $lastAlert).TotalMinutes
        
        # Don't send same alert more than once every 5 minutes
        if ($timeSinceLastAlert -lt 5) {
            return
        }
    }
    
    $MonitoringState.LastAlertTime[$alertKey] = $now
    $MonitoringState.AlertHistory += $Alert
    
    # Console alert
    Write-MonitorLog "ALERT: $($Alert.Message)" "ALERT" $serviceName
    
    # Email alert (if configured)
    if ($AlertEmail) {
        try {
            # Note: This would need SMTP configuration
            # Send-MailMessage -To $AlertEmail -Subject "Traffic Prediction System Alert - $serviceName" -Body "Alert details..." -SmtpServer "localhost"
            Write-MonitorLog "Email alert would be sent to $AlertEmail" "INFO" $serviceName
        }
        catch {
            Write-MonitorLog "Failed to send email alert: $_" "ERROR"
        }
    }
    
    # Keep alert history manageable
    if ($MonitoringState.AlertHistory.Count -gt 100) {
        $MonitoringState.AlertHistory = $MonitoringState.AlertHistory | Select-Object -Last 50
    }
}

function Show-MonitoringDashboard {
    # Clear screen for dashboard mode
    if ($Dashboard) {
        Clear-Host
    }
    
    Write-Banner "🖥️ SERVICE MONITORING DASHBOARD" "Green"
    
    $currentTime = Get-Date
    $uptime = $currentTime - $MonitoringState.StartTime
    
    Write-Host "Monitoring Runtime: $($uptime.Hours.ToString('00')):$($uptime.Minutes.ToString('00')):$($uptime.Seconds.ToString('00'))" -ForegroundColor Cyan
    Write-Host "Total Checks: $($MonitoringState.CheckCount)" -ForegroundColor Cyan
    Write-Host "Check Interval: $IntervalSeconds seconds" -ForegroundColor Cyan
    Write-Host "Last Update: $($currentTime.ToString('HH:mm:ss'))" -ForegroundColor Cyan
    Write-Host ""
    
    # Service status summary
    Write-Host "📊 SERVICE STATUS OVERVIEW" -ForegroundColor Yellow
    Write-Host "$('-' * 80)" -ForegroundColor Yellow
    
    $healthyCount = 0
    $unhealthyCount = 0
    $unknownCount = 0
    
    foreach ($serviceName in $MonitoringConfig.Services.Keys) {
        if ($MonitoringState.ServiceStates.ContainsKey($serviceName)) {
            $serviceState = $MonitoringState.ServiceStates[$serviceName]
            $status = $serviceState.CurrentState
            
            $statusIcon = switch ($status) {
                "HEALTHY" { "✅"; $healthyCount++ }
                "UNHEALTHY" { "❌"; $unhealthyCount++ }
                default { "❓"; $unknownCount++ }
            }
            
            $responseTime = if ($serviceState.LastResponseTime -gt 0) { "$($serviceState.LastResponseTime.ToString('F0'))ms" } else { "N/A" }
            $uptime = if ($serviceState.TotalChecks -gt 0) { (($serviceState.HealthyChecks / $serviceState.TotalChecks) * 100).ToString('F1') + "%" } else { "N/A" }
            
            Write-Host "$statusIcon $($serviceName.PadRight(20)) | $($status.PadRight(10)) | $($responseTime.PadRight(8)) | $uptime" -ForegroundColor White
        }
        else {
            Write-Host "❓ $($serviceName.PadRight(20)) | NOT CHECKED| N/A      | N/A" -ForegroundColor Gray
            $unknownCount++
        }
    }
    
    Write-Host ""
    Write-Host "Summary: $healthyCount Healthy, $unhealthyCount Unhealthy, $unknownCount Not Checked" -ForegroundColor Cyan
    
    # Recent alerts
    if ($MonitoringState.AlertHistory.Count -gt 0) {
        Write-Host ""
        Write-Host "🚨 RECENT ALERTS (Last 10)" -ForegroundColor Red
        Write-Host "$('-' * 80)" -ForegroundColor Red
        
        $recentAlerts = $MonitoringState.AlertHistory | Sort-Object Timestamp -Descending | Select-Object -First 10
        foreach ($alert in $recentAlerts) {
            $timeAgo = ((Get-Date) - $alert.Timestamp).TotalMinutes
            $timeString = if ($timeAgo -lt 1) { "< 1 min ago" } else { "$([math]::Round($timeAgo)) min ago" }
            
            $severityColor = switch ($alert.Severity) {
                "ERROR" { "Red" }
                "WARNING" { "Yellow" }
                default { "Magenta" }
            }
            
            Write-Host "[$timeString] $($alert.Service): $($alert.Message)" -ForegroundColor $severityColor
        }
    }
    
    # Performance metrics (if enabled)
    if ($ShowMetrics -and $MonitoringState.MetricHistory.Count -gt 0) {
        Write-Host ""
        Write-Host "📈 PERFORMANCE METRICS" -ForegroundColor Green
        Write-Host "$('-' * 80)" -ForegroundColor Green
        
        foreach ($serviceName in $MonitoringState.MetricHistory.Keys) {
            Write-Host "$serviceName Metrics:" -ForegroundColor Cyan
            
            foreach ($metricName in $MonitoringState.MetricHistory[$serviceName].Keys) {
                $metricHistory = $MonitoringState.MetricHistory[$serviceName][$metricName]
                if ($metricHistory.Count -gt 0) {
                    $latestValue = $metricHistory[-1].Value
                    Write-Host "   $metricName`: $latestValue" -ForegroundColor White
                }
            }
        }
    }
    
    if ($Dashboard) {
        Write-Host ""
        Write-Host "Press Ctrl+C to stop monitoring..." -ForegroundColor Gray
    }
}

function main {
    Write-Banner "$ScriptName v$ScriptVersion" "Green"
    
    Write-Host "Configuration:" -ForegroundColor Cyan
    Write-Host "  Continuous Monitoring: $Continuous" -ForegroundColor White
    Write-Host "  Check Interval: $IntervalSeconds seconds" -ForegroundColor White
    Write-Host "  Show Metrics: $ShowMetrics" -ForegroundColor White
    Write-Host "  Alert Mode: $AlertMode" -ForegroundColor White
    Write-Host "  Dashboard Mode: $Dashboard" -ForegroundColor White
    Write-Host "  Output File: $(if ($OutputFile) { $OutputFile } else { 'Console Only' })" -ForegroundColor White
    Write-Host "  Max Runtime: $(if ($MaxRunTime -gt 0) { "$MaxRunTime seconds" } else { 'Unlimited' })" -ForegroundColor White
    Write-Host ""
    
    # Initialize output file
    if ($OutputFile) {
        "# Traffic Prediction System - Service Monitoring Log" | Out-File -FilePath $OutputFile
        "# Started: $(Get-Date)" | Add-Content -Path $OutputFile
        "" | Add-Content -Path $OutputFile
    }
    
    Write-MonitorLog "🚀 Starting service monitoring..." "INFO"
    
    # Main monitoring loop
    do {
        $loopStartTime = Get-Date
        $MonitoringState.CheckCount++
        
        Write-MonitorLog "--- Check #$($MonitoringState.CheckCount) ---" "INFO"
        
        # Check each service
        foreach ($serviceName in $MonitoringConfig.Services.Keys) {
            $serviceConfig = $MonitoringConfig.Services[$serviceName]
            
            try {
                $healthResult = Test-ServiceHealth -ServiceName $serviceName -Config $serviceConfig
                Update-ServiceState -HealthResult $healthResult
                
                if ($healthResult.Healthy) {
                    Write-MonitorLog "$serviceName is healthy ($($healthResult.ResponseTime.ToString('F0'))ms)" "OK" $serviceName
                }
                else {
                    Write-MonitorLog "$serviceName is unhealthy: $($healthResult.Errors -join ', ')" "ERROR" $serviceName
                }
                
                # Log warnings
                foreach ($warning in $healthResult.Warnings) {
                    Write-MonitorLog $warning "WARNING" $serviceName
                }
            }
            catch {
                Write-MonitorLog "Error checking $serviceName : $_" "ERROR" $serviceName
            }
        }
        
        # Show dashboard if enabled
        if ($Dashboard -or (-not $Continuous)) {
            Show-MonitoringDashboard
        }
        
        # Check if we should continue
        if ($Continuous) {
            # Calculate runtime
            $MonitoringState.RunTime = ((Get-Date) - $MonitoringState.StartTime).TotalSeconds
            
            if ($MaxRunTime -gt 0 -and $MonitoringState.RunTime -ge $MaxRunTime) {
                Write-MonitorLog "Maximum runtime reached ($MaxRunTime seconds), stopping..." "INFO"
                break
            }
            
            # Sleep until next check
            $loopDuration = ((Get-Date) - $loopStartTime).TotalSeconds
            $sleepTime = [math]::Max(1, $IntervalSeconds - $loopDuration)
            
            if ($sleepTime -gt 0) {
                Start-Sleep -Seconds $sleepTime
            }
        }
        
    } while ($Continuous)
    
    # Final summary
    Write-MonitorLog "🏁 Monitoring completed" "INFO"
    Write-MonitorLog "Total checks performed: $($MonitoringState.CheckCount)" "INFO"
    Write-MonitorLog "Total alerts generated: $($MonitoringState.AlertHistory.Count)" "INFO"
    
    if ($OutputFile) {
        Write-MonitorLog "Full log saved to: $OutputFile" "INFO"
    }
    
    return $true
}

# Handle Ctrl+C gracefully
$null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action {
    Write-Host "`n🛑 Monitoring stopped by user" -ForegroundColor Yellow
}

# Script execution
try {
    $success = main
    exit $(if ($success) { 0 } else { 1 })
}
catch {
    Write-MonitorLog "Fatal error during monitoring: $_" "ERROR"
    exit 1
}
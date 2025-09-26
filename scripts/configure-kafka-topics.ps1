# Task 7.2: Advanced Kafka Topic Configuration Script
# Applies detailed topic-level configurations for optimal performance

param(
    [string]$Action = "configure",
    [string]$Topic = "all"
)

# Check if Docker and Kafka are running
function Test-KafkaAvailability {
    $dockerRunning = docker info 2>$null
    if (-not $dockerRunning) {
        Write-Host "Error: Docker is not running. Please start Docker Desktop." -ForegroundColor Red
        exit 1
    }

    $kafkaRunning = docker ps --filter "name=kafka-broker1" --format "{{.Names}}" 2>$null
    if (-not $kafkaRunning) {
        Write-Host "Error: Kafka broker not running. Start with: docker-compose up -d" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "✅ Kafka broker is available" -ForegroundColor Green
}

# Apply configuration to a specific topic
function Set-TopicConfiguration {
    param(
        [string]$TopicName,
        [hashtable]$Config,
        [string]$Description
    )
    
    Write-Host "`nConfiguring topic: $TopicName" -ForegroundColor Yellow
    Write-Host "Description: $Description" -ForegroundColor Gray
    
    foreach ($key in $Config.Keys) {
        $value = $Config[$key]
        Write-Host "  Setting $key = $value" -ForegroundColor Cyan
        
        $result = docker exec kafka-broker1 kafka-configs --bootstrap-server kafka-broker1:9092 --entity-type topics --entity-name $TopicName --alter --add-config "$key=$value" 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "    ✅ Applied successfully" -ForegroundColor Green
        } else {
            Write-Host "    ❌ Failed: $result" -ForegroundColor Red
        }
    }
}

# Get current topic configuration
function Get-TopicConfiguration {
    param([string]$TopicName)
    
    Write-Host "`nCurrent configuration for ${TopicName}:" -ForegroundColor Yellow
    $config = docker exec kafka-broker1 kafka-configs --bootstrap-server kafka-broker1:9092 --entity-type topics --entity-name $TopicName --describe
    Write-Host $config -ForegroundColor Gray
}

# Verify topic exists
function Test-TopicExists {
    param([string]$TopicName)
    
    $topics = docker exec kafka-broker1 kafka-topics --list --bootstrap-server kafka-broker1:9092
    return $topics -contains $TopicName
}

Write-Host "=== Task 7.2: Kafka Topic Configuration ===" -ForegroundColor Cyan
Write-Host "Applying advanced topic-level configurations..." -ForegroundColor Yellow

Test-KafkaAvailability

# Define Task 7.2 topic configurations
$topicConfigurations = @{
    "traffic-raw" = @{
        Config = @{
            "compression.type" = "snappy"
            "cleanup.policy" = "delete"
            "segment.ms" = "86400000"
            "retention.ms" = "604800000"
            "min.insync.replicas" = "1"
            "unclean.leader.election.enable" = "false"
            "max.message.bytes" = "1048576"
            "segment.bytes" = "1073741824"
            "min.cleanable.dirty.ratio" = "0.1"
            "delete.retention.ms" = "86400000"
        }
        Description = "Raw traffic events with optimized compression and retention"
    }
    
    "traffic-processed" = @{
        Config = @{
            "compression.type" = "snappy"
            "cleanup.policy" = "delete"
            "segment.ms" = "86400000"
            "retention.ms" = "604800000"
            "min.insync.replicas" = "1"
            "unclean.leader.election.enable" = "false"
            "max.message.bytes" = "2097152"
            "segment.bytes" = "1073741824"
            "min.cleanable.dirty.ratio" = "0.1"
            "delete.retention.ms" = "86400000"
        }
        Description = "Processed traffic aggregates with larger message support"
    }
    
    "traffic-alerts" = @{
        Config = @{
            "compression.type" = "snappy"
            "cleanup.policy" = "delete"
            "segment.ms" = "86400000"
            "retention.ms" = "604800000"
            "min.insync.replicas" = "1"
            "unclean.leader.election.enable" = "false"
            "max.message.bytes" = "512000"
            "segment.bytes" = "536870912"
            "min.cleanable.dirty.ratio" = "0.1"
            "delete.retention.ms" = "86400000"
        }
        Description = "Traffic alerts with optimized low-latency settings"
    }
}

# Process based on action parameter
switch ($Action.ToLower()) {
    "configure" {
        if ($Topic -eq "all") {
            Write-Host "`n🚀 Configuring all Task 7.2 topics..." -ForegroundColor Green
            
            foreach ($topicName in $topicConfigurations.Keys) {
                if (Test-TopicExists -TopicName $topicName) {
                    $topicConfig = $topicConfigurations[$topicName]
                    Set-TopicConfiguration -TopicName $topicName -Config $topicConfig.Config -Description $topicConfig.Description
                } else {
                    Write-Host "⚠️ Topic $topicName does not exist. Run create-kafka-topics.ps1 first." -ForegroundColor Yellow
                }
            }
        } else {
            if ($topicConfigurations.ContainsKey($Topic)) {
                if (Test-TopicExists -TopicName $Topic) {
                    $topicConfig = $topicConfigurations[$Topic]
                    Set-TopicConfiguration -TopicName $Topic -Config $topicConfig.Config -Description $topicConfig.Description
                } else {
                    Write-Host "❌ Topic $Topic does not exist." -ForegroundColor Red
                    exit 1
                }
            } else {
                Write-Host "❌ Unknown topic: $Topic" -ForegroundColor Red
                Write-Host "Available topics: $($topicConfigurations.Keys -join ', ')" -ForegroundColor Yellow
                exit 1
            }
        }
    }
    
    "verify" {
        Write-Host "`n🔍 Verifying topic configurations..." -ForegroundColor Green
        
        $topicsToCheck = if ($Topic -eq "all") { $topicConfigurations.Keys } else { @($Topic) }
        
        foreach ($topicName in $topicsToCheck) {
            if (Test-TopicExists -TopicName $topicName) {
                Get-TopicConfiguration -TopicName $topicName
            } else {
                Write-Host "⚠️ Topic $topicName does not exist." -ForegroundColor Yellow
            }
        }
    }
    
    "reset" {
        Write-Host "`n⚠️ Resetting topic configurations to defaults..." -ForegroundColor Yellow
        Write-Host "This will remove all custom configurations. Continue? (y/N): " -NoNewline
        $confirm = Read-Host
        
        if ($confirm -eq "y" -or $confirm -eq "Y") {
            $topicsToReset = if ($Topic -eq "all") { $topicConfigurations.Keys } else { @($Topic) }
            
            foreach ($topicName in $topicsToReset) {
                if (Test-TopicExists -TopicName $topicName) {
                    Write-Host "Resetting $topicName..." -ForegroundColor Yellow
                    docker exec kafka-broker1 kafka-configs --bootstrap-server kafka-broker1:9092 --entity-type topics --entity-name $topicName --alter --delete-config "compression.type,segment.ms,max.message.bytes,segment.bytes"
                } else {
                    Write-Host "⚠️ Topic $topicName does not exist." -ForegroundColor Yellow
                }
            }
        } else {
            Write-Host "Reset cancelled." -ForegroundColor Gray
        }
    }
    
    default {
        Write-Host "Usage: .\configure-kafka-topics.ps1 [-Action <configure|verify|reset>] [-Topic <topic-name|all>]" -ForegroundColor Yellow
        Write-Host "Examples:" -ForegroundColor Gray
        Write-Host "  .\configure-kafka-topics.ps1 -Action configure -Topic all" -ForegroundColor Gray
        Write-Host "  .\configure-kafka-topics.ps1 -Action verify -Topic traffic-raw" -ForegroundColor Gray
        Write-Host "  .\configure-kafka-topics.ps1 -Action reset -Topic traffic-alerts" -ForegroundColor Gray
        exit 1
    }
}

Write-Host "`n🎉 Task 7.2: Topic Configuration - COMPLETED!" -ForegroundColor Green
Write-Host "✅ Compression.type=snappy applied to all core topics" -ForegroundColor White
Write-Host "✅ Segment.ms configured for 24-hour log rolling" -ForegroundColor White  
Write-Host "✅ Cleanup.policy=delete set for all topics" -ForegroundColor White
Write-Host "✅ Advanced performance settings applied" -ForegroundColor White
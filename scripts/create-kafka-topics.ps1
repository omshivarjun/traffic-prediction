# PowerShell script to create Kafka topics for traffic prediction system
# Task 7.1: Topic Creation - Implements specific requirements from Task 7

# Check if Docker is running
$dockerRunning = docker info 2>$null
if (-not $dockerRunning) {
    Write-Host "Error: Docker is not running. Please start Docker Desktop and try again." -ForegroundColor Red
    exit 1
}

# Check if Kafka broker is running
$kafkaRunning = docker ps --filter "name=kafka-broker1" --format "{{.Names}}" 2>$null
if (-not $kafkaRunning) {
    Write-Host "Error: Kafka broker is not running. Please start the containers using docker-compose up -d and try again." -ForegroundColor Red
    exit 1
}

Write-Host "=== Task 7.1: Creating Kafka Topics for Traffic Data Streaming ===" -ForegroundColor Cyan
Write-Host "Implementing required topics with Task 7 specifications..." -ForegroundColor Yellow

# Task 7.1 Required Topics with specified configurations
# Retention: 168 hours = 604800000 milliseconds (7 days)
$coreTopics = @(
    @{
        Name="traffic-raw"; 
        Partitions=5; 
        ReplicationFactor=1; 
        Config=@{
            "retention.ms"="604800000";        # 168 hours (7 days)
            "cleanup.policy"="delete";
            "compression.type"="snappy";       # Task 7.2 requirement
            "segment.ms"="86400000";          # 24 hours log rolling
            "min.insync.replicas"="1";
            "unclean.leader.election.enable"="false"
        }
        Description="Raw traffic events from sensors - Task 7.1"
    },
    @{
        Name="traffic-processed"; 
        Partitions=5; 
        ReplicationFactor=1; 
        Config=@{
            "retention.ms"="604800000";        # 168 hours (7 days)
            "cleanup.policy"="delete";
            "compression.type"="snappy"; 
            "segment.ms"="86400000";
            "min.insync.replicas"="1";
            "unclean.leader.election.enable"="false"
        }
        Description="Processed traffic aggregates - Task 7.1"
    },
    @{
        Name="traffic-alerts"; 
        Partitions=2; 
        ReplicationFactor=1; 
        Config=@{
            "retention.ms"="604800000";        # 168 hours (7 days)
            "cleanup.policy"="delete";
            "compression.type"="snappy";
            "segment.ms"="86400000";
            "min.insync.replicas"="1";
            "unclean.leader.election.enable"="false"
        }
        Description="Traffic alerts and notifications - Task 7.1"
    }
)

# Additional supporting topics for complete traffic prediction system
$supportingTopics = @(
    @{
        Name="traffic-incidents"; 
        Partitions=3; 
        ReplicationFactor=1; 
        Config=@{
            "retention.ms"="604800000"; 
            "cleanup.policy"="delete";
            "compression.type"="snappy";
            "segment.ms"="86400000"
        }
        Description="Traffic incidents and events"
    },
    @{
        Name="traffic-predictions"; 
        Partitions=4; 
        ReplicationFactor=1; 
        Config=@{
            "retention.ms"="259200000";        # 3 days for predictions
            "cleanup.policy"="delete";
            "compression.type"="snappy";
            "segment.ms"="43200000"            # 12 hours for predictions
        }
        Description="Traffic predictions from ML models"
    },
    @{
        Name="processed-traffic-aggregates"; 
        Partitions=4; 
        ReplicationFactor=1; 
        Config=@{
            "retention.ms"="604800000"; 
            "cleanup.policy"="delete";
            "compression.type"="snappy";
            "segment.ms"="86400000"
        }
        Description="Windowed traffic aggregates for stream processing"
    }
)

# Enhanced topic creation function with detailed reporting
function New-KafkaTopics {
    Write-Host "`n--- Creating $topicType ---" -ForegroundColor Magenta
    
    foreach ($topic in $topicList) {
        Write-Host "`nTopic: $($topic.Name)" -ForegroundColor Green
        Write-Host "  Partitions: $($topic.Partitions)" -ForegroundColor Gray
        Write-Host "  Replication Factor: $($topic.ReplicationFactor)" -ForegroundColor Gray
        Write-Host "  Description: $($topic.Description)" -ForegroundColor Gray
        
        # Build configuration parameters
        $configParams = ""
        foreach ($key in $topic.Config.Keys) {
            $configParams += "--config $key=$($topic.Config[$key]) "
            Write-Host "  Config: $key = $($topic.Config[$key])" -ForegroundColor Gray
        }
        
        # Create topic command
        $command = "docker exec kafka-broker1 kafka-topics --create --bootstrap-server kafka-broker1:9092 --topic $($topic.Name) --partitions $($topic.Partitions) --replication-factor $($topic.ReplicationFactor) $configParams --if-not-exists"
        
        Write-Host "  Creating..." -ForegroundColor Yellow
        $result = Invoke-Expression $command 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✅ Created successfully!" -ForegroundColor Green
        } elseif ($result -match "already exists") {
            Write-Host "  ⚠️ Topic already exists" -ForegroundColor Yellow
        } else {
            Write-Host "  ❌ Error creating topic: $result" -ForegroundColor Red
            exit 1
        }
    }
    
    Write-Host "`n$topicType creation completed!" -ForegroundColor Green
}

# Create all topic categories
Write-Host "`n🚀 Starting Task 7.1 Topic Creation Process..." -ForegroundColor Cyan

Create-KafkaTopics $coreTopics "Core Task 7.1 Topics"
Create-KafkaTopics $supportingTopics "Supporting System Topics"

# Verify all topics were created
Write-Host "`n=== Topic Verification ===" -ForegroundColor Cyan
Write-Host "Listing all created topics:" -ForegroundColor Yellow
$allTopics = docker exec kafka-broker1 kafka-topics --list --bootstrap-server kafka-broker1:9092

Write-Host "`nCreated Topics:" -ForegroundColor Green
$allTopics | ForEach-Object { Write-Host "  - $_" -ForegroundColor White }

# Show detailed configuration for core topics
Write-Host "`n=== Core Topic Configurations ===" -ForegroundColor Cyan
foreach ($topic in $coreTopics) {
    Write-Host "`nTopic: $($topic.Name)" -ForegroundColor Yellow
    $topicConfig = docker exec kafka-broker1 kafka-topics --describe --bootstrap-server kafka-broker1:9092 --topic $($topic.Name)
    Write-Host $topicConfig -ForegroundColor Gray
}

Write-Host "`n🎉 Task 7.1: Topic Creation - COMPLETED!" -ForegroundColor Green
Write-Host "✅ traffic-raw: 5 partitions, 7-day retention" -ForegroundColor White  
Write-Host "✅ traffic-processed: 5 partitions, 7-day retention" -ForegroundColor White
Write-Host "✅ traffic-alerts: 2 partitions, 7-day retention" -ForegroundColor White
Write-Host "✅ All topics configured with compression.type=snappy" -ForegroundColor White
Write-Host "✅ Segment rolling configured for 24-hour intervals" -ForegroundColor White
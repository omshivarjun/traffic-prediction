# PowerShell script to start Kafka and related services

# Check if Docker is running
$dockerRunning = docker info 2>$null
if (-not $dockerRunning) {
    Write-Host "Error: Docker is not running. Please start Docker Desktop and try again." -ForegroundColor Red
    exit 1
}

# Define the services to start
$kafkaServices = @(
    "zookeeper",
    "kafka-broker1",
    "schema-registry",
    "kafka-connect",
    "kafka-ui"
)

# Function to check if a service is running
function Test-ServiceRunning($serviceName) {
    $running = docker ps --filter "name=$serviceName" --format "{{.Names}}" 2>$null
    return [bool]$running
}

# Start services
Write-Host "Starting Kafka and related services..." -ForegroundColor Cyan

# Check if services are already running
$allRunning = $true
foreach ($service in $kafkaServices) {
    if (-not (Is-ServiceRunning $service)) {
        $allRunning = $false
        break
    }
}

if ($allRunning) {
    Write-Host "All Kafka services are already running." -ForegroundColor Green
} else {
    # Start the services using docker-compose
    Write-Host "Starting Kafka services using docker-compose..." -ForegroundColor Yellow
    docker-compose up -d $kafkaServices
    
    # Wait for services to start
    Write-Host "Waiting for services to start..." -ForegroundColor Yellow
    $maxRetries = 30
    $retryCount = 0
    $allStarted = $false
    
    while (-not $allStarted -and $retryCount -lt $maxRetries) {
        Start-Sleep -Seconds 5
        $retryCount++
        
        $allStarted = $true
        foreach ($service in $kafkaServices) {
            if (-not (Is-ServiceRunning $service)) {
                $allStarted = $false
                Write-Host "Waiting for $service to start... (Attempt $retryCount/$maxRetries)" -ForegroundColor Yellow
                break
            }
        }
    }
    
    if ($allStarted) {
        Write-Host "All Kafka services started successfully!" -ForegroundColor Green
    } else {
        Write-Host "Error: Not all services started within the timeout period." -ForegroundColor Red
        Write-Host "Please check docker logs for more information:" -ForegroundColor Yellow
        Write-Host "docker-compose logs" -ForegroundColor Yellow
        exit 1
    }
}

# Create Kafka topics if they don't exist
Write-Host "\nCreating Kafka topics if they don't exist..." -ForegroundColor Cyan
& "$PSScriptRoot\create-kafka-topics.ps1"

# Deploy HDFS connector if HDFS is running
if (Is-ServiceRunning "namenode" -and Is-ServiceRunning "hive-metastore") {
    Write-Host "\nDeploying HDFS connector..." -ForegroundColor Cyan
    & "$PSScriptRoot\deploy-hdfs-connector.ps1"
} else {
    Write-Host "\nSkipping HDFS connector deployment as Hadoop services are not running." -ForegroundColor Yellow
    Write-Host "To deploy the HDFS connector later, run: .\scripts\deploy-hdfs-connector.ps1" -ForegroundColor Yellow
}

# Print service access information
Write-Host "\nKafka services are ready to use!" -ForegroundColor Green
Write-Host "\nService access information:" -ForegroundColor Cyan
Write-Host "- Kafka Broker: localhost:9092" -ForegroundColor White
Write-Host "- Schema Registry: http://localhost:8081" -ForegroundColor White
Write-Host "- Kafka Connect: http://localhost:8083" -ForegroundColor White
Write-Host "- Kafka UI: http://localhost:8080" -ForegroundColor White

Write-Host "\nTo verify Kafka topics, run: .\scripts\verify-kafka-setup.ps1" -ForegroundColor Cyan
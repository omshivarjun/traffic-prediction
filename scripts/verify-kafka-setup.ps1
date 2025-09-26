# PowerShell script to verify Kafka setup

# Check if Docker is running
$dockerRunning = docker info 2>$null
if (-not $dockerRunning) {
    Write-Host "Error: Docker is not running. Please start Docker Desktop and try again." -ForegroundColor Red
    exit 1
}

# Check if Kafka broker is running
$kafkaBrokerRunning = docker ps --filter "name=kafka-broker" --format "{{.Names}}" 2>$null
if (-not $kafkaBrokerRunning) {
    Write-Host "Error: Kafka broker is not running. Please start the services using .\scripts\start-kafka-services.ps1" -ForegroundColor Red
    exit 1
}

Write-Host "Verifying Kafka setup..." -ForegroundColor Cyan

# Verify Kafka broker
Write-Host "\nVerifying Kafka broker..." -ForegroundColor Green
docker exec kafka-broker kafka-broker-api-versions --bootstrap-server kafka-broker:9092

# List Kafka topics
Write-Host "\nListing Kafka topics..." -ForegroundColor Green
docker exec kafka-broker kafka-topics --bootstrap-server kafka-broker:9092 --list

# Verify Schema Registry
Write-Host "\nVerifying Schema Registry..." -ForegroundColor Green
try {
    $schemaRegistryStatus = Invoke-RestMethod -Uri "http://localhost:8081/subjects" -Method Get -ErrorAction Stop
    Write-Host "Schema Registry is running. Available subjects:" -ForegroundColor Green
    $schemaRegistryStatus | ForEach-Object { Write-Host "- $_" -ForegroundColor White }
} catch {
    Write-Host "Error connecting to Schema Registry: $_" -ForegroundColor Red
}

# Verify Kafka Connect
Write-Host "\nVerifying Kafka Connect..." -ForegroundColor Green
try {
    $kafkaConnectStatus = Invoke-RestMethod -Uri "http://localhost:8083/connectors" -Method Get -ErrorAction Stop
    Write-Host "Kafka Connect is running. Deployed connectors:" -ForegroundColor Green
    if ($kafkaConnectStatus.Count -eq 0) {
        Write-Host "No connectors deployed yet." -ForegroundColor Yellow
    } else {
        $kafkaConnectStatus | ForEach-Object { Write-Host "- $_" -ForegroundColor White }
    }
} catch {
    Write-Host "Error connecting to Kafka Connect: $_" -ForegroundColor Red
}

# Verify topic details for key topics
Write-Host "\nVerifying topic details for key topics..." -ForegroundColor Green
$keyTopics = @(
    "raw-traffic-events",
    "raw-traffic-incidents",
    "processed-traffic-aggregates",
    "traffic-predictions"
)

foreach ($topic in $keyTopics) {
    Write-Host "\nDetails for topic '$topic':" -ForegroundColor Cyan
    docker exec kafka-broker kafka-topics --bootstrap-server kafka-broker:9092 --describe --topic $topic
}

# Check if HDFS connector is deployed (if Hadoop is running)
$namenodeRunning = docker ps --filter "name=namenode" --format "{{.Names}}" 2>$null
if ($namenodeRunning) {
    Write-Host "\nVerifying HDFS connector status..." -ForegroundColor Green
    try {
        $hdfsConnectorStatus = Invoke-RestMethod -Uri "http://localhost:8083/connectors/hdfs-sink-connector/status" -Method Get -ErrorAction SilentlyContinue
        if ($hdfsConnectorStatus) {
            Write-Host "HDFS connector status:" -ForegroundColor Green
            $hdfsConnectorStatus | ConvertTo-Json -Depth 5
        } else {
            Write-Host "HDFS connector is not deployed. Run .\scripts\deploy-hdfs-connector.ps1 to deploy it." -ForegroundColor Yellow
        }
    } catch {
        Write-Host "HDFS connector is not deployed. Run .\scripts\deploy-hdfs-connector.ps1 to deploy it." -ForegroundColor Yellow
    }
}

Write-Host "\nKafka verification complete!" -ForegroundColor Green
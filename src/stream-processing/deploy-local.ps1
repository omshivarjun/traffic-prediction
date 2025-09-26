# Deploy and run the stream processing application locally

# Check if Node.js is installed
try {
    $nodeVersion = node -v
    Write-Host "Node.js version: $nodeVersion"
} catch {
    Write-Host "Error: Node.js is not installed. Please install Node.js before continuing."
    exit 1
}

# Check if Docker is running and Kafka containers are up
try {
    $kafkaStatus = docker ps --filter "name=kafka-broker1" --format "{{.Status}}"
    if (-not $kafkaStatus) {
        Write-Host "Error: Kafka broker container is not running. Please start the Docker containers first."
        Write-Host "Run: docker-compose up -d"
        exit 1
    }
    Write-Host "Kafka broker is running: $kafkaStatus"
} catch {
    Write-Host "Error: Docker is not running or not installed. Please start Docker before continuing."
    exit 1
}

# Set the current directory to the script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -Path $scriptDir

# Install dependencies if node_modules doesn't exist
if (-not (Test-Path -Path "node_modules")) {
    Write-Host "Installing dependencies..."
    npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Failed to install dependencies."
        exit 1
    }
}

# Build the application
Write-Host "Building the application..."
npm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Failed to build the application."
    exit 1
}

# Deploy Kafka Connect HDFS sink configuration
Write-Host "Deploying Kafka Connect HDFS sink configuration..."
$kafkaConnectUrl = "http://localhost:8083/connectors"
$hdfsConnectorConfig = Get-Content -Path "config/kafka-connect-hdfs-sink.json" -Raw

try {
    # Check if connector already exists
    $existingConnectors = Invoke-RestMethod -Uri $kafkaConnectUrl -Method Get
    
    if ($existingConnectors -contains "traffic-hdfs-sink") {
        # Update existing connector
        Write-Host "Updating existing HDFS sink connector..."
        Invoke-RestMethod -Uri "$kafkaConnectUrl/traffic-hdfs-sink/config" -Method Put -Body $hdfsConnectorConfig -ContentType "application/json"
    } else {
        # Create new connector
        Write-Host "Creating new HDFS sink connector..."
        Invoke-RestMethod -Uri $kafkaConnectUrl -Method Post -Body $hdfsConnectorConfig -ContentType "application/json"
    }
    
    Write-Host "HDFS sink connector deployed successfully."
} catch {
    Write-Host "Warning: Failed to deploy HDFS sink connector. Continuing without it."
    Write-Host "Error: $_"
}

# Start the application
Write-Host "Starting the stream processing application..."
npm start
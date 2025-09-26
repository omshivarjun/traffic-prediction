#!/usr/bin/env powershell
<#
.SYNOPSIS
    Complete METR-LA Traffic Prediction Pipeline Startup Script
    
.DESCRIPTION
    This script starts the entire traffic prediction pipeline:
    1. Docker services (Hadoop, Kafka, Spark, PostgreSQL)
    2. Downloads/prepares METR-LA dataset
    3. Creates Kafka topics
    4. Starts stream processing
    5. Initializes ML training pipeline
    6. Launches prediction service
    7. Starts visualization dashboard

.PARAMETER SkipDockerBuild
    Skip Docker image building and just start existing containers
    
.PARAMETER SkipDatasetDownload
    Skip dataset download if already exists
    
.PARAMETER FastMode
    Start with minimal data for quick testing
    
.PARAMETER CleanStart
    Clean all data and start fresh

.EXAMPLE
    .\start-complete-pipeline.ps1
    .\start-complete-pipeline.ps1 -FastMode
    .\start-complete-pipeline.ps1 -CleanStart
#>

param(
    [switch]$SkipDockerBuild,
    [switch]$SkipDatasetDownload,
    [switch]$FastMode,
    [switch]$CleanStart
)

# Configuration
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# Colors for output
$GREEN = "`e[32m"
$YELLOW = "`e[33m"
$RED = "`e[31m"
$BLUE = "`e[34m"
$NC = "`e[0m"

# Pipeline configuration
$config = @{
    # Docker services
    ComposeFile = "docker-compose.yml"
    Services = @("zookeeper", "kafka-broker1", "schema-registry", "kafka-connect", "namenode", "datanode", "resourcemanager", "nodemanager", "spark-master", "spark-worker", "postgres")
    
    # Kafka configuration
    KafkaBroker = "localhost:9094"
    Topics = @("traffic-events", "processed-traffic-aggregates", "traffic-predictions", "traffic-alerts")
    
    # HDFS configuration  
    HDFSNameNode = "http://localhost:9871"
    HDFSDataPath = "/traffic-data"
    
    # Dataset configuration
    DatasetPath = "data/metr-la"
    SampleSize = if ($FastMode) { 10000 } else { 100000 }
    
    # Service URLs
    SparkMasterUI = "http://localhost:8086"
    KafkaUI = "http://localhost:8085"
    DashboardURL = "http://localhost:3000"
    
    # Process timeouts
    ServiceStartupTimeout = 120
    DataProcessingTimeout = 300
}

function Write-ColorOutput {
    param([string]$Message, [string]$Color = $NC)
    Write-Host "${Color}${Message}${NC}"
}

function Write-StepHeader {
    param([string]$Step, [string]$Description)
    Write-Host ""
    Write-ColorOutput "═══════════════════════════════════════════════════════════════════════════════" $BLUE
    Write-ColorOutput "Step ${Step}: $Description" $BLUE
    Write-ColorOutput "═══════════════════════════════════════════════════════════════════════════════" $BLUE
    Write-Host ""
}

function Test-ServiceHealth {
    param([string]$ServiceName, [string]$URL, [int]$TimeoutSeconds = 30)
    
    Write-ColorOutput "  Checking $ServiceName health..." $YELLOW
    
    $timeout = [datetime]::Now.AddSeconds($TimeoutSeconds)
    
    while ([datetime]::Now -lt $timeout) {
        try {
            $response = Invoke-WebRequest -Uri $URL -TimeoutSec 5 -UseBasicParsing -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                Write-ColorOutput "  ✓ $ServiceName is healthy" $GREEN
                return $true
            }
        }
        catch {
            # Service not ready yet
        }
        
        Start-Sleep -Seconds 2
    }
    
    Write-ColorOutput "  ❌ $ServiceName health check failed" $RED
    return $false
}

function Wait-ForServices {
    Write-ColorOutput "Waiting for all services to be healthy..." $YELLOW
    
    $services = @(
        @{ Name = "HDFS NameNode"; URL = $config.HDFSNameNode },
        @{ Name = "Kafka UI"; URL = $config.KafkaUI },
        @{ Name = "Spark Master"; URL = $config.SparkMasterUI }
    )
    
    $allHealthy = $true
    foreach ($service in $services) {
        if (-not (Test-ServiceHealth -ServiceName $service.Name -URL $service.URL -TimeoutSeconds 60)) {
            $allHealthy = $false
        }
    }
    
    return $allHealthy
}

function Start-DockerServices {
    Write-StepHeader "1" "Starting Docker Services"
    
    # Clean start if requested
    if ($CleanStart) {
        Write-ColorOutput "Performing clean start - removing all containers and volumes..." $YELLOW
        docker-compose -f $config.ComposeFile down -v --remove-orphans
        docker system prune -f
    }
    
    # Check if Docker is running
    try {
        docker ps | Out-Null
        Write-ColorOutput "✓ Docker is running" $GREEN
    }
    catch {
        Write-ColorOutput "❌ Docker is not running. Please start Docker Desktop." $RED
        exit 1
    }
    
    # Build images if needed
    if (-not $SkipDockerBuild) {
        Write-ColorOutput "Building Docker images..." $YELLOW
        docker-compose -f $config.ComposeFile build
    }
    
    # Start services in dependency order
    Write-ColorOutput "Starting core services (Zookeeper, Kafka, HDFS)..." $YELLOW
    docker-compose -f $config.ComposeFile up -d zookeeper kafka-broker1 namenode datanode
    Start-Sleep -Seconds 20
    
    Write-ColorOutput "Starting processing services (Spark, ResourceManager)..." $YELLOW
    docker-compose -f $config.ComposeFile up -d resourcemanager nodemanager spark-master spark-worker
    Start-Sleep -Seconds 15
    
    Write-ColorOutput "Starting supporting services (Schema Registry, Connect, UI)..." $YELLOW
    docker-compose -f $config.ComposeFile up -d schema-registry kafka-connect kafka-ui postgres
    Start-Sleep -Seconds 10
    
    # Wait for services to be healthy
    if (-not (Wait-ForServices)) {
        Write-ColorOutput "❌ Some services failed to start properly" $RED
        Write-ColorOutput "Check service logs with: docker-compose logs [service-name]" $YELLOW
        exit 1
    }
    
    Write-ColorOutput "✅ All Docker services are running and healthy" $GREEN
}

function Initialize-Dataset {
    Write-StepHeader "2" "Preparing METR-LA Dataset"
    
    if ($SkipDatasetDownload -and (Test-Path "$($config.DatasetPath)/metr-la-sample.csv")) {
        Write-ColorOutput "✓ Skipping dataset download - files already exist" $GREEN
        return
    }
    
    # Ensure Python virtual environment
    if (-not (Test-Path ".venv")) {
        Write-ColorOutput "Creating Python virtual environment..." $YELLOW
        python -m venv .venv
    }
    
    # Activate virtual environment and install dependencies
    Write-ColorOutput "Installing Python dependencies..." $YELLOW
    .\.venv\Scripts\python.exe -m pip install --upgrade pip
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    
    # Run dataset preparation
    Write-ColorOutput "Generating METR-LA dataset..." $YELLOW
    $sampleSizeArg = if ($FastMode) { "--max-records 10000" } else { "--max-records 100000" }
    
    .\.venv\Scripts\python.exe scripts/download-metr-la-dataset.py
    
    # Verify dataset was created
    if (Test-Path "$($config.DatasetPath)/metr-la-sample.csv") {
        Write-ColorOutput "✅ METR-LA dataset prepared successfully" $GREEN
    }
    else {
        Write-ColorOutput "❌ Dataset preparation failed" $RED
        exit 1
    }
}

function Initialize-KafkaTopics {
    Write-StepHeader "3" "Setting up Kafka Topics"
    
    Write-ColorOutput "Creating Kafka topics..." $YELLOW
    
    foreach ($topic in $config.Topics) {
        Write-ColorOutput "  Creating topic: $topic" $YELLOW
        
        # Create topic using kafka-topics command inside container
        $createResult = docker exec kafka-broker1 kafka-topics --create `
            --bootstrap-server localhost:9092 `
            --topic $topic `
            --partitions 4 `
            --replication-factor 1 `
            --if-not-exists 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-ColorOutput "  ✓ Topic $topic created/verified" $GREEN
        }
        else {
            Write-ColorOutput "  ❌ Failed to create topic $topic" $RED
            Write-ColorOutput "    $createResult" $RED
        }
    }
    
    # Verify topics exist
    Write-ColorOutput "Verifying topics..." $YELLOW
    $listResult = docker exec kafka-broker1 kafka-topics --list --bootstrap-server localhost:9092
    
    foreach ($topic in $config.Topics) {
        if ($listResult -contains $topic) {
            Write-ColorOutput "  ✓ Topic $topic exists" $GREEN
        }
        else {
            Write-ColorOutput "  ❌ Topic $topic missing" $RED
        }
    }
}

function Start-DataStreaming {
    Write-StepHeader "4" "Starting Data Streaming Pipeline"
    
    # Start Kafka producer for METR-LA data
    Write-ColorOutput "Starting METR-LA Kafka producer..." $YELLOW
    
    $csvFile = "$($config.DatasetPath)/metr-la-sample.csv"
    if (-not (Test-Path $csvFile)) {
        Write-ColorOutput "❌ CSV file not found: $csvFile" $RED
        exit 1
    }
    
    $replaySpeed = if ($FastMode) { "0" } else { "10.0" }
    $maxRecords = if ($FastMode) { "5000" } else { "50000" }
    
    # Start producer in background
    Write-ColorOutput "  Starting producer (replay speed: ${replaySpeed}x, max records: $maxRecords)..." $YELLOW
    
    $producerArgs = @(
        "scripts/metr-la-kafka-producer-enhanced.py"
        "--csv-file", $csvFile
        "--kafka-broker", $config.KafkaBroker
        "--topic", "traffic-events"
        "--replay-speed", $replaySpeed
        "--max-records", $maxRecords
    )
    
    $producerJob = Start-Job -ScriptBlock {
        param($pythonExe, $arguments)
        & $pythonExe @arguments
    } -ArgumentList ".\.venv\Scripts\python.exe", $producerArgs
    
    Write-ColorOutput "  ✓ Producer started (Job ID: $($producerJob.Id))" $GREEN
    
    # Wait a moment for producer to start sending data
    Start-Sleep -Seconds 10
    
    # Verify data is flowing
    Write-ColorOutput "Verifying data flow..." $YELLOW
    $messageCount = docker exec kafka-broker1 kafka-run-class kafka.tools.GetOffsetShell `
        --broker-list localhost:9092 --topic traffic-events --time -1
    
    if ($messageCount -match "\d+") {
        Write-ColorOutput "  ✓ Data is flowing to Kafka" $GREEN
    }
    else {
        Write-ColorOutput "  ⚠ No data detected yet - producer may still be starting" $YELLOW
    }
    
    return $producerJob
}

function Start-SparkStreaming {
    Write-StepHeader "5" "Starting Spark Streaming"
    
    Write-ColorOutput "Starting Spark structured streaming..." $YELLOW
    
    # Submit Spark streaming job
    $sparkArgs = @(
        "spark-submit"
        "--master", "spark://localhost:7077"
        "--packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0"
        "--conf", "spark.sql.adaptive.enabled=true"
        "--conf", "spark.sql.adaptive.coalescePartitions.enabled=true"
        "src/spark/metr_la_streaming.py"
    )
    
    $streamingJob = Start-Job -ScriptBlock {
        param($arguments)
        docker exec spark-master @arguments
    } -ArgumentList $sparkArgs
    
    Write-ColorOutput "  ✓ Spark streaming job submitted (Job ID: $($streamingJob.Id))" $GREEN
    
    return $streamingJob
}

function Start-MLTraining {
    Write-StepHeader "6" "Starting ML Training Pipeline"
    
    Write-ColorOutput "Starting ML model training..." $YELLOW
    
    # Wait for some data to accumulate
    Write-ColorOutput "  Waiting for data accumulation (30 seconds)..." $YELLOW
    Start-Sleep -Seconds 30
    
    # Start ML training job
    $trainingJob = Start-Job -ScriptBlock {
        .\.venv\Scripts\python.exe scripts/ml_training_pipeline.py --config config/ml_training_config.json
    }
    
    Write-ColorOutput "  ✓ ML training started (Job ID: $($trainingJob.Id))" $GREEN
    
    return $trainingJob
}

function Start-PredictionService {
    Write-StepHeader "7" "Starting Prediction Service"
    
    Write-ColorOutput "Starting prediction service..." $YELLOW
    
    # Start prediction service
    $predictionJob = Start-Job -ScriptBlock {
        .\.venv\Scripts\python.exe scripts/prediction_service.py
    }
    
    Write-ColorOutput "  ✓ Prediction service started (Job ID: $($predictionJob.Id))" $GREEN
    
    return $predictionJob
}

function Start-Dashboard {
    Write-StepHeader "8" "Starting Visualization Dashboard"
    
    Write-ColorOutput "Starting Next.js dashboard..." $YELLOW
    
    # Install Node.js dependencies if needed
    if (-not (Test-Path "node_modules")) {
        Write-ColorOutput "  Installing Node.js dependencies..." $YELLOW
        npm install
    }
    
    # Start dashboard in development mode
    $dashboardJob = Start-Job -ScriptBlock {
        npm run dev
    }
    
    Write-ColorOutput "  ✓ Dashboard started (Job ID: $($dashboardJob.Id))" $GREEN
    Write-ColorOutput "  📊 Dashboard will be available at: $($config.DashboardURL)" $BLUE
    
    return $dashboardJob
}

function Show-PipelineStatus {
    Write-StepHeader "STATUS" "Pipeline Status Summary"
    
    Write-ColorOutput "🚀 METR-LA Traffic Prediction Pipeline Status:" $BLUE
    Write-Host ""
    
    # Service URLs
    $services = @{
        "Kafka UI" = $config.KafkaUI
        "HDFS NameNode" = $config.HDFSNameNode  
        "Spark Master" = $config.SparkMasterUI
        "Dashboard" = $config.DashboardURL
    }
    
    foreach ($service in $services.GetEnumerator()) {
        Write-ColorOutput "  📊 $($service.Key): $($service.Value)" $GREEN
    }
    
    Write-Host ""
    Write-ColorOutput "📁 Data Locations:" $BLUE
    Write-ColorOutput "  • CSV Data: $($config.DatasetPath)" $GREEN
    Write-ColorOutput "  • HDFS Path: $($config.HDFSDataPath)" $GREEN
    Write-ColorOutput "  • Kafka Topics: $($config.Topics -join ', ')" $GREEN
    
    Write-Host ""
    Write-ColorOutput "🔧 Management Commands:" $BLUE
    Write-ColorOutput "  • View logs: docker-compose logs -f [service-name]" $GREEN
    Write-ColorOutput "  • Stop pipeline: docker-compose down" $GREEN
    Write-ColorOutput "  • Monitor Kafka: Get-Job | Receive-Job" $GREEN
    
    Write-Host ""
}

function Main {
    Write-ColorOutput "🚀 Starting METR-LA Traffic Prediction Pipeline" $BLUE
    Write-ColorOutput "Configuration: FastMode=$FastMode, CleanStart=$CleanStart" $YELLOW
    Write-Host ""
    
    try {
        # Step 1: Start Docker services
        Start-DockerServices
        
        # Step 2: Prepare dataset
        Initialize-Dataset
        
        # Step 3: Setup Kafka topics
        Initialize-KafkaTopics
        
        # Step 4: Start data streaming
        $producerJob = Start-DataStreaming
        
        # Step 5: Start Spark streaming
        $streamingJob = Start-SparkStreaming
        
        # Step 6: Start ML training
        $trainingJob = Start-MLTraining
        
        # Step 7: Start prediction service
        $predictionJob = Start-PredictionService
        
        # Step 8: Start dashboard
        $dashboardJob = Start-Dashboard
        
        # Show final status
        Show-PipelineStatus
        
        Write-ColorOutput "✅ Pipeline startup completed successfully!" $GREEN
        Write-ColorOutput "   All services are running. Press Ctrl+C to monitor or use the web interfaces." $YELLOW
        
        # Keep script running and show job status
        Write-Host ""
        Write-ColorOutput "Monitoring pipeline jobs... (Press Ctrl+C to exit)" $YELLOW
        
        while ($true) {
            Start-Sleep -Seconds 30
            
            $jobs = @($producerJob, $streamingJob, $trainingJob, $predictionJob, $dashboardJob)
            $runningJobs = $jobs | Where-Object { $_.State -eq "Running" }
            
            Write-ColorOutput "[$(Get-Date -Format 'HH:mm:ss')] Running jobs: $($runningJobs.Count)/$($jobs.Count)" $GREEN
            
            # Check for completed/failed jobs
            foreach ($job in $jobs) {
                if ($job.State -eq "Failed") {
                    Write-ColorOutput "  ❌ Job $($job.Id) failed" $RED
                    Receive-Job -Job $job -ErrorAction SilentlyContinue
                }
                elseif ($job.State -eq "Completed") {
                    Write-ColorOutput "  ✓ Job $($job.Id) completed" $GREEN
                }
            }
        }
        
    }
    catch {
        Write-ColorOutput "❌ Pipeline startup failed: $($_.Exception.Message)" $RED
        Write-ColorOutput "Check logs for detailed error information." $YELLOW
        exit 1
    }
}

# Run main function
Main
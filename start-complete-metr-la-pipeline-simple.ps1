# Complete METR-LA Pipeline Startup Script (Unicode-safe version)
# This script starts the entire pipeline: Docker -> Kafka -> Spark -> ML -> Dashboard

param(
    [switch]$ProductionMode = $false,
    [int]$ProducerSpeedMultiplier = 1,
    [switch]$SkipDataCheck = $false
)

# Configuration
$KAFKA_BROKER = "localhost:9094"
$DatasetPath = "data/processed/metr_la_sample.csv"

# Global job tracking
$global:ProducerJob = $null
$global:SparkJob = $null
$global:MLJob = $null
$global:PredictionJob = $null
$global:DashboardJob = $null

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "METR-LA Complete Pipeline Startup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Register cleanup handler
$null = Register-EngineEvent PowerShell.Exiting -Action {
    Write-Host "Cleaning up background jobs..." -ForegroundColor Yellow
    Stop-AllServices
}

# Function to wait for service readiness
function Wait-ForService {
    param([string]$ServiceName, [string]$Url, [int]$TimeoutSeconds = 120)
    
    Write-Host "Waiting for $ServiceName at $Url..." -ForegroundColor Yellow
    $elapsed = 0
    
    while ($elapsed -lt $TimeoutSeconds) {
        try {
            $response = Invoke-WebRequest -Uri $Url -TimeoutSec 5 -ErrorAction Stop
            Write-Host "OK: $ServiceName is ready!" -ForegroundColor Green
            return $true
        }
        catch {
            Start-Sleep -Seconds 5
            $elapsed += 5
            Write-Host "." -NoNewline
        }
    }
    
    Write-Host "TIMEOUT: $ServiceName failed to start within $TimeoutSeconds seconds" -ForegroundColor Red
    return $false
}

# Function to verify Kafka topics
function Test-KafkaTopics {
    Write-Host "Verifying Kafka topics..." -ForegroundColor Yellow
    
    $topics = @("traffic-events", "processed-traffic-aggregates", "traffic-predictions", "traffic-alerts")
    
    foreach ($topic in $topics) {
        try {
            $result = docker exec kafka-broker1 kafka-topics --bootstrap-server kafka-broker1:9092 --describe --topic $topic 2>$null
            if ($result) {
                Write-Host "OK: Topic '$topic' ready" -ForegroundColor Green
            } else {
                Write-Host "Creating topic: $topic" -ForegroundColor Yellow
                docker exec kafka-broker1 kafka-topics --bootstrap-server kafka-broker1:9092 --create --topic $topic --partitions 3 --replication-factor 1
            }
        }
        catch {
            Write-Host "ERROR: Failed to verify topic $topic" -ForegroundColor Red
        }
    }
}

# Function to prepare dataset
function Initialize-Dataset {
    if ($SkipDataCheck) {
        Write-Host "Skipping dataset check..." -ForegroundColor Yellow
        return
    }
    
    Write-Host "Checking METR-LA dataset..." -ForegroundColor Yellow
    
    if (Test-Path $DatasetPath) {
        Write-Host "OK: Dataset already exists at $DatasetPath" -ForegroundColor Green
    } else {
        Write-Host "Generating sample dataset..." -ForegroundColor Yellow
        
        # Ensure directories exist
        if (-not (Test-Path "data/processed")) {
            New-Item -ItemType Directory -Path "data/processed" -Force | Out-Null
        }
        
        # Generate sample data (CSV only, no Kafka dependency)
        try {
            python scripts/generate-sample-data.py --output $DatasetPath --samples 1000
            Write-Host "OK: Sample dataset created" -ForegroundColor Green
        }
        catch {
            Write-Host "ERROR: Failed to generate dataset: $_" -ForegroundColor Red
            exit 1
        }
    }
}

# Function to start the Kafka producer
function Start-KafkaProducer {
    Write-Host "START: Starting enhanced Kafka producer..." -ForegroundColor Blue
    
    $producerArgs = @(
        "scripts/metr-la-kafka-producer-enhanced.py"
        "--kafka-broker", $KAFKA_BROKER
        "--topic", "traffic-events"
        "--csv-file", "data/processed/metr_la_sample.csv"
        "--replay-speed", $ProducerSpeedMultiplier
    )
    
    if ($ProductionMode) {
        $producerArgs += "--production-mode"
    }
    
    $global:ProducerJob = Start-Job -ScriptBlock {
        param($producerParams)
        & python @producerParams
    } -ArgumentList $producerArgs
    
    Write-Host "OK: Kafka producer started (Job ID: $($global:ProducerJob.Id))" -ForegroundColor Green
}

# Function to start Spark streaming
function Start-SparkStreaming {
    Write-Host "START: Starting Spark streaming application (spark-submit in container)..." -ForegroundColor Blue
    
    $global:SparkJob = Start-Job -ScriptBlock {
        docker exec spark-master spark-submit \
          --master spark://spark-master:7077 \
          --deploy-mode client \
          --conf spark.sql.adaptive.enabled=true \
          --conf spark.sql.shuffle.partitions=8 \
          /opt/spark-apps/spark/metr_la_streaming.py \
          --kafka-broker localhost:9094 \
          --input-topic traffic-events \
          --hdfs-path hdfs://localhost:9001/traffic-data/streaming \
          --checkpoint-path hdfs://localhost:9001/traffic-data/checkpoints/streaming \
          --trigger-interval "30 seconds"
    }
    
    Write-Host "OK: Spark streaming started (Job ID: $($global:SparkJob.Id))" -ForegroundColor Green
}

# Function to start ML training pipeline
function Start-MLPipeline {
    Write-Host "START: Starting ML training pipeline..." -ForegroundColor Blue
    
    Start-Sleep -Seconds 30  # Wait for some data to accumulate
    
    $global:MLJob = Start-Job -ScriptBlock {
        & python scripts/complete-pipeline.py
    }
    
    Write-Host "OK: ML pipeline started (Job ID: $($global:MLJob.Id))" -ForegroundColor Green
}

# Function to start prediction service
function Start-PredictionService {
    Write-Host "START: Starting prediction service..." -ForegroundColor Blue
    
    Start-Sleep -Seconds 60  # Wait for ML models to be ready
    
    $predictionArgs = @(
        "scripts/prediction-service-enhanced.py"
        "--kafka-broker", $KAFKA_BROKER
        "--hdfs-namenode", "hdfs://localhost:9001"
    )
    
    $global:PredictionJob = Start-Job -ScriptBlock {
        param($predictionParams)
        & python @predictionParams
    } -ArgumentList $predictionArgs
    
    Write-Host "OK: Prediction service started (Job ID: $($global:PredictionJob.Id))" -ForegroundColor Green
}

# Function to start Next.js dashboard
function Start-Dashboard {
    Write-Host "START: Starting Next.js dashboard..." -ForegroundColor Blue
    
    $global:DashboardJob = Start-Job -ScriptBlock {
        npm run dev --turbopack
    }
    
    Write-Host "OK: Dashboard started (Job ID: $($global:DashboardJob.Id))" -ForegroundColor Green
    Write-Host "WEB: Dashboard will be available at: http://localhost:3000/dashboard" -ForegroundColor Cyan
}

# Function to display system URLs
function Show-SystemUrls {
    Write-Host ""
    Write-Host "WEB: System URLs:" -ForegroundColor Cyan
    Write-Host "================================" -ForegroundColor Cyan
    Write-Host "Dashboard:          http://localhost:3000/dashboard" -ForegroundColor White
    Write-Host "Kafka UI:           http://localhost:8085" -ForegroundColor White
    Write-Host "HDFS NameNode:      http://localhost:9871" -ForegroundColor White
    Write-Host "Spark Master:       http://localhost:8086" -ForegroundColor White
    Write-Host "YARN ResourceMgr:   http://localhost:8089" -ForegroundColor White
    Write-Host ""
}

# Function to handle cleanup on exit
function Stop-AllServices {
    Write-Host ""
    Write-Host "STOP: Stopping all services..." -ForegroundColor Red
    
    # Stop background jobs
    $jobs = @($global:ProducerJob, $global:SparkJob, $global:MLJob, $global:PredictionJob, $global:DashboardJob)
    foreach ($job in $jobs) {
        if ($job) {
            Stop-Job -Job $job -ErrorAction SilentlyContinue
            Remove-Job -Job $job -ErrorAction SilentlyContinue
        }
    }
    
    # Stop Docker services
    Write-Host "Stopping Docker Compose services..." -ForegroundColor Yellow
    docker-compose down --remove-orphans
    
    Write-Host "OK: All services stopped" -ForegroundColor Green
}

# Main execution
try {
    # Step 1: Start Docker services
    Write-Host "STEP 1: Starting Docker Compose services..." -ForegroundColor Magenta
    docker-compose up -d
    
    # Step 2: Wait for core services
    Write-Host "STEP 2: Waiting for core services..." -ForegroundColor Magenta
    if (-not (Wait-ForService "Kafka UI" "http://localhost:8085" 60)) { exit 1 }
    if (-not (Wait-ForService "HDFS NameNode" "http://localhost:9871" 60)) { exit 1 }
    if (-not (Wait-ForService "Spark Master" "http://localhost:8086" 60)) { exit 1 }
    
    # Step 3: Setup Kafka topics
    Write-Host "STEP 3: Setting up Kafka topics..." -ForegroundColor Magenta
    Test-KafkaTopics
    
    # Step 4: Prepare dataset
    Write-Host "STEP 4: Preparing dataset..." -ForegroundColor Magenta
    Initialize-Dataset
    
    # Step 5: Start data pipeline components
    Write-Host "STEP 5: Starting pipeline components..." -ForegroundColor Magenta
    Start-KafkaProducer
    Start-Sleep -Seconds 10
    
    Start-SparkStreaming
    Start-Sleep -Seconds 15
    
    Start-MLPipeline
    Start-Sleep -Seconds 20
    
    Start-PredictionService
    Start-Sleep -Seconds 10
    
    # Step 6: Start dashboard
    Write-Host "STEP 6: Starting dashboard..." -ForegroundColor Magenta
    Start-Dashboard
    Start-Sleep -Seconds 5
    
    # Display system information
    Show-SystemUrls
    
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "PIPELINE STARTUP COMPLETE!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Press Ctrl+C to stop all services..." -ForegroundColor Yellow
    
    # Keep script running
    try {
        while ($true) {
            Start-Sleep -Seconds 30
            
            # Basic health check
            $runningJobs = Get-Job | Where-Object { $_.State -eq "Running" }
            Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Active jobs: $($runningJobs.Count)" -ForegroundColor Gray
        }
    }
    catch [System.Management.Automation.PipelineStoppedException] {
        Write-Host "Pipeline stopped by user" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
finally {
    Stop-AllServices
}
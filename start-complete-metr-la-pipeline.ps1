#!/usr/bin/env pwsh

# METR-LA Complete Pipeline Startup Script
# This script orchestrates the entire traffic prediction pipeline

param(
    [switch]$SkipDataDownload = $false,
    [switch]$ProductionMode = $false,
    [string]$DatasetPath = "data/raw/metr-la.h5",
    [int]$ProducerSpeedMultiplier = 1
)

$ErrorActionPreference = "Stop"

Write-Host "🚦 METR-LA Traffic Prediction Pipeline Startup" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

# Configuration
$KAFKA_BROKER = "localhost:9094"
$HDFS_NAMENODE = "localhost:9871"
$SPARK_MASTER = "spark://localhost:7077"
$KAFKA_TOPICS = @("traffic-events", "processed-traffic-aggregates", "traffic-predictions", "traffic-alerts")

# Function to check if a service is running
function Test-ServiceHealth {
    param($ServiceName, $Port, $Path = "/")
    
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$Port$Path" -Method GET -TimeoutSec 5 -ErrorAction SilentlyContinue
        return $response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

# Function to wait for service to be ready
function Wait-ForService {
    param($ServiceName, $Port, $Path = "/", $MaxWaitSeconds = 60)
    
    Write-Host "⏳ Waiting for $ServiceName to be ready..." -ForegroundColor Yellow
    $elapsed = 0
    
    while ($elapsed -lt $MaxWaitSeconds) {
        if (Test-ServiceHealth -ServiceName $ServiceName -Port $Port -Path $Path) {
            Write-Host "✅ $ServiceName is ready!" -ForegroundColor Green
            return $true
        }
        Start-Sleep -Seconds 2
        $elapsed += 2
        Write-Host "." -NoNewline -ForegroundColor Yellow
    }
    
    Write-Host ""
    Write-Host "❌ $ServiceName failed to start within $MaxWaitSeconds seconds" -ForegroundColor Red
    return $false
}

# Function to create Kafka topics
function Initialize-KafkaTopics {
    Write-Host "📋 Creating Kafka topics..." -ForegroundColor Blue
    
    foreach ($topic in $KAFKA_TOPICS) {
        try {
            $result = docker exec -it kafka kafka-topics --create --topic $topic --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1 --if-not-exists 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Host "✅ Topic '$topic' ready" -ForegroundColor Green
            } else {
                Write-Host "⚠️ Topic '$topic' might already exist" -ForegroundColor Yellow
            }
        }
        catch {
            Write-Host "❌ Failed to create topic '$topic': $_" -ForegroundColor Red
        }
    }
}

# Function to download and prepare dataset
function Initialize-Dataset {
    param($SkipDownload = $false)
    
    if ($SkipDownload) {
        Write-Host "⏭️ Skipping dataset download" -ForegroundColor Yellow
        return
    }
    
    Write-Host "📊 Preparing METR-LA dataset..." -ForegroundColor Blue
    
    if (-not (Test-Path $DatasetPath)) {
        Write-Host "⬇️ Downloading METR-LA dataset..." -ForegroundColor Blue
        & python scripts/download-metr-la-dataset.py
    } else {
        Write-Host "✅ Dataset already exists at $DatasetPath" -ForegroundColor Green
    }
    
    # Generate sample CSV for Kafka producer
    Write-Host "🔄 Generating CSV for Kafka producer..." -ForegroundColor Blue
    & python scripts/generate-metr-la-data.py --output-format csv --sample-size 10000
}

# Function to start Docker services
function Start-DockerServices {
    Write-Host "🐳 Starting Docker services..." -ForegroundColor Blue
    
    # Start core infrastructure
    docker-compose up -d zookeeper kafka schema-registry
    Wait-ForService -ServiceName "Kafka" -Port 9094 -MaxWaitSeconds 60
    
    # Start Hadoop ecosystem
    docker-compose up -d namenode datanode resourcemanager nodemanager historyserver
    Wait-ForService -ServiceName "HDFS NameNode" -Port 9871 -MaxWaitSeconds 90
    
    # Start Spark cluster
    docker-compose up -d spark-master spark-worker
    Wait-ForService -ServiceName "Spark Master" -Port 8086 -MaxWaitSeconds 60
    
    # Start additional services
    docker-compose up -d kafka-connect kafka-ui
    Wait-ForService -ServiceName "Kafka UI" -Port 8085 -MaxWaitSeconds 30
}

# Function to start the Kafka producer
function Start-KafkaProducer {
    Write-Host "🚀 Starting enhanced Kafka producer..." -ForegroundColor Blue
    
    $producerArgs = @(
        "scripts/metr-la-kafka-producer-enhanced.py"
        "--kafka-broker", $KAFKA_BROKER
        "--topic", "traffic-events"
        "--data-file", "data/processed/metr_la_sample.csv"
        "--speed-multiplier", $ProducerSpeedMultiplier
    )
    
    if ($ProductionMode) {
        $producerArgs += "--production-mode"
    }
    
    $global:ProducerJob = Start-Job -ScriptBlock {
        param($producerParams)
        & python @producerParams
    } -ArgumentList $producerArgs
    
    Write-Host "✅ Kafka producer started (Job ID: $($global:ProducerJob.Id))" -ForegroundColor Green
}

# Function to start Spark streaming
function Start-SparkStreaming {
    Write-Host "⚡ Starting Spark streaming application..." -ForegroundColor Blue
    
    $sparkArgs = @(
        "src/spark/metr_la_streaming.py"
        "--kafka-brokers", $KAFKA_BROKER
        "--hdfs-url", "hdfs://localhost:9001"
        "--checkpoint-location", "hdfs://localhost:9001/checkpoints/metr-la-streaming"
    )
    
    $global:SparkJob = Start-Job -ScriptBlock {
        param($sparkParams)
        & python @sparkParams
    } -ArgumentList $sparkArgs
    
    Write-Host "✅ Spark streaming started (Job ID: $($global:SparkJob.Id))" -ForegroundColor Green
}

# Function to start ML training pipeline
function Start-MLPipeline {
    Write-Host "🤖 Starting ML training pipeline..." -ForegroundColor Blue
    
    Start-Sleep -Seconds 30  # Wait for some data to accumulate
    
    $mlArgs = @(
        "scripts/complete-pipeline.py"
        "--mode", "training"
        "--hdfs-url", "hdfs://localhost:9001"
        "--model-output-path", "hdfs://localhost:9001/models/traffic-prediction"
    )
    
    $global:MLJob = Start-Job -ScriptBlock {
        param($mlParams)
        & python @mlParams
    } -ArgumentList $mlArgs
    
    Write-Host "✅ ML pipeline started (Job ID: $($global:MLJob.Id))" -ForegroundColor Green
}

# Function to start prediction service
function Start-PredictionService {
    Write-Host "🔮 Starting prediction service..." -ForegroundColor Blue
    
    Start-Sleep -Seconds 60  # Wait for ML models to be ready
    
    $predictionArgs = @(
        "scripts/prediction-service-enhanced.py"
        "--kafka-broker", $KAFKA_BROKER
        "--hdfs-url", "hdfs://localhost:9001"
        "--model-path", "hdfs://localhost:9001/models/traffic-prediction"
        "--output-topic", "traffic-predictions"
    )
    
    $global:PredictionJob = Start-Job -ScriptBlock {
        param($predictionParams)
        & python @predictionParams
    } -ArgumentList $predictionArgs
    
    Write-Host "✅ Prediction service started (Job ID: $($global:PredictionJob.Id))" -ForegroundColor Green
}

# Function to start Next.js dashboard
function Start-Dashboard {
    Write-Host "📈 Starting Next.js dashboard..." -ForegroundColor Blue
    
    $global:DashboardJob = Start-Job -ScriptBlock {
        npm run dev --turbopack
    }
    
    Write-Host "✅ Dashboard started (Job ID: $($global:DashboardJob.Id))" -ForegroundColor Green
    Write-Host "🌐 Dashboard will be available at: http://localhost:3000/dashboard" -ForegroundColor Cyan
}

# Function to monitor system health
function Start-HealthMonitor {
    Write-Host "🔍 Starting health monitor..." -ForegroundColor Blue
    
    $global:HealthJob = Start-Job -ScriptBlock {
        while ($true) {
            $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
            
            # Check Docker containers
            $containers = docker ps --format "table {{.Names}}\t{{.Status}}" | Select-Object -Skip 1
            
            Write-Host "[$timestamp] Container Status:" -ForegroundColor Cyan
            foreach ($container in $containers) {
                Write-Host "  $container" -ForegroundColor White
            }
            
            Start-Sleep -Seconds 30
        }
    }
    
    Write-Host "✅ Health monitor started (Job ID: $($global:HealthJob.Id))" -ForegroundColor Green
}

# Function to display system URLs
function Show-SystemUrls {
    Write-Host ""
    Write-Host "🌐 System URLs:" -ForegroundColor Cyan
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
    $jobs = @($global:ProducerJob, $global:SparkJob, $global:MLJob, $global:PredictionJob, $global:DashboardJob, $global:HealthJob)
    foreach ($job in $jobs) {
        if ($job) {
            Stop-Job -Job $job -ErrorAction SilentlyContinue
            Remove-Job -Job $job -ErrorAction SilentlyContinue
        }
    }
    
    # Stop Docker services
    Write-Host "🐳 Stopping Docker services..." -ForegroundColor Yellow
    docker-compose down
    
    Write-Host "✅ All services stopped" -ForegroundColor Green
}

# Main execution
try {
    # Register cleanup handler
    Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action { Stop-AllServices }
    
    # Step 1: Start Docker infrastructure
    Start-DockerServices
    
    # Step 2: Initialize Kafka topics
    Initialize-KafkaTopics
    
    # Step 3: Prepare dataset
    Initialize-Dataset -SkipDownload:$SkipDataDownload
    
    # Step 4: Start data pipeline components
    Start-KafkaProducer
    Start-SparkStreaming
    Start-MLPipeline
    Start-PredictionService
    
    # Step 5: Start dashboard
    Start-Dashboard
    
    # Step 6: Start monitoring
    Start-HealthMonitor
    
    # Display system information
    Show-SystemUrls
    
    Write-Host ""
    Write-Host "🎉 METR-LA Traffic Prediction Pipeline is now running!" -ForegroundColor Green
    Write-Host "Press Ctrl+C to stop all services" -ForegroundColor Yellow
    Write-Host ""
    
    # Keep script running
    while ($true) {
        # Check job status
        $runningJobs = Get-Job | Where-Object { $_.State -eq "Running" }
        Write-Host "Active jobs: $($runningJobs.Count)" -ForegroundColor Blue
        
        Start-Sleep -Seconds 60
    }
}
catch {
    Write-Host "❌ Error occurred: $_" -ForegroundColor Red
    Stop-AllServices
    exit 1
}
finally {
    Stop-AllServices
}
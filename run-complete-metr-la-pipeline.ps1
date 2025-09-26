#!/usr/bin/env powershell
<#
.SYNOPSIS
    Complete METR-LA Traffic Prediction Pipeline Orchestrator
    
.DESCRIPTION
    Orchestrates the complete pipeline workflow:
    CSV → Kafka Producer → Spark Streaming → HDFS → ML Training → Predictions → Visualization
    
.EXAMPLE
    .\run-complete-metr-la-pipeline.ps1
#>

param(
    [string]$CsvFile = "data\processed\metr_la_sample.csv",
    [int]$MaxRecords = 10000,
    [float]$ReplaySpeed = 10.0,
    [switch]$SkipTraining,
    [switch]$Debug,
    [switch]$NoCleanup
)

# Set error action preference
$ErrorActionPreference = "Stop"

# Colors for output
$Red = "`e[31m"
$Green = "`e[32m"
$Yellow = "`e[33m"
$Blue = "`e[34m"
$Reset = "`e[0m"

function Write-Status {
    param([string]$Message, [string]$Color = $Green)
    Write-Host "${Color}[$(Get-Date -Format 'HH:mm:ss')] $Message${Reset}"
}

function Write-Error {
    param([string]$Message)
    Write-Host "${Red}[$(Get-Date -Format 'HH:mm:ss')] ERROR: $Message${Reset}"
}

function Write-Warning {
    param([string]$Message)
    Write-Host "${Yellow}[$(Get-Date -Format 'HH:mm:ss')] WARNING: $Message${Reset}"
}

function Write-Info {
    param([string]$Message)
    Write-Host "${Blue}[$(Get-Date -Format 'HH:mm:ss')] INFO: $Message${Reset}"
}

function Test-ServiceHealth {
    param([string]$ServiceName, [string]$Url, [int]$TimeoutSec = 30)
    
    try {
        $response = Invoke-WebRequest -Uri $Url -Method GET -TimeoutSec $TimeoutSec -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Write-Status "✅ $ServiceName is healthy"
            return $true
        }
    }
    catch {
        Write-Warning "❌ $ServiceName health check failed: $($_.Exception.Message)"
        return $false
    }
    return $false
}

function Wait-ForService {
    param([string]$ServiceName, [string]$Url, [int]$MaxAttempts = 30)
    
    Write-Info "Waiting for $ServiceName to be ready..."
    for ($i = 1; $i -le $MaxAttempts; $i++) {
        if (Test-ServiceHealth -ServiceName $ServiceName -Url $Url) {
            return $true
        }
        Start-Sleep -Seconds 2
    }
    
    Write-Error "$ServiceName failed to become ready after $MaxAttempts attempts"
    return $false
}

function Start-Pipeline {
    Write-Status "🚀 Starting Complete METR-LA Traffic Prediction Pipeline"
    Write-Info "Pipeline Configuration:"
    Write-Info "  CSV File: $CsvFile"
    Write-Info "  Max Records: $MaxRecords"
    Write-Info "  Replay Speed: ${ReplaySpeed}x"
    Write-Info "  Skip Training: $SkipTraining"
    Write-Info "  Debug Mode: $Debug"
    
    # Step 1: Verify all services are running
    Write-Status "📋 Step 1: Verifying Infrastructure Services"
    
    $services = @(
        @{Name="Kafka"; Url="http://localhost:9094"},
        @{Name="HDFS NameNode"; Url="http://localhost:9871"},
        @{Name="Spark Master"; Url="http://localhost:8086"},
        @{Name="Schema Registry"; Url="http://localhost:8082"},
        @{Name="PostgreSQL"; Url="http://localhost:5433"; Optional=$true}
    )
    
    $healthyServices = 0
    foreach ($service in $services) {
        if (Test-ServiceHealth -ServiceName $service.Name -Url $service.Url) {
            $healthyServices++
        } elseif (-not $service.Optional) {
            Write-Error "Critical service $($service.Name) is not healthy. Please start all services first."
            return $false
        }
    }
    
    Write-Status "✅ $healthyServices/$($services.Count) services are healthy"
    
    # Step 2: Verify CSV file exists
    Write-Status "📋 Step 2: Verifying Data Source"
    if (-not (Test-Path $CsvFile)) {
        Write-Error "CSV file not found: $CsvFile"
        return $false
    }
    
    $csvInfo = Get-Item $CsvFile
    Write-Info "CSV File: $($csvInfo.FullName) (Size: $([math]::Round($csvInfo.Length/1MB, 2)) MB)"
    
    # Step 3: Create Kafka topics
    Write-Status "📋 Step 3: Setting up Kafka Topics"
    try {
        # Check if we can create topics using docker exec
        $topics = @("traffic-events", "traffic-aggregates", "traffic-predictions")
        foreach ($topic in $topics) {
            Write-Info "Creating topic: $topic"
            docker exec kafka-broker1 kafka-topics --create --topic $topic --partitions 3 --replication-factor 1 --bootstrap-server localhost:9092 --if-not-exists 2>$null
        }
        Write-Status "✅ Kafka topics configured"
    }
    catch {
        Write-Warning "Could not create Kafka topics automatically. They may already exist."
    }
    
    # Step 4: Start Kafka Producer (using Docker-based producer)
    Write-Status "📋 Step 4: Starting Kafka Producer (CSV → Kafka)"
    $producerArgs = @(
        "scripts\metr_la_docker_producer.py",
        "--csv-file", $CsvFile,
        "--topic", "traffic-events",
        "--batch-size", "50"
    )
    
    if ($MaxRecords -gt 0) {
        $producerArgs += @("--max-records", $MaxRecords)
    }
    
    Write-Info "Running Kafka Producer..."
    try {
        python @producerArgs
        if ($LASTEXITCODE -eq 0) {
            Write-Status "✅ Kafka Producer completed successfully"
        } else {
            Write-Error "Kafka Producer failed with exit code: $LASTEXITCODE"
            return $false
        }
    }
    catch {
        Write-Error "Kafka Producer failed: $_"
        return $false
    }
    
    # Step 5: Start Spark Streaming Consumer
    Write-Status "📋 Step 5: Starting Spark Streaming Consumer (Kafka → HDFS)"
    $sparkStreamingArgs = @(
        "src\spark\metr_la_streaming_consumer.py",
        "--kafka-broker", "kafka-broker1:9092",
        "--kafka-topic", "traffic-events"
    )
    
    if ($Debug) {
        $sparkStreamingArgs += "--debug"
    }
    
    # Submit Spark job
    $sparkSubmitJob = Start-Job -ScriptBlock {
        param($Args, $Debug)
        Set-Location $using:PWD
        
        # Use docker exec to submit to Spark cluster
        $sparkCmd = @(
            "docker", "exec", "spark-master",
            "spark-submit",
            "--master", "spark://spark-master:7077",
            "--packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0",
            "/opt/bitnami/spark/work-dir/src/spark/metr_la_streaming_consumer.py"
        ) + $Args
        
        if ($Debug) {
            Write-Host "Executing: $($sparkCmd -join ' ')"
        }
        
        & $sparkCmd[0] $sparkCmd[1..($sparkCmd.Length-1)]
    } -ArgumentList $sparkStreamingArgs, $Debug
    
    Write-Info "Spark Streaming Consumer started (Job ID: $($sparkSubmitJob.Id))"
    Start-Sleep -Seconds 10
    
    # Step 6: ML Training (if not skipped)
    if (-not $SkipTraining) {
        Write-Status "📋 Step 6: Starting ML Training Pipeline"
        Start-Sleep -Seconds 30  # Wait for some data to accumulate
        
        $mlTrainingJob = Start-Job -ScriptBlock {
            Set-Location $using:PWD
            
            # Use docker exec to submit ML training job
            docker exec spark-master spark-submit `
                --master spark://spark-master:7077 `
                --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 `
                /opt/bitnami/spark/work-dir/src/ml/metr_la_ml_training.py
        }
        
        Write-Info "ML Training started (Job ID: $($mlTrainingJob.Id))"
        
        # Wait for training to complete (or timeout after 10 minutes)
        $trainingResult = Wait-Job -Job $mlTrainingJob -Timeout 600
        if ($trainingResult) {
            Write-Status "✅ ML Training completed"
        } else {
            Write-Warning "ML Training is still running (continuing with pipeline)"
        }
    } else {
        Write-Info "Skipping ML Training as requested"
    }
    
    # Step 7: Start Prediction Pipeline
    Write-Status "📋 Step 7: Starting Prediction Pipeline"
    Start-Sleep -Seconds 10
    
    $predictionJob = Start-Job -ScriptBlock {
        param($Debug)
        Set-Location $using:PWD
        
        $args = @(
            "--kafka-broker", "kafka-broker1:9092"
        )
        
        if ($Debug) {
            $args += "--debug"
        }
        
        # Use docker exec to submit prediction job
        docker exec spark-master spark-submit `
            --master spark://spark-master:7077 `
            --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 `
            /opt/bitnami/spark/work-dir/src/ml/metr_la_prediction_pipeline.py @args
    } -ArgumentList $Debug
    
    Write-Info "Prediction Pipeline started (Job ID: $($predictionJob.Id))"
    
    # Step 8: Start Next.js Dashboard
    Write-Status "📋 Step 8: Starting Visualization Dashboard"
    
    # Check if Next.js is already running
    $nextjsRunning = $false
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:3001" -Method GET -TimeoutSec 5 -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            $nextjsRunning = $true
            Write-Info "Next.js dashboard is already running on http://localhost:3001"
        }
    }
    catch {
        # Next.js not running, start it
    }
    
    if (-not $nextjsRunning) {
        $nextjsJob = Start-Job -ScriptBlock {
            Set-Location $using:PWD
            npm run dev
        }
        Write-Info "Next.js Dashboard started (Job ID: $($nextjsJob.Id))"
        
        # Wait for Next.js to be ready
        Start-Sleep -Seconds 10
        if (Wait-ForService -ServiceName "Next.js Dashboard" -Url "http://localhost:3001" -MaxAttempts 15) {
            Write-Status "✅ Dashboard is ready at http://localhost:3001"
        }
    }
    
    # Step 9: Monitor Pipeline
    Write-Status "📋 Step 9: Pipeline Running - Monitoring"
    Write-Status "🎉 Complete METR-LA Pipeline is now running!"
    Write-Info ""
    Write-Info "🌐 Access Points:"
    Write-Info "  Dashboard:      http://localhost:3001/dashboard"
    Write-Info "  Kafka UI:       http://localhost:8085"
    Write-Info "  HDFS:          http://localhost:9871"
    Write-Info "  Spark Master:   http://localhost:8086"
    Write-Info ""
    Write-Info "📊 Data Flow:"
    Write-Info "  1. CSV → Kafka Producer → traffic-events topic"
    Write-Info "  2. Kafka → Spark Streaming → HDFS (aggregated data)"
    Write-Info "  3. HDFS → ML Training → Trained models"
    Write-Info "  4. Streaming data → Prediction Pipeline → traffic-predictions topic"
    Write-Info "  5. Dashboard → Real-time visualization with heatmaps"
    Write-Info ""
    
    # Monitor jobs
    $monitoringDuration = 300  # 5 minutes
    $startTime = Get-Date
    
    Write-Info "Monitoring pipeline for $($monitoringDuration/60) minutes..."
    Write-Info "Press Ctrl+C to stop the pipeline"
    
    try {
        while (((Get-Date) - $startTime).TotalSeconds -lt $monitoringDuration) {
            Start-Sleep -Seconds 30
            
            # Check job status
            $activeJobs = Get-Job | Where-Object { $_.State -eq "Running" }
            Write-Info "Active pipeline jobs: $($activeJobs.Count)"
            
            if ($Debug) {
                foreach ($job in $activeJobs) {
                    $jobOutput = Receive-Job -Job $job -Keep
                    if ($jobOutput) {
                        Write-Host "Job $($job.Id) output: $($jobOutput[-1])"
                    }
                }
            }
        }
    }
    catch {
        Write-Warning "Monitoring interrupted by user"
    }
    
    Write-Status "✅ Pipeline monitoring completed"
    
    # Cleanup option
    if (-not $NoCleanup) {
        Write-Info ""
        $cleanup = Read-Host "Stop all pipeline jobs? (y/N)"
        if ($cleanup -eq 'y' -or $cleanup -eq 'Y') {
            Write-Status "🛑 Stopping pipeline jobs..."
            Get-Job | Stop-Job
            Get-Job | Remove-Job -Force
            Write-Status "✅ Pipeline jobs stopped"
        } else {
            Write-Info "Pipeline jobs are still running in the background"
            Write-Info "Use 'Get-Job' to check status and 'Stop-Job' to stop them"
        }
    }
    
    return $true
}

# Main execution
try {
    Write-Host "${Blue}╔══════════════════════════════════════════════════════════════╗${Reset}"
    Write-Host "${Blue}║              METR-LA Traffic Prediction Pipeline             ║${Reset}"
    Write-Host "${Blue}║                     Complete Workflow                        ║${Reset}"
    Write-Host "${Blue}╚══════════════════════════════════════════════════════════════╝${Reset}"
    Write-Host ""
    
    $success = Start-Pipeline
    
    if ($success) {
        Write-Status "🎉 Pipeline execution completed successfully!"
        exit 0
    } else {
        Write-Error "Pipeline execution failed"
        exit 1
    }
}
catch {
    Write-Error "Pipeline execution failed with error: $($_.Exception.Message)"
    Write-Error "Stack trace: $($_.ScriptStackTrace)"
    exit 1
}
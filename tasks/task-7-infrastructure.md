# Task 7: Infrastructure & Operations

## Overview
Complete infrastructure setup, automation, monitoring, and operational procedures for the traffic prediction pipeline.

**Status**: Partially Complete  
**Dependencies**: None (foundational infrastructure)  
**Priority**: Critical

**Current State**:
- ✅ Docker Compose configured (10 services)
- ✅ Kafka topics created (5 topics with proper partitioning)
- ✅ Basic health checks working
- ⏳ HDFS directory structure needs setup
- ⏳ Monitoring dashboards need configuration
- ⏳ Startup automation needs enhancement

---

## Subtask 7.1: Docker Services Verification

**Status**: Complete ✅

### Current Docker Services (10 containers)

1. **zookeeper** - Kafka coordination
2. **kafka-broker1** - Kafka broker
3. **schema-registry** - Avro schema management
4. **kafka-connect** - HDFS connector
5. **postgres** - Dashboard database
6. **namenode** - HDFS namenode
7. **datanode** - HDFS datanode
8. **spark-master** - Spark cluster master
9. **spark-worker** - Spark worker nodes
10. **stream-processor** - Node.js stream processing service

### Verification Commands

```powershell
# Check all services running
docker-compose ps

# Expected output: All services "Up" and "healthy"
```

### Health Check Endpoints

- **Stream Processor**: http://localhost:3001/health
- **Kafka UI**: http://localhost:8080 (if configured)
- **HDFS NameNode**: http://localhost:9870
- **YARN ResourceManager**: http://localhost:8088
- **Spark Master**: http://localhost:8080 (if configured)
- **Schema Registry**: http://localhost:8082

### Validation Complete
- [x] All 10 services running
- [x] Health checks passing
- [x] Ports accessible

---

## Subtask 7.2: Kafka Topics Configuration

**Status**: Complete ✅

### Topics Created

```powershell
# Verify topics exist
docker exec kafka-broker1 kafka-topics --bootstrap-server localhost:9092 --list
```

**Expected Topics**:
1. **traffic-raw** - 5 partitions (raw CSV data)
2. **traffic-events** - 4 partitions (processed aggregates)
3. **traffic-predictions** - 4 partitions (ML predictions)
4. **processed-traffic-aggregates** - 4 partitions
5. **traffic-alerts** - 4 partitions

### Topic Details

```powershell
# Describe traffic-raw topic
docker exec kafka-broker1 kafka-topics `
  --bootstrap-server localhost:9092 `
  --describe `
  --topic traffic-raw
```

### Retention Configuration

```properties
# config/kafka.properties
retention.ms=604800000        # 7 days
segment.ms=86400000           # 1 day
compression.type=snappy
max.message.bytes=1048576     # 1 MB
```

### Validation Complete
- [x] All 5 topics exist
- [x] Partitions correct (traffic-raw: 5, others: 4)
- [x] Retention policies set
- [x] Compression enabled

---

## Subtask 7.3: HDFS Directory Structure Setup

**Status**: Not Started

### Required Directory Structure

```
/traffic-data/
├── raw/                              # Raw CSV data
│   └── metr-la/
│       └── year=2024/
│           └── month=09/
│               └── day=19/
│                   └── data.csv
│
├── processed/                        # Stream-processed data
│   └── aggregates/
│       └── year=2024/
│           └── month=09/
│               └── day=19/
│                   └── hour=14/
│                       └── part-00000.parquet
│
├── ml-features/                      # Engineered features
│   └── year=2024/
│       └── month=09/
│           └── day=19/
│               └── features.parquet
│
├── models/                           # Trained ML models
│   ├── random_forest/
│   │   └── 2024-09-19_14-30-00/
│   │       ├── model/
│   │       ├── metadata.json
│   │       └── feature_importance.json
│   ├── gradient_boosted_trees/
│   └── linear_regression/
│
├── predictions/                      # Real-time predictions
│   └── year=2024/
│       └── month=09/
│           └── day=19/
│               └── hour=14/
│                   └── predictions.parquet
│
└── checkpoints/                      # Spark streaming checkpoints
    ├── feature-engineering/
    ├── prediction-service/
    └── stream-processor/
```

### Setup Script

```powershell
# scripts/setup-hdfs-directories.ps1

Write-Host "Setting up HDFS directory structure..." -ForegroundColor Cyan

$directories = @(
    "/traffic-data",
    "/traffic-data/raw/metr-la",
    "/traffic-data/processed/aggregates",
    "/traffic-data/ml-features",
    "/traffic-data/models/random_forest",
    "/traffic-data/models/gradient_boosted_trees",
    "/traffic-data/models/linear_regression",
    "/traffic-data/models/preprocessing",
    "/traffic-data/predictions",
    "/traffic-data/checkpoints/feature-engineering",
    "/traffic-data/checkpoints/prediction-service",
    "/traffic-data/checkpoints/stream-processor"
)

foreach ($dir in $directories) {
    Write-Host "Creating $dir..." -NoNewline
    
    docker exec namenode hadoop fs -mkdir -p $dir 2>&1 | Out-Null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host " ✓" -ForegroundColor Green
    } else {
        Write-Host " ✗ Failed" -ForegroundColor Red
    }
}

# Set permissions
Write-Host "`nSetting permissions..." -ForegroundColor Cyan
docker exec namenode hadoop fs -chmod -R 777 /traffic-data

# Verify structure
Write-Host "`nVerifying directory structure..." -ForegroundColor Cyan
docker exec namenode hadoop fs -ls -R /traffic-data

Write-Host "`n✓ HDFS directory structure setup complete!" -ForegroundColor Green
```

### Validation Criteria
- [ ] All directories created in HDFS
- [ ] Permissions set correctly (777 for development)
- [ ] Accessible from Spark jobs
- [ ] Accessible from stream processor

---

## Subtask 7.4: Management UIs Configuration

**Status**: Partially Complete

### HDFS NameNode UI

**URL**: http://localhost:9870  
**Status**: ✅ Working

**Features**:
- Browse HDFS file system
- View datanode status
- Monitor storage usage
- Check replication status

### YARN ResourceManager UI

**URL**: http://localhost:8088  
**Status**: ✅ Working

**Features**:
- Monitor Spark applications
- View application logs
- Track resource allocation
- Check job history

### Kafka UI Setup

**Add to docker-compose.yml**:
```yaml
  kafka-ui:
    image: provectuslabs/kafka-ui:latest
    container_name: kafka-ui
    ports:
      - "8080:8080"
    environment:
      KAFKA_CLUSTERS_0_NAME: local
      KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS: kafka-broker1:9092
      KAFKA_CLUSTERS_0_SCHEMAREGISTRY: http://schema-registry:8082
    depends_on:
      - kafka-broker1
      - schema-registry
```

**URL**: http://localhost:8080  
**Features**:
- Browse topics and messages
- View consumer groups and lag
- Monitor broker health
- Manage schemas

### Schema Registry UI

**URL**: http://localhost:8082  
**Status**: ✅ Working

**Endpoints**:
- List schemas: `http://localhost:8082/subjects`
- Get schema: `http://localhost:8082/subjects/{subject}/versions/latest`

### Spark Master UI

**Configure in docker-compose.yml**:
```yaml
  spark-master:
    # ... existing config
    ports:
      - "7077:7077"   # Spark submit
      - "8081:8080"   # Web UI
    environment:
      - SPARK_MASTER_WEBUI_PORT=8080
```

**URL**: http://localhost:8081  
**Features**:
- Monitor running applications
- View worker nodes
- Check executor logs
- Resource utilization

### Validation Criteria
- [ ] HDFS UI accessible and showing datanodes
- [ ] YARN UI showing cluster resources
- [ ] Kafka UI installed and showing topics
- [ ] Schema Registry accessible
- [ ] Spark UI showing master and workers

---

## Subtask 7.5: Comprehensive Health Check System

**Status**: Not Started

### Health Check Script

```powershell
# scripts/health-check.ps1

param(
    [switch]$Detailed,
    [switch]$Continuous
)

function Test-ServiceHealth {
    param(
        [string]$ServiceName,
        [string]$Endpoint,
        [int]$ExpectedStatus = 200
    )
    
    try {
        $response = Invoke-WebRequest -Uri $Endpoint -TimeoutSec 5 -UseBasicParsing
        $status = if ($response.StatusCode -eq $ExpectedStatus) { "✓" } else { "✗" }
        $color = if ($response.StatusCode -eq $ExpectedStatus) { "Green" } else { "Red" }
        
        Write-Host "$status $ServiceName" -ForegroundColor $color
        
        if ($Detailed) {
            Write-Host "  Status: $($response.StatusCode)" -ForegroundColor Gray
            if ($response.Content) {
                $content = $response.Content | ConvertFrom-Json
                Write-Host "  Details: $($content | ConvertTo-Json -Compress)" -ForegroundColor Gray
            }
        }
        
        return $true
    } catch {
        Write-Host "✗ $ServiceName - $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

function Test-KafkaTopic {
    param([string]$Topic)
    
    $result = docker exec kafka-broker1 kafka-topics `
        --bootstrap-server localhost:9092 `
        --describe `
        --topic $Topic 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Kafka Topic: $Topic" -ForegroundColor Green
        
        if ($Detailed) {
            $partitions = ($result | Select-String "PartitionCount").ToString() -replace ".*PartitionCount:(\d+).*", '$1'
            Write-Host "  Partitions: $partitions" -ForegroundColor Gray
        }
        
        return $true
    } else {
        Write-Host "✗ Kafka Topic: $Topic - Not found" -ForegroundColor Red
        return $false
    }
}

function Test-HDFSDirectory {
    param([string]$Path)
    
    $result = docker exec namenode hadoop fs -test -d $Path 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ HDFS Directory: $Path" -ForegroundColor Green
        return $true
    } else {
        Write-Host "✗ HDFS Directory: $Path - Not found" -ForegroundColor Red
        return $false
    }
}

function Run-HealthChecks {
    Write-Host "`n=== TRAFFIC PREDICTION SYSTEM HEALTH CHECK ===" -ForegroundColor Cyan
    Write-Host "Timestamp: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')`n" -ForegroundColor Gray
    
    # Docker Services
    Write-Host "Docker Services:" -ForegroundColor Yellow
    $services = docker-compose ps --services
    foreach ($service in $services) {
        $status = docker-compose ps $service | Select-String "Up"
        if ($status) {
            Write-Host "✓ $service" -ForegroundColor Green
        } else {
            Write-Host "✗ $service" -ForegroundColor Red
        }
    }
    
    Write-Host "`nWeb Services:" -ForegroundColor Yellow
    Test-ServiceHealth "Stream Processor" "http://localhost:3001/health"
    Test-ServiceHealth "HDFS NameNode" "http://localhost:9870"
    Test-ServiceHealth "YARN ResourceManager" "http://localhost:8088"
    Test-ServiceHealth "Schema Registry" "http://localhost:8082"
    
    Write-Host "`nKafka Topics:" -ForegroundColor Yellow
    Test-KafkaTopic "traffic-raw"
    Test-KafkaTopic "traffic-events"
    Test-KafkaTopic "traffic-predictions"
    
    Write-Host "`nHDFS Directories:" -ForegroundColor Yellow
    Test-HDFSDirectory "/traffic-data"
    Test-HDFSDirectory "/traffic-data/ml-features"
    Test-HDFSDirectory "/traffic-data/models"
    Test-HDFSDirectory "/traffic-data/predictions"
    
    Write-Host "`n=== Health Check Complete ===" -ForegroundColor Cyan
}

# Main execution
if ($Continuous) {
    while ($true) {
        Clear-Host
        Run-HealthChecks
        Write-Host "`nRefreshing in 30 seconds... (Ctrl+C to stop)" -ForegroundColor Gray
        Start-Sleep -Seconds 30
    }
} else {
    Run-HealthChecks
}
```

**Usage**:
```powershell
# Basic health check
.\scripts\health-check.ps1

# Detailed health check
.\scripts\health-check.ps1 -Detailed

# Continuous monitoring
.\scripts\health-check.ps1 -Continuous
```

### Validation Criteria
- [ ] Script checks all Docker services
- [ ] Verifies all web UIs accessible
- [ ] Checks all Kafka topics exist
- [ ] Validates HDFS directory structure
- [ ] Provides clear status reporting
- [ ] Continuous mode for monitoring

---

## Subtask 7.6: Startup Automation & Orchestration

**Status**: Partially Complete

### Enhanced Startup Script

```powershell
# start-all.ps1 (Enhanced)

param(
    [switch]$Clean,          # Clean start (remove volumes)
    [switch]$SkipValidation, # Skip health checks
    [switch]$Verbose         # Show detailed output
)

$ErrorActionPreference = "Stop"

Write-Host "`n=== METR-LA Traffic Prediction System Startup ===" -ForegroundColor Cyan
Write-Host "Timestamp: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')`n" -ForegroundColor Gray

# Step 1: Clean previous state (if requested)
if ($Clean) {
    Write-Host "Step 1: Cleaning previous state..." -ForegroundColor Yellow
    docker-compose down -v
    Write-Host "✓ Previous state cleaned`n" -ForegroundColor Green
} else {
    Write-Host "Step 1: Stopping existing services..." -ForegroundColor Yellow
    docker-compose down
    Write-Host "✓ Services stopped`n" -ForegroundColor Green
}

# Step 2: Start infrastructure services (Zookeeper, Kafka, HDFS)
Write-Host "Step 2: Starting infrastructure services..." -ForegroundColor Yellow
docker-compose up -d zookeeper kafka-broker1 namenode datanode

Write-Host "Waiting for infrastructure to be ready..." -NoNewline
Start-Sleep -Seconds 15
Write-Host " ✓`n" -ForegroundColor Green

# Step 3: Start Schema Registry and Kafka Connect
Write-Host "Step 3: Starting Schema Registry and Kafka Connect..." -ForegroundColor Yellow
docker-compose up -d schema-registry kafka-connect

Write-Host "Waiting for schema services..." -NoNewline
Start-Sleep -Seconds 10
Write-Host " ✓`n" -ForegroundColor Green

# Step 4: Create Kafka topics
Write-Host "Step 4: Creating Kafka topics..." -ForegroundColor Yellow
.\scripts\create-kafka-topics.ps1

# Step 5: Setup HDFS directories
Write-Host "`nStep 5: Setting up HDFS directory structure..." -ForegroundColor Yellow
.\scripts\setup-hdfs-directories.ps1

# Step 6: Start Spark cluster
Write-Host "`nStep 6: Starting Spark cluster..." -ForegroundColor Yellow
docker-compose up -d spark-master spark-worker

Write-Host "Waiting for Spark..." -NoNewline
Start-Sleep -Seconds 10
Write-Host " ✓`n" -ForegroundColor Green

# Step 7: Start application services
Write-Host "Step 7: Starting application services..." -ForegroundColor Yellow
docker-compose up -d stream-processor postgres

Write-Host "Waiting for application services..." -NoNewline
Start-Sleep -Seconds 10
Write-Host " ✓`n" -ForegroundColor Green

# Step 8: Verify system health
if (-not $SkipValidation) {
    Write-Host "Step 8: Running health checks..." -ForegroundColor Yellow
    .\scripts\health-check.ps1
}

# Step 9: Display summary
Write-Host "`n=== System Startup Complete ===" -ForegroundColor Green
Write-Host "`nAvailable UIs:" -ForegroundColor Cyan
Write-Host "  • Stream Processor: http://localhost:3001/health" -ForegroundColor Gray
Write-Host "  • HDFS NameNode:    http://localhost:9870" -ForegroundColor Gray
Write-Host "  • YARN Resource:    http://localhost:8088" -ForegroundColor Gray
Write-Host "  • Schema Registry:  http://localhost:8082" -ForegroundColor Gray
Write-Host "  • Kafka UI:         http://localhost:8080 (if configured)" -ForegroundColor Gray

Write-Host "`nNext Steps:" -ForegroundColor Cyan
Write-Host "  1. Start data ingestion:  .\scripts\send-csv-events.ps1" -ForegroundColor Gray
Write-Host "  2. Monitor health:        .\scripts\health-check.ps1 -Continuous" -ForegroundColor Gray
Write-Host "  3. View stream logs:      docker logs -f stream-processor" -ForegroundColor Gray

Write-Host "`n"
```

### Enhanced Stop Script

```powershell
# stop-all.ps1

param(
    [switch]$RemoveVolumes,  # Remove data volumes
    [switch]$Force           # Force stop without confirmation
)

if ($RemoveVolumes -and -not $Force) {
    $confirm = Read-Host "This will DELETE ALL DATA. Are you sure? (yes/no)"
    if ($confirm -ne "yes") {
        Write-Host "Cancelled." -ForegroundColor Yellow
        exit
    }
}

Write-Host "Stopping all services..." -ForegroundColor Yellow

if ($RemoveVolumes) {
    docker-compose down -v
    Write-Host "✓ All services stopped and volumes removed" -ForegroundColor Green
} else {
    docker-compose down
    Write-Host "✓ All services stopped (data preserved)" -ForegroundColor Green
}
```

### Validation Criteria
- [ ] start-all.ps1 orchestrates full startup
- [ ] Services start in correct order
- [ ] Health checks validate readiness
- [ ] Clear status reporting throughout
- [ ] Error handling and rollback
- [ ] stop-all.ps1 with safety confirmations

---

## Subtask 7.7: Logging and Monitoring

**Status**: Not Started

### Centralized Logging

```powershell
# scripts/view-logs.ps1

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet('stream-processor', 'spark-master', 'spark-worker', 'kafka', 'hdfs', 'all')]
    [string]$Service = 'all',
    
    [Parameter(Mandatory=$false)]
    [int]$Lines = 100,
    
    [switch]$Follow
)

function Show-Logs {
    param([string]$Container, [string]$DisplayName)
    
    Write-Host "`n=== $DisplayName ===" -ForegroundColor Cyan
    
    if ($Follow) {
        docker logs -f --tail $Lines $Container
    } else {
        docker logs --tail $Lines $Container
    }
}

switch ($Service) {
    'stream-processor' { Show-Logs 'stream-processor' 'Stream Processor' }
    'spark-master'     { Show-Logs 'spark-master' 'Spark Master' }
    'spark-worker'     { Show-Logs 'spark-worker' 'Spark Worker' }
    'kafka'            { Show-Logs 'kafka-broker1' 'Kafka Broker' }
    'hdfs'             { Show-Logs 'namenode' 'HDFS NameNode' }
    'all'              {
        Show-Logs 'stream-processor' 'Stream Processor'
        Show-Logs 'spark-master' 'Spark Master'
        Show-Logs 'kafka-broker1' 'Kafka Broker'
        Show-Logs 'namenode' 'HDFS NameNode'
    }
}
```

### Prometheus Metrics (Future Enhancement)

```yaml
# docker-compose-monitoring.yml (optional)
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'

  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/dashboards:/etc/grafana/provisioning/dashboards
    depends_on:
      - prometheus

volumes:
  prometheus_data:
  grafana_data:
```

---

## Completion Criteria

### Infrastructure Complete When:
- [ ] All Docker services running healthy
- [ ] Kafka topics created and configured
- [ ] HDFS directory structure setup
- [ ] All management UIs accessible
- [ ] Health check system working
- [ ] Startup/shutdown automation complete
- [ ] Logging system configured

### Operational Readiness:
- [ ] Start-all script orchestrates full startup
- [ ] Health checks validate all components
- [ ] Clear documentation for operations
- [ ] Troubleshooting guide available
- [ ] Monitoring UIs configured
- [ ] System can recover from failures

---

## Next Steps
→ Proceed to **Task 8: End-to-End Validation & Testing**

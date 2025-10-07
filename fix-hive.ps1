#!/usr/bin/env pwsh
# Fix Hive Metastore and Hive Server Issues
# This script initializes the Hive metastore schema and restarts Hive services

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "   Hive Docker Fix Script" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check if PostgreSQL metastore is running
Write-Host "Step 1 of 5: Checking Hive PostgreSQL metastore..." -ForegroundColor Yellow
$postgresStatus = docker ps --filter "name=hive-metastore-postgresql" --format "{{.Status}}"
if ($postgresStatus -match "Up") {
    Write-Host "SUCCESS: Hive PostgreSQL metastore is running" -ForegroundColor Green
} else {
    Write-Host "WARNING: Hive PostgreSQL metastore is not running. Starting it..." -ForegroundColor Red
    docker-compose up -d hive-metastore-postgresql
    Start-Sleep -Seconds 10
}

# Step 2: Stop existing Hive containers
Write-Host ""
Write-Host "Step 2 of 5: Stopping Hive containers..." -ForegroundColor Yellow
docker-compose stop hive-metastore hive-server 2>$null
docker-compose rm -f hive-metastore hive-server 2>$null
Write-Host "SUCCESS: Hive containers stopped and removed" -ForegroundColor Green

# Step 3: Initialize Hive metastore schema
Write-Host ""
Write-Host "Step 3 of 5: Initializing Hive metastore schema..." -ForegroundColor Yellow
Write-Host "This will create the necessary database tables in PostgreSQL" -ForegroundColor Gray

# Run schematool to initialize the metastore
docker run --rm `
    --network traffic-prediction_default `
    -e HIVE_CORE_CONF_javax_jdo_option_ConnectionURL="jdbc:postgresql://hive-metastore-postgresql:5432/metastore" `
    -e HIVE_CORE_CONF_javax_jdo_option_ConnectionDriverName="org.postgresql.Driver" `
    -e HIVE_CORE_CONF_javax_jdo_option_ConnectionUserName="hive" `
    -e HIVE_CORE_CONF_javax_jdo_option_ConnectionPassword="hive" `
    bde2020/hive:2.3.2-postgresql-metastore `
    /opt/hive/bin/schematool -dbType postgres -initSchema

if ($LASTEXITCODE -eq 0) {
    Write-Host "SUCCESS: Hive metastore schema initialized successfully" -ForegroundColor Green
} else {
    Write-Host "WARNING: Failed to initialize Hive metastore schema" -ForegroundColor Red
    Write-Host "Schema may already exist (this is OK)" -ForegroundColor Yellow
}

# Step 4: Start Hive services with updated configuration
Write-Host ""
Write-Host "Step 4 of 5: Starting Hive services..." -ForegroundColor Yellow
docker-compose up -d hive-metastore
Start-Sleep -Seconds 15

docker-compose up -d hive-server
Start-Sleep -Seconds 10

# Step 5: Verify services are running
Write-Host ""
Write-Host "Step 5 of 5: Verifying Hive services..." -ForegroundColor Yellow
Write-Host ""

$metastoreStatus = docker ps --filter "name=hive-metastore" --format "{{.Status}}"
$serverStatus = docker ps --filter "name=hive-server" --format "{{.Status}}"

Write-Host "Hive Metastore Status:" -ForegroundColor Cyan
if ($metastoreStatus -match "Up") {
    Write-Host "SUCCESS: Running - $metastoreStatus" -ForegroundColor Green
} else {
    Write-Host "ERROR: Not running" -ForegroundColor Red
    Write-Host "Checking logs..." -ForegroundColor Yellow
    docker logs hive-metastore --tail 20
}

Write-Host ""
Write-Host "Hive Server Status:" -ForegroundColor Cyan
if ($serverStatus -match "Up") {
    Write-Host "SUCCESS: Running - $serverStatus" -ForegroundColor Green
} else {
    Write-Host "ERROR: Not running" -ForegroundColor Red
    Write-Host "Checking logs..." -ForegroundColor Yellow
    docker logs hive-server --tail 20
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "   Hive Fix Complete!" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host ""
Write-Host "Test Hive CLI:" -ForegroundColor White
Write-Host "  docker exec -it hive-server /opt/hive/bin/beeline -u jdbc:hive2://localhost:10000" -ForegroundColor Gray
Write-Host ""
Write-Host "Create a test table:" -ForegroundColor White
Write-Host '  CREATE TABLE test (id INT, name STRING);' -ForegroundColor Gray
Write-Host ""
Write-Host "Check Hive metastore logs if issues persist:" -ForegroundColor White
Write-Host "  docker logs hive-metastore" -ForegroundColor Gray
Write-Host ""

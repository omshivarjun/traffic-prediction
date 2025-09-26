#!/usr/bin/env pwsh
# =====================================================
# Local PostgreSQL Database Setup Script
# =====================================================
# This script sets up the traffic prediction database on local PostgreSQL
# Use this if you want to run the database locally instead of in Docker

param(
    [string]$PostgresUser = "postgres",
    [string]$PostgresPassword = "",
    [string]$DatabaseHost = "localhost",
    [int]$DatabasePort = 5432
)

Write-Host "Setting up Traffic Prediction Database on Local PostgreSQL..." -ForegroundColor Cyan

# Check if PostgreSQL is running
Write-Host "Checking PostgreSQL service status..." -ForegroundColor Yellow
try {
    $pgService = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue | Where-Object { $_.Status -eq "Running" }
    if (-not $pgService) {
        Write-Host "PostgreSQL service is not running. Please start PostgreSQL first." -ForegroundColor Red
        Write-Host "Try: net start postgresql-x64-17 (or your PostgreSQL service name)" -ForegroundColor Yellow
        exit 1
    }
    Write-Host "PostgreSQL service is running: $($pgService.Name)" -ForegroundColor Green
} catch {
    Write-Host "Could not check PostgreSQL service status: $($_.Exception.Message)" -ForegroundColor Red
}

# Test PostgreSQL connection
Write-Host "Testing PostgreSQL connection..." -ForegroundColor Yellow
try {
    if ($PostgresPassword) {
        $env:PGPASSWORD = $PostgresPassword
    }
    
    $testResult = psql -h $DatabaseHost -p $DatabasePort -U $PostgresUser -d postgres -c "SELECT version();" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Could not connect to PostgreSQL. Please check your credentials." -ForegroundColor Red
        Write-Host "Error: $testResult" -ForegroundColor Red
        exit 1
    }
    Write-Host "PostgreSQL connection successful!" -ForegroundColor Green
} catch {
    Write-Host "Error testing PostgreSQL connection: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Create database and user
Write-Host "Creating database and user..." -ForegroundColor Yellow
try {
    Write-Host "Creating traffic_user and traffic_db..." -ForegroundColor Cyan
    psql -h $DatabaseHost -p $DatabasePort -U $PostgresUser -d postgres -f "create_local_db.sql"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to create database and user. Check create_local_db.sql" -ForegroundColor Red
        exit 1
    }
    Write-Host "Database and user created successfully!" -ForegroundColor Green
} catch {
    Write-Host "Error creating database and user: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Run database schema
Write-Host "Setting up database schema..." -ForegroundColor Yellow
try {
    Write-Host "Creating traffic schema and tables..." -ForegroundColor Cyan
    psql -h $DatabaseHost -p $DatabasePort -U traffic_user -d traffic_db -f "database\init\01_create_schema.sql"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to create database schema. Check 01_create_schema.sql" -ForegroundColor Red
        exit 1
    }
    Write-Host "Database schema created successfully!" -ForegroundColor Green
} catch {
    Write-Host "Error creating database schema: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Verify setup
Write-Host "Verifying database setup..." -ForegroundColor Yellow
try {
    $tableCount = psql -h $DatabaseHost -p $DatabasePort -U traffic_user -d traffic_db -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'traffic';"
    Write-Host "Created $($tableCount.Trim()) tables in traffic schema" -ForegroundColor Green
    
    $sensorCount = psql -h $DatabaseHost -p $DatabasePort -U traffic_user -d traffic_db -t -c "SELECT COUNT(*) FROM traffic.sensors;"
    Write-Host "Inserted $($sensorCount.Trim()) sample sensors" -ForegroundColor Green
    
    Write-Host "Database setup completed successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Database connection details:" -ForegroundColor Cyan
    Write-Host "  Host: $DatabaseHost" -ForegroundColor White
    Write-Host "  Port: $DatabasePort" -ForegroundColor White
    Write-Host "  Database: traffic_db" -ForegroundColor White
    Write-Host "  User: traffic_user" -ForegroundColor White
    Write-Host "  Password: traffic_password" -ForegroundColor White
    Write-Host ""
    Write-Host "You can now update your .env file with:" -ForegroundColor Yellow
    Write-Host "DATABASE_URL=postgresql://traffic_user:traffic_password@localhost:5432/traffic_db" -ForegroundColor White
    
} catch {
    Write-Host "Error verifying database setup: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Clean up environment variable
if ($PostgresPassword) {
    Remove-Item env:PGPASSWORD -ErrorAction SilentlyContinue
}

Write-Host "Local PostgreSQL database setup complete!" -ForegroundColor Green
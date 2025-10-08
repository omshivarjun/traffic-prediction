# Send Real METR-LA Traffic Events from CSV to Kafka
# This script reads the actual METR-LA dataset and sends it to Kafka

param(
    [int]$DelaySeconds = 1,
    [string]$CsvPath = "src\kafka\test_data.csv",
    [string]$KafkaContainer = "kafka-broker1",
    [string]$Topic = "traffic-raw"  # Changed to traffic-raw (input topic for stream-processor)
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "METR-LA CSV Data Streamer" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if CSV exists
if (-not (Test-Path $CsvPath)) {
    Write-Host "ERROR: CSV file not found at $CsvPath" -ForegroundColor Red
    exit 1
}

# Count total records
$totalRecords = (Import-Csv $CsvPath).Count
Write-Host "Found $totalRecords traffic records in CSV" -ForegroundColor Green
Write-Host "Delay between events: $DelaySeconds second(s)" -ForegroundColor Yellow
Write-Host "Kafka Topic: $Topic" -ForegroundColor Yellow
Write-Host ""

# Read and send each record
$eventCount = 0
$skipped = 0
Import-Csv $CsvPath | ForEach-Object {
    # Validate speed (must be non-negative)
    $speed = [double]$_.speed_mph
    if ($speed -lt 0) {
        $skipped++
        Write-Host "SKIPPED: $($_.sensor_id) has negative speed: $speed mph" -ForegroundColor Yellow
        return
    }
    
    $eventCount++
    
    # Create traffic event JSON from CSV row
    $event = @{
        event_id = [Guid]::NewGuid().ToString()
        sensor_id = $_.sensor_id
        timestamp = $_.timestamp
        speed_mph = [double]$_.speed_mph
        volume_vph = [int]$_.volume_vph
        occupancy_percent = [double]$_.occupancy_percent
        coordinates = @{
            latitude = [double]$_.latitude
            longitude = [double]$_.longitude
        }
        road_name = $_.road_name
        direction = $_.direction
        lane_count = [int]$_.lane_count
        segment_id = "seg_$($_.sensor_id)"
        weather_condition = "clear"
        incident_nearby = $false
    } | ConvertTo-Json -Compress

    # Send to Kafka
    try {
        $kafkaCommand = "echo '$event' | /opt/bitnami/kafka/bin/kafka-console-producer.sh --broker-list localhost:9092 --topic $Topic"
        docker exec -i $KafkaContainer bash -c $kafkaCommand 2>&1 | Out-Null
        
        # Progress indicator
        $percentage = [math]::Round(($eventCount / $totalRecords) * 100, 1)
        Write-Host "[$eventCount/$totalRecords] ($percentage%) Sent: $($_.sensor_id) | Speed: $($_.speed_mph) mph | Location: ($($_.latitude), $($_.longitude))" -ForegroundColor Green
        
        # Delay between events
        if ($DelaySeconds -gt 0 -and $eventCount -lt $totalRecords) {
            Start-Sleep -Seconds $DelaySeconds
        }
    }
    catch {
        Write-Host "ERROR sending event $eventCount : $_" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Summary:" -ForegroundColor Cyan
Write-Host "  Total Events Sent: $eventCount" -ForegroundColor Green
Write-Host "  Skipped (invalid): $skipped" -ForegroundColor Yellow
Write-Host "  Source File: $CsvPath" -ForegroundColor Yellow
Write-Host "  Topic: $Topic" -ForegroundColor Yellow
Write-Host ""
Write-Host "Check the dashboard at http://localhost:3000" -ForegroundColor Cyan
Write-Host "Predictions should appear on the map!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan

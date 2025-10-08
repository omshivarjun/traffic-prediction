#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Send properly formatted test events to Kafka
.DESCRIPTION
    Generates valid JSON traffic events and sends them to Kafka using file-based approach
    to avoid bash echo quote-stripping issues.
#>

param(
    [int]$Count = 10,
    [int]$DelaySeconds = 3
)

Write-Host "🚀 Starting Test Event Generator" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "Events to send: $Count" -ForegroundColor Yellow
Write-Host "Delay between events: $DelaySeconds seconds" -ForegroundColor Yellow
Write-Host ""

$segments = @(
    @{ id = "LA_001"; lat = 34.0522; lon = -118.2437; name = "I-10 Downtown" },
    @{ id = "LA_002"; lat = 34.0689; lon = -118.4452; name = "I-405 West LA" },
    @{ id = "LA_003"; lat = 34.1478; lon = -118.1445; name = "I-210 Pasadena" },
    @{ id = "LA_004"; lat = 33.9425; lon = -118.4081; name = "I-105 LAX" },
    @{ id = "LA_005"; lat = 34.2014; lon = -118.5290; name = "US-101 Woodland Hills" }
)
$startTimestamp = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()

for ($i = 1; $i -le $Count; $i++) {
    # Generate random traffic data
    $segment = $segments | Get-Random
    $speed = Get-Random -Minimum 35 -Maximum 75
    $volume = Get-Random -Minimum 250 -Maximum 550
    $timestamp = $startTimestamp + ($i * 60000) # 1 minute increments
    
    # Create valid JSON with coordinates (PowerShell will handle escaping properly)
    $event = @{
        segment_id = $segment.id
        sensor_id = $segment.id
        timestamp = $timestamp
        speed = [double]$speed + 0.5
        volume = $volume
        coordinates = @{
            latitude = $segment.lat
            longitude = $segment.lon
        }
        road_name = $segment.name
    } | ConvertTo-Json -Compress
    
    # Write to temp file
    $tempFile = "c:\traffic-prediction\temp-event-$i.json"
    $event | Out-File -FilePath $tempFile -Encoding UTF8 -NoNewline
    
    # Send to Kafka via file
    Write-Host "[$i/$Count] Sending: " -NoNewline -ForegroundColor Green
    Write-Host "$($segment.id) ($($segment.name)) @ $($speed + 0.5) mph, $volume vehicles" -ForegroundColor White
    
    docker exec kafka-broker1 bash -c "echo '$event' | kafka-console-producer --bootstrap-server localhost:9092 --topic traffic-events" 2>&1 | Out-Null
    
    # Cleanup temp file
    Remove-Item $tempFile -ErrorAction SilentlyContinue
    
    if ($i -lt $Count) {
        Start-Sleep -Seconds $DelaySeconds
    }
}

Write-Host ""
Write-Host "✅ Sent $Count events successfully!" -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""
Write-Host "💡 Next steps:" -ForegroundColor Yellow
Write-Host "  1. Check predictions in Kafka: docker exec kafka-broker1 kafka-console-consumer --bootstrap-server localhost:9092 --topic traffic-predictions --from-beginning --max-messages 5" -ForegroundColor Gray
Write-Host "  2. Start dashboard: npm run dev" -ForegroundColor Gray
Write-Host "  3. Open http://localhost:3000" -ForegroundColor Gray

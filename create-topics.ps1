# Simple script to create Kafka topics for traffic prediction system

Write-Host "Creating Kafka topics..." -ForegroundColor Cyan

# Core topics for traffic prediction
$topics = @(
    "traffic-events",
    "processed-traffic-aggregates", 
    "traffic-predictions",
    "traffic-alerts",
    "traffic-incidents"
)

foreach ($topic in $topics) {
    Write-Host "Creating topic: $topic" -ForegroundColor Yellow
    
    $result = docker exec kafka-broker1 kafka-topics --create --bootstrap-server kafka-broker1:9092 --topic $topic --partitions 4 --replication-factor 1 --if-not-exists 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Topic $topic created successfully!" -ForegroundColor Green
    } elseif ($result -match "already exists") {
        Write-Host "⚠️ Topic $topic already exists" -ForegroundColor Yellow  
    } else {
        Write-Host "❌ Error creating topic $topic : $result" -ForegroundColor Red
    }
}

Write-Host "`nListing all topics:" -ForegroundColor Cyan
docker exec kafka-broker1 kafka-topics --list --bootstrap-server kafka-broker1:9092

Write-Host "`n🎉 Topic creation completed!" -ForegroundColor Green
#!/usr/bin/env pwsh
# Test script to verify predictions are flowing to frontend

Write-Host "🧪 Testing Traffic Predictions Display" -ForegroundColor Cyan
Write-Host ""

# Step 1: Send test predictions to Kafka
Write-Host "1️⃣ Sending 10 test predictions to Kafka..." -ForegroundColor Yellow
1..10 | ForEach-Object {
    $speed = Get-Random -Min 30 -Max 70
    $predictedSpeed = Get-Random -Min 25 -Max 65
    $volume = Get-Random -Min 50 -Max 200
    $prediction = @"
{"segment_id":"TEST_SEGMENT_$_","timestamp":"2025-01-21 14:$($_):00","prediction_time":$([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()),"actual_speed":$speed,"predicted_speed":$predictedSpeed,"actual_volume":$volume,"predicted_volume":150,"confidence":0.90,"horizon_minutes":15}
"@
    echo $prediction | docker exec -i kafka-broker1 kafka-console-producer --bootstrap-server localhost:9092 --topic traffic-predictions 2>$null
    Write-Host "   ✅ Sent prediction for TEST_SEGMENT_$_" -ForegroundColor Green
}

Write-Host ""
Write-Host "2️⃣ Verifying messages in Kafka topic..." -ForegroundColor Yellow
$offsets = docker exec -it kafka-broker1 kafka-run-class kafka.tools.GetOffsetShell --broker-list localhost:9092 --topic traffic-predictions 2>$null
Write-Host $offsets
Write-Host ""

Write-Host "3️⃣ Checking consumer group status..." -ForegroundColor Yellow
docker exec -it kafka-broker1 kafka-consumer-groups --bootstrap-server localhost:9092 --describe --group nextjs-prediction-consumer-group 2>$null | Select-String -Pattern "TOPIC|traffic-predictions"
Write-Host ""

Write-Host "4️⃣ Next Steps:" -ForegroundColor Cyan
Write-Host "   a) Open browser to http://localhost:3000"
Write-Host "   b) Check browser console for prediction logs"
Write-Host "   c) Look for '🚦 Prediction:' messages in Next.js terminal"
Write-Host "   d) Verify predictions appear on the map"
Write-Host ""
Write-Host "📊 If predictions don't appear:" -ForegroundColor Yellow
Write-Host "   - Check Next.js terminal for '📨 RECEIVED MESSAGE' logs"
Write-Host "   - Check browser DevTools → Network → EventStream"
Write-Host "   - Look for '✅ Sent prediction via SSE' in logs"
Write-Host ""

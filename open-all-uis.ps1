# Open All METR-LA Pipeline Monitoring UIs

Write-Host ""
Write-Host "Opening All METR-LA Pipeline Monitoring UIs..." -ForegroundColor Green
Write-Host ""

# Open Kafka UI
Write-Host "Opening Kafka UI (Message Monitoring)..." -ForegroundColor Yellow
Start-Process "http://localhost:8085"
Start-Sleep -Milliseconds 500

# Open HDFS NameNode UI
Write-Host "Opening HDFS NameNode (Data Storage)..." -ForegroundColor Yellow
Start-Process "http://localhost:9871"
Start-Sleep -Milliseconds 500

# Open Spark Master UI
Write-Host "Opening Spark Master (Job Processing)..." -ForegroundColor Yellow
Start-Process "http://localhost:8086"
Start-Sleep -Milliseconds 500

# Open YARN Resource Manager UI
Write-Host "Opening YARN Resource Manager (Hadoop Jobs)..." -ForegroundColor Yellow
Start-Process "http://localhost:8089"
Start-Sleep -Milliseconds 500

# Open Spark History Server UI
Write-Host "Opening Spark History Server (Job History)..." -ForegroundColor Yellow
Start-Process "http://localhost:8189"
Start-Sleep -Milliseconds 500

# Open Traffic Dashboard
Write-Host "Opening Traffic Dashboard (Interactive Heatmap)..." -ForegroundColor Yellow
Start-Process "http://localhost:3000/dashboard"

Write-Host ""
Write-Host "All UIs opened in your default browser!" -ForegroundColor Green
Write-Host ""
Write-Host "Quick Reference:" -ForegroundColor Blue
Write-Host "- Kafka (8085): See live traffic messages in Topics -> traffic-events"
Write-Host "- HDFS (9871): Browse data in Utilities -> Browse File System -> /traffic-data/"
Write-Host "- Spark (8086): Monitor jobs in Running/Completed Applications"
Write-Host "- YARN (8089): Check cluster resources and job management"
Write-Host "- History (8189): Analyze completed job performance"
Write-Host "- Dashboard (3000): Interactive LA traffic heatmap"
Write-Host ""
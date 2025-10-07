# Start Real-time Traffic Prediction Service
# This service reads from Kafka, applies ML model, and publishes predictions

Write-Host "🚀 Starting Real-time Traffic Prediction Service..." -ForegroundColor Cyan
Write-Host ""

# Check if Spark is running
Write-Host "1️⃣ Checking Spark master..." -ForegroundColor Yellow
$sparkStatus = docker ps --filter "name=spark-master" --format "{{.Status}}"
if ($sparkStatus -like "*Up*") {
    Write-Host "   ✅ Spark master is running" -ForegroundColor Green
} else {
    Write-Host "   ❌ Spark master is not running!" -ForegroundColor Red
    Write-Host "   Please start Spark: docker-compose up -d spark-master" -ForegroundColor Yellow
    exit 1
}

# Check if Kafka is running
Write-Host "2️⃣ Checking Kafka..." -ForegroundColor Yellow
$kafkaStatus = docker ps --filter "name=kafka-broker1" --format "{{.Status}}"
if ($kafkaStatus -like "*Up*") {
    Write-Host "   ✅ Kafka is running" -ForegroundColor Green
} else {
    Write-Host "   ❌ Kafka is not running!" -ForegroundColor Red
    Write-Host "   Please start Kafka: docker-compose up -d kafka-broker1" -ForegroundColor Yellow
    exit 1
}

# Check if HDFS is running
Write-Host "3️⃣ Checking HDFS..." -ForegroundColor Yellow
$hdfsStatus = docker ps --filter "name=namenode" --format "{{.Status}}"
if ($hdfsStatus -like "*Up*") {
    Write-Host "   ✅ HDFS is running" -ForegroundColor Green
} else {
    Write-Host "   ❌ HDFS is not running!" -ForegroundColor Red
    Write-Host "   Please start HDFS: docker-compose up -d namenode datanode" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "4️⃣ Starting prediction service in Spark..." -ForegroundColor Yellow
Write-Host ""

# Run the streaming predictor
docker exec -it spark-master bash -c @"
source /opt/bitnami/spark/venv/bin/activate && \
/opt/bitnami/spark/bin/spark-submit \
  --master local[2] \
  --driver-memory 2g \
  --executor-memory 2g \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \
  /opt/spark-apps/src/ml/streaming_predictor.py
"@

Write-Host ""
Write-Host "✅ Prediction service stopped" -ForegroundColor Green

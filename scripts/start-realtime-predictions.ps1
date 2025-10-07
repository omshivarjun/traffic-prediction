# Start Real-time Traffic Prediction Service
# This service reads from Kafka, applies ML model, and publishes predictions

Write-Host "🚀 Starting Real-time Traffic Prediction Service..." -ForegroundColor Cyan
Write-Host ""
Write-Host "📊 Service Details:" -ForegroundColor Yellow
Write-Host "   - Model: Linear Regression (99.99% accuracy)"
Write-Host "   - Input: Kafka topic 'traffic-events'"
Write-Host "   - Output: Kafka topic 'traffic-predictions'"
Write-Host "   - Prediction horizon: 5 minutes ahead"
Write-Host ""

# Run in Spark container
docker exec -it spark-master bash -c @"
source /opt/bitnami/spark/venv/bin/activate && \
/opt/bitnami/spark/bin/spark-submit \
  --master local[*] \
  --driver-memory 2g \
  --executor-memory 2g \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \
  --conf spark.sql.streaming.checkpointLocation=hdfs://namenode:9000/checkpoints/predictions \
  /opt/spark-apps/src/prediction/realtime_prediction_service.py \
  --kafka-brokers kafka-broker1:9092 \
  --console-output
"@

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ Prediction service completed successfully!" -ForegroundColor Green
} else {
    Write-Host "`n❌ Prediction service failed with exit code: $LASTEXITCODE" -ForegroundColor Red
}

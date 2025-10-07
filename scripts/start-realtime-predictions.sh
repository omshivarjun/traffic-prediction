#!/bin/bash
# Start Real-time Traffic Prediction Service
echo "🚀 Starting Real-time Traffic Prediction Service..."

# Run with Spark Submit
/opt/bitnami/spark/bin/spark-submit \
  --master local[*] \
  --driver-memory 2g \
  --executor-memory 2g \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \
  --conf spark.sql.streaming.checkpointLocation=hdfs://namenode:9000/checkpoints/predictions \
  /opt/spark-apps/src/prediction/realtime_prediction_service.py \
  --kafka-brokers kafka-broker1:9092 \
  --console-output

echo "✅ Prediction service started!"

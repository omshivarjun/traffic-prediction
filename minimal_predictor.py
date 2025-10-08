#!/usr/bin/env python3
"""
Minimal Traffic Prediction Service - Kafka to Kafka
Reads traffic-events → Applies GBT model → Writes traffic-predictions
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, to_json, struct, current_timestamp
from pyspark.sql.types import *
from pyspark.ml import PipelineModel
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    logger.info("=" * 60)
    logger.info("🚀 Starting Minimal Traffic Prediction Service")
    logger.info("=" * 60)
    
    # Create Spark session
    logger.info("Creating Spark session...")
    spark = SparkSession.builder \
        .appName("TrafficPredictions") \
        .master("local[2]") \
        .config("spark.driver.memory", "2g") \
        .config("spark.executor.memory", "1g") \
        .config("spark.sql.shuffle.partitions", "2") \
        .getOrCreate()
    
    logger.info("✅ Spark session created")
    
    # Load GBT model from HDFS
    model_path = "hdfs://namenode:9000/traffic-data/models/gbt-sample-model"
    logger.info(f"📂 Loading model from {model_path}...")
    
    try:
        model = PipelineModel.load(model_path)
        logger.info("✅ Model loaded successfully!")
    except Exception as e:
        logger.error(f"❌ Failed to load model: {e}")
        raise
    
    # Define schema for traffic events
    event_schema = StructType([
        StructField("segment_id", StringType()),
        StructField("timestamp", LongType()),
        StructField("speed", DoubleType()),
        StructField("volume", IntegerType()),
        StructField("occupancy", DoubleType()),
        StructField("hour", IntegerType()),
        StructField("day_of_week", IntegerType()),
        StructField("month", IntegerType())
    ])
    
    # Read from Kafka traffic-events topic
    logger.info("🔌 Connecting to Kafka (reading from traffic-events)...")
    raw_stream = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", "kafka-broker1:9092,kafka-broker2:9093") \
        .option("subscribe", "traffic-events") \
        .option("startingOffsets", "latest") \
        .option("failOnDataLoss", "false") \
        .load()
    
    logger.info("✅ Connected to Kafka!")
    
    # Parse JSON from Kafka value
    parsed_stream = raw_stream.select(
        from_json(col("value").cast("string"), event_schema).alias("data")
    ).select("data.*")
    
    logger.info("📊 Parsing events...")
    
    # Apply model to make predictions
    logger.info("🔮 Applying ML model to stream...")
    predictions = model.transform(parsed_stream)
    
    # Select output columns
    output = predictions.select(
        col("segment_id"),
        col("timestamp"),
        col("speed").alias("actual_speed"),
        col("prediction").alias("predicted_speed"),
        current_timestamp().alias("prediction_time")
    )
    
    # Convert to JSON for Kafka
    kafka_output = output.select(
        to_json(struct("*")).alias("value")
    )
    
    # Write to Kafka traffic-predictions topic
    logger.info("📤 Writing predictions to traffic-predictions topic...")
    query = kafka_output.writeStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", "kafka-broker1:9092,kafka-broker2:9093") \
        .option("topic", "traffic-predictions") \
        .option("checkpointLocation", "/tmp/checkpoint") \
        .outputMode("append") \
        .start()
    
    logger.info("✅ Streaming started successfully!")
    logger.info("🔄 Processing events in real-time...")
    logger.info("Press Ctrl+C to stop")
    
    query.awaitTermination()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n⏹️  Stopping service...")
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise

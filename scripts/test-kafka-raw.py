#!/usr/bin/env python3
"""
Ultra-simple test to see raw Kafka messages
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import *

spark = SparkSession.builder \
    .appName("Kafka Raw Test") \
    .master("local[2]") \
    .getOrCreate()

# Read Kafka - just get raw value
df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka-broker1:9092,kafka-broker2:9093") \
    .option("subscribe", "traffic-events") \
    .option("startingOffsets", "earliest") \
    .load()

# Show raw Kafka data
query = df.selectExpr("CAST(value AS STRING) as json_str") \
    .writeStream \
    .outputMode("append") \
    .format("console") \
    .option("truncate", False) \
    .trigger(processingTime="5 seconds") \
    .start()

print("✅ Showing raw Kafka messages...")
print("Press Ctrl+C to stop...")
query.awaitTermination()

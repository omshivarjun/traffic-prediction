"""
Spark Structured Streaming Consumer for Traffic Events
Reads from Kafka traffic-events topic and processes in real-time
Performs windowed aggregations and writes to HDFS
"""

import os
import sys
from pathlib import Path
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_spark_session():
    """Create Spark session with Kafka and HDFS support"""
    spark = SparkSession.builder \
        .appName("TrafficStreamProcessor") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .config("spark.streaming.stopGracefullyOnShutdown", "true") \
        .config("spark.sql.streaming.checkpointLocation", "/tmp/spark-checkpoint") \
        .config("spark.jars.packages", 
                "org.apache.spark:spark-sql-kafka-0-10_2.12:3.1.2") \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    return spark

def define_traffic_schema():
    """Define schema for incoming traffic events"""
    return StructType([
        StructField("timestamp", StringType(), True),
        StructField("sensor_id", StringType(), True),
        StructField("speed_mph", DoubleType(), True),
        StructField("volume_vehicles_per_hour", DoubleType(), True),
        StructField("latitude", DoubleType(), True),
        StructField("longitude", DoubleType(), True),
        StructField("road_type", StringType(), True),
        StructField("road_name", StringType(), True),
        StructField("direction", StringType(), True),
        StructField("producer_timestamp", StringType(), True),
        StructField("data_source", StringType(), True)
    ])

class TrafficStreamProcessor:
    """Process traffic events from Kafka using Spark Structured Streaming"""
    
    def __init__(self, kafka_config: dict, hdfs_config: dict):
        self.kafka_config = kafka_config
        self.hdfs_config = hdfs_config
        self.spark = create_spark_session()
        self.traffic_schema = define_traffic_schema()
        
    def read_kafka_stream(self):
        """Read streaming data from Kafka"""
        logger.info(f"Reading from Kafka topic: {self.kafka_config['topic']}")
        
        df = self.spark \
            .readStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", self.kafka_config['bootstrap_servers']) \
            .option("subscribe", self.kafka_config['topic']) \
            .option("startingOffsets", "latest") \
            .option("failOnDataLoss", "false") \
            .load()
        
        # Parse JSON values
        parsed_df = df.select(
            col("key").cast("string").alias("kafka_key"),
            col("timestamp").alias("kafka_timestamp"),
            from_json(col("value").cast("string"), self.traffic_schema).alias("data")
        ).select(
            col("kafka_key"),
            col("kafka_timestamp"),
            col("data.*")
        )
        
        # Convert timestamp to proper format
        processed_df = parsed_df.withColumn(
            "timestamp", 
            to_timestamp(col("timestamp"), "yyyy-MM-dd HH:mm:ss")
        ).withColumn(
            "producer_timestamp",
            to_timestamp(col("producer_timestamp"))
        )
        
        return processed_df
    
    def create_windowed_aggregations(self, df):
        """Create windowed aggregations for traffic analysis"""
        
        # 5-minute window aggregations by sensor
        sensor_aggregates = df \
            .filter(col("speed_mph").isNotNull() | col("volume_vehicles_per_hour").isNotNull()) \
            .groupBy(
                window(col("timestamp"), "5 minutes"),
                col("sensor_id"),
                col("road_name"),
                col("road_type"),
                col("direction"),
                col("latitude"),
                col("longitude")
            ).agg(
                avg("speed_mph").alias("avg_speed_mph"),
                max("speed_mph").alias("max_speed_mph"),
                min("speed_mph").alias("min_speed_mph"),
                avg("volume_vehicles_per_hour").alias("avg_volume_vph"),
                max("volume_vehicles_per_hour").alias("max_volume_vph"),
                sum("volume_vehicles_per_hour").alias("total_volume_vph"),
                count("*").alias("reading_count"),
                first("data_source").alias("data_source")
            ).select(
                col("window.start").alias("window_start"),
                col("window.end").alias("window_end"),
                col("sensor_id"),
                col("road_name"),
                col("road_type"),
                col("direction"),
                col("latitude"),
                col("longitude"),
                col("avg_speed_mph"),
                col("max_speed_mph"),
                col("min_speed_mph"),
                col("avg_volume_vph"),
                col("max_volume_vph"),
                col("total_volume_vph"),
                col("reading_count"),
                col("data_source"),
                current_timestamp().alias("processed_timestamp")
            )
        
        return sensor_aggregates
    
    def create_road_level_aggregations(self, df):
        """Create road-level aggregations"""
        
        road_aggregates = df \
            .filter(col("speed_mph").isNotNull() | col("volume_vehicles_per_hour").isNotNull()) \
            .groupBy(
                window(col("timestamp"), "5 minutes"),
                col("road_name"),
                col("road_type"),
                col("direction")
            ).agg(
                avg("speed_mph").alias("avg_speed_mph"),
                avg("volume_vehicles_per_hour").alias("avg_volume_vph"),
                sum("volume_vehicles_per_hour").alias("total_volume_vph"),
                count("*").alias("sensor_count"),
                collect_list("sensor_id").alias("sensor_ids"),
                first("data_source").alias("data_source")
            ).select(
                col("window.start").alias("window_start"),
                col("window.end").alias("window_end"),
                col("road_name"),
                col("road_type"),
                col("direction"),
                col("avg_speed_mph"),
                col("avg_volume_vph"),
                col("total_volume_vph"),
                col("sensor_count"),
                col("sensor_ids"),
                col("data_source"),
                current_timestamp().alias("processed_timestamp")
            )
        
        return road_aggregates
    
    def write_to_hdfs(self, df, output_path: str, checkpoint_path: str):
        """Write streaming DataFrame to HDFS with checkpointing"""
        
        query = df.writeStream \
            .format("parquet") \
            .option("path", output_path) \
            .option("checkpointLocation", checkpoint_path) \
            .partitionBy("road_type") \
            .outputMode("append") \
            .trigger(processingTime="30 seconds") \
            .start()
        
        return query
    
    def start_processing(self):
        """Start the streaming processing pipeline"""
        logger.info("Starting traffic stream processing...")
        
        try:
            # Read from Kafka
            raw_stream = self.read_kafka_stream()
            
            # Create aggregations
            sensor_aggs = self.create_windowed_aggregations(raw_stream)
            road_aggs = self.create_road_level_aggregations(raw_stream)
            
            # Write raw events to HDFS
            raw_query = self.write_to_hdfs(
                raw_stream,
                self.hdfs_config['raw_events_path'],
                self.hdfs_config['raw_events_checkpoint']
            )
            
            # Write sensor aggregations to HDFS
            sensor_query = self.write_to_hdfs(
                sensor_aggs,
                self.hdfs_config['sensor_aggregates_path'],
                self.hdfs_config['sensor_aggregates_checkpoint']
            )
            
            # Write road aggregations to HDFS
            road_query = self.write_to_hdfs(
                road_aggs,
                self.hdfs_config['road_aggregates_path'],
                self.hdfs_config['road_aggregates_checkpoint']
            )
            
            # Start console output for monitoring (optional)
            console_query = sensor_aggs \
                .writeStream \
                .outputMode("append") \
                .format("console") \
                .option("truncate", "false") \
                .option("numRows", 5) \
                .trigger(processingTime="60 seconds") \
                .start()
            
            logger.info("Streaming queries started successfully")
            logger.info("Raw events -> " + self.hdfs_config['raw_events_path'])
            logger.info("Sensor aggregates -> " + self.hdfs_config['sensor_aggregates_path'])
            logger.info("Road aggregates -> " + self.hdfs_config['road_aggregates_path'])
            
            # Wait for termination
            raw_query.awaitTermination()
            
        except Exception as e:
            logger.error(f"Error in streaming processing: {e}")
            raise
        finally:
            self.spark.stop()

def main():
    """Main function"""
    
    # Configuration
    kafka_config = {
        'bootstrap_servers': 'localhost:9093',
        'topic': 'traffic-events'
    }
    
    hdfs_config = {
        'raw_events_path': 'hdfs://localhost:9000/traffic-data/streaming/raw-events',
        'sensor_aggregates_path': 'hdfs://localhost:9000/traffic-data/streaming/sensor-aggregates',
        'road_aggregates_path': 'hdfs://localhost:9000/traffic-data/streaming/road-aggregates',
        'raw_events_checkpoint': '/tmp/spark-checkpoint/raw-events',
        'sensor_aggregates_checkpoint': '/tmp/spark-checkpoint/sensor-aggregates',
        'road_aggregates_checkpoint': '/tmp/spark-checkpoint/road-aggregates'
    }
    
    # Start processing
    processor = TrafficStreamProcessor(kafka_config, hdfs_config)
    processor.start_processing()

if __name__ == "__main__":
    main()
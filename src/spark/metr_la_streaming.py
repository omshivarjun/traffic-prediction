#!/usr/bin/env python3
"""
METR-LA Spark Structured Streaming Consumer
Consumes traffic events from Kafka, processes them in real-time,
and writes structured data to HDFS with proper time-based partitioning
"""

import os
import sys
import json
import logging
import signal
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass, asdict

# PySpark imports
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, 
    DoubleType, TimestampType, BooleanType, LongType, MapType
)
from pyspark.sql.functions import (
    col, window, avg, sum as spark_sum, count, max as spark_max, 
    min as spark_min, when, unix_timestamp, from_json, to_json,
    current_timestamp, expr, lit, coalesce, round as spark_round,
    from_unixtime, date_format, collect_list, struct, split, regexp_extract,
    hour, dayofweek, month, year, stddev, percentile_approx
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("metr_la_streaming")

@dataclass
class MetrLAStreamingConfig:
    """Configuration for METR-LA Spark Streaming application"""
    # Spark Configuration
    app_name: str = "MetrLA-TrafficStreaming"
    master: str = "local[*]"
    
    # Kafka Configuration
    kafka_bootstrap_servers: str = "localhost:9094"
    input_topic: str = "traffic-events"
    output_topic_aggregates: str = "processed-traffic-aggregates"
    output_topic_predictions: str = "traffic-predictions"
    kafka_starting_offsets: str = "latest"
    
    # Processing Configuration
    window_duration: str = "5 minutes"
    slide_duration: str = "1 minute"
    watermark_delay: str = "2 minutes"
    congestion_speed_threshold_mph: float = 25.0  # mph
    congestion_speed_threshold_kmh: float = 40.0  # km/h
    
    # Output Configuration
    hdfs_output_path: str = "hdfs://localhost:9001/traffic-data/streaming"
    checkpoint_location: str = "hdfs://localhost:9001/traffic-data/checkpoints/streaming"
    
    # Performance Configuration
    max_offsets_per_trigger: int = 5000
    trigger_processing_time: str = "30 seconds"
    output_mode: str = "append"
    
    # Logging Configuration
    log_level: str = "INFO"

class MetrLAStreamingProcessor:
    """Spark Structured Streaming processor for METR-LA traffic data"""
    
    def __init__(self, config: MetrLAStreamingConfig):
        """Initialize the streaming processor"""
        self.config = config
        self.spark: Optional[SparkSession] = None
        self.running_queries: List[Any] = []
        self.logger = self._setup_logging()
        
        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logger = logging.getLogger("metr_la_streaming")
        logger.setLevel(getattr(logging, self.config.log_level.upper()))
        
        # Clear existing handlers
        logger.handlers.clear()
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        return logger
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.shutdown()
    
    def initialize_spark(self):
        """Initialize Spark session with streaming and Kafka support"""
        self.logger.info("Initializing Spark session for streaming...")
        
        try:
            # Create Spark session with optimized configuration
            builder = SparkSession.builder \
                .appName(self.config.app_name) \
                .master(self.config.master) \
                .config("spark.sql.streaming.checkpointLocation", self.config.checkpoint_location) \
                .config("spark.sql.streaming.stateStore.maintenanceInterval", "60s") \
                .config("spark.sql.adaptive.enabled", "true") \
                .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
                .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
                .config("spark.sql.streaming.metricsEnabled", "true") \
                .config("spark.sql.execution.arrow.pyspark.enabled", "true") \
                .config("spark.sql.shuffle.partitions", "200") \
                .config("spark.default.parallelism", "8")
            
            self.spark = builder.getOrCreate()
            
            # Set log level
            self.spark.sparkContext.setLogLevel(self.config.log_level)
            
            self.logger.info(f"Spark session initialized successfully - Version: {self.spark.version}")
            self.logger.info(f"Checkpoint location: {self.config.checkpoint_location}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Spark session: {e}")
            raise
    
    def get_metr_la_event_schema(self) -> StructType:
        """Define schema for METR-LA traffic events from Kafka"""
        return StructType([
            StructField("event_id", StringType(), True),
            StructField("segment_id", StringType(), True),
            StructField("timestamp", LongType(), True),  # epoch milliseconds
            StructField("speed_kmh", DoubleType(), True),
            StructField("speed_mph", DoubleType(), True),
            StructField("volume_vph", IntegerType(), True),
            StructField("occupancy", DoubleType(), True),
            StructField("coordinates", StructType([
                StructField("latitude", DoubleType(), True),
                StructField("longitude", DoubleType(), True)
            ]), True),
            StructField("source", StringType(), True),
            StructField("quality_score", DoubleType(), True),
            StructField("metadata", MapType(StringType(), StringType()), True)
        ])
    
    def read_kafka_stream(self) -> DataFrame:
        """Read streaming data from Kafka traffic-events topic"""
        self.logger.info(f"Setting up Kafka stream from topic: {self.config.input_topic}")
        
        try:
            if not self.spark:
                raise RuntimeError("Spark session not initialized")
            
            # Read from Kafka
            kafka_df = self.spark.readStream \
                .format("kafka") \
                .option("kafka.bootstrap.servers", self.config.kafka_bootstrap_servers) \
                .option("subscribe", self.config.input_topic) \
                .option("startingOffsets", self.config.kafka_starting_offsets) \
                .option("maxOffsetsPerTrigger", self.config.max_offsets_per_trigger) \
                .option("failOnDataLoss", "false") \
                .load()
            
            # Parse JSON messages
            event_schema = self.get_metr_la_event_schema()
            
            parsed_df = kafka_df.select(
                col("key").cast("string").alias("kafka_key"),
                col("topic").alias("kafka_topic"),
                col("partition").alias("kafka_partition"),
                col("offset").alias("kafka_offset"),
                col("timestamp").alias("kafka_timestamp"),
                from_json(col("value").cast("string"), event_schema).alias("data")
            ).select(
                col("kafka_key"),
                col("kafka_topic"), 
                col("kafka_partition"),
                col("kafka_offset"),
                col("kafka_timestamp"),
                col("data.*")
            )
            
            # Convert timestamp and add processing time
            processed_df = parsed_df.withColumn(
                "event_time", 
                (col("timestamp") / 1000).cast(TimestampType())
            ).withColumn(
                "processing_time", current_timestamp()
            ).withColumn(
                "ingestion_delay_seconds",
                unix_timestamp(col("processing_time")) - unix_timestamp(col("event_time"))
            )
            
            self.logger.info("Kafka stream setup completed")
            return processed_df
            
        except Exception as e:
            self.logger.error(f"Failed to setup Kafka stream: {e}")
            raise
    
    def enrich_traffic_data(self, df: DataFrame) -> DataFrame:
        """Enrich traffic data with derived features"""
        enriched_df = df.withColumn(
            # Extract sensor information from metadata
            "sensor_id", col("metadata").getItem("sensor_id")
        ).withColumn(
            "road_name", col("metadata").getItem("road_name")
        ).withColumn(
            "road_type", col("metadata").getItem("road_type")
        ).withColumn(
            "direction", col("metadata").getItem("direction")
        ).withColumn(
            # Time-based features
            "hour_of_day", hour(col("event_time"))
        ).withColumn(
            "day_of_week", dayofweek(col("event_time"))
        ).withColumn(
            "month", month(col("event_time"))
        ).withColumn(
            "is_weekend", 
            when((col("day_of_week") == 1) | (col("day_of_week") == 7), lit(True)).otherwise(lit(False))
        ).withColumn(
            "is_rush_hour",
            when(
                ((col("hour_of_day") >= 7) & (col("hour_of_day") <= 9)) | 
                ((col("hour_of_day") >= 17) & (col("hour_of_day") <= 19)),
                lit(True)
            ).otherwise(lit(False))
        ).withColumn(
            # Congestion detection
            "is_congested_mph",
            when(col("speed_mph").isNull(), lit(False))
            .when(col("speed_mph") < self.config.congestion_speed_threshold_mph, lit(True))
            .otherwise(lit(False))
        ).withColumn(
            "is_congested_kmh",
            when(col("speed_kmh").isNull(), lit(False))
            .when(col("speed_kmh") < self.config.congestion_speed_threshold_kmh, lit(True))
            .otherwise(lit(False))
        ).withColumn(
            "congestion_level",
            when(col("speed_mph").isNull(), lit("unknown"))
            .when(col("speed_mph") < 15, lit("severe"))
            .when(col("speed_mph") < 25, lit("heavy"))
            .when(col("speed_mph") < 35, lit("moderate"))
            .otherwise(lit("free_flow"))
        ).withColumn(
            # Traffic efficiency metrics
            "traffic_efficiency",
            when(col("volume_vph").isNull() | (col("volume_vph") == 0), lit(0))
            .otherwise(coalesce(col("speed_mph"), lit(0)) / (col("volume_vph") / 100.0))
        )
        
        return enriched_df
    
    def create_windowed_aggregates(self, enriched_df: DataFrame) -> DataFrame:
        """Create windowed aggregations for traffic analytics"""
        self.logger.info("Creating windowed traffic aggregations...")
        
        # Add watermark for late data handling
        watermarked_df = enriched_df.withWatermark("event_time", self.config.watermark_delay)
        
        # Filter out low quality data
        quality_df = watermarked_df.filter(col("quality_score") >= 0.5)
        
        # Create windowed aggregations
        windowed_aggregates = quality_df \
            .groupBy(
                col("sensor_id"),
                col("segment_id"),
                window(col("event_time"), self.config.window_duration, self.config.slide_duration),
                col("road_name"),
                col("road_type"),
                col("direction")
            ) \
            .agg(
                # Speed metrics (both mph and km/h)
                avg("speed_mph").alias("avg_speed_mph"),
                spark_min(col("speed_mph")).alias("min_speed_mph"),
                spark_max(col("speed_mph")).alias("max_speed_mph"),
                stddev("speed_mph").alias("stddev_speed_mph"),
                percentile_approx("speed_mph", 0.5).alias("median_speed_mph"),
                
                avg("speed_kmh").alias("avg_speed_kmh"),
                spark_min(col("speed_kmh")).alias("min_speed_kmh"),
                spark_max(col("speed_kmh")).alias("max_speed_kmh"),
                
                # Volume metrics
                avg("volume_vph").alias("avg_volume_vph"),
                spark_min(col("volume_vph")).alias("min_volume_vph"),
                spark_max(col("volume_vph")).alias("max_volume_vph"),
                spark_sum("volume_vph").alias("total_volume"),
                
                # Quality and efficiency metrics
                avg("quality_score").alias("avg_quality_score"),
                avg("traffic_efficiency").alias("avg_traffic_efficiency"),
                
                # Congestion metrics
                spark_sum(when(col("is_congested_mph"), 1).otherwise(0)).alias("congested_count"),
                count("*").alias("total_count"),
                
                # Coordinates (assuming similar for sensor)
                avg("coordinates.latitude").alias("avg_latitude"),
                avg("coordinates.longitude").alias("avg_longitude"),
                
                # Time features
                avg("hour_of_day").alias("avg_hour_of_day"),
                spark_max(col("is_weekend")).alias("is_weekend"),
                spark_max(col("is_rush_hour")).alias("is_rush_hour"),
                
                # Data freshness
                avg("ingestion_delay_seconds").alias("avg_ingestion_delay_seconds"),
                spark_max(col("processing_time")).alias("latest_processing_time"),
                
                # Event tracking
                collect_list("event_id").alias("event_ids")
            ) \
            .withColumn("congestion_ratio", col("congested_count") / col("total_count")) \
            .withColumn("window_start", col("window.start")) \
            .withColumn("window_end", col("window.end")) \
            .withColumn("processing_timestamp", current_timestamp()) \
            .drop("window")
        
        # Add traffic flow classification
        classified_aggregates = windowed_aggregates.withColumn(
            "traffic_flow_level",
            when(col("congestion_ratio") >= 0.8, lit("heavy_congestion"))
            .when(col("congestion_ratio") >= 0.6, lit("moderate_congestion"))
            .when(col("congestion_ratio") >= 0.3, lit("light_congestion"))
            .otherwise(lit("free_flow"))
        ).withColumn(
            "speed_variability",
            when(col("avg_speed_mph").isNull() | (col("avg_speed_mph") == 0), lit(0))
            .otherwise(coalesce(col("stddev_speed_mph"), lit(0)) / col("avg_speed_mph"))
        )
        
        return classified_aggregates
    
    def start_hdfs_sink(self, aggregates_df: DataFrame):
        """Start HDFS sink for processed aggregates with time-based partitioning"""
        self.logger.info(f"Starting HDFS sink to path: {self.config.hdfs_output_path}")
        
        try:
            # Prepare data for HDFS storage with time-based partitioning
            hdfs_output = aggregates_df.withColumn(
                "year", year(col("window_start"))
            ).withColumn(
                "month", date_format(col("window_start"), "MM")
            ).withColumn(
                "day", date_format(col("window_start"), "dd")
            ).withColumn(
                "hour", date_format(col("window_start"), "HH")
            )
            
            query = hdfs_output.writeStream \
                .format("parquet") \
                .option("path", self.config.hdfs_output_path) \
                .option("checkpointLocation", f"{self.config.checkpoint_location}/hdfs") \
                .partitionBy("year", "month", "day", "hour") \
                .outputMode(self.config.output_mode) \
                .trigger(processingTime=self.config.trigger_processing_time) \
                .start()
            
            self.running_queries.append(query)
            self.logger.info("HDFS sink started successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to start HDFS sink: {e}")
            raise
    
    def start_kafka_aggregates_sink(self, aggregates_df: DataFrame):
        """Start Kafka sink for processed aggregates"""
        self.logger.info(f"Starting Kafka aggregates sink to topic: {self.config.output_topic_aggregates}")
        
        try:
            # Convert to JSON for Kafka output
            kafka_output = aggregates_df.select(
                col("sensor_id").alias("key"),
                to_json(struct([
                    col("sensor_id"),
                    col("segment_id"),
                    col("window_start"),
                    col("window_end"),
                    col("avg_speed_mph"),
                    col("avg_speed_kmh"),
                    col("avg_volume_vph"),
                    col("total_volume"),
                    col("congestion_ratio"),
                    col("traffic_flow_level"),
                    col("speed_variability"),
                    col("total_count"),
                    col("avg_quality_score"),
                    col("avg_latitude"),
                    col("avg_longitude"),
                    col("road_name"),
                    col("road_type"),
                    col("direction"),
                    col("is_weekend"),
                    col("is_rush_hour"),
                    col("processing_timestamp")
                ])).alias("value")
            )
            
            query = kafka_output.writeStream \
                .format("kafka") \
                .option("kafka.bootstrap.servers", self.config.kafka_bootstrap_servers) \
                .option("topic", self.config.output_topic_aggregates) \
                .option("checkpointLocation", f"{self.config.checkpoint_location}/kafka-aggregates") \
                .outputMode(self.config.output_mode) \
                .trigger(processingTime=self.config.trigger_processing_time) \
                .start()
            
            self.running_queries.append(query)
            self.logger.info("Kafka aggregates sink started")
            
        except Exception as e:
            self.logger.error(f"Failed to start Kafka aggregates sink: {e}")
            raise
    
    def start_console_sink(self, aggregates_df: DataFrame):
        """Start console sink for monitoring"""
        try:
            # Select key metrics for console output
            console_output = aggregates_df.select(
                col("sensor_id"),
                col("window_start"),
                col("avg_speed_mph"),
                col("avg_volume_vph"),
                col("congestion_ratio"),
                col("traffic_flow_level"),
                col("total_count"),
                col("avg_quality_score")
            )
            
            query = console_output.writeStream \
                .format("console") \
                .option("truncate", "false") \
                .option("numRows", 10) \
                .outputMode(self.config.output_mode) \
                .trigger(processingTime=self.config.trigger_processing_time) \
                .start()
            
            self.running_queries.append(query)
            self.logger.info("Console monitoring sink started")
            
        except Exception as e:
            self.logger.error(f"Failed to start console sink: {e}")
            # Don't raise for console sink failures
    
    def process_metr_la_stream(self):
        """Process METR-LA traffic data stream"""
        self.logger.info("Starting METR-LA traffic stream processing...")
        
        try:
            # Read Kafka stream
            raw_stream = self.read_kafka_stream()
            
            # Enrich with derived features
            enriched_stream = self.enrich_traffic_data(raw_stream)
            
            # Create windowed aggregations
            aggregated_stream = self.create_windowed_aggregates(enriched_stream)
            
            # Start output sinks
            self.start_hdfs_sink(aggregated_stream)
            self.start_kafka_aggregates_sink(aggregated_stream)
            self.start_console_sink(aggregated_stream)
            
            self.logger.info("METR-LA stream processing started successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to process METR-LA stream: {e}")
            raise
    
    def wait_for_termination(self):
        """Wait for all streaming queries to terminate"""
        self.logger.info("Waiting for streaming queries to terminate...")
        
        try:
            for query in self.running_queries:
                query.awaitTermination()
        except KeyboardInterrupt:
            self.logger.info("Received interrupt signal")
            self.shutdown()
    
    def shutdown(self):
        """Gracefully shutdown streaming processor"""
        self.logger.info("Shutting down METR-LA streaming processor...")
        
        try:
            # Stop all running queries
            for query in self.running_queries:
                if query.isActive:
                    self.logger.info(f"Stopping query: {query.name or query.id}")
                    query.stop()
            
            # Stop Spark session
            if self.spark:
                self.spark.stop()
            
            self.logger.info("METR-LA streaming processor shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")

def create_default_config() -> MetrLAStreamingConfig:
    """Create default streaming configuration"""
    return MetrLAStreamingConfig()

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='METR-LA Spark Structured Streaming Processor')
    parser.add_argument('--kafka-broker', default='localhost:9094', help='Kafka broker address')
    parser.add_argument('--input-topic', default='traffic-events', help='Input Kafka topic')
    parser.add_argument('--hdfs-path', default='hdfs://localhost:9001/traffic-data/streaming', 
                       help='HDFS output path')
    parser.add_argument('--checkpoint-path', default='hdfs://localhost:9001/traffic-data/checkpoints/streaming',
                       help='Checkpoint location')
    parser.add_argument('--window-duration', default='5 minutes', help='Window duration')
    parser.add_argument('--trigger-interval', default='30 seconds', help='Trigger processing time')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                       default='INFO', help='Log level')
    
    args = parser.parse_args()
    
    # Create configuration
    config = MetrLAStreamingConfig(
        kafka_bootstrap_servers=args.kafka_broker,
        input_topic=args.input_topic,
        hdfs_output_path=args.hdfs_path,
        checkpoint_location=args.checkpoint_path,
        window_duration=args.window_duration,
        trigger_processing_time=args.trigger_interval,
        log_level=args.log_level
    )
    
    # Initialize processor
    processor = MetrLAStreamingProcessor(config)
    
    try:
        print("🚀 Starting METR-LA Spark Structured Streaming")
        print(f"📡 Input Topic: {args.input_topic}")
        print(f"💾 HDFS Output: {args.hdfs_path}")
        print(f"⏱️  Window Duration: {args.window_duration}")
        print(f"🔄 Trigger Interval: {args.trigger_interval}")
        print("=" * 60)
        
        processor.initialize_spark()
        processor.process_metr_la_stream()
        processor.wait_for_termination()
        
        print("✅ METR-LA streaming processing completed!")
        
    except KeyboardInterrupt:
        processor.logger.info("Received keyboard interrupt")
    except Exception as e:
        processor.logger.error(f"Streaming processor failed: {e}", exc_info=True)
        return 1
    finally:
        processor.shutdown()
    
    return 0

if __name__ == "__main__":
    exit(main())
#!/usr/bin/env python3
"""
Spark Streaming Jobs for Traffic Analytics - Task 9
Real-time processing of traffic data streams with windowed aggregations and multi-output sinks

This module implements:
- Spark Streaming context setup with Kafka integration
- Real-time traffic data processing with congestion detection
- Windowed aggregations for traffic analytics
- Multi-output destinations (Kafka, PostgreSQL, HDFS, cache)
"""

import os
import sys
import json
import logging
import signal
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    # Import for type checking only to avoid runtime import issues
    pass
from dataclasses import dataclass, asdict
from pathlib import Path

# PySpark imports
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, 
    DoubleType, TimestampType, BooleanType
)
from pyspark.sql.functions import (
    col, window, avg, sum as spark_sum, count, max as spark_max, 
    min as spark_min, when, unix_timestamp, from_json, to_json,
    current_timestamp, expr, lit, coalesce, round as spark_round,
    from_unixtime, date_format, collect_list, struct
)


@dataclass
class StreamingConfig:
    """Configuration for Spark Streaming application"""
    # Spark Configuration
    app_name: str = "TrafficPredictionStreaming"
    master: str = "local[*]"
    batch_interval_seconds: int = 10
    
    # Kafka Configuration
    kafka_bootstrap_servers: str = "localhost:9092"
    input_topic: str = "traffic-raw"
    output_topic_aggregates: str = "traffic-aggregates"
    output_topic_alerts: str = "traffic-alerts"
    kafka_starting_offsets: str = "latest"
    
    # Processing Configuration
    window_duration: str = "5 minutes"
    slide_duration: str = "30 seconds"
    congestion_speed_threshold: float = 40.0  # km/h (roughly 25 mph)
    watermark_delay: str = "1 minute"
    
    # Output Configuration
    hdfs_output_path: str = "hdfs://localhost:9000/traffic/streaming"
    checkpoint_location: str = "hdfs://localhost:9000/traffic/checkpoints"
    postgresql_url: str = "jdbc:postgresql://localhost:5432/traffic_prediction"
    postgresql_table: str = "traffic_aggregates"
    postgresql_user: str = "postgres"
    postgresql_password: str = "casa1234"
    
    # Performance Configuration
    max_offsets_per_trigger: int = 10000
    trigger_processing_time: str = "10 seconds"
    output_mode: str = "append"
    
    # Logging Configuration
    log_level: str = "INFO"


class TrafficStreamingProcessor:
    """Spark Streaming processor for real-time traffic data"""
    
    def __init__(self, config: StreamingConfig):
        """Initialize Spark Streaming processor"""
        self.config = config
        self.spark: Optional[SparkSession] = None
        self.running_queries: List[Any] = []  # StreamingQuery objects
        self.logger = self._setup_logging()
        
        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logger = logging.getLogger("traffic_streaming")
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
    
    def initialize(self):
        """Initialize Spark session and streaming context"""
        self.logger.info("Initializing Spark Streaming session...")
        
        try:
            # Create Spark session with streaming and Kafka support
            builder = SparkSession.builder
            # Use getattr to handle dynamic API access
            builder = getattr(builder, 'appName')(self.config.app_name)
            builder = getattr(builder, 'master')(self.config.master) 
            builder = builder.config("spark.sql.streaming.checkpointLocation", self.config.checkpoint_location)
            builder = builder.config("spark.sql.streaming.stateStore.maintenanceInterval", "30s")
            builder = builder.config("spark.sql.adaptive.enabled", "true")
            builder = builder.config("spark.sql.adaptive.coalescePartitions.enabled", "true")
            builder = builder.config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
            builder = builder.config("spark.sql.streaming.metricsEnabled", "true")
            builder = builder.config("spark.sql.execution.arrow.pyspark.enabled", "true")
            
            self.spark = builder.getOrCreate()
            
            # Set log level
            if self.spark and hasattr(self.spark, 'sparkContext'):
                self.spark.sparkContext.setLogLevel(self.config.log_level)
            
            self.logger.info("Spark session initialized successfully")
            if self.spark and hasattr(self.spark, 'version'):
                self.logger.info(f"Spark version: {self.spark.version}")
            self.logger.info(f"Checkpoint location: {self.config.checkpoint_location}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Spark session: {e}")
            raise
    
    def get_traffic_event_schema(self) -> StructType:
        """Define schema for incoming traffic events"""
        return StructType([
            StructField("event_id", StringType(), True),
            StructField("segment_id", StringType(), True),
            StructField("timestamp", IntegerType(), True),  # epoch milliseconds
            StructField("speed_kmh", DoubleType(), True),
            StructField("volume_vph", IntegerType(), True),
            StructField("occupancy_percent", DoubleType(), True),
            StructField("coordinates", StructType([
                StructField("latitude", DoubleType(), True),
                StructField("longitude", DoubleType(), True)
            ]), True),
            StructField("source", StringType(), True),
            StructField("quality_score", DoubleType(), True),
            StructField("metadata", StructType([
                StructField("sensor_id", StringType(), True),
                StructField("road_type", StringType(), True),
                StructField("road_name", StringType(), True),
                StructField("direction", StringType(), True),
                StructField("lanes", StringType(), True),
                StructField("original_timestamp", StringType(), True)
            ]), True)
        ])
    
    def read_kafka_stream(self) -> DataFrame:
        """Read streaming data from Kafka topic"""
        self.logger.info(f"Setting up Kafka stream from topic: {self.config.input_topic}")
        
        try:
            # Read from Kafka
            if not self.spark:
                raise RuntimeError("Spark session not initialized")
                
            kafka_df = getattr(self.spark, 'readStream') \
                .format("kafka") \
                .option("kafka.bootstrap.servers", self.config.kafka_bootstrap_servers) \
                .option("subscribe", self.config.input_topic) \
                .option("startingOffsets", self.config.kafka_starting_offsets) \
                .option("maxOffsetsPerTrigger", self.config.max_offsets_per_trigger) \
                .option("failOnDataLoss", "false") \
                .load()
            
            # Parse JSON messages
            traffic_schema = self.get_traffic_event_schema()
            
            parsed_df = kafka_df.select(
                col("key").cast("string").alias("kafka_key"),
                col("topic").alias("kafka_topic"),
                col("partition").alias("kafka_partition"),
                col("offset").alias("kafka_offset"),
                col("timestamp").alias("kafka_timestamp"),
                from_json(col("value").cast("string"), traffic_schema).alias("data")
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
                "event_time", from_unixtime(col("timestamp") / 1000).cast(TimestampType())
            ).withColumn(
                "processing_time", current_timestamp()
            )
            
            self.logger.info("Kafka stream setup completed")
            return processed_df
            
        except Exception as e:
            self.logger.error(f"Failed to setup Kafka stream: {e}")
            raise
    
    def detect_congestion(self, df: DataFrame) -> DataFrame:
        """Detect congestion based on speed thresholds"""
        return df.withColumn(
            "is_congested",
            when(col("speed_kmh").isNull(), lit(False))
            .when(col("speed_kmh") < self.config.congestion_speed_threshold, lit(True))
            .otherwise(lit(False))
        ).withColumn(
            "congestion_level",
            when(col("speed_kmh").isNull(), lit("unknown"))
            .when(col("speed_kmh") < 20, lit("severe"))
            .when(col("speed_kmh") < 30, lit("heavy"))
            .when(col("speed_kmh") < 40, lit("moderate"))
            .otherwise(lit("free_flow"))
        )
    
    def calculate_traffic_density(self, df: DataFrame) -> DataFrame:
        """Calculate traffic density metrics"""
        return df.withColumn(
            "density_vehicles_km",
            when(col("speed_kmh").isNull() | (col("speed_kmh") == 0), lit(0))
            .otherwise(col("volume_vph") / col("speed_kmh"))
        ).withColumn(
            "flow_efficiency",
            when(col("volume_vph").isNull() | col("occupancy_percent").isNull(), lit(0))
            .when(col("occupancy_percent") == 0, lit(1))
            .otherwise(col("volume_vph") / col("occupancy_percent"))
        )
    
    def process_traffic_stream(self):
        """Process real-time traffic data streams with windowed aggregations"""
        self.logger.info("Starting traffic stream processing...")
        
        try:
            # Read Kafka stream
            raw_stream = self.read_kafka_stream()
            
            # Add watermark for late data handling
            watermarked_stream = raw_stream.withWatermark("event_time", self.config.watermark_delay)
            
            # Detect congestion and calculate metrics
            enriched_stream = self.detect_congestion(watermarked_stream)
            enriched_stream = self.calculate_traffic_density(enriched_stream)
            
            # Filter out low quality data
            quality_stream = enriched_stream.filter(col("quality_score") >= 0.5)
            
            # Create windowed aggregations
            windowed_aggregates = quality_stream \
                .groupBy(
                    col("segment_id"),
                    window(col("event_time"), self.config.window_duration, self.config.slide_duration),
                    col("metadata.road_name"),
                    col("metadata.road_type"),
                    col("metadata.direction")
                ) \
                .agg(
                    # Speed metrics
                    avg("speed_kmh").alias("avg_speed_kmh"),
                    spark_min("speed_kmh").alias("min_speed_kmh"),
                    spark_max("speed_kmh").alias("max_speed_kmh"),
                    
                    # Volume metrics
                    avg("volume_vph").alias("avg_volume_vph"),
                    spark_sum("volume_vph").alias("total_volume"),
                    
                    # Occupancy metrics
                    avg("occupancy_percent").alias("avg_occupancy_percent"),
                    spark_max("occupancy_percent").alias("max_occupancy_percent"),
                    
                    # Density metrics
                    avg("density_vehicles_km").alias("avg_density_vehicles_km"),
                    avg("flow_efficiency").alias("avg_flow_efficiency"),
                    
                    # Congestion metrics
                    spark_sum(when(col("is_congested"), 1).otherwise(0)).alias("congested_count"),
                    count("*").alias("total_count"),
                    avg("quality_score").alias("avg_quality_score"),
                    
                    # Coordinates (assuming similar for segment)
                    avg("coordinates.latitude").alias("avg_latitude"),
                    avg("coordinates.longitude").alias("avg_longitude"),
                    
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
            )
            
            # Start multiple output sinks
            self._start_kafka_sink(classified_aggregates)
            self._start_hdfs_sink(classified_aggregates)
            self._start_console_sink(classified_aggregates)
            self._start_alert_sink(enriched_stream)
            
            self.logger.info("Traffic stream processing started successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to process traffic stream: {e}")
            raise
    
    def _start_kafka_sink(self, df: DataFrame):
        """Start Kafka sink for processed aggregates"""
        self.logger.info(f"Starting Kafka sink to topic: {self.config.output_topic_aggregates}")
        
        try:
            # Convert to JSON for Kafka output
            kafka_output = df.select(
                col("segment_id").alias("key"),
                to_json(struct([
                    col("segment_id"),
                    col("window_start"),
                    col("window_end"),
                    col("avg_speed_kmh"),
                    col("avg_volume_vph"),
                    col("avg_occupancy_percent"),
                    col("avg_density_vehicles_km"),
                    col("congestion_ratio"),
                    col("traffic_flow_level"),
                    col("total_count"),
                    col("avg_quality_score"),
                    col("avg_latitude"),
                    col("avg_longitude"),
                    col("road_name"),
                    col("road_type"),
                    col("direction"),
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
            self.logger.error(f"Failed to start Kafka sink: {e}")
            raise
    
    def _start_hdfs_sink(self, df: DataFrame):
        """Start HDFS sink for long-term storage"""
        self.logger.info(f"Starting HDFS sink to path: {self.config.hdfs_output_path}")
        
        try:
            # Prepare data for HDFS storage with partitioning
            hdfs_output = df.withColumn(
                "year", date_format(col("window_start"), "yyyy")
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
            self.logger.info("HDFS sink started")
            
        except Exception as e:
            self.logger.error(f"Failed to start HDFS sink: {e}")
            raise
    
    def _start_console_sink(self, df: DataFrame):
        """Start console sink for monitoring"""
        try:
            # Select key metrics for console output
            console_output = df.select(
                col("segment_id"),
                col("window_start"),
                col("avg_speed_kmh"),
                col("avg_volume_vph"),
                col("congestion_ratio"),
                col("traffic_flow_level"),
                col("total_count")
            )
            
            query = console_output.writeStream \
                .format("console") \
                .option("truncate", "false") \
                .option("numRows", 20) \
                .outputMode(self.config.output_mode) \
                .trigger(processingTime=self.config.trigger_processing_time) \
                .start()
            
            self.running_queries.append(query)
            self.logger.info("Console sink started")
            
        except Exception as e:
            self.logger.error(f"Failed to start console sink: {e}")
            # Don't raise for console sink failures
    
    def _start_alert_sink(self, df: DataFrame):
        """Start alert sink for congestion alerts"""
        self.logger.info(f"Starting alert sink to topic: {self.config.output_topic_alerts}")
        
        try:
            # Filter for severe congestion events
            alert_conditions = df.filter(
                (col("congestion_level") == "severe") |
                (col("occupancy_percent") > 90) |
                (col("quality_score") < 0.3)
            )
            
            # Create alert messages
            alert_output = alert_conditions.select(
                col("segment_id").alias("key"),
                to_json(struct([
                    col("event_id"),
                    col("segment_id"),
                    col("event_time"),
                    col("speed_kmh"),
                    col("volume_vph"),
                    col("occupancy_percent"),
                    col("congestion_level"),
                    col("quality_score"),
                    col("coordinates"),
                    col("metadata"),
                    lit("congestion_alert").alias("alert_type"),
                    current_timestamp().alias("alert_timestamp")
                ])).alias("value")
            )
            
            query = alert_output.writeStream \
                .format("kafka") \
                .option("kafka.bootstrap.servers", self.config.kafka_bootstrap_servers) \
                .option("topic", self.config.output_topic_alerts) \
                .option("checkpointLocation", f"{self.config.checkpoint_location}/kafka-alerts") \
                .outputMode(self.config.output_mode) \
                .trigger(processingTime=self.config.trigger_processing_time) \
                .start()
            
            self.running_queries.append(query)
            self.logger.info("Alert sink started")
            
        except Exception as e:
            self.logger.error(f"Failed to start alert sink: {e}")
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
        """Gracefully shutdown streaming context"""
        self.logger.info("Shutting down streaming processor...")
        
        try:
            # Stop all running queries
            for query in self.running_queries:
                if query.isActive:
                    self.logger.info(f"Stopping query: {query.name or query.id}")
                    query.stop()
            
            # Stop Spark session
            if self.spark:
                self.spark.stop()
            
            self.logger.info("Streaming processor shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")


def load_config_from_file(config_file: str) -> StreamingConfig:
    """Load configuration from file"""
    config_path = Path(config_file)
    
    if config_path.exists():
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        return StreamingConfig(**config_data)
    else:
        return StreamingConfig()


def create_default_config_file(config_file: str):
    """Create default configuration file"""
    config = StreamingConfig()
    config_path = Path(config_file)
    
    # Create directory if it doesn't exist
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(config_path, 'w') as f:
        json.dump(asdict(config), f, indent=2)
    
    print(f"Created default configuration file: {config_file}")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Traffic Prediction Spark Streaming Processor')
    parser.add_argument('--config', '-c', default='config/streaming_config.json', 
                       help='Configuration file path')
    parser.add_argument('--create-config', action='store_true', 
                       help='Create default configuration file')
    parser.add_argument('--log-level', '-l', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                       help='Log level')
    
    args = parser.parse_args()
    
    # Create default config if requested
    if args.create_config:
        create_default_config_file(args.config)
        return
    
    # Load configuration
    config = load_config_from_file(args.config)
    
    if args.log_level:
        config.log_level = args.log_level
    
    # Initialize and run processor
    processor = TrafficStreamingProcessor(config)
    
    try:
        print("=" * 60)
        print("Traffic Prediction Spark Streaming Processor - Task 9")
        print("=" * 60)
        
        processor.initialize()
        processor.process_traffic_stream()
        processor.wait_for_termination()
        
    except KeyboardInterrupt:
        processor.logger.info("Received keyboard interrupt")
    except Exception as e:
        processor.logger.error(f"Streaming processor failed: {e}", exc_info=True)
    finally:
        processor.shutdown()


if __name__ == "__main__":
    main()
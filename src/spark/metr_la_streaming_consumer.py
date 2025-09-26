#!/usr/bin/env python3
"""
METR-LA Spark Structured Streaming Consumer
Kafka → Spark → HDFS pipeline for real-time traffic data processing

Features:
- Real-time streaming from Kafka
- Data aggregation and windowing
- HDFS storage with partitioning
- Schema validation
- Checkpointing for fault tolerance
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from pathlib import Path

# Add PySpark to path
spark_home = os.environ.get('SPARK_HOME', '/opt/bitnami/spark')
sys.path.append(os.path.join(spark_home, 'python'))
sys.path.append(os.path.join(spark_home, 'python', 'lib', 'py4j-0.10.9.7-src.zip'))

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import (
    col, from_json, to_timestamp, window, avg, max, min, count, 
    current_timestamp, date_format, year, month, dayofmonth, hour,
    stddev, percentile_approx, when, isnan, isnull, desc
)
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, IntegerType, 
    TimestampType, LongType
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("metr_la_spark_streaming")

class MetrLASparkStreaming:
    """Spark Structured Streaming for METR-LA traffic data pipeline"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Spark streaming with configuration"""
        self.config = config
        self.spark = None
        self._setup_spark_session()
        
    def _setup_spark_session(self):
        """Create Spark session with optimal configuration"""
        try:
            self.spark = SparkSession.builder \
                .appName("METR-LA-Traffic-Streaming") \
                .config("spark.master", "spark://spark-master:7077") \
                .config("spark.sql.adaptive.enabled", "true") \
                .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
                .config("spark.sql.streaming.checkpointLocation", "/tmp/spark-checkpoints") \
                .config("spark.hadoop.fs.defaultFS", "hdfs://namenode:9000") \
                .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
                .config("spark.sql.streaming.forceDeleteTempCheckpointLocation", "true") \
                .config("spark.sql.execution.arrow.pyspark.enabled", "true") \
                .config("spark.jars.packages", 
                       "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,"
                       "org.apache.hadoop:hadoop-client:3.2.1") \
                .getOrCreate()
            
            # Set log level
            self.spark.sparkContext.setLogLevel("WARN")
            
            logger.info("✅ Spark session created successfully")
            logger.info(f"   App Name: {self.spark.sparkContext.appName}")
            logger.info(f"   Master: {self.spark.sparkContext.master}")
            logger.info(f"   Spark Version: {self.spark.version}")
            
        except Exception as e:
            logger.error(f"❌ Failed to create Spark session: {e}")
            raise
    
    def get_traffic_event_schema(self) -> StructType:
        """Define schema for traffic events from Kafka"""
        return StructType([
            StructField("timestamp", StringType(), True),
            StructField("sensor_id", StringType(), True),
            StructField("speed_mph", DoubleType(), True),
            StructField("latitude", DoubleType(), True),
            StructField("longitude", DoubleType(), True),
            StructField("segment_id", StringType(), True),
            StructField("road_type", StringType(), True),
            StructField("lane_count", IntegerType(), True),
            StructField("event_id", StringType(), True),
            StructField("event_time", StringType(), True),
            StructField("pipeline_source", StringType(), True)
        ])
    
    def create_kafka_stream(self) -> DataFrame:
        """Create streaming DataFrame from Kafka"""
        try:
            kafka_config = self.config.get('kafka', {})
            
            stream_df = self.spark \
                .readStream \
                .format("kafka") \
                .option("kafka.bootstrap.servers", kafka_config.get('bootstrap_servers', 'kafka-broker1:9092')) \
                .option("subscribe", kafka_config.get('topic', 'traffic-events')) \
                .option("startingOffsets", "latest") \
                .option("failOnDataLoss", "false") \
                .option("maxOffsetsPerTrigger", 10000) \
                .load()
            
            logger.info("✅ Kafka stream created successfully")
            return stream_df
            
        except Exception as e:
            logger.error(f"❌ Failed to create Kafka stream: {e}")
            raise
    
    def parse_traffic_events(self, kafka_df: DataFrame) -> DataFrame:
        """Parse JSON messages from Kafka into structured data"""
        try:
            traffic_schema = self.get_traffic_event_schema()
            
            # Parse JSON and extract fields
            parsed_df = kafka_df \
                .select(
                    from_json(col("value").cast("string"), traffic_schema).alias("data"),
                    col("timestamp").alias("kafka_timestamp"),
                    col("offset"),
                    col("partition")
                ) \
                .select(
                    col("data.*"),
                    col("kafka_timestamp"),
                    col("offset"),
                    col("partition")
                ) \
                .withColumn("event_timestamp", to_timestamp(col("timestamp"), "yyyy-MM-dd HH:mm:ss")) \
                .withColumn("processing_time", current_timestamp()) \
                .filter(col("sensor_id").isNotNull()) \
                .filter(col("speed_mph").isNotNull()) \
                .filter(col("speed_mph") >= 0) \
                .filter(col("speed_mph") <= 120)  # Filter unrealistic speeds
            
            logger.info("✅ Traffic events parsing configured")
            return parsed_df
            
        except Exception as e:
            logger.error(f"❌ Failed to parse traffic events: {e}")
            raise
    
    def create_traffic_aggregates(self, traffic_df: DataFrame) -> DataFrame:
        """Create windowed aggregations for traffic data"""
        try:
            # 5-minute windowed aggregations
            aggregated_df = traffic_df \
                .withWatermark("event_timestamp", "10 minutes") \
                .groupBy(
                    window(col("event_timestamp"), "5 minutes"),
                    col("segment_id"),
                    col("sensor_id"),
                    col("road_type"),
                    col("lane_count")
                ) \
                .agg(
                    avg("speed_mph").alias("avg_speed_mph"),
                    max("speed_mph").alias("max_speed_mph"),
                    min("speed_mph").alias("min_speed_mph"),
                    stddev("speed_mph").alias("stddev_speed_mph"),
                    count("*").alias("record_count"),
                    percentile_approx("speed_mph", 0.5).alias("median_speed_mph"),
                    percentile_approx("speed_mph", 0.85).alias("p85_speed_mph")
                ) \
                .withColumn("window_start", col("window.start")) \
                .withColumn("window_end", col("window.end")) \
                .withColumn("aggregation_time", current_timestamp()) \
                .select(
                    col("window_start"),
                    col("window_end"), 
                    col("segment_id"),
                    col("sensor_id"),
                    col("road_type"),
                    col("lane_count"),
                    col("avg_speed_mph"),
                    col("max_speed_mph"),
                    col("min_speed_mph"),
                    col("stddev_speed_mph"),
                    col("median_speed_mph"),
                    col("p85_speed_mph"),
                    col("record_count"),
                    col("aggregation_time")
                )
            
            logger.info("✅ Traffic aggregations configured")
            return aggregated_df
            
        except Exception as e:
            logger.error(f"❌ Failed to create aggregations: {e}")
            raise
    
    def write_to_hdfs(self, df: DataFrame, output_path: str, checkpoint_path: str):
        """Write streaming data to HDFS with partitioning"""
        try:
            hdfs_config = self.config.get('hdfs', {})
            
            # Add partitioning columns
            partitioned_df = df \
                .withColumn("year", year(col("window_start"))) \
                .withColumn("month", month(col("window_start"))) \
                .withColumn("day", dayofmonth(col("window_start"))) \
                .withColumn("hour", hour(col("window_start")))
            
            # Write to HDFS with partitioning
            query = partitioned_df \
                .writeStream \
                .format("parquet") \
                .outputMode("append") \
                .option("path", output_path) \
                .option("checkpointLocation", checkpoint_path) \
                .partitionBy("year", "month", "day", "hour") \
                .trigger(processingTime='30 seconds') \
                .start()
            
            logger.info(f"✅ HDFS writing started to: {output_path}")
            logger.info(f"   Checkpoint: {checkpoint_path}")
            logger.info(f"   Partitioned by: year/month/day/hour")
            
            return query
            
        except Exception as e:
            logger.error(f"❌ Failed to write to HDFS: {e}")
            raise
    
    def write_to_console(self, df: DataFrame, query_name: str = "console"):
        """Write streaming data to console for debugging"""
        try:
            query = df \
                .writeStream \
                .outputMode("append") \
                .format("console") \
                .option("truncate", False) \
                .option("numRows", 20) \
                .queryName(query_name) \
                .trigger(processingTime='10 seconds') \
                .start()
            
            logger.info(f"✅ Console output started for query: {query_name}")
            return query
            
        except Exception as e:
            logger.error(f"❌ Failed to write to console: {e}")
            raise
    
    def run_streaming_pipeline(self):
        """Run the complete streaming pipeline"""
        try:
            logger.info("🚀 Starting METR-LA Streaming Pipeline")
            
            # Create Kafka stream
            kafka_stream = self.create_kafka_stream()
            
            # Parse traffic events
            traffic_events = self.parse_traffic_events(kafka_stream)
            
            # Create aggregations
            traffic_aggregates = self.create_traffic_aggregates(traffic_events)
            
            # HDFS output paths
            raw_events_path = "hdfs://namenode:9000/traffic-data/raw-events"
            aggregates_path = "hdfs://namenode:9000/traffic-data/aggregates"
            raw_checkpoint = "hdfs://namenode:9000/checkpoints/raw-events"
            agg_checkpoint = "hdfs://namenode:9000/checkpoints/aggregates"
            
            # Write raw events to HDFS
            raw_query = self.write_to_hdfs(
                traffic_events,
                raw_events_path,
                raw_checkpoint
            )
            
            # Write aggregates to HDFS
            agg_query = self.write_to_hdfs(
                traffic_aggregates,
                aggregates_path,
                agg_checkpoint
            )
            
            # Optional: Console output for monitoring
            if self.config.get('debug', False):
                console_query = self.write_to_console(traffic_aggregates, "traffic_aggregates")
            
            logger.info("✅ All streaming queries started successfully")
            logger.info("📊 Pipeline is processing traffic data...")
            logger.info("🛑 Press Ctrl+C to stop")
            
            # Wait for termination
            raw_query.awaitTermination()
            
        except KeyboardInterrupt:
            logger.info("🛑 Received interrupt signal, stopping streams...")
            self._stop_all_queries()
        except Exception as e:
            logger.error(f"❌ Pipeline failed: {e}", exc_info=True)
            raise
        finally:
            if self.spark:
                self.spark.stop()
    
    def _stop_all_queries(self):
        """Stop all active streaming queries"""
        try:
            for query in self.spark.streams.active:
                logger.info(f"Stopping query: {query.name}")
                query.stop()
            logger.info("✅ All queries stopped")
        except Exception as e:
            logger.error(f"Error stopping queries: {e}")

def create_default_config() -> Dict[str, Any]:
    """Create default configuration for the streaming pipeline"""
    return {
        'kafka': {
            'bootstrap_servers': 'kafka-broker1:9092',
            'topic': 'traffic-events'
        },
        'hdfs': {
            'namenode_url': 'hdfs://namenode:9000',
            'base_path': '/traffic-data'
        },
        'spark': {
            'app_name': 'METR-LA-Traffic-Streaming',
            'master': 'spark://spark-master:7077'
        },
        'debug': False
    }

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='METR-LA Spark Streaming Pipeline')
    parser.add_argument('--kafka-broker', default='kafka-broker1:9092', help='Kafka broker address')
    parser.add_argument('--kafka-topic', default='traffic-events', help='Kafka topic name')
    parser.add_argument('--debug', action='store_true', help='Enable debug console output')
    
    args = parser.parse_args()
    
    # Create configuration
    config = create_default_config()
    config['kafka']['bootstrap_servers'] = args.kafka_broker
    config['kafka']['topic'] = args.kafka_topic
    config['debug'] = args.debug
    
    try:
        # Create and run streaming pipeline
        pipeline = MetrLASparkStreaming(config)
        pipeline.run_streaming_pipeline()
        
    except KeyboardInterrupt:
        logger.info("Pipeline interrupted by user")
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
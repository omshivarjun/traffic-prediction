#!/usr/bin/env python3
"""
METR-LA Prediction Pipeline
Loads trained models and generates real-time traffic predictions

Features:
- Loads best trained model from HDFS
- Real-time prediction on streaming data
- Publishes predictions to Kafka predictions topic
- Stores predictions back to HDFS
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from pathlib import Path

# Add PySpark to path
spark_home = os.environ.get('SPARK_HOME', '/opt/bitnami/spark')
sys.path.append(os.path.join(spark_home, 'python'))
sys.path.append(os.path.join(spark_home, 'python', 'lib', 'py4j-0.10.9.7-src.zip'))

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import (
    col, from_json, to_timestamp, current_timestamp, 
    struct, to_json, when, isnan, isnull, desc,
    year, month, dayofmonth, hour
)
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, 
    IntegerType, TimestampType
)

from pyspark.ml import Pipeline, PipelineModel
from pyspark.ml.regression import LinearRegressionModel, RandomForestRegressionModel, GBTRegressionModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("metr_la_prediction")

class MetrLAPredictionPipeline:
    """Real-time traffic prediction pipeline"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize prediction pipeline"""
        self.config = config
        self.spark = None
        self.preprocessing_model = None
        self.prediction_model = None
        self.model_metadata = None
        self._setup_spark_session()
        self._load_models()
    
    def _setup_spark_session(self):
        """Create Spark session with streaming configuration"""
        try:
            self.spark = SparkSession.builder \
                .appName("METR-LA-Prediction-Pipeline") \
                .config("spark.master", "spark://spark-master:7077") \
                .config("spark.sql.adaptive.enabled", "true") \
                .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
                .config("spark.hadoop.fs.defaultFS", "hdfs://namenode:9000") \
                .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
                .config("spark.sql.streaming.checkpointLocation", "/tmp/prediction-checkpoints") \
                .config("spark.sql.streaming.forceDeleteTempCheckpointLocation", "true") \
                .config("spark.sql.execution.arrow.pyspark.enabled", "true") \
                .config("spark.jars.packages", 
                       "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,"
                       "org.apache.hadoop:hadoop-client:3.2.1") \
                .getOrCreate()
            
            # Set log level
            self.spark.sparkContext.setLogLevel("WARN")
            
            logger.info("✅ Spark prediction session created successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to create Spark session: {e}")
            raise
    
    def _load_models(self):
        """Load trained models from HDFS"""
        try:
            logger.info("📥 Loading trained models from HDFS...")
            
            # Load model metadata to find latest models
            metadata_path = "hdfs://namenode:9000/traffic-models/metadata"
            
            try:
                # Find latest metadata file
                metadata_files = self.spark.read.json(metadata_path).collect()
                if not metadata_files:
                    raise ValueError("No model metadata found")
                
                # Get latest metadata
                latest_metadata = max(metadata_files, key=lambda x: x['timestamp'])
                self.model_metadata = latest_metadata.asDict()
                
                logger.info(f"   Latest model timestamp: {self.model_metadata['timestamp']}")
                logger.info(f"   Best model: {self.model_metadata['best_model']}")
                
                # Load preprocessing model
                preprocessing_path = self.model_metadata['preprocessing_path']
                self.preprocessing_model = PipelineModel.load(preprocessing_path)
                logger.info(f"   Preprocessing model loaded: {preprocessing_path}")
                
                # Load best prediction model
                best_model_path = self.model_metadata['best_model_path']
                
                # Load based on model type
                best_model_type = self.model_metadata['best_model']
                if best_model_type == 'linear_regression':
                    self.prediction_model = LinearRegressionModel.load(best_model_path)
                elif best_model_type == 'random_forest':
                    self.prediction_model = RandomForestRegressionModel.load(best_model_path)
                elif best_model_type == 'gradient_boosted_trees':
                    self.prediction_model = GBTRegressionModel.load(best_model_path)
                else:
                    raise ValueError(f"Unknown model type: {best_model_type}")
                
                logger.info(f"   Prediction model loaded: {best_model_path}")
                logger.info("✅ All models loaded successfully")
                
            except Exception as e:
                logger.warning(f"Could not load models from HDFS: {e}")
                logger.info("Will run without pre-trained models (mock predictions)")
                
        except Exception as e:
            logger.error(f"❌ Failed to load models: {e}")
            # Continue without models for testing
            pass
    
    def get_traffic_aggregate_schema(self) -> StructType:
        """Define schema for aggregated traffic data"""
        return StructType([
            StructField("window_start", StringType(), True),
            StructField("window_end", StringType(), True),
            StructField("segment_id", StringType(), True),
            StructField("sensor_id", StringType(), True),
            StructField("road_type", StringType(), True),
            StructField("lane_count", IntegerType(), True),
            StructField("avg_speed_mph", DoubleType(), True),
            StructField("max_speed_mph", DoubleType(), True),
            StructField("min_speed_mph", DoubleType(), True),
            StructField("stddev_speed_mph", DoubleType(), True),
            StructField("median_speed_mph", DoubleType(), True),
            StructField("p85_speed_mph", DoubleType(), True),
            StructField("record_count", IntegerType(), True),
            StructField("aggregation_time", StringType(), True)
        ])
    
    def create_aggregates_stream(self) -> DataFrame:
        """Create streaming DataFrame from traffic aggregates topic"""
        try:
            kafka_config = self.config.get('kafka', {})
            
            stream_df = self.spark \
                .readStream \
                .format("kafka") \
                .option("kafka.bootstrap.servers", kafka_config.get('bootstrap_servers', 'kafka-broker1:9092')) \
                .option("subscribe", "traffic-aggregates") \
                .option("startingOffsets", "latest") \
                .option("failOnDataLoss", "false") \
                .option("maxOffsetsPerTrigger", 1000) \
                .load()
            
            logger.info("✅ Traffic aggregates stream created")
            return stream_df
            
        except Exception as e:
            logger.error(f"❌ Failed to create aggregates stream: {e}")
            raise
    
    def parse_aggregates(self, kafka_df: DataFrame) -> DataFrame:
        """Parse aggregated traffic data from Kafka"""
        try:
            aggregates_schema = self.get_traffic_aggregate_schema()
            
            # Parse JSON messages
            parsed_df = kafka_df \
                .select(
                    from_json(col("value").cast("string"), aggregates_schema).alias("data"),
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
                .withColumn("window_start_ts", to_timestamp(col("window_start"), "yyyy-MM-dd HH:mm:ss")) \
                .withColumn("prediction_time", current_timestamp()) \
                .filter(col("segment_id").isNotNull()) \
                .filter(col("avg_speed_mph").isNotNull())
            
            logger.info("✅ Aggregates parsing configured")
            return parsed_df
            
        except Exception as e:
            logger.error(f"❌ Failed to parse aggregates: {e}")
            raise
    
    def generate_predictions(self, aggregates_df: DataFrame) -> DataFrame:
        """Generate traffic predictions"""
        try:
            if self.preprocessing_model and self.prediction_model:
                # Use real trained models
                logger.info("🤖 Generating predictions with trained models...")
                
                # Apply preprocessing
                processed_df = self.preprocessing_model.transform(aggregates_df)
                
                # Generate predictions
                predictions_df = self.prediction_model.transform(processed_df)
                
                # Select prediction results
                result_df = predictions_df.select(
                    col("segment_id"),
                    col("sensor_id"),
                    col("window_start"),
                    col("window_end"),
                    col("avg_speed_mph").alias("current_speed"),
                    col("prediction").alias("predicted_speed_5min"),
                    col("road_type"),
                    col("lane_count"),
                    col("prediction_time")
                )
                
            else:
                # Mock predictions for testing
                logger.info("🔮 Generating mock predictions (no trained models available)...")
                
                result_df = aggregates_df.select(
                    col("segment_id"),
                    col("sensor_id"),
                    col("window_start"),
                    col("window_end"),
                    col("avg_speed_mph").alias("current_speed"),
                    # Simple mock prediction: slight trend continuation
                    (col("avg_speed_mph") * 0.95 + 
                     when(col("avg_speed_mph") > 50, -2.0).otherwise(1.0)).alias("predicted_speed_5min"),
                    col("road_type"),
                    col("lane_count"),
                    col("prediction_time")
                )
            
            # Add prediction metadata
            final_df = result_df \
                .withColumn("prediction_horizon_minutes", lit(5)) \
                .withColumn("model_type", lit(self.model_metadata.get('best_model', 'mock') if self.model_metadata else 'mock')) \
                .withColumn("prediction_id", 
                           concat(col("segment_id"), lit("_"), 
                                 date_format(col("prediction_time"), "yyyyMMddHHmmss"))) \
                .withColumn("confidence_score", lit(0.85))  # Mock confidence
            
            logger.info("✅ Predictions generated")
            return final_df
            
        except Exception as e:
            logger.error(f"❌ Failed to generate predictions: {e}")
            raise
    
    def publish_predictions_to_kafka(self, predictions_df: DataFrame):
        """Publish predictions to Kafka predictions topic"""
        try:
            kafka_config = self.config.get('kafka', {})
            
            # Convert predictions to JSON for Kafka
            kafka_df = predictions_df.select(
                col("segment_id").alias("key"),
                to_json(struct(
                    col("segment_id"),
                    col("sensor_id"),
                    col("window_start"),
                    col("window_end"),
                    col("current_speed"),
                    col("predicted_speed_5min"),
                    col("road_type"),
                    col("lane_count"),
                    col("prediction_time"),
                    col("prediction_horizon_minutes"),
                    col("model_type"),
                    col("prediction_id"),
                    col("confidence_score")
                )).alias("value")
            )
            
            # Write to Kafka predictions topic
            query = kafka_df.writeStream \
                .format("kafka") \
                .option("kafka.bootstrap.servers", kafka_config.get('bootstrap_servers', 'kafka-broker1:9092')) \
                .option("topic", "traffic-predictions") \
                .option("checkpointLocation", "hdfs://namenode:9000/checkpoints/predictions-kafka") \
                .outputMode("append") \
                .trigger(processingTime='10 seconds') \
                .start()
            
            logger.info("✅ Predictions publishing to Kafka started")
            return query
            
        except Exception as e:
            logger.error(f"❌ Failed to publish predictions to Kafka: {e}")
            raise
    
    def save_predictions_to_hdfs(self, predictions_df: DataFrame):
        """Save predictions to HDFS"""
        try:
            # Add partitioning columns
            partitioned_df = predictions_df \
                .withColumn("year", year(col("prediction_time"))) \
                .withColumn("month", month(col("prediction_time"))) \
                .withColumn("day", dayofmonth(col("prediction_time"))) \
                .withColumn("hour", hour(col("prediction_time")))
            
            # Write to HDFS with partitioning
            query = partitioned_df \
                .writeStream \
                .format("parquet") \
                .outputMode("append") \
                .option("path", "hdfs://namenode:9000/traffic-predictions") \
                .option("checkpointLocation", "hdfs://namenode:9000/checkpoints/predictions-hdfs") \
                .partitionBy("year", "month", "day", "hour") \
                .trigger(processingTime='30 seconds') \
                .start()
            
            logger.info("✅ Predictions saving to HDFS started")
            return query
            
        except Exception as e:
            logger.error(f"❌ Failed to save predictions to HDFS: {e}")
            raise
    
    def run_prediction_pipeline(self):
        """Run the complete prediction pipeline"""
        try:
            logger.info("🚀 Starting METR-LA Prediction Pipeline")
            
            # Create aggregates stream
            aggregates_stream = self.create_aggregates_stream()
            
            # Parse aggregates
            parsed_aggregates = self.parse_aggregates(aggregates_stream)
            
            # Generate predictions
            predictions = self.generate_predictions(parsed_aggregates)
            
            # Publish to Kafka
            kafka_query = self.publish_predictions_to_kafka(predictions)
            
            # Save to HDFS
            hdfs_query = self.save_predictions_to_hdfs(predictions)
            
            # Optional: Console output for monitoring
            if self.config.get('debug', False):
                console_query = predictions.writeStream \
                    .outputMode("append") \
                    .format("console") \
                    .option("truncate", False) \
                    .option("numRows", 10) \
                    .trigger(processingTime='15 seconds') \
                    .start()
            
            logger.info("✅ All prediction streams started successfully")
            logger.info("🔮 Pipeline is generating traffic predictions...")
            logger.info("🛑 Press Ctrl+C to stop")
            
            # Wait for termination
            kafka_query.awaitTermination()
            
        except KeyboardInterrupt:
            logger.info("🛑 Received interrupt signal, stopping streams...")
            self._stop_all_queries()
        except Exception as e:
            logger.error(f"❌ Prediction pipeline failed: {e}", exc_info=True)
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

# Add missing imports
from pyspark.sql.functions import lit, concat, date_format

def create_default_config() -> Dict[str, Any]:
    """Create default configuration for prediction pipeline"""
    return {
        'kafka': {
            'bootstrap_servers': 'kafka-broker1:9092',
            'aggregates_topic': 'traffic-aggregates',
            'predictions_topic': 'traffic-predictions'
        },
        'hdfs': {
            'namenode_url': 'hdfs://namenode:9000',
            'models_path': '/traffic-models',
            'predictions_path': '/traffic-predictions'
        },
        'spark': {
            'app_name': 'METR-LA-Prediction-Pipeline',
            'master': 'spark://spark-master:7077'
        },
        'debug': False
    }

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='METR-LA Prediction Pipeline')
    parser.add_argument('--kafka-broker', default='kafka-broker1:9092', help='Kafka broker address')
    parser.add_argument('--debug', action='store_true', help='Enable debug console output')
    
    args = parser.parse_args()
    
    # Create configuration
    config = create_default_config()
    config['kafka']['bootstrap_servers'] = args.kafka_broker
    config['debug'] = args.debug
    
    try:
        # Create and run prediction pipeline
        pipeline = MetrLAPredictionPipeline(config)
        pipeline.run_prediction_pipeline()
        
    except KeyboardInterrupt:
        logger.info("Pipeline interrupted by user")
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
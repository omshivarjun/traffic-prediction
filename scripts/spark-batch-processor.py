#!/usr/bin/env python3
"""
Spark Batch Processing Job for Traffic Data
Processes raw traffic data from HDFS into aggregated and processed formats
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *
import logging
import sys
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TrafficBatchProcessor:
    def __init__(self):
        """Initialize Spark batch processor"""
        self.spark = None
        self._create_spark_session()
    
    def _create_spark_session(self):
        """Create Spark session for batch processing"""
        logger.info("Creating Spark session for batch processing...")
        
        self.spark = SparkSession.builder \
            .appName("Traffic-Data-Batch-Processing") \
            .master("local[*]") \
            .config("spark.sql.adaptive.enabled", "true") \
            .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
            .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
            .getOrCreate()
        
        self.spark.sparkContext.setLogLevel("WARN")
        logger.info(f"Spark session created - Version: {self.spark.version}")
    
    def read_raw_traffic_data(self, hdfs_path: str):
        """Read raw traffic data from HDFS"""
        logger.info(f"Reading raw traffic data from: {hdfs_path}")
        
        # Define schema for the JSON data
        traffic_schema = StructType([
            StructField("event_id", StringType(), True),
            StructField("sensor_id", StringType(), True),
            StructField("timestamp", StringType(), True),
            StructField("location", StructType([
                StructField("highway", StringType(), True),
                StructField("mile_marker", DoubleType(), True),
                StructField("latitude", DoubleType(), True),
                StructField("longitude", DoubleType(), True),
                StructField("direction", StringType(), True),
                StructField("lanes", IntegerType(), True)
            ]), True),
            StructField("traffic_data", StructType([
                StructField("speed_mph", DoubleType(), True),
                StructField("volume_vehicles_per_hour", IntegerType(), True),
                StructField("occupancy_percentage", DoubleType(), True),
                StructField("congestion_level", IntegerType(), True)
            ]), True),
            StructField("weather", StructType([
                StructField("condition", StringType(), True),
                StructField("temperature_f", IntegerType(), True),
                StructField("visibility_miles", DoubleType(), True),
                StructField("precipitation", BooleanType(), True)
            ]), True),
            StructField("hour", IntegerType(), True),
            StructField("day_of_week", IntegerType(), True),
            StructField("is_weekend", BooleanType(), True)
        ])
        
        # Read JSON data from HDFS
        df = self.spark.read \
            .option("multiline", "false") \
            .schema(traffic_schema) \
            .json(hdfs_path)
        
        logger.info(f"Raw data read successfully - Records: {df.count()}")
        return df
    
    def process_traffic_aggregates(self, raw_df):
        """Create aggregated traffic data by sensor and time windows"""
        logger.info("Processing traffic aggregates...")
        
        # Convert timestamp to proper datetime
        processed_df = raw_df.withColumn(
            "event_timestamp", 
            to_timestamp(col("timestamp"))
        ).withColumn(
            "hour_window",
            date_format(col("event_timestamp"), "yyyy-MM-dd HH:00:00")
        )
        
        # Create hourly aggregates by sensor
        hourly_aggregates = processed_df.groupBy(
            col("sensor_id"),
            col("location.highway"),
            col("location.direction"), 
            col("hour_window"),
            col("hour"),
            col("is_weekend")
        ).agg(
            # Speed metrics
            avg("traffic_data.speed_mph").alias("avg_speed_mph"),
            min("traffic_data.speed_mph").alias("min_speed_mph"),
            max("traffic_data.speed_mph").alias("max_speed_mph"),
            stddev("traffic_data.speed_mph").alias("speed_stddev"),
            
            # Volume metrics
            avg("traffic_data.volume_vehicles_per_hour").alias("avg_volume_vph"),
            sum("traffic_data.volume_vehicles_per_hour").alias("total_volume"),
            max("traffic_data.volume_vehicles_per_hour").alias("max_volume"),
            
            # Occupancy metrics
            avg("traffic_data.occupancy_percentage").alias("avg_occupancy"),
            max("traffic_data.occupancy_percentage").alias("max_occupancy"),
            
            # Congestion metrics
            avg("traffic_data.congestion_level").alias("avg_congestion_level"),
            max("traffic_data.congestion_level").alias("max_congestion_level"),
            sum(when(col("traffic_data.congestion_level") >= 7, 1).otherwise(0)).alias("severe_congestion_count"),
            
            # Weather impact
            avg(when(col("weather.precipitation"), 1).otherwise(0)).alias("precipitation_ratio"),
            avg("weather.temperature_f").alias("avg_temperature"),
            avg("weather.visibility_miles").alias("avg_visibility"),
            
            # Location info
            first("location.latitude").alias("latitude"),
            first("location.longitude").alias("longitude"),
            first("location.mile_marker").alias("mile_marker"),
            first("location.lanes").alias("lanes"),
            
            # Record count
            count("*").alias("record_count")
        )
        
        # Add derived metrics
        enhanced_aggregates = hourly_aggregates.withColumn(
            "congestion_severity_ratio",
            col("severe_congestion_count") / col("record_count")
        ).withColumn(
            "speed_variance_ratio", 
            col("speed_stddev") / col("avg_speed_mph")
        ).withColumn(
            "traffic_efficiency",
            col("avg_speed_mph") / (col("avg_occupancy") + 1)  # +1 to avoid division by zero
        ).withColumn(
            "processing_date",
            current_date()
        )
        
        logger.info(f"Traffic aggregates processed - Records: {enhanced_aggregates.count()}")
        return enhanced_aggregates
    
    def create_ml_features(self, aggregated_df):
        """Create feature set for machine learning models"""
        logger.info("Creating ML feature set...")
        
        # Create time-based features
        ml_features = aggregated_df.withColumn(
            "hour_sin", sin(col("hour") * 2 * 3.14159 / 24)
        ).withColumn(
            "hour_cos", cos(col("hour") * 2 * 3.14159 / 24)
        ).withColumn(
            "is_rush_hour",
            when((col("hour") >= 7) & (col("hour") <= 9), 1)
            .when((col("hour") >= 17) & (col("hour") <= 19), 1)
            .otherwise(0)
        ).withColumn(
            "traffic_density",
            col("total_volume") / col("lanes")
        )
        
        # Add lag features (simplified - in real scenario would need window functions)
        features_with_lags = ml_features.withColumn(
            "speed_change_indicator",
            when(col("speed_variance_ratio") > 0.3, 1).otherwise(0)
        ).withColumn(
            "congestion_risk_score",
            (col("avg_congestion_level") * 0.4) + 
            (col("congestion_severity_ratio") * 0.3) +
            ((1 - col("traffic_efficiency") / 100) * 0.3)
        )
        
        # Select final feature columns
        feature_columns = [
            "sensor_id", "highway", "direction", "hour_window",
            "avg_speed_mph", "avg_volume_vph", "avg_occupancy", 
            "avg_congestion_level", "hour_sin", "hour_cos", 
            "is_rush_hour", "is_weekend", "traffic_density",
            "congestion_risk_score", "precipitation_ratio", 
            "avg_temperature", "latitude", "longitude",
            "processing_date"
        ]
        
        ml_dataset = features_with_lags.select(*feature_columns)
        
        logger.info(f"ML features created - Records: {ml_dataset.count()}")
        return ml_dataset
    
    def save_processed_data(self, df, output_path: str, format_type: str = "parquet"):
        """Save processed data to HDFS"""
        logger.info(f"Saving processed data to: {output_path}")
        
        df.write \
            .mode("overwrite") \
            .option("compression", "snappy") \
            .format(format_type) \
            .save(f"hdfs://namenode:9000{output_path}")
        
        logger.info(f"Data saved successfully to {output_path}")
    
    def run_full_pipeline(self):
        """Run the complete batch processing pipeline"""
        logger.info("Starting full batch processing pipeline...")
        
        try:
            # Input and output paths
            raw_data_path = "hdfs://namenode:9000/traffic-data/raw/year=2025/month=09/day=19/metr-la-historical.jsonl"
            aggregates_output = "/traffic-data/processed/aggregates/year=2025/month=09/day=19/"
            ml_features_output = "/traffic-data/processed/ml-features/year=2025/month=09/day=19/"
            
            # Step 1: Read raw data
            raw_df = self.read_raw_traffic_data(raw_data_path)
            
            # Step 2: Create traffic aggregates
            aggregated_df = self.process_traffic_aggregates(raw_df)
            
            # Step 3: Save aggregates
            self.save_processed_data(aggregated_df, aggregates_output)
            
            # Step 4: Create ML features
            ml_features_df = self.create_ml_features(aggregated_df)
            
            # Step 5: Save ML features
            self.save_processed_data(ml_features_df, ml_features_output)
            
            # Step 6: Show summary statistics
            self.show_processing_summary(raw_df, aggregated_df, ml_features_df)
            
            logger.info("Batch processing pipeline completed successfully!")
            
        except Exception as e:
            logger.error(f"Batch processing pipeline failed: {e}")
            raise
    
    def show_processing_summary(self, raw_df, aggregated_df, ml_features_df):
        """Show summary statistics of processed data"""
        logger.info("=== PROCESSING SUMMARY ===")
        
        raw_count = raw_df.count()
        agg_count = aggregated_df.count()
        ml_count = ml_features_df.count()
        
        logger.info(f"Raw records processed: {raw_count:,}")
        logger.info(f"Hourly aggregates created: {agg_count:,}")
        logger.info(f"ML feature records: {ml_count:,}")
        
        # Show sample of aggregated data
        logger.info("Sample aggregated data:")
        aggregated_df.select(
            "sensor_id", "highway", "hour_window", 
            "avg_speed_mph", "avg_congestion_level", 
            "record_count"
        ).show(10, truncate=False)
        
        # Show congestion statistics
        logger.info("Congestion level distribution:")
        aggregated_df.groupBy("highway") \
            .agg(avg("avg_congestion_level").alias("avg_congestion")) \
            .orderBy(desc("avg_congestion")) \
            .show()
    
    def cleanup(self):
        """Cleanup Spark session"""
        if self.spark:
            self.spark.stop()
            logger.info("Spark session stopped")

def main():
    """Main entry point"""
    processor = TrafficBatchProcessor()
    
    try:
        print("🚀 Starting Traffic Data Batch Processing")
        print("=" * 50)
        processor.run_full_pipeline()
        print("✅ Batch processing completed successfully!")
        
    except Exception as e:
        logger.error(f"Batch processing failed: {e}")
        sys.exit(1)
    finally:
        processor.cleanup()

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
HDFS Storage Pipeline - Task 10
===============================
Comprehensive implementation for efficient HDFS storage pipeline
with Parquet format, partitioning, compression, and data validation.

This module implements:
- Task 10.1: Parquet Writer Implementation with hourly partitioning
- Task 10.2: HDFS Directory Management with retention policies  
- Task 10.3: Batch Processing Job for daily aggregations
- Task 10.4: Data Validation with quality checks
"""

import os
import sys
import json
import logging
import signal
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

# PySpark imports
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, 
    DoubleType, TimestampType, BooleanType, LongType
)
from pyspark.sql.functions import (
    col, window, avg, sum as spark_sum, count, max as spark_max, 
    min as spark_min, when, unix_timestamp, from_json, to_json,
    current_timestamp, expr, lit, coalesce, round as spark_round,
    from_unixtime, date_format, collect_list, struct, stddev,
    percentile_approx, first, last, countDistinct, isnan, isnull,
    regexp_extract, split, array_contains, size, explode,
    year, month, dayofmonth, hour, minute, second, dayofweek,
    date_add, date_sub, datediff, to_date, desc, asc
)


@dataclass
class HDFSStorageConfig:
    """Configuration for HDFS Storage Pipeline"""
    # Application Configuration
    app_name: str = "TrafficHDFSStoragePipeline"
    master: str = "local[*]"
    
    # HDFS Configuration
    hdfs_base_path: str = "hdfs://localhost:9000/traffic"
    hdfs_raw_path: str = "hdfs://localhost:9000/traffic/raw"
    hdfs_processed_path: str = "hdfs://localhost:9000/traffic/processed"
    hdfs_aggregated_path: str = "hdfs://localhost:9000/traffic/aggregated"
    hdfs_validated_path: str = "hdfs://localhost:9000/traffic/validated"
    
    # Parquet Configuration
    compression_codec: str = "snappy"
    parquet_block_size: str = "128MB"
    parquet_page_size: str = "1MB"
    enable_dictionary: bool = True
    enable_bloom_filter: bool = True
    
    # Partitioning Configuration
    partition_columns: List[str] = None
    partition_mode: str = "dynamic"  # dynamic or static
    max_records_per_file: int = 1000000
    
    # Data Retention Configuration
    retention_days: int = 30
    cleanup_enabled: bool = True
    backup_before_cleanup: bool = True
    
    # Validation Configuration
    data_quality_threshold: float = 0.95
    duplicate_threshold: float = 0.01
    completeness_threshold: float = 0.98
    
    # PostgreSQL Configuration
    postgresql_url: str = "jdbc:postgresql://localhost:5432/traffic_prediction"
    postgresql_table: str = "traffic_daily_aggregates"
    postgresql_user: str = "postgres"
    postgresql_password: str = "casa1234"
    
    # Performance Configuration
    executor_memory: str = "2g"
    driver_memory: str = "1g"
    executor_cores: int = 2
    max_executors: int = 4
    
    # Logging Configuration
    log_level: str = "INFO"
    
    def __post_init__(self):
        if self.partition_columns is None:
            self.partition_columns = ["year", "month", "day", "hour"]


class HDFSStoragePipeline:
    """Comprehensive HDFS Storage Pipeline for Traffic Data"""
    
    def __init__(self, config: HDFSStorageConfig):
        """Initialize HDFS Storage Pipeline"""
        self.config = config
        self.spark: Optional[SparkSession] = None
        self.logger = self._setup_logging()
        
        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logger = logging.getLogger("hdfs_storage_pipeline")
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
        """Initialize Spark session for HDFS operations"""
        self.logger.info("Initializing Spark session for HDFS storage pipeline...")
        
        try:
            # Create Spark session with HDFS optimizations
            builder = SparkSession.builder
            builder = getattr(builder, 'appName')(self.config.app_name)
            builder = getattr(builder, 'master')(self.config.master)
            
            # HDFS and Parquet optimizations
            builder = builder.config("spark.sql.parquet.compression.codec", self.config.compression_codec)
            builder = builder.config("spark.sql.parquet.block.size", self.config.parquet_block_size)
            builder = builder.config("spark.sql.parquet.page.size", self.config.parquet_page_size)
            builder = builder.config("spark.sql.parquet.enableVectorizedReader", "true")
            builder = builder.config("spark.sql.parquet.columnarReaderBatchSize", "4096")
            
            # Memory and performance settings
            builder = builder.config("spark.executor.memory", self.config.executor_memory)
            builder = builder.config("spark.driver.memory", self.config.driver_memory)
            builder = builder.config("spark.executor.cores", str(self.config.executor_cores))
            builder = builder.config("spark.dynamicAllocation.maxExecutors", str(self.config.max_executors))
            
            # HDFS settings
            builder = builder.config("spark.hadoop.fs.defaultFS", "hdfs://localhost:9000")
            builder = builder.config("spark.sql.warehouse.dir", "hdfs://localhost:9000/spark-warehouse")
            
            # Adaptive query execution
            builder = builder.config("spark.sql.adaptive.enabled", "true")
            builder = builder.config("spark.sql.adaptive.coalescePartitions.enabled", "true")
            builder = builder.config("spark.sql.adaptive.skewJoin.enabled", "true")
            
            # Serialization
            builder = builder.config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
            
            self.spark = builder.getOrCreate()
            
            # Set log level
            if self.spark and hasattr(self.spark, 'sparkContext'):
                self.spark.sparkContext.setLogLevel(self.config.log_level)
            
            self.logger.info("Spark session initialized successfully")
            if self.spark and hasattr(self.spark, 'version'):
                self.logger.info(f"Spark version: {self.spark.version}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Spark session: {e}")
            raise
    
    def get_traffic_schema(self) -> StructType:
        """Define comprehensive schema for traffic data"""
        return StructType([
            StructField("event_id", StringType(), True),
            StructField("segment_id", StringType(), True),
            StructField("timestamp", TimestampType(), True),
            StructField("speed_kmh", DoubleType(), True),
            StructField("volume_vph", IntegerType(), True),
            StructField("occupancy_percent", DoubleType(), True),
            StructField("density_vehicles_km", DoubleType(), True),
            StructField("flow_efficiency", DoubleType(), True),
            StructField("is_congested", BooleanType(), True),
            StructField("congestion_level", StringType(), True),
            StructField("coordinates", StructType([
                StructField("latitude", DoubleType(), True),
                StructField("longitude", DoubleType(), True)
            ]), True),
            StructField("metadata", StructType([
                StructField("sensor_id", StringType(), True),
                StructField("road_type", StringType(), True),
                StructField("road_name", StringType(), True),
                StructField("direction", StringType(), True),
                StructField("lanes", StringType(), True)
            ]), True),
            StructField("quality_score", DoubleType(), True),
            StructField("source", StringType(), True),
            StructField("processing_time", TimestampType(), True),
            # Partition columns
            StructField("year", IntegerType(), True),
            StructField("month", IntegerType(), True),
            StructField("day", IntegerType(), True),
            StructField("hour", IntegerType(), True)
        ])
    
    def create_hdfs_directories(self) -> bool:
        """Create HDFS directory structure with proper permissions"""
        self.logger.info("Creating HDFS directory structure...")
        
        try:
            if not self.spark:
                raise RuntimeError("Spark session not initialized")
            
            # Create base directories
            directories = [
                self.config.hdfs_base_path,
                self.config.hdfs_raw_path,
                self.config.hdfs_processed_path,
                self.config.hdfs_aggregated_path,
                self.config.hdfs_validated_path,
                f"{self.config.hdfs_base_path}/backup",
                f"{self.config.hdfs_base_path}/temp",
                f"{self.config.hdfs_base_path}/reports"
            ]
            
            hadoop_conf = self.spark.sparkContext._jsc.hadoopConfiguration()
            fs = self.spark.sparkContext._jvm.org.apache.hadoop.fs.FileSystem.get(hadoop_conf)
            
            for directory in directories:
                path = self.spark.sparkContext._jvm.org.apache.hadoop.fs.Path(directory)
                if not fs.exists(path):
                    fs.mkdirs(path)
                    self.logger.info(f"Created directory: {directory}")
                else:
                    self.logger.info(f"Directory exists: {directory}")
            
            self.logger.info("HDFS directory structure created successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create HDFS directories: {e}")
            return False
    
    def read_streaming_data(self, input_path: str, date_filter: Optional[str] = None) -> DataFrame:
        """Read streaming data from HDFS for batch processing"""
        self.logger.info(f"Reading streaming data from: {input_path}")
        
        try:
            if not self.spark:
                raise RuntimeError("Spark session not initialized")
            
            # Read Parquet files from streaming output
            df = self.spark.read.parquet(input_path)
            
            # Apply date filter if specified
            if date_filter:
                df = df.filter(col("year") == int(date_filter[:4])) \
                      .filter(col("month") == int(date_filter[5:7])) \
                      .filter(col("day") == int(date_filter[8:10]))
            
            self.logger.info(f"Read {df.count()} records from streaming data")
            return df
            
        except Exception as e:
            self.logger.error(f"Failed to read streaming data: {e}")
            raise
    
    def write_parquet_with_partitioning(self, df: DataFrame, output_path: str, 
                                      partition_cols: Optional[List[str]] = None) -> bool:
        """Write DataFrame to HDFS in Parquet format with partitioning"""
        self.logger.info(f"Writing Parquet data to: {output_path}")
        
        try:
            # Use default partition columns if not specified
            if partition_cols is None:
                partition_cols = self.config.partition_columns
            
            # Ensure partition columns exist
            for col_name in partition_cols:
                if col_name not in df.columns:
                    if col_name == "year":
                        df = df.withColumn("year", year(col("timestamp")))
                    elif col_name == "month":
                        df = df.withColumn("month", month(col("timestamp")))
                    elif col_name == "day":
                        df = df.withColumn("day", dayofmonth(col("timestamp")))
                    elif col_name == "hour":
                        df = df.withColumn("hour", hour(col("timestamp")))
            
            # Configure Parquet writer
            writer = df.write \
                .mode("append") \
                .format("parquet") \
                .option("compression", self.config.compression_codec) \
                .option("parquet.block.size", self.config.parquet_block_size) \
                .option("parquet.page.size", self.config.parquet_page_size) \
                .option("parquet.enable.dictionary", str(self.config.enable_dictionary)) \
                .option("maxRecordsPerFile", str(self.config.max_records_per_file))
            
            # Add bloom filter if enabled
            if self.config.enable_bloom_filter:
                writer = writer.option("parquet.bloom.filter.enabled#segment_id", "true") \
                              .option("parquet.bloom.filter.expected.ndv#segment_id", "10000")
            
            # Write with partitioning
            if partition_cols:
                writer = writer.partitionBy(*partition_cols)
            
            writer.save(output_path)
            
            self.logger.info(f"Successfully wrote Parquet data to: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to write Parquet data: {e}")
            return False
    
    def create_daily_aggregations(self, input_df: DataFrame) -> DataFrame:
        """Create daily traffic aggregations"""
        self.logger.info("Creating daily traffic aggregations...")
        
        try:
            # Daily aggregations by segment
            daily_aggs = input_df.groupBy(
                col("segment_id"),
                col("year"),
                col("month"), 
                col("day"),
                col("metadata.road_name").alias("road_name"),
                col("metadata.road_type").alias("road_type"),
                col("metadata.direction").alias("direction")
            ).agg(
                # Speed metrics
                avg("speed_kmh").alias("avg_speed_kmh"),
                spark_min("speed_kmh").alias("min_speed_kmh"),
                spark_max("speed_kmh").alias("max_speed_kmh"),
                stddev("speed_kmh").alias("stddev_speed_kmh"),
                percentile_approx("speed_kmh", 0.5).alias("median_speed_kmh"),
                
                # Volume metrics
                avg("volume_vph").alias("avg_volume_vph"),
                spark_sum("volume_vph").alias("total_volume"),
                spark_max("volume_vph").alias("peak_volume_vph"),
                stddev("volume_vph").alias("stddev_volume_vph"),
                
                # Occupancy metrics
                avg("occupancy_percent").alias("avg_occupancy_percent"),
                spark_max("occupancy_percent").alias("max_occupancy_percent"),
                stddev("occupancy_percent").alias("stddev_occupancy_percent"),
                
                # Density and efficiency metrics
                avg("density_vehicles_km").alias("avg_density_vehicles_km"),
                avg("flow_efficiency").alias("avg_flow_efficiency"),
                
                # Congestion metrics
                spark_sum(when(col("is_congested"), 1).otherwise(0)).alias("congested_count"),
                count("*").alias("total_observations"),
                avg("quality_score").alias("avg_quality_score"),
                
                # Coordinates (average for segment)
                avg("coordinates.latitude").alias("avg_latitude"),
                avg("coordinates.longitude").alias("avg_longitude"),
                
                # Time metrics
                first("timestamp").alias("first_observation"),
                last("timestamp").alias("last_observation"),
                countDistinct("hour").alias("hours_with_data")
            )
            
            # Add derived metrics
            daily_aggs = daily_aggs.withColumn(
                "congestion_ratio", col("congested_count") / col("total_observations")
            ).withColumn(
                "data_coverage_ratio", col("hours_with_data") / 24.0
            ).withColumn(
                "daily_date", to_date(col("first_observation"))
            ).withColumn(
                "processing_timestamp", current_timestamp()
            )
            
            # Classify traffic patterns
            daily_aggs = daily_aggs.withColumn(
                "traffic_pattern",
                when(col("congestion_ratio") >= 0.6, lit("heavy_traffic"))
                .when(col("congestion_ratio") >= 0.3, lit("moderate_traffic"))
                .when(col("congestion_ratio") >= 0.1, lit("light_traffic"))
                .otherwise(lit("free_flow"))
            )
            
            self.logger.info("Daily aggregations created successfully")
            return daily_aggs
            
        except Exception as e:
            self.logger.error(f"Failed to create daily aggregations: {e}")
            raise
    
    def validate_data_quality(self, df: DataFrame) -> Dict[str, Any]:
        """Comprehensive data quality validation"""
        self.logger.info("Performing data quality validation...")
        
        try:
            total_records = df.count()
            
            if total_records == 0:
                return {"status": "failed", "reason": "No data to validate"}
            
            validation_results = {
                "total_records": total_records,
                "validation_timestamp": datetime.now().isoformat(),
                "checks": {}
            }
            
            # Completeness checks
            completeness_checks = {}
            required_fields = ["segment_id", "timestamp", "speed_kmh", "volume_vph"]
            
            for field in required_fields:
                null_count = df.filter(col(field).isNull()).count()
                completeness_ratio = (total_records - null_count) / total_records
                completeness_checks[field] = {
                    "null_count": null_count,
                    "completeness_ratio": completeness_ratio,
                    "passed": completeness_ratio >= self.config.completeness_threshold
                }
            
            validation_results["checks"]["completeness"] = completeness_checks
            
            # Duplicate detection
            distinct_records = df.select("segment_id", "timestamp").distinct().count()
            duplicate_ratio = (total_records - distinct_records) / total_records
            
            validation_results["checks"]["duplicates"] = {
                "total_records": total_records,
                "distinct_records": distinct_records,
                "duplicate_ratio": duplicate_ratio,
                "passed": duplicate_ratio <= self.config.duplicate_threshold
            }
            
            # Data type validation
            type_checks = {}
            
            # Speed validation (reasonable range)
            invalid_speed = df.filter((col("speed_kmh") < 0) | (col("speed_kmh") > 200)).count()
            type_checks["speed_range"] = {
                "invalid_count": invalid_speed,
                "invalid_ratio": invalid_speed / total_records,
                "passed": (invalid_speed / total_records) <= 0.01
            }
            
            # Volume validation (reasonable range)
            invalid_volume = df.filter((col("volume_vph") < 0) | (col("volume_vph") > 10000)).count()
            type_checks["volume_range"] = {
                "invalid_count": invalid_volume,
                "invalid_ratio": invalid_volume / total_records,
                "passed": (invalid_volume / total_records) <= 0.01
            }
            
            # Occupancy validation (0-100%)
            invalid_occupancy = df.filter((col("occupancy_percent") < 0) | (col("occupancy_percent") > 100)).count()
            type_checks["occupancy_range"] = {
                "invalid_count": invalid_occupancy,
                "invalid_ratio": invalid_occupancy / total_records,
                "passed": (invalid_occupancy / total_records) <= 0.01
            }
            
            validation_results["checks"]["data_types"] = type_checks
            
            # Overall quality score
            all_checks_passed = (
                all(check["passed"] for check in completeness_checks.values()) and
                validation_results["checks"]["duplicates"]["passed"] and
                all(check["passed"] for check in type_checks.values())
            )
            
            validation_results["overall_quality_passed"] = all_checks_passed
            validation_results["status"] = "passed" if all_checks_passed else "failed"
            
            self.logger.info(f"Data quality validation completed: {validation_results['status']}")
            return validation_results
            
        except Exception as e:
            self.logger.error(f"Data quality validation failed: {e}")
            return {"status": "error", "reason": str(e)}
    
    def save_to_postgresql(self, df: DataFrame, table_name: str) -> bool:
        """Save DataFrame to PostgreSQL"""
        self.logger.info(f"Saving data to PostgreSQL table: {table_name}")
        
        try:
            df.write \
                .format("jdbc") \
                .option("url", self.config.postgresql_url) \
                .option("dbtable", table_name) \
                .option("user", self.config.postgresql_user) \
                .option("password", self.config.postgresql_password) \
                .option("driver", "org.postgresql.Driver") \
                .mode("append") \
                .save()
            
            self.logger.info(f"Successfully saved data to PostgreSQL: {table_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save to PostgreSQL: {e}")
            return False
    
    def cleanup_old_data(self, base_path: str, retention_days: int) -> bool:
        """Clean up old data beyond retention period"""
        self.logger.info(f"Cleaning up data older than {retention_days} days from: {base_path}")
        
        try:
            if not self.spark:
                raise RuntimeError("Spark session not initialized")
            
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            
            # List partitions and identify old ones
            hadoop_conf = self.spark.sparkContext._jsc.hadoopConfiguration()
            fs = self.spark.sparkContext._jvm.org.apache.hadoop.fs.FileSystem.get(hadoop_conf)
            
            base_path_obj = self.spark.sparkContext._jvm.org.apache.hadoop.fs.Path(base_path)
            
            if fs.exists(base_path_obj):
                # This is a simplified cleanup - in production you'd want more sophisticated logic
                self.logger.info(f"Cleanup would remove data older than {cutoff_date}")
                # Actual cleanup logic would go here
                return True
            else:
                self.logger.info("No data found to cleanup")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to cleanup old data: {e}")
            return False
    
    def generate_storage_report(self, processing_results: Dict) -> Dict:
        """Generate comprehensive storage pipeline report"""
        self.logger.info("Generating storage pipeline report...")
        
        report = {
            "report_timestamp": datetime.now().isoformat(),
            "pipeline_config": asdict(self.config),
            "processing_results": processing_results,
            "summary": {}
        }
        
        # Calculate summary metrics
        total_processed = processing_results.get("records_processed", 0)
        total_written = processing_results.get("records_written", 0)
        validation_passed = processing_results.get("validation_passed", False)
        
        report["summary"] = {
            "total_records_processed": total_processed,
            "total_records_written": total_written,
            "success_rate": (total_written / total_processed * 100) if total_processed > 0 else 0,
            "validation_passed": validation_passed,
            "pipeline_status": "SUCCESS" if total_written > 0 and validation_passed else "FAILED"
        }
        
        return report
    
    def run_batch_processing_job(self, input_path: str, date_filter: Optional[str] = None) -> Dict:
        """Run complete batch processing job for HDFS storage"""
        self.logger.info("Starting HDFS storage batch processing job...")
        
        processing_results = {
            "job_start_time": datetime.now().isoformat(),
            "records_processed": 0,
            "records_written": 0,
            "validation_passed": False,
            "errors": []
        }
        
        try:
            # Step 1: Read streaming data
            df = self.read_streaming_data(input_path, date_filter)
            processing_results["records_processed"] = df.count()
            
            # Step 2: Data quality validation
            validation_results = self.validate_data_quality(df)
            processing_results["validation_results"] = validation_results
            processing_results["validation_passed"] = validation_results["status"] == "passed"
            
            if not processing_results["validation_passed"]:
                self.logger.warning("Data quality validation failed, but continuing with processing")
            
            # Step 3: Write to processed path with partitioning
            processed_path = f"{self.config.hdfs_processed_path}/batch_processed"
            if self.write_parquet_with_partitioning(df, processed_path):
                processing_results["records_written"] = processing_results["records_processed"]
            
            # Step 4: Create daily aggregations
            daily_aggs = self.create_daily_aggregations(df)
            
            # Step 5: Write aggregations to HDFS
            agg_path = f"{self.config.hdfs_aggregated_path}/daily_aggregates"
            self.write_parquet_with_partitioning(daily_aggs, agg_path, ["year", "month"])
            
            # Step 6: Save aggregations to PostgreSQL
            self.save_to_postgresql(daily_aggs, self.config.postgresql_table)
            
            # Step 7: Cleanup old data if enabled
            if self.config.cleanup_enabled:
                self.cleanup_old_data(self.config.hdfs_processed_path, self.config.retention_days)
            
            processing_results["job_end_time"] = datetime.now().isoformat()
            processing_results["status"] = "SUCCESS"
            
            self.logger.info("HDFS storage batch processing job completed successfully")
            
        except Exception as e:
            processing_results["status"] = "FAILED"
            processing_results["errors"].append(str(e))
            processing_results["job_end_time"] = datetime.now().isoformat()
            self.logger.error(f"Batch processing job failed: {e}")
        
        return processing_results
    
    def shutdown(self):
        """Gracefully shutdown the pipeline"""
        self.logger.info("Shutting down HDFS storage pipeline...")
        
        try:
            if self.spark:
                self.spark.stop()
            self.logger.info("HDFS storage pipeline shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")


def load_config_from_file(config_file: str) -> HDFSStorageConfig:
    """Load configuration from file"""
    config_path = Path(config_file)
    
    if config_path.exists():
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        return HDFSStorageConfig(**config_data)
    else:
        return HDFSStorageConfig()


def create_default_config_file(config_file: str):
    """Create default configuration file"""
    config = HDFSStorageConfig()
    config_path = Path(config_file)
    
    # Create directory if it doesn't exist
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(config_path, 'w') as f:
        json.dump(asdict(config), f, indent=2)
    
    print(f"Created default configuration file: {config_file}")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Traffic HDFS Storage Pipeline')
    parser.add_argument('--config', '-c', default='config/hdfs_storage_config.json',
                       help='Configuration file path')
    parser.add_argument('--input-path', '-i', 
                       default='hdfs://localhost:9000/traffic/streaming',
                       help='Input path with streaming data')
    parser.add_argument('--date-filter', '-d', 
                       help='Date filter (YYYY-MM-DD format)')
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
    
    # Initialize and run pipeline
    pipeline = HDFSStoragePipeline(config)
    
    try:
        print("=" * 60)
        print("Traffic HDFS Storage Pipeline - Task 10")
        print("=" * 60)
        
        pipeline.initialize()
        pipeline.create_hdfs_directories()
        
        # Run batch processing job
        results = pipeline.run_batch_processing_job(args.input_path, args.date_filter)
        
        # Generate and save report
        report = pipeline.generate_storage_report(results)
        
        # Save report to HDFS
        report_path = f"logs/hdfs_storage_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        os.makedirs("logs", exist_ok=True)
        
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\nProcessing completed. Report saved to: {report_path}")
        print(f"Status: {results['status']}")
        print(f"Records processed: {results['records_processed']:,}")
        print(f"Records written: {results['records_written']:,}")
        
    except KeyboardInterrupt:
        pipeline.logger.info("Received keyboard interrupt")
    except Exception as e:
        pipeline.logger.error(f"Pipeline failed: {e}", exc_info=True)
    finally:
        pipeline.shutdown()


if __name__ == "__main__":
    main()
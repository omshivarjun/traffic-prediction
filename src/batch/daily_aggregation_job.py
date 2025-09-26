#!/usr/bin/env python3
"""
HDFS Batch Processing Job - Task 10.3
=====================================
Daily batch processing jobs for traffic data aggregation,
PostgreSQL storage, and report generation.
"""

import os
import sys
import json
import logging
import psycopg2
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict

# Add spark module to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'spark'))

try:
    from hdfs_storage import HDFSStoragePipeline, HDFSStorageConfig
except ImportError:
    # Fallback if import fails
    print("Warning: Could not import HDFSStoragePipeline, using minimal config")
    HDFSStoragePipeline = None
    HDFSStorageConfig = None

# PostgreSQL import with fallback
try:
    import psycopg2
except ImportError:
    print("Warning: psycopg2 not available, PostgreSQL features disabled")
    psycopg2 = None


@dataclass
class BatchJobConfig:
    """Configuration for batch processing jobs"""
    job_name: str = "daily_traffic_aggregation"
    schedule_hour: int = 2  # Run at 2 AM daily
    max_parallel_jobs: int = 4
    processing_timeout: int = 3600  # 1 hour timeout
    
    # PostgreSQL connection
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_database: str = "traffic_prediction"
    postgres_user: str = "postgres"
    postgres_password: str = "casa1234"
    
    # Processing parameters
    aggregation_levels: List[str] = None
    segment_batch_size: int = 100
    memory_per_executor: str = "2g"
    num_executors: int = 4
    
    def __post_init__(self):
        if self.aggregation_levels is None:
            self.aggregation_levels = ["hourly", "daily", "weekly", "monthly"]


@dataclass
class JobResult:
    """Result of batch processing job"""
    job_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = "RUNNING"
    records_processed: int = 0
    records_created: int = 0
    errors: List[str] = None
    performance_metrics: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.performance_metrics is None:
            self.performance_metrics = {}


class BatchJobOrchestrator:
    """Orchestrates daily batch processing jobs"""
    
    def __init__(self, config: BatchJobConfig, storage_config: HDFSStorageConfig):
        """Initialize batch job orchestrator"""
        self.config = config
        self.storage_config = storage_config
        self.storage_pipeline = HDFSStoragePipeline(storage_config)
        self.logger = self._setup_logging()
        self._pg_connection = None
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logger = logging.getLogger("batch_job_orchestrator")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            
            # Console handler
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
            
            # File handler
            os.makedirs("logs", exist_ok=True)
            file_handler = logging.FileHandler("logs/batch_processing.log")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        
        return logger
    
    def _get_postgres_connection(self):
        """Get PostgreSQL connection"""
        if self._pg_connection is None or self._pg_connection.closed:
            try:
                self._pg_connection = psycopg2.connect(
                    host=self.config.postgres_host,
                    port=self.config.postgres_port,
                    database=self.config.postgres_database,
                    user=self.config.postgres_user,
                    password=self.config.postgres_password
                )
                self._pg_connection.autocommit = True
            except Exception as e:
                self.logger.error(f"Failed to connect to PostgreSQL: {e}")
                raise
        
        return self._pg_connection
    
    def create_aggregation_tables(self) -> bool:
        """Create PostgreSQL tables for aggregated data"""
        self.logger.info("Creating aggregation tables in PostgreSQL...")
        
        table_schemas = {
            "daily_traffic_summary": """
                CREATE TABLE IF NOT EXISTS daily_traffic_summary (
                    id SERIAL PRIMARY KEY,
                    processing_date DATE NOT NULL,
                    segment_id VARCHAR(50) NOT NULL,
                    total_vehicles INTEGER NOT NULL DEFAULT 0,
                    avg_speed FLOAT NOT NULL DEFAULT 0.0,
                    max_speed FLOAT NOT NULL DEFAULT 0.0,
                    min_speed FLOAT NOT NULL DEFAULT 0.0,
                    avg_density FLOAT NOT NULL DEFAULT 0.0,
                    incident_count INTEGER NOT NULL DEFAULT 0,
                    congestion_hours FLOAT NOT NULL DEFAULT 0.0,
                    quality_score FLOAT NOT NULL DEFAULT 0.0,
                    data_completeness FLOAT NOT NULL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (processing_date, segment_id)
                );
            """,
            
            "hourly_traffic_aggregates": """
                CREATE TABLE IF NOT EXISTS hourly_traffic_aggregates (
                    id SERIAL PRIMARY KEY,
                    processing_hour TIMESTAMP NOT NULL,
                    segment_id VARCHAR(50) NOT NULL,
                    vehicle_count INTEGER NOT NULL DEFAULT 0,
                    avg_speed FLOAT NOT NULL DEFAULT 0.0,
                    speed_variance FLOAT NOT NULL DEFAULT 0.0,
                    density FLOAT NOT NULL DEFAULT 0.0,
                    flow_rate FLOAT NOT NULL DEFAULT 0.0,
                    incident_impact FLOAT NOT NULL DEFAULT 0.0,
                    weather_factor FLOAT NOT NULL DEFAULT 1.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (processing_hour, segment_id)
                );
            """,
            
            "batch_job_history": """
                CREATE TABLE IF NOT EXISTS batch_job_history (
                    id SERIAL PRIMARY KEY,
                    job_id VARCHAR(100) NOT NULL UNIQUE,
                    job_name VARCHAR(100) NOT NULL,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP,
                    status VARCHAR(20) NOT NULL,
                    records_processed INTEGER DEFAULT 0,
                    records_created INTEGER DEFAULT 0,
                    error_count INTEGER DEFAULT 0,
                    error_details TEXT,
                    performance_metrics JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """,
            
            "data_quality_reports": """
                CREATE TABLE IF NOT EXISTS data_quality_reports (
                    id SERIAL PRIMARY KEY,
                    report_date DATE NOT NULL,
                    report_type VARCHAR(50) NOT NULL,
                    total_records INTEGER NOT NULL DEFAULT 0,
                    valid_records INTEGER NOT NULL DEFAULT 0,
                    duplicate_records INTEGER NOT NULL DEFAULT 0,
                    missing_data_records INTEGER NOT NULL DEFAULT 0,
                    quality_score FLOAT NOT NULL DEFAULT 0.0,
                    issues_found JSONB,
                    recommendations JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (report_date, report_type)
                );
            """
        }
        
        try:
            conn = self._get_postgres_connection()
            cursor = conn.cursor()
            
            for table_name, schema in table_schemas.items():
                cursor.execute(schema)
                self.logger.info(f"✅ Created/verified table: {table_name}")
            
            # Create indexes for better performance
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_daily_summary_date ON daily_traffic_summary(processing_date);",
                "CREATE INDEX IF NOT EXISTS idx_daily_summary_segment ON daily_traffic_summary(segment_id);",
                "CREATE INDEX IF NOT EXISTS idx_hourly_agg_hour ON hourly_traffic_aggregates(processing_hour);",
                "CREATE INDEX IF NOT EXISTS idx_hourly_agg_segment ON hourly_traffic_aggregates(segment_id);",
                "CREATE INDEX IF NOT EXISTS idx_job_history_date ON batch_job_history(start_time);",
                "CREATE INDEX IF NOT EXISTS idx_quality_reports_date ON data_quality_reports(report_date);"
            ]
            
            for index_sql in indexes:
                cursor.execute(index_sql)
            
            cursor.close()
            self.logger.info("✅ All aggregation tables created successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to create aggregation tables: {e}")
            return False
    
    def run_daily_aggregation_job(self, processing_date: Optional[datetime] = None) -> JobResult:
        """Run daily traffic data aggregation job"""
        if processing_date is None:
            processing_date = datetime.now() - timedelta(days=1)  # Previous day
        
        job_id = f"daily_agg_{processing_date.strftime('%Y%m%d')}_{int(datetime.now().timestamp())}"
        
        job_result = JobResult(
            job_id=job_id,
            start_time=datetime.now()
        )
        
        self.logger.info(f"Starting daily aggregation job: {job_id}")
        self.logger.info(f"Processing date: {processing_date.strftime('%Y-%m-%d')}")
        
        try:
            # 1. Load raw streaming data from HDFS
            raw_data_path = self.storage_pipeline.get_partition_path(
                self.storage_config.streaming_data_path,
                processing_date
            )
            
            self.logger.info(f"Loading data from: {raw_data_path}")
            
            # Initialize Spark session
            from pyspark import SparkContext, SparkConf
            from pyspark.sql import SparkSession
            from pyspark.sql.functions import *
            from pyspark.sql.types import *
            
            conf = SparkConf().setAppName(f"DailyAggregation-{job_id}")
            conf.set("spark.executor.memory", self.config.memory_per_executor)
            conf.set("spark.executor.instances", str(self.config.num_executors))
            conf.set("spark.sql.adaptive.enabled", "true")
            conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")
            
            spark = SparkSession.builder.config(conf=conf).getOrCreate()
            
            # 2. Read streaming data for the processing date
            try:
                df = spark.read.parquet(raw_data_path)
                job_result.records_processed = df.count()
                self.logger.info(f"Loaded {job_result.records_processed:,} records")
                
            except Exception as e:
                self.logger.warning(f"No data found for date {processing_date}: {e}")
                job_result.status = "COMPLETED"
                job_result.end_time = datetime.now()
                return job_result
            
            # 3. Create hourly aggregations
            hourly_aggs = self._create_hourly_aggregations(spark, df, processing_date)
            
            # 4. Create daily summaries
            daily_summaries = self._create_daily_summaries(spark, df, processing_date)
            
            # 5. Store aggregations in PostgreSQL
            hourly_records = self._store_hourly_aggregations(hourly_aggs)
            daily_records = self._store_daily_summaries(daily_summaries)
            
            job_result.records_created = hourly_records + daily_records
            
            # 6. Generate data quality report
            quality_report = self._generate_quality_report(spark, df, processing_date)
            self._store_quality_report(quality_report)
            
            # 7. Performance metrics
            job_result.performance_metrics = {
                "processing_time_seconds": (datetime.now() - job_result.start_time).total_seconds(),
                "records_per_second": job_result.records_processed / max(1, (datetime.now() - job_result.start_time).total_seconds()),
                "hourly_aggregations_created": hourly_records,
                "daily_summaries_created": daily_records,
                "data_quality_score": quality_report.get("overall_quality_score", 0.0)
            }
            
            job_result.status = "COMPLETED"
            job_result.end_time = datetime.now()
            
            self.logger.info(f"✅ Daily aggregation job completed: {job_id}")
            self.logger.info(f"   Records processed: {job_result.records_processed:,}")
            self.logger.info(f"   Records created: {job_result.records_created:,}")
            self.logger.info(f"   Processing time: {job_result.performance_metrics['processing_time_seconds']:.2f}s")
            
            spark.stop()
            
        except Exception as e:
            job_result.status = "FAILED"
            job_result.end_time = datetime.now()
            job_result.errors.append(str(e))
            self.logger.error(f"❌ Daily aggregation job failed: {e}")
            
            if 'spark' in locals():
                spark.stop()
        
        # Store job result in database
        self._store_job_result(job_result)
        
        return job_result
    
    def _create_hourly_aggregations(self, spark, df, processing_date: datetime):
        """Create hourly traffic aggregations"""
        self.logger.info("Creating hourly aggregations...")
        
        from pyspark.sql.functions import *
        from pyspark.sql.window import Window
        
        # Add hour column for grouping
        df_with_hour = df.withColumn("processing_hour", 
                                   date_trunc("hour", col("timestamp")))
        
        # Group by hour and segment_id
        hourly_aggs = df_with_hour.groupBy("processing_hour", "segment_id").agg(
            count("*").alias("vehicle_count"),
            avg("speed").alias("avg_speed"),
            variance("speed").alias("speed_variance"),
            avg("density").alias("density"),
            avg("flow_rate").alias("flow_rate"),
            sum(when(col("incident_detected") == True, 1).otherwise(0)).alias("incident_count"),
            max("weather_factor").alias("weather_factor")
        )
        
        # Calculate incident impact as percentage
        hourly_aggs = hourly_aggs.withColumn(
            "incident_impact",
            when(col("vehicle_count") > 0, col("incident_count") / col("vehicle_count")).otherwise(0.0)
        )
        
        # Fill null values
        hourly_aggs = hourly_aggs.fillna({
            "avg_speed": 0.0,
            "speed_variance": 0.0,
            "density": 0.0,
            "flow_rate": 0.0,
            "incident_impact": 0.0,
            "weather_factor": 1.0
        })
        
        return hourly_aggs.collect()
    
    def _create_daily_summaries(self, spark, df, processing_date: datetime):
        """Create daily traffic summaries"""
        self.logger.info("Creating daily summaries...")
        
        from pyspark.sql.functions import *
        
        # Group by segment_id for daily aggregation
        daily_summaries = df.groupBy("segment_id").agg(
            count("*").alias("total_vehicles"),
            avg("speed").alias("avg_speed"),
            max("speed").alias("max_speed"),
            min("speed").alias("min_speed"),
            avg("density").alias("avg_density"),
            sum(when(col("incident_detected") == True, 1).otherwise(0)).alias("incident_count"),
            countDistinct("timestamp").alias("unique_timestamps")
        )
        
        # Calculate congestion hours (assuming speed < 30 mph indicates congestion)
        congestion_df = df.filter(col("speed") < 30.0).groupBy("segment_id").agg(
            countDistinct(date_trunc("hour", col("timestamp"))).alias("congestion_hours")
        )
        
        # Join with congestion data
        daily_summaries = daily_summaries.join(
            congestion_df, on="segment_id", how="left"
        ).fillna({"congestion_hours": 0})
        
        # Calculate data completeness (assuming 24 hours * expected readings per hour)
        expected_readings = 24 * 60  # Assuming minute-level data
        daily_summaries = daily_summaries.withColumn(
            "data_completeness",
            least(col("total_vehicles") / lit(expected_readings), lit(1.0))
        )
        
        # Calculate quality score (0-100)
        daily_summaries = daily_summaries.withColumn(
            "quality_score",
            (col("data_completeness") * 50) +  # 50% weight for completeness
            (when(col("avg_speed").between(0, 80), 25).otherwise(0)) +  # 25% for reasonable speed
            (when(col("incident_count") >= 0, 25).otherwise(0))  # 25% for valid incident data
        )
        
        # Add processing date
        daily_summaries = daily_summaries.withColumn(
            "processing_date", 
            lit(processing_date.date())
        )
        
        # Fill null values
        daily_summaries = daily_summaries.fillna({
            "avg_speed": 0.0,
            "max_speed": 0.0,
            "min_speed": 0.0,
            "avg_density": 0.0,
            "incident_count": 0,
            "congestion_hours": 0.0,
            "quality_score": 0.0,
            "data_completeness": 0.0
        })
        
        return daily_summaries.collect()
    
    def _store_hourly_aggregations(self, hourly_data: List) -> int:
        """Store hourly aggregations in PostgreSQL"""
        if not hourly_data:
            return 0
        
        self.logger.info(f"Storing {len(hourly_data)} hourly aggregations...")
        
        try:
            conn = self._get_postgres_connection()
            cursor = conn.cursor()
            
            # Prepare insert statement
            insert_sql = """
                INSERT INTO hourly_traffic_aggregates 
                (processing_hour, segment_id, vehicle_count, avg_speed, speed_variance, 
                 density, flow_rate, incident_impact, weather_factor)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (processing_hour, segment_id) 
                DO UPDATE SET
                    vehicle_count = EXCLUDED.vehicle_count,
                    avg_speed = EXCLUDED.avg_speed,
                    speed_variance = EXCLUDED.speed_variance,
                    density = EXCLUDED.density,
                    flow_rate = EXCLUDED.flow_rate,
                    incident_impact = EXCLUDED.incident_impact,
                    weather_factor = EXCLUDED.weather_factor
            """
            
            records_inserted = 0
            for row in hourly_data:
                try:
                    cursor.execute(insert_sql, (
                        row['processing_hour'],
                        row['segment_id'],
                        row['vehicle_count'],
                        float(row['avg_speed'] or 0.0),
                        float(row['speed_variance'] or 0.0),
                        float(row['density'] or 0.0),
                        float(row['flow_rate'] or 0.0),
                        float(row['incident_impact'] or 0.0),
                        float(row['weather_factor'] or 1.0)
                    ))
                    records_inserted += 1
                except Exception as e:
                    self.logger.warning(f"Failed to insert hourly record: {e}")
            
            cursor.close()
            self.logger.info(f"✅ Stored {records_inserted} hourly aggregations")
            return records_inserted
            
        except Exception as e:
            self.logger.error(f"❌ Failed to store hourly aggregations: {e}")
            return 0
    
    def _store_daily_summaries(self, daily_data: List) -> int:
        """Store daily summaries in PostgreSQL"""
        if not daily_data:
            return 0
        
        self.logger.info(f"Storing {len(daily_data)} daily summaries...")
        
        try:
            conn = self._get_postgres_connection()
            cursor = conn.cursor()
            
            # Prepare insert statement
            insert_sql = """
                INSERT INTO daily_traffic_summary 
                (processing_date, segment_id, total_vehicles, avg_speed, max_speed, min_speed,
                 avg_density, incident_count, congestion_hours, quality_score, data_completeness)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (processing_date, segment_id) 
                DO UPDATE SET
                    total_vehicles = EXCLUDED.total_vehicles,
                    avg_speed = EXCLUDED.avg_speed,
                    max_speed = EXCLUDED.max_speed,
                    min_speed = EXCLUDED.min_speed,
                    avg_density = EXCLUDED.avg_density,
                    incident_count = EXCLUDED.incident_count,
                    congestion_hours = EXCLUDED.congestion_hours,
                    quality_score = EXCLUDED.quality_score,
                    data_completeness = EXCLUDED.data_completeness,
                    updated_at = CURRENT_TIMESTAMP
            """
            
            records_inserted = 0
            for row in daily_data:
                try:
                    cursor.execute(insert_sql, (
                        row['processing_date'],
                        row['segment_id'],
                        row['total_vehicles'],
                        float(row['avg_speed'] or 0.0),
                        float(row['max_speed'] or 0.0),
                        float(row['min_speed'] or 0.0),
                        float(row['avg_density'] or 0.0),
                        row['incident_count'],
                        float(row['congestion_hours'] or 0.0),
                        float(row['quality_score'] or 0.0),
                        float(row['data_completeness'] or 0.0)
                    ))
                    records_inserted += 1
                except Exception as e:
                    self.logger.warning(f"Failed to insert daily record: {e}")
            
            cursor.close()
            self.logger.info(f"✅ Stored {records_inserted} daily summaries")
            return records_inserted
            
        except Exception as e:
            self.logger.error(f"❌ Failed to store daily summaries: {e}")
            return 0
    
    def _generate_quality_report(self, spark, df, processing_date: datetime) -> Dict[str, Any]:
        """Generate data quality report"""
        self.logger.info("Generating data quality report...")
        
        from pyspark.sql.functions import *
        
        total_records = df.count()
        
        # Check for null values
        null_checks = {}
        for column in df.columns:
            null_count = df.filter(col(column).isNull()).count()
            null_checks[column] = {
                "null_count": null_count,
                "null_percentage": (null_count / total_records * 100) if total_records > 0 else 0
            }
        
        # Check for duplicates
        distinct_records = df.dropDuplicates().count()
        duplicate_count = total_records - distinct_records
        
        # Check for out-of-range values
        invalid_speeds = df.filter((col("speed") < 0) | (col("speed") > 200)).count()
        invalid_densities = df.filter((col("density") < 0) | (col("density") > 1000)).count()
        
        # Calculate overall quality score
        completeness_score = (distinct_records / max(1, total_records)) * 100
        validity_score = ((total_records - invalid_speeds - invalid_densities) / max(1, total_records)) * 100
        overall_quality_score = (completeness_score + validity_score) / 2
        
        quality_report = {
            "report_date": processing_date.date().isoformat(),
            "report_type": "daily_batch",
            "total_records": total_records,
            "valid_records": distinct_records,
            "duplicate_records": duplicate_count,
            "null_value_analysis": null_checks,
            "invalid_values": {
                "invalid_speeds": invalid_speeds,
                "invalid_densities": invalid_densities
            },
            "quality_scores": {
                "completeness_score": completeness_score,
                "validity_score": validity_score,
                "overall_quality_score": overall_quality_score
            },
            "issues_found": [],
            "recommendations": []
        }
        
        # Add issues and recommendations
        if duplicate_count > total_records * 0.05:  # More than 5% duplicates
            quality_report["issues_found"].append("High duplicate rate detected")
            quality_report["recommendations"].append("Implement deduplication in streaming pipeline")
        
        if invalid_speeds > total_records * 0.01:  # More than 1% invalid speeds
            quality_report["issues_found"].append("Invalid speed values detected")
            quality_report["recommendations"].append("Add speed validation in data ingestion")
        
        return quality_report
    
    def _store_quality_report(self, quality_report: Dict[str, Any]) -> bool:
        """Store quality report in PostgreSQL"""
        try:
            conn = self._get_postgres_connection()
            cursor = conn.cursor()
            
            insert_sql = """
                INSERT INTO data_quality_reports 
                (report_date, report_type, total_records, valid_records, duplicate_records,
                 missing_data_records, quality_score, issues_found, recommendations)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (report_date, report_type) 
                DO UPDATE SET
                    total_records = EXCLUDED.total_records,
                    valid_records = EXCLUDED.valid_records,
                    duplicate_records = EXCLUDED.duplicate_records,
                    missing_data_records = EXCLUDED.missing_data_records,
                    quality_score = EXCLUDED.quality_score,
                    issues_found = EXCLUDED.issues_found,
                    recommendations = EXCLUDED.recommendations
            """
            
            # Calculate missing data records from null analysis
            missing_data_records = sum(
                analysis["null_count"] for analysis in quality_report["null_value_analysis"].values()
            )
            
            cursor.execute(insert_sql, (
                quality_report["report_date"],
                quality_report["report_type"],
                quality_report["total_records"],
                quality_report["valid_records"],
                quality_report["duplicate_records"],
                missing_data_records,
                quality_report["quality_scores"]["overall_quality_score"],
                json.dumps(quality_report["issues_found"]),
                json.dumps(quality_report["recommendations"])
            ))
            
            cursor.close()
            self.logger.info("✅ Quality report stored successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to store quality report: {e}")
            return False
    
    def _store_job_result(self, job_result: JobResult) -> bool:
        """Store job execution result in database"""
        try:
            conn = self._get_postgres_connection()
            cursor = conn.cursor()
            
            insert_sql = """
                INSERT INTO batch_job_history 
                (job_id, job_name, start_time, end_time, status, records_processed,
                 records_created, error_count, error_details, performance_metrics)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (job_id) 
                DO UPDATE SET
                    end_time = EXCLUDED.end_time,
                    status = EXCLUDED.status,
                    records_processed = EXCLUDED.records_processed,
                    records_created = EXCLUDED.records_created,
                    error_count = EXCLUDED.error_count,
                    error_details = EXCLUDED.error_details,
                    performance_metrics = EXCLUDED.performance_metrics
            """
            
            cursor.execute(insert_sql, (
                job_result.job_id,
                self.config.job_name,
                job_result.start_time,
                job_result.end_time,
                job_result.status,
                job_result.records_processed,
                job_result.records_created,
                len(job_result.errors),
                '\n'.join(job_result.errors) if job_result.errors else None,
                json.dumps(job_result.performance_metrics)
            ))
            
            cursor.close()
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to store job result: {e}")
            return False
    
    def get_job_history(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get recent job execution history"""
        try:
            conn = self._get_postgres_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT job_id, job_name, start_time, end_time, status, 
                       records_processed, records_created, error_count, performance_metrics
                FROM batch_job_history 
                WHERE start_time >= %s 
                ORDER BY start_time DESC
            """, (datetime.now() - timedelta(days=days),))
            
            columns = [desc[0] for desc in cursor.description]
            results = []
            
            for row in cursor.fetchall():
                job_data = dict(zip(columns, row))
                # Convert datetime objects to strings for JSON serialization
                if job_data['start_time']:
                    job_data['start_time'] = job_data['start_time'].isoformat()
                if job_data['end_time']:
                    job_data['end_time'] = job_data['end_time'].isoformat()
                results.append(job_data)
            
            cursor.close()
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to get job history: {e}")
            return []
    
    def cleanup_old_job_history(self, retention_days: int = 30) -> int:
        """Clean up old job history records"""
        try:
            conn = self._get_postgres_connection()
            cursor = conn.cursor()
            
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            
            cursor.execute("""
                DELETE FROM batch_job_history 
                WHERE start_time < %s
            """, (cutoff_date,))
            
            deleted_count = cursor.rowcount
            cursor.close()
            
            self.logger.info(f"Cleaned up {deleted_count} old job history records")
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup job history: {e}")
            return 0


def main():
    """Main execution function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='HDFS Batch Processing Job')
    parser.add_argument('--action', '-a', 
                       choices=['run-daily', 'create-tables', 'job-history', 'cleanup'],
                       default='run-daily',
                       help='Action to perform')
    parser.add_argument('--date', '-d', 
                       help='Processing date (YYYY-MM-DD), defaults to yesterday')
    parser.add_argument('--config', '-c', default='config/hdfs_storage_config.json',
                       help='Configuration file path')
    parser.add_argument('--retention-days', '-r', type=int, default=30,
                       help='Retention period for cleanup')
    
    args = parser.parse_args()
    
    # Load configuration
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"❌ Configuration file not found: {args.config}")
        return 1
    
    try:
        with open(config_path) as f:
            config_data = json.load(f)
        
        # Initialize configurations
        storage_config = HDFSStorageConfig(**config_data)
        batch_config = BatchJobConfig()
        
        # Update batch config with any loaded values
        for key, value in config_data.items():
            if hasattr(batch_config, key):
                setattr(batch_config, key, value)
        
        orchestrator = BatchJobOrchestrator(batch_config, storage_config)
        
        if args.action == 'create-tables':
            print("Creating PostgreSQL tables...")
            success = orchestrator.create_aggregation_tables()
            if success:
                print("✅ Tables created successfully")
                return 0
            else:
                print("❌ Failed to create tables")
                return 1
        
        elif args.action == 'run-daily':
            # Parse processing date
            processing_date = None
            if args.date:
                try:
                    processing_date = datetime.strptime(args.date, '%Y-%m-%d')
                except ValueError:
                    print(f"❌ Invalid date format: {args.date}. Use YYYY-MM-DD")
                    return 1
            
            print("Running daily aggregation job...")
            result = orchestrator.run_daily_aggregation_job(processing_date)
            
            if result.status == "COMPLETED":
                print(f"✅ Job completed successfully: {result.job_id}")
                print(f"   Records processed: {result.records_processed:,}")
                print(f"   Records created: {result.records_created:,}")
                if result.performance_metrics:
                    print(f"   Processing time: {result.performance_metrics.get('processing_time_seconds', 0):.2f}s")
                return 0
            else:
                print(f"❌ Job failed: {result.job_id}")
                for error in result.errors:
                    print(f"   Error: {error}")
                return 1
        
        elif args.action == 'job-history':
            print("Retrieving job history...")
            history = orchestrator.get_job_history()
            
            if history:
                print(f"Recent job history ({len(history)} jobs):")
                for job in history:
                    status_icon = "✅" if job['status'] == 'COMPLETED' else "❌"
                    print(f"  {status_icon} {job['job_id']} - {job['status']} - {job['start_time']}")
                    print(f"      Processed: {job['records_processed']:,}, Created: {job['records_created']:,}")
            else:
                print("No job history found")
            return 0
        
        elif args.action == 'cleanup':
            print(f"Cleaning up old job history (retention: {args.retention_days} days)...")
            deleted = orchestrator.cleanup_old_job_history(args.retention_days)
            print(f"✅ Cleaned up {deleted} old job records")
            return 0
    
    except Exception as e:
        print(f"❌ Operation failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
"""
PySpark Traffic Prediction Job

Distributed batch prediction processing using Spark for scalable traffic forecasting.
This job integrates with the core prediction service to provide distributed processing
capabilities for large-scale traffic prediction workloads.
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import traceback

# Spark imports
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import col, when, lit, udf, struct, collect_list
from pyspark.sql.types import StructType, StructField, StringType, FloatType, IntegerType, TimestampType
from pyspark import SparkContext

# Add prediction service to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from prediction_service import PredictionServiceConfig, DatabaseManager, ModelManager, FeatureProcessor

logger = logging.getLogger(__name__)


class SparkPredictionJob:
    """Spark-based distributed prediction job"""
    
    def __init__(self, config_path: str = "config/prediction_service_config.json"):
        """Initialize Spark prediction job"""
        
        # Load configuration
        self.config = PredictionServiceConfig(config_path)
        self.spark_config = self.config.spark_config
        
        # Initialize Spark session
        self.spark = self._create_spark_session()
        self.sc = self.spark.sparkContext
        
        # Setup logging
        self._setup_logging()
        
        # Initialize components
        self.db_manager = DatabaseManager(self.config)
        self.model_manager = ModelManager(self.config, self.spark)
        
        logger.info("Spark Prediction Job initialized successfully")
    
    def _setup_logging(self):
        """Setup distributed logging for Spark"""
        log_config = self.config.config['logging']
        
        # Configure main logger
        logging.basicConfig(
            level=getattr(logging, log_config['level']),
            format=f"[SPARK-{self.sc.applicationId}] {log_config['log_format']}",
            handlers=[
                logging.StreamHandler()
            ]
        )
        
        # Configure Spark logging
        self.sc.setLogLevel("WARN")  # Reduce Spark verbosity
    
    def _create_spark_session(self) -> SparkSession:
        """Create optimized Spark session for prediction workload"""
        
        builder = SparkSession.builder.appName(
            f"TrafficPredictionJob-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        )
        
        # Core Spark configuration
        default_config = {
            "spark.sql.adaptive.enabled": "true",
            "spark.sql.adaptive.coalescePartitions.enabled": "true",
            "spark.sql.adaptive.skewJoin.enabled": "true",
            "spark.serializer": "org.apache.spark.serializer.KryoSerializer",
            "spark.sql.execution.arrow.pyspark.enabled": "true",
            "spark.sql.execution.arrow.maxRecordsPerBatch": "10000",
            "spark.sql.broadcastTimeout": "36000",
            "spark.network.timeout": "800s",
            "spark.executor.heartbeatInterval": "60s"
        }
        
        # Apply default configuration
        for key, value in default_config.items():
            builder = builder.config(key, value)
        
        # Apply custom configuration from config file
        custom_config = self.spark_config.get('config', {})
        for key, value in custom_config.items():
            builder = builder.config(key, str(value))
        
        # Dynamic resource allocation based on data size
        data_size_gb = self._estimate_data_size()
        if data_size_gb > 10:
            builder = builder.config("spark.dynamicAllocation.enabled", "true")
            builder = builder.config("spark.dynamicAllocation.minExecutors", "2")
            builder = builder.config("spark.dynamicAllocation.maxExecutors", "10")
        
        return builder.getOrCreate()
    
    def _estimate_data_size(self) -> float:
        """Estimate data size for resource allocation"""
        try:
            # Query database for approximate data size
            sensor_count_query = "SELECT COUNT(*) as count FROM traffic.sensors WHERE status = 'active'"
            result = self.db_manager.execute_query(sensor_count_query)
            sensor_count = result[0]['count'] if result else 100
            
            # Estimate: 100 sensors * 24 hours * 12 readings/hour * 1KB per reading
            estimated_gb = (sensor_count * 24 * 12 * 1024) / (1024 * 1024 * 1024)
            return max(1.0, estimated_gb)  # Minimum 1GB
            
        except Exception as e:
            logger.warning(f"Could not estimate data size: {str(e)}")
            return 5.0  # Default 5GB
    
    def load_traffic_data_as_spark_df(self, hours_back: int = 24) -> DataFrame:
        """Load traffic data into Spark DataFrame"""
        logger.info(f"Loading traffic data from last {hours_back} hours into Spark DataFrame")
        
        # Define schema for traffic data
        traffic_schema = StructType([
            StructField("sensor_id", StringType(), False),
            StructField("location", StringType(), True),
            StructField("road_name", StringType(), True),
            StructField("road_type", StringType(), True),
            StructField("direction", StringType(), True),
            StructField("lane_count", IntegerType(), True),
            StructField("speed_limit", FloatType(), True),
            StructField("timestamp", TimestampType(), False),
            StructField("speed", FloatType(), True),
            StructField("volume", IntegerType(), True),
            StructField("occupancy", FloatType(), True),
            StructField("weather_condition", StringType(), True),
            StructField("temperature_c", FloatType(), True),
            StructField("humidity_percent", FloatType(), True),
            StructField("quality_score", FloatType(), True),
        ])
        
        # PostgreSQL connection properties
        pg_config = self.config.postgres_config
        jdbc_url = f"jdbc:postgresql://{pg_config['host']}:{pg_config['port']}/{pg_config['database']}"
        
        connection_properties = {
            "user": pg_config['user'],
            "password": os.getenv('POSTGRES_PASSWORD', pg_config.get('password', '')),
            "driver": "org.postgresql.Driver",
            "fetchsize": "10000",
            "batchsize": "10000"
        }
        
        # Build query with time filter
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        
        query = f"""
        (SELECT 
            s.sensor_id,
            ST_AsText(s.location) as location,
            s.road_name,
            s.road_type,
            s.direction,
            s.lane_count,
            s.speed_limit,
            tr.timestamp,
            tr.speed,
            tr.volume,
            tr.occupancy,
            tr.weather_condition,
            tr.temperature_c,
            tr.humidity_percent,
            tr.quality_score
        FROM traffic.sensors s
        JOIN traffic.traffic_readings tr ON s.id = tr.sensor_id
        WHERE tr.timestamp >= '{cutoff_time.isoformat()}'
          AND s.status = 'active'
          AND tr.quality_score >= 0.7
        ORDER BY s.sensor_id, tr.timestamp DESC) as traffic_data
        """
        
        try:
            # Load data using Spark JDBC
            df = self.spark.read.jdbc(
                url=jdbc_url,
                table=query,
                properties=connection_properties
            )
            
            # Cache the DataFrame for multiple operations
            df = df.cache()
            
            record_count = df.count()
            sensor_count = df.select("sensor_id").distinct().count()
            
            logger.info(f"Loaded {record_count} traffic records from {sensor_count} sensors into Spark DataFrame")
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to load traffic data into Spark DataFrame: {str(e)}")
            raise
    
    def process_features_with_spark(self, traffic_df: DataFrame) -> DataFrame:
        """Process features using Spark operations"""
        logger.info("Processing features using Spark DataFrame operations")
        
        try:
            # Add time-based features
            traffic_df = traffic_df.withColumn("hour_of_day", 
                                             col("timestamp").cast("timestamp").cast("int") % 86400 / 3600) \
                                   .withColumn("day_of_week", 
                                             col("timestamp").cast("timestamp").cast("int") / 86400 % 7) \
                                   .withColumn("is_weekend", 
                                             col("day_of_week") >= 5) \
                                   .withColumn("is_rush_hour",
                                             when((col("day_of_week") < 5) & 
                                                  (((col("hour_of_day") >= 7) & (col("hour_of_day") <= 9)) |
                                                   ((col("hour_of_day") >= 17) & (col("hour_of_day") <= 19))), 
                                                  True).otherwise(False))
            
            # Window functions for statistical features (last 10 readings per sensor)
            from pyspark.sql.window import Window
            
            # Define window: last 10 readings per sensor ordered by timestamp desc
            window_spec = Window.partitionBy("sensor_id").orderBy(col("timestamp").desc()).rowsBetween(0, 9)
            
            # Calculate rolling statistics
            from pyspark.sql.functions import avg, stddev, min as spark_min, max as spark_max, first, count
            
            feature_df = traffic_df.withColumn("avg_speed_1h", avg("speed").over(window_spec)) \
                                   .withColumn("std_speed_1h", stddev("speed").over(window_spec)) \
                                   .withColumn("min_speed_1h", spark_min("speed").over(window_spec)) \
                                   .withColumn("max_speed_1h", spark_max("speed").over(window_spec)) \
                                   .withColumn("avg_volume_1h", avg("volume").over(window_spec)) \
                                   .withColumn("std_volume_1h", stddev("volume").over(window_spec)) \
                                   .withColumn("avg_occupancy_1h", avg("occupancy").over(window_spec)) \
                                   .withColumn("std_occupancy_1h", stddev("occupancy").over(window_spec)) \
                                   .withColumn("readings_count", count("*").over(window_spec))
            
            # Get latest reading per sensor (for current conditions)
            latest_window = Window.partitionBy("sensor_id").orderBy(col("timestamp").desc())
            from pyspark.sql.functions import row_number
            
            latest_readings = feature_df.withColumn("row_num", row_number().over(latest_window)) \
                                        .filter(col("row_num") == 1) \
                                        .drop("row_num")
            
            # Fill null values with defaults
            feature_columns = {
                "avg_speed_1h": 50.0,
                "std_speed_1h": 10.0,
                "min_speed_1h": 0.0,
                "max_speed_1h": 100.0,
                "avg_volume_1h": 1000,
                "std_volume_1h": 500,
                "avg_occupancy_1h": 50.0,
                "std_occupancy_1h": 20.0,
                "temperature_c": 20.0,
                "humidity_percent": 50.0,
                "quality_score": 0.8
            }
            
            for col_name, default_val in feature_columns.items():
                if col_name in latest_readings.columns:
                    latest_readings = latest_readings.fillna({col_name: default_val})
            
            # Cache processed features
            latest_readings = latest_readings.cache()
            
            feature_count = latest_readings.count()
            logger.info(f"Processed features for {feature_count} sensors using Spark")
            
            return latest_readings
            
        except Exception as e:
            logger.error(f"Feature processing with Spark failed: {str(e)}")
            raise
    
    def generate_predictions_with_spark(self, features_df: DataFrame) -> List[Dict]:
        """Generate predictions using Spark with broadcasted model"""
        logger.info("Generating predictions using Spark with distributed processing")
        
        try:
            # Load model and broadcast it
            model, metadata = self.model_manager.get_model()
            model_broadcast = self.sc.broadcast(model)
            metadata_broadcast = self.sc.broadcast(metadata)
            
            logger.info(f"Broadcasting model: {metadata.get('model_name', 'unknown')} v{metadata.get('version', '1.0')}")
            
            # Convert Spark DataFrame to Pandas for prediction (collect to driver)
            # For very large datasets, consider using mapPartitions for distributed prediction
            features_pandas = features_df.toPandas()
            
            if features_pandas.empty:
                logger.warning("No features available for prediction")
                return []
            
            # Use the core prediction logic
            feature_processor = FeatureProcessor(self.config)
            
            # Generate predictions for each horizon
            all_predictions = []
            horizons = self.config.prediction_settings['horizon_minutes']
            
            for horizon in horizons:
                try:
                    # Generate predictions for this horizon
                    horizon_predictions = self._generate_spark_predictions(
                        features_pandas, model_broadcast.value, 
                        metadata_broadcast.value, horizon
                    )
                    all_predictions.extend(horizon_predictions)
                    
                    logger.info(f"Generated {len(horizon_predictions)} predictions for {horizon}-minute horizon")
                    
                except Exception as e:
                    logger.error(f"Failed to generate predictions for {horizon}-minute horizon: {str(e)}")
            
            # Cleanup broadcasts
            model_broadcast.unpersist()
            metadata_broadcast.unpersist()
            
            logger.info(f"Generated total of {len(all_predictions)} predictions using Spark")
            return all_predictions
            
        except Exception as e:
            logger.error(f"Spark prediction generation failed: {str(e)}")
            raise
    
    def _generate_spark_predictions(self, features_df, model, metadata, horizon_minutes: int) -> List[Dict]:
        """Generate predictions for specific horizon using distributed model"""
        predictions = []
        prediction_timestamp = datetime.now()
        target_timestamp = prediction_timestamp + timedelta(minutes=horizon_minutes)
        
        # Prepare features for prediction
        non_feature_cols = [
            'sensor_id', 'location', 'road_name', 'road_type', 'direction', 
            'timestamp', 'weather_condition'
        ]
        feature_cols = [col for col in features_df.columns if col not in non_feature_cols]
        
        if not feature_cols:
            logger.warning("No feature columns found for prediction")
            return []
        
        # Prepare feature matrix
        X = features_df[feature_cols].fillna(0)
        
        try:
            # Make predictions using the model
            if hasattr(model, 'predict'):
                predictions_raw = model.predict(X)
            else:
                logger.error("Model does not have predict method")
                return []
            
            # Process predictions
            for idx, (_, row) in enumerate(features_df.iterrows()):
                if idx >= len(predictions_raw):
                    break
                
                # Extract prediction values
                pred_values = predictions_raw[idx]
                if hasattr(pred_values, '__len__') and len(pred_values) > 1:
                    predicted_speed = float(pred_values[0])
                    predicted_volume = float(pred_values[1]) if len(pred_values) > 1 else None
                else:
                    predicted_speed = float(pred_values)
                    predicted_volume = None
                
                # Calculate travel time
                predicted_travel_time = None
                if predicted_speed and predicted_speed > 0:
                    predicted_travel_time = int((1.0 / predicted_speed) * 3600)
                
                # Calculate confidence (simplified)
                confidence_score = min(1.0, 0.7 + (row.get('quality_score', 0.5) * 0.3))
                
                prediction = {
                    'sensor_id': row['sensor_id'],
                    'prediction_timestamp': prediction_timestamp,
                    'horizon_minutes': horizon_minutes,
                    'predicted_speed': predicted_speed,
                    'predicted_volume': predicted_volume,
                    'predicted_travel_time': predicted_travel_time,
                    'confidence_score': confidence_score,
                    'model_name': metadata.get('model_name', 'unknown'),
                    'model_version': metadata.get('version', '1.0'),
                    'features_used': feature_cols,
                    'target_timestamp': target_timestamp
                }
                
                predictions.append(prediction)
        
        except Exception as e:
            logger.error(f"Prediction generation failed: {str(e)}")
            raise
        
        return predictions
    
    def run_spark_prediction_job(self) -> Dict[str, Any]:
        """Run complete Spark-based prediction job"""
        logger.info("Starting Spark prediction job")
        start_time = datetime.now()
        
        try:
            # Step 1: Load traffic data into Spark DataFrame
            traffic_df = self.load_traffic_data_as_spark_df(hours_back=24)
            
            if traffic_df.count() == 0:
                logger.warning("No traffic data available for Spark processing")
                return {
                    "status": "skipped",
                    "reason": "No traffic data available",
                    "processing_time": (datetime.now() - start_time).total_seconds()
                }
            
            # Step 2: Process features with Spark
            features_df = self.process_features_with_spark(traffic_df)
            
            if features_df.count() == 0:
                logger.warning("No features could be processed with Spark")
                return {
                    "status": "failed",
                    "reason": "Spark feature processing failed",
                    "processing_time": (datetime.now() - start_time).total_seconds()
                }
            
            # Step 3: Generate predictions
            predictions = self.generate_predictions_with_spark(features_df)
            
            if not predictions:
                logger.warning("No predictions generated by Spark job")
                return {
                    "status": "failed",
                    "reason": "Spark prediction generation failed",
                    "processing_time": (datetime.now() - start_time).total_seconds()
                }
            
            # Step 4: Store predictions
            logger.info("Storing Spark-generated predictions...")
            stored_count = self.db_manager.store_predictions(predictions)
            
            # Step 5: Cleanup DataFrames
            traffic_df.unpersist()
            features_df.unpersist()
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            result = {
                "status": "completed",
                "job_type": "spark_distributed",
                "predictions_generated": len(predictions),
                "predictions_stored": stored_count,
                "sensors_processed": features_df.select("sensor_id").distinct().count(),
                "processing_time": processing_time,
                "timestamp": datetime.now().isoformat(),
                "spark_application_id": self.sc.applicationId,
                "executors_used": len(self.sc.statusTracker().getExecutorInfos())
            }
            
            logger.info(f"Spark prediction job completed: {json.dumps(result, indent=2)}")
            return result
            
        except Exception as e:
            error_msg = f"Spark prediction job failed: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            return {
                "status": "failed",
                "error": error_msg,
                "processing_time": (datetime.now() - start_time).total_seconds(),
                "timestamp": datetime.now().isoformat()
            }
    
    def cleanup(self):
        """Cleanup Spark resources"""
        try:
            if hasattr(self, 'db_manager'):
                self.db_manager.close()
            
            if hasattr(self, 'spark'):
                self.spark.stop()
            
            logger.info("Spark prediction job cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during Spark cleanup: {str(e)}")


def main():
    """Main execution function for Spark job"""
    job = None
    
    try:
        # Initialize Spark job
        job = SparkPredictionJob()
        
        # Run the job
        result = job.run_spark_prediction_job()
        
        # Print results
        print("\n" + "="*80)
        print("SPARK PREDICTION JOB RESULTS")
        print("="*80)
        print(json.dumps(result, indent=2))
        print("="*80)
        
        # Exit code based on result
        if result.get('status') == 'completed':
            exit(0)
        else:
            exit(1)
    
    except Exception as e:
        print(f"Fatal error in Spark job: {str(e)}", file=sys.stderr)
        exit(1)
    
    finally:
        if job:
            job.cleanup()


if __name__ == "__main__":
    main()
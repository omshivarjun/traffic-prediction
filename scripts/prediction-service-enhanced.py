#!/usr/bin/env python3
"""
Enhanced Traffic Prediction Service
Generates real-time predictions and stores them in HDFS and Kafka

Features:
- Load trained ML models from HDFS
- Generate predictions from streaming data
- Store predictions back to HDFS  
- Push predictions to Kafka 'predictions' topic
- Real-time monitoring and health checks
"""

import os
import sys
import json
import time
import logging
import pickle
import joblib
import signal
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
import threading
import queue

# Data processing
import pandas as pd
import numpy as np

# Kafka
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError

# Spark for HDFS integration
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import *
from pyspark.sql.types import *

# ML libraries  
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
import xgboost as xgb

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("prediction_service")

@dataclass
class PredictionServiceConfig:
    """Configuration for the prediction service"""
    # Kafka Configuration
    kafka_bootstrap_servers: str = "localhost:9094"
    input_topic: str = "processed-traffic-aggregates"
    output_topic: str = "traffic-predictions"
    consumer_group_id: str = "prediction-service"
    
    # HDFS Configuration
    hdfs_namenode: str = "hdfs://localhost:9001"
    model_path: str = "hdfs://localhost:9001/traffic/models"
    predictions_output_path: str = "hdfs://localhost:9001/traffic/predictions"
    
    # Model Configuration
    model_types: List[str] = None
    prediction_horizon_minutes: List[int] = None
    confidence_intervals: bool = True
    ensemble_predictions: bool = True
    
    # Processing Configuration
    batch_size: int = 100
    prediction_frequency_seconds: int = 30
    max_queue_size: int = 1000
    
    # Performance Configuration
    enable_caching: bool = True
    cache_ttl_seconds: int = 300
    parallel_predictions: bool = True
    max_workers: int = 4
    
    def __post_init__(self):
        if self.model_types is None:
            self.model_types = ["random_forest", "xgboost", "gradient_boosting"]
        if self.prediction_horizon_minutes is None:
            self.prediction_horizon_minutes = [5, 15, 30, 60]

class ModelManager:
    """Manages loading and caching of ML models"""
    
    def __init__(self, spark_session: SparkSession, config: PredictionServiceConfig):
        self.spark = spark_session
        self.config = config
        self.models = {}
        self.scalers = {}
        self.model_metadata = {}
        self.last_model_update = {}
        
    def load_models(self) -> bool:
        """Load all trained models from HDFS"""
        try:
            logger.info("Loading models from HDFS...")
            
            # List available models in HDFS
            model_path = self.config.model_path
            
            for model_type in self.config.model_types:
                model_file_path = f"{model_path}/{model_type}_model.pkl"
                scaler_file_path = f"{model_path}/{model_type}_scaler.pkl"
                metadata_file_path = f"{model_path}/{model_type}_metadata.json"
                
                try:
                    # Load model using Spark (for HDFS access)
                    model_data = self._load_from_hdfs(model_file_path)
                    scaler_data = self._load_from_hdfs(scaler_file_path)
                    metadata_data = self._load_from_hdfs(metadata_file_path)
                    
                    # Deserialize model and scaler
                    model = pickle.loads(model_data)
                    scaler = pickle.loads(scaler_data) if scaler_data else None
                    metadata = json.loads(metadata_data.decode('utf-8')) if metadata_data else {}
                    
                    self.models[model_type] = model
                    self.scalers[model_type] = scaler
                    self.model_metadata[model_type] = metadata
                    self.last_model_update[model_type] = datetime.now()
                    
                    logger.info(f"✓ Loaded {model_type} model (accuracy: {metadata.get('test_rmse', 'N/A')})")
                    
                except Exception as e:
                    logger.warning(f"Failed to load {model_type} model: {e}")
                    continue
            
            if not self.models:
                logger.error("No models loaded successfully")
                return False
                
            logger.info(f"Successfully loaded {len(self.models)} models")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load models: {e}")
            return False
    
    def _load_from_hdfs(self, hdfs_path: str) -> bytes:
        """Load file from HDFS using Spark"""
        try:
            # Use Spark to read binary file from HDFS
            rdd = self.spark.sparkContext.binaryFiles(hdfs_path)
            if rdd.isEmpty():
                return None
            return rdd.collect()[0][1]
        except Exception:
            return None
    
    def get_model(self, model_type: str):
        """Get a loaded model"""
        return self.models.get(model_type)
    
    def get_scaler(self, model_type: str):
        """Get a loaded scaler"""
        return self.scalers.get(model_type)
    
    def get_metadata(self, model_type: str) -> Dict:
        """Get model metadata"""
        return self.model_metadata.get(model_type, {})
    
    def refresh_models_if_needed(self) -> bool:
        """Check and refresh models if they've been updated"""
        try:
            # Check if models need refreshing (every 5 minutes)
            current_time = datetime.now()
            refresh_needed = any(
                (current_time - last_update).total_seconds() > 300
                for last_update in self.last_model_update.values()
            )
            
            if refresh_needed:
                logger.info("Refreshing models...")
                return self.load_models()
            
            return True
            
        except Exception as e:
            logger.error(f"Error refreshing models: {e}")
            return False

class PredictionEngine:
    """Core prediction engine"""
    
    def __init__(self, model_manager: ModelManager, config: PredictionServiceConfig):
        self.model_manager = model_manager
        self.config = config
        self.prediction_cache = {}
        
    def generate_predictions(self, traffic_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate predictions for traffic data"""
        try:
            if not traffic_data:
                return []
            
            # Convert to DataFrame for processing
            df = pd.DataFrame(traffic_data)
            
            # Feature engineering
            df = self._engineer_features(df)
            
            # Generate predictions for each model and horizon
            predictions = []
            
            for model_type in self.config.model_types:
                model = self.model_manager.get_model(model_type)
                scaler = self.model_manager.get_scaler(model_type)
                
                if not model:
                    continue
                
                try:
                    # Prepare features
                    features = self._prepare_features(df, scaler)
                    
                    # Generate predictions for each horizon
                    for horizon_minutes in self.config.prediction_horizon_minutes:
                        pred_values = model.predict(features)
                        
                        # Create prediction records
                        for i, (_, row) in enumerate(df.iterrows()):
                            prediction = {
                                'timestamp': datetime.now().isoformat(),
                                'sensor_id': row.get('sensor_id', f'sensor_{i}'),
                                'prediction_timestamp': (datetime.now() + timedelta(minutes=horizon_minutes)).isoformat(),
                                'horizon_minutes': horizon_minutes,
                                'model_type': model_type,
                                'predicted_speed_mph': float(pred_values[i]),
                                'predicted_congestion_level': self._calculate_congestion_level(pred_values[i]),
                                'confidence_score': self._calculate_confidence(model, features[i:i+1]),
                                'latitude': row.get('latitude', 0.0),
                                'longitude': row.get('longitude', 0.0),
                                'road_type': row.get('road_type', 'unknown'),
                                'road_name': row.get('road_name', 'unknown')
                            }
                            
                            # Add confidence intervals if enabled
                            if self.config.confidence_intervals:
                                confidence_interval = self._calculate_confidence_interval(
                                    model, features[i:i+1], confidence_level=0.95
                                )
                                prediction.update({
                                    'prediction_lower_bound': float(confidence_interval[0]),
                                    'prediction_upper_bound': float(confidence_interval[1])
                                })
                            
                            predictions.append(prediction)
                            
                except Exception as e:
                    logger.error(f"Error generating predictions with {model_type}: {e}")
                    continue
            
            # Generate ensemble predictions if enabled
            if self.config.ensemble_predictions and len(self.config.model_types) > 1:
                ensemble_predictions = self._generate_ensemble_predictions(df, predictions)
                predictions.extend(ensemble_predictions)
            
            logger.info(f"Generated {len(predictions)} predictions")
            return predictions
            
        except Exception as e:
            logger.error(f"Error generating predictions: {e}")
            return []
    
    def _engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Engineer features for prediction"""
        try:
            # Time-based features
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df['hour'] = df['timestamp'].dt.hour
                df['day_of_week'] = df['timestamp'].dt.dayofweek
                df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
                df['is_rush_hour'] = ((df['hour'].between(7, 9)) | (df['hour'].between(17, 19))).astype(int)
            
            # Traffic features
            numeric_columns = ['speed_mph', 'volume_vehicles_per_hour']
            for col in numeric_columns:
                if col in df.columns:
                    df[f'{col}_rolling_mean'] = df[col].rolling(window=3, min_periods=1).mean()
                    df[f'{col}_rolling_std'] = df[col].rolling(window=3, min_periods=1).std().fillna(0)
            
            # Categorical encoding
            categorical_columns = ['road_type', 'direction']
            for col in categorical_columns:
                if col in df.columns:
                    df[f'{col}_encoded'] = pd.Categorical(df[col]).codes
            
            return df
            
        except Exception as e:
            logger.error(f"Error in feature engineering: {e}")
            return df
    
    def _prepare_features(self, df: pd.DataFrame, scaler=None) -> np.ndarray:
        """Prepare features for model input"""
        try:
            # Select feature columns (exclude target and identifier columns)
            feature_columns = [col for col in df.columns if col not in [
                'sensor_id', 'timestamp', 'speed_mph', 'volume_vehicles_per_hour'
            ] and df[col].dtype in ['int64', 'float64']]
            
            features = df[feature_columns].fillna(0).values
            
            # Apply scaling if scaler is available
            if scaler:
                features = scaler.transform(features)
            
            return features
            
        except Exception as e:
            logger.error(f"Error preparing features: {e}")
            return np.array([])
    
    def _calculate_congestion_level(self, speed_mph: float) -> int:
        """Calculate congestion level from speed"""
        if speed_mph >= 50:
            return 1  # Free flow
        elif speed_mph >= 35:
            return 2  # Light traffic
        elif speed_mph >= 25:
            return 3  # Moderate traffic
        elif speed_mph >= 15:
            return 4  # Heavy traffic
        else:
            return 5  # Severe congestion
    
    def _calculate_confidence(self, model, features: np.ndarray) -> float:
        """Calculate prediction confidence score"""
        try:
            # For tree-based models, use prediction variance across trees
            if hasattr(model, 'estimators_'):
                predictions = np.array([tree.predict(features)[0] for tree in model.estimators_])
                confidence = 1.0 - (np.std(predictions) / np.mean(predictions)) if np.mean(predictions) != 0 else 0.5
                return max(0.0, min(1.0, confidence))
            
            # Default confidence for other models
            return 0.8
            
        except Exception:
            return 0.5
    
    def _calculate_confidence_interval(self, model, features: np.ndarray, confidence_level: float = 0.95) -> tuple:
        """Calculate prediction confidence intervals"""
        try:
            if hasattr(model, 'estimators_'):
                # For ensemble models, use prediction variance
                predictions = np.array([tree.predict(features)[0] for tree in model.estimators_])
                mean_pred = np.mean(predictions)
                std_pred = np.std(predictions)
                
                # Calculate confidence interval
                z_score = 1.96 if confidence_level == 0.95 else 2.58  # 95% or 99%
                margin = z_score * std_pred
                
                return (mean_pred - margin, mean_pred + margin)
            
            # Default interval for other models
            pred = model.predict(features)[0]
            margin = pred * 0.1  # 10% margin
            return (pred - margin, pred + margin)
            
        except Exception:
            pred = model.predict(features)[0]
            return (pred * 0.9, pred * 1.1)
    
    def _generate_ensemble_predictions(self, df: pd.DataFrame, individual_predictions: List[Dict]) -> List[Dict]:
        """Generate ensemble predictions from individual model predictions"""
        try:
            ensemble_predictions = []
            
            # Group predictions by sensor and horizon
            grouped_predictions = {}
            for pred in individual_predictions:
                key = (pred['sensor_id'], pred['horizon_minutes'])
                if key not in grouped_predictions:
                    grouped_predictions[key] = []
                grouped_predictions[key].append(pred)
            
            # Create ensemble predictions
            for (sensor_id, horizon_minutes), preds in grouped_predictions.items():
                if len(preds) < 2:  # Need at least 2 models for ensemble
                    continue
                
                # Calculate ensemble metrics
                speeds = [p['predicted_speed_mph'] for p in preds]
                weights = [p['confidence_score'] for p in preds]
                
                # Weighted average
                ensemble_speed = np.average(speeds, weights=weights)
                ensemble_confidence = np.mean(weights)
                
                # Create ensemble prediction
                base_pred = preds[0]  # Use first prediction as template
                ensemble_pred = {
                    'timestamp': datetime.now().isoformat(),
                    'sensor_id': sensor_id,
                    'prediction_timestamp': base_pred['prediction_timestamp'],
                    'horizon_minutes': horizon_minutes,
                    'model_type': 'ensemble',
                    'predicted_speed_mph': float(ensemble_speed),
                    'predicted_congestion_level': self._calculate_congestion_level(ensemble_speed),
                    'confidence_score': float(ensemble_confidence),
                    'latitude': base_pred.get('latitude', 0.0),
                    'longitude': base_pred.get('longitude', 0.0),
                    'road_type': base_pred.get('road_type', 'unknown'),
                    'road_name': base_pred.get('road_name', 'unknown'),
                    'ensemble_components': len(preds)
                }
                
                ensemble_predictions.append(ensemble_pred)
            
            return ensemble_predictions
            
        except Exception as e:
            logger.error(f"Error generating ensemble predictions: {e}")
            return []

class TrafficPredictionService:
    """Main prediction service class"""
    
    def __init__(self, config: PredictionServiceConfig):
        self.config = config
        self.running = False
        self.spark = None
        self.model_manager = None
        self.prediction_engine = None
        self.kafka_consumer = None
        self.kafka_producer = None
        self.prediction_queue = queue.Queue(maxsize=config.max_queue_size)
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def initialize(self) -> bool:
        """Initialize the prediction service"""
        try:
            logger.info("Initializing Traffic Prediction Service...")
            
            # Initialize Spark session
            self.spark = self._create_spark_session()
            if not self.spark:
                return False
            
            # Initialize model manager and load models
            self.model_manager = ModelManager(self.spark, self.config)
            if not self.model_manager.load_models():
                logger.error("Failed to load models")
                return False
            
            # Initialize prediction engine
            self.prediction_engine = PredictionEngine(self.model_manager, self.config)
            
            # Initialize Kafka connections
            if not self._initialize_kafka():
                return False
            
            logger.info("✅ Prediction service initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize prediction service: {e}")
            return False
    
    def _create_spark_session(self) -> Optional[SparkSession]:
        """Create Spark session for HDFS access"""
        try:
            spark = SparkSession.builder \
                .appName("TrafficPredictionService") \
                .config("spark.sql.adaptive.enabled", "true") \
                .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
                .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
                .getOrCreate()
            
            spark.sparkContext.setLogLevel("WARN")
            logger.info("✓ Spark session created")
            return spark
            
        except Exception as e:
            logger.error(f"Failed to create Spark session: {e}")
            return None
    
    def _initialize_kafka(self) -> bool:
        """Initialize Kafka consumer and producer"""
        try:
            # Initialize consumer
            self.kafka_consumer = KafkaConsumer(
                self.config.input_topic,
                bootstrap_servers=self.config.kafka_bootstrap_servers,
                group_id=self.config.consumer_group_id,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',
                enable_auto_commit=True,
                consumer_timeout_ms=5000
            )
            
            # Initialize producer
            self.kafka_producer = KafkaProducer(
                bootstrap_servers=self.config.kafka_bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                acks='all',
                retries=3
            )
            
            logger.info("✓ Kafka connections initialized")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Kafka: {e}")
            return False
    
    def run(self):
        """Run the prediction service"""
        try:
            logger.info("🚀 Starting Traffic Prediction Service")
            self.running = True
            
            # Start prediction processing thread
            prediction_thread = threading.Thread(target=self._prediction_worker)
            prediction_thread.start()
            
            # Start HDFS writer thread
            hdfs_writer_thread = threading.Thread(target=self._hdfs_writer_worker)
            hdfs_writer_thread.start()
            
            # Main consumer loop
            while self.running:
                try:
                    # Poll for messages
                    message_batch = self.kafka_consumer.poll(timeout_ms=1000)
                    
                    if message_batch:
                        traffic_data = []
                        for partition_messages in message_batch.values():
                            for message in partition_messages:
                                traffic_data.append(message.value)
                        
                        if traffic_data:
                            # Add to prediction queue
                            try:
                                self.prediction_queue.put(traffic_data, timeout=1)
                                logger.debug(f"Added {len(traffic_data)} records to prediction queue")
                            except queue.Full:
                                logger.warning("Prediction queue is full, dropping messages")
                    
                    # Refresh models periodically
                    self.model_manager.refresh_models_if_needed()
                    
                except Exception as e:
                    logger.error(f"Error in main loop: {e}")
                    time.sleep(1)
            
            # Wait for threads to complete
            prediction_thread.join(timeout=30)
            hdfs_writer_thread.join(timeout=30)
            
        except Exception as e:
            logger.error(f"Error running prediction service: {e}")
        finally:
            self._cleanup()
    
    def _prediction_worker(self):
        """Worker thread for generating predictions"""
        logger.info("Prediction worker started")
        
        while self.running:
            try:
                # Get traffic data from queue
                traffic_data = self.prediction_queue.get(timeout=1)
                
                # Generate predictions
                predictions = self.prediction_engine.generate_predictions(traffic_data)
                
                # Send predictions to Kafka
                for prediction in predictions:
                    try:
                        self.kafka_producer.send(
                            self.config.output_topic,
                            value=prediction,
                            key=prediction['sensor_id']
                        )
                    except Exception as e:
                        logger.error(f"Error sending prediction to Kafka: {e}")
                
                # Flush producer
                self.kafka_producer.flush(timeout=5)
                
                self.prediction_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in prediction worker: {e}")
        
        logger.info("Prediction worker stopped")
    
    def _hdfs_writer_worker(self):
        """Worker thread for writing predictions to HDFS"""
        logger.info("HDFS writer worker started")
        
        prediction_buffer = []
        last_write_time = time.time()
        
        while self.running:
            try:
                # Collect predictions from Kafka topic (for HDFS storage)
                consumer_messages = self.kafka_consumer.poll(timeout_ms=1000)
                
                for partition_messages in consumer_messages.values():
                    for message in partition_messages:
                        if message.topic == self.config.output_topic:
                            prediction_buffer.append(message.value)
                
                # Write to HDFS periodically or when buffer is full
                current_time = time.time()
                if (len(prediction_buffer) >= self.config.batch_size or 
                    current_time - last_write_time > 60):  # Write every minute
                    
                    if prediction_buffer:
                        self._write_predictions_to_hdfs(prediction_buffer)
                        prediction_buffer.clear()
                        last_write_time = current_time
                
            except Exception as e:
                logger.error(f"Error in HDFS writer worker: {e}")
                time.sleep(1)
        
        # Write remaining predictions
        if prediction_buffer:
            self._write_predictions_to_hdfs(prediction_buffer)
        
        logger.info("HDFS writer worker stopped")
    
    def _write_predictions_to_hdfs(self, predictions: List[Dict]):
        """Write predictions to HDFS with time-based partitioning"""
        try:
            if not predictions:
                return
            
            # Convert to DataFrame
            df = self.spark.createDataFrame(predictions)
            
            # Add partitioning columns
            df = df.withColumn("year", year(col("timestamp"))) \
                  .withColumn("month", month(col("timestamp"))) \
                  .withColumn("day", dayofmonth(col("timestamp"))) \
                  .withColumn("hour", hour(col("timestamp")))
            
            # Write to HDFS with partitioning
            output_path = f"{self.config.predictions_output_path}/year={datetime.now().year}/month={datetime.now().month:02d}/day={datetime.now().day:02d}"
            
            df.write \
              .mode("append") \
              .option("compression", "snappy") \
              .parquet(output_path)
            
            logger.info(f"✓ Wrote {len(predictions)} predictions to HDFS: {output_path}")
            
        except Exception as e:
            logger.error(f"Error writing predictions to HDFS: {e}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
    
    def stop(self):
        """Stop the prediction service"""
        logger.info("Stopping prediction service...")
        self.running = False
    
    def _cleanup(self):
        """Cleanup resources"""
        try:
            if self.kafka_consumer:
                self.kafka_consumer.close()
            if self.kafka_producer:
                self.kafka_producer.close()
            if self.spark:
                self.spark.stop()
            logger.info("✓ Cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

def load_config(config_path: str = None) -> PredictionServiceConfig:
    """Load configuration from file or use defaults"""
    config = PredictionServiceConfig()
    
    if config_path and Path(config_path).exists():
        try:
            with open(config_path, 'r') as f:
                config_data = json.load(f)
            
            # Update config with loaded values
            for key, value in config_data.items():
                if hasattr(config, key):
                    setattr(config, key, value)
            
            logger.info(f"Configuration loaded from {config_path}")
        except Exception as e:
            logger.warning(f"Failed to load config from {config_path}: {e}")
    
    return config

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Traffic Prediction Service')
    parser.add_argument('--config', help='Configuration file path')
    parser.add_argument('--kafka-broker', default='localhost:9094', help='Kafka broker address')
    parser.add_argument('--hdfs-namenode', default='hdfs://localhost:9001', help='HDFS NameNode URL')
    
    args = parser.parse_args()
    
    try:
        # Load configuration
        config = load_config(args.config)
        
        # Override with command line arguments
        if args.kafka_broker:
            config.kafka_bootstrap_servers = args.kafka_broker
        if args.hdfs_namenode:
            config.hdfs_namenode = args.hdfs_namenode
            config.model_path = f"{args.hdfs_namenode}/traffic/models"
            config.predictions_output_path = f"{args.hdfs_namenode}/traffic/predictions"
        
        # Create and run service
        service = TrafficPredictionService(config)
        
        if service.initialize():
            service.run()
        else:
            logger.error("Failed to initialize prediction service")
            return 1
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("Service interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"Service failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
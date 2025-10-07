"""
Traffic Prediction Service

Comprehensive batch prediction service that:
- Loads latest ML models from HDFS
- Reads recent traffic data from PostgreSQL
- Generates predictions for multiple horizons
- Stores predictions back to PostgreSQL
- Provides monitoring and performance tracking
"""

import os
import sys
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import traceback

import pandas as pd
import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor
import psycopg2.pool

# Add ML module to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'ml'))
from model_persistence import ModelPersistenceManager

# SAFETY-CRITICAL: Import safety validator
from safety_validator import PredictionSafetyValidator, validate_predictions_safe

# Spark integration
from pyspark.sql import SparkSession
from pyspark import SparkContext

logger = logging.getLogger(__name__)


class PredictionServiceConfig:
    """Configuration management for prediction service"""
    
    def __init__(self, config_path: str = "config/prediction_service_config.json"):
        self.config_path = config_path
        self.config = self._load_config()
        self._validate_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            raise ValueError(f"Failed to load configuration from {self.config_path}: {str(e)}")
    
    def _validate_config(self):
        """Validate configuration completeness"""
        required_sections = [
            'prediction_service', 'data_sources', 'prediction_settings',
            'model_settings', 'scheduling', 'monitoring', 'logging'
        ]
        
        for section in required_sections:
            if section not in self.config:
                raise ValueError(f"Missing required configuration section: {section}")
    
    @property
    def postgres_config(self) -> Dict[str, Any]:
        return self.config['data_sources']['postgresql']
    
    @property
    def hdfs_config(self) -> Dict[str, Any]:
        return self.config['data_sources']['hdfs']
    
    @property
    def prediction_settings(self) -> Dict[str, Any]:
        return self.config['prediction_settings']
    
    @property
    def model_settings(self) -> Dict[str, Any]:
        return self.config['model_settings']
    
    @property
    def monitoring_settings(self) -> Dict[str, Any]:
        return self.config['monitoring']
    
    @property
    def spark_config(self) -> Dict[str, Any]:
        return self.config.get('spark', {})


class DatabaseManager:
    """PostgreSQL database connection and query management"""
    
    def __init__(self, config: PredictionServiceConfig):
        self.config = config
        self.pg_config = config.postgres_config
        self.connection_pool = None
        self._initialize_connection_pool()
    
    def _initialize_connection_pool(self):
        """Initialize PostgreSQL connection pool"""
        try:
            self.connection_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=self.pg_config.get('connection_pool_size', 10),
                host=self.pg_config['host'],
                port=self.pg_config['port'],
                database=self.pg_config['database'],
                user=self.pg_config['user'],
                password=os.getenv('POSTGRES_PASSWORD', self.pg_config.get('password', '')),
                connect_timeout=self.pg_config.get('connection_timeout', 30)
            )
            logger.info("PostgreSQL connection pool initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL connection pool: {str(e)}")
            raise
    
    def get_connection(self):
        """Get connection from pool"""
        return self.connection_pool.getconn()
    
    def return_connection(self, conn):
        """Return connection to pool"""
        self.connection_pool.putconn(conn)
    
    def execute_query(self, query: str, params: Optional[Tuple] = None) -> List[Dict]:
        """Execute query and return results"""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                if cursor.description:
                    return [dict(row) for row in cursor.fetchall()]
                return []
        except Exception as e:
            logger.error(f"Database query failed: {str(e)}")
            raise
        finally:
            if conn:
                self.return_connection(conn)
    
    def execute_many(self, query: str, data: List[Tuple]) -> int:
        """Execute many statements and return affected rows"""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cursor:
                cursor.executemany(query, data)
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Database bulk operation failed: {str(e)}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                self.return_connection(conn)
    
    def get_recent_traffic_data(self, hours_back: int = 24) -> pd.DataFrame:
        """Get recent traffic data for prediction"""
        query = """
        SELECT 
            s.sensor_id,
            s.location,
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
        WHERE tr.timestamp >= %s
          AND s.status = 'active'
          AND tr.quality_score >= 0.7
        ORDER BY s.sensor_id, tr.timestamp DESC
        """
        
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        results = self.execute_query(query, (cutoff_time,))
        
        if not results:
            logger.warning(f"No traffic data found for last {hours_back} hours")
            return pd.DataFrame()
        
        df = pd.DataFrame(results)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        logger.info(f"Retrieved {len(df)} traffic readings from {len(df['sensor_id'].unique())} sensors")
        return df
    
    def get_active_sensors(self) -> List[Dict]:
        """Get list of active sensors"""
        query = """
        SELECT sensor_id, road_name, road_type, direction, 
               ST_X(location::geometry) as longitude,
               ST_Y(location::geometry) as latitude
        FROM traffic.sensors 
        WHERE status = 'active'
        """
        return self.execute_query(query)
    
    def store_predictions(self, predictions: List[Dict]) -> int:
        """Store predictions in database"""
        if not predictions:
            return 0
        
        # Get sensor IDs mapping
        sensor_mapping = {}
        sensor_query = "SELECT id, sensor_id FROM traffic.sensors WHERE sensor_id = ANY(%s)"
        sensor_ids = list(set(pred['sensor_id'] for pred in predictions))
        
        sensor_results = self.execute_query(sensor_query, (sensor_ids,))
        for row in sensor_results:
            sensor_mapping[row['sensor_id']] = row['id']
        
        # Prepare prediction data
        prediction_data = []
        for pred in predictions:
            if pred['sensor_id'] not in sensor_mapping:
                logger.warning(f"Sensor {pred['sensor_id']} not found in database, skipping prediction")
                continue
            
            prediction_data.append((
                sensor_mapping[pred['sensor_id']],  # sensor_id (UUID)
                pred['prediction_timestamp'],       # prediction_timestamp
                pred['horizon_minutes'],            # horizon_minutes
                pred.get('predicted_speed'),        # predicted_speed
                pred.get('predicted_volume'),       # predicted_volume
                pred.get('predicted_travel_time'),  # predicted_travel_time
                pred.get('confidence_score', 0.5),  # confidence_score
                pred.get('model_name', 'unknown'),  # model_name
                pred.get('model_version', '1.0'),   # model_version
                json.dumps(pred.get('features_used', {})),  # features_used
                pred.get('prediction_interval_lower'),      # prediction_interval_lower
                pred.get('prediction_interval_upper')       # prediction_interval_upper
            ))
        
        if not prediction_data:
            logger.warning("No valid predictions to store")
            return 0
        
        # Insert predictions
        insert_query = """
        INSERT INTO traffic.predictions (
            sensor_id, prediction_timestamp, horizon_minutes,
            predicted_speed, predicted_volume, predicted_travel_time,
            confidence_score, model_name, model_version, features_used,
            prediction_interval_lower, prediction_interval_upper
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        rows_affected = self.execute_many(insert_query, prediction_data)
        logger.info(f"Stored {rows_affected} predictions in database")
        return rows_affected
    
    def cleanup_old_predictions(self, days_to_keep: int = 30) -> int:
        """Clean up old predictions"""
        query = """
        DELETE FROM traffic.predictions 
        WHERE created_at < %s
        """
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cursor:
                cursor.execute(query, (cutoff_date,))
                conn.commit()
                rows_deleted = cursor.rowcount
                logger.info(f"Cleaned up {rows_deleted} old predictions")
                return rows_deleted
        except Exception as e:
            logger.error(f"Failed to cleanup old predictions: {str(e)}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                self.return_connection(conn)
    
    def close(self):
        """Close connection pool"""
        if self.connection_pool:
            self.connection_pool.closeall()
            logger.info("Database connection pool closed")


class ModelManager:
    """Manages ML model loading and caching"""
    
    def __init__(self, config: PredictionServiceConfig, spark_session: SparkSession):
        self.config = config
        self.spark = spark_session
        self.model_settings = config.model_settings
        self.hdfs_config = config.hdfs_config
        
        # Initialize model persistence manager
        self.model_persistence = ModelPersistenceManager(
            self._create_ml_config(), 
            spark_session
        )
        
        # Model cache
        self.model_cache = {}
        self.cache_timestamps = {}
        self.cache_ttl_minutes = self.model_settings.get('model_cache_ttl_minutes', 120)
    
    def _create_ml_config(self):
        """Create ML config for model persistence"""
        # Create a minimal ML config object
        class MLConfig:
            def __init__(self):
                self.persistence = type('obj', (object,), {
                    'model_registry_path': 'model_registry',
                    'hdfs_model_path': self.hdfs_config['model_base_path']
                })()
        
        return MLConfig()
    
    def get_model(self, model_name: Optional[str] = None, 
                  model_version: Optional[str] = None) -> Tuple[Any, Dict]:
        """Get model from cache or load from HDFS"""
        model_name = model_name or self.model_settings['default_model_name']
        model_version = model_version or self.model_settings['model_version']
        
        cache_key = f"{model_name}_{model_version}"
        
        # Check cache validity
        if self._is_cache_valid(cache_key):
            logger.debug(f"Using cached model: {cache_key}")
            return self.model_cache[cache_key]
        
        # Load model from HDFS
        try:
            logger.info(f"Loading model from HDFS: {model_name} v{model_version}")
            model, metadata = self.model_persistence.load_model(model_name, model_version)
            
            # Update cache
            self.model_cache[cache_key] = (model, metadata)
            self.cache_timestamps[cache_key] = datetime.now()
            
            logger.info(f"Model loaded successfully: {model_name} v{model_version}")
            return model, metadata
            
        except Exception as e:
            logger.error(f"Failed to load model {model_name} v{model_version}: {str(e)}")
            
            # Try fallback models
            for fallback_model in self.model_settings.get('fallback_models', []):
                if fallback_model != model_name:
                    try:
                        logger.info(f"Trying fallback model: {fallback_model}")
                        return self.get_model(fallback_model, model_version)
                    except Exception as fallback_error:
                        logger.warning(f"Fallback model {fallback_model} also failed: {str(fallback_error)}")
            
            raise Exception(f"No available models could be loaded. Last error: {str(e)}")
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached model is still valid"""
        if cache_key not in self.model_cache:
            return False
        
        cache_time = self.cache_timestamps.get(cache_key)
        if not cache_time:
            return False
        
        age_minutes = (datetime.now() - cache_time).total_seconds() / 60
        return age_minutes < self.cache_ttl_minutes
    
    def clear_cache(self):
        """Clear model cache"""
        self.model_cache.clear()
        self.cache_timestamps.clear()
        logger.info("Model cache cleared")


class FeatureProcessor:
    """Processes traffic data into features for ML models"""
    
    def __init__(self, config: PredictionServiceConfig):
        self.config = config
    
    def prepare_features(self, traffic_data: pd.DataFrame) -> pd.DataFrame:
        """Prepare features from traffic data"""
        if traffic_data.empty:
            return pd.DataFrame()
        
        logger.info(f"Preparing features from {len(traffic_data)} traffic records")
        
        # Group by sensor for feature engineering
        features_list = []
        
        for sensor_id, sensor_data in traffic_data.groupby('sensor_id'):
            try:
                sensor_features = self._create_sensor_features(sensor_id, sensor_data)
                features_list.append(sensor_features)
            except Exception as e:
                logger.warning(f"Failed to create features for sensor {sensor_id}: {str(e)}")
        
        if not features_list:
            logger.warning("No features could be created from traffic data")
            return pd.DataFrame()
        
        features_df = pd.DataFrame(features_list)
        logger.info(f"Created {len(features_df)} feature records with {len(features_df.columns)} features")
        
        return features_df
    
    def _create_sensor_features(self, sensor_id: str, sensor_data: pd.DataFrame) -> Dict:
        """Create features for a single sensor"""
        # Sort by timestamp
        sensor_data = sensor_data.sort_values('timestamp')
        
        # Base features
        features = {
            'sensor_id': sensor_id,
            'road_name': sensor_data.iloc[0]['road_name'],
            'road_type': sensor_data.iloc[0]['road_type'],
            'direction': sensor_data.iloc[0]['direction'],
            'lane_count': sensor_data.iloc[0]['lane_count'],
            'speed_limit': sensor_data.iloc[0]['speed_limit']
        }
        
        # Recent measurements (last few hours)
        recent_data = sensor_data.head(10)  # Most recent 10 readings
        
        if not recent_data.empty:
            # Current conditions
            latest = recent_data.iloc[0]
            features.update({
                'current_speed': latest['speed'],
                'current_volume': latest['volume'],
                'current_occupancy': latest['occupancy'],
                'current_temperature': latest.get('temperature_c'),
                'current_humidity': latest.get('humidity_percent'),
                'weather_condition': latest.get('weather_condition', 'unknown'),
                'quality_score': latest['quality_score'],
                'timestamp': latest['timestamp']
            })
            
            # Statistical features from recent data
            features.update({
                'avg_speed_1h': recent_data['speed'].mean(),
                'std_speed_1h': recent_data['speed'].std(),
                'min_speed_1h': recent_data['speed'].min(),
                'max_speed_1h': recent_data['speed'].max(),
                'avg_volume_1h': recent_data['volume'].mean(),
                'std_volume_1h': recent_data['volume'].std(),
                'avg_occupancy_1h': recent_data['occupancy'].mean(),
                'std_occupancy_1h': recent_data['occupancy'].std()
            })
            
            # Time-based features
            features.update({
                'hour_of_day': latest['timestamp'].hour,
                'day_of_week': latest['timestamp'].weekday(),
                'is_weekend': latest['timestamp'].weekday() >= 5,
                'is_rush_hour': self._is_rush_hour(latest['timestamp']),
                'month': latest['timestamp'].month
            })
            
            # Trend features (if we have enough data)
            if len(recent_data) >= 3:
                speed_trend = np.polyfit(range(len(recent_data)), recent_data['speed'][::-1], 1)[0]
                volume_trend = np.polyfit(range(len(recent_data)), recent_data['volume'][::-1], 1)[0]
                
                features.update({
                    'speed_trend': speed_trend,
                    'volume_trend': volume_trend,
                    'speed_change_rate': (recent_data.iloc[0]['speed'] - recent_data.iloc[-1]['speed']) / len(recent_data),
                    'volume_change_rate': (recent_data.iloc[0]['volume'] - recent_data.iloc[-1]['volume']) / len(recent_data)
                })
        
        # Fill missing values with defaults
        for key, value in features.items():
            if pd.isna(value) or value is None:
                if key.endswith('_speed') or key == 'current_speed':
                    features[key] = 50.0  # Default speed
                elif key.endswith('_volume') or key == 'current_volume':
                    features[key] = 1000  # Default volume
                elif key.endswith('_occupancy') or key == 'current_occupancy':
                    features[key] = 50.0  # Default occupancy
                else:
                    features[key] = 0.0
        
        return features
    
    def _is_rush_hour(self, timestamp: datetime) -> bool:
        """Determine if timestamp is during rush hour"""
        hour = timestamp.hour
        weekday = timestamp.weekday()
        
        # Rush hours: 7-9 AM and 5-7 PM on weekdays
        if weekday < 5:  # Monday to Friday
            return (7 <= hour <= 9) or (17 <= hour <= 19)
        
        return False


class PredictionGenerator:
    """Generates predictions using ML models"""
    
    def __init__(self, config: PredictionServiceConfig, model_manager: ModelManager):
        self.config = config
        self.model_manager = model_manager
        self.prediction_settings = config.prediction_settings
        
        # SAFETY-CRITICAL: Initialize safety validator
        self.safety_validator = PredictionSafetyValidator()
        logger.info("Safety validator initialized for prediction bounds checking")
    
    def generate_predictions(self, features: pd.DataFrame) -> List[Dict]:
        """Generate predictions for all sensors and horizons"""
        if features.empty:
            logger.warning("No features provided for prediction")
            return []
        
        logger.info(f"Generating predictions for {len(features)} sensors")
        
        # Load model
        try:
            model, metadata = self.model_manager.get_model()
            model_name = metadata.get('model_name', 'unknown')
            model_version = metadata.get('version', '1.0')
            
            logger.info(f"Using model: {model_name} v{model_version}")
            
        except Exception as e:
            logger.error(f"Failed to load model for prediction: {str(e)}")
            return []
        
        # Generate predictions for each horizon
        all_predictions = []
        horizons = self.prediction_settings['horizon_minutes']
        
        for horizon in horizons:
            try:
                horizon_predictions = self._generate_horizon_predictions(
                    features, model, metadata, horizon
                )
                all_predictions.extend(horizon_predictions)
                logger.debug(f"Generated {len(horizon_predictions)} predictions for {horizon}-minute horizon")
                
            except Exception as e:
                logger.error(f"Failed to generate predictions for {horizon}-minute horizon: {str(e)}")
        
        # SAFETY-CRITICAL: Validate all predictions before returning
        logger.info(f"Validating {len(all_predictions)} predictions for safety bounds")
        validated_predictions, validation_summary = self.safety_validator.validate_batch(all_predictions)
        
        # Log validation results
        logger.info(
            f"Validation complete: {validation_summary['valid']}/{validation_summary['total']} valid, "
            f"{validation_summary['warnings']} warnings, {validation_summary['invalid']} invalid"
        )
        
        if validation_summary['invalid'] > 0:
            logger.error(
                f"WARNING: {validation_summary['invalid']} predictions failed safety validation "
                f"and were corrected/removed"
            )
        
        logger.info(f"Generated and validated total of {len(validated_predictions)} predictions")
        return validated_predictions
    
    def _generate_horizon_predictions(self, features: pd.DataFrame, model: Any, 
                                    metadata: Dict, horizon_minutes: int) -> List[Dict]:
        """Generate predictions for a specific horizon"""
        predictions = []
        prediction_timestamp = datetime.now()
        target_timestamp = prediction_timestamp + timedelta(minutes=horizon_minutes)
        
        # Prepare feature columns (exclude non-feature columns)
        non_feature_cols = ['sensor_id', 'road_name', 'road_type', 'direction', 'timestamp']
        feature_cols = [col for col in features.columns if col not in non_feature_cols]
        
        if not feature_cols:
            logger.warning("No feature columns found for prediction")
            return []
        
        # Get features for prediction
        X = features[feature_cols].fillna(0)
        
        try:
            # Make predictions
            if hasattr(model, 'predict'):
                predictions_raw = model.predict(X)
            else:
                logger.error("Model does not have predict method")
                return []
            
            # Calculate confidence scores (simplified approach)
            confidence_scores = self._calculate_confidence_scores(X, model, metadata)
            
            # Create prediction records
            for idx, (_, row) in enumerate(features.iterrows()):
                if idx >= len(predictions_raw):
                    break
                
                # Extract prediction values (assuming multi-output: speed, volume)
                pred_values = predictions_raw[idx]
                if isinstance(pred_values, (list, np.ndarray)):
                    predicted_speed = float(pred_values[0]) if len(pred_values) > 0 else None
                    predicted_volume = float(pred_values[1]) if len(pred_values) > 1 else None
                else:
                    # Single output assumed to be speed
                    predicted_speed = float(pred_values)
                    predicted_volume = None
                
                # Calculate travel time if we have speed
                predicted_travel_time = None
                if predicted_speed and predicted_speed > 0:
                    # Assume 1 mile segment for travel time calculation
                    predicted_travel_time = int((1.0 / predicted_speed) * 3600)  # seconds
                
                # Create prediction record
                prediction = {
                    'sensor_id': row['sensor_id'],
                    'prediction_timestamp': prediction_timestamp,
                    'horizon_minutes': horizon_minutes,
                    'predicted_speed': predicted_speed,
                    'predicted_volume': predicted_volume,
                    'predicted_travel_time': predicted_travel_time,
                    'confidence_score': confidence_scores[idx] if idx < len(confidence_scores) else 0.5,
                    'model_name': metadata.get('model_name', 'unknown'),
                    'model_version': metadata.get('version', '1.0'),
                    'features_used': feature_cols,
                    'prediction_interval_lower': None,  # Could be calculated with uncertainty quantification
                    'prediction_interval_upper': None,
                    'target_timestamp': target_timestamp
                }
                
                predictions.append(prediction)
        
        except Exception as e:
            logger.error(f"Prediction generation failed: {str(e)}")
            logger.error(f"Feature shape: {X.shape}, Model type: {type(model)}")
            raise
        
        return predictions
    
    def _calculate_confidence_scores(self, X: pd.DataFrame, model: Any, 
                                   metadata: Dict) -> List[float]:
        """Calculate confidence scores for predictions"""
        try:
            # Simple confidence based on feature quality and model uncertainty
            base_confidence = 0.7
            
            # Adjust based on feature completeness
            completeness_scores = []
            for _, row in X.iterrows():
                non_null_ratio = (row.notna()).sum() / len(row)
                completeness_scores.append(min(1.0, base_confidence + (non_null_ratio * 0.3)))
            
            return completeness_scores
            
        except Exception as e:
            logger.warning(f"Failed to calculate confidence scores: {str(e)}")
            return [0.5] * len(X)  # Default confidence


class MetricsCollector:
    """Collects and stores performance metrics"""
    
    def __init__(self, config: PredictionServiceConfig, db_manager: DatabaseManager):
        self.config = config
        self.db_manager = db_manager
        self.monitoring_settings = config.monitoring_settings
    
    def record_prediction_metrics(self, predictions: List[Dict], 
                                processing_time: float, error_count: int = 0):
        """Record metrics for prediction batch"""
        if not self.monitoring_settings.get('enable_metrics', True):
            return
        
        try:
            metrics = {
                'timestamp': datetime.now(),
                'prediction_count': len(predictions),
                'processing_time_seconds': processing_time,
                'error_count': error_count,
                'success_rate': (len(predictions) - error_count) / max(len(predictions), 1),
                'performance_threshold_met': processing_time <= self.monitoring_settings.get('performance_threshold_seconds', 300)
            }
            
            # Log metrics
            logger.info(f"Prediction Metrics: {json.dumps(metrics, default=str, indent=2)}")
            
            # Store in database if table exists
            self._store_metrics_to_db(metrics)
            
        except Exception as e:
            logger.error(f"Failed to record prediction metrics: {str(e)}")
    
    def _store_metrics_to_db(self, metrics: Dict):
        """Store metrics to database"""
        # This would require a metrics table - for now just log
        pass


class TrafficPredictionService:
    """Main traffic prediction service"""
    
    def __init__(self, config_path: str = "config/prediction_service_config.json"):
        """Initialize the prediction service"""
        
        # Load configuration
        self.config = PredictionServiceConfig(config_path)
        
        # Setup logging
        self._setup_logging()
        
        # Initialize Spark session
        self.spark = self._create_spark_session()
        
        # Initialize components
        self.db_manager = DatabaseManager(self.config)
        self.model_manager = ModelManager(self.config, self.spark)
        self.feature_processor = FeatureProcessor(self.config)
        self.prediction_generator = PredictionGenerator(self.config, self.model_manager)
        self.metrics_collector = MetricsCollector(self.config, self.db_manager)
        
        logger.info("Traffic Prediction Service initialized successfully")
    
    def _setup_logging(self):
        """Setup logging configuration"""
        log_config = self.config.config['logging']
        
        # Create logs directory
        log_dir = Path(log_config['log_file_path']).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure logging
        logging.basicConfig(
            level=getattr(logging, log_config['level']),
            format=log_config['log_format'],
            handlers=[
                logging.FileHandler(log_config['log_file_path']),
                logging.StreamHandler()
            ]
        )
    
    def _create_spark_session(self) -> SparkSession:
        """Create Spark session"""
        spark_config = self.config.spark_config
        
        builder = SparkSession.builder.appName(spark_config.get('app_name', 'TrafficPredictionService'))
        
        for key, value in spark_config.get('config', {}).items():
            builder = builder.config(key, value)
        
        return builder.getOrCreate()
    
    def run_batch_prediction(self) -> Dict[str, Any]:
        """Run a complete batch prediction cycle"""
        logger.info("Starting batch prediction cycle")
        start_time = time.time()
        
        try:
            # Step 1: Load recent traffic data from PostgreSQL
            logger.info("Loading recent traffic data...")
            traffic_data = self.db_manager.get_recent_traffic_data(hours_back=24)
            
            if traffic_data.empty:
                logger.warning("No traffic data available for prediction")
                return {
                    "status": "skipped",
                    "reason": "No traffic data available",
                    "processing_time": time.time() - start_time
                }
            
            # Step 2: Prepare features
            logger.info("Preparing features for prediction...")
            features = self.feature_processor.prepare_features(traffic_data)
            
            if features.empty:
                logger.warning("No features could be prepared")
                return {
                    "status": "failed",
                    "reason": "Feature preparation failed",
                    "processing_time": time.time() - start_time
                }
            
            # Step 3: Generate predictions
            logger.info("Generating predictions...")
            predictions = self.prediction_generator.generate_predictions(features)
            
            if not predictions:
                logger.warning("No predictions could be generated")
                return {
                    "status": "failed",
                    "reason": "Prediction generation failed",
                    "processing_time": time.time() - start_time
                }
            
            # Step 4: Store predictions in PostgreSQL
            logger.info("Storing predictions...")
            stored_count = self.db_manager.store_predictions(predictions)
            
            # Step 5: Record metrics
            processing_time = time.time() - start_time
            self.metrics_collector.record_prediction_metrics(predictions, processing_time)
            
            # Step 6: Cleanup old predictions
            if self.config.config['scheduling'].get('cleanup_interval_hours', 24) <= 1:
                cleanup_count = self.db_manager.cleanup_old_predictions(
                    self.config.config['scheduling'].get('data_retention_days', 30)
                )
                logger.info(f"Cleaned up {cleanup_count} old predictions")
            
            result = {
                "status": "completed",
                "predictions_generated": len(predictions),
                "predictions_stored": stored_count,
                "sensors_processed": len(features),
                "processing_time": processing_time,
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Batch prediction completed successfully: {json.dumps(result, indent=2)}")
            return result
            
        except Exception as e:
            error_msg = f"Batch prediction failed: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            return {
                "status": "failed",
                "error": error_msg,
                "processing_time": time.time() - start_time,
                "timestamp": datetime.now().isoformat()
            }
    
    def cleanup(self):
        """Cleanup resources"""
        try:
            if hasattr(self, 'db_manager'):
                self.db_manager.close()
            
            if hasattr(self, 'spark'):
                self.spark.stop()
            
            logger.info("Traffic Prediction Service cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")


def main():
    """Main execution function"""
    service = None
    
    try:
        # Initialize service
        service = TrafficPredictionService()
        
        # Run batch prediction
        result = service.run_batch_prediction()
        
        # Print results
        print("\n" + "="*60)
        print("BATCH PREDICTION RESULTS")
        print("="*60)
        print(json.dumps(result, indent=2))
        print("="*60)
        
        # Exit code based on result
        if result.get('status') == 'completed':
            exit(0)
        else:
            exit(1)
    
    except Exception as e:
        print(f"Fatal error: {str(e)}", file=sys.stderr)
        exit(1)
    
    finally:
        if service:
            service.cleanup()


if __name__ == "__main__":
    main()
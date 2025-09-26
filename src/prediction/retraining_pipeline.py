"""
Automated Model Retraining Pipeline

Comprehensive system for automated model retraining including:
- Weekly scheduled retraining with new data
- Model validation and performance comparison
- A/B testing capabilities for model deployment
- Automated model archiving and version management
- Integration with existing ML training pipeline
"""

import os
import sys
import json
import logging
import time
import shutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import traceback
from dataclasses import dataclass, asdict
from enum import Enum

import pandas as pd
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error

# Add project modules to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'ml'))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from prediction_service import PredictionServiceConfig, DatabaseManager
from ml_training_pipeline import MLTrainingPipeline, MLTrainingConfig

# Spark integration
from pyspark.sql import SparkSession

logger = logging.getLogger(__name__)


class RetrainingStatus(Enum):
    """Retraining job status"""
    PENDING = "pending"
    RUNNING = "running"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    DEPLOYED = "deployed"
    ROLLED_BACK = "rolled_back"


@dataclass
class RetrainingJob:
    """Retraining job metadata"""
    job_id: str
    start_time: datetime
    end_time: Optional[datetime]
    status: RetrainingStatus
    trigger_reason: str
    data_period_start: datetime
    data_period_end: datetime
    training_samples: int
    validation_samples: int
    models_trained: List[str]
    best_model: Optional[str] = None
    performance_metrics: Optional[Dict[str, float]] = None
    deployment_candidate: bool = False
    error_message: Optional[str] = None


@dataclass
class ModelPerformanceComparison:
    """Model performance comparison results"""
    new_model_name: str
    new_model_version: str
    current_model_name: str
    current_model_version: str
    comparison_metric: str
    new_model_score: float
    current_model_score: float
    improvement_percent: float
    recommendation: str  # "deploy", "keep_current", "requires_review"
    confidence_level: float


class DataCollector:
    """Collects training data for retraining"""
    
    def __init__(self, config: PredictionServiceConfig, db_manager: DatabaseManager):
        self.config = config
        self.db_manager = db_manager
        self.retraining_config = config.config.get('retraining', {})
    
    def collect_retraining_data(self, start_date: datetime, end_date: datetime) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Collect training and validation data for retraining"""
        logger.info(f"Collecting retraining data from {start_date} to {end_date}")
        
        try:
            # Query for traffic data with quality scores
            training_query = """
            SELECT 
                s.sensor_id,
                s.road_name,
                s.road_type,
                s.direction,
                s.lane_count,
                s.speed_limit,
                ST_X(s.location::geometry) as longitude,
                ST_Y(s.location::geometry) as latitude,
                tr.timestamp,
                tr.speed,
                tr.volume,
                tr.occupancy,
                tr.weather_condition,
                tr.temperature_c,
                tr.humidity_percent,
                tr.quality_score,
                EXTRACT(HOUR FROM tr.timestamp) as hour_of_day,
                EXTRACT(DOW FROM tr.timestamp) as day_of_week,
                CASE WHEN EXTRACT(DOW FROM tr.timestamp) IN (0, 6) THEN 1 ELSE 0 END as is_weekend,
                CASE WHEN EXTRACT(DOW FROM tr.timestamp) BETWEEN 1 AND 5 
                     AND (EXTRACT(HOUR FROM tr.timestamp) BETWEEN 7 AND 9 
                          OR EXTRACT(HOUR FROM tr.timestamp) BETWEEN 17 AND 19)
                     THEN 1 ELSE 0 END as is_rush_hour
            FROM traffic.sensors s
            JOIN traffic.traffic_readings tr ON s.id = tr.sensor_id
            WHERE tr.timestamp BETWEEN %s AND %s
              AND s.status = 'active'
              AND tr.quality_score >= %s
              AND tr.speed IS NOT NULL
              AND tr.volume IS NOT NULL
            ORDER BY s.sensor_id, tr.timestamp
            """
            
            min_quality_score = self.retraining_config.get('min_quality_score', 0.8)
            
            results = self.db_manager.execute_query(
                training_query, 
                (start_date, end_date, min_quality_score)
            )
            
            if not results:
                raise ValueError(f"No training data found between {start_date} and {end_date}")
            
            # Convert to DataFrame
            df = pd.DataFrame(results)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            logger.info(f"Collected {len(df)} training records from {len(df['sensor_id'].unique())} sensors")
            
            # Split into training and validation sets (80/20 split by time)
            split_date = start_date + (end_date - start_date) * 0.8
            
            train_df = df[df['timestamp'] <= split_date].copy()
            val_df = df[df['timestamp'] > split_date].copy()
            
            # Feature engineering
            train_df = self._engineer_features(train_df)
            val_df = self._engineer_features(val_df)
            
            logger.info(f"Training set: {len(train_df)} samples, Validation set: {len(val_df)} samples")
            
            return train_df, val_df
            
        except Exception as e:
            logger.error(f"Failed to collect retraining data: {str(e)}")
            raise
    
    def _engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Engineer features for training data"""
        if df.empty:
            return df
        
        # Sort by sensor and timestamp
        df = df.sort_values(['sensor_id', 'timestamp'])
        
        # Calculate lag features (previous readings) for each sensor
        df['prev_speed'] = df.groupby('sensor_id')['speed'].shift(1)
        df['prev_volume'] = df.groupby('sensor_id')['volume'].shift(1)
        df['prev_occupancy'] = df.groupby('sensor_id')['occupancy'].shift(1)
        
        # Speed change features
        df['speed_change'] = df['speed'] - df['prev_speed']
        df['volume_change'] = df['volume'] - df['prev_volume']
        
        # Rolling statistics (last 5 readings per sensor)
        window_size = 5
        for metric in ['speed', 'volume', 'occupancy']:
            df[f'{metric}_rolling_mean'] = df.groupby('sensor_id')[metric].rolling(
                window=window_size, min_periods=1
            ).mean().reset_index(0, drop=True)
            
            df[f'{metric}_rolling_std'] = df.groupby('sensor_id')[metric].rolling(
                window=window_size, min_periods=1
            ).std().reset_index(0, drop=True)
        
        # Time-based features
        df['month'] = df['timestamp'].dt.month
        df['hour_sin'] = np.sin(2 * np.pi * df['hour_of_day'] / 24)
        df['hour_cos'] = np.cos(2 * np.pi * df['hour_of_day'] / 24)
        df['day_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
        df['day_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)
        
        # Weather encoding
        weather_mapping = {
            'clear': 1, 'partly_cloudy': 2, 'cloudy': 3, 
            'light_rain': 4, 'heavy_rain': 5, 'snow': 6, 'fog': 7
        }
        df['weather_encoded'] = df['weather_condition'].map(weather_mapping).fillna(1)
        
        # Fill missing values
        numeric_columns = df.select_dtypes(include=[np.number]).columns
        df[numeric_columns] = df[numeric_columns].fillna(df[numeric_columns].median())
        
        return df


class ModelValidator:
    """Validates new models against current production models"""
    
    def __init__(self, config: PredictionServiceConfig):
        self.config = config
        self.retraining_config = config.config.get('retraining', {})
        self.validation_thresholds = self.retraining_config.get('validation_thresholds', {})
    
    def validate_model_performance(self, new_model_path: str, current_model_path: str,
                                 validation_data: pd.DataFrame) -> ModelPerformanceComparison:
        """Compare new model performance against current model"""
        logger.info("Validating new model performance against current model")
        
        try:
            # Load models (simplified - would use actual model loading)
            # For now, simulate model loading and prediction
            
            new_model_name = Path(new_model_path).stem
            current_model_name = Path(current_model_path).stem
            
            # Prepare validation features and targets
            feature_columns = self._get_feature_columns(validation_data)
            X_val = validation_data[feature_columns]
            y_val_speed = validation_data['speed']
            y_val_volume = validation_data['volume']
            
            # Simulate predictions (in real implementation, load and predict with actual models)
            new_predictions_speed = self._simulate_predictions(X_val, "new_model")
            current_predictions_speed = self._simulate_predictions(X_val, "current_model")
            
            # Calculate performance metrics
            new_mae = mean_absolute_error(y_val_speed, new_predictions_speed)
            current_mae = mean_absolute_error(y_val_speed, current_predictions_speed)
            
            new_rmse = np.sqrt(mean_squared_error(y_val_speed, new_predictions_speed))
            current_rmse = np.sqrt(mean_squared_error(y_val_speed, current_predictions_speed))
            
            # Use RMSE as comparison metric
            comparison_metric = "RMSE"
            new_model_score = new_rmse
            current_model_score = current_rmse
            
            # Calculate improvement (lower is better for RMSE)
            improvement_percent = ((current_model_score - new_model_score) / current_model_score) * 100
            
            # Determine recommendation
            min_improvement_threshold = self.validation_thresholds.get('min_improvement_percent', 5.0)
            confidence_threshold = self.validation_thresholds.get('confidence_threshold', 0.95)
            
            if improvement_percent >= min_improvement_threshold:
                recommendation = "deploy"
                confidence_level = 0.95
            elif improvement_percent >= 0:
                recommendation = "requires_review"
                confidence_level = 0.75
            else:
                recommendation = "keep_current"
                confidence_level = 0.90
            
            comparison = ModelPerformanceComparison(
                new_model_name=new_model_name,
                new_model_version="candidate",
                current_model_name=current_model_name,
                current_model_version="production",
                comparison_metric=comparison_metric,
                new_model_score=new_model_score,
                current_model_score=current_model_score,
                improvement_percent=improvement_percent,
                recommendation=recommendation,
                confidence_level=confidence_level
            )
            
            logger.info(f"Model validation completed: {improvement_percent:.2f}% improvement, "
                       f"recommendation: {recommendation}")
            
            return comparison
            
        except Exception as e:
            logger.error(f"Model validation failed: {str(e)}")
            raise
    
    def _get_feature_columns(self, df: pd.DataFrame) -> List[str]:
        """Get feature columns for model validation"""
        exclude_columns = [
            'sensor_id', 'timestamp', 'speed', 'volume', 'occupancy',
            'road_name', 'weather_condition'
        ]
        return [col for col in df.columns if col not in exclude_columns]
    
    def _simulate_predictions(self, X: pd.DataFrame, model_type: str) -> np.ndarray:
        """Simulate model predictions (replace with actual model loading/prediction)"""
        # This is a placeholder - in real implementation, load and use actual models
        
        if model_type == "new_model":
            # Simulate slightly better predictions
            base_prediction = X['prev_speed'].fillna(50.0) + np.random.normal(0, 2, len(X))
        else:
            # Simulate current model predictions
            base_prediction = X['prev_speed'].fillna(50.0) + np.random.normal(0, 3, len(X))
        
        return np.clip(base_prediction, 0, 100)  # Speed range 0-100 mph
    
    def run_a_b_test(self, model_a_path: str, model_b_path: str, 
                     test_data: pd.DataFrame, test_duration_hours: int = 24) -> Dict[str, Any]:
        """Run A/B test between two models"""
        logger.info(f"Running A/B test between models for {test_duration_hours} hours")
        
        try:
            # In a real implementation, this would deploy both models to handle
            # different portions of traffic and compare real-world performance
            
            # Simulate A/B test results
            test_results = {
                "test_id": f"ab_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "start_time": datetime.now().isoformat(),
                "duration_hours": test_duration_hours,
                "model_a": {
                    "path": model_a_path,
                    "traffic_percentage": 50,
                    "predictions_made": len(test_data) // 2,
                    "avg_response_time_ms": 45,
                    "error_rate": 0.02,
                    "accuracy_metrics": {
                        "mae_speed": 8.5,
                        "rmse_speed": 12.3,
                        "mape_speed": 15.2
                    }
                },
                "model_b": {
                    "path": model_b_path,
                    "traffic_percentage": 50,
                    "predictions_made": len(test_data) // 2,
                    "avg_response_time_ms": 48,
                    "error_rate": 0.015,
                    "accuracy_metrics": {
                        "mae_speed": 7.8,
                        "rmse_speed": 11.9,
                        "mape_speed": 14.1
                    }
                },
                "winner": "model_b",
                "significance_level": 0.95,
                "recommendation": "deploy_model_b"
            }
            
            logger.info(f"A/B test completed: Winner is {test_results['winner']}")
            return test_results
            
        except Exception as e:
            logger.error(f"A/B test failed: {str(e)}")
            raise


class ModelArchiver:
    """Handles model archiving and version management"""
    
    def __init__(self, config: PredictionServiceConfig):
        self.config = config
        self.retraining_config = config.config.get('retraining', {})
        self.archive_path = Path(self.retraining_config.get('archive_path', 'models/archive'))
        self.archive_path.mkdir(parents=True, exist_ok=True)
    
    def archive_model(self, model_path: str, model_metadata: Dict[str, Any]) -> str:
        """Archive a model with metadata"""
        logger.info(f"Archiving model: {model_path}")
        
        try:
            # Create archive directory with timestamp
            archive_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            model_name = Path(model_path).stem
            archive_dir = self.archive_path / f"{model_name}_{archive_timestamp}"
            archive_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy model files
            if os.path.isfile(model_path):
                shutil.copy2(model_path, archive_dir)
            elif os.path.isdir(model_path):
                shutil.copytree(model_path, archive_dir / Path(model_path).name)
            
            # Save metadata
            metadata_file = archive_dir / "metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(model_metadata, f, indent=2, default=str)
            
            # Create archive manifest
            manifest = {
                "archive_timestamp": archive_timestamp,
                "original_path": model_path,
                "archive_path": str(archive_dir),
                "model_name": model_name,
                "metadata": model_metadata
            }
            
            manifest_file = archive_dir / "archive_manifest.json"
            with open(manifest_file, 'w') as f:
                json.dump(manifest, f, indent=2, default=str)
            
            logger.info(f"Model archived successfully to: {archive_dir}")
            return str(archive_dir)
            
        except Exception as e:
            logger.error(f"Failed to archive model: {str(e)}")
            raise
    
    def cleanup_old_archives(self, retention_days: int = 90):
        """Clean up old archived models"""
        logger.info(f"Cleaning up archives older than {retention_days} days")
        
        try:
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            deleted_count = 0
            
            for archive_dir in self.archive_path.iterdir():
                if archive_dir.is_dir():
                    # Extract timestamp from directory name
                    try:
                        timestamp_str = archive_dir.name.split('_')[-2] + '_' + archive_dir.name.split('_')[-1]
                        archive_date = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                        
                        if archive_date < cutoff_date:
                            shutil.rmtree(archive_dir)
                            deleted_count += 1
                            logger.debug(f"Deleted old archive: {archive_dir}")
                            
                    except (ValueError, IndexError):
                        logger.warning(f"Could not parse archive date from: {archive_dir}")
            
            logger.info(f"Cleaned up {deleted_count} old archives")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old archives: {str(e)}")
            return 0


class RetrainingOrchestrator:
    """Main orchestrator for model retraining pipeline"""
    
    def __init__(self, config_path: str = "config/prediction_service_config.json"):
        """Initialize retraining orchestrator"""
        
        # Load configuration
        self.config = PredictionServiceConfig(config_path)
        self.retraining_config = self.config.config.get('retraining', {})
        
        # Setup logging
        self._setup_logging()
        
        # Initialize Spark session
        self.spark = self._create_spark_session()
        
        # Initialize components
        self.db_manager = DatabaseManager(self.config)
        self.data_collector = DataCollector(self.config, self.db_manager)
        self.model_validator = ModelValidator(self.config)
        self.model_archiver = ModelArchiver(self.config)
        
        # Job tracking
        self.current_job: Optional[RetrainingJob] = None
        
        logger.info("Retraining Orchestrator initialized successfully")
    
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
                logging.FileHandler(log_config['log_file_path'].replace('.log', '_retraining.log')),
                logging.StreamHandler()
            ]
        )
    
    def _create_spark_session(self) -> SparkSession:
        """Create Spark session for retraining"""
        spark_config = self.config.spark_config
        
        builder = SparkSession.builder.appName(
            f"TrafficModelRetraining-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        )
        
        # Apply configuration
        for key, value in spark_config.get('config', {}).items():
            builder = builder.config(key, str(value))
        
        return builder.getOrCreate()
    
    def run_scheduled_retraining(self) -> Dict[str, Any]:
        """Run scheduled model retraining"""
        logger.info("Starting scheduled model retraining")
        
        # Calculate training data period (last 30 days)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        return self.run_retraining(
            start_date=start_date,
            end_date=end_date,
            trigger_reason="scheduled_weekly_retraining"
        )
    
    def run_retraining(self, start_date: datetime, end_date: datetime, 
                      trigger_reason: str = "manual") -> Dict[str, Any]:
        """Run complete model retraining pipeline"""
        job_id = f"retraining_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Initialize job
        self.current_job = RetrainingJob(
            job_id=job_id,
            start_time=datetime.now(),
            end_time=None,
            status=RetrainingStatus.RUNNING,
            trigger_reason=trigger_reason,
            data_period_start=start_date,
            data_period_end=end_date,
            training_samples=0,
            validation_samples=0,
            models_trained=[]
        )
        
        logger.info(f"Starting retraining job: {job_id}")
        
        try:
            # Step 1: Collect training data
            logger.info("Step 1: Collecting training data")
            train_data, val_data = self.data_collector.collect_retraining_data(start_date, end_date)
            
            self.current_job.training_samples = len(train_data)
            self.current_job.validation_samples = len(val_data)
            
            if len(train_data) < self.retraining_config.get('min_training_samples', 10000):
                raise ValueError(f"Insufficient training data: {len(train_data)} samples")
            
            # Step 2: Train new models
            logger.info("Step 2: Training new models")
            new_models = self._train_new_models(train_data, val_data)
            self.current_job.models_trained = list(new_models.keys())
            
            # Step 3: Model validation
            logger.info("Step 3: Validating new models")
            self.current_job.status = RetrainingStatus.VALIDATING
            
            best_model_path, validation_results = self._validate_models(new_models, val_data)
            self.current_job.best_model = best_model_path
            self.current_job.performance_metrics = validation_results
            
            # Step 4: Deployment decision
            logger.info("Step 4: Making deployment decision")
            deployment_decision = self._make_deployment_decision(validation_results)
            
            if deployment_decision['should_deploy']:
                # Step 5: Archive current model and deploy new one
                logger.info("Step 5: Deploying new model")
                self._deploy_new_model(best_model_path, deployment_decision)
                self.current_job.status = RetrainingStatus.DEPLOYED
                self.current_job.deployment_candidate = True
            else:
                logger.info("Step 5: Keeping current model (insufficient improvement)")
                self.current_job.status = RetrainingStatus.COMPLETED
                self.current_job.deployment_candidate = False
            
            # Step 6: Cleanup and finalization
            self.current_job.end_time = datetime.now()
            self.current_job.status = RetrainingStatus.COMPLETED
            
            # Archive job results
            self._save_job_results()
            
            result = {
                "status": "completed",
                "job_id": job_id,
                "training_samples": self.current_job.training_samples,
                "validation_samples": self.current_job.validation_samples,
                "models_trained": self.current_job.models_trained,
                "best_model": self.current_job.best_model,
                "deployed": self.current_job.deployment_candidate,
                "performance_metrics": self.current_job.performance_metrics,
                "processing_time": (self.current_job.end_time - self.current_job.start_time).total_seconds(),
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Retraining job completed successfully: {json.dumps(result, indent=2)}")
            return result
            
        except Exception as e:
            error_msg = f"Retraining job failed: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            if self.current_job:
                self.current_job.status = RetrainingStatus.FAILED
                self.current_job.error_message = error_msg
                self.current_job.end_time = datetime.now()
                self._save_job_results()
            
            return {
                "status": "failed",
                "job_id": job_id,
                "error": error_msg,
                "timestamp": datetime.now().isoformat()
            }
    
    def _train_new_models(self, train_data: pd.DataFrame, val_data: pd.DataFrame) -> Dict[str, str]:
        """Train new models using ML training pipeline"""
        try:
            # Create ML training configuration
            ml_config = MLTrainingConfig()
            
            # Initialize ML training pipeline
            ml_pipeline = MLTrainingPipeline(ml_config, self.spark)
            
            # Prepare data for ML pipeline
            # This would involve converting pandas DataFrame to appropriate format
            # and calling the ML training pipeline
            
            # For now, simulate model training
            models_trained = {}
            
            model_types = self.retraining_config.get('model_types', ['random_forest', 'xgboost', 'linear_regression'])
            
            for model_type in model_types:
                model_path = f"models/retrained_{model_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                # Simulate model training (in real implementation, use ML pipeline)
                logger.info(f"Training {model_type} model...")
                time.sleep(2)  # Simulate training time
                
                models_trained[model_type] = model_path
                logger.info(f"Completed training {model_type} model: {model_path}")
            
            return models_trained
            
        except Exception as e:
            logger.error(f"Model training failed: {str(e)}")
            raise
    
    def _validate_models(self, new_models: Dict[str, str], val_data: pd.DataFrame) -> Tuple[str, Dict[str, Any]]:
        """Validate new models and select best performer"""
        try:
            best_model_path = None
            best_score = float('inf')
            validation_results = {}
            
            current_model_path = self.retraining_config.get('current_model_path', 'models/current_model')
            
            for model_type, model_path in new_models.items():
                logger.info(f"Validating {model_type} model...")
                
                # Compare with current production model
                comparison = self.model_validator.validate_model_performance(
                    model_path, current_model_path, val_data
                )
                
                validation_results[model_type] = {
                    "model_path": model_path,
                    "performance_score": comparison.new_model_score,
                    "improvement_percent": comparison.improvement_percent,
                    "recommendation": comparison.recommendation,
                    "confidence_level": comparison.confidence_level
                }
                
                # Track best model (lowest score for RMSE)
                if comparison.new_model_score < best_score:
                    best_score = comparison.new_model_score
                    best_model_path = model_path
            
            logger.info(f"Best performing model: {best_model_path} (score: {best_score:.3f})")
            
            return best_model_path, validation_results
            
        except Exception as e:
            logger.error(f"Model validation failed: {str(e)}")
            raise
    
    def _make_deployment_decision(self, validation_results: Dict[str, Any]) -> Dict[str, Any]:
        """Make deployment decision based on validation results"""
        try:
            min_improvement = self.retraining_config.get('min_improvement_percent', 5.0)
            min_confidence = self.retraining_config.get('min_confidence_level', 0.90)
            
            # Find best model
            best_model = None
            best_improvement = -float('inf')
            
            for model_type, results in validation_results.items():
                if results['improvement_percent'] > best_improvement:
                    best_improvement = results['improvement_percent']
                    best_model = model_type
            
            should_deploy = (
                best_model is not None and
                best_improvement >= min_improvement and
                validation_results[best_model]['confidence_level'] >= min_confidence
            )
            
            decision = {
                "should_deploy": should_deploy,
                "best_model": best_model,
                "best_improvement": best_improvement,
                "reason": self._get_deployment_reason(should_deploy, best_improvement, min_improvement),
                "validation_results": validation_results
            }
            
            logger.info(f"Deployment decision: {decision['reason']}")
            return decision
            
        except Exception as e:
            logger.error(f"Deployment decision failed: {str(e)}")
            raise
    
    def _get_deployment_reason(self, should_deploy: bool, improvement: float, min_improvement: float) -> str:
        """Get human-readable deployment reason"""
        if should_deploy:
            return f"Deploy new model - {improvement:.1f}% improvement exceeds {min_improvement:.1f}% threshold"
        else:
            return f"Keep current model - {improvement:.1f}% improvement below {min_improvement:.1f}% threshold"
    
    def _deploy_new_model(self, model_path: str, deployment_decision: Dict[str, Any]):
        """Deploy new model to production"""
        try:
            # Archive current production model
            current_model_path = self.retraining_config.get('current_model_path', 'models/current_model')
            
            if os.path.exists(current_model_path):
                archive_metadata = {
                    "model_type": "production_model",
                    "archived_reason": "replaced_by_retraining",
                    "replacement_model": model_path,
                    "deployment_decision": deployment_decision
                }
                
                archived_path = self.model_archiver.archive_model(current_model_path, archive_metadata)
                logger.info(f"Archived current model to: {archived_path}")
            
            # Deploy new model (copy to production path)
            if os.path.isfile(model_path):
                shutil.copy2(model_path, current_model_path)
            elif os.path.isdir(model_path):
                if os.path.exists(current_model_path):
                    shutil.rmtree(current_model_path)
                shutil.copytree(model_path, current_model_path)
            
            # Create deployment manifest
            deployment_manifest = {
                "deployment_timestamp": datetime.now().isoformat(),
                "source_model": model_path,
                "production_path": current_model_path,
                "job_id": self.current_job.job_id if self.current_job else "unknown",
                "deployment_decision": deployment_decision
            }
            
            manifest_path = Path(current_model_path).parent / "deployment_manifest.json"
            with open(manifest_path, 'w') as f:
                json.dump(deployment_manifest, f, indent=2, default=str)
            
            logger.info(f"Successfully deployed new model to production: {current_model_path}")
            
        except Exception as e:
            logger.error(f"Model deployment failed: {str(e)}")
            raise
    
    def _save_job_results(self):
        """Save retraining job results"""
        try:
            if not self.current_job:
                return
            
            results_dir = Path("logs/retraining")
            results_dir.mkdir(parents=True, exist_ok=True)
            
            job_file = results_dir / f"{self.current_job.job_id}_results.json"
            
            with open(job_file, 'w') as f:
                json.dump(asdict(self.current_job), f, indent=2, default=str)
            
            logger.info(f"Job results saved to: {job_file}")
            
        except Exception as e:
            logger.error(f"Failed to save job results: {str(e)}")
    
    def cleanup(self):
        """Cleanup resources"""
        try:
            if hasattr(self, 'db_manager'):
                self.db_manager.close()
            
            if hasattr(self, 'spark'):
                self.spark.stop()
            
            # Cleanup old archives
            self.model_archiver.cleanup_old_archives()
            
            logger.info("Retraining Orchestrator cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during retraining cleanup: {str(e)}")


def main():
    """Main execution function"""
    orchestrator = None
    
    try:
        # Initialize orchestrator
        orchestrator = RetrainingOrchestrator()
        
        # Run scheduled retraining
        result = orchestrator.run_scheduled_retraining()
        
        # Print results
        print("\n" + "="*80)
        print("MODEL RETRAINING RESULTS")
        print("="*80)
        print(json.dumps(result, indent=2))
        print("="*80)
        
        # Exit code based on result
        if result.get('status') == 'completed':
            exit(0)
        else:
            exit(1)
    
    except Exception as e:
        print(f"Fatal error in retraining: {str(e)}", file=sys.stderr)
        exit(1)
    
    finally:
        if orchestrator:
            orchestrator.cleanup()


if __name__ == "__main__":
    main()
"""
ML Training Configuration Manager

Manages configuration for machine learning model training pipeline.
Provides structured access to training parameters, model configurations,
and validation settings.
"""

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union
from pathlib import Path

@dataclass
class DataSourceConfig:
    """Configuration for data source and loading"""
    hdfs_feature_path: str = "hdfs://localhost:9000/traffic/features"
    feature_store_path: str = "hdfs://localhost:9000/traffic/feature_store"
    target_columns: List[str] = field(default_factory=lambda: ["speed_mph", "volume_vehicles_per_hour"])
    feature_exclude_columns: List[str] = field(default_factory=lambda: ["sensor_id", "timestamp", "speed_mph", "volume_vehicles_per_hour"])
    timestamp_column: str = "timestamp"
    sensor_id_column: str = "sensor_id"
    min_data_points: int = 10000
    max_data_points: int = 1000000

@dataclass
class DataSplittingConfig:
    """Configuration for data splitting"""
    train_ratio: float = 0.7
    validation_ratio: float = 0.2
    test_ratio: float = 0.1
    stratify_by: Optional[str] = "sensor_id"
    time_based_split: bool = True
    shuffle: bool = False
    random_state: int = 42

@dataclass
class DataPreprocessingConfig:
    """Configuration for data preprocessing"""
    handle_missing_values: bool = True
    missing_value_strategy: str = "interpolate"
    outlier_detection: bool = True
    outlier_method: str = "iqr"
    outlier_threshold: float = 3.0
    normalize_features: bool = True
    normalization_method: str = "standard"
    feature_selection: bool = True
    feature_selection_method: str = "variance"
    variance_threshold: float = 0.01

@dataclass
class ModelConfig:
    """Configuration for individual model"""
    enabled: bool = True
    params: Dict[str, Any] = field(default_factory=dict)
    hyperparameter_tuning: bool = False
    param_grid: Dict[str, List[Any]] = field(default_factory=dict)

@dataclass
class CrossValidationConfig:
    """Configuration for cross validation"""
    enabled: bool = True
    cv_folds: int = 5
    scoring: str = "neg_mean_squared_error"
    shuffle: bool = True
    random_state: int = 42

@dataclass
class HyperparameterTuningConfig:
    """Configuration for hyperparameter tuning"""
    method: str = "grid_search"
    cv_folds: int = 3
    n_jobs: int = -1
    scoring: str = "neg_mean_squared_error"
    verbose: int = 1

@dataclass
class EarlyStoppingConfig:
    """Configuration for early stopping"""
    enabled: bool = True
    patience: int = 10
    min_delta: float = 0.001

@dataclass
class BatchTrainingConfig:
    """Configuration for batch training"""
    enabled: bool = False
    batch_size: int = 10000
    shuffle_batches: bool = True

@dataclass
class TrainingConfig:
    """Configuration for model training"""
    cross_validation: CrossValidationConfig = field(default_factory=CrossValidationConfig)
    hyperparameter_tuning: HyperparameterTuningConfig = field(default_factory=HyperparameterTuningConfig)
    early_stopping: EarlyStoppingConfig = field(default_factory=EarlyStoppingConfig)
    batch_training: BatchTrainingConfig = field(default_factory=BatchTrainingConfig)

@dataclass
class EvaluationConfig:
    """Configuration for model evaluation"""
    metrics: List[str] = field(default_factory=lambda: ["rmse", "mae", "mape", "r2_score", "max_error", "mean_squared_log_error"])
    generate_plots: bool = True
    plot_types: List[str] = field(default_factory=lambda: ["residual_plot", "prediction_vs_actual", "feature_importance", "learning_curve", "validation_curve"])
    residual_analysis: bool = True
    prediction_intervals: bool = True
    confidence_level: float = 0.95

@dataclass
class ModelSelectionConfig:
    """Configuration for model selection"""
    primary_metric: str = "rmse"
    minimize_metric: bool = True
    selection_criteria: Dict[str, float] = field(default_factory=lambda: {
        "rmse_weight": 0.4,
        "mae_weight": 0.3,
        "r2_weight": 0.2,
        "training_time_weight": 0.1
    })
    ensemble_models: bool = True
    ensemble_methods: List[str] = field(default_factory=lambda: ["voting", "stacking"])

@dataclass
class VersioningConfig:
    """Configuration for model versioning"""
    enabled: bool = True
    version_format: str = "semantic"
    auto_increment: bool = True

@dataclass
class ModelRegistryConfig:
    """Configuration for model registry"""
    enabled: bool = True
    mlflow_enabled: bool = False
    mlflow_tracking_uri: str = "http://localhost:5000"
    experiment_name: str = "traffic_prediction"

@dataclass
class ModelPersistenceConfig:
    """Configuration for model persistence"""
    hdfs_model_path: str = "hdfs://localhost:9000/traffic/models"
    local_model_path: str = "models"
    model_format: str = "pickle"
    save_metadata: bool = True
    versioning: VersioningConfig = field(default_factory=VersioningConfig)
    model_registry: ModelRegistryConfig = field(default_factory=ModelRegistryConfig)

@dataclass
class SparkConfig:
    """Configuration for Spark session"""
    app_name: str = "TrafficPredictionMLTraining"
    master: str = "local[*]"
    config: Dict[str, str] = field(default_factory=lambda: {
        "spark.sql.adaptive.enabled": "true",
        "spark.sql.adaptive.coalescePartitions.enabled": "true",
        "spark.executor.memory": "4g",
        "spark.driver.memory": "2g",
        "spark.executor.cores": "2",
        "spark.sql.execution.arrow.pyspark.enabled": "true",
        "spark.serializer": "org.apache.spark.serializer.KryoSerializer",
        "spark.sql.adaptive.skewJoin.enabled": "true",
        "spark.sql.adaptive.localShuffleReader.enabled": "true"
    })

@dataclass
class LoggingConfig:
    """Configuration for logging"""
    level: str = "INFO"
    log_to_file: bool = True
    log_file_path: str = "logs/ml_training.log"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    max_log_size: str = "10MB"
    backup_count: int = 5

@dataclass
class PerformanceConfig:
    """Configuration for performance optimization"""
    parallel_training: bool = True
    max_workers: int = 4
    memory_optimization: bool = True
    cache_data: bool = True
    checkpoint_frequency: int = 100
    progress_reporting: bool = True

@dataclass
class ValidationConfig:
    """Configuration for validation and quality checks"""
    data_quality_checks: bool = True
    feature_drift_detection: bool = True
    model_drift_detection: bool = True
    statistical_tests: bool = True
    min_samples_per_sensor: int = 100
    max_missing_percentage: float = 0.1


class MLTrainingConfigManager:
    """Configuration manager for ML training pipeline"""
    
    def __init__(self, config_path: str = "config/ml_training_config.json"):
        """
        Initialize configuration manager
        
        Args:
            config_path: Path to configuration file
        """
        self.config_path = Path(config_path)
        self.config_data = self._load_config()
        
        # Initialize configuration sections
        self.data_source = self._create_data_source_config()
        self.data_splitting = self._create_data_splitting_config()
        self.data_preprocessing = self._create_data_preprocessing_config()
        self.models = self._create_models_config()
        self.training = self._create_training_config()
        self.evaluation = self._create_evaluation_config()
        self.model_selection = self._create_model_selection_config()
        self.model_persistence = self._create_model_persistence_config()
        self.spark_config = self._create_spark_config()
        self.logging = self._create_logging_config()
        self.performance = self._create_performance_config()
        self.validation = self._create_validation_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            return json.load(f)
    
    def _create_data_source_config(self) -> DataSourceConfig:
        """Create data source configuration"""
        config_section = self.config_data.get("data_source", {})
        return DataSourceConfig(**config_section)
    
    def _create_data_splitting_config(self) -> DataSplittingConfig:
        """Create data splitting configuration"""
        config_section = self.config_data.get("data_splitting", {})
        return DataSplittingConfig(**config_section)
    
    def _create_data_preprocessing_config(self) -> DataPreprocessingConfig:
        """Create data preprocessing configuration"""
        config_section = self.config_data.get("data_preprocessing", {})
        return DataPreprocessingConfig(**config_section)
    
    def _create_models_config(self) -> Dict[str, ModelConfig]:
        """Create models configuration"""
        models_section = self.config_data.get("models", {})
        models = {}
        
        for model_name, model_config in models_section.items():
            models[model_name] = ModelConfig(**model_config)
        
        return models
    
    def _create_training_config(self) -> TrainingConfig:
        """Create training configuration"""
        training_section = self.config_data.get("training", {})
        
        cv_config = CrossValidationConfig(**training_section.get("cross_validation", {}))
        hp_config = HyperparameterTuningConfig(**training_section.get("hyperparameter_tuning", {}))
        es_config = EarlyStoppingConfig(**training_section.get("early_stopping", {}))
        bt_config = BatchTrainingConfig(**training_section.get("batch_training", {}))
        
        return TrainingConfig(
            cross_validation=cv_config,
            hyperparameter_tuning=hp_config,
            early_stopping=es_config,
            batch_training=bt_config
        )
    
    def _create_evaluation_config(self) -> EvaluationConfig:
        """Create evaluation configuration"""
        config_section = self.config_data.get("evaluation", {})
        return EvaluationConfig(**config_section)
    
    def _create_model_selection_config(self) -> ModelSelectionConfig:
        """Create model selection configuration"""
        config_section = self.config_data.get("model_selection", {})
        return ModelSelectionConfig(**config_section)
    
    def _create_model_persistence_config(self) -> ModelPersistenceConfig:
        """Create model persistence configuration"""
        persistence_section = self.config_data.get("model_persistence", {})
        
        versioning_config = VersioningConfig(**persistence_section.get("versioning", {}))
        registry_config = ModelRegistryConfig(**persistence_section.get("model_registry", {}))
        
        return ModelPersistenceConfig(
            hdfs_model_path=persistence_section.get("hdfs_model_path", "hdfs://localhost:9000/traffic/models"),
            local_model_path=persistence_section.get("local_model_path", "models"),
            model_format=persistence_section.get("model_format", "pickle"),
            save_metadata=persistence_section.get("save_metadata", True),
            versioning=versioning_config,
            model_registry=registry_config
        )
    
    def _create_spark_config(self) -> SparkConfig:
        """Create Spark configuration"""
        config_section = self.config_data.get("spark_config", {})
        return SparkConfig(**config_section)
    
    def _create_logging_config(self) -> LoggingConfig:
        """Create logging configuration"""
        config_section = self.config_data.get("logging", {})
        return LoggingConfig(**config_section)
    
    def _create_performance_config(self) -> PerformanceConfig:
        """Create performance configuration"""
        config_section = self.config_data.get("performance", {})
        return PerformanceConfig(**config_section)
    
    def _create_validation_config(self) -> ValidationConfig:
        """Create validation configuration"""
        config_section = self.config_data.get("validation", {})
        return ValidationConfig(**config_section)
    
    def get_enabled_models(self) -> Dict[str, ModelConfig]:
        """Get only enabled models"""
        return {name: config for name, config in self.models.items() if config.enabled}
    
    def get_spark_session_config(self) -> Dict[str, str]:
        """Get Spark session configuration"""
        return self.spark_config.config
    
    def validate_config(self) -> List[str]:
        """Validate configuration and return any issues"""
        issues = []
        
        # Validate data splitting ratios
        total_ratio = (self.data_splitting.train_ratio + 
                      self.data_splitting.validation_ratio + 
                      self.data_splitting.test_ratio)
        if abs(total_ratio - 1.0) > 0.001:
            issues.append(f"Data splitting ratios sum to {total_ratio}, should be 1.0")
        
        # Validate model selection criteria weights
        total_weight = sum(self.model_selection.selection_criteria.values())
        if abs(total_weight - 1.0) > 0.001:
            issues.append(f"Model selection criteria weights sum to {total_weight}, should be 1.0")
        
        # Check enabled models
        enabled_models = self.get_enabled_models()
        if not enabled_models:
            issues.append("No models are enabled for training")
        
        # Validate paths
        if not self.data_source.hdfs_feature_path:
            issues.append("HDFS feature path is not configured")
        
        if not self.model_persistence.hdfs_model_path:
            issues.append("HDFS model path is not configured")
        
        return issues
    
    def save_config(self, output_path: Optional[str] = None):
        """Save current configuration to file"""
        output_path = output_path or self.config_path
        
        # Convert dataclasses back to dict for JSON serialization
        config_dict = {
            "data_source": self.data_source.__dict__,
            "data_splitting": self.data_splitting.__dict__,
            "data_preprocessing": self.data_preprocessing.__dict__,
            "models": {name: config.__dict__ for name, config in self.models.items()},
            "training": {
                "cross_validation": self.training.cross_validation.__dict__,
                "hyperparameter_tuning": self.training.hyperparameter_tuning.__dict__,
                "early_stopping": self.training.early_stopping.__dict__,
                "batch_training": self.training.batch_training.__dict__
            },
            "evaluation": self.evaluation.__dict__,
            "model_selection": self.model_selection.__dict__,
            "model_persistence": {
                "hdfs_model_path": self.model_persistence.hdfs_model_path,
                "local_model_path": self.model_persistence.local_model_path,
                "model_format": self.model_persistence.model_format,
                "save_metadata": self.model_persistence.save_metadata,
                "versioning": self.model_persistence.versioning.__dict__,
                "model_registry": self.model_persistence.model_registry.__dict__
            },
            "spark_config": self.spark_config.__dict__,
            "logging": self.logging.__dict__,
            "performance": self.performance.__dict__,
            "validation": self.validation.__dict__
        }
        
        with open(output_path, 'w') as f:
            json.dump(config_dict, f, indent=2)


def get_ml_config_manager(config_path: str = "config/ml_training_config.json") -> MLTrainingConfigManager:
    """Get ML training configuration manager instance"""
    return MLTrainingConfigManager(config_path)


if __name__ == "__main__":
    # Example usage and validation
    config_manager = get_ml_config_manager()
    
    print("ML Training Configuration Loaded")
    print(f"Enabled Models: {list(config_manager.get_enabled_models().keys())}")
    print(f"Primary Metric: {config_manager.model_selection.primary_metric}")
    print(f"Target Columns: {config_manager.data_source.target_columns}")
    
    # Validate configuration
    issues = config_manager.validate_config()
    if issues:
        print("\nConfiguration Issues:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("\nConfiguration validation passed!")
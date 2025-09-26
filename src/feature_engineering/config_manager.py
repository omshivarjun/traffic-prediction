"""
Feature Engineering Configuration Manager

This module provides configuration management for the feature engineering pipeline,
integrating with existing HDFS pipeline configuration and Spark optimization settings.
"""

import json
import os
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class TemporalFeaturesConfig:
    """Configuration for temporal feature extraction"""
    enabled: bool = True
    lag_periods: Optional[List[int]] = None
    rolling_windows: Optional[List[int]] = None
    cyclical_encoding: Optional[Dict[str, bool]] = None
    trend_analysis: Optional[Dict[str, Any]] = None
    statistical_features: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        # Set defaults if None
        if self.lag_periods is None:
            self.lag_periods = [1, 2, 3, 4, 5, 6]
        if self.rolling_windows is None:
            self.rolling_windows = [5, 15, 30, 60]
        if self.cyclical_encoding is None:
            self.cyclical_encoding = {"hour": True, "day_of_week": True, "month": True}
        if self.trend_analysis is None:
            self.trend_analysis = {"enabled": True, "macd_periods": [12, 26, 9], "rsi_period": 14}
        if self.statistical_features is None:
            self.statistical_features = {"enabled": True, "z_score_window": 60, "percentile_ranks": [25, 50, 75, 90, 95]}

@dataclass 
class SpatialFeaturesConfig:
    """Configuration for spatial feature extraction"""
    enabled: bool = True
    adjacency_threshold_meters: float = 500.0
    neighbor_analysis: Optional[Dict[str, Any]] = None
    network_topology: Optional[Dict[str, Any]] = None
    spatial_correlations: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.neighbor_analysis is None:
            self.neighbor_analysis = {
                "max_neighbors": 5,
                "distance_weights": True,
                "directional_flow": True
            }
        if self.network_topology is None:
            self.network_topology = {
                "centrality_measures": ["betweenness", "closeness", "degree"],
                "clustering_coefficient": True,
                "shortest_paths": True
            }
        if self.spatial_correlations is None:
            self.spatial_correlations = {
                "correlation_window": 60,
                "min_correlation_threshold": 0.3,
                "max_distance_km": 2.0
            }

@dataclass
class FeaturePipelineConfig:
    """Configuration for feature pipeline processing"""
    data_quality: Optional[Dict[str, Any]] = None
    preprocessing: Optional[Dict[str, Any]] = None
    feature_scaling: Optional[Dict[str, Any]] = None
    feature_selection: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.data_quality is None:
            self.data_quality = {
                "missing_value_threshold": 0.1,
                "outlier_detection": {
                    "method": "iqr",
                    "iqr_multiplier": 1.5,
                    "zscore_threshold": 3.0
                },
                "data_drift_detection": True
            }
        if self.preprocessing is None:
            self.preprocessing = {
                "handle_missing": "interpolate",
                "outlier_treatment": "cap",
                "data_validation": True
            }
        if self.feature_scaling is None:
            self.feature_scaling = {
                "method": "standard",
                "per_feature": True,
                "robust_scaling_quantile_range": [25.0, 75.0]
            }
        if self.feature_selection is None:
            self.feature_selection = {
                "enabled": False,
                "methods": ["correlation", "mutual_info", "recursive"],
                "correlation_threshold": 0.95,
                "importance_threshold": 0.01
            }

@dataclass
class FeatureStoreConfig:
    """Configuration for feature store"""
    storage: Optional[Dict[str, Any]] = None
    versioning: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    mlflow_integration: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.storage is None:
            self.storage = {
                "base_path": "hdfs://localhost:9000/traffic/features",
                "format": "parquet",
                "compression": "snappy",
                "partitioning": ["year", "month", "day"]
            }
        if self.versioning is None:
            self.versioning = {
                "enabled": True,
                "max_versions": 10,
                "cleanup_after_days": 90,
                "schema_evolution": True
            }
        if self.metadata is None:
            self.metadata = {
                "track_lineage": True,
                "quality_metrics": True,
                "usage_statistics": True
            }
        if self.mlflow_integration is None:
            self.mlflow_integration = {
                "enabled": False,
                "tracking_uri": "file:///tmp/mlflow",
                "experiment_name": "traffic-prediction-features"
            }

@dataclass
class SparkOptimizationConfig:
    """Configuration for Spark optimization"""
    sql: Optional[Dict[str, Any]] = None
    execution: Optional[Dict[str, Any]] = None
    memory: Optional[Dict[str, Any]] = None
    io: Optional[Dict[str, Any]] = None
    feature_specific: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.sql is None:
            self.sql = {
                "adaptive.enabled": True,
                "adaptive.coalescePartitions.enabled": True,
                "adaptive.skewJoin.enabled": True,
                "cbo.enabled": True
            }
        if self.execution is None:
            self.execution = {
                "dynamicAllocation.enabled": True,
                "dynamicAllocation.minExecutors": 1,
                "dynamicAllocation.maxExecutors": 10,
                "cores.max": 4
            }
        if self.memory is None:
            self.memory = {
                "executor.memory": "2g",
                "executor.memoryFraction": 0.8,
                "serializer": "org.apache.spark.serializer.KryoSerializer"
            }
        if self.io is None:
            self.io = {
                "compression.codec": "snappy",
                "serialization.objectStreamReset": 100,
                "sql.files.maxPartitionBytes": "128MB"
            }
        if self.feature_specific is None:
            self.feature_specific = {
                "broadcast_threshold": "10MB",
                "window_partition_size": 1000000,
                "cache_intermediate_results": True,
                "checkpoint_interval": 10
            }

@dataclass
class MonitoringConfig:
    """Configuration for monitoring and alerting"""
    enabled: bool = True
    metrics: Optional[Dict[str, bool]] = None
    alerts: Optional[Dict[str, Any]] = None
    logging: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metrics is None:
            self.metrics = {
                "feature_drift": True,
                "data_quality": True,
                "pipeline_performance": True
            }
        if self.alerts is None:
            self.alerts = {
                "quality_degradation_threshold": 0.8,
                "drift_detection_threshold": 0.05,
                "pipeline_failure_notification": True
            }
        if self.logging is None:
            self.logging = {
                "level": "INFO",
                "file_rotation": True,
                "max_file_size": "100MB",
                "retention_days": 30
            }

@dataclass
class HDFSIntegrationConfig:
    """Configuration for HDFS integration"""
    namenode_url: str = "hdfs://localhost:9000"
    data_paths: Optional[Dict[str, str]] = None
    replication_factor: int = 2
    block_size: str = "128MB"
    permissions: str = "755"
    
    def __post_init__(self):
        if self.data_paths is None:
            self.data_paths = {
                "raw_traffic": "/traffic/raw",
                "processed_features": "/traffic/features",
                "models": "/traffic/models",
                "metadata": "/traffic/metadata"
            }

class FeatureEngineeringConfigManager:
    """Main configuration manager for feature engineering pipeline"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        
        # Default config path
        if config_path is None:
            config_path = self._find_config_file()
        
        self.config_path = config_path
        self.config_data = {}
        
        # Configuration components
        self.temporal_features: Optional[TemporalFeaturesConfig] = None
        self.spatial_features: Optional[SpatialFeaturesConfig] = None
        self.feature_pipeline: Optional[FeaturePipelineConfig] = None
        self.feature_store: Optional[FeatureStoreConfig] = None
        self.spark_optimization: Optional[SparkOptimizationConfig] = None
        self.monitoring: Optional[MonitoringConfig] = None
        self.hdfs_integration: Optional[HDFSIntegrationConfig] = None
        
        # Load configuration
        self.load_config()
    
    def _find_config_file(self) -> str:
        """Find the configuration file in standard locations"""
        possible_paths = [
            "config/feature_engineering_config.json",
            "../config/feature_engineering_config.json",
            "../../config/feature_engineering_config.json",
            os.path.join(os.path.dirname(__file__), "../config/feature_engineering_config.json"),
            os.path.join(os.path.dirname(__file__), "../../config/feature_engineering_config.json")
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        # Return default path if not found
        return "config/feature_engineering_config.json"
    
    def load_config(self):
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    self.config_data = json.load(f)
                self.logger.info(f"Loaded configuration from {self.config_path}")
            else:
                self.logger.warning(f"Configuration file not found: {self.config_path}")
                self.config_data = self._get_default_config()
            
            # Parse configuration sections
            self._parse_config_sections()
            
        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}")
            self.config_data = self._get_default_config()
            self._parse_config_sections()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            "feature_engineering": {
                "temporal_features": {},
                "spatial_features": {},
                "feature_pipeline": {},
                "feature_store": {},
                "spark_optimization": {},
                "monitoring": {}
            },
            "hdfs_integration": {}
        }
    
    def _parse_config_sections(self):
        """Parse configuration sections into dataclass objects"""
        fe_config = self.config_data.get("feature_engineering", {})
        
        # Parse each section
        self.temporal_features = TemporalFeaturesConfig(
            **fe_config.get("temporal_features", {})
        )
        
        self.spatial_features = SpatialFeaturesConfig(
            **fe_config.get("spatial_features", {})
        )
        
        self.feature_pipeline = FeaturePipelineConfig(
            **fe_config.get("feature_pipeline", {})
        )
        
        self.feature_store = FeatureStoreConfig(
            **fe_config.get("feature_store", {})
        )
        
        self.spark_optimization = SparkOptimizationConfig(
            **fe_config.get("spark_optimization", {})
        )
        
        self.monitoring = MonitoringConfig(
            **fe_config.get("monitoring", {})
        )
        
        self.hdfs_integration = HDFSIntegrationConfig(
            **self.config_data.get("hdfs_integration", {})
        )
    
    def get_spark_config(self) -> Dict[str, str]:
        """Get Spark configuration as key-value pairs"""
        spark_config = {}
        
        if self.spark_optimization:
            # SQL configurations
            if self.spark_optimization.sql:
                for key, value in self.spark_optimization.sql.items():
                    spark_config[f"spark.sql.{key}"] = str(value).lower() if isinstance(value, bool) else str(value)
            
            # Execution configurations  
            if self.spark_optimization.execution:
                for key, value in self.spark_optimization.execution.items():
                    spark_config[f"spark.{key}"] = str(value).lower() if isinstance(value, bool) else str(value)
            
            # Memory configurations
            if self.spark_optimization.memory:
                for key, value in self.spark_optimization.memory.items():
                    spark_key = f"spark.executor.{key}" if not key.startswith("executor") else f"spark.{key}"
                    spark_config[spark_key] = str(value)
            
            # I/O configurations
            if self.spark_optimization.io:
                for key, value in self.spark_optimization.io.items():
                    if key == "compression.codec":
                        spark_config["spark.io.compression.codec"] = str(value)
                    elif key == "serialization.objectStreamReset":
                        spark_config["spark.serialization.objectStreamReset"] = str(value)
                    elif key == "sql.files.maxPartitionBytes":
                        spark_config["spark.sql.files.maxPartitionBytes"] = str(value)
        
        return spark_config
    
    def get_hdfs_paths(self) -> Dict[str, str]:
        """Get HDFS paths with full URLs"""
        if not self.hdfs_integration:
            return {}
        
        base_url = self.hdfs_integration.namenode_url
        paths = {}
        
        if self.hdfs_integration.data_paths:
            for key, path in self.hdfs_integration.data_paths.items():
                paths[key] = f"{base_url}{path}"
        
        return paths
    
    def validate_config(self) -> List[str]:
        """Validate configuration and return list of issues"""
        issues = []
        
        # Validate temporal features
        if self.temporal_features and self.temporal_features.enabled:
            if not self.temporal_features.lag_periods:
                issues.append("Temporal features enabled but no lag periods specified")
            if not self.temporal_features.rolling_windows:
                issues.append("Temporal features enabled but no rolling windows specified")
        
        # Validate spatial features
        if self.spatial_features and self.spatial_features.enabled:
            if self.spatial_features.adjacency_threshold_meters <= 0:
                issues.append("Spatial features adjacency threshold must be positive")
        
        # Validate feature store paths
        if self.feature_store and self.feature_store.storage:
            if not self.feature_store.storage.get("base_path"):
                issues.append("Feature store base path not specified")
        
        # Validate HDFS integration
        if self.hdfs_integration:
            if not self.hdfs_integration.namenode_url:
                issues.append("HDFS namenode URL not specified")
            if not self.hdfs_integration.data_paths:
                issues.append("HDFS data paths not specified")
        
        return issues
    
    def save_config(self, config_path: Optional[str] = None):
        """Save current configuration to file"""
        save_path = config_path or self.config_path
        
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            with open(save_path, 'w') as f:
                json.dump(self.config_data, f, indent=2)
            
            self.logger.info(f"Configuration saved to {save_path}")
            
        except Exception as e:
            self.logger.error(f"Error saving configuration: {e}")
    
    def override_config(self, overrides: Dict[str, Any]):
        """Override configuration values"""
        def deep_update(base_dict, update_dict):
            for key, value in update_dict.items():
                if isinstance(value, dict) and key in base_dict and isinstance(base_dict[key], dict):
                    deep_update(base_dict[key], value)
                else:
                    base_dict[key] = value
        
        deep_update(self.config_data, overrides)
        self._parse_config_sections()
        self.logger.info("Configuration overrides applied")
    
    def get_feature_engineering_summary(self) -> Dict[str, Any]:
        """Get summary of feature engineering configuration"""
        return {
            "temporal_features_enabled": self.temporal_features.enabled if self.temporal_features else False,
            "spatial_features_enabled": self.spatial_features.enabled if self.spatial_features else False,
            "lag_periods_count": len(self.temporal_features.lag_periods) if self.temporal_features and self.temporal_features.lag_periods else 0,
            "rolling_windows_count": len(self.temporal_features.rolling_windows) if self.temporal_features and self.temporal_features.rolling_windows else 0,
            "adjacency_threshold": self.spatial_features.adjacency_threshold_meters if self.spatial_features else 0,
            "feature_store_enabled": self.feature_store.versioning.get("enabled", False) if self.feature_store and self.feature_store.versioning else False,
            "mlflow_enabled": self.feature_store.mlflow_integration.get("enabled", False) if self.feature_store and self.feature_store.mlflow_integration else False,
            "monitoring_enabled": self.monitoring.enabled if self.monitoring else False
        }

# Global configuration instance
_config_manager = None

def get_config_manager() -> FeatureEngineeringConfigManager:
    """Get global configuration manager instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = FeatureEngineeringConfigManager()
    return _config_manager

def reload_config():
    """Reload configuration from file"""
    global _config_manager
    if _config_manager:
        _config_manager.load_config()

if __name__ == "__main__":
    # Example usage
    config_manager = FeatureEngineeringConfigManager()
    
    # Validate configuration
    issues = config_manager.validate_config()
    if issues:
        print("Configuration issues found:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("Configuration is valid")
    
    # Get summary
    summary = config_manager.get_feature_engineering_summary()
    print("\nFeature Engineering Configuration Summary:")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    
    # Get Spark configuration
    spark_config = config_manager.get_spark_config()
    print(f"\nSpark Configuration ({len(spark_config)} settings)")
    for key, value in list(spark_config.items())[:5]:  # Show first 5
        print(f"  {key}: {value}")
    
    # Get HDFS paths
    hdfs_paths = config_manager.get_hdfs_paths()
    print(f"\nHDFS Paths ({len(hdfs_paths)} paths)")
    for key, value in hdfs_paths.items():
        print(f"  {key}: {value}")
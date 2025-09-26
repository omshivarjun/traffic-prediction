"""
Feature Store Module

This module provides comprehensive feature storage and versioning capabilities
for machine learning feature management. It supports HDFS storage, feature versioning,
metadata tracking, and integration with MLflow for feature lifecycle management.
"""

import os
import json
import hashlib
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Union, Any
from dataclasses import dataclass, asdict
from pathlib import Path

try:
    from pyspark.sql import SparkSession, DataFrame as SparkDataFrame
    from pyspark.sql.functions import col, current_timestamp, lit, when, count, sum as spark_sum
    from pyspark.sql.types import StructType, StructField, StringType, IntegerType, FloatType, TimestampType
except ImportError:
    # Fallback for type checking
    SparkSession = Any
    SparkDataFrame = Any
from pyspark.sql.functions import col, current_timestamp, lit, when, count, sum as spark_sum
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, FloatType, TimestampType

logger = logging.getLogger(__name__)

@dataclass
class FeatureVersion:
    """Represents a version of a feature set"""
    version_id: str
    version_number: int
    created_timestamp: str
    created_by: str
    description: str
    schema_hash: str
    feature_count: int
    row_count: int
    storage_path: str
    metadata_path: str
    tags: List[str]
    parent_version: Optional[str] = None
    is_active: bool = True

@dataclass
class FeatureMetadata:
    """Metadata for individual features"""
    feature_name: str
    feature_type: str
    data_type: str
    description: str
    source_columns: List[str]
    transformation_logic: str
    creation_timestamp: str
    last_updated: str
    statistics: Dict[str, Any]
    quality_score: float
    tags: List[str]

@dataclass
class FeatureSet:
    """Represents a complete feature set"""
    feature_set_id: str
    name: str
    description: str
    created_timestamp: str
    current_version: FeatureVersion
    all_versions: List[FeatureVersion]
    features: List[FeatureMetadata]
    schema: StructType
    tags: List[str]

class FeatureVersionManager:
    """Manages feature versioning and lineage"""
    
    def __init__(self, base_path: str = "hdfs://localhost:9000/traffic/features"):
        self.base_path = base_path
        self.versions_path = f"{base_path}/versions"
        self.metadata_path = f"{base_path}/metadata"
        self.logger = logging.getLogger(__name__)
        
        # Ensure directories exist
        self._create_directory_structure()
    
    def _create_directory_structure(self):
        """Create necessary directory structure"""
        # This would create HDFS directories in a real implementation
        pass
    
    def generate_version_id(self, feature_set_name: str, timestamp: Optional[datetime] = None) -> str:
        """Generate a unique version ID"""
        if timestamp is None:
            timestamp = datetime.now()
        
        timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
        hash_input = f"{feature_set_name}_{timestamp_str}"
        hash_value = hashlib.md5(hash_input.encode()).hexdigest()[:8]
        
        return f"{feature_set_name}_v{timestamp_str}_{hash_value}"
    
    def calculate_schema_hash(self, df: Any) -> str:
        """Calculate hash of DataFrame schema for change detection"""
        schema_str = str(df.schema)
        return hashlib.md5(schema_str.encode()).hexdigest()
    
    def create_version(self, df: Any,
                      feature_set_name: str,
                      description: str,
                      created_by: str = "system",
                      tags: Optional[List[str]] = None,
                      parent_version: Optional[str] = None) -> FeatureVersion:
        """
        Create a new version of a feature set
        
        Args:
            df: DataFrame containing features
            feature_set_name: Name of the feature set
            description: Description of this version
            created_by: User who created the version
            tags: Optional tags for categorization
            parent_version: Parent version ID if this is an update
            
        Returns:
            FeatureVersion object
        """
        self.logger.info(f"Creating new version of feature set: {feature_set_name}")
        
        # Generate version information
        timestamp = datetime.now()
        version_id = self.generate_version_id(feature_set_name, timestamp)
        schema_hash = self.calculate_schema_hash(df)
        row_count = df.count()
        feature_count = len(df.columns)
        
        # Determine version number
        existing_versions = self.list_versions(feature_set_name)
        version_number = max([v.version_number for v in existing_versions], default=0) + 1
        
        # Define storage paths
        storage_path = f"{self.versions_path}/{feature_set_name}/{version_id}"
        metadata_path = f"{self.metadata_path}/{version_id}.json"
        
        # Create version object
        version = FeatureVersion(
            version_id=version_id,
            version_number=version_number,
            created_timestamp=timestamp.isoformat(),
            created_by=created_by,
            description=description,
            schema_hash=schema_hash,
            feature_count=feature_count,
            row_count=row_count,
            storage_path=storage_path,
            metadata_path=metadata_path,
            tags=tags or [],
            parent_version=parent_version,
            is_active=True
        )
        
        return version
    
    def save_version(self, df: Any, version: FeatureVersion):
        """
        Save a feature version to storage
        
        Args:
            df: DataFrame to save
            version: Version metadata
        """
        self.logger.info(f"Saving version {version.version_id}")
        
        # Add versioning metadata to DataFrame
        df_with_metadata = df.withColumn("_version_id", lit(version.version_id)) \
                            .withColumn("_created_timestamp", lit(version.created_timestamp)) \
                            .withColumn("_version_number", lit(version.version_number))
        
        # Save data in Parquet format with partitioning
        df_with_metadata.write \
            .mode("overwrite") \
            .option("compression", "snappy") \
            .parquet(version.storage_path)
        
        # Save version metadata
        metadata = asdict(version)
        # In a real implementation, this would save to HDFS
        # For now, we'll create a local representation
        local_path = version.metadata_path.replace("hdfs://localhost:9000/", "")
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        with open(local_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        self.logger.info(f"Version {version.version_id} saved successfully")
    
    def load_version(self, spark: Any, version_id: str) -> Tuple[Any, FeatureVersion]:
        """
        Load a specific version of features
        
        Args:
            spark: Spark session
            version_id: Version ID to load
            
        Returns:
            Tuple of (DataFrame, FeatureVersion)
        """
        self.logger.info(f"Loading version {version_id}")
        
        # Load metadata
        metadata_path = f"{self.metadata_path}/{version_id}.json"
        local_metadata_path = metadata_path.replace("hdfs://localhost:9000/", "")
        
        with open(local_metadata_path, 'r') as f:
            version_data = json.load(f)
        
        version = FeatureVersion(**version_data)
        
        # Load data
        df = spark.read.parquet(version.storage_path)
        
        # Remove versioning metadata columns
        feature_columns = [col for col in df.columns 
                          if not col.startswith('_version') and not col.startswith('_created')]
        df = df.select(*feature_columns)
        
        return df, version
    
    def list_versions(self, feature_set_name: Optional[str] = None) -> List[FeatureVersion]:
        """
        List all versions of a feature set or all feature sets
        
        Args:
            feature_set_name: Optional feature set name to filter
            
        Returns:
            List of FeatureVersion objects
        """
        versions = []
        
        # In a real implementation, this would scan HDFS directories
        # For now, return empty list as placeholder
        
        return versions
    
    def get_latest_version(self, feature_set_name: str) -> Optional[FeatureVersion]:
        """Get the latest version of a feature set"""
        versions = self.list_versions(feature_set_name)
        if not versions:
            return None
        
        return max(versions, key=lambda v: v.version_number)
    
    def compare_versions(self, version_id_1: str, version_id_2: str) -> Dict[str, Any]:
        """
        Compare two versions and return differences
        
        Args:
            version_id_1: First version ID
            version_id_2: Second version ID
            
        Returns:
            Dictionary containing comparison results
        """
        # Load both versions metadata
        # This is a placeholder implementation
        return {
            "schema_changes": [],
            "feature_count_change": 0,
            "row_count_change": 0,
            "new_features": [],
            "removed_features": [],
            "modified_features": []
        }

class FeatureStore:
    """Main feature store class for managing feature lifecycle"""
    
    def __init__(self, spark_session: Any, 
                 base_path: str = "hdfs://localhost:9000/traffic/features",
                 enable_mlflow: bool = False):
        self.spark = spark_session
        self.base_path = base_path
        self.enable_mlflow = enable_mlflow
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.version_manager = FeatureVersionManager(base_path)
        
        # MLflow integration (if enabled)
        self.mlflow_client = None
        if enable_mlflow:
            self._initialize_mlflow()
        
        # Feature registry
        self.feature_registry = {}
        self._load_feature_registry()
    
    def _initialize_mlflow(self):
        """Initialize MLflow tracking"""
        try:
            import mlflow
            from mlflow.tracking import MlflowClient
            
            # Set tracking URI (would be configured for production)
            mlflow.set_tracking_uri("file:///tmp/mlflow")
            self.mlflow_client = MlflowClient()
            
            # Create experiment if it doesn't exist
            experiment_name = "traffic-prediction-features"
            try:
                experiment = mlflow.get_experiment_by_name(experiment_name)
                if experiment is None:
                    mlflow.create_experiment(experiment_name)
            except:
                pass
                
            self.logger.info("MLflow integration initialized")
            
        except ImportError:
            self.logger.warning("MLflow not available, feature tracking disabled")
            self.enable_mlflow = False
    
    def _load_feature_registry(self):
        """Load existing feature registry"""
        registry_path = f"{self.base_path}/registry.json"
        local_registry_path = registry_path.replace("hdfs://localhost:9000/", "")
        
        if os.path.exists(local_registry_path):
            with open(local_registry_path, 'r') as f:
                self.feature_registry = json.load(f)
        else:
            self.feature_registry = {}
    
    def _save_feature_registry(self):
        """Save feature registry"""
        registry_path = f"{self.base_path}/registry.json"
        local_registry_path = registry_path.replace("hdfs://localhost:9000/", "")
        
        os.makedirs(os.path.dirname(local_registry_path), exist_ok=True)
        with open(local_registry_path, 'w') as f:
            json.dump(self.feature_registry, f, indent=2)
    
    def register_feature_set(self, df: Any,
                           feature_set_name: str,
                           description: str,
                           feature_metadata: Optional[Dict[str, FeatureMetadata]] = None,
                           tags: Optional[List[str]] = None,
                           created_by: str = "system") -> FeatureSet:
        """
        Register a new feature set or create a new version
        
        Args:
            df: DataFrame containing features
            feature_set_name: Name of the feature set
            description: Description of the feature set
            feature_metadata: Optional metadata for individual features
            tags: Optional tags for categorization
            created_by: User who created the feature set
            
        Returns:
            FeatureSet object
        """
        self.logger.info(f"Registering feature set: {feature_set_name}")
        
        # Create version
        version = self.version_manager.create_version(
            df, feature_set_name, description, created_by, tags or []
        )
        
        # Save version
        self.version_manager.save_version(df, version)
        
        # Extract feature metadata if not provided
        if feature_metadata is None:
            feature_metadata = self._extract_feature_metadata(df)
        
        # Create feature set
        feature_set = FeatureSet(
            feature_set_id=feature_set_name,
            name=feature_set_name,
            description=description,
            created_timestamp=datetime.now().isoformat(),
            current_version=version,
            all_versions=[version],
            features=list(feature_metadata.values()) if feature_metadata else [],
            schema=df.schema,
            tags=tags or []
        )
        
        # Update registry
        if feature_set_name in self.feature_registry:
            # Update existing feature set
            existing_data = self.feature_registry[feature_set_name]
            existing_data["all_versions"].append(asdict(version))
            existing_data["current_version"] = asdict(version)
        else:
            # Register new feature set
            self.feature_registry[feature_set_name] = asdict(feature_set)
        
        self._save_feature_registry()
        
        # MLflow tracking
        if self.enable_mlflow:
            self._log_to_mlflow(feature_set, version)
        
        self.logger.info(f"Feature set {feature_set_name} registered successfully")
        return feature_set
    
    def get_feature_set(self, feature_set_name: str, 
                       version: Optional[str] = None) -> Tuple[Any, FeatureSet]:
        """
        Retrieve a feature set
        
        Args:
            feature_set_name: Name of the feature set
            version: Optional specific version (defaults to latest)
            
        Returns:
            Tuple of (DataFrame, FeatureSet)
        """
        if feature_set_name not in self.feature_registry:
            raise ValueError(f"Feature set {feature_set_name} not found")
        
        # Get feature set metadata
        feature_set_data = self.feature_registry[feature_set_name]
        feature_set = FeatureSet(**feature_set_data)
        
        # Determine version to load
        if version is None:
            version_to_load = feature_set.current_version.version_id
        else:
            version_to_load = version
        
        # Load data
        df, version_obj = self.version_manager.load_version(self.spark, version_to_load)
        
        return df, feature_set
    
    def list_feature_sets(self, tags: Optional[List[str]] = None) -> List[str]:
        """
        List available feature sets
        
        Args:
            tags: Optional tags to filter by
            
        Returns:
            List of feature set names
        """
        if tags is None:
            return list(self.feature_registry.keys())
        
        # Filter by tags
        matching_sets = []
        for name, data in self.feature_registry.items():
            if any(tag in data.get("tags", []) for tag in tags):
                matching_sets.append(name)
        
        return matching_sets
    
    def search_features(self, query: str, feature_set_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search for features by name or description
        
        Args:
            query: Search query
            feature_set_name: Optional feature set to limit search
            
        Returns:
            List of matching features
        """
        matching_features = []
        
        feature_sets_to_search = [feature_set_name] if feature_set_name else self.feature_registry.keys()
        
        for fs_name in feature_sets_to_search:
            if fs_name not in self.feature_registry:
                continue
                
            feature_set_data = self.feature_registry[fs_name]
            for feature in feature_set_data.get("features", []):
                if (query.lower() in feature["feature_name"].lower() or 
                    query.lower() in feature["description"].lower()):
                    feature_info = feature.copy()
                    feature_info["feature_set"] = fs_name
                    matching_features.append(feature_info)
        
        return matching_features
    
    def create_feature_view(self, feature_set_name: str,
                          selected_features: List[str],
                          view_name: str,
                          filters: Optional[Dict[str, Any]] = None) -> Any:
        """
        Create a view with selected features
        
        Args:
            feature_set_name: Source feature set
            selected_features: List of features to include
            view_name: Name for the view
            filters: Optional filters to apply
            
        Returns:
            DataFrame view
        """
        df, _ = self.get_feature_set(feature_set_name)
        
        # Select features
        if selected_features:
            available_features = [col for col in selected_features if col in df.columns]
            df = df.select(*available_features)
        
        # Apply filters
        if filters:
            for column, condition in filters.items():
                if column in df.columns:
                    if isinstance(condition, dict):
                        if "min" in condition:
                            df = df.filter(col(column) >= condition["min"])
                        if "max" in condition:
                            df = df.filter(col(column) <= condition["max"])
                    else:
                        df = df.filter(col(column) == condition)
        
        # Create temporary view
        df.createOrReplaceTempView(view_name)
        
        return df
    
    def validate_feature_quality(self, df: Any, 
                                feature_set_name: str) -> Dict[str, Any]:
        """
        Validate feature quality and generate report
        
        Args:
            df: DataFrame to validate
            feature_set_name: Name of the feature set
            
        Returns:
            Quality validation report
        """
        self.logger.info(f"Validating feature quality for {feature_set_name}")
        
        total_rows = df.count()
        quality_report = {
            "feature_set_name": feature_set_name,
            "validation_timestamp": datetime.now().isoformat(),
            "total_rows": total_rows,
            "total_features": len(df.columns),
            "quality_checks": {},
            "overall_score": 0.0
        }
        
        # Missing value check
        missing_counts = {}
        for column in df.columns:
            null_count = df.filter(col(column).isNull()).count()
            missing_percentage = (null_count / total_rows) * 100 if total_rows > 0 else 0
            missing_counts[column] = {
                "null_count": null_count,
                "missing_percentage": missing_percentage
            }
        
        quality_report["quality_checks"]["missing_values"] = missing_counts
        
        # Data type consistency check
        schema_info = {}
        for field in df.schema.fields:
            schema_info[field.name] = {
                "data_type": str(field.dataType),
                "nullable": field.nullable
            }
        
        quality_report["quality_checks"]["schema_consistency"] = schema_info
        
        # Calculate overall quality score
        avg_missing_percentage = sum(m["missing_percentage"] for m in missing_counts.values()) / len(missing_counts)
        completeness_score = max(0, 100 - avg_missing_percentage)
        
        quality_report["overall_score"] = completeness_score
        
        return quality_report
    
    def _extract_feature_metadata(self, df: Any) -> Dict[str, FeatureMetadata]:
        """Extract basic metadata for features"""
        metadata = {}
        
        for field in df.schema.fields:
            feature_meta = FeatureMetadata(
                feature_name=field.name,
                feature_type="unknown",  # Would be determined based on naming conventions
                data_type=str(field.dataType),
                description=f"Feature: {field.name}",
                source_columns=[field.name],
                transformation_logic="direct",
                creation_timestamp=datetime.now().isoformat(),
                last_updated=datetime.now().isoformat(),
                statistics={},
                quality_score=100.0,
                tags=[]
            )
            metadata[field.name] = feature_meta
        
        return metadata
    
    def _log_to_mlflow(self, feature_set: FeatureSet, version: FeatureVersion):
        """Log feature set information to MLflow"""
        if not self.enable_mlflow:
            return
        
        try:
            import mlflow
            
            with mlflow.start_run(run_name=f"feature_set_{feature_set.name}_{version.version_number}"):
                # Log parameters
                mlflow.log_param("feature_set_name", feature_set.name)
                mlflow.log_param("version_number", version.version_number)
                mlflow.log_param("feature_count", version.feature_count)
                mlflow.log_param("row_count", version.row_count)
                
                # Log metrics
                mlflow.log_metric("feature_count", version.feature_count)
                mlflow.log_metric("row_count", version.row_count)
                
                # Log tags
                for tag in feature_set.tags:
                    mlflow.set_tag(f"tag_{tag}", "true")
                
                # Log artifacts (metadata)
                metadata_dict = {
                    "feature_set": asdict(feature_set),
                    "version": asdict(version)
                }
                
                # Save metadata to temp file and log as artifact
                temp_file = f"/tmp/feature_metadata_{version.version_id}.json"
                with open(temp_file, 'w') as f:
                    json.dump(metadata_dict, f, indent=2)
                
                mlflow.log_artifact(temp_file, "feature_metadata")
                
        except Exception as e:
            self.logger.warning(f"Failed to log to MLflow: {e}")

    def cleanup_old_versions(self, feature_set_name: str, 
                           keep_versions: int = 5,
                           older_than_days: int = 30):
        """
        Clean up old versions of a feature set
        
        Args:
            feature_set_name: Name of the feature set
            keep_versions: Number of recent versions to keep
            older_than_days: Only delete versions older than this many days
        """
        self.logger.info(f"Cleaning up old versions of {feature_set_name}")
        
        # This would implement actual cleanup logic
        # For now, it's a placeholder
        pass

# Utility functions
def create_feature_documentation(feature_set: FeatureSet) -> str:
    """Generate documentation for a feature set"""
    doc = f"""
# Feature Set: {feature_set.name}

## Description
{feature_set.description}

## Current Version
- Version: {feature_set.current_version.version_number}
- Created: {feature_set.current_version.created_timestamp}
- Features: {feature_set.current_version.feature_count}
- Rows: {feature_set.current_version.row_count}

## Features
"""
    
    for feature in feature_set.features:
        doc += f"""
### {feature.feature_name}
- **Type**: {feature.feature_type}
- **Data Type**: {feature.data_type}
- **Description**: {feature.description}
- **Quality Score**: {feature.quality_score}
"""
    
    return doc

if __name__ == "__main__":
    # Example usage
    spark = SparkSession.builder \
        .appName("FeatureStoreExample") \
        .config("spark.sql.adaptive.enabled", "true") \
        .getOrCreate()
    
    # Initialize feature store
    feature_store = FeatureStore(spark, enable_mlflow=False)
    
    # Create sample feature data
    sample_data = [
        ("SENSOR_001", "2023-06-01 10:00:00", 25.5, 60.0, 10, 3, 0),
        ("SENSOR_002", "2023-06-01 10:00:00", 30.2, 45.0, 10, 3, 0),
        ("SENSOR_003", "2023-06-01 10:00:00", 28.7, 55.0, 10, 3, 0)
    ]
    
    columns = ["sensor_id", "timestamp", "speed_mph", "volume_vph", "hour", "day_of_week", "is_weekend"]
    df = spark.createDataFrame(sample_data, columns)
    
    # Register feature set
    feature_set = feature_store.register_feature_set(
        df=df,
        feature_set_name="traffic_basic_features",
        description="Basic traffic features for prediction",
        tags=["traffic", "temporal", "v1"]
    )
    
    print(f"Registered feature set: {feature_set.name}")
    print(f"Version: {feature_set.current_version.version_number}")
    print(f"Features: {feature_set.current_version.feature_count}")
    
    # Validate quality
    quality_report = feature_store.validate_feature_quality(df, "traffic_basic_features")
    print(f"Quality Score: {quality_report['overall_score']:.2f}")
    
    # Generate documentation
    doc = create_feature_documentation(feature_set)
    print("\nFeature Documentation:")
    print(doc[:500] + "...")
    
    spark.stop()
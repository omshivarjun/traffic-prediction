"""
Model Persistence and Versioning System

Handles model storage, versioning, metadata tracking, and integration
with HDFS and feature store. Provides comprehensive model lifecycle management.
"""

import os
import json
import pickle
import joblib
import shutil
import logging
import hashlib
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional, Union
from dataclasses import dataclass, asdict
from pathlib import Path
import uuid

import pandas as pd
import numpy as np

# HDFS integration
from pyspark.sql import SparkSession
from pyspark.ml import Pipeline, PipelineModel

# Import our components
from config_manager import MLTrainingConfigManager, get_ml_config_manager
from model_trainer import TrainedModel, ModelMetrics

logger = logging.getLogger(__name__)


@dataclass
class ModelVersion:
    """Represents a version of a model"""
    version_id: str
    version_number: str
    model_name: str
    model_type: str
    created_at: datetime
    created_by: str
    description: str
    tags: List[str]
    parent_version: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = asdict(self)
        result["created_at"] = self.created_at.isoformat()
        return result


@dataclass 
class ModelMetadata:
    """Comprehensive model metadata"""
    model_id: str
    model_name: str
    model_type: str
    version: ModelVersion
    metrics: ModelMetrics
    hyperparameters: Dict[str, Any]
    feature_columns: List[str]
    target_columns: List[str]
    training_metadata: Dict[str, Any]
    data_schema: Dict[str, Any]
    model_size_mb: float
    model_hash: str
    dependencies: Dict[str, str]
    deployment_info: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = asdict(self)
        result["version"] = self.version.to_dict()
        result["metrics"] = self.metrics.to_dict()
        return result


class ModelVersionManager:
    """Manages model versioning and lineage"""
    
    def __init__(self, config: MLTrainingConfigManager):
        self.config = config
        self.version_registry: Dict[str, List[ModelVersion]] = {}
        self._load_version_registry()
    
    def _load_version_registry(self):
        """Load existing version registry"""
        registry_path = self._get_registry_path()
        if os.path.exists(registry_path):
            try:
                with open(registry_path, 'r') as f:
                    registry_data = json.load(f)
                
                for model_name, versions in registry_data.items():
                    self.version_registry[model_name] = []
                    for version_data in versions:
                        version_data["created_at"] = datetime.fromisoformat(version_data["created_at"])
                        version = ModelVersion(**version_data)
                        self.version_registry[model_name].append(version)
                        
                logger.info(f"Loaded version registry with {len(self.version_registry)} models")
            except Exception as e:
                logger.error(f"Failed to load version registry: {str(e)}")
                self.version_registry = {}
    
    def _save_version_registry(self):
        """Save version registry"""
        registry_path = self._get_registry_path()
        os.makedirs(os.path.dirname(registry_path), exist_ok=True)
        
        try:
            registry_data = {}
            for model_name, versions in self.version_registry.items():
                registry_data[model_name] = [version.to_dict() for version in versions]
            
            with open(registry_path, 'w') as f:
                json.dump(registry_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save version registry: {str(e)}")
    
    def _get_registry_path(self) -> str:
        """Get path to version registry file"""
        local_path = self.config.model_persistence.local_model_path
        return os.path.join(local_path, "model_version_registry.json")
    
    def create_new_version(self, model_name: str, model_type: str, 
                          description: str = "", tags: List[str] = None,
                          parent_version: str = None, created_by: str = "system") -> ModelVersion:
        """
        Create a new model version
        
        Args:
            model_name: Name of the model
            model_type: Type of the model
            description: Version description
            tags: Version tags
            parent_version: Parent version ID (for lineage)
            created_by: Who created this version
            
        Returns:
            New model version
        """
        # Generate version ID
        version_id = str(uuid.uuid4())
        
        # Determine version number
        if model_name not in self.version_registry:
            self.version_registry[model_name] = []
        
        existing_versions = self.version_registry[model_name]
        
        if self.config.model_persistence.versioning.version_format == "semantic":
            # Semantic versioning (v1.0.0, v1.1.0, etc.)
            if not existing_versions:
                version_number = "v1.0.0"
            else:
                # Get latest version and increment
                latest_version = existing_versions[-1]
                parts = latest_version.version_number.replace('v', '').split('.')
                major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
                version_number = f"v{major}.{minor + 1}.0"
        else:
            # Sequential versioning (v1, v2, etc.)
            version_number = f"v{len(existing_versions) + 1}"
        
        # Create version
        version = ModelVersion(
            version_id=version_id,
            version_number=version_number,
            model_name=model_name,
            model_type=model_type,
            created_at=datetime.now(),
            created_by=created_by,
            description=description,
            tags=tags or [],
            parent_version=parent_version
        )
        
        # Add to registry
        self.version_registry[model_name].append(version)
        self._save_version_registry()
        
        logger.info(f"Created new version {version_number} for model {model_name}")
        return version
    
    def get_latest_version(self, model_name: str) -> Optional[ModelVersion]:
        """Get the latest version of a model"""
        if model_name not in self.version_registry or not self.version_registry[model_name]:
            return None
        
        return self.version_registry[model_name][-1]
    
    def get_version(self, model_name: str, version_number: str) -> Optional[ModelVersion]:
        """Get a specific version of a model"""
        if model_name not in self.version_registry:
            return None
        
        for version in self.version_registry[model_name]:
            if version.version_number == version_number:
                return version
        
        return None
    
    def list_versions(self, model_name: str) -> List[ModelVersion]:
        """List all versions of a model"""
        return self.version_registry.get(model_name, [])
    
    def list_all_models(self) -> List[str]:
        """List all model names"""
        return list(self.version_registry.keys())


class HDFSModelStorage:
    """Handles model storage in HDFS"""
    
    def __init__(self, config: MLTrainingConfigManager, spark_session: Optional[SparkSession] = None):
        self.config = config
        self.spark = spark_session
        self.hdfs_base_path = config.model_persistence.hdfs_model_path
    
    def save_model_to_hdfs(self, model: Any, model_path: str) -> bool:
        """
        Save model to HDFS
        
        Args:
            model: Model to save
            model_path: HDFS path to save model
            
        Returns:
            Success status
        """
        try:
            if hasattr(model, 'save'):
                # Spark ML models
                model.save(model_path)
            else:
                # Scikit-learn models - save to local first, then copy to HDFS
                local_temp_path = f"/tmp/model_{uuid.uuid4().hex}.pkl"
                
                if self.config.model_persistence.model_format == "pickle":
                    with open(local_temp_path, 'wb') as f:
                        pickle.dump(model, f)
                elif self.config.model_persistence.model_format == "joblib":
                    joblib.dump(model, local_temp_path)
                
                # Copy to HDFS (would require HDFS client)
                # For now, just copy to configured path
                hdfs_local_path = model_path.replace("hdfs://localhost:9000", "")
                os.makedirs(os.path.dirname(hdfs_local_path), exist_ok=True)
                shutil.copy2(local_temp_path, hdfs_local_path)
                
                # Clean up temp file
                os.remove(local_temp_path)
            
            logger.info(f"Model saved to HDFS: {model_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save model to HDFS: {str(e)}")
            return False
    
    def load_model_from_hdfs(self, model_path: str) -> Optional[Any]:
        """
        Load model from HDFS
        
        Args:
            model_path: HDFS path to model
            
        Returns:
            Loaded model or None if failed
        """
        try:
            if model_path.endswith('.pkl') or 'pickle' in model_path:
                # Pickle format
                local_path = model_path.replace("hdfs://localhost:9000", "")
                with open(local_path, 'rb') as f:
                    model = pickle.load(f)
            elif model_path.endswith('.joblib') or 'joblib' in model_path:
                # Joblib format
                local_path = model_path.replace("hdfs://localhost:9000", "")
                model = joblib.load(local_path)
            else:
                # Try Spark ML model
                if self.spark:
                    from pyspark.ml import PipelineModel
                    model = PipelineModel.load(model_path)
                else:
                    raise ValueError("Spark session required for Spark ML models")
            
            logger.info(f"Model loaded from HDFS: {model_path}")
            return model
            
        except Exception as e:
            logger.error(f"Failed to load model from HDFS: {str(e)}")
            return None


class ModelPersistenceManager:
    """Main model persistence and versioning manager"""
    
    def __init__(self, config: MLTrainingConfigManager, spark_session: Optional[SparkSession] = None):
        """
        Initialize model persistence manager
        
        Args:
            config: ML training configuration
            spark_session: Optional Spark session
        """
        self.config = config
        self.spark = spark_session
        self.version_manager = ModelVersionManager(config)
        self.hdfs_storage = HDFSModelStorage(config, spark_session)
        self.model_metadata: Dict[str, ModelMetadata] = {}
        
        # Ensure directories exist
        os.makedirs(self.config.model_persistence.local_model_path, exist_ok=True)
        
        logger.info("ModelPersistenceManager initialized")
    
    def save_trained_model(self, trained_model: TrainedModel,
                          feature_columns: List[str],
                          target_columns: List[str],
                          data_schema: Dict[str, Any],
                          description: str = "",
                          tags: List[str] = None,
                          created_by: str = "system") -> str:
        """
        Save a trained model with full metadata and versioning
        
        Args:
            trained_model: Trained model container
            feature_columns: List of feature column names
            target_columns: List of target column names
            data_schema: Schema of training data
            description: Model description
            tags: Model tags
            created_by: Who created the model
            
        Returns:
            Model version ID
        """
        logger.info(f"Saving trained model: {trained_model.model_name}")
        
        # Create new version
        version = self.version_manager.create_new_version(
            model_name=trained_model.model_name,
            model_type=trained_model.model_type,
            description=description,
            tags=tags,
            created_by=created_by
        )
        
        # Calculate model hash
        model_hash = self._calculate_model_hash(trained_model.model)
        
        # Get model size
        model_size_mb = self._get_model_size(trained_model.model)
        
        # Create model metadata
        model_metadata = ModelMetadata(
            model_id=version.version_id,
            model_name=trained_model.model_name,
            model_type=trained_model.model_type,
            version=version,
            metrics=trained_model.metrics,
            hyperparameters=trained_model.hyperparameters,
            feature_columns=feature_columns,
            target_columns=target_columns,
            training_metadata=trained_model.training_metadata,
            data_schema=data_schema,
            model_size_mb=model_size_mb,
            model_hash=model_hash,
            dependencies=self._get_dependencies(),
            deployment_info={}
        )
        
        # Save model artifacts
        self._save_model_artifacts(trained_model, version, model_metadata)
        
        # Store metadata
        self.model_metadata[version.version_id] = model_metadata
        
        logger.info(f"Model {trained_model.model_name} saved with version {version.version_number}")
        return version.version_id
    
    def _save_model_artifacts(self, trained_model: TrainedModel, 
                            version: ModelVersion, metadata: ModelMetadata):
        """Save all model artifacts (model, metadata, etc.)"""
        
        # Create version directory
        version_dir = os.path.join(
            self.config.model_persistence.local_model_path,
            trained_model.model_name,
            version.version_number
        )
        os.makedirs(version_dir, exist_ok=True)
        
        # Save model binary
        model_filename = f"model.{self.config.model_persistence.model_format}"
        model_path = os.path.join(version_dir, model_filename)
        
        if self.config.model_persistence.model_format == "pickle":
            with open(model_path, 'wb') as f:
                pickle.dump(trained_model.model, f)
        elif self.config.model_persistence.model_format == "joblib":
            joblib.dump(trained_model.model, model_path)
        
        # Save metadata
        if self.config.model_persistence.save_metadata:
            metadata_path = os.path.join(version_dir, "metadata.json")
            with open(metadata_path, 'w') as f:
                json.dump(self._convert_for_json(metadata.to_dict()), f, indent=2)
        
        # Save feature importance if available
        if trained_model.feature_importance:
            importance_path = os.path.join(version_dir, "feature_importance.json")
            with open(importance_path, 'w') as f:
                json.dump(trained_model.feature_importance, f, indent=2)
        
        # Save to HDFS if enabled
        hdfs_path = f"{self.config.model_persistence.hdfs_model_path}/{trained_model.model_name}/{version.version_number}"
        self.hdfs_storage.save_model_to_hdfs(trained_model.model, f"{hdfs_path}/{model_filename}")
        
        # Save metadata to HDFS
        if self.config.model_persistence.save_metadata:
            hdfs_metadata_path = f"{hdfs_path}/metadata.json"
            self._save_json_to_hdfs(metadata.to_dict(), hdfs_metadata_path)
    
    def load_model(self, model_name: str, version_number: Optional[str] = None) -> Tuple[Any, ModelMetadata]:
        """
        Load a model with its metadata
        
        Args:
            model_name: Name of the model
            version_number: Version number (latest if not specified)
            
        Returns:
            Tuple of (model, metadata)
        """
        # Get version
        if version_number:
            version = self.version_manager.get_version(model_name, version_number)
        else:
            version = self.version_manager.get_latest_version(model_name)
        
        if not version:
            raise ValueError(f"Model {model_name} version {version_number or 'latest'} not found")
        
        logger.info(f"Loading model {model_name} version {version.version_number}")
        
        # Load model binary
        version_dir = os.path.join(
            self.config.model_persistence.local_model_path,
            model_name,
            version.version_number
        )
        
        model_filename = f"model.{self.config.model_persistence.model_format}"
        model_path = os.path.join(version_dir, model_filename)
        
        if not os.path.exists(model_path):
            # Try loading from HDFS
            hdfs_path = f"{self.config.model_persistence.hdfs_model_path}/{model_name}/{version.version_number}/{model_filename}"
            model = self.hdfs_storage.load_model_from_hdfs(hdfs_path)
        else:
            # Load from local storage
            if self.config.model_persistence.model_format == "pickle":
                with open(model_path, 'rb') as f:
                    model = pickle.load(f)
            elif self.config.model_persistence.model_format == "joblib":
                model = joblib.load(model_path)
        
        # Load metadata
        metadata_path = os.path.join(version_dir, "metadata.json")
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r') as f:
                metadata_dict = json.load(f)
            
            # Reconstruct metadata object (simplified)
            metadata = self._reconstruct_metadata(metadata_dict)
        else:
            metadata = None
        
        logger.info(f"Model {model_name} version {version.version_number} loaded successfully")
        return model, metadata
    
    def list_models(self) -> List[Dict[str, Any]]:
        """List all available models with their versions"""
        models_info = []
        
        for model_name in self.version_manager.list_all_models():
            versions = self.version_manager.list_versions(model_name)
            latest_version = versions[-1] if versions else None
            
            model_info = {
                "model_name": model_name,
                "total_versions": len(versions),
                "latest_version": latest_version.version_number if latest_version else None,
                "created_at": latest_version.created_at.isoformat() if latest_version else None,
                "model_type": latest_version.model_type if latest_version else None
            }
            
            models_info.append(model_info)
        
        return models_info
    
    def delete_model_version(self, model_name: str, version_number: str) -> bool:
        """
        Delete a specific model version
        
        Args:
            model_name: Name of the model
            version_number: Version to delete
            
        Returns:
            Success status
        """
        try:
            # Remove from version registry
            if model_name in self.version_manager.version_registry:
                versions = self.version_manager.version_registry[model_name]
                self.version_manager.version_registry[model_name] = [
                    v for v in versions if v.version_number != version_number
                ]
                self.version_manager._save_version_registry()
            
            # Remove local files
            version_dir = os.path.join(
                self.config.model_persistence.local_model_path,
                model_name,
                version_number
            )
            if os.path.exists(version_dir):
                shutil.rmtree(version_dir)
            
            # Remove from HDFS (simplified)
            hdfs_path = f"{self.config.model_persistence.hdfs_model_path}/{model_name}/{version_number}"
            hdfs_local_path = hdfs_path.replace("hdfs://localhost:9000", "")
            if os.path.exists(hdfs_local_path):
                shutil.rmtree(hdfs_local_path)
            
            logger.info(f"Deleted model {model_name} version {version_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete model version: {str(e)}")
            return False
    
    def compare_model_versions(self, model_name: str, 
                             version1: str, version2: str) -> Dict[str, Any]:
        """
        Compare two versions of a model
        
        Args:
            model_name: Name of the model
            version1: First version to compare
            version2: Second version to compare
            
        Returns:
            Comparison results
        """
        # Load both versions' metadata
        v1 = self.version_manager.get_version(model_name, version1)
        v2 = self.version_manager.get_version(model_name, version2)
        
        if not v1 or not v2:
            raise ValueError("One or both versions not found")
        
        # Load metadata
        try:
            _, metadata1 = self.load_model(model_name, version1)
            _, metadata2 = self.load_model(model_name, version2)
        except Exception as e:
            logger.error(f"Could not load metadata for comparison: {str(e)}")
            return {"error": str(e)}
        
        comparison = {
            "model_name": model_name,
            "version_comparison": {
                version1: v1.to_dict(),
                version2: v2.to_dict()
            },
            "metrics_comparison": {},
            "hyperparameter_differences": {},
            "feature_differences": {}
        }
        
        if metadata1 and metadata2:
            # Compare metrics
            comparison["metrics_comparison"] = {
                version1: metadata1.metrics.to_dict(),
                version2: metadata2.metrics.to_dict()
            }
            
            # Compare hyperparameters
            comparison["hyperparameter_differences"] = self._compare_dicts(
                metadata1.hyperparameters, metadata2.hyperparameters
            )
            
            # Compare features
            comparison["feature_differences"] = {
                "added_features": list(set(metadata2.feature_columns) - set(metadata1.feature_columns)),
                "removed_features": list(set(metadata1.feature_columns) - set(metadata2.feature_columns)),
                "common_features": list(set(metadata1.feature_columns) & set(metadata2.feature_columns))
            }
        
        return comparison
    
    def export_model(self, model_name: str, version_number: str, 
                    export_format: str, output_path: str) -> str:
        """
        Export model in different formats
        
        Args:
            model_name: Name of the model
            version_number: Version to export
            export_format: Export format ('onnx', 'pmml', 'tensorflow', etc.)
            output_path: Output path for exported model
            
        Returns:
            Path to exported model
        """
        model, metadata = self.load_model(model_name, version_number)
        
        if export_format == "onnx":
            return self._export_to_onnx(model, metadata, output_path)
        elif export_format == "pmml":
            return self._export_to_pmml(model, metadata, output_path)
        elif export_format == "json":
            return self._export_to_json(model, metadata, output_path)
        else:
            raise ValueError(f"Unsupported export format: {export_format}")
    
    def _calculate_model_hash(self, model: Any) -> str:
        """Calculate hash of model for change detection"""
        try:
            if hasattr(model, '__getstate__'):
                model_bytes = pickle.dumps(model.__getstate__())
            else:
                model_bytes = pickle.dumps(model)
            
            return hashlib.sha256(model_bytes).hexdigest()
        except Exception:
            return "unknown"
    
    def _get_model_size(self, model: Any) -> float:
        """Get model size in MB"""
        try:
            import sys
            size_bytes = sys.getsizeof(pickle.dumps(model))
            return size_bytes / (1024 * 1024)  # Convert to MB
        except Exception:
            return 0.0
    
    def _get_dependencies(self) -> Dict[str, str]:
        """Get current package dependencies"""
        try:
            import pkg_resources
            dependencies = {}
            for pkg in pkg_resources.working_set:
                dependencies[pkg.project_name] = pkg.version
            return dependencies
        except Exception:
            return {}
    
    def _save_json_to_hdfs(self, data: Dict[str, Any], hdfs_path: str):
        """Save JSON data to HDFS (simplified implementation)"""
        local_path = hdfs_path.replace("hdfs://localhost:9000", "")
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        with open(local_path, 'w') as f:
            json.dump(self._convert_for_json(data), f, indent=2)
    
    def _convert_for_json(self, obj: Any) -> Any:
        """Convert objects for JSON serialization"""
        if isinstance(obj, dict):
            return {key: self._convert_for_json(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_for_json(item) for item in obj]
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (np.integer, np.floating)):
            return obj.item()
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif pd.isna(obj):
            return None
        else:
            return obj
    
    def _reconstruct_metadata(self, metadata_dict: Dict[str, Any]) -> ModelMetadata:
        """Reconstruct metadata object from dictionary (simplified)"""
        # This is a simplified reconstruction - would need more robust implementation
        return None
    
    def _compare_dicts(self, dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
        """Compare two dictionaries and return differences"""
        differences = {
            "added": {},
            "removed": {},
            "changed": {}
        }
        
        all_keys = set(dict1.keys()) | set(dict2.keys())
        
        for key in all_keys:
            if key not in dict1:
                differences["added"][key] = dict2[key]
            elif key not in dict2:
                differences["removed"][key] = dict1[key]
            elif dict1[key] != dict2[key]:
                differences["changed"][key] = {
                    "old": dict1[key],
                    "new": dict2[key]
                }
        
        return differences
    
    def _export_to_onnx(self, model: Any, metadata: ModelMetadata, output_path: str) -> str:
        """Export model to ONNX format"""
        # Placeholder - would require skl2onnx or similar
        logger.warning("ONNX export not implemented")
        return output_path
    
    def _export_to_pmml(self, model: Any, metadata: ModelMetadata, output_path: str) -> str:
        """Export model to PMML format"""
        # Placeholder - would require sklearn2pmml or similar
        logger.warning("PMML export not implemented")
        return output_path
    
    def _export_to_json(self, model: Any, metadata: ModelMetadata, output_path: str) -> str:
        """Export model metadata to JSON"""
        try:
            export_data = {
                "model_metadata": metadata.to_dict() if metadata else {},
                "export_timestamp": datetime.now().isoformat(),
                "export_format": "json"
            }
            
            with open(output_path, 'w') as f:
                json.dump(self._convert_for_json(export_data), f, indent=2)
            
            return output_path
        except Exception as e:
            logger.error(f"Failed to export to JSON: {str(e)}")
            raise
    
    def get_model_registry_status(self) -> Dict[str, Any]:
        """Get overall status of model registry"""
        total_models = len(self.version_manager.list_all_models())
        total_versions = sum(len(versions) for versions in self.version_manager.version_registry.values())
        
        # Calculate storage usage
        local_path = Path(self.config.model_persistence.local_model_path)
        if local_path.exists():
            total_size = sum(f.stat().st_size for f in local_path.rglob('*') if f.is_file())
            storage_mb = total_size / (1024 * 1024)
        else:
            storage_mb = 0.0
        
        return {
            "total_models": total_models,
            "total_versions": total_versions,
            "storage_usage_mb": storage_mb,
            "registry_path": self.version_manager._get_registry_path(),
            "hdfs_enabled": bool(self.config.model_persistence.hdfs_model_path),
            "versioning_enabled": self.config.model_persistence.versioning.enabled
        }


if __name__ == "__main__":
    # Example usage
    config = get_ml_config_manager()
    persistence_manager = ModelPersistenceManager(config)
    
    print("ModelPersistenceManager initialized successfully")
    print(f"Local model path: {config.model_persistence.local_model_path}")
    print(f"HDFS model path: {config.model_persistence.hdfs_model_path}")
    print(f"Model format: {config.model_persistence.model_format}")
    print(f"Versioning enabled: {config.model_persistence.versioning.enabled}")
    
    # Show registry status
    status = persistence_manager.get_model_registry_status()
    print(f"Registry status: {status}")
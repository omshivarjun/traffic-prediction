"""
Feature Engineering Pipeline

This module provides a comprehensive feature engineering pipeline that orchestrates
temporal and spatial feature extraction, data preprocessing, and feature storage.
It integrates with HDFS for data input/output and handles the complete ML feature preparation workflow.
"""

import os
import json
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Union, Any
from dataclasses import dataclass, asdict
from pathlib import Path

from pyspark.sql import SparkSession, DataFrame as SparkDataFrame
from pyspark.sql.functions import (
    col, when, isnan, isnull, coalesce, lit, count, sum as spark_sum,
    mean, stddev, min as spark_min, max as spark_max, percentile_approx
)
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, FloatType, DoubleType, TimestampType
from pyspark.ml.feature import VectorAssembler, StandardScaler, MinMaxScaler, RobustScaler
from pyspark.ml.feature import StringIndexer, OneHotEncoder, PCA, VectorSizeHint
from pyspark.ml import Pipeline, PipelineModel
from pyspark.ml.evaluation import RegressionEvaluator

# Import our feature engineering modules
from temporal_features import TemporalFeatureExtractor, TemporalFeatureConfig
from spatial_features import SpatialFeatureExtractor, SpatialFeatureConfig

logger = logging.getLogger(__name__)

@dataclass
class FeaturePipelineConfig:
    """Configuration for the complete feature engineering pipeline"""
    # Data source configuration
    hdfs_input_path: str = "hdfs://localhost:9000/traffic/processed"
    hdfs_output_path: str = "hdfs://localhost:9000/traffic/features"
    sensor_metadata_path: str = "data/raw/metr_la_sensor_metadata.csv"
    
    # Feature engineering configuration
    temporal_config: TemporalFeatureConfig = None
    spatial_config: SpatialFeatureConfig = None
    
    # Pipeline processing configuration
    enable_temporal_features: bool = True
    enable_spatial_features: bool = True
    enable_feature_scaling: bool = True
    enable_dimensionality_reduction: bool = False
    
    # Data quality and preprocessing
    missing_value_threshold: float = 0.1  # Drop columns with >10% missing values
    outlier_detection_method: str = "iqr"  # "iqr", "zscore", "isolation_forest"
    outlier_threshold: float = 3.0
    
    # Feature selection
    enable_feature_selection: bool = True
    feature_selection_method: str = "variance"  # "variance", "correlation", "mutual_info"
    variance_threshold: float = 0.01
    correlation_threshold: float = 0.95
    
    # Scaling and normalization
    scaling_method: str = "standard"  # "standard", "minmax", "robust", "none"
    
    # Output configuration
    feature_file_format: str = "parquet"  # "parquet", "csv", "orc"
    enable_feature_metadata: bool = True
    enable_data_validation: bool = True
    
    # Performance optimization
    repartition_size: int = 200
    cache_intermediate_results: bool = True
    
    def __post_init__(self):
        if self.temporal_config is None:
            self.temporal_config = TemporalFeatureConfig()
        if self.spatial_config is None:
            self.spatial_config = SpatialFeatureConfig()

class DataQualityAnalyzer:
    """Analyzes and reports on data quality issues"""
    
    def __init__(self, spark_session: SparkSession):
        self.spark = spark_session
        self.logger = logging.getLogger(__name__)
    
    def analyze_data_quality(self, df: SparkDataFrame) -> Dict[str, Any]:
        """
        Perform comprehensive data quality analysis
        
        Args:
            df: Input DataFrame
            
        Returns:
            Dictionary containing quality metrics
        """
        self.logger.info("Analyzing data quality")
        
        total_rows = df.count()
        quality_report = {
            "total_rows": total_rows,
            "total_columns": len(df.columns),
            "missing_value_analysis": {},
            "data_type_analysis": {},
            "outlier_analysis": {},
            "duplicate_analysis": {},
            "completeness_score": 0.0,
            "consistency_score": 0.0,
            "overall_quality_score": 0.0
        }
        
        # Missing value analysis
        for column in df.columns:
            null_count = df.filter(col(column).isNull() | isnan(col(column))).count()
            missing_percentage = (null_count / total_rows) * 100 if total_rows > 0 else 0
            
            quality_report["missing_value_analysis"][column] = {
                "null_count": null_count,
                "missing_percentage": missing_percentage
            }
        
        # Data type analysis
        for column, dtype in df.dtypes:
            quality_report["data_type_analysis"][column] = dtype
        
        # Duplicate analysis
        distinct_rows = df.distinct().count()
        duplicate_count = total_rows - distinct_rows
        quality_report["duplicate_analysis"] = {
            "total_duplicates": duplicate_count,
            "duplicate_percentage": (duplicate_count / total_rows) * 100 if total_rows > 0 else 0
        }
        
        # Calculate completeness score
        avg_missing_percentage = np.mean([
            metrics["missing_percentage"] 
            for metrics in quality_report["missing_value_analysis"].values()
        ])
        quality_report["completeness_score"] = max(0, 100 - avg_missing_percentage)
        
        # Calculate consistency score (placeholder - would implement more sophisticated checks)
        quality_report["consistency_score"] = 90.0  # Simplified
        
        # Overall quality score
        quality_report["overall_quality_score"] = (
            quality_report["completeness_score"] * 0.4 +
            quality_report["consistency_score"] * 0.3 +
            max(0, 100 - quality_report["duplicate_analysis"]["duplicate_percentage"]) * 0.3
        )
        
        return quality_report
    
    def detect_outliers(self, df: SparkDataFrame, 
                       numeric_columns: List[str],
                       method: str = "iqr",
                       threshold: float = 3.0) -> SparkDataFrame:
        """
        Detect and flag outliers in numeric columns
        
        Args:
            df: Input DataFrame
            numeric_columns: List of numeric columns to analyze
            method: Outlier detection method
            threshold: Threshold for outlier detection
            
        Returns:
            DataFrame with outlier flags
        """
        self.logger.info(f"Detecting outliers using {method} method")
        
        for column in numeric_columns:
            if method == "iqr":
                # Calculate IQR bounds
                quantiles = df.select(
                    percentile_approx(col(column), 0.25).alias("q1"),
                    percentile_approx(col(column), 0.75).alias("q3")
                ).collect()[0]
                
                q1, q3 = quantiles["q1"], quantiles["q3"]
                iqr = q3 - q1
                lower_bound = q1 - 1.5 * iqr
                upper_bound = q3 + 1.5 * iqr
                
                df = df.withColumn(f"{column}_outlier",
                                 when((col(column) < lower_bound) | (col(column) > upper_bound), 1)
                                 .otherwise(0))
                
            elif method == "zscore":
                # Calculate z-score bounds
                stats = df.select(
                    mean(col(column)).alias("mean"),
                    stddev(col(column)).alias("std")
                ).collect()[0]
                
                col_mean, col_std = stats["mean"], stats["std"]
                
                df = df.withColumn(f"{column}_zscore", 
                                 (col(column) - lit(col_mean)) / lit(col_std))
                df = df.withColumn(f"{column}_outlier",
                                 when((col(f"{column}_zscore") > threshold) | 
                                     (col(f"{column}_zscore") < -threshold), 1)
                                 .otherwise(0))
        
        return df

class FeatureValidator:
    """Validates feature engineering results"""
    
    def __init__(self, spark_session: SparkSession):
        self.spark = spark_session
        self.logger = logging.getLogger(__name__)
    
    def validate_features(self, df: SparkDataFrame, 
                         feature_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate engineered features
        
        Args:
            df: DataFrame with engineered features
            feature_metadata: Metadata about expected features
            
        Returns:
            Validation report
        """
        self.logger.info("Validating engineered features")
        
        validation_report = {
            "feature_validation": {},
            "schema_validation": {},
            "data_integrity": {},
            "validation_passed": True,
            "validation_errors": []
        }
        
        # Check if expected features are present
        expected_columns = set()
        if "temporal_features" in feature_metadata:
            for feature_category in feature_metadata["temporal_features"].values():
                if isinstance(feature_category, list):
                    expected_columns.update(feature_category)
        
        if "spatial_features" in feature_metadata:
            for feature_category in feature_metadata["spatial_features"].values():
                if isinstance(feature_category, list):
                    expected_columns.update(feature_category)
        
        actual_columns = set(df.columns)
        
        # Check for missing features
        missing_features = expected_columns - actual_columns
        if missing_features:
            validation_report["validation_errors"].append(f"Missing features: {missing_features}")
            validation_report["validation_passed"] = False
        
        # Check data types
        for column, dtype in df.dtypes:
            validation_report["schema_validation"][column] = dtype
        
        # Check for infinite or null values in feature columns
        feature_columns = [col for col in df.columns if any(suffix in col for suffix in 
                          ['_lag_', '_rolling_', '_neighbor_', '_upstream_', '_downstream_'])]
        
        for column in feature_columns:
            null_count = df.filter(col(column).isNull() | isnan(col(column))).count()
            if null_count > 0:
                validation_report["data_integrity"][column] = f"Contains {null_count} null/infinite values"
        
        # Calculate feature statistics
        validation_report["feature_statistics"] = self._calculate_feature_statistics(df, feature_columns)
        
        return validation_report
    
    def _calculate_feature_statistics(self, df: SparkDataFrame, 
                                    feature_columns: List[str]) -> Dict[str, Any]:
        """Calculate basic statistics for feature columns"""
        stats = {}
        
        for column in feature_columns[:10]:  # Limit to first 10 to avoid too much computation
            try:
                column_stats = df.select(
                    count(col(column)).alias("count"),
                    mean(col(column)).alias("mean"),
                    stddev(col(column)).alias("std"),
                    spark_min(col(column)).alias("min"),
                    spark_max(col(column)).alias("max")
                ).collect()[0]
                
                stats[column] = {
                    "count": column_stats["count"],
                    "mean": float(column_stats["mean"]) if column_stats["mean"] else None,
                    "std": float(column_stats["std"]) if column_stats["std"] else None,
                    "min": float(column_stats["min"]) if column_stats["min"] else None,
                    "max": float(column_stats["max"]) if column_stats["max"] else None
                }
            except Exception as e:
                stats[column] = {"error": str(e)}
        
        return stats

class FeaturePipeline:
    """Main feature engineering pipeline orchestrator"""
    
    def __init__(self, config: FeaturePipelineConfig = None):
        self.config = config or FeaturePipelineConfig()
        self.logger = logging.getLogger(__name__)
        
        # Initialize Spark session
        self.spark = self._initialize_spark_session()
        
        # Initialize components
        self.temporal_extractor = None
        self.spatial_extractor = None
        self.quality_analyzer = DataQualityAnalyzer(self.spark)
        self.feature_validator = FeatureValidator(self.spark)
        
        # Load sensor metadata if spatial features are enabled
        if self.config.enable_spatial_features:
            self.sensor_metadata = self._load_sensor_metadata()
        
        # Pipeline results storage
        self.pipeline_metadata = {
            "execution_timestamp": datetime.now().isoformat(),
            "config": asdict(self.config),
            "processing_stages": [],
            "feature_metadata": {},
            "quality_report": {},
            "validation_report": {}
        }
    
    def _initialize_spark_session(self) -> SparkSession:
        """Initialize Spark session with optimal configuration"""
        return SparkSession.builder \
            .appName("TrafficFeatureEngineeringPipeline") \
            .config("spark.sql.adaptive.enabled", "true") \
            .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
            .config("spark.sql.adaptive.skewedJoin.enabled", "true") \
            .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
            .config("spark.sql.execution.arrow.pyspark.enabled", "true") \
            .getOrCreate()
    
    def _load_sensor_metadata(self) -> Optional[pd.DataFrame]:
        """Load sensor metadata for spatial features"""
        try:
            sensor_metadata = pd.read_csv(self.config.sensor_metadata_path)
            self.logger.info(f"Loaded metadata for {len(sensor_metadata)} sensors")
            return sensor_metadata
        except Exception as e:
            self.logger.warning(f"Could not load sensor metadata: {e}")
            return None
    
    def load_data(self, input_path: Optional[str] = None) -> SparkDataFrame:
        """
        Load data from HDFS or local storage
        
        Args:
            input_path: Optional override for input path
            
        Returns:
            Loaded DataFrame
        """
        path = input_path or self.config.hdfs_input_path
        self.logger.info(f"Loading data from: {path}")
        
        try:
            if path.endswith(".parquet") or "parquet" in path:
                df = self.spark.read.parquet(path)
            elif path.endswith(".csv") or "csv" in path:
                df = self.spark.read.option("header", "true").option("inferSchema", "true").csv(path)
            else:
                # Try parquet first, then CSV
                try:
                    df = self.spark.read.parquet(path)
                except:
                    df = self.spark.read.option("header", "true").option("inferSchema", "true").csv(path)
            
            self.logger.info(f"Loaded {df.count()} rows with {len(df.columns)} columns")
            return df.repartition(self.config.repartition_size)
            
        except Exception as e:
            self.logger.error(f"Error loading data: {e}")
            raise
    
    def preprocess_data(self, df: SparkDataFrame) -> SparkDataFrame:
        """
        Preprocess data before feature engineering
        
        Args:
            df: Input DataFrame
            
        Returns:
            Preprocessed DataFrame
        """
        self.logger.info("Preprocessing data")
        
        # Data quality analysis
        quality_report = self.quality_analyzer.analyze_data_quality(df)
        self.pipeline_metadata["quality_report"] = quality_report
        
        # Handle missing values
        df = self._handle_missing_values(df)
        
        # Detect and handle outliers
        numeric_columns = [col_name for col_name, dtype in df.dtypes 
                          if dtype in ['int', 'bigint', 'float', 'double']]
        df = self.quality_analyzer.detect_outliers(
            df, numeric_columns, 
            self.config.outlier_detection_method, 
            self.config.outlier_threshold
        )
        
        # Data type conversions
        df = self._standardize_data_types(df)
        
        self.pipeline_metadata["processing_stages"].append({
            "stage": "preprocessing",
            "timestamp": datetime.now().isoformat(),
            "rows_processed": df.count(),
            "columns_after": len(df.columns)
        })
        
        return df
    
    def extract_temporal_features(self, df: SparkDataFrame) -> SparkDataFrame:
        """
        Extract temporal features
        
        Args:
            df: Input DataFrame
            
        Returns:
            DataFrame with temporal features
        """
        if not self.config.enable_temporal_features:
            self.logger.info("Temporal features disabled, skipping")
            return df
        
        self.logger.info("Extracting temporal features")
        
        # Initialize temporal extractor
        if self.temporal_extractor is None:
            self.temporal_extractor = TemporalFeatureExtractor(self.spark, self.config.temporal_config)
        
        # Extract features
        df = self.temporal_extractor.extract_all_temporal_features(df)
        
        # Store metadata
        temporal_metadata = self.temporal_extractor.get_feature_metadata()
        self.pipeline_metadata["feature_metadata"]["temporal"] = temporal_metadata
        
        self.pipeline_metadata["processing_stages"].append({
            "stage": "temporal_features",
            "timestamp": datetime.now().isoformat(),
            "rows_processed": df.count(),
            "columns_after": len(df.columns)
        })
        
        return df
    
    def extract_spatial_features(self, df: SparkDataFrame) -> SparkDataFrame:
        """
        Extract spatial features
        
        Args:
            df: Input DataFrame
            
        Returns:
            DataFrame with spatial features
        """
        if not self.config.enable_spatial_features or self.sensor_metadata is None:
            self.logger.info("Spatial features disabled or no sensor metadata, skipping")
            return df
        
        self.logger.info("Extracting spatial features")
        
        # Initialize spatial extractor
        if self.spatial_extractor is None:
            self.spatial_extractor = SpatialFeatureExtractor(
                self.spark, self.sensor_metadata, self.config.spatial_config
            )
        
        # Extract features
        df = self.spatial_extractor.extract_all_spatial_features(df)
        
        # Store metadata
        spatial_metadata = self.spatial_extractor.get_spatial_feature_metadata()
        self.pipeline_metadata["feature_metadata"]["spatial"] = spatial_metadata
        
        self.pipeline_metadata["processing_stages"].append({
            "stage": "spatial_features",
            "timestamp": datetime.now().isoformat(),
            "rows_processed": df.count(),
            "columns_after": len(df.columns)
        })
        
        return df
    
    def perform_feature_selection(self, df: SparkDataFrame) -> SparkDataFrame:
        """
        Perform feature selection to reduce dimensionality
        
        Args:
            df: DataFrame with all features
            
        Returns:
            DataFrame with selected features
        """
        if not self.config.enable_feature_selection:
            return df
        
        self.logger.info("Performing feature selection")
        
        # Get feature columns (exclude ID and target columns)
        feature_columns = [col_name for col_name in df.columns 
                          if col_name not in ['sensor_id', 'timestamp', 'speed_mph', 'volume_vehicles_per_hour']]
        
        if self.config.feature_selection_method == "variance":
            df = self._variance_threshold_selection(df, feature_columns)
        elif self.config.feature_selection_method == "correlation":
            df = self._correlation_threshold_selection(df, feature_columns)
        
        return df
    
    def scale_features(self, df: SparkDataFrame) -> Tuple[SparkDataFrame, Optional[PipelineModel]]:
        """
        Scale features using the specified method
        
        Args:
            df: Input DataFrame
            
        Returns:
            Tuple of (scaled DataFrame, fitted scaler model)
        """
        if not self.config.enable_feature_scaling or self.config.scaling_method == "none":
            return df, None
        
        self.logger.info(f"Scaling features using {self.config.scaling_method} method")
        
        # Get numeric feature columns
        feature_columns = [col_name for col_name, dtype in df.dtypes 
                          if dtype in ['int', 'bigint', 'float', 'double'] 
                          and col_name not in ['sensor_id', 'timestamp']]
        
        # Create vector assembler
        assembler = VectorAssembler(inputCols=feature_columns, outputCol="features_vector")
        
        # Create scaler
        if self.config.scaling_method == "standard":
            scaler = StandardScaler(inputCol="features_vector", outputCol="scaled_features",
                                  withStd=True, withMean=True)
        elif self.config.scaling_method == "minmax":
            scaler = MinMaxScaler(inputCol="features_vector", outputCol="scaled_features")
        elif self.config.scaling_method == "robust":
            scaler = RobustScaler(inputCol="features_vector", outputCol="scaled_features")
        else:
            raise ValueError(f"Unknown scaling method: {self.config.scaling_method}")
        
        # Create and fit pipeline
        pipeline = Pipeline(stages=[assembler, scaler])
        scaler_model = pipeline.fit(df)
        
        # Transform data
        df_scaled = scaler_model.transform(df)
        
        return df_scaled, scaler_model
    
    def save_features(self, df: SparkDataFrame, output_path: Optional[str] = None):
        """
        Save engineered features to storage
        
        Args:
            df: DataFrame with features to save
            output_path: Optional override for output path
        """
        path = output_path or self.config.hdfs_output_path
        self.logger.info(f"Saving features to: {path}")
        
        # Save main feature data
        if self.config.feature_file_format == "parquet":
            df.write.mode("overwrite").parquet(path)
        elif self.config.feature_file_format == "csv":
            df.coalesce(1).write.mode("overwrite").option("header", "true").csv(path)
        elif self.config.feature_file_format == "orc":
            df.write.mode("overwrite").orc(path)
        
        # Save metadata if enabled
        if self.config.enable_feature_metadata:
            metadata_path = f"{path}_metadata.json"
            with open(metadata_path.replace("hdfs://localhost:9000/", ""), "w") as f:
                json.dump(self.pipeline_metadata, f, indent=2)
    
    def run_pipeline(self, input_path: Optional[str] = None, 
                    output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Run the complete feature engineering pipeline
        
        Args:
            input_path: Optional override for input path
            output_path: Optional override for output path
            
        Returns:
            Pipeline execution report
        """
        self.logger.info("Starting feature engineering pipeline")
        start_time = datetime.now()
        
        try:
            # Load data
            df = self.load_data(input_path)
            
            if self.config.cache_intermediate_results:
                df.cache()
            
            # Preprocess data
            df = self.preprocess_data(df)
            
            # Extract temporal features
            df = self.extract_temporal_features(df)
            
            # Extract spatial features
            df = self.extract_spatial_features(df)
            
            # Perform feature selection
            df = self.perform_feature_selection(df)
            
            # Scale features
            df, scaler_model = self.scale_features(df)
            
            # Validate features
            if self.config.enable_data_validation:
                validation_report = self.feature_validator.validate_features(
                    df, self.pipeline_metadata["feature_metadata"]
                )
                self.pipeline_metadata["validation_report"] = validation_report
            
            # Save results
            self.save_features(df, output_path)
            
            # Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Create final report
            final_report = {
                "pipeline_success": True,
                "execution_time_seconds": execution_time,
                "final_row_count": df.count(),
                "final_column_count": len(df.columns),
                "metadata": self.pipeline_metadata
            }
            
            self.logger.info(f"Pipeline completed successfully in {execution_time:.2f} seconds")
            return final_report
            
        except Exception as e:
            self.logger.error(f"Pipeline failed: {e}")
            return {
                "pipeline_success": False,
                "error": str(e),
                "execution_time_seconds": (datetime.now() - start_time).total_seconds(),
                "metadata": self.pipeline_metadata
            }
        
        finally:
            # Clean up
            if hasattr(self, 'spark'):
                self.spark.catalog.clearCache()
    
    def _handle_missing_values(self, df: SparkDataFrame) -> SparkDataFrame:
        """Handle missing values in the dataset"""
        # Simple forward fill for now - can be enhanced
        for column in df.columns:
            if column not in ['sensor_id', 'timestamp']:
                df = df.withColumn(column, coalesce(col(column), lit(0.0)))
        return df
    
    def _standardize_data_types(self, df: SparkDataFrame) -> SparkDataFrame:
        """Standardize data types"""
        # Ensure timestamp is proper type
        if 'timestamp' in df.columns:
            df = df.withColumn('timestamp', col('timestamp').cast('timestamp'))
        
        return df
    
    def _variance_threshold_selection(self, df: SparkDataFrame, 
                                    feature_columns: List[str]) -> SparkDataFrame:
        """Remove features with low variance"""
        columns_to_keep = []
        
        for column in feature_columns:
            variance = df.select(stddev(col(column)).alias("std")).collect()[0]["std"]
            if variance is not None and variance > self.config.variance_threshold:
                columns_to_keep.append(column)
        
        # Keep original non-feature columns plus selected features
        all_columns_to_keep = [col for col in df.columns if col not in feature_columns] + columns_to_keep
        return df.select(*all_columns_to_keep)
    
    def _correlation_threshold_selection(self, df: SparkDataFrame, 
                                       feature_columns: List[str]) -> SparkDataFrame:
        """Remove highly correlated features"""
        # This is a simplified implementation - would need more sophisticated correlation analysis
        return df  # Placeholder
    
    def close(self):
        """Clean up resources"""
        if hasattr(self, 'spark'):
            self.spark.stop()

if __name__ == "__main__":
    # Example usage
    
    # Configuration
    config = FeaturePipelineConfig(
        enable_temporal_features=True,
        enable_spatial_features=True,
        enable_feature_scaling=True,
        scaling_method="standard",
        hdfs_input_path="data/processed/metr_la_ml_ready.csv",
        hdfs_output_path="data/features/engineered_features",
        sensor_metadata_path="data/raw/metr_la_sensor_metadata.csv"
    )
    
    # Initialize and run pipeline
    pipeline = FeaturePipeline(config)
    
    try:
        report = pipeline.run_pipeline()
        
        print("=== Feature Engineering Pipeline Report ===")
        print(f"Success: {report['pipeline_success']}")
        print(f"Execution Time: {report['execution_time_seconds']:.2f} seconds")
        
        if report['pipeline_success']:
            print(f"Final Rows: {report['final_row_count']}")
            print(f"Final Columns: {report['final_column_count']}")
            
            # Print processing stages
            print("\nProcessing Stages:")
            for stage in report['metadata']['processing_stages']:
                print(f"  {stage['stage']}: {stage['columns_after']} columns")
        else:
            print(f"Error: {report['error']}")
    
    except Exception as e:
        print(f"Pipeline execution failed: {e}")
    
    finally:
        pipeline.close()
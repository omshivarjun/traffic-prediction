"""
Data Loading Pipeline for ML Training

Handles data loading from feature engineering pipeline output,
data splitting, preprocessing, and batch preparation for model training.
Integrates with HDFS storage and feature store.
"""

import os
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Union, Any
from pathlib import Path
import pickle
import warnings
warnings.filterwarnings('ignore')

from pyspark.sql import SparkSession, DataFrame as SparkDataFrame
from pyspark.sql.functions import (
    col, when, isnan, isnull, coalesce, lit, count, sum as spark_sum,
    mean, stddev, min as spark_min, max as spark_max, percentile_approx,
    row_number, monotonically_increasing_id, rand
)
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, FloatType, DoubleType, TimestampType
from pyspark.sql.window import Window
from pyspark.ml.feature import VectorAssembler, StandardScaler, MinMaxScaler, RobustScaler
from pyspark.ml.feature import Imputer

# Scikit-learn for additional preprocessing
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.preprocessing import StandardScaler as SklearnStandardScaler, MinMaxScaler as SklearnMinMaxScaler, RobustScaler as SklearnRobustScaler
from sklearn.impute import SimpleImputer, KNNImputer
from sklearn.feature_selection import VarianceThreshold, SelectKBest, f_regression, mutual_info_regression

# Import configuration manager
from config_manager import MLTrainingConfigManager, get_ml_config_manager

logger = logging.getLogger(__name__)


class DataQualityAnalyzer:
    """Analyzes data quality issues and generates reports"""
    
    def __init__(self, config: MLTrainingConfigManager):
        self.config = config
    
    def analyze_spark_dataframe(self, df: SparkDataFrame) -> Dict[str, Any]:
        """Analyze data quality for Spark DataFrame"""
        logger.info("Analyzing data quality for Spark DataFrame")
        
        total_rows = df.count()
        total_cols = len(df.columns)
        
        quality_report = {
            "total_rows": total_rows,
            "total_columns": total_cols,
            "columns": {},
            "overall_quality_score": 0.0,
            "issues": []
        }
        
        if total_rows == 0:
            quality_report["issues"].append("Dataset is empty")
            return quality_report
        
        # Analyze each column
        for column in df.columns:
            col_stats = self._analyze_column_spark(df, column, total_rows)
            quality_report["columns"][column] = col_stats
            
            # Check for quality issues
            if col_stats["missing_percentage"] > self.config.validation.max_missing_percentage * 100:
                quality_report["issues"].append(f"Column '{column}' has {col_stats['missing_percentage']:.1f}% missing values")
        
        # Calculate overall quality score
        avg_missing = np.mean([col_stats["missing_percentage"] for col_stats in quality_report["columns"].values()])
        quality_report["overall_quality_score"] = max(0.0, 1.0 - (avg_missing / 100.0))
        
        return quality_report
    
    def _analyze_column_spark(self, df: SparkDataFrame, column: str, total_rows: int) -> Dict[str, Any]:
        """Analyze individual column in Spark DataFrame"""
        col_type = dict(df.dtypes)[column]
        
        # Count missing values
        missing_count = df.filter(col(column).isNull() | isnan(col(column))).count()
        missing_percentage = (missing_count / total_rows) * 100 if total_rows > 0 else 0
        
        stats = {
            "data_type": col_type,
            "missing_count": missing_count,
            "missing_percentage": missing_percentage,
            "non_null_count": total_rows - missing_count
        }
        
        # Additional stats for numeric columns
        if col_type in ['int', 'bigint', 'float', 'double']:
            numeric_stats = df.select(
                mean(col(column)).alias("mean"),
                stddev(col(column)).alias("stddev"),
                spark_min(col(column)).alias("min"),
                spark_max(col(column)).alias("max"),
                percentile_approx(col(column), 0.25).alias("q25"),
                percentile_approx(col(column), 0.5).alias("median"),
                percentile_approx(col(column), 0.75).alias("q75")
            ).collect()[0]
            
            stats.update({
                "mean": float(numeric_stats["mean"]) if numeric_stats["mean"] is not None else None,
                "std": float(numeric_stats["stddev"]) if numeric_stats["stddev"] is not None else None,
                "min": float(numeric_stats["min"]) if numeric_stats["min"] is not None else None,
                "max": float(numeric_stats["max"]) if numeric_stats["max"] is not None else None,
                "q25": float(numeric_stats["q25"]) if numeric_stats["q25"] is not None else None,
                "median": float(numeric_stats["median"]) if numeric_stats["median"] is not None else None,
                "q75": float(numeric_stats["q75"]) if numeric_stats["q75"] is not None else None
            })
        
        return stats
    
    def analyze_pandas_dataframe(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze data quality for Pandas DataFrame"""
        logger.info("Analyzing data quality for Pandas DataFrame")
        
        quality_report = {
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "columns": {},
            "overall_quality_score": 0.0,
            "issues": []
        }
        
        if len(df) == 0:
            quality_report["issues"].append("Dataset is empty")
            return quality_report
        
        # Analyze each column
        for column in df.columns:
            col_stats = self._analyze_column_pandas(df, column)
            quality_report["columns"][column] = col_stats
            
            # Check for quality issues
            if col_stats["missing_percentage"] > self.config.validation.max_missing_percentage * 100:
                quality_report["issues"].append(f"Column '{column}' has {col_stats['missing_percentage']:.1f}% missing values")
        
        # Calculate overall quality score
        avg_missing = np.mean([col_stats["missing_percentage"] for col_stats in quality_report["columns"].values()])
        quality_report["overall_quality_score"] = max(0.0, 1.0 - (avg_missing / 100.0))
        
        return quality_report
    
    def _analyze_column_pandas(self, df: pd.DataFrame, column: str) -> Dict[str, Any]:
        """Analyze individual column in Pandas DataFrame"""
        series = df[column]
        missing_count = series.isnull().sum()
        missing_percentage = (missing_count / len(df)) * 100 if len(df) > 0 else 0
        
        stats = {
            "data_type": str(series.dtype),
            "missing_count": int(missing_count),
            "missing_percentage": float(missing_percentage),
            "non_null_count": len(df) - missing_count
        }
        
        # Additional stats for numeric columns
        if pd.api.types.is_numeric_dtype(series):
            numeric_series = series.dropna()
            if len(numeric_series) > 0:
                stats.update({
                    "mean": float(numeric_series.mean()),
                    "std": float(numeric_series.std()),
                    "min": float(numeric_series.min()),
                    "max": float(numeric_series.max()),
                    "q25": float(numeric_series.quantile(0.25)),
                    "median": float(numeric_series.median()),
                    "q75": float(numeric_series.quantile(0.75))
                })
        
        return stats


class DataLoader:
    """Main data loading and preprocessing pipeline"""
    
    def __init__(self, config: MLTrainingConfigManager, spark_session: Optional[SparkSession] = None):
        """
        Initialize data loader
        
        Args:
            config: ML training configuration
            spark_session: Optional Spark session (will create if not provided)
        """
        self.config = config
        self.spark = spark_session or self._create_spark_session()
        self.quality_analyzer = DataQualityAnalyzer(config)
        
        # Initialize preprocessing components
        self.scaler = None
        self.imputer = None
        self.feature_selector = None
        
        # Data storage
        self.feature_columns = []
        self.target_columns = config.data_source.target_columns
        
        logger.info("DataLoader initialized")
    
    def _create_spark_session(self) -> SparkSession:
        """Create Spark session with configuration"""
        builder = SparkSession.builder.appName(self.config.spark_config.app_name)
        
        # Apply Spark configuration
        for key, value in self.config.spark_config.config.items():
            builder = builder.config(key, value)
        
        return builder.getOrCreate()
    
    def load_features_from_hdfs(self, feature_path: Optional[str] = None) -> SparkDataFrame:
        """
        Load features from HDFS feature store
        
        Args:
            feature_path: Optional override for feature path
            
        Returns:
            Spark DataFrame with features
        """
        path = feature_path or self.config.data_source.hdfs_feature_path
        logger.info(f"Loading features from HDFS: {path}")
        
        try:
            # Try different formats
            if path.endswith('.parquet') or '/parquet' in path:
                df = self.spark.read.parquet(path)
            elif path.endswith('.csv'):
                df = self.spark.read.option("header", "true").option("inferSchema", "true").csv(path)
            elif path.endswith('.orc'):
                df = self.spark.read.orc(path)
            else:
                # Default to parquet
                df = self.spark.read.parquet(path)
            
            logger.info(f"Loaded {df.count()} rows with {len(df.columns)} columns")
            return df
        
        except Exception as e:
            logger.error(f"Failed to load features from {path}: {str(e)}")
            raise
    
    def load_features_from_feature_store(self, feature_set_name: str, version: Optional[str] = None) -> SparkDataFrame:
        """
        Load features from feature store
        
        Args:
            feature_set_name: Name of feature set
            version: Optional version (latest if not specified)
            
        Returns:
            Spark DataFrame with features
        """
        logger.info(f"Loading feature set '{feature_set_name}' version '{version or 'latest'}'")
        
        # This would integrate with the feature store from Task 11
        # For now, use the HDFS path approach
        feature_store_path = f"{self.config.data_source.feature_store_path}/{feature_set_name}"
        if version:
            feature_store_path = f"{feature_store_path}/v{version}"
        
        return self.load_features_from_hdfs(feature_store_path)
    
    def preprocess_data(self, df: SparkDataFrame) -> SparkDataFrame:
        """
        Preprocess data according to configuration
        
        Args:
            df: Input DataFrame
            
        Returns:
            Preprocessed DataFrame
        """
        logger.info("Starting data preprocessing")
        
        # Data quality analysis
        quality_report = self.quality_analyzer.analyze_spark_dataframe(df)
        logger.info(f"Data quality score: {quality_report['overall_quality_score']:.3f}")
        
        if quality_report["issues"]:
            logger.warning(f"Data quality issues found: {quality_report['issues']}")
        
        # Handle missing values
        if self.config.data_preprocessing.handle_missing_values:
            df = self._handle_missing_values_spark(df)
        
        # Outlier detection and handling
        if self.config.data_preprocessing.outlier_detection:
            df = self._handle_outliers_spark(df)
        
        # Feature selection
        if self.config.data_preprocessing.feature_selection:
            df = self._feature_selection_spark(df)
        
        logger.info("Data preprocessing completed")
        return df
    
    def _handle_missing_values_spark(self, df: SparkDataFrame) -> SparkDataFrame:
        """Handle missing values in Spark DataFrame"""
        logger.info(f"Handling missing values using {self.config.data_preprocessing.missing_value_strategy} strategy")
        
        if self.config.data_preprocessing.missing_value_strategy == "drop":
            return df.dropna()
        
        elif self.config.data_preprocessing.missing_value_strategy == "interpolate":
            # Simple forward fill for now (more sophisticated interpolation would require time-series ordering)
            numeric_columns = [col_name for col_name, dtype in df.dtypes if dtype in ['int', 'bigint', 'float', 'double']]
            
            for column in numeric_columns:
                mean_value = df.select(mean(col(column))).collect()[0][0]
                if mean_value is not None:
                    df = df.fillna(mean_value, subset=[column])
        
        elif self.config.data_preprocessing.missing_value_strategy == "mean":
            numeric_columns = [col_name for col_name, dtype in df.dtypes if dtype in ['int', 'bigint', 'float', 'double']]
            
            for column in numeric_columns:
                mean_value = df.select(mean(col(column))).collect()[0][0]
                if mean_value is not None:
                    df = df.fillna(mean_value, subset=[column])
        
        return df
    
    def _handle_outliers_spark(self, df: SparkDataFrame) -> SparkDataFrame:
        """Handle outliers in Spark DataFrame"""
        logger.info(f"Handling outliers using {self.config.data_preprocessing.outlier_method} method")
        
        if self.config.data_preprocessing.outlier_method == "iqr":
            return self._handle_outliers_iqr_spark(df)
        elif self.config.data_preprocessing.outlier_method == "zscore":
            return self._handle_outliers_zscore_spark(df)
        
        return df
    
    def _handle_outliers_iqr_spark(self, df: SparkDataFrame) -> SparkDataFrame:
        """Handle outliers using IQR method in Spark"""
        numeric_columns = [col_name for col_name, dtype in df.dtypes 
                          if dtype in ['int', 'bigint', 'float', 'double'] 
                          and col_name not in [self.config.data_source.sensor_id_column, self.config.data_source.timestamp_column]]
        
        for column in numeric_columns:
            # Calculate quartiles
            quartiles = df.select(
                percentile_approx(col(column), 0.25).alias("q25"),
                percentile_approx(col(column), 0.75).alias("q75")
            ).collect()[0]
            
            if quartiles["q25"] is not None and quartiles["q75"] is not None:
                q25, q75 = quartiles["q25"], quartiles["q75"]
                iqr = q75 - q25
                lower_bound = q25 - 1.5 * iqr
                upper_bound = q75 + 1.5 * iqr
                
                # Cap outliers instead of removing them
                df = df.withColumn(
                    column,
                    when(col(column) < lower_bound, lower_bound)
                    .when(col(column) > upper_bound, upper_bound)
                    .otherwise(col(column))
                )
        
        return df
    
    def _handle_outliers_zscore_spark(self, df: SparkDataFrame) -> SparkDataFrame:
        """Handle outliers using Z-score method in Spark"""
        threshold = self.config.data_preprocessing.outlier_threshold
        numeric_columns = [col_name for col_name, dtype in df.dtypes 
                          if dtype in ['int', 'bigint', 'float', 'double'] 
                          and col_name not in [self.config.data_source.sensor_id_column, self.config.data_source.timestamp_column]]
        
        for column in numeric_columns:
            # Calculate mean and standard deviation
            stats = df.select(
                mean(col(column)).alias("mean"),
                stddev(col(column)).alias("stddev")
            ).collect()[0]
            
            if stats["mean"] is not None and stats["stddev"] is not None:
                col_mean, col_std = stats["mean"], stats["stddev"]
                
                if col_std > 0:
                    lower_bound = col_mean - threshold * col_std
                    upper_bound = col_mean + threshold * col_std
                    
                    # Cap outliers
                    df = df.withColumn(
                        column,
                        when(col(column) < lower_bound, lower_bound)
                        .when(col(column) > upper_bound, upper_bound)
                        .otherwise(col(column))
                    )
        
        return df
    
    def _feature_selection_spark(self, df: SparkDataFrame) -> SparkDataFrame:
        """Perform feature selection in Spark"""
        if self.config.data_preprocessing.feature_selection_method == "variance":
            return self._variance_threshold_selection_spark(df)
        
        return df
    
    def _variance_threshold_selection_spark(self, df: SparkDataFrame) -> SparkDataFrame:
        """Remove low-variance features in Spark"""
        numeric_columns = [col_name for col_name, dtype in df.dtypes 
                          if dtype in ['int', 'bigint', 'float', 'double'] 
                          and col_name not in self.config.data_source.feature_exclude_columns]
        
        columns_to_keep = []
        
        for column in numeric_columns:
            variance = df.select(stddev(col(column))).collect()[0][0]
            if variance is not None and variance > self.config.data_preprocessing.variance_threshold:
                columns_to_keep.append(column)
        
        # Keep non-feature columns plus selected feature columns
        all_columns_to_keep = ([col for col in df.columns if col not in numeric_columns] + 
                              columns_to_keep)
        
        logger.info(f"Feature selection kept {len(columns_to_keep)} out of {len(numeric_columns)} features")
        return df.select(*all_columns_to_keep)
    
    def split_data_spark(self, df: SparkDataFrame) -> Tuple[SparkDataFrame, SparkDataFrame, SparkDataFrame]:
        """
        Split data into train/validation/test sets using Spark
        
        Args:
            df: Input DataFrame
            
        Returns:
            Tuple of (train_df, val_df, test_df)
        """
        logger.info("Splitting data into train/validation/test sets")
        
        if self.config.data_splitting.time_based_split and self.config.data_source.timestamp_column in df.columns:
            return self._time_based_split_spark(df)
        else:
            return self._random_split_spark(df)
    
    def _time_based_split_spark(self, df: SparkDataFrame) -> Tuple[SparkDataFrame, SparkDataFrame, SparkDataFrame]:
        """Time-based data splitting"""
        timestamp_col = self.config.data_source.timestamp_column
        
        # Sort by timestamp
        df_sorted = df.orderBy(col(timestamp_col))
        
        total_count = df_sorted.count()
        train_count = int(total_count * self.config.data_splitting.train_ratio)
        val_count = int(total_count * self.config.data_splitting.validation_ratio)
        
        # Add row numbers
        window = Window.orderBy(col(timestamp_col))
        df_with_row_num = df_sorted.withColumn("row_num", row_number().over(window))
        
        # Split based on row numbers
        train_df = df_with_row_num.filter(col("row_num") <= train_count).drop("row_num")
        val_df = df_with_row_num.filter(
            (col("row_num") > train_count) & (col("row_num") <= train_count + val_count)
        ).drop("row_num")
        test_df = df_with_row_num.filter(col("row_num") > train_count + val_count).drop("row_num")
        
        logger.info(f"Time-based split: Train={train_df.count()}, Val={val_df.count()}, Test={test_df.count()}")
        return train_df, val_df, test_df
    
    def _random_split_spark(self, df: SparkDataFrame) -> Tuple[SparkDataFrame, SparkDataFrame, SparkDataFrame]:
        """Random data splitting"""
        train_ratio = self.config.data_splitting.train_ratio
        val_ratio = self.config.data_splitting.validation_ratio
        test_ratio = self.config.data_splitting.test_ratio
        
        # Spark's randomSplit method
        train_df, val_df, test_df = df.randomSplit([train_ratio, val_ratio, test_ratio], 
                                                  seed=self.config.data_splitting.random_state)
        
        logger.info(f"Random split: Train={train_df.count()}, Val={val_df.count()}, Test={test_df.count()}")
        return train_df, val_df, test_df
    
    def convert_to_pandas(self, df: SparkDataFrame) -> pd.DataFrame:
        """Convert Spark DataFrame to Pandas DataFrame"""
        logger.info("Converting Spark DataFrame to Pandas DataFrame")
        
        # Use Arrow for faster conversion if available
        try:
            pandas_df = df.toPandas()
        except Exception as e:
            logger.warning(f"Arrow conversion failed, using standard conversion: {str(e)}")
            pandas_df = df.toPandas()
        
        return pandas_df
    
    def prepare_training_data(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Prepare features and targets for training
        
        Args:
            df: Input DataFrame
            
        Returns:
            Tuple of (features_df, targets_df)
        """
        logger.info("Preparing training data (features and targets)")
        
        # Separate features and targets
        feature_columns = [col for col in df.columns if col not in self.config.data_source.feature_exclude_columns]
        target_columns = self.config.data_source.target_columns
        
        # Ensure target columns exist
        available_targets = [col for col in target_columns if col in df.columns]
        if not available_targets:
            raise ValueError(f"No target columns found in data. Expected: {target_columns}")
        
        features_df = df[feature_columns]
        targets_df = df[available_targets]
        
        # Store feature column names for later use
        self.feature_columns = feature_columns
        
        logger.info(f"Prepared features: {len(feature_columns)} columns")
        logger.info(f"Prepared targets: {len(available_targets)} columns")
        
        return features_df, targets_df
    
    def normalize_features(self, X_train: pd.DataFrame, X_val: pd.DataFrame, X_test: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Normalize features using configured method
        
        Args:
            X_train: Training features
            X_val: Validation features  
            X_test: Test features
            
        Returns:
            Tuple of normalized (X_train, X_val, X_test)
        """
        if not self.config.data_preprocessing.normalize_features:
            return X_train, X_val, X_test
        
        logger.info(f"Normalizing features using {self.config.data_preprocessing.normalization_method} method")
        
        # Select numeric columns
        numeric_columns = X_train.select_dtypes(include=[np.number]).columns.tolist()
        
        # Initialize scaler
        if self.config.data_preprocessing.normalization_method == "standard":
            self.scaler = SklearnStandardScaler()
        elif self.config.data_preprocessing.normalization_method == "minmax":
            self.scaler = SklearnMinMaxScaler()
        elif self.config.data_preprocessing.normalization_method == "robust":
            self.scaler = SklearnRobustScaler()
        else:
            logger.warning(f"Unknown normalization method: {self.config.data_preprocessing.normalization_method}")
            return X_train, X_val, X_test
        
        # Fit on training data and transform all sets
        X_train_scaled = X_train.copy()
        X_val_scaled = X_val.copy()
        X_test_scaled = X_test.copy()
        
        X_train_scaled[numeric_columns] = self.scaler.fit_transform(X_train[numeric_columns])
        X_val_scaled[numeric_columns] = self.scaler.transform(X_val[numeric_columns])
        X_test_scaled[numeric_columns] = self.scaler.transform(X_test[numeric_columns])
        
        return X_train_scaled, X_val_scaled, X_test_scaled
    
    def save_preprocessor_artifacts(self, output_dir: str):
        """Save preprocessing artifacts (scalers, imputers, etc.)"""
        os.makedirs(output_dir, exist_ok=True)
        
        if self.scaler is not None:
            scaler_path = os.path.join(output_dir, "scaler.pkl")
            with open(scaler_path, 'wb') as f:
                pickle.dump(self.scaler, f)
            logger.info(f"Saved scaler to {scaler_path}")
        
        if self.feature_columns:
            feature_cols_path = os.path.join(output_dir, "feature_columns.pkl")
            with open(feature_cols_path, 'wb') as f:
                pickle.dump(self.feature_columns, f)
            logger.info(f"Saved feature columns to {feature_cols_path}")
    
    def load_data_complete_pipeline(self, 
                                   feature_path: Optional[str] = None,
                                   convert_to_pandas: bool = True) -> Dict[str, Any]:
        """
        Complete data loading pipeline
        
        Args:
            feature_path: Optional override for feature path
            convert_to_pandas: Whether to convert to Pandas for ML training
            
        Returns:
            Dictionary containing train/val/test data and metadata
        """
        logger.info("Starting complete data loading pipeline")
        
        # Load features from HDFS
        df_spark = self.load_features_from_hdfs(feature_path)
        
        # Preprocess data
        df_spark = self.preprocess_data(df_spark)
        
        # Split data
        train_spark, val_spark, test_spark = self.split_data_spark(df_spark)
        
        result = {
            "spark_dataframes": {
                "train": train_spark,
                "validation": val_spark,
                "test": test_spark
            },
            "metadata": {
                "total_samples": df_spark.count(),
                "train_samples": train_spark.count(),
                "val_samples": val_spark.count(),
                "test_samples": test_spark.count(),
                "feature_columns": [col for col in df_spark.columns if col not in self.config.data_source.feature_exclude_columns],
                "target_columns": self.config.data_source.target_columns
            }
        }
        
        if convert_to_pandas:
            logger.info("Converting to Pandas DataFrames for ML training")
            
            # Convert to Pandas
            train_pd = self.convert_to_pandas(train_spark)
            val_pd = self.convert_to_pandas(val_spark)
            test_pd = self.convert_to_pandas(test_spark)
            
            # Prepare features and targets
            X_train, y_train = self.prepare_training_data(train_pd)
            X_val, y_val = self.prepare_training_data(val_pd)
            X_test, y_test = self.prepare_training_data(test_pd)
            
            # Normalize features
            X_train_norm, X_val_norm, X_test_norm = self.normalize_features(X_train, X_val, X_test)
            
            result["pandas_dataframes"] = {
                "train": {"X": X_train_norm, "y": y_train},
                "validation": {"X": X_val_norm, "y": y_val},
                "test": {"X": X_test_norm, "y": y_test}
            }
        
        logger.info("Data loading pipeline completed successfully")
        return result
    
    def close(self):
        """Clean up resources"""
        if hasattr(self, 'spark') and self.spark:
            self.spark.stop()


if __name__ == "__main__":
    # Example usage
    config = get_ml_config_manager()
    
    # Create data loader
    data_loader = DataLoader(config)
    
    try:
        # Load and prepare data
        data_result = data_loader.load_data_complete_pipeline()
        
        print("Data Loading Pipeline Results:")
        print(f"Total samples: {data_result['metadata']['total_samples']}")
        print(f"Train samples: {data_result['metadata']['train_samples']}")
        print(f"Validation samples: {data_result['metadata']['val_samples']}")
        print(f"Test samples: {data_result['metadata']['test_samples']}")
        print(f"Feature columns: {len(data_result['metadata']['feature_columns'])}")
        print(f"Target columns: {data_result['metadata']['target_columns']}")
        
        if "pandas_dataframes" in data_result:
            train_data = data_result["pandas_dataframes"]["train"]
            print(f"Training features shape: {train_data['X'].shape}")
            print(f"Training targets shape: {train_data['y'].shape}")
        
    finally:
        data_loader.close()
"""
Temporal Feature Engineering Module

This module provides comprehensive temporal feature extraction for traffic prediction models.
It includes time-based features, lag features, rolling statistics, and advanced temporal patterns.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Union
from dataclasses import dataclass
import logging
from sklearn.preprocessing import LabelEncoder, StandardScaler
from pyspark.sql import SparkSession, DataFrame as SparkDataFrame
from pyspark.sql.functions import (
    col, hour, dayofweek, when, lag, avg, stddev, max as spark_max, min as spark_min,
    unix_timestamp, from_unixtime, date_format, isnan, isnull, coalesce, lit,
    row_number, sum as spark_sum, count, percentile_approx
)
from pyspark.sql.window import Window
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, FloatType, BooleanType, TimestampType

logger = logging.getLogger(__name__)

@dataclass
class TemporalFeatureConfig:
    """Configuration for temporal feature extraction"""
    lag_periods: List[int] = None  # Default: [1, 2, 3, 4, 5, 6]
    rolling_windows: List[int] = None  # Default: [3, 6, 12, 24]
    enable_cyclical_encoding: bool = True
    enable_holiday_features: bool = True
    enable_rush_hour_features: bool = True
    enable_weather_time_features: bool = True
    time_zone: str = "America/Los_Angeles"
    
    def __post_init__(self):
        if self.lag_periods is None:
            self.lag_periods = [1, 2, 3, 4, 5, 6]
        if self.rolling_windows is None:
            self.rolling_windows = [3, 6, 12, 24]

class TimePeriodAnalyzer:
    """Advanced time period analysis for traffic patterns"""
    
    def __init__(self, config: TemporalFeatureConfig = None):
        self.config = config or TemporalFeatureConfig()
        self.logger = logging.getLogger(__name__)
        
        # Rush hour definitions
        self.rush_hours = {
            'morning_start': 6,
            'morning_end': 10,
            'evening_start': 16,
            'evening_end': 20
        }
        
        # Holiday definitions (simplified - can be extended with actual holiday calendar)
        self.holidays = [
            "2023-01-01", "2023-07-04", "2023-12-25", "2023-11-23", "2023-11-24"
        ]
    
    def extract_basic_temporal_features(self, df: SparkDataFrame, timestamp_col: str = "timestamp") -> SparkDataFrame:
        """
        Extract basic temporal features from timestamp column
        
        Args:
            df: Input Spark DataFrame
            timestamp_col: Name of timestamp column
            
        Returns:
            DataFrame with additional temporal features
        """
        self.logger.info("Extracting basic temporal features")
        
        # Basic time components
        df = df.withColumn("hour", hour(col(timestamp_col))) \
               .withColumn("day_of_week", dayofweek(col(timestamp_col))) \
               .withColumn("day_of_month", date_format(col(timestamp_col), "d").cast(IntegerType())) \
               .withColumn("day_of_year", date_format(col(timestamp_col), "D").cast(IntegerType())) \
               .withColumn("week_of_year", date_format(col(timestamp_col), "w").cast(IntegerType())) \
               .withColumn("month", date_format(col(timestamp_col), "M").cast(IntegerType())) \
               .withColumn("quarter", date_format(col(timestamp_col), "Q").cast(IntegerType())) \
               .withColumn("year", date_format(col(timestamp_col), "y").cast(IntegerType()))
        
        # Weekend flag
        df = df.withColumn("is_weekend", 
                          when((col("day_of_week") == 1) | (col("day_of_week") == 7), 1).otherwise(0))
        
        # Rush hour flags
        df = df.withColumn("is_morning_rush", 
                          when((col("hour") >= self.rush_hours['morning_start']) & 
                               (col("hour") < self.rush_hours['morning_end']), 1).otherwise(0))
        
        df = df.withColumn("is_evening_rush", 
                          when((col("hour") >= self.rush_hours['evening_start']) & 
                               (col("hour") < self.rush_hours['evening_end']), 1).otherwise(0))
        
        df = df.withColumn("is_rush_hour", 
                          when((col("is_morning_rush") == 1) | (col("is_evening_rush") == 1), 1).otherwise(0))
        
        # Time period classification
        df = df.withColumn("time_period",
                          when(col("is_morning_rush") == 1, "morning_rush")
                          .when(col("is_evening_rush") == 1, "evening_rush")
                          .when((col("hour") >= 10) & (col("hour") < 16), "midday")
                          .when((col("hour") >= 22) | (col("hour") < 6), "late_night")
                          .otherwise("other"))
        
        return df
    
    def extract_cyclical_features(self, df: SparkDataFrame) -> SparkDataFrame:
        """
        Extract cyclical encoding of temporal features
        
        Args:
            df: DataFrame with basic temporal features
            
        Returns:
            DataFrame with cyclical encodings
        """
        if not self.config.enable_cyclical_encoding:
            return df
            
        self.logger.info("Extracting cyclical temporal features")
        
        # Hour cyclical encoding (24 hours)
        df = df.withColumn("hour_sin", (col("hour") * 2 * np.pi / 24.0).sin()) \
               .withColumn("hour_cos", (col("hour") * 2 * np.pi / 24.0).cos())
        
        # Day of week cyclical encoding (7 days)
        df = df.withColumn("dow_sin", ((col("day_of_week") - 1) * 2 * np.pi / 7.0).sin()) \
               .withColumn("dow_cos", ((col("day_of_week") - 1) * 2 * np.pi / 7.0).cos())
        
        # Day of month cyclical encoding (31 days)
        df = df.withColumn("dom_sin", ((col("day_of_month") - 1) * 2 * np.pi / 31.0).sin()) \
               .withColumn("dom_cos", ((col("day_of_month") - 1) * 2 * np.pi / 31.0).cos())
        
        # Month cyclical encoding (12 months)
        df = df.withColumn("month_sin", ((col("month") - 1) * 2 * np.pi / 12.0).sin()) \
               .withColumn("month_cos", ((col("month") - 1) * 2 * np.pi / 12.0).cos())
        
        return df
    
    def extract_lag_features(self, df: SparkDataFrame, 
                           value_columns: List[str],
                           partition_columns: List[str] = None,
                           order_column: str = "timestamp") -> SparkDataFrame:
        """
        Extract lag features for specified columns
        
        Args:
            df: Input DataFrame
            value_columns: Columns to create lag features for
            partition_columns: Columns to partition by (e.g., sensor_id)
            order_column: Column to order by for lag calculation
            
        Returns:
            DataFrame with lag features
        """
        self.logger.info(f"Extracting lag features for columns: {value_columns}")
        
        if partition_columns is None:
            partition_columns = ["sensor_id"]
            
        # Define window specification
        window = Window.partitionBy(*partition_columns).orderBy(order_column)
        
        # Create lag features for each specified period
        for period in self.config.lag_periods:
            for col_name in value_columns:
                lag_col_name = f"{col_name}_lag_{period}"
                df = df.withColumn(lag_col_name, lag(col(col_name), period).over(window))
        
        return df
    
    def extract_rolling_features(self, df: SparkDataFrame,
                               value_columns: List[str],
                               partition_columns: List[str] = None,
                               order_column: str = "timestamp") -> SparkDataFrame:
        """
        Extract rolling window statistics
        
        Args:
            df: Input DataFrame
            value_columns: Columns to calculate rolling statistics for
            partition_columns: Columns to partition by
            order_column: Column to order by
            
        Returns:
            DataFrame with rolling features
        """
        self.logger.info(f"Extracting rolling window features for columns: {value_columns}")
        
        if partition_columns is None:
            partition_columns = ["sensor_id"]
        
        # Create rolling features for each window size
        for window_size in self.config.rolling_windows:
            window = Window.partitionBy(*partition_columns).orderBy(order_column).rowsBetween(-window_size, 0)
            
            for col_name in value_columns:
                # Rolling average
                df = df.withColumn(f"{col_name}_rolling_mean_{window_size}h", 
                                 avg(col(col_name)).over(window))
                
                # Rolling standard deviation
                df = df.withColumn(f"{col_name}_rolling_std_{window_size}h", 
                                 stddev(col(col_name)).over(window))
                
                # Rolling min/max
                df = df.withColumn(f"{col_name}_rolling_min_{window_size}h", 
                                 spark_min(col(col_name)).over(window))
                df = df.withColumn(f"{col_name}_rolling_max_{window_size}h", 
                                 spark_max(col(col_name)).over(window))
                
                # Rolling sum (useful for volume)
                df = df.withColumn(f"{col_name}_rolling_sum_{window_size}h", 
                                 spark_sum(col(col_name)).over(window))
                
                # Rolling count (for data availability)
                df = df.withColumn(f"{col_name}_rolling_count_{window_size}h", 
                                 count(col(col_name)).over(window))
        
        return df
    
    def extract_trend_features(self, df: SparkDataFrame,
                             value_columns: List[str],
                             partition_columns: List[str] = None,
                             order_column: str = "timestamp") -> SparkDataFrame:
        """
        Extract trend and momentum features
        
        Args:
            df: Input DataFrame
            value_columns: Columns to calculate trends for
            partition_columns: Columns to partition by
            order_column: Column to order by
            
        Returns:
            DataFrame with trend features
        """
        self.logger.info(f"Extracting trend features for columns: {value_columns}")
        
        if partition_columns is None:
            partition_columns = ["sensor_id"]
        
        window = Window.partitionBy(*partition_columns).orderBy(order_column)
        
        for col_name in value_columns:
            # First difference (change from previous period)
            df = df.withColumn(f"{col_name}_diff_1", 
                             col(col_name) - lag(col(col_name), 1).over(window))
            
            # Second difference (acceleration)
            df = df.withColumn(f"{col_name}_diff_2", 
                             col(f"{col_name}_diff_1") - lag(col(f"{col_name}_diff_1"), 1).over(window))
            
            # Percentage change
            df = df.withColumn(f"{col_name}_pct_change", 
                             (col(col_name) - lag(col(col_name), 1).over(window)) / 
                             (lag(col(col_name), 1).over(window) + 0.001))  # Small epsilon to avoid division by zero
            
            # Moving average convergence divergence (MACD) - using 12 and 26 period averages
            ema_12_window = Window.partitionBy(*partition_columns).orderBy(order_column).rowsBetween(-12, 0)
            ema_26_window = Window.partitionBy(*partition_columns).orderBy(order_column).rowsBetween(-26, 0)
            
            df = df.withColumn(f"{col_name}_ema_12", avg(col(col_name)).over(ema_12_window))
            df = df.withColumn(f"{col_name}_ema_26", avg(col(col_name)).over(ema_26_window))
            df = df.withColumn(f"{col_name}_macd", 
                             col(f"{col_name}_ema_12") - col(f"{col_name}_ema_26"))
        
        return df
    
    def extract_statistical_features(self, df: SparkDataFrame,
                                   value_columns: List[str],
                                   partition_columns: List[str] = None) -> SparkDataFrame:
        """
        Extract statistical features over historical data
        
        Args:
            df: Input DataFrame
            value_columns: Columns to calculate statistics for
            partition_columns: Columns to partition by
            
        Returns:
            DataFrame with statistical features
        """
        self.logger.info(f"Extracting statistical features for columns: {value_columns}")
        
        # Create features based on historical statistics per sensor and time period
        for col_name in value_columns:
            # Hour-of-day statistics
            hour_stats = df.groupBy("sensor_id", "hour").agg(
                avg(col(col_name)).alias(f"{col_name}_hour_avg"),
                stddev(col(col_name)).alias(f"{col_name}_hour_std"),
                percentile_approx(col(col_name), 0.5).alias(f"{col_name}_hour_median"),
                percentile_approx(col(col_name), 0.75).alias(f"{col_name}_hour_q75"),
                percentile_approx(col(col_name), 0.25).alias(f"{col_name}_hour_q25")
            )
            
            df = df.join(hour_stats, on=["sensor_id", "hour"], how="left")
            
            # Day-of-week statistics
            dow_stats = df.groupBy("sensor_id", "day_of_week").agg(
                avg(col(col_name)).alias(f"{col_name}_dow_avg"),
                stddev(col(col_name)).alias(f"{col_name}_dow_std")
            )
            
            df = df.join(dow_stats, on=["sensor_id", "day_of_week"], how="left")
            
            # Calculate z-scores (how unusual current value is)
            df = df.withColumn(f"{col_name}_hour_zscore", 
                             (col(col_name) - col(f"{col_name}_hour_avg")) / 
                             (col(f"{col_name}_hour_std") + 0.001))
            
            df = df.withColumn(f"{col_name}_dow_zscore", 
                             (col(col_name) - col(f"{col_name}_dow_avg")) / 
                             (col(f"{col_name}_dow_std") + 0.001))
        
        return df

class TemporalFeatureExtractor:
    """Main class for temporal feature extraction"""
    
    def __init__(self, spark_session: SparkSession, config: TemporalFeatureConfig = None):
        self.spark = spark_session
        self.config = config or TemporalFeatureConfig()
        self.analyzer = TimePeriodAnalyzer(config)
        self.logger = logging.getLogger(__name__)
        
        # Configure Spark for optimal performance
        self.spark.conf.set("spark.sql.adaptive.enabled", "true")
        self.spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")
        
    def extract_all_temporal_features(self, df: SparkDataFrame,
                                    timestamp_col: str = "timestamp",
                                    value_columns: List[str] = None,
                                    partition_columns: List[str] = None) -> SparkDataFrame:
        """
        Extract all temporal features from the dataset
        
        Args:
            df: Input Spark DataFrame
            timestamp_col: Name of timestamp column
            value_columns: Columns to create lag/rolling features for
            partition_columns: Columns to partition by for window operations
            
        Returns:
            DataFrame with all temporal features
        """
        self.logger.info("Starting comprehensive temporal feature extraction")
        
        if value_columns is None:
            value_columns = ["speed_mph", "volume_vehicles_per_hour"]
        
        if partition_columns is None:
            partition_columns = ["sensor_id"]
        
        # Start with basic temporal features
        df = self.analyzer.extract_basic_temporal_features(df, timestamp_col)
        
        # Add cyclical encodings
        df = self.analyzer.extract_cyclical_features(df)
        
        # Add lag features
        df = self.analyzer.extract_lag_features(df, value_columns, partition_columns, timestamp_col)
        
        # Add rolling window features
        df = self.analyzer.extract_rolling_features(df, value_columns, partition_columns, timestamp_col)
        
        # Add trend features
        df = self.analyzer.extract_trend_features(df, value_columns, partition_columns, timestamp_col)
        
        # Add statistical features
        df = self.analyzer.extract_statistical_features(df, value_columns, partition_columns)
        
        # Handle missing values created by lag/rolling operations
        df = self._handle_missing_values(df)
        
        self.logger.info("Temporal feature extraction completed")
        return df
    
    def _handle_missing_values(self, df: SparkDataFrame) -> SparkDataFrame:
        """
        Handle missing values created during feature engineering
        
        Args:
            df: DataFrame potentially containing missing values
            
        Returns:
            DataFrame with missing values handled
        """
        self.logger.info("Handling missing values in temporal features")
        
        # Get all column names
        all_columns = df.columns
        
        # Identify feature columns that might have missing values
        feature_columns = [col_name for col_name in all_columns 
                          if any(suffix in col_name for suffix in ['_lag_', '_rolling_', '_diff_', '_pct_change', '_macd'])]
        
        # Fill missing values with appropriate strategies
        for col_name in feature_columns:
            if '_lag_' in col_name:
                # For lag features, forward fill or use 0
                df = df.withColumn(col_name, coalesce(col(col_name), lit(0.0)))
            elif '_rolling_' in col_name:
                # For rolling features, use the current value or global mean
                if 'mean' in col_name or 'avg' in col_name:
                    original_col = col_name.split('_rolling_')[0]
                    df = df.withColumn(col_name, coalesce(col(col_name), col(original_col)))
                else:
                    df = df.withColumn(col_name, coalesce(col(col_name), lit(0.0)))
            elif '_diff_' in col_name or '_pct_change' in col_name:
                # For difference features, use 0
                df = df.withColumn(col_name, coalesce(col(col_name), lit(0.0)))
            elif 'zscore' in col_name:
                # For z-scores, use 0 (neutral)
                df = df.withColumn(col_name, coalesce(col(col_name), lit(0.0)))
        
        return df
    
    def get_feature_metadata(self) -> Dict:
        """
        Get metadata about extracted temporal features
        
        Returns:
            Dictionary containing feature metadata
        """
        return {
            "temporal_features": {
                "basic_features": [
                    "hour", "day_of_week", "day_of_month", "day_of_year", 
                    "week_of_year", "month", "quarter", "year",
                    "is_weekend", "is_morning_rush", "is_evening_rush", 
                    "is_rush_hour", "time_period"
                ],
                "cyclical_features": [
                    "hour_sin", "hour_cos", "dow_sin", "dow_cos",
                    "dom_sin", "dom_cos", "month_sin", "month_cos"
                ] if self.config.enable_cyclical_encoding else [],
                "lag_periods": self.config.lag_periods,
                "rolling_windows": self.config.rolling_windows,
                "statistical_features": [
                    "hour_avg", "hour_std", "hour_median", "hour_q75", "hour_q25",
                    "dow_avg", "dow_std", "hour_zscore", "dow_zscore"
                ],
                "trend_features": [
                    "diff_1", "diff_2", "pct_change", "ema_12", "ema_26", "macd"
                ]
            },
            "config": {
                "lag_periods": self.config.lag_periods,
                "rolling_windows": self.config.rolling_windows,
                "enable_cyclical_encoding": self.config.enable_cyclical_encoding,
                "enable_holiday_features": self.config.enable_holiday_features,
                "enable_rush_hour_features": self.config.enable_rush_hour_features,
                "time_zone": self.config.time_zone
            }
        }

# Example usage and testing functions
def create_sample_temporal_data(spark: SparkSession) -> SparkDataFrame:
    """Create sample data for testing temporal features"""
    import pandas as pd
    from datetime import datetime, timedelta
    
    # Generate sample data
    start_date = datetime(2023, 6, 1)
    dates = [start_date + timedelta(hours=i) for i in range(168)]  # 1 week of hourly data
    
    sample_data = []
    for sensor_id in ["METR_LA_001", "METR_LA_002", "METR_LA_003"]:
        for date in dates:
            # Simulate traffic patterns
            hour = date.hour
            dow = date.weekday()
            
            # Morning rush: higher volume, lower speed
            if 6 <= hour <= 9:
                speed = np.random.normal(25, 5)
                volume = np.random.normal(60, 10)
            # Evening rush
            elif 16 <= hour <= 19:
                speed = np.random.normal(20, 5)
                volume = np.random.normal(70, 15)
            # Night
            elif hour <= 5 or hour >= 22:
                speed = np.random.normal(45, 8)
                volume = np.random.normal(15, 5)
            # Regular day
            else:
                speed = np.random.normal(35, 7)
                volume = np.random.normal(40, 10)
            
            # Weekend adjustments
            if dow in [5, 6]:  # Saturday, Sunday
                volume *= 0.7
                speed *= 1.1
            
            sample_data.append({
                'sensor_id': sensor_id,
                'timestamp': date,
                'speed_mph': max(5, speed),
                'volume_vehicles_per_hour': max(0, volume)
            })
    
    # Convert to Spark DataFrame
    pandas_df = pd.DataFrame(sample_data)
    return spark.createDataFrame(pandas_df)

if __name__ == "__main__":
    # Example usage
    spark = SparkSession.builder \
        .appName("TemporalFeatureExtraction") \
        .config("spark.sql.adaptive.enabled", "true") \
        .getOrCreate()
    
    # Create sample data
    df = create_sample_temporal_data(spark)
    
    # Initialize extractor
    config = TemporalFeatureConfig(
        lag_periods=[1, 2, 3, 6],
        rolling_windows=[3, 6, 12],
        enable_cyclical_encoding=True
    )
    extractor = TemporalFeatureExtractor(spark, config)
    
    # Extract features
    df_with_features = extractor.extract_all_temporal_features(df)
    
    # Show results
    print("Original columns:", len(df.columns))
    print("Enhanced columns:", len(df_with_features.columns))
    
    # Show feature metadata
    metadata = extractor.get_feature_metadata()
    print("\nFeature Metadata:")
    for category, features in metadata["temporal_features"].items():
        print(f"{category}: {len(features)} features")
    
    # Save sample output for inspection
    df_with_features.coalesce(1).write.mode("overwrite").option("header", "true").csv("temporal_features_sample")
    
    spark.stop()
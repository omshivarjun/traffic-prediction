# Task 3: Phase 3 - Feature Engineering Pipeline

## Overview
Implement comprehensive feature engineering pipeline using Spark to transform raw traffic data into ML-ready features. Extract time-based, spatial, and traffic-specific features optimized for prediction models.

**Status**: Not Started  
**Dependencies**: Task 2 (Stream Processing must be outputting to HDFS)  
**Priority**: High

---

## Subtask 3.1: Time-Based Feature Extraction

**Status**: Not Started

### Description
Extract temporal features from timestamps to capture traffic patterns across different time periods.

### Implementation Details

**Features to Extract**:
1. **Hour of Day** (sine/cosine encoding for cyclical nature)
2. **Day of Week** (one-hot encoded)
3. **Is Weekend** (boolean)
4. **Is Rush Hour** (boolean: 7-9am, 4-7pm)
5. **Time Since Midnight** (seconds)

**Spark Code**:
```python
# src/feature-engineering/time_features.py
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    hour, dayofweek, sin, cos, when, col,
    unix_timestamp, to_timestamp, lit
)
import math

class TimeFeatureExtractor:
    """Extract time-based features from traffic events"""
    
    def __init__(self, spark):
        self.spark = spark
    
    def extract_features(self, df):
        """
        Add time-based features to DataFrame
        
        Args:
            df: DataFrame with 'timestamp' column
            
        Returns:
            DataFrame with additional time features
        """
        # Extract hour (0-23)
        df = df.withColumn("hour", hour(col("timestamp")))
        
        # Cyclical encoding for hour (sine/cosine)
        # This preserves the circular nature of time
        df = df.withColumn(
            "hour_sin",
            sin(col("hour") * 2 * lit(math.pi) / 24)
        )
        df = df.withColumn(
            "hour_cos",
            cos(col("hour") * 2 * lit(math.pi) / 24)
        )
        
        # Day of week (1=Sunday, 7=Saturday in Spark)
        df = df.withColumn("day_of_week", dayofweek(col("timestamp")))
        
        # Is weekend (Saturday=7, Sunday=1)
        df = df.withColumn(
            "is_weekend",
            when((col("day_of_week") == 1) | (col("day_of_week") == 7), 1).otherwise(0)
        )
        
        # Is rush hour (7-9am or 4-7pm)
        df = df.withColumn(
            "is_rush_hour",
            when(
                ((col("hour") >= 7) & (col("hour") < 9)) |
                ((col("hour") >= 16) & (col("hour") < 19)),
                1
            ).otherwise(0)
        )
        
        # Time since midnight (seconds)
        df = df.withColumn(
            "time_since_midnight",
            col("hour") * 3600 +
            minute(col("timestamp")) * 60 +
            second(col("timestamp"))
        )
        
        return df
```

### Validation Criteria
- [ ] All timestamps successfully parsed
- [ ] hour_sin and hour_cos values in range [-1, 1]
- [ ] is_weekend correctly identifies Saturdays and Sundays
- [ ] is_rush_hour correctly identifies 7-9am and 4-7pm periods
- [ ] No null values in time features

### Test Strategy
```python
def test_time_features():
    # Test with known timestamps
    test_data = [
        ("2024-01-01 08:00:00", 8, True, True),  # Monday 8am (rush hour)
        ("2024-01-06 14:00:00", 14, True, False), # Saturday 2pm (weekend, not rush)
        ("2024-01-02 18:00:00", 18, False, True)  # Tuesday 6pm (rush hour)
    ]
    
    # Verify each feature extraction
    for timestamp, expected_hour, expected_weekend, expected_rush in test_data:
        result = extract_time_features(timestamp)
        assert result['hour'] == expected_hour
        assert result['is_weekend'] == expected_weekend
        assert result['is_rush_hour'] == expected_rush
```

---

## Subtask 3.2: Spatial Feature Extraction

**Status**: Not Started

### Description
Extract location-based features from sensor coordinates and identifiers.

### Implementation Details

**Features to Extract**:
1. **Highway Type** (encoded from sensor_id pattern)
2. **Latitude/Longitude** (normalized)
3. **Distance from City Center** (calculated)
4. **Sensor Cluster** (K-means grouping)

**Spark Code**:
```python
# src/feature-engineering/spatial_features.py
from pyspark.sql.functions import (
    col, regexp_extract, sqrt, pow, lit,
    when, udf
)
from pyspark.sql.types import StringType, DoubleType

class SpatialFeatureExtractor:
    """Extract spatial features from sensor locations"""
    
    # LA city center coordinates
    LA_CENTER_LAT = 34.0522
    LA_CENTER_LON = -118.2437
    
    def __init__(self, spark):
        self.spark = spark
    
    def extract_features(self, df):
        """
        Add spatial features to DataFrame
        
        Args:
            df: DataFrame with 'sensor_id', 'latitude', 'longitude'
            
        Returns:
            DataFrame with additional spatial features
        """
        # Extract highway type from sensor_id
        # Pattern: METR_LA_{highway}_{number}
        df = df.withColumn(
            "highway_type",
            regexp_extract(col("sensor_id"), r"METR_LA_(\d+)_", 1)
        )
        
        # Encode common highways
        df = df.withColumn(
            "highway_encoded",
            when(col("highway_type") == "101", 1)
            .when(col("highway_type") == "110", 2)
            .when(col("highway_type") == "405", 3)
            .when(col("highway_type") == "10", 4)
            .otherwise(0)  # Unknown/other
        )
        
        # Normalize latitude and longitude
        # LA bounds: lat 33.7-34.5, lon -119 to -117
        df = df.withColumn(
            "lat_normalized",
            (col("latitude") - 33.7) / (34.5 - 33.7)
        )
        df = df.withColumn(
            "lon_normalized",
            (col("longitude") - (-119)) / ((-117) - (-119))
        )
        
        # Calculate distance from LA city center (in km)
        # Using haversine distance approximation
        df = df.withColumn(
            "distance_from_center",
            sqrt(
                pow((col("latitude") - lit(self.LA_CENTER_LAT)) * 111, 2) +
                pow((col("longitude") - lit(self.LA_CENTER_LON)) * 111 * 
                    cos(lit(self.LA_CENTER_LAT) * lit(3.14159) / 180), 2)
            )
        )
        
        return df
    
    def cluster_sensors(self, df, n_clusters=10):
        """
        Cluster sensors by geographic location using K-means
        
        Args:
            df: DataFrame with lat/lon features
            n_clusters: Number of clusters to create
            
        Returns:
            DataFrame with cluster assignment
        """
        from pyspark.ml.clustering import KMeans
        from pyspark.ml.feature import VectorAssembler
        
        # Prepare features for clustering
        assembler = VectorAssembler(
            inputCols=["latitude", "longitude"],
            outputCol="location_vector"
        )
        df = assembler.transform(df)
        
        # Train K-means model
        kmeans = KMeans(
            k=n_clusters,
            featuresCol="location_vector",
            predictionCol="sensor_cluster"
        )
        model = kmeans.fit(df)
        
        # Add cluster predictions
        df = model.transform(df)
        
        return df
```

### Validation Criteria
- [ ] highway_encoded correctly extracted from sensor_id
- [ ] lat_normalized and lon_normalized in range [0, 1]
- [ ] distance_from_center calculated for all sensors
- [ ] sensor_cluster assigned (0 to n_clusters-1)
- [ ] No null values in spatial features

---

## Subtask 3.3: Traffic-Specific Feature Extraction

**Status**: Not Started

### Description
Calculate traffic flow metrics and efficiency indicators.

### Implementation Details

**Features to Calculate**:
1. **Traffic Efficiency** = speed / free_flow_speed
2. **Occupancy Ratio** = occupancy / max_occupancy
3. **Flow Rate** = volume / time_window
4. **Speed Variance** (within time window)
5. **Congestion Level** (categorical: low/medium/high)

**According to workflow document, traffic_efficiency has 81% feature importance!**

**Spark Code**:
```python
# src/feature-engineering/traffic_features.py
from pyspark.sql.functions import (
    col, avg, stddev, when, lag, lead
)
from pyspark.sql.window import Window

class TrafficFeatureExtractor:
    """Extract traffic-specific features"""
    
    # Free flow speed by highway (mph)
    FREE_FLOW_SPEEDS = {
        "101": 65,
        "110": 65,
        "405": 65,
        "10": 65,
        "default": 60
    }
    
    def __init__(self, spark):
        self.spark = spark
    
    def extract_features(self, df):
        """
        Add traffic-specific features to DataFrame
        
        Args:
            df: DataFrame with traffic measurements
            
        Returns:
            DataFrame with traffic features
        """
        # Get free flow speed for each sensor
        df = df.withColumn(
            "free_flow_speed",
            when(col("highway_type") == "101", 65)
            .when(col("highway_type") == "110", 65)
            .when(col("highway_type") == "405", 65)
            .when(col("highway_type") == "10", 65)
            .otherwise(60)
        )
        
        # Traffic efficiency (MOST IMPORTANT - 81% feature importance)
        df = df.withColumn(
            "traffic_efficiency",
            col("speed") / col("free_flow_speed")
        )
        
        # Occupancy ratio (if occupancy data available)
        if "occupancy" in df.columns:
            df = df.withColumn(
                "occupancy_ratio",
                col("occupancy") / 100.0  # Assuming occupancy is 0-100
            )
        
        # Flow rate (vehicles per hour)
        # Assuming volume is count per 5-minute window
        df = df.withColumn(
            "flow_rate",
            col("volume") * 12  # Convert 5-min to hourly
        )
        
        # Calculate speed variance over time window
        # Window: partition by sensor, order by time, last 6 records (30 min)
        window_spec = Window.partitionBy("sensor_id") \
                           .orderBy("timestamp") \
                           .rowsBetween(-5, 0)
        
        df = df.withColumn(
            "speed_variance",
            stddev(col("speed")).over(window_spec)
        )
        
        # Congestion level (categorical)
        df = df.withColumn(
            "congestion_level",
            when(col("traffic_efficiency") > 0.8, "low")
            .when(col("traffic_efficiency") > 0.5, "medium")
            .otherwise("high")
        )
        
        # Speed change rate (acceleration/deceleration)
        df = df.withColumn(
            "prev_speed",
            lag(col("speed"), 1).over(
                Window.partitionBy("sensor_id").orderBy("timestamp")
            )
        )
        df = df.withColumn(
            "speed_change",
            col("speed") - col("prev_speed")
        )
        
        return df
```

### Validation Criteria
- [ ] traffic_efficiency in range [0, 2] (can exceed 1 if above free flow)
- [ ] occupancy_ratio in range [0, 1]
- [ ] flow_rate calculated correctly (volume * 12)
- [ ] speed_variance calculated for rolling window
- [ ] congestion_level correctly categorized
- [ ] No divide-by-zero errors

---

## Subtask 3.4: Historical Feature Engineering

**Status**: Not Started

### Description
Create lagged features and moving averages to capture historical patterns.

### Implementation Details

**Features to Create**:
1. **Speed Lag Features** (t-1, t-2, t-3 timesteps)
2. **Moving Averages** (15-min, 30-min, 60-min windows)
3. **Trend Indicators** (increasing/decreasing/stable)

**Spark Code**:
```python
# src/feature-engineering/historical_features.py
from pyspark.sql.functions import (
    col, lag, avg, when, lit
)
from pyspark.sql.window import Window

class HistoricalFeatureExtractor:
    """Extract historical/lagged features"""
    
    def __init__(self, spark):
        self.spark = spark
    
    def extract_features(self, df):
        """
        Add historical features to DataFrame
        
        Args:
            df: DataFrame with time-series traffic data
            
        Returns:
            DataFrame with historical features
        """
        # Define window for each sensor ordered by time
        window_spec = Window.partitionBy("sensor_id").orderBy("timestamp")
        
        # Lagged speed features (previous 3 timesteps = 15 minutes)
        df = df.withColumn("speed_lag_1", lag(col("speed"), 1).over(window_spec))
        df = df.withColumn("speed_lag_2", lag(col("speed"), 2).over(window_spec))
        df = df.withColumn("speed_lag_3", lag(col("speed"), 3).over(window_spec))
        
        # Moving averages
        # 15-minute MA (3 records at 5-min intervals)
        window_15min = window_spec.rowsBetween(-2, 0)
        df = df.withColumn(
            "speed_ma_15min",
            avg(col("speed")).over(window_15min)
        )
        
        # 30-minute MA (6 records)
        window_30min = window_spec.rowsBetween(-5, 0)
        df = df.withColumn(
            "speed_ma_30min",
            avg(col("speed")).over(window_30min)
        )
        
        # 60-minute MA (12 records)
        window_60min = window_spec.rowsBetween(-11, 0)
        df = df.withColumn(
            "speed_ma_60min",
            avg(col("speed")).over(window_60min)
        )
        
        # Trend indicator (comparing current to 30-min MA)
        df = df.withColumn(
            "trend",
            when(col("speed") > col("speed_ma_30min") * 1.1, "increasing")
            .when(col("speed") < col("speed_ma_30min") * 0.9, "decreasing")
            .otherwise("stable")
        )
        
        return df
```

### Validation Criteria
- [ ] Lag features correctly shift timestamps
- [ ] Moving averages calculated over correct windows
- [ ] Trend correctly categorized
- [ ] First records have nulls for unavailable lags (expected)

---

## Subtask 3.5: Feature Storage Pipeline to HDFS

**Status**: Not Started

### Description
Create Spark job to process features and store to HDFS in partitioned Parquet format.

### Implementation Details

**Storage Structure**:
```
/traffic-data/processed/ml-features/
  year=2024/
    month=01/
      day=07/
        part-00000.parquet
        part-00001.parquet
```

**Complete Spark Job**:
```python
# src/feature-engineering/feature_pipeline.py
from pyspark.sql import SparkSession
from time_features import TimeFeatureExtractor
from spatial_features import SpatialFeatureExtractor
from traffic_features import TrafficFeatureExtractor
from historical_features import HistoricalFeatureExtractor
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FeatureEngineeringPipeline:
    """Complete feature engineering pipeline"""
    
    def __init__(self):
        self.spark = SparkSession.builder \
            .appName("TrafficFeatureEngineering") \
            .config("spark.sql.shuffle.partitions", "10") \
            .getOrCreate()
        
        # Initialize extractors
        self.time_extractor = TimeFeatureExtractor(self.spark)
        self.spatial_extractor = SpatialFeatureExtractor(self.spark)
        self.traffic_extractor = TrafficFeatureExtractor(self.spark)
        self.historical_extractor = HistoricalFeatureExtractor(self.spark)
    
    def run_pipeline(self, input_path, output_path):
        """
        Execute full feature engineering pipeline
        
        Args:
            input_path: HDFS path to raw aggregated traffic data
            output_path: HDFS path for ML-ready features
        """
        logger.info(f"Reading data from {input_path}")
        
        # Read aggregated traffic data from HDFS
        df = self.spark.read.parquet(input_path)
        
        logger.info(f"Initial record count: {df.count()}")
        
        # Apply feature extractors in sequence
        logger.info("Extracting time features...")
        df = self.time_extractor.extract_features(df)
        
        logger.info("Extracting spatial features...")
        df = self.spatial_extractor.extract_features(df)
        
        logger.info("Extracting traffic features...")
        df = self.traffic_extractor.extract_features(df)
        
        logger.info("Extracting historical features...")
        df = self.historical_extractor.extract_features(df)
        
        # Drop intermediate columns
        feature_columns = [
            # Original
            "sensor_id", "timestamp", "speed", "volume",
            # Time features
            "hour_sin", "hour_cos", "is_weekend", "is_rush_hour",
            # Spatial features
            "highway_encoded", "lat_normalized", "lon_normalized",
            "distance_from_center", "sensor_cluster",
            # Traffic features (MOST IMPORTANT: traffic_efficiency = 81%)
            "traffic_efficiency", "occupancy_ratio", "flow_rate",
            "speed_variance", "congestion_level",
            # Historical features
            "speed_lag_1", "speed_lag_2", "speed_lag_3",
            "speed_ma_15min", "speed_ma_30min", "speed_ma_60min",
            "trend"
        ]
        
        df = df.select(feature_columns)
        
        # Remove rows with null historical features (first few records)
        df = df.na.drop(subset=["speed_lag_3", "speed_ma_60min"])
        
        logger.info(f"Final record count after cleaning: {df.count()}")
        
        # Write to HDFS in partitioned Parquet format
        logger.info(f"Writing features to {output_path}")
        df.write \
          .mode("append") \
          .partitionBy("year", "month", "day") \
          .parquet(output_path)
        
        logger.info("Feature pipeline completed successfully")
        
        # Show sample
        df.show(5, truncate=False)
        
        return df

if __name__ == "__main__":
    pipeline = FeatureEngineeringPipeline()
    
    input_path = "hdfs://namenode:9000/traffic-data/processed/aggregates/"
    output_path = "hdfs://namenode:9000/traffic-data/processed/ml-features/"
    
    pipeline.run_pipeline(input_path, output_path)
```

**Execution Script**:
```bash
#!/bin/bash
# scripts/run-feature-engineering.sh

spark-submit \
  --master spark://spark-master:7077 \
  --executor-memory 2G \
  --total-executor-cores 4 \
  --conf spark.sql.shuffle.partitions=10 \
  src/feature-engineering/feature_pipeline.py
```

### Validation Criteria
- [ ] All feature columns present in output
- [ ] Data partitioned by year/month/day
- [ ] Parquet files readable
- [ ] No null values in critical features (traffic_efficiency, hour_sin/cos)
- [ ] File size reasonable (compressed)

### Test Strategy
```python
def test_feature_pipeline():
    # Read back from HDFS
    df = spark.read.parquet("hdfs://namenode:9000/traffic-data/processed/ml-features/")
    
    # Verify all features exist
    expected_features = [
        "traffic_efficiency", "hour_sin", "hour_cos",
        "is_weekend", "highway_encoded", "speed_variance"
    ]
    for feature in expected_features:
        assert feature in df.columns
    
    # Verify traffic_efficiency in valid range
    stats = df.select("traffic_efficiency").describe().collect()
    max_efficiency = float(stats[4][1])  # max value
    assert max_efficiency <= 2.0
    
    # Verify no nulls in key features
    null_counts = df.select(
        [count(when(col(c).isNull(), c)).alias(c) for c in expected_features]
    ).collect()[0]
    for count in null_counts:
        assert count == 0
```

---

## Completion Criteria

### Phase 3 Complete When:
- [ ] Time features extracted (hour_sin/cos, is_weekend, is_rush_hour)
- [ ] Spatial features extracted (highway_encoded, normalized lat/lon, distance)
- [ ] Traffic features calculated (traffic_efficiency with 81% importance)
- [ ] Historical features created (lags, moving averages, trends)
- [ ] Features stored to HDFS at `/traffic-data/processed/ml-features/`
- [ ] Spark job runs successfully end-to-end
- [ ] All validation tests pass
- [ ] Sample output verified in HDFS

### Performance Targets
- Feature extraction: < 30 seconds for 1000 records
- HDFS write: Partitioned by date for efficient querying
- No data loss during transformation
- All 207 sensors represented in output

---

## Next Steps
1. Set up Spark environment and dependencies
2. Implement and test each feature extractor individually
3. Integrate into complete pipeline
4. Run on sample data
5. Validate output quality
6. Deploy to production
7. → Proceed to **Task 4: ML Training Pipeline**

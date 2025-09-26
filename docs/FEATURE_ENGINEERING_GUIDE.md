# Feature Engineering Pipeline Documentation

## Overview

The Feature Engineering Pipeline is a comprehensive system for extracting, transforming, and managing machine learning features from traffic data. It provides temporal and spatial feature extraction, data quality analysis, feature validation, and a complete feature store with versioning capabilities.

## Architecture

```
Traffic Data → Temporal Features → Feature Pipeline → Feature Store → ML Models
     ↓              ↓                    ↓              ↓
Spatial Features → Data Quality → Feature Validation → Versioning
```

### Core Components

1. **Temporal Feature Extractor** - Time-based feature extraction
2. **Spatial Feature Extractor** - Location-based feature extraction  
3. **Feature Pipeline** - Orchestrates the complete feature engineering workflow
4. **Feature Store** - Manages feature storage, versioning, and metadata
5. **Configuration Manager** - Handles all configuration aspects

## Quick Start

### 1. Configuration Setup

Ensure your configuration is valid:

```powershell
.\scripts\manage-feature-pipeline.ps1 -Action config-validate
```

### 2. Run Complete Pipeline

Process traffic data through the full pipeline:

```powershell
.\scripts\manage-feature-pipeline.ps1 -Action run-pipeline -FeatureSet traffic_basic -InputPath "hdfs://localhost:9000/traffic/raw" -OutputPath "hdfs://localhost:9000/traffic/features/traffic_basic"
```

### 3. Validate Features

Check feature quality and consistency:

```powershell
.\scripts\manage-feature-pipeline.ps1 -Action validate-features -FeatureSet traffic_basic
```

### 4. List Available Features

See what features are available:

```powershell
.\scripts\manage-feature-pipeline.ps1 -Action list-features
```

## Feature Types

### Temporal Features

Temporal features capture time-based patterns in traffic data:

#### Basic Temporal Features
- **Hour of Day** (0-23): `hour`
- **Day of Week** (0-6): `day_of_week` 
- **Month** (1-12): `month`
- **Weekend Flag**: `is_weekend` (boolean)
- **Holiday Flag**: `is_holiday` (boolean)

#### Cyclical Encoding
Time features are encoded using sine/cosine transformations to capture cyclical nature:
- `hour_sin`, `hour_cos` - Hour cyclical encoding
- `day_of_week_sin`, `day_of_week_cos` - Day of week cyclical encoding
- `month_sin`, `month_cos` - Month cyclical encoding

#### Lag Features
Historical values for trend analysis:
- `speed_lag_1` through `speed_lag_6` - Speed values from 1-6 time periods ago
- `volume_lag_1` through `volume_lag_6` - Volume values from 1-6 time periods ago
- `occupancy_lag_1` through `occupancy_lag_6` - Occupancy values from 1-6 time periods ago

#### Rolling Window Features
Statistical measures over time windows:
- `speed_rolling_mean_5`, `speed_rolling_mean_15`, `speed_rolling_mean_30`, `speed_rolling_mean_60`
- `speed_rolling_std_5`, `speed_rolling_std_15`, `speed_rolling_std_30`, `speed_rolling_std_60`
- `volume_rolling_mean_5`, `volume_rolling_mean_15`, `volume_rolling_mean_30`, `volume_rolling_mean_60`
- `volume_rolling_std_5`, `volume_rolling_std_15`, `volume_rolling_std_30`, `volume_rolling_std_60`

#### Trend Analysis Features
Advanced trend indicators:
- `speed_macd` - Moving Average Convergence Divergence for speed
- `speed_rsi` - Relative Strength Index for speed
- `volume_trend_slope` - Linear trend slope for volume
- `speed_momentum` - Speed momentum indicator

#### Statistical Features
- `speed_zscore` - Z-score for outlier detection
- `volume_percentile_rank` - Percentile rank within historical data
- `speed_seasonal_deviation` - Deviation from seasonal patterns

### Spatial Features

Spatial features capture location-based relationships and traffic flow patterns:

#### Adjacency Features
- `adjacent_sensors` - List of nearby sensors within threshold distance
- `adjacency_count` - Number of adjacent sensors
- `distance_to_nearest` - Distance to nearest sensor

#### Neighbor Features
Traffic data from neighboring sensors:
- `neighbor_speed_avg` - Average speed of neighboring sensors
- `neighbor_volume_avg` - Average volume of neighboring sensors
- `neighbor_speed_std` - Standard deviation of neighbor speeds
- `neighbor_volume_std` - Standard deviation of neighbor volumes

#### Directional Flow Features
- `upstream_speed_avg` - Average speed from upstream sensors
- `downstream_speed_avg` - Average speed from downstream sensors
- `upstream_volume_sum` - Total volume from upstream sensors
- `downstream_volume_sum` - Total volume to downstream sensors
- `flow_differential` - Difference between upstream and downstream flow

#### Network Topology Features
- `betweenness_centrality` - Sensor importance in traffic network
- `closeness_centrality` - How central the sensor is to all others
- `degree_centrality` - Number of connections relative to maximum possible
- `clustering_coefficient` - How connected the sensor's neighbors are
- `shortest_path_avg` - Average shortest path to all other sensors

#### Spatial Correlation Features
- `speed_spatial_correlation` - Correlation with neighboring sensor speeds
- `volume_spatial_correlation` - Correlation with neighboring sensor volumes
- `distance_weighted_speed` - Distance-weighted average of neighbor speeds
- `distance_weighted_volume` - Distance-weighted average of neighbor volumes

## Configuration

### Configuration File Structure

The feature engineering pipeline is configured through `config/feature_engineering_config.json`:

```json
{
  "feature_engineering": {
    "temporal_features": {
      "enabled": true,
      "lag_periods": [1, 2, 3, 4, 5, 6],
      "rolling_windows": [5, 15, 30, 60],
      "cyclical_encoding": {
        "hour": true,
        "day_of_week": true,
        "month": true
      }
    },
    "spatial_features": {
      "enabled": true,
      "adjacency_threshold_meters": 500.0,
      "neighbor_analysis": {
        "max_neighbors": 5,
        "distance_weights": true
      }
    }
  }
}
```

### Key Configuration Sections

#### Temporal Features Configuration
- `enabled`: Enable/disable temporal feature extraction
- `lag_periods`: List of lag periods to calculate (e.g., [1,2,3] for t-1, t-2, t-3)
- `rolling_windows`: Window sizes for rolling statistics (in time periods)
- `cyclical_encoding`: Which time features to encode cyclically

#### Spatial Features Configuration
- `enabled`: Enable/disable spatial feature extraction
- `adjacency_threshold_meters`: Distance threshold for sensor adjacency
- `max_neighbors`: Maximum number of neighbors to consider
- `distance_weights`: Use distance weighting for neighbor features

#### Feature Pipeline Configuration
- `data_quality.missing_value_threshold`: Maximum allowed missing value percentage
- `preprocessing.handle_missing`: Strategy for handling missing values ("interpolate", "drop", "fill")
- `feature_scaling.method`: Scaling method ("standard", "minmax", "robust")

#### Spark Optimization Configuration
- `sql.adaptive.enabled`: Enable Spark adaptive query execution
- `execution.dynamicAllocation.enabled`: Enable dynamic executor allocation
- `memory.executor.memory`: Executor memory allocation
- `io.compression.codec`: Compression codec for I/O operations

## Usage Examples

### Python API Usage

#### Basic Feature Extraction

```python
from pyspark.sql import SparkSession
from feature_engineering.temporal_features import TemporalFeatureExtractor, TemporalFeatureConfig
from feature_engineering.spatial_features import SpatialFeatureExtractor, SpatialFeatureConfig

# Initialize Spark
spark = SparkSession.builder.appName("FeatureExtraction").getOrCreate()

# Load traffic data
traffic_df = spark.read.parquet("hdfs://localhost:9000/traffic/raw/2023/06/01")

# Extract temporal features
temporal_config = TemporalFeatureConfig()
temporal_extractor = TemporalFeatureExtractor(spark, temporal_config)
temporal_features_df = temporal_extractor.extract_features(traffic_df, "timestamp")

# Extract spatial features
sensor_metadata = {...}  # Load sensor metadata
spatial_config = SpatialFeatureConfig()
spatial_extractor = SpatialFeatureExtractor(spark, spatial_config, sensor_metadata)
spatial_features_df = spatial_extractor.extract_features(traffic_df)

# Combine features
combined_df = temporal_features_df.join(spatial_features_df, ["sensor_id", "timestamp"])

# Save results
combined_df.write.mode("overwrite").parquet("hdfs://localhost:9000/traffic/features/combined")
```

#### Using the Feature Pipeline

```python
from feature_engineering.feature_pipeline import FeaturePipeline, FeaturePipelineConfig
from feature_engineering.config_manager import get_config_manager

# Load configuration
config_manager = get_config_manager()
pipeline_config = config_manager.feature_pipeline

# Initialize pipeline
pipeline = FeaturePipeline(spark, pipeline_config)

# Process features
input_df = spark.read.parquet("hdfs://localhost:9000/traffic/raw")
result_df = pipeline.process_features(input_df, "traffic_features_v1")

# Validate feature quality
quality_report = pipeline.generate_quality_report(result_df, "traffic_features_v1")
print(f"Quality Score: {quality_report['overall_score']:.2f}")
```

#### Using the Feature Store

```python
from feature_engineering.feature_store import FeatureStore

# Initialize feature store
feature_store = FeatureStore(spark, enable_mlflow=True)

# Register feature set
feature_set = feature_store.register_feature_set(
    df=result_df,
    feature_set_name="traffic_features_v1",
    description="Traffic features with temporal and spatial components",
    tags=["traffic", "temporal", "spatial", "v1"]
)

# Retrieve feature set later
df, metadata = feature_store.get_feature_set("traffic_features_v1")

# Search for specific features
speed_features = feature_store.search_features("speed")
temporal_features = feature_store.search_features("temporal")
```

### PowerShell Script Usage

#### Pipeline Management

```powershell
# Validate configuration
.\scripts\manage-feature-pipeline.ps1 -Action config-validate

# Run full pipeline
.\scripts\manage-feature-pipeline.ps1 -Action run-pipeline -FeatureSet "traffic_v1" -Verbose

# Extract only temporal features
.\scripts\manage-feature-pipeline.ps1 -Action extract-temporal -InputPath "hdfs://localhost:9000/traffic/raw" -OutputPath "hdfs://localhost:9000/traffic/temporal"

# Extract only spatial features  
.\scripts\manage-feature-pipeline.ps1 -Action extract-spatial -InputPath "hdfs://localhost:9000/traffic/raw" -OutputPath "hdfs://localhost:9000/traffic/spatial"

# Validate feature quality
.\scripts\manage-feature-pipeline.ps1 -Action validate-features -FeatureSet "traffic_v1"

# Store features in feature store
.\scripts\manage-feature-pipeline.ps1 -Action store-features -FeatureSet "traffic_v1" -InputPath "hdfs://localhost:9000/traffic/features/traffic_v1"

# List available feature sets
.\scripts\manage-feature-pipeline.ps1 -Action list-features

# Clean cache
.\scripts\manage-feature-pipeline.ps1 -Action clean-cache
```

#### Testing

```powershell
# Run comprehensive tests
.\scripts\run-feature-engineering-tests.ps1

# Run tests with verbose output
.\scripts\run-feature-engineering-tests.ps1 -Verbose

# Generate coverage report
.\scripts\run-feature-engineering-tests.ps1 -Coverage
```

## Data Quality and Validation

### Data Quality Checks

The pipeline performs several data quality checks:

1. **Missing Value Analysis**
   - Calculates missing value percentage per feature
   - Flags features exceeding the configured threshold
   - Provides imputation recommendations

2. **Outlier Detection**
   - Uses IQR method for outlier identification
   - Calculates Z-scores for statistical outliers
   - Provides outlier treatment recommendations

3. **Data Type Validation**
   - Ensures correct data types for all features
   - Validates numeric ranges for traffic metrics
   - Checks timestamp format consistency

4. **Schema Validation**
   - Validates required columns are present
   - Checks for unexpected schema changes
   - Ensures feature naming conventions

### Feature Validation Rules

#### Traffic Speed Features
- Range: 0-120 mph
- Missing values: < 10%
- Outliers: Beyond 3 standard deviations

#### Traffic Volume Features  
- Range: 0-5000 vehicles/hour
- Missing values: < 5%
- Non-negative values only

#### Temporal Features
- Hour: 0-23 range
- Day of week: 0-6 range  
- Cyclical encodings: [-1, 1] range

#### Spatial Features
- Distance features: Non-negative
- Correlation features: [-1, 1] range
- Count features: Non-negative integers

## Performance Optimization

### Spark Configuration

The pipeline includes optimized Spark settings:

```json
{
  "spark_optimization": {
    "sql": {
      "adaptive.enabled": true,
      "adaptive.coalescePartitions.enabled": true,
      "adaptive.skewJoin.enabled": true
    },
    "execution": {
      "dynamicAllocation.enabled": true,
      "dynamicAllocation.maxExecutors": 10
    },
    "memory": {
      "executor.memory": "2g",
      "executor.memoryFraction": 0.8
    }
  }
}
```

### Performance Tips

1. **Data Partitioning**
   - Partition by date for temporal queries
   - Partition by sensor_id for spatial analysis
   - Use appropriate partition sizes (128MB default)

2. **Caching Strategy**
   - Cache intermediate results for iterative operations
   - Use appropriate storage levels (MEMORY_AND_DISK_SER)
   - Clear cache when no longer needed

3. **Feature Selection**
   - Disable unused feature types in configuration
   - Reduce lag periods and rolling windows if not needed
   - Limit number of neighbors for spatial features

4. **Resource Allocation**
   - Scale executors based on data size
   - Monitor memory usage and adjust executor memory
   - Use dynamic allocation for variable workloads

## Troubleshooting

### Common Issues

#### Configuration Errors
```
Error: Feature store base path not specified
Solution: Set feature_store.storage.base_path in configuration
```

#### Missing Dependencies
```
Error: PySpark not available
Solution: Install PySpark with: pip install pyspark
```

#### HDFS Connection Issues
```
Error: Failed to connect to HDFS
Solution: Verify Hadoop cluster is running and accessible
```

#### Memory Issues  
```
Error: Java heap space
Solution: Increase executor memory in Spark configuration
```

### Debugging Steps

1. **Enable Verbose Logging**
   ```powershell
   .\scripts\manage-feature-pipeline.ps1 -Action run-pipeline -FeatureSet test -Verbose
   ```

2. **Check Configuration**
   ```powershell
   .\scripts\manage-feature-pipeline.ps1 -Action config-validate
   ```

3. **Run Tests**
   ```powershell
   .\scripts\run-feature-engineering-tests.ps1 -Verbose
   ```

4. **Check Logs**
   - Pipeline logs: `logs/feature_engineering_*.log`
   - Spark logs: `logs/spark/`
   - HDFS logs: Check Hadoop cluster logs

## Best Practices

### Development

1. **Feature Naming Conventions**
   - Use descriptive names: `speed_rolling_mean_15` not `srm15`
   - Include units where relevant: `distance_meters`
   - Use consistent prefixes: `neighbor_*`, `lag_*`

2. **Configuration Management**
   - Version control configuration files
   - Use environment-specific configurations
   - Document configuration changes

3. **Testing**
   - Test with representative data samples
   - Validate feature distributions
   - Check feature importance in models

### Production

1. **Monitoring**
   - Monitor feature drift over time
   - Track data quality metrics
   - Alert on pipeline failures

2. **Versioning**
   - Version feature sets for reproducibility
   - Document feature changes
   - Maintain backward compatibility

3. **Performance**
   - Profile pipeline performance regularly
   - Optimize bottleneck operations
   - Scale resources based on data growth

## Integration with ML Pipeline

### Feature Selection

```python
# Get features for model training
features_df, metadata = feature_store.get_feature_set("traffic_features_v1")

# Select features for specific model
model_features = [
    "speed_rolling_mean_15", "volume_rolling_mean_15",
    "hour_sin", "hour_cos", "day_of_week_sin", "day_of_week_cos",
    "neighbor_speed_avg", "upstream_volume_sum"
]

ml_ready_df = features_df.select(["sensor_id", "timestamp"] + model_features)
```

### Model Training Integration

```python
from pyspark.ml.feature import VectorAssembler
from pyspark.ml.regression import LinearRegression

# Prepare features for ML
assembler = VectorAssembler(inputCols=model_features, outputCol="features")
ml_df = assembler.transform(ml_ready_df)

# Train model
lr = LinearRegression(featuresCol="features", labelCol="target")
model = lr.fit(ml_df)

# Feature importance analysis
feature_importance = list(zip(model_features, model.coefficients))
```

## API Reference

### TemporalFeatureExtractor

#### Constructor
```python
TemporalFeatureExtractor(spark_session, config)
```

#### Methods
- `extract_features(df, timestamp_col)` - Extract all temporal features
- `extract_basic_temporal_features(df, timestamp_col)` - Basic time features only
- `extract_cyclical_features(df, timestamp_col)` - Cyclical encodings only  
- `extract_lag_features(df, feature_cols, timestamp_col)` - Lag features only
- `extract_rolling_features(df, feature_cols, timestamp_col)` - Rolling window features only

### SpatialFeatureExtractor

#### Constructor
```python
SpatialFeatureExtractor(spark_session, config, sensor_metadata)
```

#### Methods
- `extract_features(df)` - Extract all spatial features
- `extract_adjacency_features(df)` - Sensor adjacency features only
- `extract_neighbor_features(df)` - Neighbor-based features only
- `extract_directional_features(df)` - Directional flow features only
- `extract_network_features(df)` - Network topology features only

### FeaturePipeline

#### Constructor
```python
FeaturePipeline(spark_session, config)
```

#### Methods
- `process_features(df, feature_set_name)` - Run complete pipeline
- `analyze_data_quality(df)` - Perform data quality analysis
- `validate_features(df)` - Validate feature quality
- `preprocess_data(df)` - Data preprocessing only
- `scale_features(df, feature_cols)` - Feature scaling only

### FeatureStore

#### Constructor
```python
FeatureStore(spark_session, base_path, enable_mlflow)
```

#### Methods
- `register_feature_set(df, name, description, tags)` - Register new feature set
- `get_feature_set(name, version)` - Retrieve feature set
- `list_feature_sets(tags)` - List available feature sets
- `search_features(query)` - Search for specific features
- `validate_feature_quality(df, name)` - Validate feature quality

## Support and Contributing

### Getting Help

1. Check this documentation first
2. Review configuration examples
3. Run diagnostic tests
4. Check logs for error details
5. Consult team or create support ticket

### Contributing

1. Follow coding standards and naming conventions
2. Add comprehensive tests for new features
3. Update documentation for changes
4. Validate performance impact
5. Review with team before merging

### Version History

- **v1.0** - Initial implementation with temporal and spatial features
- **v1.1** - Added feature store and versioning capabilities  
- **v1.2** - Enhanced data quality validation and monitoring
- **v1.3** - Performance optimizations and configuration improvements
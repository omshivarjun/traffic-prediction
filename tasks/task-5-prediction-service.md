# Task 5: Phase 5 - Real-time Prediction Service

## Overview
Implement real-time traffic prediction service that loads trained ML models, subscribes to traffic-events topic, applies feature engineering, generates predictions with confidence intervals, and publishes to traffic-predictions topic.

**Status**: Not Started  
**Dependencies**: Task 4 (ML models must be trained and saved to HDFS)  
**Priority**: High

**Performance Targets**:
- **Latency**: < 5 seconds end-to-end
- **Throughput**: Handle 5-8 predictions/second
- **Accuracy**: Inherit from Random Forest R²=0.9996

---

## Subtask 5.1: Model Loading Service

**Status**: Not Started

### Description
Service to load trained models from HDFS on startup with caching for performance.

### Implementation Details

```python
# src/prediction-service/model_loader.py
from pyspark.ml.regression import RandomForestRegressionModel
from pyspark.ml import PipelineModel
import logging
import os

logger = logging.getLogger(__name__)

class ModelLoader:
    """Load and cache ML models from HDFS"""
    
    def __init__(self, spark):
        self.spark = spark
        self.models = {}
        self.preprocessing_pipeline = None
        
        self.HDFS_BASE = "hdfs://namenode:9000/traffic-data/models/"
    
    def load_preprocessing_pipeline(self):
        """
        Load preprocessing pipeline (scaling, encoding)
        
        Returns:
            Preprocessing PipelineModel
        """
        logger.info("Loading preprocessing pipeline...")
        
        pipeline_path = self.HDFS_BASE + "preprocessing/model"
        
        try:
            self.preprocessing_pipeline = PipelineModel.load(pipeline_path)
            logger.info("✓ Preprocessing pipeline loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load preprocessing pipeline: {e}")
            raise
        
        return self.preprocessing_pipeline
    
    def load_random_forest_model(self):
        """
        Load Random Forest model (primary production model)
        
        Returns:
            RandomForestRegressionModel
        """
        logger.info("Loading Random Forest model...")
        
        # Get latest model version
        model_path = self._get_latest_model_path("random_forest")
        
        try:
            model = RandomForestRegressionModel.load(model_path + "model")
            self.models['random_forest'] = model
            
            logger.info(f"✓ Random Forest loaded from {model_path}")
            logger.info(f"  Number of trees: {model.getNumTrees}")
            logger.info(f"  Max depth: {model.getMaxDepth()}")
            
            # Load metadata
            metadata = self._load_metadata(model_path)
            if metadata:
                logger.info(f"  R²: {metadata.get('metrics', {}).get('r2', 'N/A')}")
                logger.info(f"  RMSE: {metadata.get('metrics', {}).get('rmse', 'N/A')}")
            
        except Exception as e:
            logger.error(f"Failed to load Random Forest model: {e}")
            raise
        
        return self.models['random_forest']
    
    def _get_latest_model_path(self, model_name):
        """
        Get path to latest version of model
        
        Args:
            model_name: Model directory name
            
        Returns:
            Full HDFS path to latest model
        """
        import subprocess
        
        base_path = f"{self.HDFS_BASE}{model_name}/"
        
        # List versions
        result = subprocess.run([
            "hadoop", "fs", "-ls", base_path
        ], capture_output=True, text=True)
        
        versions = []
        for line in result.stdout.split('\n'):
            if base_path in line:
                version = line.split()[-1].replace(base_path, '').strip('/')
                if version:
                    versions.append(version)
        
        if not versions:
            raise FileNotFoundError(f"No model versions found at {base_path}")
        
        latest = sorted(versions)[-1]
        return f"{base_path}{latest}/"
    
    def _load_metadata(self, model_path):
        """Load model metadata JSON"""
        import subprocess
        import json
        import tempfile
        
        metadata_hdfs = model_path + "metadata.json"
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
                temp_path = f.name
            
            # Copy from HDFS
            subprocess.run([
                "hadoop", "fs", "-get",
                metadata_hdfs,
                temp_path
            ], check=True)
            
            # Read JSON
            with open(temp_path, 'r') as f:
                metadata = json.load(f)
            
            os.remove(temp_path)
            return metadata
            
        except Exception as e:
            logger.warning(f"Could not load metadata: {e}")
            return None
    
    def get_model(self, model_name='random_forest'):
        """
        Get cached model instance
        
        Args:
            model_name: Model to retrieve
            
        Returns:
            Cached model
        """
        if model_name not in self.models:
            if model_name == 'random_forest':
                self.load_random_forest_model()
            else:
                raise ValueError(f"Unknown model: {model_name}")
        
        return self.models[model_name]
```

### Validation Criteria
- [ ] Models loaded successfully on startup
- [ ] Preprocessing pipeline loaded
- [ ] Model metadata readable
- [ ] Model caching working
- [ ] Error handling for missing models

---

## Subtask 5.2: Real-time Feature Engineering

**Status**: Not Started

### Description
Apply same feature engineering as training phase to incoming traffic events in real-time.

### Implementation Details

```python
# src/prediction-service/realtime_features.py
from pyspark.sql.functions import (
    col, hour, dayofweek, sin, cos, when, lit,
    lag, avg, stddev, unix_timestamp
)
from pyspark.sql.window import Window
import math
import logging

logger = logging.getLogger(__name__)

class RealtimeFeatureExtractor:
    """Extract features from streaming traffic events"""
    
    def __init__(self, spark):
        self.spark = spark
        
        # LA city center
        self.LA_CENTER_LAT = 34.0522
        self.LA_CENTER_LON = -118.2437
        
        # Free flow speeds
        self.FREE_FLOW_SPEEDS = {
            "101": 65, "110": 65, "405": 65, "10": 65, "default": 60
        }
    
    def extract_all_features(self, df):
        """
        Apply all feature engineering steps
        
        Args:
            df: DataFrame with traffic events
            
        Returns:
            DataFrame with ML-ready features
        """
        # Time features
        df = self._extract_time_features(df)
        
        # Spatial features
        df = self._extract_spatial_features(df)
        
        # Traffic features
        df = self._extract_traffic_features(df)
        
        # Historical features (requires state management)
        df = self._extract_historical_features(df)
        
        return df
    
    def _extract_time_features(self, df):
        """Extract time-based features"""
        
        # Hour with sine/cosine encoding
        df = df.withColumn("hour", hour(col("timestamp")))
        df = df.withColumn(
            "hour_sin",
            sin(col("hour") * 2 * lit(math.pi) / 24)
        )
        df = df.withColumn(
            "hour_cos",
            cos(col("hour") * 2 * lit(math.pi) / 24)
        )
        
        # Day of week
        df = df.withColumn("day_of_week", dayofweek(col("timestamp")))
        
        # Is weekend
        df = df.withColumn(
            "is_weekend",
            when((col("day_of_week") == 1) | (col("day_of_week") == 7), 1).otherwise(0)
        )
        
        # Is rush hour
        df = df.withColumn(
            "is_rush_hour",
            when(
                ((col("hour") >= 7) & (col("hour") < 9)) |
                ((col("hour") >= 16) & (col("hour") < 19)),
                1
            ).otherwise(0)
        )
        
        # Time since midnight
        df = df.withColumn(
            "time_since_midnight",
            col("hour") * 3600
        )
        
        return df
    
    def _extract_spatial_features(self, df):
        """Extract spatial features"""
        
        # Extract highway type from sensor_id
        from pyspark.sql.functions import regexp_extract, sqrt, pow
        
        df = df.withColumn(
            "highway_type",
            regexp_extract(col("sensor_id"), r"METR_LA_(\d+)_", 1)
        )
        
        # Encode highway
        df = df.withColumn(
            "highway_encoded",
            when(col("highway_type") == "101", 1)
            .when(col("highway_type") == "110", 2)
            .when(col("highway_type") == "405", 3)
            .when(col("highway_type") == "10", 4)
            .otherwise(0)
        )
        
        # Normalize coordinates (if available)
        if "latitude" in df.columns:
            df = df.withColumn(
                "lat_normalized",
                (col("latitude") - 33.7) / (34.5 - 33.7)
            )
            df = df.withColumn(
                "lon_normalized",
                (col("longitude") - (-119)) / ((-117) - (-119))
            )
            
            # Distance from center
            df = df.withColumn(
                "distance_from_center",
                sqrt(
                    pow((col("latitude") - lit(self.LA_CENTER_LAT)) * 111, 2) +
                    pow((col("longitude") - lit(self.LA_CENTER_LON)) * 111 * 
                        cos(lit(self.LA_CENTER_LAT) * lit(math.pi) / 180), 2)
                )
            )
        
        return df
    
    def _extract_traffic_features(self, df):
        """Extract traffic-specific features"""
        
        # Free flow speed
        df = df.withColumn(
            "free_flow_speed",
            when(col("highway_type") == "101", 65)
            .when(col("highway_type") == "110", 65)
            .when(col("highway_type") == "405", 65)
            .when(col("highway_type") == "10", 65)
            .otherwise(60)
        )
        
        # Traffic efficiency (81% importance!)
        df = df.withColumn(
            "traffic_efficiency",
            col("speed") / col("free_flow_speed")
        )
        
        # Occupancy ratio (if available)
        if "occupancy" in df.columns:
            df = df.withColumn(
                "occupancy_ratio",
                col("occupancy") / 100.0
            )
        
        # Flow rate
        if "volume" in df.columns:
            df = df.withColumn(
                "flow_rate",
                col("volume") * 12  # 5-min to hourly
            )
        
        return df
    
    def _extract_historical_features(self, df):
        """
        Extract historical features
        
        NOTE: For real-time, we need state management.
        This is a simplified version using window functions.
        """
        window_spec = Window.partitionBy("sensor_id").orderBy("timestamp")
        
        # Lagged speeds
        df = df.withColumn("speed_lag_1", lag(col("speed"), 1).over(window_spec))
        df = df.withColumn("speed_lag_2", lag(col("speed"), 2).over(window_spec))
        df = df.withColumn("speed_lag_3", lag(col("speed"), 3).over(window_spec))
        
        # Moving averages
        window_15min = window_spec.rowsBetween(-2, 0)
        df = df.withColumn("speed_ma_15min", avg(col("speed")).over(window_15min))
        
        window_30min = window_spec.rowsBetween(-5, 0)
        df = df.withColumn("speed_ma_30min", avg(col("speed")).over(window_30min))
        
        window_60min = window_spec.rowsBetween(-11, 0)
        df = df.withColumn("speed_ma_60min", avg(col("speed")).over(window_60min))
        
        # Speed variance
        df = df.withColumn(
            "speed_variance",
            stddev(col("speed")).over(window_30min)
        )
        
        return df
```

### Validation Criteria
- [ ] All features extracted in real-time
- [ ] Feature values match training distribution
- [ ] No null values in critical features
- [ ] Performance < 100ms per event

---

## Subtask 5.3: Prediction Generation with Confidence Intervals

**Status**: Not Started

### Description
Generate speed predictions using Random Forest model with confidence intervals.

### Implementation Details

```python
# src/prediction-service/predictor.py
from pyspark.sql.functions import col, struct, to_json, udf
from pyspark.sql.types import DoubleType, StructType, StructField
import logging
import numpy as np

logger = logging.getLogger(__name__)

class TrafficPredictor:
    """Generate traffic predictions with confidence intervals"""
    
    def __init__(self, model, preprocessing_pipeline):
        self.model = model
        self.preprocessing_pipeline = preprocessing_pipeline
    
    def predict(self, features_df):
        """
        Generate predictions with confidence intervals
        
        Args:
            features_df: DataFrame with extracted features
            
        Returns:
            DataFrame with predictions and confidence intervals
        """
        # Apply preprocessing (scaling, encoding)
        features_transformed = self.preprocessing_pipeline.transform(features_df)
        
        # Generate predictions
        predictions = self.model.transform(features_transformed)
        
        # Random Forest provides tree-level predictions
        # We can calculate confidence interval from tree variance
        predictions = predictions.withColumn(
            "predicted_speed",
            col("prediction")
        )
        
        # Calculate confidence interval (±2 std deviations = ~95%)
        # For Random Forest, we approximate from RMSE
        # From training: RMSE = 0.752
        predictions = predictions.withColumn(
            "confidence_interval_lower",
            col("predicted_speed") - lit(0.752 * 2)
        )
        predictions = predictions.withColumn(
            "confidence_interval_upper",
            col("predicted_speed") + lit(0.752 * 2)
        )
        
        # Confidence score (based on variance if available)
        predictions = predictions.withColumn(
            "confidence_score",
            lit(0.9996)  # Model R² score
        )
        
        # Select output columns
        output_cols = [
            "sensor_id",
            "timestamp",
            "predicted_speed",
            "confidence_interval_lower",
            "confidence_interval_upper",
            "confidence_score",
            "speed",  # Actual speed (if available for monitoring)
            "traffic_efficiency"  # Key feature (81% importance)
        ]
        
        # Filter to available columns
        available_cols = [c for c in output_cols if c in predictions.columns]
        predictions = predictions.select(available_cols)
        
        return predictions
    
    def predict_with_advanced_confidence(self, features_df):
        """
        Advanced confidence calculation using tree-level predictions
        
        For production use with ensemble models
        """
        # This would require accessing individual tree predictions
        # Not directly supported in Spark MLlib
        # Alternative: Use prediction variance from trees
        
        pass
```

### Validation Criteria
- [ ] Predictions generated successfully
- [ ] Confidence intervals calculated
- [ ] Prediction latency < 100ms
- [ ] Predictions in reasonable range (0-80 mph)

---

## Subtask 5.4: Kafka Publisher for Predictions

**Status**: Not Started

### Description
Publish predictions to traffic-predictions Kafka topic in Avro format.

### Implementation Details

```python
# src/prediction-service/kafka_publisher.py
from confluent_kafka import Producer
from confluent_kafka.avro import AvroProducer
from confluent_kafka.avro import load as avro_load
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class PredictionPublisher:
    """Publish predictions to Kafka topic"""
    
    def __init__(self, bootstrap_servers, schema_registry_url, topic="traffic-predictions"):
        self.topic = topic
        
        # Load Avro schema
        with open('schemas/traffic-prediction.avsc', 'r') as f:
            self.value_schema = avro_load(f)
        
        # Initialize Avro producer
        self.producer = AvroProducer({
            'bootstrap.servers': bootstrap_servers,
            'schema.registry.url': schema_registry_url
        }, default_value_schema=self.value_schema)
    
    def publish_predictions(self, predictions_df):
        """
        Publish predictions to Kafka
        
        Args:
            predictions_df: Spark DataFrame with predictions
        """
        # Convert to Pandas for iteration
        predictions_pandas = predictions_df.toPandas()
        
        for _, row in predictions_pandas.iterrows():
            prediction_record = {
                "sensor_id": row['sensor_id'],
                "timestamp": int(row['timestamp'].timestamp() * 1000),
                "predicted_speed": float(row['predicted_speed']),
                "confidence_interval_lower": float(row['confidence_interval_lower']),
                "confidence_interval_upper": float(row['confidence_interval_upper']),
                "confidence_score": float(row['confidence_score']),
                "model_version": "random_forest_v1",
                "prediction_timestamp": int(datetime.now().timestamp() * 1000)
            }
            
            try:
                # Publish to Kafka
                self.producer.produce(
                    topic=self.topic,
                    value=prediction_record
                )
                
            except Exception as e:
                logger.error(f"Failed to publish prediction: {e}")
        
        # Flush
        self.producer.flush()
        
        logger.info(f"Published {len(predictions_pandas)} predictions to {self.topic}")
    
    def publish_single(self, prediction):
        """Publish a single prediction"""
        self.producer.produce(
            topic=self.topic,
            value=prediction
        )
        self.producer.flush()
```

### Validation Criteria
- [ ] Predictions published to traffic-predictions topic
- [ ] Avro schema validation passes
- [ ] No data loss during publishing
- [ ] Throughput matches input rate

---

## Subtask 5.5: HDFS Prediction Storage

**Status**: Not Started

### Description
Store predictions to HDFS for historical analysis and model monitoring.

### Implementation Details

```python
# src/prediction-service/hdfs_storage.py
from pyspark.sql.functions import col, year, month, dayofmonth
import logging

logger = logging.getLogger(__name__)

class PredictionStorage:
    """Store predictions to HDFS"""
    
    HDFS_BASE = "hdfs://namenode:9000/traffic-data/predictions/"
    
    def __init__(self, spark):
        self.spark = spark
    
    def store_predictions(self, predictions_df):
        """
        Store predictions to HDFS in partitioned Parquet
        
        Args:
            predictions_df: DataFrame with predictions
        """
        # Add partition columns
        predictions_df = predictions_df.withColumn("year", year(col("timestamp")))
        predictions_df = predictions_df.withColumn("month", month(col("timestamp")))
        predictions_df = predictions_df.withColumn("day", dayofmonth(col("timestamp")))
        
        # Write to HDFS
        output_path = self.HDFS_BASE
        
        logger.info(f"Writing predictions to {output_path}")
        
        predictions_df.write \
            .mode("append") \
            .partitionBy("year", "month", "day") \
            .parquet(output_path)
        
        logger.info(f"Stored {predictions_df.count()} predictions")
```

---

## Subtask 5.6: Complete Prediction Service

**Status**: Not Started

### Description
Integrate all components into streaming prediction service.

### Implementation Details

```python
# src/prediction-service/service.py
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, LongType
import logging

from model_loader import ModelLoader
from realtime_features import RealtimeFeatureExtractor
from predictor import TrafficPredictor
from kafka_publisher import PredictionPublisher
from hdfs_storage import PredictionStorage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RealTimePredictionService:
    """Real-time traffic prediction service"""
    
    def __init__(self):
        # Initialize Spark
        self.spark = SparkSession.builder \
            .appName("TrafficPredictionService") \
            .config("spark.streaming.stopGracefullyOnShutdown", "true") \
            .config("spark.sql.streaming.checkpointLocation", "/tmp/spark-checkpoint") \
            .getOrCreate()
        
        # Load models
        logger.info("Loading ML models...")
        loader = ModelLoader(self.spark)
        self.preprocessing_pipeline = loader.load_preprocessing_pipeline()
        self.model = loader.load_random_forest_model()
        
        # Initialize components
        self.feature_extractor = RealtimeFeatureExtractor(self.spark)
        self.predictor = TrafficPredictor(self.model, self.preprocessing_pipeline)
        self.publisher = PredictionPublisher(
            bootstrap_servers="kafka-broker1:9092",
            schema_registry_url="http://schema-registry:8082"
        )
        self.storage = PredictionStorage(self.spark)
        
        logger.info("✓ Prediction service initialized")
    
    def run(self):
        """Start streaming prediction service"""
        logger.info("Starting real-time prediction service...")
        
        # Define input schema
        traffic_schema = StructType([
            StructField("sensor_id", StringType(), True),
            StructField("timestamp", LongType(), True),
            StructField("speed", DoubleType(), True),
            StructField("volume", DoubleType(), True),
            StructField("occupancy", DoubleType(), True)
        ])
        
        # Read from Kafka traffic-events topic
        traffic_stream = self.spark.readStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", "kafka-broker1:9092") \
            .option("subscribe", "traffic-events") \
            .option("startingOffsets", "latest") \
            .load()
        
        # Parse JSON
        traffic_df = traffic_stream.select(
            from_json(col("value").cast("string"), traffic_schema).alias("data")
        ).select("data.*")
        
        # Extract features
        logger.info("Applying feature engineering...")
        features_df = self.feature_extractor.extract_all_features(traffic_df)
        
        # Generate predictions
        logger.info("Generating predictions...")
        predictions_df = self.predictor.predict(features_df)
        
        # Output to Kafka and HDFS
        query = predictions_df.writeStream \
            .foreachBatch(self._process_batch) \
            .outputMode("append") \
            .start()
        
        logger.info("✓ Prediction service running")
        logger.info(f"  Input: traffic-events topic")
        logger.info(f"  Output: traffic-predictions topic + HDFS")
        logger.info(f"  Model: Random Forest (R²=0.9996)")
        
        query.awaitTermination()
    
    def _process_batch(self, batch_df, batch_id):
        """
        Process each micro-batch
        
        Args:
            batch_df: Batch DataFrame
            batch_id: Batch identifier
        """
        if batch_df.count() == 0:
            return
        
        logger.info(f"Processing batch {batch_id} with {batch_df.count()} records")
        
        # Publish to Kafka
        self.publisher.publish_predictions(batch_df)
        
        # Store to HDFS
        self.storage.store_predictions(batch_df)
        
        logger.info(f"✓ Batch {batch_id} processed successfully")

if __name__ == "__main__":
    service = RealTimePredictionService()
    service.run()
```

**Execution**:
```bash
spark-submit \
  --master spark://spark-master:7077 \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.1.2 \
  --executor-memory 2G \
  --driver-memory 1G \
  src/prediction-service/service.py
```

**Docker Service**:
```yaml
# Add to docker-compose.yml
prediction-service:
  build:
    context: .
    dockerfile: src/prediction-service/Dockerfile
  container_name: prediction-service
  environment:
    SPARK_MASTER: spark://spark-master:7077
    KAFKA_BROKERS: kafka-broker1:9092
    SCHEMA_REGISTRY: http://schema-registry:8082
  depends_on:
    - spark-master
    - kafka-broker1
  networks:
    - traffic-network
```

---

## Completion Criteria

### Phase 5 Complete When:
- [ ] Models loaded from HDFS successfully
- [ ] Real-time feature extraction working
- [ ] Predictions generated with confidence intervals
- [ ] Predictions published to traffic-predictions topic
- [ ] Predictions stored to HDFS
- [ ] End-to-end latency < 5 seconds
- [ ] Throughput matches input rate (5-8 rec/sec)
- [ ] Service runs continuously without errors
- [ ] Model R²=0.9996 accuracy maintained

### Performance Targets
- **Latency**: < 5 seconds per prediction
- **Throughput**: 5-8 predictions/second
- **Accuracy**: R²=0.9996 (from model)
- **Availability**: 99%+ uptime

---

## Next Steps
→ Proceed to **Task 6: Dashboard Visualization**

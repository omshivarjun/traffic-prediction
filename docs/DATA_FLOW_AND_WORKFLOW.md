# 🌊 Traffic Prediction System - Complete Data Flow & Workflow Documentation

> **Comprehensive guide documenting the end-to-end data flow and workflow for all system components**

**Last Updated:** October 7, 2025  
**System Version:** Production v1.0  
**Architecture:** Multi-layered Big Data Pipeline (Kafka + Hadoop + Spark + Next.js)

---

## 📋 Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Layers](#architecture-layers)
3. [Data Flow Diagrams](#data-flow-diagrams)
4. [Component Workflows](#component-workflows)
5. [Integration Points](#integration-points)
6. [Deployment Flow](#deployment-flow)

---

## 🎯 System Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        TRAFFIC PREDICTION SYSTEM                          │
│                     Multi-Layered Big Data Pipeline                       │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│   DATA       │      │   STREAM     │      │    BATCH     │
│  INGESTION   │─────▶│  PROCESSING  │─────▶│  PROCESSING  │
│   LAYER      │      │    LAYER     │      │    LAYER     │
└──────────────┘      └──────────────┘      └──────────────┘
       │                     │                      │
       │                     │                      │
       ▼                     ▼                      ▼
┌──────────────────────────────────────────────────────────┐
│              STORAGE LAYER (HDFS + Kafka)                 │
└──────────────────────────────────────────────────────────┘
       │                     │                      │
       │                     │                      │
       ▼                     ▼                      ▼
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│  PREDICTION  │      │  ANALYTICS   │      │  FRONTEND    │
│   SERVICE    │◀─────│   SERVICE    │◀─────│  DASHBOARD   │
│   LAYER      │      │    LAYER     │      │    LAYER     │
└──────────────┘      └──────────────┘      └──────────────┘
```

### Core Technologies

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Ingestion** | Python Producer, Kafka Producer API | Ingest METR-LA traffic data |
| **Streaming** | Kafka, Kafka Streams (Node.js), Spark Streaming | Real-time event processing |
| **Batch** | Hadoop MapReduce, Spark MLlib | Feature engineering & ML training |
| **Storage** | HDFS, HBase, Kafka Topics | Persistent & distributed storage |
| **ML** | Spark MLlib, Python scikit-learn | Model training & predictions |
| **API** | Next.js API Routes, FastAPI | RESTful and SSE endpoints |
| **Frontend** | Next.js 15, React 19, Leaflet | Interactive dashboard |

---

## 🏗️ Architecture Layers

### Layer 1: Data Ingestion

**Purpose:** Ingest raw traffic data from METR-LA dataset and external sources

```
┌─────────────────────────────────────────────────────────────────┐
│                      DATA INGESTION LAYER                        │
└─────────────────────────────────────────────────────────────────┘

Data Sources:
  📊 METR-LA Dataset (CSV)
  📊 Test Scenarios (JSON)
  📊 Real-time Sensors (Future)

         │
         ▼

┌─────────────────────────────────────────────────────────────────┐
│  PRODUCERS                                                       │
│  ┌────────────────────┐  ┌──────────────────┐                  │
│  │ TrafficProducer    │  │ Test Event       │                  │
│  │ (Python)           │  │ Generator (PS)   │                  │
│  │                    │  │                  │                  │
│  │ • Reads CSV        │  │ • Generates      │                  │
│  │ • Parses METR-LA   │  │   mock events    │                  │
│  │ • Rate limiting    │  │ • For testing    │                  │
│  │ • Batching         │  │                  │                  │
│  └────────────────────┘  └──────────────────┘                  │
└─────────────────────────────────────────────────────────────────┘

         │
         ▼

┌─────────────────────────────────────────────────────────────────┐
│  KAFKA TOPICS (Raw Events)                                       │
│  • traffic-raw          : Raw unvalidated events                 │
│  • traffic-events       : Validated events                       │
└─────────────────────────────────────────────────────────────────┘
```

**Key Files:**
- `src/producer/traffic_producer.py` - Main producer implementation
- `scripts/kafka_producer.py` - Test event producer
- `scripts/send-test-events.ps1` - PowerShell test script
- `scripts/generate-metr-la-data.py` - METR-LA dataset loader

**Data Flow:**

1. **CSV Reading** → Producer reads METR-LA CSV with 207 sensors
2. **Event Construction** → Creates TrafficEvent objects with:
   - `event_id`: Unique identifier
   - `segment_id`: Road segment (LA_001 - LA_207)
   - `timestamp`: Unix timestamp (milliseconds)
   - `speed_kmh`: Speed in km/h
   - `volume_vph`: Vehicles per hour
   - `occupancy_percent`: Lane occupancy %
   - `coordinates`: Lat/Lon [latitude, longitude]
   - `metadata`: Additional context
3. **Kafka Publishing** → Sends to `traffic-raw` topic
4. **Partitioning** → Events partitioned by `segment_id` for parallelism

**Configuration:**
```ini
# producer_config.ini
[producer]
kafka_bootstrap_servers = localhost:9092
topic_name = traffic-raw
replay_speed = 1.0        # Real-time = 1.0
batch_size = 100
compression_type = snappy
acks = 1
```

---

### Layer 2: Stream Processing

**Purpose:** Real-time validation, transformation, and aggregation of traffic events

```
┌─────────────────────────────────────────────────────────────────┐
│                    STREAM PROCESSING LAYER                       │
└─────────────────────────────────────────────────────────────────┘

Kafka Topics (Input):
  • traffic-raw (26 partitions)

         │
         ▼

┌─────────────────────────────────────────────────────────────────┐
│  STREAM PROCESSORS                                               │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  Node.js Kafka Streams Processor                       │    │
│  │  (src/stream-processing/index.js)                      │    │
│  │                                                         │    │
│  │  1. Consume from traffic-raw                           │    │
│  │  2. Validate event schema                              │    │
│  │  3. Check data quality                                 │    │
│  │  4. Flatten nested structures                          │    │
│  │  5. Add processing metadata                            │    │
│  │  6. Publish to traffic-events                          │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  Spark Structured Streaming Processor                  │    │
│  │  (scripts/spark_streaming_processor.py)                │    │
│  │                                                         │    │
│  │  1. Read from Kafka (traffic-events)                   │    │
│  │  2. Windowed aggregations (5-min tumbling)             │    │
│  │  3. Calculate statistics (avg, min, max, std)          │    │
│  │  4. Write to HDFS (Parquet)                            │    │
│  │  5. Maintain streaming state                           │    │
│  └────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘

         │
         ▼

Kafka Topics (Output):
  • traffic-events (12 partitions)        : Validated events
  • processed-traffic-aggregates (8)      : Aggregated data

HDFS Output:
  • /traffic-data/streaming/raw-events
  • /traffic-data/streaming/sensor-aggregates
  • /traffic-data/streaming/road-aggregates
```

**Stream Processing Workflows:**

#### Workflow 1: Event Validation & Transformation

```javascript
// Node.js Stream Processor (index.js)

Input Event (traffic-raw):
{
  "event_id": "evt_12345",
  "segment_id": "LA_123",
  "timestamp": 1696723200000,
  "speed_kmh": 65.5,
  "volume_vph": 450,
  "occupancy_percent": 12.3,
  "coordinates": [34.0522, -118.2437],
  "metadata": { "quality": "high" }
}

         │
         ▼

[Validation Layer]
✓ Schema validation (required fields present)
✓ Data type checks (speed > 0, volume >= 0)
✓ Range validation (0 <= occupancy <= 100)
✓ Coordinate bounds check

         │
         ▼

[Transformation Layer]
• Flatten nested structures
• Add processing timestamp
• Add processor_id
• Calculate derived fields

         │
         ▼

Output Event (traffic-events):
{
  "event_id": "evt_12345",
  "segment_id": "LA_123",
  "timestamp": 1696723200000,
  "speed_kmh": 65.5,
  "volume_vph": 450,
  "occupancy_percent": 12.3,
  "latitude": 34.0522,
  "longitude": -118.2437,
  "quality": "high",
  "processed_at": "2025-10-07T12:00:00.123Z",
  "processor_id": "stream-processor-1",
  "validation_status": "valid"
}
```

#### Workflow 2: Windowed Aggregation

```python
# Spark Streaming Processor (spark_streaming_processor.py)

[Read from Kafka]
  topic: traffic-events
  format: JSON
  
         │
         ▼

[Define Windows]
  • Tumbling window: 5 minutes
  • Watermark: 10 seconds (handle late data)
  
         │
         ▼

[Aggregation Operations]
  GROUP BY: segment_id, window
  METRICS:
    - avg_speed: AVG(speed_kmh)
    - min_speed: MIN(speed_kmh)
    - max_speed: MAX(speed_kmh)
    - std_speed: STDDEV(speed_kmh)
    - total_volume: SUM(volume_vph)
    - avg_occupancy: AVG(occupancy_percent)
    - event_count: COUNT(*)
  
         │
         ▼

[Output to HDFS]
  Path: /traffic-data/streaming/sensor-aggregates
  Format: Parquet
  Partitioning: year/month/day/hour
  Checkpoint: /tmp/spark-checkpoint/sensor-aggregates
```

**Key Files:**
- `src/stream-processing/index.js` - Node.js event processor
- `src/stream-processing/processors/` - Specialized processors
- `scripts/spark_streaming_processor.py` - Spark streaming job
- `src/validation/input_data_validator.py` - Validation logic

**Performance Metrics:**
- **Throughput:** ~1,000 events/second
- **Latency:** <100ms (validation) + <5s (aggregation)
- **Error Rate:** <0.1%

---

### Layer 3: Batch Processing

**Purpose:** Feature engineering and ML model training on historical data

```
┌─────────────────────────────────────────────────────────────────┐
│                     BATCH PROCESSING LAYER                       │
└─────────────────────────────────────────────────────────────────┘

HDFS Input:
  • /traffic-data/raw                    : Raw historical events
  • /traffic-data/streaming/aggregates   : Streaming aggregates

         │
         ▼

┌─────────────────────────────────────────────────────────────────┐
│  FEATURE ENGINEERING PIPELINE                                    │
│  (src/batch-processing/spark_feature_engineering.py)             │
│                                                                   │
│  Step 1: Load Data from HDFS                                     │
│    → Read Parquet files                                          │
│    → Schema validation                                           │
│                                                                   │
│  Step 2: Temporal Features                                       │
│    → hour, day_of_week, day_of_month, month                      │
│    → is_weekend, is_rush_hour                                    │
│    → hour_sin, hour_cos (cyclical encoding)                      │
│                                                                   │
│  Step 3: Rolling Window Features                                 │
│    → speed_rolling_avg (15min, 30min, 1hr)                       │
│    → speed_rolling_std, speed_rolling_min, speed_rolling_max     │
│    → volume_rolling_avg, volume_rolling_std                      │
│                                                                   │
│  Step 4: Lagged Features                                         │
│    → speed_lag_15min, speed_lag_30min, speed_lag_60min           │
│    → volume_lag_15min, volume_lag_30min                          │
│                                                                   │
│  Step 5: Segment-Level Features                                  │
│    → segment_avg_speed, segment_std_speed                        │
│    → segment_avg_volume, segment_std_volume                      │
│    → segment_min_speed, segment_max_speed                        │
│                                                                   │
│  Step 6: Derived Features                                        │
│    → speed_change = speed - speed_lag_15min                      │
│    → speed_normalized = (speed - mean) / std                     │
│    → congestion_index = volume / avg_volume                      │
│                                                                   │
│  Step 7: Save to HDFS                                            │
│    → ml_features (Parquet, partitioned by segment_id)            │
│    → segment_profiles (summary stats per segment)                │
│    → hourly_aggregates (time-based patterns)                     │
└─────────────────────────────────────────────────────────────────┘

         │
         ▼

HDFS Output:
  • /traffic-data/features/ml_features
  • /traffic-data/features/segment_profiles
  • /traffic-data/features/hourly_aggregates

         │
         ▼

┌─────────────────────────────────────────────────────────────────┐
│  ML MODEL TRAINING PIPELINE                                      │
│  (src/batch-processing/spark_train_models.py)                    │
│                                                                   │
│  Step 1: Load Features                                           │
│    → Read from /traffic-data/features/ml_features                │
│    → Schema validation                                           │
│                                                                   │
│  Step 2: Feature Preparation                                     │
│    → Select feature columns (18 features)                        │
│    → VectorAssembler: Create feature vectors                     │
│    → StandardScaler: Normalize features                          │
│                                                                   │
│  Step 3: Train/Val/Test Split                                    │
│    → Train: 70% (chronological split)                            │
│    → Validation: 15%                                             │
│    → Test: 15%                                                   │
│                                                                   │
│  Step 4: Model Training                                          │
│    ┌─────────────────────────────────────────┐                  │
│    │ Linear Regression                       │                  │
│    │  • Fast baseline model                  │                  │
│    │  • Interpretable coefficients           │                  │
│    └─────────────────────────────────────────┘                  │
│    ┌─────────────────────────────────────────┐                  │
│    │ Random Forest Regressor                 │                  │
│    │  • numTrees: 100                        │                  │
│    │  • maxDepth: 10                         │                  │
│    │  • Handles non-linearity                │                  │
│    └─────────────────────────────────────────┘                  │
│    ┌─────────────────────────────────────────┐                  │
│    │ Gradient Boosted Trees                  │                  │
│    │  • maxIter: 100                         │                  │
│    │  • stepSize: 0.1                        │                  │
│    │  • Best accuracy                        │                  │
│    └─────────────────────────────────────────┘                  │
│    ┌─────────────────────────────────────────┐                  │
│    │ Decision Tree Regressor                 │                  │
│    │  • maxDepth: 10                         │                  │
│    │  • Simple interpretable model           │                  │
│    └─────────────────────────────────────────┘                  │
│                                                                   │
│  Step 5: Model Evaluation                                        │
│    → RMSE (Root Mean Squared Error)                              │
│    → R² Score (Coefficient of Determination)                     │
│    → MAE (Mean Absolute Error)                                   │
│    → Select best model based on validation RMSE                  │
│                                                                   │
│  Step 6: Model Persistence                                       │
│    → Save models to HDFS                                         │
│    → Save preprocessing pipeline                                 │
│    → Export model metadata (JSON)                                │
│    → Generate model evaluation report                            │
└─────────────────────────────────────────────────────────────────┘

         │
         ▼

HDFS Output:
  • /traffic-data/models/linear_regression
  • /traffic-data/models/random_forest
  • /traffic-data/models/gradient_boosted_trees
  • /traffic-data/models/decision_tree
  • /traffic-data/models/preprocessing_pipeline
  • /traffic-data/models/metadata.json
```

**Batch Job Execution:**

```bash
# Submit Feature Engineering Job to YARN
spark-submit \
  --master yarn \
  --deploy-mode cluster \
  --num-executors 4 \
  --executor-memory 2G \
  --driver-memory 1G \
  src/batch-processing/spark_feature_engineering.py \
  hdfs://namenode:9000/traffic-data/raw \
  hdfs://namenode:9000/traffic-data/features

# Submit ML Training Job
spark-submit \
  --master yarn \
  --deploy-mode cluster \
  --num-executors 4 \
  --executor-memory 2G \
  --driver-memory 1G \
  src/batch-processing/spark_train_models.py \
  hdfs://namenode:9000/traffic-data/features/ml_features \
  hdfs://namenode:9000/traffic-data/models
```

**Key Files:**
- `src/batch-processing/spark_feature_engineering.py` - Feature pipeline
- `src/batch-processing/spark_train_models.py` - ML training
- `src/batch-processing/train_models.py` - Alternative training script
- `src/feature_engineering/feature_pipeline.py` - Feature orchestrator
- `src/ml/ml_training_pipeline.py` - Complete ML pipeline

**Feature Engineering Output Schema:**

```python
ml_features Schema:
├── segment_id: string
├── timestamp: long
├── speed: double
├── volume: double
├── occupancy: double
├── hour: integer
├── day_of_week: integer
├── day_of_month: integer
├── month: integer
├── is_weekend: integer (0/1)
├── is_rush_hour: integer (0/1)
├── speed_rolling_avg: double
├── speed_rolling_std: double
├── speed_rolling_min: double
├── speed_rolling_max: double
├── speed_change: double
├── speed_normalized: double
├── segment_avg_speed: double
├── segment_std_speed: double
├── volume_rolling_avg: double
├── volume_rolling_std: double
├── segment_avg_volume: double
└── segment_std_volume: double
```

---

### Layer 4: Storage Layer

**Purpose:** Persistent storage for raw data, features, models, and streaming state

```
┌─────────────────────────────────────────────────────────────────┐
│                        STORAGE LAYER                             │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────────┐         ┌──────────────────────┐
│   HDFS (Hadoop 3.2)  │         │  Kafka Topics        │
│   Port: 9000         │         │  Port: 9092          │
├──────────────────────┤         ├──────────────────────┤
│ Directory Structure: │         │ Topics:              │
│                      │         │                      │
│ /traffic-data/       │         │ • traffic-raw        │
│   ├── raw/           │         │   (26 partitions)    │
│   │   └── year/      │         │                      │
│   │       └── month/ │         │ • traffic-events     │
│   │           └── day/│        │   (12 partitions)    │
│   │                  │         │                      │
│   ├── streaming/     │         │ • processed-traffic- │
│   │   ├── raw-events/│         │   aggregates         │
│   │   ├── sensor-    │         │   (8 partitions)     │
│   │   │   aggregates/│         │                      │
│   │   └── road-      │         │ • traffic-predictions│
│   │       aggregates/│         │   (4 partitions)     │
│   │                  │         │                      │
│   ├── features/      │         │ • traffic-incidents  │
│   │   ├── ml_features│         │   (4 partitions)     │
│   │   ├── segment_   │         │                      │
│   │   │   profiles/  │         │ Retention:           │
│   │   └── hourly_    │         │ • 7 days (default)   │
│   │       aggregates/│         │                      │
│   │                  │         │ Compression:         │
│   └── models/        │         │ • Snappy             │
│       ├── linear_    │         │                      │
│       │   regression/│         │ Replication:         │
│       ├── random_    │         │ • Factor: 1          │
│       │   forest/    │         │                      │
│       ├── gradient_  │         │ Consumer Groups:     │
│       │   boosted_   │         │ • stream-processor   │
│       │   trees/     │         │ • prediction-service │
│       ├── preprocessing│        │ • nextjs-dashboard   │
│       └── metadata.  │         │                      │
│           json       │         │                      │
│                      │         │                      │
│ Format: Parquet      │         │ Format: Avro/JSON    │
│ Compression: Snappy  │         │ Schema Registry:     │
│ Replication: 3       │         │ • Port 8081          │
│ Block Size: 128MB    │         │ • Avro schemas       │
└──────────────────────┘         └──────────────────────┘

┌──────────────────────┐
│   HBase (Optional)   │
│   Port: 16010        │
├──────────────────────┤
│ Tables:              │
│                      │
│ • traffic_events     │
│   Row Key: segment_id│
│            + timestamp│
│                      │
│ • predictions        │
│   Row Key: segment_id│
│            + timestamp│
│                      │
│ Column Families:     │
│ • data (sensor data) │
│ • meta (metadata)    │
│                      │
│ Use Case:            │
│ • Real-time lookups  │
│ • Fast key-value     │
│   access             │
└──────────────────────┘
```

**HDFS Directory Details:**

| Path | Purpose | Format | Partitioning |
|------|---------|--------|-------------|
| `/traffic-data/raw` | Raw historical events | Parquet | year/month/day |
| `/traffic-data/streaming/raw-events` | Real-time events from Kafka | Parquet | year/month/day/hour |
| `/traffic-data/streaming/sensor-aggregates` | 5-min aggregated sensor data | Parquet | year/month/day |
| `/traffic-data/features/ml_features` | ML-ready features | Parquet | segment_id |
| `/traffic-data/features/segment_profiles` | Statistical profiles per segment | Parquet | - |
| `/traffic-data/models/` | Trained ML models | Spark ML | model_type |

**Kafka Topic Configuration:**

```yaml
Topics:
  traffic-raw:
    partitions: 26
    replication-factor: 1
    retention.ms: 604800000  # 7 days
    compression.type: snappy
    
  traffic-events:
    partitions: 12
    replication-factor: 1
    retention.ms: 604800000
    compression.type: snappy
    
  processed-traffic-aggregates:
    partitions: 8
    replication-factor: 1
    retention.ms: 2592000000  # 30 days
    
  traffic-predictions:
    partitions: 4
    replication-factor: 1
    retention.ms: 604800000
    cleanup.policy: delete
```

---

### Layer 5: Prediction Service

**Purpose:** Real-time traffic prediction using trained ML models

```
┌─────────────────────────────────────────────────────────────────┐
│                     PREDICTION SERVICE LAYER                     │
└─────────────────────────────────────────────────────────────────┘

Input Sources:
  1. Kafka: traffic-events topic
  2. HDFS: Trained models
  3. HBase: Historical patterns (optional)

         │
         ▼

┌─────────────────────────────────────────────────────────────────┐
│  STREAMING PREDICTION SERVICE                                    │
│  (src/ml/simple_streaming_predictor.py)                          │
│                                                                   │
│  Initialization:                                                 │
│    1. Load trained model from HDFS                               │
│    2. Load preprocessing pipeline                                │
│    3. Connect to Kafka (consumer + producer)                     │
│    4. Initialize feature cache                                   │
│                                                                   │
│  Real-Time Processing Loop:                                      │
│                                                                   │
│    ┌──────────────────────────────────────┐                     │
│    │ 1. Consume Event from Kafka          │                     │
│    │    Topic: traffic-events              │                     │
│    │    Event: { segment_id, timestamp,    │                     │
│    │            speed, volume, ... }       │                     │
│    └──────────────────────────────────────┘                     │
│              │                                                    │
│              ▼                                                    │
│    ┌──────────────────────────────────────┐                     │
│    │ 2. Feature Extraction                 │                     │
│    │    • Extract temporal features        │                     │
│    │    • Get historical patterns          │                     │
│    │    • Calculate rolling averages       │                     │
│    │    • Retrieve segment statistics      │                     │
│    └──────────────────────────────────────┘                     │
│              │                                                    │
│              ▼                                                    │
│    ┌──────────────────────────────────────┐                     │
│    │ 3. Feature Vector Assembly            │                     │
│    │    Features:                          │                     │
│    │    [hour, day_of_week, is_weekend,    │                     │
│    │     is_rush_hour, speed_rolling_avg,  │                     │
│    │     speed_rolling_std, volume_avg,    │                     │
│    │     segment_avg_speed, ...]           │                     │
│    └──────────────────────────────────────┘                     │
│              │                                                    │
│              ▼                                                    │
│    ┌──────────────────────────────────────┐                     │
│    │ 4. Model Prediction                   │                     │
│    │    predicted_speed_15min = model.     │                     │
│    │                   predict(features)   │                     │
│    │    predicted_speed_30min = model.     │                     │
│    │                   predict(features2)  │                     │
│    └──────────────────────────────────────┘                     │
│              │                                                    │
│              ▼                                                    │
│    ┌──────────────────────────────────────┐                     │
│    │ 5. Post-Processing                    │                     │
│    │    • Clamp predictions (0-120 mph)    │                     │
│    │    • Calculate confidence intervals   │                     │
│    │    • Assign congestion category:      │                     │
│    │      - free_flow (>50 mph)            │                     │
│    │      - light_traffic (35-50)          │                     │
│    │      - heavy_traffic (20-35)          │                     │
│    │      - severe_congestion (<20)        │                     │
│    └──────────────────────────────────────┘                     │
│              │                                                    │
│              ▼                                                    │
│    ┌──────────────────────────────────────┐                     │
│    │ 6. Create Prediction Event            │                     │
│    │    {                                  │                     │
│    │      prediction_id,                   │                     │
│    │      segment_id,                      │                     │
│    │      timestamp,                       │                     │
│    │      current_speed,                   │                     │
│    │      current_volume,                  │                     │
│    │      predicted_speed,                 │                     │
│    │      predicted_volume,                │                     │
│    │      prediction_horizon_minutes: 15,  │                     │
│    │      confidence_score,                │                     │
│    │      category,                        │                     │
│    │      coordinates: [lat, lon],         │                     │
│    │      model_version                    │                     │
│    │    }                                  │                     │
│    └──────────────────────────────────────┘                     │
│              │                                                    │
│              ▼                                                    │
│    ┌──────────────────────────────────────┐                     │
│    │ 7. Publish to Kafka                   │                     │
│    │    Topic: traffic-predictions         │                     │
│    │    Partition Key: segment_id          │                     │
│    └──────────────────────────────────────┘                     │
└─────────────────────────────────────────────────────────────────┘

         │
         ▼

Kafka Topic (Output):
  • traffic-predictions (4 partitions)

         │
         ▼

Consumers:
  • Next.js Dashboard (via predictionConsumer.ts)
  • Analytics Service
  • Alerting System
```

**Prediction Event Schema:**

```json
{
  "prediction_id": "pred_abc123",
  "segment_id": "LA_123",
  "timestamp": 1696723200000,
  "prediction_timestamp": 1696724100000,
  "current_speed": 45.5,
  "current_volume": 450,
  "predicted_speed": 38.2,
  "predicted_volume": 520,
  "prediction_horizon_minutes": 15,
  "confidence_score": 0.87,
  "confidence_interval": {
    "lower": 35.1,
    "upper": 41.3
  },
  "category": "heavy_traffic",
  "coordinates": [34.0522, -118.2437],
  "model_version": "random_forest_v1.2",
  "features_used": [...],
  "processing_time_ms": 45
}
```

**Key Files:**
- `src/ml/simple_streaming_predictor.py` - Main prediction service
- `src/prediction/prediction_service.py` - Alternative implementation
- `src/ml/streaming_predictor.py` - Advanced predictor
- `src/prediction/realtime_prediction_service.py` - Real-time service

---

### Layer 6: Frontend Dashboard

**Purpose:** Interactive web dashboard for visualizing predictions and analytics

```
┌─────────────────────────────────────────────────────────────────┐
│                      FRONTEND DASHBOARD LAYER                    │
│                    Next.js 15 + React 19 + Leaflet              │
└─────────────────────────────────────────────────────────────────┘

User Access:
  http://localhost:3000/predictions

         │
         ▼

┌─────────────────────────────────────────────────────────────────┐
│  NEXT.JS APP ROUTER                                              │
│  (src/app/)                                                      │
│                                                                   │
│  Pages:                                                          │
│  • /                    → Home page                              │
│  • /predictions         → Main predictions dashboard             │
│  • /city-planner        → City planner tools                     │
│                                                                   │
│  API Routes:                                                     │
│  • GET  /api/predictions        → Fetch latest predictions       │
│  • GET  /api/predictions/stream → SSE real-time stream           │
│  • POST /api/predictions        → Receive prediction (webhook)   │
└─────────────────────────────────────────────────────────────────┘

         │
         ▼

┌─────────────────────────────────────────────────────────────────┐
│  BACKEND API LAYER (Next.js API Routes)                          │
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ GET /api/predictions/stream                            │     │
│  │ (src/app/api/predictions/stream/route.ts)              │     │
│  │                                                         │     │
│  │ Server-Sent Events Endpoint                            │     │
│  │                                                         │     │
│  │ 1. Get singleton Kafka consumer                        │     │
│  │ 2. Start consumer if not running                       │     │
│  │    → Connect to Kafka broker                           │     │
│  │    → Wait 1 second for broker initialization           │     │
│  │    → Subscribe to 'traffic-predictions' topic          │     │
│  │ 3. Create SSE stream                                   │     │
│  │ 4. Send initial connection message                     │     │
│  │ 5. Send current predictions (initial state)            │     │
│  │ 6. Subscribe to new prediction events                  │     │
│  │ 7. Stream predictions to client in real-time           │     │
│  │ 8. Send stats every 10 seconds                         │     │
│  │ 9. Handle client disconnect (cleanup)                  │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ Kafka Consumer (Singleton)                             │     │
│  │ (src/lib/kafka/predictionConsumer.ts)                  │     │
│  │                                                         │     │
│  │ Responsibilities:                                      │     │
│  │ • Connect to Kafka broker (localhost:9092)             │     │
│  │ • Subscribe to traffic-predictions topic               │     │
│  │ • Consume prediction messages                          │     │
│  │ • Maintain latest predictions Map (by segment_id)      │     │
│  │ • Calculate statistics (total, avg speed, categories)  │     │
│  │ • Notify subscribers on new predictions                │     │
│  │ • Handle reconnection and errors                       │     │
│  │                                                         │     │
│  │ Methods:                                               │     │
│  │ • start() - Start consuming                            │     │
│  │ • stop() - Stop and disconnect                         │     │
│  │ • getAllPredictions() - Get current state              │     │
│  │ • getStats() - Get aggregated stats                    │     │
│  │ • onPrediction(callback) - Subscribe to updates        │     │
│  │ • isRunning() - Check consumer status                  │     │
│  └────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘

         │
         ▼

┌─────────────────────────────────────────────────────────────────┐
│  REACT FRONTEND COMPONENTS                                       │
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ PredictionsPage                                        │     │
│  │ (src/app/predictions/page.tsx)                         │     │
│  │                                                         │     │
│  │ Main Dashboard Container:                              │     │
│  │ • Uses usePredictions hook                             │     │
│  │ • Renders TrafficMapWithPredictions                    │     │
│  │ • Renders PredictionAnalyticsPanel                     │     │
│  │ • Shows connection status                              │     │
│  │ • Displays error messages                              │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ usePredictions Hook                                    │     │
│  │ (src/hooks/usePredictions.ts)                          │     │
│  │                                                         │     │
│  │ SSE Connection Manager:                                │     │
│  │ 1. Create EventSource to /api/predictions/stream       │     │
│  │ 2. Handle connection events                            │     │
│  │ 3. Process SSE messages:                               │     │
│  │    • 'connected' → Set connection status               │     │
│  │    • 'initial' → Load initial predictions              │     │
│  │    • 'prediction' → Add new prediction                 │     │
│  │    • 'stats' → Update statistics                       │     │
│  │    • 'error' → Display error                           │     │
│  │ 4. Auto-reconnect on disconnect (max 5 attempts)       │     │
│  │ 5. Cleanup on unmount                                  │     │
│  │                                                         │     │
│  │ State Management:                                      │     │
│  │ • predictions: TrafficPrediction[]                     │     │
│  │ • stats: PredictionStats                               │     │
│  │ • isConnected: boolean                                 │     │
│  │ • error: string | null                                 │     │
│  │ • lastUpdate: Date | null                              │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ TrafficMapWithPredictions                              │     │
│  │ (src/components/TrafficMapWithPredictions.tsx)         │     │
│  │                                                         │     │
│  │ Interactive Leaflet Map:                               │     │
│  │ • Display LA region (34.0522, -118.2437)               │     │
│  │ • Render prediction markers                            │     │
│  │ • Color-coded by congestion category:                  │     │
│  │   - Green: Free flow (>50 mph)                         │     │
│  │   - Yellow: Light traffic (35-50 mph)                  │     │
│  │   - Orange: Heavy traffic (20-35 mph)                  │     │
│  │   - Red: Severe congestion (<20 mph)                   │     │
│  │ • Click marker → Show prediction details               │     │
│  │ • Real-time updates (predictions prop)                 │     │
│  │ • Auto-zoom to fit all markers                         │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ PredictionAnalyticsPanel                               │     │
│  │ (src/components/PredictionAnalyticsPanel.tsx)          │     │
│  │                                                         │     │
│  │ Real-Time Statistics Dashboard:                        │     │
│  │ • Total predictions count                              │     │
│  │ • Average predicted speed                              │     │
│  │ • Average current speed                                │     │
│  │ • Congestion breakdown (pie chart)                     │     │
│  │ • Recent predictions list                              │     │
│  │ • Last update timestamp                                │     │
│  │ • Connection status indicator                          │     │
│  └────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

**SSE Message Flow:**

```javascript
// Client-side (usePredictions.ts)

1. Create EventSource connection:
   const eventSource = new EventSource('/api/predictions/stream')

2. Handle messages:
   eventSource.onmessage = (event) => {
     const message = JSON.parse(event.data)
     
     switch(message.type) {
       case 'connected':
         // Set isConnected = true
         break
         
       case 'initial':
         // Load initial predictions
         setPredictions(message.predictions)
         break
         
       case 'prediction':
         // Add new prediction
         setPredictions(prev => [message.data, ...prev].slice(0, 50))
         setLastUpdate(new Date())
         break
         
       case 'stats':
         // Update statistics
         setStats(message.data)
         break
         
       case 'error':
         // Display error
         setError(message.message)
         break
     }
   }

3. Handle errors and reconnection:
   eventSource.onerror = () => {
     setIsConnected(false)
     // Attempt reconnect (max 5 times)
     if (reconnectAttempts < 5) {
       setTimeout(() => connect(), 3000)
     }
   }

4. Cleanup on unmount:
   return () => eventSource.close()
```

**Component Hierarchy:**

```
App (layout.tsx)
 │
 ├─ HomePage (page.tsx)
 │
 └─ PredictionsPage (predictions/page.tsx)
     │
     ├─ usePredictions() hook
     │   └─ EventSource → /api/predictions/stream
     │       └─ Kafka Consumer → traffic-predictions topic
     │
     ├─ TrafficMapWithPredictions
     │   ├─ Leaflet Map
     │   ├─ TileLayer (OpenStreetMap)
     │   └─ Markers (color-coded by category)
     │
     └─ PredictionAnalyticsPanel
         ├─ Statistics Cards
         ├─ Congestion Chart
         └─ Recent Predictions List
```

**Key Files:**
- `src/app/predictions/page.tsx` - Main dashboard page
- `src/hooks/usePredictions.ts` - SSE hook
- `src/components/TrafficMapWithPredictions.tsx` - Map component
- `src/components/PredictionAnalyticsPanel.tsx` - Analytics panel
- `src/lib/kafka/predictionConsumer.ts` - Kafka consumer singleton
- `src/app/api/predictions/stream/route.ts` - SSE endpoint
- `src/app/api/predictions/route.ts` - REST endpoint

---

## 🔄 Complete End-to-End Data Flow

### E2E Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                  COMPLETE END-TO-END DATA FLOW                        │
└──────────────────────────────────────────────────────────────────────┘

[1. DATA INGESTION]
  METR-LA CSV (207 sensors × 12,672 timestamps)
         │
         ▼
  TrafficProducer.py
    • Parses CSV
    • Creates TrafficEvent objects
    • Sends to Kafka
         │
         ▼
  Kafka Topic: traffic-raw (26 partitions)

─────────────────────────────────────────────────────────────────────

[2. STREAM PROCESSING - VALIDATION]
  Kafka Consumer (Node.js)
         │
         ▼
  ValidationProcessor
    • Schema validation
    • Data quality checks
    • Range validation
         │
         ▼
  TransformProcessor
    • Flatten structures
    • Add metadata
    • Calculate derived fields
         │
         ▼
  Kafka Topic: traffic-events (12 partitions)

─────────────────────────────────────────────────────────────────────

[3. STREAM PROCESSING - AGGREGATION]
  Kafka Consumer (Spark Streaming)
         │
         ▼
  WindowedAggregationProcessor
    • 5-minute tumbling windows
    • Calculate statistics (avg, min, max, std)
    • Group by segment_id
         │
         ▼
  HDFS: /traffic-data/streaming/sensor-aggregates (Parquet)
  Kafka Topic: processed-traffic-aggregates (8 partitions)

─────────────────────────────────────────────────────────────────────

[4. BATCH PROCESSING - FEATURE ENGINEERING]
  HDFS Input: /traffic-data/raw
         │
         ▼
  Spark Job: FeatureEngineeringJob
    • Load historical data
    • Extract temporal features
    • Create rolling window features
    • Calculate lagged features
    • Generate segment statistics
         │
         ▼
  HDFS Output:
    • /traffic-data/features/ml_features
    • /traffic-data/features/segment_profiles
    • /traffic-data/features/hourly_aggregates

─────────────────────────────────────────────────────────────────────

[5. BATCH PROCESSING - ML TRAINING]
  HDFS Input: /traffic-data/features/ml_features
         │
         ▼
  Spark Job: MLTrainingJob
    • Load features
    • Prepare training data (VectorAssembler + Scaler)
    • Split: Train (70%) / Val (15%) / Test (15%)
    • Train 4 models:
      - Linear Regression
      - Random Forest
      - Gradient Boosted Trees
      - Decision Tree
    • Evaluate (RMSE, R², MAE)
    • Select best model
         │
         ▼
  HDFS Output:
    • /traffic-data/models/random_forest (best model)
    • /traffic-data/models/preprocessing_pipeline
    • /traffic-data/models/metadata.json

─────────────────────────────────────────────────────────────────────

[6. REAL-TIME PREDICTION]
  Kafka Topic: traffic-events
         │
         ▼
  StreamingPredictorService
    • Load model from HDFS
    • Consume events
    • Extract features
    • Make predictions
    • Post-process results
         │
         ▼
  Kafka Topic: traffic-predictions (4 partitions)

─────────────────────────────────────────────────────────────────────

[7. FRONTEND DELIVERY]
  Kafka Topic: traffic-predictions
         │
         ▼
  Next.js Kafka Consumer (predictionConsumer.ts)
    • Consume predictions
    • Maintain latest state
    • Calculate statistics
         │
         ▼
  SSE Stream (/api/predictions/stream)
    • Stream to connected clients
    • Send stats every 10s
         │
         ▼
  React Frontend (usePredictions hook)
    • EventSource connection
    • Real-time updates
         │
         ▼
  Dashboard Components
    • TrafficMapWithPredictions (Leaflet map)
    • PredictionAnalyticsPanel (stats)
         │
         ▼
  User Browser
    • Visual map with color-coded markers
    • Real-time congestion updates
    • Analytics dashboard
```

### Timing & Latency

| Stage | Latency | Throughput |
|-------|---------|------------|
| **Data Ingestion** | ~10ms | 1,000 events/sec |
| **Stream Validation** | ~50ms | 800 events/sec |
| **Stream Aggregation** | ~5s (window) | 500 events/sec |
| **Batch Feature Engineering** | ~10-30 min | N/A (batch) |
| **Batch ML Training** | ~1-2 hours | N/A (batch) |
| **Real-Time Prediction** | ~100ms | 200 predictions/sec |
| **Frontend SSE Delivery** | ~50ms | Real-time |
| **End-to-End (ingestion → dashboard)** | **~6 seconds** | - |

---

## 🔗 Integration Points

### 1. Kafka ↔ Stream Processor

**Technology:** KafkaJS (Node.js), Kafka Consumer API (Python)

**Connection:**
```javascript
// Node.js Stream Processor
const kafka = new Kafka({
  clientId: 'stream-processor-client',
  brokers: ['kafka-broker1:9092'],
  retry: { initialRetryTime: 300, retries: 10 },
  connectionTimeout: 10000
})

const consumer = kafka.consumer({ groupId: 'stream-processor-group' })
await consumer.connect()
await consumer.subscribe({ topic: 'traffic-raw' })
```

**Data Exchange:**
- **Input:** Raw traffic events (JSON)
- **Output:** Validated events (JSON)
- **Error Handling:** Invalid events sent to `invalid-events` topic

---

### 2. Kafka ↔ Spark Streaming

**Technology:** Spark Structured Streaming, Kafka Source

**Connection:**
```python
# Spark Streaming Job
df = spark.readStream \
  .format("kafka") \
  .option("kafka.bootstrap.servers", "kafka-broker1:9092") \
  .option("subscribe", "traffic-events") \
  .option("startingOffsets", "latest") \
  .load()
```

**Data Exchange:**
- **Input:** Validated traffic events (JSON)
- **Output:** 
  - HDFS: Parquet files
  - Kafka: `processed-traffic-aggregates` topic
- **Checkpointing:** `/tmp/spark-checkpoint/sensor-aggregates`

---

### 3. HDFS ↔ Spark Batch Jobs

**Technology:** Spark SQL, Parquet

**Connection:**
```python
# Feature Engineering Job
df = spark.read.parquet("hdfs://namenode:9000/traffic-data/raw")

# ML Training Job
features_df = spark.read.parquet("hdfs://namenode:9000/traffic-data/features/ml_features")
```

**Data Exchange:**
- **Read:** Parquet files (compressed with Snappy)
- **Write:** Partitioned Parquet files
- **Schema Evolution:** Supported via Parquet metadata

---

### 4. HDFS ↔ Prediction Service

**Technology:** Spark MLlib Model Persistence

**Connection:**
```python
from pyspark.ml import PipelineModel

# Load model
model = PipelineModel.load("hdfs://namenode:9000/traffic-data/models/random_forest")

# Load preprocessing pipeline
preprocessor = PipelineModel.load("hdfs://namenode:9000/traffic-data/models/preprocessing_pipeline")
```

**Data Exchange:**
- **Model Format:** Spark ML model (directory structure)
- **Metadata:** JSON file with model version, metrics
- **Versioning:** Timestamp-based directories

---

### 5. Kafka ↔ Next.js Dashboard

**Technology:** KafkaJS, Server-Sent Events (SSE)

**Connection:**
```typescript
// predictionConsumer.ts
const kafka = new Kafka({
  clientId: 'nextjs-dashboard',
  brokers: ['localhost:9092'],
  retry: { retries: 8, initialRetryTime: 300 }
})

const consumer = kafka.consumer({
  groupId: 'nextjs-prediction-consumer-group',
  sessionTimeout: 60000
})

await consumer.connect()
await new Promise(resolve => setTimeout(resolve, 1000)) // Wait for broker
await consumer.subscribe({ topic: 'traffic-predictions' })
```

**Data Exchange:**
- **Input:** Traffic predictions (JSON)
- **Output:** SSE stream to browser
- **Error Handling:** Reconnection with exponential backoff

---

## 🚀 Deployment Flow

### Development Environment

```bash
# 1. Start Docker Infrastructure
docker compose up -d

# 2. Verify Services
docker ps
# Expected: Kafka, Zookeeper, HDFS NameNode/DataNode, YARN ResourceManager

# 3. Start Stream Processor
cd src/stream-processing
npm install
npm start

# 4. Start Prediction Service (optional)
cd src/ml
python simple_streaming_predictor.py

# 5. Start Next.js Dashboard
npm install
npm run dev

# 6. Generate Test Data
powershell -File .\scripts\send-test-events.ps1 -Count 100

# 7. Access Dashboard
open http://localhost:3000/predictions
```

### Production Deployment

```bash
# 1. Build Frontend
npm run build
npm start  # Production server

# 2. Submit Batch Jobs to YARN
spark-submit \
  --master yarn \
  --deploy-mode cluster \
  --num-executors 4 \
  --executor-memory 2G \
  src/batch-processing/spark_feature_engineering.py

spark-submit \
  --master yarn \
  --deploy-mode cluster \
  --num-executors 4 \
  --executor-memory 2G \
  src/batch-processing/spark_train_models.py

# 3. Deploy Stream Processor (Docker)
docker build -t stream-processor src/stream-processing
docker run -d --name stream-processor \
  --network kafka-network \
  stream-processor

# 4. Start Prediction Service
python src/ml/simple_streaming_predictor.py \
  --kafka-broker kafka-broker1:9092 \
  --model-path hdfs://namenode:9000/traffic-data/models/random_forest

# 5. Monitor Services
# Kafka UI: http://localhost:8080
# HDFS UI: http://localhost:9870
# YARN UI: http://localhost:8088
# Next.js: http://localhost:3000
```

---

## 📊 Monitoring & Observability

### Key Metrics

| Component | Metrics | Dashboard |
|-----------|---------|-----------|
| **Kafka** | Messages/sec, Lag, Partition distribution | Kafka UI (port 8080) |
| **Stream Processor** | Throughput, Error rate, Latency | Console logs, Health endpoint |
| **Spark Jobs** | Task duration, Memory usage, Shuffle metrics | YARN UI (port 8088) |
| **HDFS** | Storage usage, Block replication, DataNode health | HDFS UI (port 9870) |
| **Prediction Service** | Predictions/sec, Model latency, Accuracy | Application logs |
| **Next.js** | Active connections, SSE clients, Prediction count | Browser console |

### Health Checks

```bash
# Kafka broker health
docker exec kafka-broker1 kafka-broker-api-versions --bootstrap-server localhost:9092

# HDFS health
docker exec namenode hdfs dfsadmin -report

# Stream processor health
curl http://localhost:3001/health

# Prediction service health
curl http://localhost:8000/health

# Next.js health
curl http://localhost:3000/api/health
```

---

## 🎓 Conclusion

This comprehensive documentation covers the complete data flow and workflow for all components in the Traffic Prediction System. Each layer is designed for:

- **Scalability:** Kafka partitioning, Spark distributed processing
- **Reliability:** Error handling, retry logic, checkpointing
- **Performance:** Batching, compression, caching
- **Maintainability:** Modular design, clear interfaces
- **Observability:** Logging, metrics, health checks

For component-specific details, refer to individual documentation files in the `docs/` directory.

---

## 🔧 Troubleshooting

### Common Issues

#### 1. Multiple Kafka Consumer Instances (Rebalancing Errors)

**Symptoms:**
```
{"level":"ERROR","logger":"kafkajs","error":"The group is rebalancing, so a rejoin is needed"}
🔌 Starting prediction consumer for SSE stream...
⚠️ Consumer already exists, waiting for connection...
```

**Cause:** Multiple Next.js processes or hot-reload creating duplicate consumers in the same consumer group.

**Solution:**
```powershell
# Kill all Node.js processes
Get-Process -Name node -ErrorAction SilentlyContinue | Stop-Process -Force

# Restart Next.js cleanly
npm run dev
```

**Prevention:** The singleton pattern in `predictionConsumer.ts` helps, but during development restarts, ensure only one Next.js instance is running.

---

#### 2. SSE Connection Drops After 60 Seconds

**Symptoms:**
```
GET /api/predictions/stream 200 in 60436ms
📡 Client disconnected from prediction stream
```

**Cause:** Browser EventSource timeout or network proxy closing idle connections.

**Solution:**
- Stats messages sent every 10 seconds keep connection alive
- Client auto-reconnects (5 attempts with 3s delay)
- Check for network proxies or VPN timeouts

---

#### 3. No Predictions Appearing on Dashboard

**Symptoms:**
- Dashboard shows "Connected! Waiting for predictions..."
- No markers on map

**Cause:** No events in `traffic-predictions` topic.

**Solution:**
```powershell
# Send test events
.\scripts\send-test-events.ps1 -Count 10

# Check if prediction service is running
docker ps | findstr prediction

# Verify Kafka topics
docker exec kafka-broker1 kafka-topics --list --bootstrap-server localhost:9092
```

---

#### 4. 404 Errors for `/predictions/stream`

**Symptoms:**
```
GET /predictions/stream 404 in 67ms
```

**Cause:** Incorrect endpoint (should be `/api/predictions/stream`).

**Solution:**
- The correct SSE endpoint is `/api/predictions/stream` (note the `/api/` prefix)
- Check `usePredictions.ts` hook is using correct path
- Clear browser cache if old routes are cached

---

#### 5. Kafka Consumer Not Starting

**Symptoms:**
```
❌ Failed to connect to Kafka broker
Error: Broker not connected
```

**Cause:** Kafka broker not running or connection timeout.

**Solution:**
```powershell
# Check Kafka containers
docker ps | findstr kafka

# Restart Kafka services
docker compose restart kafka-broker1 zookeeper

# Verify Kafka health
docker exec kafka-broker1 kafka-broker-api-versions --bootstrap-server localhost:9092
```

---

## 📞 Support & Contact

For issues, questions, or contributions:
- **GitHub Issues:** [traffic-prediction/issues](https://github.com/omshivarjun/traffic-prediction/issues)
- **Documentation:** See other files in `docs/` directory
- **Team Structure:** Refer to `AGENTS.md`

---

**Document Version:** 1.0  
**Last Updated:** October 7, 2025  
**Maintained By:** Traffic Prediction Team  
**Contact:** See `AGENTS.md` for team structure

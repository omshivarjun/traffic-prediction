# METR-LA Traffic Prediction System - ML Pipeline & Data Processing Analysis

## Table of Contents
1. [Machine Learning Architecture Overview](#machine-learning-architecture-overview)
2. [Stream Processing Pipeline](#stream-processing-pipeline)
3. [Batch Processing Pipeline](#batch-processing-pipeline)
4. [Data Models and Schemas](#data-models-and-schemas)
5. [Feature Engineering Pipeline](#feature-engineering-pipeline)
6. [Model Training and Deployment](#model-training-and-deployment)

## Machine Learning Architecture Overview

The ML pipeline follows a **Lambda Architecture** pattern, combining both real-time stream processing and batch processing for comprehensive traffic prediction:

### **Lambda Architecture Components**

```
┌─────────────────────────────────────────────────────────────────┐
│                        Speed Layer                               │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐  │
│  │  Kafka Streams  │ -> │ Stream Processor│ -> │ Real-time   │  │
│  │  (Raw Events)   │    │   (Aggregation) │    │ Predictions │  │
│  └─────────────────┘    └─────────────────┘    └─────────────┘  │
└─────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────┐
│                        Batch Layer                               │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐  │
│  │     HDFS        │ -> │  Spark MLlib    │ -> │ ML Models   │  │
│  │ (Historical)    │    │   (Training)    │    │ (Export)    │  │
│  └─────────────────┘    └─────────────────┘    └─────────────┘  │
└─────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────┐
│                       Serving Layer                              │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐  │
│  │     HBase       │ -> │   Prediction    │ -> │  Frontend   │  │
│  │  (Real-time)    │    │     API         │    │    UI       │  │
│  └─────────────────┘    └─────────────────┘    └─────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Why Lambda Architecture:**
- **Low Latency**: Stream processing provides real-time predictions
- **High Throughput**: Batch processing handles large historical datasets
- **Fault Tolerance**: Batch layer can recompute speed layer if needed
- **Data Quality**: Batch processing ensures data accuracy and completeness

## Stream Processing Pipeline

### **Kafka Topics and Data Flow**

The system uses **4 primary Kafka topics** for different stages of processing:

```yaml
Topics:
  - raw-traffic-events (26 partitions)
  - traffic-incidents (8 partitions)  
  - processed-traffic-aggregates (12 partitions)
  - traffic-predictions (6 partitions)
```

### **Stream Processing Architecture (TypeScript/Node.js)**

Located in `src/stream-processing/`, the real-time processing uses **Kafka Streams** with Node.js:

```typescript
// src/stream-processing/processors/trafficEventProcessor.ts
import { Kafka, Consumer, Producer } from 'kafkajs';
import { TrafficEvent, ProcessedTrafficAggregate } from '../types/trafficTypes';

export class TrafficEventProcessor {
    private kafka: Kafka;
    private consumer: Consumer;
    private producer: Producer;
    private stateStore: Map<string, TrafficSegmentState> = new Map();

    constructor() {
        this.kafka = new Kafka({
            clientId: 'traffic-event-processor',
            brokers: [process.env.KAFKA_BROKERS || 'localhost:9092'],
            retry: {
                retries: 5,
                initialRetryTime: 100,
                factor: 2
            }
        });
        
        this.consumer = this.kafka.consumer({ groupId: 'traffic-processing-group' });
        this.producer = this.kafka.producer({
            maxInFlightRequests: 1,
            idempotent: true,
            transactionTimeout: 30000
        });
    }
```

**Why TypeScript for Stream Processing:**
- **Type Safety**: Prevents runtime errors in stream transformations
- **Developer Experience**: Better IDE support and refactoring
- **JSON Integration**: Natural handling of Kafka JSON messages
- **Performance**: V8 optimizations for high-throughput processing

**Kafka Configuration Analysis:**
- **Idempotent Producer**: Prevents duplicate messages during retries
- **Max In Flight**: Ensures message ordering within partitions
- **Retry Logic**: Exponential backoff for connection resilience
- **Transaction Timeout**: Ensures processing completion

### **Windowed Aggregation Implementation**

```typescript
interface TrafficSegmentState {
    segmentId: string;
    windowStart: number;
    windowEnd: number;
    speedSum: number;
    volumeSum: number;
    eventCount: number;
    lastUpdated: number;
}

public async processTrafficEvents(): Promise<void> {
    await this.consumer.subscribe({ topic: 'raw-traffic-events', fromBeginning: false });
    
    await this.consumer.run({
        eachMessage: async ({ topic, partition, message }) => {
            try {
                const event: TrafficEvent = JSON.parse(message.value?.toString() || '{}');
                
                // Window-based aggregation (5-minute tumbling windows)
                const windowSize = 5 * 60 * 1000; // 5 minutes in milliseconds
                const eventTimestamp = new Date(event.timestamp).getTime();
                const windowStart = Math.floor(eventTimestamp / windowSize) * windowSize;
                const windowEnd = windowStart + windowSize;
                
                const stateKey = `${event.segment_id}_${windowStart}`;
                
                // Update or create segment state
                const currentState = this.stateStore.get(stateKey) || {
                    segmentId: event.segment_id,
                    windowStart,
                    windowEnd,
                    speedSum: 0,
                    volumeSum: 0,
                    eventCount: 0,
                    lastUpdated: Date.now()
                };
                
                // Aggregate metrics
                currentState.speedSum += event.speed || 0;
                currentState.volumeSum += event.volume || 0;
                currentState.eventCount += 1;
                currentState.lastUpdated = Date.now();
                
                this.stateStore.set(stateKey, currentState);
                
                // Emit aggregate when window is complete or near complete
                if (this.shouldEmitWindow(currentState)) {
                    await this.emitAggregatedData(currentState);
                    this.stateStore.delete(stateKey); // Clean up completed windows
                }
                
            } catch (error) {
                console.error('Error processing traffic event:', error);
            }
        },
    });
}
```

**Stream Processing Design Patterns:**

**Windowed Aggregation:**
- **Tumbling Windows**: 5-minute non-overlapping time windows
- **State Management**: In-memory state store for window accumulation
- **Window Completion**: Emit when window time expires
- **Memory Management**: Clean up completed windows

**Fault Tolerance:**
- **Consumer Groups**: Automatic partition rebalancing
- **Offset Management**: Kafka handles message acknowledgment
- **Error Handling**: Continue processing despite individual message errors
- **State Recovery**: Rebuild state from Kafka log on restart

### **Real-time Prediction Logic**

```typescript
interface PredictionFeatures {
    avgSpeed: number;
    volumeDensity: number;
    timeOfDay: number;
    dayOfWeek: number;
    historicalAvgSpeed: number;
    incidentNearby: boolean;
    weatherConditions?: string;
}

private async generatePrediction(aggregate: ProcessedTrafficAggregate): Promise<TrafficPrediction> {
    const features = this.extractFeatures(aggregate);
    
    // Simple linear regression model (placeholder for ML model)
    const prediction = this.applyLinearModel(features);
    
    // Enhanced prediction with confidence scoring
    const confidence = this.calculateConfidence(features, prediction);
    
    return {
        sensor_id: aggregate.sensor_id,
        segment_id: aggregate.segment_id,
        timestamp: new Date().toISOString(),
        predicted_speed: prediction.speed,
        predicted_volume: prediction.volume,
        confidence_score: confidence,
        model_name: 'streaming_linear_regression',
        prediction_horizon: 15, // 15-minute ahead prediction
        features_used: Object.keys(features)
    };
}

private extractFeatures(aggregate: ProcessedTrafficAggregate): PredictionFeatures {
    const now = new Date();
    const timeOfDay = now.getHours() + (now.getMinutes() / 60);
    const dayOfWeek = now.getDay();
    
    return {
        avgSpeed: aggregate.avg_speed,
        volumeDensity: aggregate.total_volume / (aggregate.segment_length || 1),
        timeOfDay,
        dayOfWeek,
        historicalAvgSpeed: this.getHistoricalAverage(aggregate.segment_id, timeOfDay, dayOfWeek),
        incidentNearby: this.checkIncidentProximity(aggregate.segment_id),
        weatherConditions: this.getCurrentWeather()
    };
}
```

**Feature Engineering Analysis:**
- **Temporal Features**: Time of day, day of week for cyclical patterns
- **Spatial Features**: Volume density, historical averages
- **Context Features**: Incidents, weather conditions
- **Real-time Features**: Current speed, volume measurements

## Batch Processing Pipeline

### **Hadoop MapReduce Jobs (Java)**

The batch processing system uses **Hadoop 3.2.1** with **Spark MLlib 3.1.2** for large-scale ML training:

```xml
<!-- src/batch-processing/pom.xml -->
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.trafficprediction</groupId>
    <artifactId>batch-processing</artifactId>
    <version>1.0-SNAPSHOT</version>
    <packaging>jar</packaging>

    <properties>
        <maven.compiler.source>11</maven.compiler.source>
        <maven.compiler.target>11</maven.compiler.target>
        <hadoop.version>3.2.1</hadoop.version>
        <spark.version>3.1.2</spark.version>
        <hive.version>3.1.2</hive.version>
    </properties>

    <dependencies>
        <dependency>
            <groupId>org.apache.hadoop</groupId>
            <artifactId>hadoop-client</artifactId>
            <version>${hadoop.version}</version>
        </dependency>
        <dependency>
            <groupId>org.apache.spark</groupId>
            <artifactId>spark-core_2.12</artifactId>
            <version>${spark.version}</version>
        </dependency>
        <dependency>
            <groupId>org.apache.spark</groupId>
            <artifactId>spark-mllib_2.12</artifactId>
            <version>${spark.version}</version>
        </dependency>
    </dependencies>
</project>
```

**Why These Versions:**
- **Hadoop 3.2.1**: Stable release with HDFS 3.0 features
- **Spark 3.1.2**: Performance improvements and ML algorithm enhancements
- **Hive 3.1.2**: SQL interface for batch data analysis
- **Java 11**: LTS version with performance optimizations

### **Feature Engineering Job**

```java
// src/batch-processing/src/main/java/com/trafficprediction/jobs/FeatureEngineeringJob.java
package com.trafficprediction.jobs;

import org.apache.spark.SparkConf;
import org.apache.spark.api.java.JavaSparkContext;
import org.apache.spark.sql.*;
import org.apache.spark.sql.types.*;
import static org.apache.spark.sql.functions.*;

public class FeatureEngineeringJob {
    
    public static void main(String[] args) {
        SparkConf conf = new SparkConf()
            .setAppName("Traffic Feature Engineering")
            .setMaster("yarn")
            .set("spark.sql.adaptive.enabled", "true")
            .set("spark.sql.adaptive.coalescePartitions.enabled", "true")
            .set("spark.serializer", "org.apache.spark.serializer.KryoSerializer");
            
        SparkSession spark = SparkSession.builder().config(conf).getOrCreate();
        JavaSparkContext jsc = JavaSparkContext.fromSparkContext(spark.sparkContext());
        
        try {
            // Load raw traffic data from HDFS
            Dataset<Row> rawTraffic = spark.read()
                .option("header", "true")
                .option("inferSchema", "true")
                .csv("hdfs://namenode:9000/traffic-data/raw/metr-la-*.csv");
            
            // Feature engineering transformations
            Dataset<Row> featuresDF = rawTraffic
                .withColumn("hour_of_day", hour(col("timestamp")))
                .withColumn("day_of_week", dayofweek(col("timestamp")))
                .withColumn("month", month(col("timestamp")))
                .withColumn("is_weekend", when(col("day_of_week").isin(1, 7), 1).otherwise(0))
                .withColumn("is_rush_hour", 
                    when(col("hour_of_day").between(7, 9).or(col("hour_of_day").between(17, 19)), 1)
                    .otherwise(0))
                .withColumn("speed_change_rate", 
                    col("speed").minus(lag("speed", 1).over(
                        Window.partitionBy("sensor_id").orderBy("timestamp"))))
                .withColumn("rolling_avg_speed", 
                    avg("speed").over(
                        Window.partitionBy("sensor_id")
                               .orderBy("timestamp")
                               .rangeBetween(-3600, 0))) // 1-hour rolling average
                .withColumn("volume_density", col("volume").divide(col("lane_count")))
                .na().drop(); // Remove rows with null values
            
            // Save engineered features to HDFS
            featuresDF.coalesce(10) // Reduce number of output files
                .write()
                .mode(SaveMode.Overwrite)
                .option("compression", "snappy")
                .parquet("hdfs://namenode:9000/traffic-data/features/");
                
            System.out.println("Feature engineering completed successfully");
            
        } finally {
            spark.stop();
        }
    }
}
```

**Feature Engineering Analysis:**

**Temporal Features:**
- **hour_of_day**: Captures daily traffic patterns (0-23)
- **day_of_week**: Weekday vs weekend patterns (1-7)
- **is_rush_hour**: Binary feature for peak traffic times
- **is_weekend**: Binary feature for weekend behavior

**Derived Features:**
- **speed_change_rate**: Rate of speed change for trend analysis
- **rolling_avg_speed**: Smoothed speed values to reduce noise
- **volume_density**: Traffic density per lane for capacity analysis

**Window Functions:**
- **Lag Window**: Compare current vs previous values
- **Rolling Window**: 1-hour rolling averages
- **Partition Strategy**: Group by sensor_id for temporal continuity

### **ML Model Training Job**

```java
// src/batch-processing/src/main/java/com/trafficprediction/jobs/MLTrainingJob.java
package com.trafficprediction.jobs;

import org.apache.spark.ml.Pipeline;
import org.apache.spark.ml.PipelineModel;
import org.apache.spark.ml.PipelineStage;
import org.apache.spark.ml.evaluation.RegressionEvaluator;
import org.apache.spark.ml.feature.*;
import org.apache.spark.ml.regression.*;
import org.apache.spark.ml.tuning.*;
import org.apache.spark.sql.*;

public class MLTrainingJob {
    
    public void trainModels(SparkSession spark) {
        // Load feature-engineered data
        Dataset<Row> featuresDF = spark.read()
            .parquet("hdfs://namenode:9000/traffic-data/features/");
        
        // Prepare feature vector
        String[] featureColumns = {
            "hour_of_day", "day_of_week", "is_weekend", "is_rush_hour",
            "rolling_avg_speed", "volume_density", "speed_change_rate"
        };
        
        VectorAssembler assembler = new VectorAssembler()
            .setInputCols(featureColumns)
            .setOutputCol("features");
        
        // Split data for training and testing
        Dataset<Row>[] splits = featuresDF.randomSplit(new double[]{0.8, 0.2}, 42L);
        Dataset<Row> trainData = splits[0];
        Dataset<Row> testData = splits[1];
        
        // Train multiple models and compare performance
        trainLinearRegression(trainData, testData, assembler);
        trainRandomForest(trainData, testData, assembler);
        trainGradientBoosting(trainData, testData, assembler);
    }
    
    private void trainLinearRegression(Dataset<Row> trainData, Dataset<Row> testData, 
                                      VectorAssembler assembler) {
        
        // Feature scaling for linear regression
        StandardScaler scaler = new StandardScaler()
            .setInputCol("features")
            .setOutputCol("scaledFeatures");
        
        LinearRegression lr = new LinearRegression()
            .setFeaturesCol("scaledFeatures")
            .setLabelCol("speed")
            .setPredictionCol("predicted_speed")
            .setMaxIter(100)
            .setRegParam(0.1)
            .setElasticNetParam(0.01);
        
        // Create pipeline
        Pipeline pipeline = new Pipeline()
            .setStages(new PipelineStage[]{assembler, scaler, lr});
        
        // Hyperparameter tuning
        ParamGridBuilder paramGrid = new ParamGridBuilder()
            .addGrid(lr.regParam(), new double[]{0.01, 0.1, 1.0})
            .addGrid(lr.elasticNetParam(), new double[]{0.0, 0.01, 0.1});
        
        RegressionEvaluator evaluator = new RegressionEvaluator()
            .setLabelCol("speed")
            .setPredictionCol("predicted_speed")
            .setMetricName("rmse");
        
        CrossValidator cv = new CrossValidator()
            .setEstimator(pipeline)
            .setEvaluator(evaluator)
            .setEstimatorParamMaps(paramGrid.build())
            .setNumFolds(5);
        
        // Train model
        CrossValidatorModel cvModel = cv.fit(trainData);
        
        // Evaluate on test data
        Dataset<Row> predictions = cvModel.transform(testData);
        double rmse = evaluator.evaluate(predictions);
        
        System.out.println("Linear Regression RMSE: " + rmse);
        
        // Save model
        try {
            cvModel.write().overwrite()
                .save("hdfs://namenode:9000/models/linear_regression/");
        } catch (Exception e) {
            System.err.println("Error saving model: " + e.getMessage());
        }
    }
    
    private void trainRandomForest(Dataset<Row> trainData, Dataset<Row> testData, 
                                  VectorAssembler assembler) {
        
        RandomForestRegressor rf = new RandomForestRegressor()
            .setFeaturesCol("features")
            .setLabelCol("speed")
            .setPredictionCol("predicted_speed")
            .setNumTrees(50)
            .setMaxDepth(10)
            .setSubsamplingRate(0.8);
        
        Pipeline pipeline = new Pipeline()
            .setStages(new PipelineStage[]{assembler, rf});
        
        // Hyperparameter tuning for Random Forest
        ParamGridBuilder paramGrid = new ParamGridBuilder()
            .addGrid(rf.numTrees(), new int[]{30, 50, 100})
            .addGrid(rf.maxDepth(), new int[]{5, 10, 15});
        
        RegressionEvaluator evaluator = new RegressionEvaluator()
            .setLabelCol("speed")
            .setPredictionCol("predicted_speed")
            .setMetricName("rmse");
        
        CrossValidator cv = new CrossValidator()
            .setEstimator(pipeline)
            .setEvaluator(evaluator)
            .setEstimatorParamMaps(paramGrid.build())
            .setNumFolds(3);
        
        CrossValidatorModel cvModel = cv.fit(trainData);
        Dataset<Row> predictions = cvModel.transform(testData);
        double rmse = evaluator.evaluate(predictions);
        
        System.out.println("Random Forest RMSE: " + rmse);
        
        // Save model
        try {
            cvModel.write().overwrite()
                .save("hdfs://namenode:9000/models/random_forest/");
        } catch (Exception e) {
            System.err.println("Error saving Random Forest model: " + e.getMessage());
        }
    }
}
```

**Model Training Analysis:**

**Algorithm Selection:**
- **Linear Regression**: Fast, interpretable baseline model
- **Random Forest**: Handles non-linear patterns, feature importance
- **Gradient Boosting**: High accuracy for complex patterns

**Hyperparameter Tuning:**
- **Cross Validation**: 5-fold CV for reliable performance estimation
- **Grid Search**: Systematic hyperparameter exploration
- **Regularization**: L1/L2 regularization to prevent overfitting

**Model Evaluation:**
- **RMSE**: Root Mean Square Error for regression evaluation
- **Train/Test Split**: 80/20 split for unbiased performance assessment
- **Feature Scaling**: StandardScaler for linear models

## Data Models and Schemas

### **Avro Schema Definitions**

The system uses **Avro schemas** for data serialization and schema evolution:

```json
// schemas/traffic-event.avsc
{
    "type": "record",
    "name": "TrafficEvent",
    "namespace": "com.trafficprediction.events",
    "fields": [
        {"name": "sensor_id", "type": "string", "doc": "Unique sensor identifier"},
        {"name": "timestamp", "type": "string", "doc": "Event timestamp in ISO format"},
        {"name": "speed", "type": ["null", "double"], "default": null, "doc": "Vehicle speed in mph"},
        {"name": "volume", "type": ["null", "int"], "default": null, "doc": "Traffic volume count"},
        {"name": "occupancy", "type": ["null", "double"], "default": null, "doc": "Lane occupancy percentage"},
        {"name": "latitude", "type": ["null", "double"], "default": null, "doc": "GPS latitude"},
        {"name": "longitude", "type": ["null", "double"], "default": null, "doc": "GPS longitude"},
        {"name": "road_type", "type": ["null", "string"], "default": null, "doc": "Type of road"},
        {"name": "lane_count", "type": ["null", "int"], "default": null, "doc": "Number of lanes"},
        {"name": "weather_conditions", "type": ["null", "string"], "default": null, "doc": "Weather description"}
    ]
}
```

**Schema Design Analysis:**
- **Optional Fields**: Union types with null for missing data
- **Documentation**: Field-level documentation for clarity
- **Namespace**: Prevents naming conflicts across systems
- **Default Values**: Graceful handling of missing fields

### **TypeScript Type Generation**

```typescript
// src/lib/models/trafficData.ts (generated from Avro schemas)
export interface TrafficEvent {
    sensor_id: string;
    timestamp: string;
    speed?: number | null;
    volume?: number | null;
    occupancy?: number | null;
    latitude?: number | null;
    longitude?: number | null;
    road_type?: string | null;
    lane_count?: number | null;
    weather_conditions?: string | null;
}

export interface ProcessedTrafficAggregate {
    segment_id: string;
    window_start: string;
    window_end: string;
    sensor_count: number;
    avg_speed: number;
    total_volume: number;
    avg_occupancy: number;
    speed_variance: number;
    volume_variance: number;
    max_speed: number;
    min_speed: number;
    road_types: string[];
    weather_impact_score?: number;
}
```

**Type Safety Benefits:**
- **Compile-time Validation**: Catch type errors before runtime
- **IDE Support**: IntelliSense and auto-completion
- **Refactoring Safety**: Rename and move operations
- **API Contract**: Ensures frontend-backend compatibility

This ML pipeline provides a comprehensive approach to traffic prediction, combining real-time stream processing with batch model training for both immediate responsiveness and long-term accuracy improvements.
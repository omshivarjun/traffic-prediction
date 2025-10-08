#!/usr/bin/env python3
"""
Traffic Prediction Service (Simplified for Spark Master)
Uses existing Spark installation in spark-master container
"""
import os
import sys
import logging
from datetime import datetime
from typing import List, Optional
import math

# Set Spark paths for Bitnami container
os.environ['SPARK_HOME'] = '/opt/bitnami/spark'
os.environ['PYTHONPATH'] = f"{os.environ['SPARK_HOME']}/python:{os.environ['SPARK_HOME']}/python/lib/py4j-0.10.9.7-src.zip"

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Import PySpark after setting environment
from pyspark.sql import SparkSession
from pyspark.ml import PipelineModel
from pyspark.sql import functions as F
from pyspark.sql.functions import col, sin, cos, when, lit, hour as spark_hour, dayofweek, month as spark_month
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, FloatType, TimestampType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Traffic Prediction API",
    description="Real-time traffic speed predictions using trained ML model",
    version="1.0.0"
)

# Global variables
spark: Optional[SparkSession] = None
model: Optional[PipelineModel] = None
feature_columns: Optional[List[str]] = None

# Pydantic models for API
class TrafficInput(BaseModel):
    """Input schema for traffic prediction"""
    timestamp: str = Field(..., description="ISO format timestamp")
    sensor_id: int = Field(..., description="Traffic sensor ID")
    latitude: float = Field(..., description="Sensor latitude")
    longitude: float = Field(..., description="Sensor longitude")
    volume: float = Field(default=0.0, description="Traffic volume (vehicles/hour)")
    occupancy: float = Field(default=0.0, description="Lane occupancy (0-1)")
    num_lanes: int = Field(default=3, description="Number of lanes")
    
    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2023-06-15T14:30:00",
                "sensor_id": 101,
                "latitude": 34.0522,
                "longitude": -118.2437,
                "volume": 1200.0,
                "occupancy": 0.45,
                "num_lanes": 4
            }
        }

class PredictionOutput(BaseModel):
    """Output schema for traffic prediction"""
    predicted_speed: float = Field(..., description="Predicted speed in mph")
    sensor_id: int = Field(..., description="Sensor ID")
    timestamp: str = Field(..., description="Prediction timestamp")
    confidence: str = Field(default="high", description="Prediction confidence")

class BatchTrafficInput(BaseModel):
    """Batch input for multiple predictions"""
    data: List[TrafficInput]

class BatchPredictionOutput(BaseModel):
    """Batch output for multiple predictions"""
    predictions: List[PredictionOutput]
    count: int

def create_spark_session() -> SparkSession:
    """Create Spark session with HDFS access"""
    logger.info("Creating Spark session...")
    
    spark = SparkSession.builder \
        .appName("TrafficPredictionService") \
        .master("local[2]") \
        .config("spark.driver.memory", "2g") \
        .config("spark.executor.memory", "1g") \
        .config("spark.sql.shuffle.partitions", "4") \
        .config("spark.hadoop.fs.defaultFS", "hdfs://namenode:9000") \
        .getOrCreate()
    
    logger.info("✅ Spark session created successfully")
    return spark

def load_model_from_hdfs(spark_session: SparkSession, model_path: str) -> PipelineModel:
    """Load trained model from HDFS"""
    logger.info(f"Loading model from HDFS: {model_path}")
    
    try:
        model = PipelineModel.load(model_path)
        logger.info("✅ Model loaded successfully from HDFS")
        return model
    except Exception as e:
        logger.error(f"❌ Failed to load model: {str(e)}")
        raise

def get_feature_columns() -> List[str]:
    """Get list of feature columns (56 total)"""
    features = []
    
    # Time-based features (6)
    features.extend(['hour_sin', 'hour_cos', 'day_of_week', 'month', 'is_weekend', 'is_rush_hour'])
    
    # Spatial features (9)
    features.extend(['latitude_norm', 'longitude_norm'])
    features.extend(['highway_I_5', 'highway_I_10', 'highway_I_110', 'highway_I_405', 'highway_US_101', 'highway_other'])
    
    # Traffic features (2)
    features.extend(['volume_normalized', 'congestion_index'])
    
    # Original features (11)
    features.extend(['sensor_id', 'volume', 'occupancy', 'num_lanes', 'latitude', 'longitude'])
    features.extend(['hour', 'day_of_month', 'year', 'speed_limit', 'is_holiday'])
    
    # Historical features (27) - zeros for real-time
    historical_features = [
        'speed_lag_1', 'speed_lag_2', 'speed_lag_3',
        'speed_rolling_mean_3', 'speed_rolling_std_3', 'speed_rolling_max_3', 'speed_rolling_min_3',
        'speed_rolling_mean_6', 'speed_rolling_std_6', 'speed_rolling_max_6', 'speed_rolling_min_6',
        'volume_lag_1', 'volume_lag_2', 'volume_lag_3',
        'volume_rolling_mean_3', 'volume_rolling_std_3', 'volume_rolling_max_3', 'volume_rolling_min_3',
        'volume_rolling_mean_6', 'volume_rolling_std_6', 'volume_rolling_max_6', 'volume_rolling_min_6',
        'occupancy_lag_1', 'occupancy_rolling_mean_3', 'occupancy_rolling_std_3',
        'occupancy_rolling_max_3', 'occupancy_rolling_min_3', 'occupancy_rolling_max_6'
    ]
    features.extend(historical_features)
    
    return features

def engineer_features(df):
    """Apply complete feature engineering pipeline"""
    
    # Parse timestamp
    df = df.withColumn('timestamp_parsed', F.to_timestamp(col('timestamp')))
    
    # Extract time components
    df = df.withColumn('hour', spark_hour(col('timestamp_parsed')))
    df = df.withColumn('day_of_week', dayofweek(col('timestamp_parsed')))
    df = df.withColumn('month', spark_month(col('timestamp_parsed')))
    df = df.withColumn('day_of_month', F.dayofmonth(col('timestamp_parsed')))
    df = df.withColumn('year', F.year(col('timestamp_parsed')))
    
    # Time-based features - cyclical encoding
    df = df.withColumn('hour_sin', sin(col('hour') * 2 * math.pi / 24))
    df = df.withColumn('hour_cos', cos(col('hour') * 2 * math.pi / 24))
    
    # Weekend indicator
    df = df.withColumn('is_weekend', when(col('day_of_week').isin([1, 7]), 1).otherwise(0))
    
    # Rush hour indicator (7-9 AM and 4-6 PM)
    df = df.withColumn('is_rush_hour',
        when((col('hour') >= 7) & (col('hour') <= 9), 1)
        .when((col('hour') >= 16) & (col('hour') <= 18), 1)
        .otherwise(0))
    
    # Spatial features - normalized coordinates (LA area: 33.7-34.8 lat, -118.7 to -117.6 lon)
    df = df.withColumn('latitude_norm', (col('latitude') - 33.7) / (34.8 - 33.7))
    df = df.withColumn('longitude_norm', (col('longitude') + 118.7) / (-117.6 + 118.7))
    
    # Highway encoding based on sensor_id ranges (one-hot)
    df = df.withColumn('highway_I_5', when((col('sensor_id') >= 1) & (col('sensor_id') <= 40), 1).otherwise(0))
    df = df.withColumn('highway_I_10', when((col('sensor_id') >= 41) & (col('sensor_id') <= 80), 1).otherwise(0))
    df = df.withColumn('highway_I_110', when((col('sensor_id') >= 81) & (col('sensor_id') <= 120), 1).otherwise(0))
    df = df.withColumn('highway_I_405', when((col('sensor_id') >= 121) & (col('sensor_id') <= 160), 1).otherwise(0))
    df = df.withColumn('highway_US_101', when((col('sensor_id') >= 161) & (col('sensor_id') <= 200), 1).otherwise(0))
    df = df.withColumn('highway_other', when(col('sensor_id') > 200, 1).otherwise(0))
    
    # Traffic features
    df = df.withColumn('volume_normalized', col('volume') / 2000.0)  # Typical max volume
    df = df.withColumn('congestion_index', col('volume') * col('occupancy'))
    
    # Additional original features
    df = df.withColumn('speed_limit', lit(65.0))  # Default speed limit
    df = df.withColumn('is_holiday', lit(0))  # Default non-holiday
    
    # Historical features (all zeros for real-time predictions - no historical data available)
    historical_features = [
        'speed_lag_1', 'speed_lag_2', 'speed_lag_3',
        'speed_rolling_mean_3', 'speed_rolling_std_3', 'speed_rolling_max_3', 'speed_rolling_min_3',
        'speed_rolling_mean_6', 'speed_rolling_std_6', 'speed_rolling_max_6', 'speed_rolling_min_6',
        'volume_lag_1', 'volume_lag_2', 'volume_lag_3',
        'volume_rolling_mean_3', 'volume_rolling_std_3', 'volume_rolling_max_3', 'volume_rolling_min_3',
        'volume_rolling_mean_6', 'volume_rolling_std_6', 'volume_rolling_max_6', 'volume_rolling_min_6',
        'occupancy_lag_1', 'occupancy_rolling_mean_3', 'occupancy_rolling_std_3',
        'occupancy_rolling_max_3', 'occupancy_rolling_min_3', 'occupancy_rolling_max_6'
    ]
    
    for feat in historical_features:
        df = df.withColumn(feat, lit(0.0))
    
    return df

# API Endpoints
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "Traffic Prediction API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "/health": "Health check",
            "/predict": "Single traffic prediction (POST)",
            "/batch-predict": "Batch predictions (POST)"
        },
        "model_loaded": model is not None
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy" if (spark is not None and model is not None) else "initializing",
        "model_loaded": model is not None,
        "spark_active": spark is not None,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/predict", response_model=PredictionOutput)
async def predict(input_data: TrafficInput):
    """Make a single traffic prediction"""
    if model is None or spark is None:
        raise HTTPException(status_code=503, detail="Service not ready - model or Spark not initialized")
    
    try:
        logger.info(f"Prediction request for sensor {input_data.sensor_id}")
        
        # Create DataFrame from input
        schema = StructType([
            StructField("timestamp", StringType(), True),
            StructField("sensor_id", IntegerType(), True),
            StructField("latitude", FloatType(), True),
            StructField("longitude", FloatType(), True),
            StructField("volume", FloatType(), True),
            StructField("occupancy", FloatType(), True),
            StructField("num_lanes", IntegerType(), True)
        ])
        
        data = [(
            input_data.timestamp,
            input_data.sensor_id,
            float(input_data.latitude),
            float(input_data.longitude),
            float(input_data.volume),
            float(input_data.occupancy),
            input_data.num_lanes
        )]
        
        df = spark.createDataFrame(data, schema)
        
        # Engineer features
        df = engineer_features(df)
        
        # Make prediction
        predictions = model.transform(df)
        
        # Extract result
        result = predictions.select('prediction', 'sensor_id', 'timestamp').first()
        predicted_speed = round(float(result['prediction']), 2)
        
        logger.info(f"Prediction successful: {predicted_speed} mph")
        
        return PredictionOutput(
            predicted_speed=predicted_speed,
            sensor_id=input_data.sensor_id,
            timestamp=input_data.timestamp,
            confidence="high" if 20.0 <= predicted_speed <= 80.0 else "medium"
        )
        
    except Exception as e:
        logger.error(f"Prediction failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

@app.post("/batch-predict", response_model=BatchPredictionOutput)
async def batch_predict(input_data: BatchTrafficInput):
    """Make batch traffic predictions"""
    if model is None or spark is None:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    try:
        logger.info(f"Batch prediction request for {len(input_data.data)} inputs")
        
        # Create DataFrame from batch
        schema = StructType([
            StructField("timestamp", StringType(), True),
            StructField("sensor_id", IntegerType(), True),
            StructField("latitude", FloatType(), True),
            StructField("longitude", FloatType(), True),
            StructField("volume", FloatType(), True),
            StructField("occupancy", FloatType(), True),
            StructField("num_lanes", IntegerType(), True)
        ])
        
        data = [(
            item.timestamp,
            item.sensor_id,
            float(item.latitude),
            float(item.longitude),
            float(item.volume),
            float(item.occupancy),
            item.num_lanes
        ) for item in input_data.data]
        
        df = spark.createDataFrame(data, schema)
        
        # Engineer features
        df = engineer_features(df)
        
        # Make predictions
        predictions = model.transform(df)
        
        # Collect results
        results = predictions.select('prediction', 'sensor_id', 'timestamp').collect()
        
        prediction_list = [
            PredictionOutput(
                predicted_speed=round(float(row['prediction']), 2),
                sensor_id=int(row['sensor_id']),
                timestamp=row['timestamp'],
                confidence="high"
            )
            for row in results
        ]
        
        logger.info(f"Batch prediction successful: {len(prediction_list)} predictions")
        
        return BatchPredictionOutput(
            predictions=prediction_list,
            count=len(prediction_list)
        )
        
    except Exception as e:
        logger.error(f"Batch prediction failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Batch prediction failed: {str(e)}")

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize Spark and load model on startup"""
    global spark, model, feature_columns
    
    try:
        logger.info("🚀 Starting Traffic Prediction Service...")
        
        # Create Spark session
        spark = create_spark_session()
        
        # Load model from HDFS
        model_path = "hdfs://namenode:9000/traffic-data/models/gbt-sample-model"
        model = load_model_from_hdfs(spark, model_path)
        
        # Get feature columns
        feature_columns = get_feature_columns()
        
        logger.info(f"✅ Service initialized successfully with {len(feature_columns)} features!")
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {str(e)}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global spark
    
    logger.info("Shutting down service...")
    
    if spark is not None:
        spark.stop()
        logger.info("Spark session stopped")

# Run with uvicorn
if __name__ == "__main__":
    import uvicorn
    
    # Find uvicorn in .local/bin
    uvicorn_path = os.path.expanduser("~/.local/bin/uvicorn")
    
    logger.info("Starting FastAPI server on port 8001...")
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")

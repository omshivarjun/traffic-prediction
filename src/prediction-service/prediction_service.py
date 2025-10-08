#!/usr/bin/env python3
"""
Traffic Prediction Service
Real-time traffic speed prediction using trained GBT model
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import numpy as np
from datetime import datetime
import logging
import sys
import os

# Add PySpark to path
os.environ['SPARK_HOME'] = '/opt/spark'
sys.path.append('/opt/spark/python')
sys.path.append('/opt/spark/python/lib/py4j-0.10.9-src.zip')

from pyspark.sql import SparkSession
from pyspark.ml import PipelineModel
from pyspark.ml.feature import VectorAssembler
from pyspark.sql.types import StructType, StructField, DoubleType, IntegerType, StringType, TimestampType
from pyspark.sql.functions import col, lit, sin, cos, hour, dayofweek, month, when
import math

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="Traffic Prediction API",
    description="Real-time traffic speed predictions using ML",
    version="1.0.0"
)

# Global variables
spark = None
model = None
feature_columns = None

class TrafficInput(BaseModel):
    """Single traffic data point for prediction"""
    timestamp: str = Field(..., description="ISO format timestamp")
    sensor_id: int = Field(..., description="Traffic sensor ID")
    latitude: float = Field(..., description="Sensor latitude")
    longitude: float = Field(..., description="Sensor longitude")
    volume: float = Field(default=0.0, description="Traffic volume (vehicles/hour)")
    occupancy: float = Field(default=0.0, description="Lane occupancy (0-1)")
    num_lanes: int = Field(default=3, description="Number of lanes")
    
    class Config:
        schema_extra = {
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

class BatchTrafficInput(BaseModel):
    """Batch of traffic data points"""
    data: List[TrafficInput]

class PredictionOutput(BaseModel):
    """Prediction result"""
    predicted_speed: float
    sensor_id: int
    timestamp: str
    confidence: Optional[str] = "high"

class BatchPredictionOutput(BaseModel):
    """Batch prediction results"""
    predictions: List[PredictionOutput]
    count: int

def create_spark_session():
    """Create Spark session with HDFS configuration"""
    logger.info("Creating Spark session...")
    
    return SparkSession.builder \
        .appName("Traffic_Prediction_Service") \
        .master("local[2]") \
        .config("spark.driver.memory", "2g") \
        .config("spark.executor.memory", "1g") \
        .config("spark.hadoop.fs.defaultFS", "hdfs://namenode:9000") \
        .config("spark.sql.shuffle.partitions", "4") \
        .getOrCreate()

def load_model_from_hdfs(spark, model_path):
    """Load trained model from HDFS"""
    logger.info(f"Loading model from HDFS: {model_path}")
    
    try:
        # Load the GBT model
        model = PipelineModel.load(model_path)
        logger.info("✅ Model loaded successfully!")
        return model
    except Exception as e:
        logger.error(f"❌ Failed to load model: {e}")
        raise

def get_feature_columns():
    """Define feature columns used during training"""
    return [
        # Original features
        'volume', 'occupancy', 'num_lanes',
        'latitude', 'longitude',
        
        # Time features
        'hour_sin', 'hour_cos', 'day_of_week', 'month',
        'is_weekend', 'is_rush_hour',
        
        # Spatial features
        'latitude_norm', 'longitude_norm',
        'highway_I_5', 'highway_I_10', 'highway_I_110',
        'highway_I_405', 'highway_US_101', 'highway_other',
        
        # Traffic features
        'volume_normalized', 'congestion_index',
        
        # Historical features (using zeros for real-time prediction)
        'speed_lag_1', 'speed_lag_2', 'speed_lag_3',
        'volume_lag_1', 'volume_lag_2', 'volume_lag_3',
        'occupancy_lag_1', 'occupancy_lag_2', 'occupancy_lag_3',
        
        'speed_rolling_mean_3', 'speed_rolling_std_3',
        'speed_rolling_min_3', 'speed_rolling_max_3',
        'volume_rolling_mean_3', 'volume_rolling_std_3',
        'volume_rolling_min_3', 'volume_rolling_max_3',
        'occupancy_rolling_mean_3', 'occupancy_rolling_std_3',
        'occupancy_rolling_min_3', 'occupancy_rolling_max_3',
        
        'speed_rolling_mean_6', 'speed_rolling_std_6',
        'speed_rolling_min_6', 'speed_rolling_max_6',
        'volume_rolling_mean_6', 'volume_rolling_std_6',
        'volume_rolling_min_6', 'volume_rolling_max_6',
        'occupancy_rolling_mean_6', 'occupancy_rolling_std_6',
        'occupancy_rolling_min_6', 'occupancy_rolling_max_6'
    ]

def engineer_features(df):
    """Apply feature engineering to input data"""
    
    # Time-based features
    df = df.withColumn('hour', hour(col('timestamp')))
    df = df.withColumn('hour_sin', sin(col('hour') * 2 * math.pi / 24))
    df = df.withColumn('hour_cos', cos(col('hour') * 2 * math.pi / 24))
    df = df.withColumn('day_of_week', dayofweek(col('timestamp')))
    df = df.withColumn('month', month(col('timestamp')))
    df = df.withColumn('is_weekend', when(col('day_of_week').isin([1, 7]), 1).otherwise(0))
    df = df.withColumn('is_rush_hour', 
        when((col('hour') >= 7) & (col('hour') <= 9), 1)
        .when((col('hour') >= 16) & (col('hour') <= 18), 1)
        .otherwise(0))
    
    # Spatial features (normalized)
    lat_min, lat_max = 33.7, 34.8
    lon_min, lon_max = -118.7, -117.6
    
    df = df.withColumn('latitude_norm', 
        (col('latitude') - lat_min) / (lat_max - lat_min))
    df = df.withColumn('longitude_norm',
        (col('longitude') - lon_min) / (lon_max - lon_min))
    
    # Highway encoding (simplified - based on sensor_id ranges)
    df = df.withColumn('highway_I_5', when((col('sensor_id') >= 1) & (col('sensor_id') <= 40), 1).otherwise(0))
    df = df.withColumn('highway_I_10', when((col('sensor_id') >= 41) & (col('sensor_id') <= 80), 1).otherwise(0))
    df = df.withColumn('highway_I_110', when((col('sensor_id') >= 81) & (col('sensor_id') <= 120), 1).otherwise(0))
    df = df.withColumn('highway_I_405', when((col('sensor_id') >= 121) & (col('sensor_id') <= 160), 1).otherwise(0))
    df = df.withColumn('highway_US_101', when((col('sensor_id') >= 161) & (col('sensor_id') <= 200), 1).otherwise(0))
    df = df.withColumn('highway_other', when(col('sensor_id') > 200, 1).otherwise(0))
    
    # Traffic features
    df = df.withColumn('volume_normalized', col('volume') / 2000.0)
    df = df.withColumn('congestion_index', 
        when(col('occupancy') > 0, col('volume') * col('occupancy'))
        .otherwise(0))
    
    # Historical features (use zeros for real-time - no historical data available)
    historical_features = [
        'speed_lag_1', 'speed_lag_2', 'speed_lag_3',
        'volume_lag_1', 'volume_lag_2', 'volume_lag_3',
        'occupancy_lag_1', 'occupancy_lag_2', 'occupancy_lag_3',
        'speed_rolling_mean_3', 'speed_rolling_std_3',
        'speed_rolling_min_3', 'speed_rolling_max_3',
        'volume_rolling_mean_3', 'volume_rolling_std_3',
        'volume_rolling_min_3', 'volume_rolling_max_3',
        'occupancy_rolling_mean_3', 'occupancy_rolling_std_3',
        'occupancy_rolling_min_3', 'occupancy_rolling_max_3',
        'speed_rolling_mean_6', 'speed_rolling_std_6',
        'speed_rolling_min_6', 'speed_rolling_max_6',
        'volume_rolling_mean_6', 'volume_rolling_std_6',
        'volume_rolling_min_6', 'volume_rolling_max_6',
        'occupancy_rolling_mean_6', 'occupancy_rolling_std_6',
        'occupancy_rolling_min_6', 'occupancy_rolling_max_6'
    ]
    
    for feat in historical_features:
        df = df.withColumn(feat, lit(0.0))
    
    return df

@app.on_event("startup")
async def startup_event():
    """Initialize service on startup"""
    global spark, model, feature_columns
    
    logger.info("🚀 Starting Traffic Prediction Service...")
    
    try:
        # Create Spark session
        spark = create_spark_session()
        
        # Load model from HDFS
        model_path = "hdfs://namenode:9000/traffic-data/models/gbt-sample-model"
        model = load_model_from_hdfs(spark, model_path)
        
        # Get feature columns
        feature_columns = get_feature_columns()
        
        logger.info("✅ Service initialized successfully!")
        logger.info(f"📊 Using {len(feature_columns)} features")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize service: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
    global spark
    
    logger.info("🛑 Shutting down Traffic Prediction Service...")
    
    if spark:
        spark.stop()
        logger.info("✅ Spark session stopped")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Traffic Prediction API",
        "status": "running",
        "model": "GBT (R² = 0.9975)",
        "endpoints": {
            "predict": "/predict",
            "batch_predict": "/batch-predict",
            "health": "/health"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "spark_active": spark is not None,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/predict", response_model=PredictionOutput)
async def predict(input_data: TrafficInput):
    """
    Predict traffic speed for a single data point
    """
    global spark, model, feature_columns
    
    if not model or not spark:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        # Create DataFrame from input
        schema = StructType([
            StructField("timestamp", StringType(), True),
            StructField("sensor_id", IntegerType(), True),
            StructField("latitude", DoubleType(), True),
            StructField("longitude", DoubleType(), True),
            StructField("volume", DoubleType(), True),
            StructField("occupancy", DoubleType(), True),
            StructField("num_lanes", IntegerType(), True)
        ])
        
        data = [(
            input_data.timestamp,
            input_data.sensor_id,
            input_data.latitude,
            input_data.longitude,
            input_data.volume,
            input_data.occupancy,
            input_data.num_lanes
        )]
        
        df = spark.createDataFrame(data, schema)
        df = df.withColumn('timestamp', col('timestamp').cast(TimestampType()))
        
        # Engineer features
        df = engineer_features(df)
        
        # Make prediction
        predictions = model.transform(df)
        
        # Extract prediction
        result = predictions.select('prediction', 'sensor_id', 'timestamp').first()
        predicted_speed = float(result['prediction'])
        
        return PredictionOutput(
            predicted_speed=round(predicted_speed, 2),
            sensor_id=input_data.sensor_id,
            timestamp=input_data.timestamp,
            confidence="high" if predicted_speed > 0 else "low"
        )
        
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

@app.post("/batch-predict", response_model=BatchPredictionOutput)
async def batch_predict(input_data: BatchTrafficInput):
    """
    Predict traffic speed for multiple data points
    """
    global spark, model, feature_columns
    
    if not model or not spark:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        # Create DataFrame from batch input
        schema = StructType([
            StructField("timestamp", StringType(), True),
            StructField("sensor_id", IntegerType(), True),
            StructField("latitude", DoubleType(), True),
            StructField("longitude", DoubleType(), True),
            StructField("volume", DoubleType(), True),
            StructField("occupancy", DoubleType(), True),
            StructField("num_lanes", IntegerType(), True)
        ])
        
        data = [
            (
                item.timestamp,
                item.sensor_id,
                item.latitude,
                item.longitude,
                item.volume,
                item.occupancy,
                item.num_lanes
            )
            for item in input_data.data
        ]
        
        df = spark.createDataFrame(data, schema)
        df = df.withColumn('timestamp', col('timestamp').cast(TimestampType()))
        
        # Engineer features
        df = engineer_features(df)
        
        # Make predictions
        predictions = model.transform(df)
        
        # Extract predictions
        results = predictions.select('prediction', 'sensor_id', 'timestamp').collect()
        
        prediction_list = [
            PredictionOutput(
                predicted_speed=round(float(row['prediction']), 2),
                sensor_id=int(row['sensor_id']),
                timestamp=str(row['timestamp']),
                confidence="high" if row['prediction'] > 0 else "low"
            )
            for row in results
        ]
        
        return BatchPredictionOutput(
            predictions=prediction_list,
            count=len(prediction_list)
        )
        
    except Exception as e:
        logger.error(f"Batch prediction error: {e}")
        raise HTTPException(status_code=500, detail=f"Batch prediction failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

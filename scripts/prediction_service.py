"""
Traffic Prediction Service
Loads trained models and generates real-time predictions
Stores predictions in HDFS and pushes to Kafka predictions topic
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

# Kafka
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError

# Spark
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *
from pyspark.ml import PipelineModel

# ML
import pandas as pd
import numpy as np
import joblib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_spark_session():
    """Create Spark session for predictions"""
    spark = SparkSession.builder \
        .appName("TrafficPredictionService") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.driver.memory", "2g") \
        .config("spark.executor.memory", "2g") \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    return spark

class TrafficPredictionService:
    """Service for generating and serving traffic predictions"""
    
    def __init__(self, kafka_config: Dict, hdfs_config: Dict, model_config: Dict):
        self.kafka_config = kafka_config
        self.hdfs_config = hdfs_config
        self.model_config = model_config
        self.spark = create_spark_session()
        
        # Initialize Kafka producer for predictions
        self.producer = KafkaProducer(
            bootstrap_servers=kafka_config['bootstrap_servers'],
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None,
            acks='all',
            retries=3
        )
        
        # Load models
        self.spark_models = {}
        self.sklearn_models = {}
        self.load_models()
        
    def load_models(self):
        """Load all trained models"""
        logger.info("Loading trained models...")
        
        try:
            # Load Spark models
            for model_name in self.model_config['spark_models']:
                model_path = f"{self.hdfs_config['models_path']}/spark/{model_name}"
                try:
                    model = PipelineModel.load(model_path)
                    self.spark_models[model_name] = model
                    logger.info(f"Loaded Spark model: {model_name}")
                except Exception as e:
                    logger.warning(f"Could not load Spark model {model_name}: {e}")
            
            # Load sklearn models
            local_models_dir = Path("models/sklearn")
            if local_models_dir.exists():
                for model_name in self.model_config['sklearn_models']:
                    model_file = local_models_dir / f"{model_name}.pkl"
                    if model_file.exists():
                        model_dict = joblib.load(model_file)
                        self.sklearn_models[model_name] = model_dict
                        logger.info(f"Loaded sklearn model: {model_name}")
                    else:
                        logger.warning(f"sklearn model file not found: {model_file}")
            
            logger.info(f"Loaded {len(self.spark_models)} Spark models and {len(self.sklearn_models)} sklearn models")
            
        except Exception as e:
            logger.error(f"Error loading models: {e}")
            raise
    
    def get_recent_data(self, hours_back: int = 1) -> Any:
        """Get recent traffic data for prediction"""
        logger.info(f"Loading recent data ({hours_back} hours back)...")
        
        try:
            # Calculate time window
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours_back)
            
            # Load sensor aggregates from HDFS
            sensor_df = self.spark.read.parquet(
                self.hdfs_config['sensor_aggregates_path']
            ).filter(
                col("window_start") >= lit(start_time.strftime("%Y-%m-%d %H:%M:%S"))
            )
            
            # Load road aggregates
            road_df = self.spark.read.parquet(
                self.hdfs_config['road_aggregates_path']
            ).filter(
                col("window_start") >= lit(start_time.strftime("%Y-%m-%d %H:%M:%S"))
            )
            
            logger.info(f"Loaded {sensor_df.count()} recent sensor records")
            return sensor_df, road_df
            
        except Exception as e:
            logger.error(f"Error loading recent data: {e}")
            return None, None
    
    def prepare_prediction_features(self, sensor_df, road_df):
        """Prepare features for prediction"""
        logger.info("Preparing prediction features...")
        
        # Create same features as training
        sensor_features = sensor_df.withColumn(
            "hour_of_day", hour(col("window_start"))
        ).withColumn(
            "day_of_week", dayofweek(col("window_start"))
        ).withColumn(
            "is_weekend", when(dayofweek(col("window_start")).isin([1, 7]), 1).otherwise(0)
        ).withColumn(
            "is_rush_hour", 
            when((hour(col("window_start")).between(7, 9)) | 
                 (hour(col("window_start")).between(17, 19)), 1).otherwise(0)
        ).withColumn(
            "speed_variance", col("max_speed_mph") - col("min_speed_mph")
        ).withColumn(
            "volume_per_reading", col("total_volume_vph") / col("reading_count")
        ).withColumn(
            "congestion_level",
            when(col("avg_speed_mph") < 20, "high")
            .when(col("avg_speed_mph") < 40, "medium")
            .otherwise("low")
        ).filter(
            col("avg_speed_mph").isNotNull() & 
            col("avg_volume_vph").isNotNull()
        )
        
        # Join with road features
        road_features = road_df.select(
            col("window_start"),
            col("road_name"),
            col("avg_speed_mph").alias("road_avg_speed"),
            col("avg_volume_vph").alias("road_avg_volume"),
            col("sensor_count")
        )
        
        prediction_df = sensor_features.join(
            road_features,
            on=["window_start", "road_name"],
            how="left"
        )
        
        return prediction_df
    
    def generate_spark_predictions(self, prediction_df):
        """Generate predictions using Spark models"""
        logger.info("Generating Spark predictions...")
        
        predictions = {}
        
        for model_name, model in self.spark_models.items():
            try:
                # Make predictions
                pred_df = model.transform(prediction_df)
                
                # Extract predictions and format
                if 'congestion' in model_name:
                    pred_results = pred_df.select(
                        col("sensor_id"),
                        col("window_start"),
                        col("road_name"),
                        col("latitude"),
                        col("longitude"),
                        col("prediction").alias("predicted_congestion_class"),
                        col("avg_speed_mph").alias("actual_speed")
                    ).collect()
                else:
                    pred_results = pred_df.select(
                        col("sensor_id"),
                        col("window_start"),
                        col("road_name"),
                        col("latitude"),
                        col("longitude"),
                        col("prediction").alias("predicted_speed"),
                        col("avg_speed_mph").alias("actual_speed")
                    ).collect()
                
                predictions[model_name] = pred_results
                logger.info(f"Generated {len(pred_results)} predictions with {model_name}")
                
            except Exception as e:
                logger.error(f"Error generating predictions with {model_name}: {e}")
        
        return predictions
    
    def generate_sklearn_predictions(self, prediction_df):
        """Generate predictions using sklearn models"""
        logger.info("Generating sklearn predictions...")
        
        predictions = {}
        
        if not self.sklearn_models:
            logger.warning("No sklearn models loaded")
            return predictions
        
        try:
            # Convert to Pandas
            pandas_df = prediction_df.toPandas()
            
            for model_name, model_dict in self.sklearn_models.items():
                try:
                    model = model_dict['model']
                    scaler = model_dict['scaler']
                    feature_cols = model_dict['feature_columns']
                    
                    # Prepare features (same as training)
                    df_encoded = pd.get_dummies(
                        pandas_df, 
                        columns=['road_type', 'direction'],
                        prefix=['road_type', 'direction']
                    )
                    
                    # Ensure all training features are present
                    for col in feature_cols:
                        if col not in df_encoded.columns:
                            df_encoded[col] = 0
                    
                    X = df_encoded[feature_cols].fillna(0)
                    X_scaled = scaler.transform(X)
                    
                    # Generate predictions
                    y_pred = model.predict(X_scaled)
                    
                    # Create prediction results
                    pred_results = []
                    for i, pred in enumerate(y_pred):
                        pred_results.append({
                            'sensor_id': pandas_df.iloc[i]['sensor_id'],
                            'window_start': pandas_df.iloc[i]['window_start'].isoformat(),
                            'road_name': pandas_df.iloc[i]['road_name'],
                            'latitude': pandas_df.iloc[i]['latitude'],
                            'longitude': pandas_df.iloc[i]['longitude'],
                            'predicted_speed': float(pred),
                            'actual_speed': float(pandas_df.iloc[i]['avg_speed_mph']),
                            'model_name': model_name
                        })
                    
                    predictions[model_name] = pred_results
                    logger.info(f"Generated {len(pred_results)} predictions with {model_name}")
                    
                except Exception as e:
                    logger.error(f"Error generating predictions with {model_name}: {e}")
        
        except Exception as e:
            logger.error(f"Error in sklearn prediction pipeline: {e}")
        
        return predictions
    
    def publish_predictions_to_kafka(self, all_predictions: Dict):
        """Publish predictions to Kafka predictions topic"""
        logger.info("Publishing predictions to Kafka...")
        
        predictions_sent = 0
        
        for model_name, predictions in all_predictions.items():
            for pred in predictions:
                try:
                    # Create prediction message
                    message = {
                        'sensor_id': pred.get('sensor_id'),
                        'timestamp': pred.get('window_start') if isinstance(pred.get('window_start'), str) 
                                   else pred.get('window_start').isoformat() if pred.get('window_start') else None,
                        'road_name': pred.get('road_name'),
                        'latitude': float(pred.get('latitude', 0)),
                        'longitude': float(pred.get('longitude', 0)),
                        'predicted_speed': float(pred.get('predicted_speed', 0)),
                        'predicted_congestion_class': pred.get('predicted_congestion_class'),
                        'actual_speed': float(pred.get('actual_speed', 0)),
                        'model_name': model_name,
                        'prediction_timestamp': datetime.now().isoformat(),
                        'confidence_score': 0.85  # Placeholder
                    }
                    
                    # Send to Kafka
                    self.producer.send(
                        self.kafka_config['predictions_topic'],
                        key=message['sensor_id'],
                        value=message
                    )
                    predictions_sent += 1
                    
                except Exception as e:
                    logger.error(f"Error sending prediction to Kafka: {e}")
        
        # Flush producer
        self.producer.flush()
        logger.info(f"Published {predictions_sent} predictions to Kafka")
    
    def save_predictions_to_hdfs(self, all_predictions: Dict):
        """Save predictions to HDFS"""
        logger.info("Saving predictions to HDFS...")
        
        try:
            # Flatten all predictions
            all_pred_records = []
            for model_name, predictions in all_predictions.items():
                for pred in predictions:
                    record = {
                        'sensor_id': pred.get('sensor_id'),
                        'timestamp': pred.get('window_start') if isinstance(pred.get('window_start'), str) 
                                   else pred.get('window_start').isoformat() if pred.get('window_start') else None,
                        'road_name': pred.get('road_name'),
                        'latitude': float(pred.get('latitude', 0)),
                        'longitude': float(pred.get('longitude', 0)),
                        'predicted_speed': float(pred.get('predicted_speed', 0)),
                        'predicted_congestion_class': pred.get('predicted_congestion_class'),
                        'actual_speed': float(pred.get('actual_speed', 0)),
                        'model_name': model_name,
                        'prediction_timestamp': datetime.now().isoformat(),
                        'prediction_date': datetime.now().strftime('%Y-%m-%d'),
                        'prediction_hour': datetime.now().hour
                    }
                    all_pred_records.append(record)
            
            if all_pred_records:
                # Convert to Spark DataFrame
                pred_df = self.spark.createDataFrame(all_pred_records)
                
                # Write to HDFS with partitioning
                pred_df.write \
                    .mode("append") \
                    .partitionBy("prediction_date", "model_name") \
                    .parquet(self.hdfs_config['predictions_path'])
                
                logger.info(f"Saved {len(all_pred_records)} predictions to HDFS")
        
        except Exception as e:
            logger.error(f"Error saving predictions to HDFS: {e}")
    
    def run_prediction_cycle(self, hours_back: int = 1):
        """Run one complete prediction cycle"""
        logger.info("Starting prediction cycle...")
        
        try:
            # Get recent data
            sensor_df, road_df = self.get_recent_data(hours_back)
            
            if sensor_df is None or road_df is None:
                logger.warning("No recent data available for predictions")
                return
            
            # Prepare features
            prediction_df = self.prepare_prediction_features(sensor_df, road_df)
            
            if prediction_df.count() == 0:
                logger.warning("No valid data for predictions")
                return
            
            # Generate predictions
            spark_predictions = self.generate_spark_predictions(prediction_df)
            sklearn_predictions = self.generate_sklearn_predictions(prediction_df)
            
            # Combine all predictions
            all_predictions = {**spark_predictions, **sklearn_predictions}
            
            if not all_predictions:
                logger.warning("No predictions generated")
                return
            
            # Publish to Kafka
            self.publish_predictions_to_kafka(all_predictions)
            
            # Save to HDFS
            self.save_predictions_to_hdfs(all_predictions)
            
            logger.info("Prediction cycle completed successfully")
            
        except Exception as e:
            logger.error(f"Error in prediction cycle: {e}")
    
    def run_continuous_predictions(self, interval_minutes: int = 5):
        """Run continuous prediction service"""
        logger.info(f"Starting continuous prediction service (interval: {interval_minutes} minutes)")
        
        try:
            while True:
                start_time = time.time()
                
                # Run prediction cycle
                self.run_prediction_cycle()
                
                # Calculate sleep time
                elapsed = time.time() - start_time
                sleep_time = max(0, (interval_minutes * 60) - elapsed)
                
                logger.info(f"Prediction cycle completed in {elapsed:.1f}s. "
                          f"Sleeping for {sleep_time:.1f}s...")
                
                time.sleep(sleep_time)
                
        except KeyboardInterrupt:
            logger.info("Shutting down prediction service...")
        except Exception as e:
            logger.error(f"Error in continuous prediction service: {e}")
        finally:
            self.producer.close()
            self.spark.stop()

def main():
    """Main function"""
    
    # Configuration
    kafka_config = {
        'bootstrap_servers': 'localhost:9093',
        'predictions_topic': 'traffic-predictions'
    }
    
    hdfs_config = {
        'sensor_aggregates_path': 'hdfs://localhost:9000/traffic-data/streaming/sensor-aggregates',
        'road_aggregates_path': 'hdfs://localhost:9000/traffic-data/streaming/road-aggregates',
        'models_path': 'hdfs://localhost:9000/traffic-data/models',
        'predictions_path': 'hdfs://localhost:9000/traffic-data/predictions'
    }
    
    model_config = {
        'spark_models': ['spark_rf_speed', 'spark_gbt_speed', 'spark_rf_congestion'],
        'sklearn_models': ['sklearn_rf', 'sklearn_gbt', 'sklearn_lr']
    }
    
    # Create and run prediction service
    service = TrafficPredictionService(kafka_config, hdfs_config, model_config)
    
    # Run single prediction cycle or continuous
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--continuous', action='store_true', help='Run continuous prediction service')
    parser.add_argument('--interval', type=int, default=5, help='Prediction interval in minutes')
    args = parser.parse_args()
    
    if args.continuous:
        service.run_continuous_predictions(args.interval)
    else:
        service.run_prediction_cycle()

if __name__ == "__main__":
    main()
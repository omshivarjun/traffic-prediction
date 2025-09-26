"""
Spark MLlib Traffic Prediction Model Training
Reads processed data from HDFS and trains ML models for traffic prediction
Supports both Spark MLlib and TensorFlow/scikit-learn models
"""

import os
import sys
import json
import pickle
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Any

# Spark imports
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *
from pyspark.ml.feature import VectorAssembler, StandardScaler, StringIndexer
from pyspark.ml.regression import RandomForestRegressor, GBTRegressor, LinearRegression
from pyspark.ml.classification import RandomForestClassifier, GBTClassifier
from pyspark.ml.evaluation import RegressionEvaluator, MulticlassClassificationEvaluator
from pyspark.ml import Pipeline
from pyspark.ml.tuning import CrossValidator, ParamGridBuilder

# ML imports
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor as SKRandomForest
from sklearn.ensemble import GradientBoostingRegressor as SKGradientBoosting
from sklearn.linear_model import LinearRegression as SKLinearRegression
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.preprocessing import StandardScaler as SKStandardScaler
import joblib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_spark_session():
    """Create Spark session for ML training"""
    spark = SparkSession.builder \
        .appName("TrafficMLTraining") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
        .config("spark.driver.memory", "4g") \
        .config("spark.executor.memory", "4g") \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    return spark

class TrafficMLTrainer:
    """ML trainer for traffic prediction models"""
    
    def __init__(self, spark_session: SparkSession, hdfs_config: Dict):
        self.spark = spark_session
        self.hdfs_config = hdfs_config
        self.models = {}
        self.evaluations = {}
        
    def load_training_data(self) -> Tuple[Any, Any]:
        """Load and prepare training data from HDFS"""
        logger.info("Loading training data from HDFS...")
        
        try:
            # Load sensor aggregates (main training data)
            sensor_df = self.spark.read.parquet(
                self.hdfs_config['sensor_aggregates_path']
            )
            
            # Load road aggregates for additional features
            road_df = self.spark.read.parquet(
                self.hdfs_config['road_aggregates_path']
            )
            
            logger.info(f"Loaded {sensor_df.count()} sensor records")
            logger.info(f"Loaded {road_df.count()} road records")
            
            return sensor_df, road_df
            
        except Exception as e:
            logger.error(f"Error loading training data: {e}")
            raise
    
    def create_features(self, sensor_df, road_df):
        """Create ML features from raw data"""
        logger.info("Creating ML features...")
        
        # Feature engineering for sensor data
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
        
        # Create road-level features
        road_features = road_df.select(
            col("window_start"),
            col("road_name"),
            col("avg_speed_mph").alias("road_avg_speed"),
            col("avg_volume_vph").alias("road_avg_volume"),
            col("sensor_count")
        )
        
        # Join sensor and road features
        joined_features = sensor_features.join(
            road_features,
            on=["window_start", "road_name"],
            how="left"
        )
        
        logger.info(f"Created features for {joined_features.count()} records")
        return joined_features
    
    def train_spark_models(self, training_df):
        """Train models using Spark MLlib"""
        logger.info("Training Spark MLlib models...")
        
        # Prepare features for Spark ML
        feature_cols = [
            "avg_volume_vph", "max_volume_vph", "total_volume_vph",
            "reading_count", "hour_of_day", "day_of_week", 
            "is_weekend", "is_rush_hour", "speed_variance",
            "volume_per_reading", "latitude", "longitude",
            "road_avg_volume", "sensor_count"
        ]
        
        # Remove nulls
        clean_df = training_df.filter(
            reduce(lambda x, y: x & y, [col(c).isNotNull() for c in feature_cols])
        )
        
        # String indexer for categorical features
        road_type_indexer = StringIndexer(
            inputCol="road_type", 
            outputCol="road_type_indexed"
        )
        
        direction_indexer = StringIndexer(
            inputCol="direction", 
            outputCol="direction_indexed"
        )
        
        congestion_indexer = StringIndexer(
            inputCol="congestion_level",
            outputCol="congestion_indexed"
        )
        
        # Vector assembler
        feature_cols_indexed = feature_cols + ["road_type_indexed", "direction_indexed"]
        assembler = VectorAssembler(
            inputCols=feature_cols_indexed,
            outputCol="features"
        )
        
        # Scaler
        scaler = StandardScaler(
            inputCol="features",
            outputCol="scaled_features"
        )
        
        # Split data
        train_df, test_df = clean_df.randomSplit([0.8, 0.2], seed=42)
        
        models_to_train = {
            'spark_rf_speed': RandomForestRegressor(
                featuresCol="scaled_features",
                labelCol="avg_speed_mph",
                numTrees=100,
                maxDepth=10
            ),
            'spark_gbt_speed': GBTRegressor(
                featuresCol="scaled_features",
                labelCol="avg_speed_mph",
                maxIter=100,
                maxDepth=8
            ),
            'spark_rf_congestion': RandomForestClassifier(
                featuresCol="scaled_features",
                labelCol="congestion_indexed",
                numTrees=100,
                maxDepth=10
            )
        }
        
        spark_models = {}
        
        for model_name, model in models_to_train.items():
            logger.info(f"Training {model_name}...")
            
            # Create pipeline
            if 'congestion' in model_name:
                pipeline = Pipeline(stages=[
                    road_type_indexer, direction_indexer, congestion_indexer,
                    assembler, scaler, model
                ])
            else:
                pipeline = Pipeline(stages=[
                    road_type_indexer, direction_indexer,
                    assembler, scaler, model
                ])
            
            # Train model
            fitted_pipeline = pipeline.fit(train_df)
            
            # Make predictions
            predictions = fitted_pipeline.transform(test_df)
            
            # Evaluate
            if 'congestion' in model_name:
                evaluator = MulticlassClassificationEvaluator(
                    labelCol="congestion_indexed",
                    predictionCol="prediction",
                    metricName="accuracy"
                )
                accuracy = evaluator.evaluate(predictions)
                self.evaluations[model_name] = {"accuracy": accuracy}
                logger.info(f"{model_name} accuracy: {accuracy:.4f}")
            else:
                evaluator = RegressionEvaluator(
                    labelCol="avg_speed_mph",
                    predictionCol="prediction",
                    metricName="rmse"
                )
                rmse = evaluator.evaluate(predictions)
                
                r2_evaluator = RegressionEvaluator(
                    labelCol="avg_speed_mph",
                    predictionCol="prediction",
                    metricName="r2"
                )
                r2 = r2_evaluator.evaluate(predictions)
                
                self.evaluations[model_name] = {"rmse": rmse, "r2": r2}
                logger.info(f"{model_name} - RMSE: {rmse:.4f}, R²: {r2:.4f}")
            
            spark_models[model_name] = fitted_pipeline
        
        return spark_models
    
    def train_sklearn_models(self, training_df):
        """Train models using scikit-learn (converted to Pandas)"""
        logger.info("Training scikit-learn models...")
        
        # Convert to Pandas (sample if too large)
        pandas_df = training_df.sample(fraction=0.1, seed=42).toPandas()
        logger.info(f"Using {len(pandas_df)} samples for sklearn training")
        
        # Prepare features
        feature_cols = [
            "avg_volume_vph", "max_volume_vph", "total_volume_vph",
            "reading_count", "hour_of_day", "day_of_week", 
            "is_weekend", "is_rush_hour", "speed_variance",
            "volume_per_reading", "latitude", "longitude",
            "road_avg_volume", "sensor_count"
        ]
        
        # Handle categorical features
        pandas_df = pd.get_dummies(
            pandas_df, 
            columns=['road_type', 'direction'],
            prefix=['road_type', 'direction']
        )
        
        # Get final feature columns
        feature_cols_final = [col for col in pandas_df.columns 
                             if col.startswith(tuple(feature_cols + ['road_type_', 'direction_']))]
        
        X = pandas_df[feature_cols_final].fillna(0)
        y_speed = pandas_df['avg_speed_mph'].fillna(pandas_df['avg_speed_mph'].mean())
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y_speed, test_size=0.2, random_state=42
        )
        
        # Scale features
        scaler = SKStandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Train models
        sklearn_models = {
            'sklearn_rf': SKRandomForest(n_estimators=100, max_depth=10, random_state=42),
            'sklearn_gbt': SKGradientBoosting(n_estimators=100, max_depth=8, random_state=42),
            'sklearn_lr': SKLinearRegression()
        }
        
        trained_sklearn_models = {}
        
        for name, model in sklearn_models.items():
            logger.info(f"Training {name}...")
            
            # Fit model
            model.fit(X_train_scaled, y_train)
            
            # Predict
            y_pred = model.predict(X_test_scaled)
            
            # Evaluate
            rmse = np.sqrt(mean_squared_error(y_test, y_pred))
            mae = mean_absolute_error(y_test, y_pred)
            r2 = r2_score(y_test, y_pred)
            
            self.evaluations[name] = {
                "rmse": rmse,
                "mae": mae,
                "r2": r2
            }
            
            logger.info(f"{name} - RMSE: {rmse:.4f}, MAE: {mae:.4f}, R²: {r2:.4f}")
            
            trained_sklearn_models[name] = {
                'model': model,
                'scaler': scaler,
                'feature_columns': feature_cols_final
            }
        
        return trained_sklearn_models
    
    def save_models(self, spark_models, sklearn_models):
        """Save all trained models"""
        logger.info("Saving models...")
        
        # Create model metadata
        metadata = {
            'training_timestamp': datetime.now().isoformat(),
            'spark_models': list(spark_models.keys()),
            'sklearn_models': list(sklearn_models.keys()),
            'evaluations': self.evaluations,
            'data_sources': ['sensor_aggregates', 'road_aggregates']
        }
        
        # Save Spark models to HDFS
        for name, model in spark_models.items():
            model_path = f"{self.hdfs_config['models_path']}/spark/{name}"
            model.write().overwrite().save(model_path)
            logger.info(f"Saved Spark model {name} to {model_path}")
        
        # Save sklearn models locally (then copy to HDFS)
        local_models_dir = Path("models/sklearn")
        local_models_dir.mkdir(parents=True, exist_ok=True)
        
        for name, model_dict in sklearn_models.items():
            model_file = local_models_dir / f"{name}.pkl"
            joblib.dump(model_dict, model_file)
            logger.info(f"Saved sklearn model {name} to {model_file}")
        
        # Save metadata
        metadata_file = local_models_dir / "metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info("All models saved successfully")
        return metadata
    
    def train_all_models(self):
        """Train all models end-to-end"""
        logger.info("Starting comprehensive ML training pipeline...")
        
        try:
            # Load data
            sensor_df, road_df = self.load_training_data()
            
            # Create features
            training_df = self.create_features(sensor_df, road_df)
            
            # Train Spark models
            spark_models = self.train_spark_models(training_df)
            
            # Train sklearn models
            sklearn_models = self.train_sklearn_models(training_df)
            
            # Save all models
            metadata = self.save_models(spark_models, sklearn_models)
            
            logger.info("ML training pipeline completed successfully!")
            return metadata
            
        except Exception as e:
            logger.error(f"Error in ML training pipeline: {e}")
            raise

def main():
    """Main function"""
    
    # Configuration
    hdfs_config = {
        'sensor_aggregates_path': 'hdfs://localhost:9000/traffic-data/streaming/sensor-aggregates',
        'road_aggregates_path': 'hdfs://localhost:9000/traffic-data/streaming/road-aggregates',
        'models_path': 'hdfs://localhost:9000/traffic-data/models'
    }
    
    # Create Spark session
    spark = create_spark_session()
    
    try:
        # Create trainer and run
        trainer = TrafficMLTrainer(spark, hdfs_config)
        metadata = trainer.train_all_models()
        
        print("\n" + "="*50)
        print("MODEL TRAINING COMPLETED")
        print("="*50)
        print(f"Training completed at: {metadata['training_timestamp']}")
        print(f"Spark models trained: {len(metadata['spark_models'])}")
        print(f"Sklearn models trained: {len(metadata['sklearn_models'])}")
        print("\nModel Performance:")
        for model_name, metrics in metadata['evaluations'].items():
            print(f"  {model_name}: {metrics}")
        
    finally:
        spark.stop()

if __name__ == "__main__":
    main()
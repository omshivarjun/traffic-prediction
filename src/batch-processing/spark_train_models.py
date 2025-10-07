#!/usr/bin/env python3
"""
Traffic Prediction ML Model Training with PySpark MLlib
Trains multiple regression models WITHOUT Hive
"""

import sys
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.ml.feature import VectorAssembler, StandardScaler
from pyspark.ml.regression import (
    LinearRegression,
    RandomForestRegressor,
    GBTRegressor
)
from pyspark.ml.evaluation import RegressionEvaluator
from pyspark.ml import Pipeline

def create_spark_session():
    """Create Spark session configured for ML"""
    return SparkSession.builder \
        .appName("TrafficMLTraining") \
        .config("spark.sql.warehouse.dir", "hdfs://namenode:9000/warehouse") \
        .config("spark.executor.memory", "2g") \
        .config("spark.driver.memory", "1g") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
        .config("spark.kryoserializer.buffer.max", "512m") \
        .getOrCreate()

def load_features(spark, features_path):
    """Load engineered features from HDFS"""
    print(f"📂 Loading features from: {features_path}")
    df = spark.read.parquet(features_path)
    print(f"✅ Loaded {df.count():,} feature records")
    print(f"📊 Schema:")
    df.printSchema()
    return df

def prepare_training_data(df):
    """Prepare features and labels for ML"""
    print("\n🔧 Preparing training data...")
    
    # Select feature columns (numeric only)
    feature_cols = [
        "hour", "day_of_week", "day_of_month", "month",
        "is_weekend", "is_rush_hour",
        "speed_rolling_avg", "speed_rolling_std",
        "speed_rolling_min", "speed_rolling_max",
        "segment_avg_speed", "segment_std_speed"
    ]
    
    # Add volume features if available
    if "volume_rolling_avg" in df.columns:
        feature_cols.extend([
            "volume", "volume_rolling_avg", "volume_rolling_std",
            "segment_avg_volume", "segment_std_volume"
        ])
    
    # Filter available columns
    available_features = [col for col in feature_cols if col in df.columns]
    print(f"📊 Using {len(available_features)} features: {available_features}")
    
    # Drop nulls in critical columns
    df = df.dropna(subset=["speed"] + available_features)
    
    # Assemble features into vector
    assembler = VectorAssembler(
        inputCols=available_features,
        outputCol="raw_features",
        handleInvalid="skip"
    )
    
    # Scale features
    scaler = StandardScaler(
        inputCol="raw_features",
        outputCol="features",
        withStd=True,
        withMean=True
    )
    
    # Create pipeline for preprocessing
    preprocessing_pipeline = Pipeline(stages=[assembler, scaler])
    
    # Fit and transform
    print("🔄 Applying feature preprocessing...")
    preprocessing_model = preprocessing_pipeline.fit(df)
    df_processed = preprocessing_model.transform(df)
    
    # Select final columns
    df_final = df_processed.select("features", "speed", "segment_id")
    
    print(f"✅ Preprocessed {df_final.count():,} records")
    return df_final, preprocessing_model, available_features

def split_data(df, train_ratio=0.7, val_ratio=0.15, test_ratio=0.15):
    """Split data into train, validation, and test sets"""
    print(f"\n📊 Splitting data: {train_ratio:.0%} train, {val_ratio:.0%} val, {test_ratio:.0%} test")
    
    # Split data
    train_df, val_df, test_df = df.randomSplit([train_ratio, val_ratio, test_ratio], seed=42)
    
    print(f"✅ Train set: {train_df.count():,} records")
    print(f"✅ Validation set: {val_df.count():,} records")
    print(f"✅ Test set: {test_df.count():,} records")
    
    return train_df, val_df, test_df

def train_linear_regression(train_df, val_df):
    """Train Linear Regression model"""
    print("\n" + "="*60)
    print("📈 Training Linear Regression Model")
    print("="*60)
    
    lr = LinearRegression(
        featuresCol="features",
        labelCol="speed",
        maxIter=100,
        regParam=0.01,
        elasticNetParam=0.5
    )
    
    print("🔄 Fitting model...")
    lr_model = lr.fit(train_df)
    
    # Evaluate on validation set
    val_predictions = lr_model.transform(val_df)
    
    evaluator_rmse = RegressionEvaluator(
        labelCol="speed",
        predictionCol="prediction",
        metricName="rmse"
    )
    evaluator_mae = RegressionEvaluator(
        labelCol="speed",
        predictionCol="prediction",
        metricName="mae"
    )
    evaluator_r2 = RegressionEvaluator(
        labelCol="speed",
        predictionCol="prediction",
        metricName="r2"
    )
    
    rmse = evaluator_rmse.evaluate(val_predictions)
    mae = evaluator_mae.evaluate(val_predictions)
    r2 = evaluator_r2.evaluate(val_predictions)
    
    print(f"\n📊 Linear Regression Performance:")
    print(f"   RMSE: {rmse:.4f} mph")
    print(f"   MAE:  {mae:.4f} mph")
    print(f"   R²:   {r2:.4f}")
    
    return lr_model, {"rmse": rmse, "mae": mae, "r2": r2}

def train_random_forest(train_df, val_df):
    """Train Random Forest Regressor"""
    print("\n" + "="*60)
    print("🌳 Training Random Forest Model")
    print("="*60)
    
    rf = RandomForestRegressor(
        featuresCol="features",
        labelCol="speed",
        numTrees=100,
        maxDepth=10,
        minInstancesPerNode=5,
        seed=42
    )
    
    print("🔄 Fitting model (this may take a few minutes)...")
    rf_model = rf.fit(train_df)
    
    # Evaluate
    val_predictions = rf_model.transform(val_df)
    
    evaluator_rmse = RegressionEvaluator(labelCol="speed", predictionCol="prediction", metricName="rmse")
    evaluator_mae = RegressionEvaluator(labelCol="speed", predictionCol="prediction", metricName="mae")
    evaluator_r2 = RegressionEvaluator(labelCol="speed", predictionCol="prediction", metricName="r2")
    
    rmse = evaluator_rmse.evaluate(val_predictions)
    mae = evaluator_mae.evaluate(val_predictions)
    r2 = evaluator_r2.evaluate(val_predictions)
    
    print(f"\n📊 Random Forest Performance:")
    print(f"   RMSE: {rmse:.4f} mph")
    print(f"   MAE:  {mae:.4f} mph")
    print(f"   R²:   {r2:.4f}")
    print(f"   Feature Importances: {rf_model.featureImportances}")
    
    return rf_model, {"rmse": rmse, "mae": mae, "r2": r2}

def train_gradient_boosting(train_df, val_df):
    """Train Gradient Boosted Trees"""
    print("\n" + "="*60)
    print("⚡ Training Gradient Boosting Model")
    print("="*60)
    
    gbt = GBTRegressor(
        featuresCol="features",
        labelCol="speed",
        maxIter=100,
        maxDepth=5,
        stepSize=0.1,
        seed=42
    )
    
    print("🔄 Fitting model (this may take several minutes)...")
    gbt_model = gbt.fit(train_df)
    
    # Evaluate
    val_predictions = gbt_model.transform(val_df)
    
    evaluator_rmse = RegressionEvaluator(labelCol="speed", predictionCol="prediction", metricName="rmse")
    evaluator_mae = RegressionEvaluator(labelCol="speed", predictionCol="prediction", metricName="mae")
    evaluator_r2 = RegressionEvaluator(labelCol="speed", predictionCol="prediction", metricName="r2")
    
    rmse = evaluator_rmse.evaluate(val_predictions)
    mae = evaluator_mae.evaluate(val_predictions)
    r2 = evaluator_r2.evaluate(val_predictions)
    
    print(f"\n📊 Gradient Boosting Performance:")
    print(f"   RMSE: {rmse:.4f} mph")
    print(f"   MAE:  {mae:.4f} mph")
    print(f"   R²:   {r2:.4f}")
    print(f"   Feature Importances: {gbt_model.featureImportances}")
    
    return gbt_model, {"rmse": rmse, "mae": mae, "r2": r2}

def select_best_model(models_metrics):
    """Select best model based on RMSE"""
    print("\n" + "="*60)
    print("🏆 Model Selection")
    print("="*60)
    
    best_model_name = None
    best_rmse = float('inf')
    
    for model_name, metrics in models_metrics.items():
        print(f"\n{model_name}:")
        print(f"  RMSE: {metrics['rmse']:.4f}")
        print(f"  MAE:  {metrics['mae']:.4f}")
        print(f"  R²:   {metrics['r2']:.4f}")
        
        if metrics['rmse'] < best_rmse:
            best_rmse = metrics['rmse']
            best_model_name = model_name
    
    print(f"\n🏆 Best Model: {best_model_name} (RMSE: {best_rmse:.4f})")
    return best_model_name

def test_final_model(model, test_df, model_name):
    """Test final model on test set"""
    print("\n" + "="*60)
    print(f"🧪 Final Test Evaluation: {model_name}")
    print("="*60)
    
    test_predictions = model.transform(test_df)
    
    evaluator_rmse = RegressionEvaluator(labelCol="speed", predictionCol="prediction", metricName="rmse")
    evaluator_mae = RegressionEvaluator(labelCol="speed", predictionCol="prediction", metricName="mae")
    evaluator_r2 = RegressionEvaluator(labelCol="speed", predictionCol="prediction", metricName="r2")
    
    rmse = evaluator_rmse.evaluate(test_predictions)
    mae = evaluator_mae.evaluate(test_predictions)
    r2 = evaluator_r2.evaluate(test_predictions)
    
    print(f"\n📊 Test Set Performance:")
    print(f"   RMSE: {rmse:.4f} mph")
    print(f"   MAE:  {mae:.4f} mph")
    print(f"   R²:   {r2:.4f}")
    
    # Show sample predictions
    print("\n📋 Sample Predictions:")
    test_predictions.select("speed", "prediction", "segment_id").show(10)
    
    return {"rmse": rmse, "mae": mae, "r2": r2}

def save_models(models, preprocessing_model, output_path):
    """Save all trained models to HDFS"""
    print("\n" + "="*60)
    print("💾 Saving Models to HDFS")
    print("="*60)
    
    # Save preprocessing pipeline
    preprocessing_path = f"{output_path}/preprocessing"
    print(f"💾 Saving preprocessing pipeline to: {preprocessing_path}")
    preprocessing_model.write().overwrite().save(preprocessing_path)
    
    # Save individual models
    for model_name, model in models.items():
        model_path = f"{output_path}/{model_name}"
        print(f"💾 Saving {model_name} to: {model_path}")
        model.write().overwrite().save(model_path)
    
    print("\n✅ All models saved successfully!")

def main(features_path, output_path):
    """Main ML training pipeline"""
    print("="*60)
    print("🚀 Traffic Prediction ML Training (Spark MLlib - No Hive)")
    print("="*60)
    
    # Create Spark session
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")
    
    try:
        # Load features
        df = load_features(spark, features_path)
        
        # Prepare training data
        df_prepared, preprocessing_model, feature_names = prepare_training_data(df)
        
        # Split data
        train_df, val_df, test_df = split_data(df_prepared)
        
        # Cache datasets for performance
        train_df.cache()
        val_df.cache()
        test_df.cache()
        
        # Train models
        models = {}
        models_metrics = {}
        
        # Linear Regression
        lr_model, lr_metrics = train_linear_regression(train_df, val_df)
        models["linear_regression"] = lr_model
        models_metrics["Linear Regression"] = lr_metrics
        
        # Random Forest
        rf_model, rf_metrics = train_random_forest(train_df, val_df)
        models["random_forest"] = rf_model
        models_metrics["Random Forest"] = rf_metrics
        
        # Gradient Boosting
        gbt_model, gbt_metrics = train_gradient_boosting(train_df, val_df)
        models["gradient_boosting"] = gbt_model
        models_metrics["Gradient Boosting"] = gbt_metrics
        
        # Select best model
        best_model_name = select_best_model(models_metrics)
        
        # Test best model
        best_model_key = best_model_name.lower().replace(" ", "_")
        test_metrics = test_final_model(models[best_model_key], test_df, best_model_name)
        
        # Save all models
        save_models(models, preprocessing_model, output_path)
        
        print("\n" + "="*60)
        print("✅ ML TRAINING COMPLETE!")
        print("="*60)
        print(f"\n🏆 Best Model: {best_model_name}")
        print(f"📊 Test RMSE: {test_metrics['rmse']:.4f} mph")
        print(f"📊 Test MAE: {test_metrics['mae']:.4f} mph")
        print(f"📊 Test R²: {test_metrics['r2']:.4f}")
        print(f"\n💾 Models saved to: {output_path}")
        print(f"📊 Features used: {len(feature_names)}")
        
    except Exception as e:
        print(f"\n❌ Error in ML training: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        spark.stop()

if __name__ == "__main__":
    # Default paths
    features_path = "hdfs://namenode:9000/traffic-data/features/ml_features"
    output_path = "hdfs://namenode:9000/traffic-data/models"
    
    # Allow command line arguments
    if len(sys.argv) > 1:
        features_path = sys.argv[1]
    if len(sys.argv) > 2:
        output_path = sys.argv[2]
    
    print(f"📍 Features path: {features_path}")
    print(f"📍 Output path: {output_path}")
    
    main(features_path, output_path)

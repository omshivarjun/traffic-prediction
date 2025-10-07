#!/usr/bin/env python3
"""
ML Model Training Script for Traffic Prediction
Trains 4 models: Random Forest, GBT, Linear Regression, Decision Tree
Uses PySpark MLlib on HDFS data (no Hive needed!)
"""

from pyspark.sql import SparkSession
from pyspark.ml.feature import VectorAssembler
from pyspark.ml.regression import (
    RandomForestRegressor,
    GBTRegressor,
    LinearRegression,
    DecisionTreeRegressor
)
from pyspark.ml.evaluation import RegressionEvaluator
from pyspark.ml import Pipeline
import sys
from datetime import datetime

def create_spark_session():
    """Create Spark session for ML training"""
    return SparkSession.builder \
        .appName("Traffic ML Model Training") \
        .config("spark.sql.warehouse.dir", "hdfs://namenode:9000/warehouse") \
        .config("spark.driver.memory", "2g") \
        .config("spark.executor.memory", "2g") \
        .getOrCreate()

def load_features(spark, hdfs_path):
    """Load engineered features from HDFS"""
    print(f"\n📂 Loading features from: {hdfs_path}")
    df = spark.read.parquet(hdfs_path)
    
    print(f"✅ Loaded {df.count()} feature records")
    print("\n📊 Feature schema:")
    df.printSchema()
    
    return df

def prepare_data(df, feature_cols, label_col):
    """Prepare features for ML training"""
    print(f"\n🔧 Preparing features: {feature_cols}")
    print(f"🎯 Target label: {label_col}")
    
    # Remove nulls
    df_clean = df.dropna(subset=feature_cols + [label_col])
    
    # Create feature vector
    assembler = VectorAssembler(
        inputCols=feature_cols,
        outputCol="features",
        handleInvalid="skip"
    )
    
    df_vectorized = assembler.transform(df_clean)
    
    # Split train/test (80/20)
    train_df, test_df = df_vectorized.randomSplit([0.8, 0.2], seed=42)
    
    print(f"📦 Training set: {train_df.count()} records")
    print(f"📦 Test set: {test_df.count()} records")
    
    return assembler, train_df, test_df

def train_random_forest(train_df, test_df, label_col):
    """Train Random Forest model"""
    print("\n🌲 Training Random Forest Regressor...")
    
    rf = RandomForestRegressor(
        featuresCol="features",
        labelCol=label_col,
        predictionCol="prediction",
        numTrees=20,  # Reduced from 100
        maxDepth=5,    # Reduced from 10
        seed=42
    )
    
    model = rf.fit(train_df)
    predictions = model.transform(test_df)
    
    return model, predictions

def train_gbt(train_df, test_df, label_col):
    """Train Gradient Boosted Trees model"""
    print("\n🚀 Training Gradient Boosted Trees...")
    
    gbt = GBTRegressor(
        featuresCol="features",
        labelCol=label_col,
        predictionCol="prediction",
        maxIter=20,    # Reduced from 100
        maxDepth=3,     # Reduced from 5
        seed=42
    )
    
    model = gbt.fit(train_df)
    predictions = model.transform(test_df)
    
    return model, predictions

def train_linear_regression(train_df, test_df, label_col):
    """Train Linear Regression model"""
    print("\n📈 Training Linear Regression...")
    
    lr = LinearRegression(
        featuresCol="features",
        labelCol=label_col,
        predictionCol="prediction",
        maxIter=50,      # Reduced from 100
        regParam=0.1,
        elasticNetParam=0.5
    )
    
    model = lr.fit(train_df)
    predictions = model.transform(test_df)
    
    return model, predictions

def train_decision_tree(train_df, test_df, label_col):
    """Train Decision Tree model"""
    print("\n🌳 Training Decision Tree...")
    
    dt = DecisionTreeRegressor(
        featuresCol="features",
        labelCol=label_col,
        predictionCol="prediction",
        maxDepth=5,   # Reduced from 10
        seed=42
    )
    
    model = dt.fit(train_df)
    predictions = model.transform(test_df)
    
    return model, predictions

def evaluate_model(predictions, label_col, model_name):
    """Evaluate model performance"""
    evaluator_rmse = RegressionEvaluator(
        labelCol=label_col,
        predictionCol="prediction",
        metricName="rmse"
    )
    
    evaluator_r2 = RegressionEvaluator(
        labelCol=label_col,
        predictionCol="prediction",
        metricName="r2"
    )
    
    evaluator_mae = RegressionEvaluator(
        labelCol=label_col,
        predictionCol="prediction",
        metricName="mae"
    )
    
    rmse = evaluator_rmse.evaluate(predictions)
    r2 = evaluator_r2.evaluate(predictions)
    mae = evaluator_mae.evaluate(predictions)
    
    print(f"\n📊 {model_name} Metrics:")
    print(f"   RMSE: {rmse:.4f}")
    print(f"   R²:   {r2:.4f}")
    print(f"   MAE:  {mae:.4f}")
    
    return {"rmse": rmse, "r2": r2, "mae": mae}

def save_model(model, assembler, hdfs_path, model_name):
    """Save model to HDFS"""
    model_path = f"{hdfs_path}/{model_name}"
    assembler_path = f"{hdfs_path}/{model_name}_assembler"
    
    print(f"\n💾 Saving {model_name} to HDFS: {model_path}")
    
    # Save model
    model.write().overwrite().save(model_path)
    
    # Save assembler
    assembler.write().overwrite().save(assembler_path)
    
    print(f"✅ Model saved successfully!")
    
    return model_path

def train_all_models(spark, feature_type="speed"):
    """Train all 4 models for speed or volume prediction"""
    
    print(f"\n{'='*60}")
    print(f"🎯 Training Models for {feature_type.upper()} Prediction")
    print(f"{'='*60}")
    
    # Load features from actual HDFS location
    hdfs_input = "hdfs://namenode:9000/traffic-data/features/ml_features"
    df = load_features(spark, hdfs_input)
    
    # Define features and label based on actual schema
    feature_cols = [
        "hour", "day_of_week", "day_of_month", "month",
        "is_weekend", "is_rush_hour",
        "speed_rolling_avg", "speed_rolling_std",
        "speed_rolling_min", "speed_rolling_max",
        "speed_change", "speed_normalized",
        "segment_avg_speed", "segment_std_speed",
        "volume_rolling_avg", "volume_rolling_std",
        "segment_avg_volume", "segment_std_volume"
    ]
    
    # Label column
    if feature_type == "speed":
        label_col = "speed"
    else:
        label_col = "volume"
    
    # Prepare data
    assembler, train_df, test_df = prepare_data(df, feature_cols, label_col)
    
    # Train all models
    models_results = {}
    
    # 1. Random Forest
    rf_model, rf_predictions = train_random_forest(train_df, test_df, label_col)
    rf_metrics = evaluate_model(rf_predictions, label_col, "Random Forest")
    rf_path = save_model(
        rf_model, 
        assembler, 
        "hdfs://namenode:9000/ml/models",
        f"{feature_type}_random_forest"
    )
    models_results["random_forest"] = {"model": rf_model, "metrics": rf_metrics, "path": rf_path}
    
    # 2. Gradient Boosted Trees
    gbt_model, gbt_predictions = train_gbt(train_df, test_df, label_col)
    gbt_metrics = evaluate_model(gbt_predictions, label_col, "Gradient Boosted Trees")
    gbt_path = save_model(
        gbt_model,
        assembler,
        "hdfs://namenode:9000/ml/models",
        f"{feature_type}_gbt"
    )
    models_results["gbt"] = {"model": gbt_model, "metrics": gbt_metrics, "path": gbt_path}
    
    # 3. Linear Regression
    lr_model, lr_predictions = train_linear_regression(train_df, test_df, label_col)
    lr_metrics = evaluate_model(lr_predictions, label_col, "Linear Regression")
    lr_path = save_model(
        lr_model,
        assembler,
        "hdfs://namenode:9000/ml/models",
        f"{feature_type}_linear_regression"
    )
    models_results["linear_regression"] = {"model": lr_model, "metrics": lr_metrics, "path": lr_path}
    
    # 4. Decision Tree
    dt_model, dt_predictions = train_decision_tree(train_df, test_df, label_col)
    dt_metrics = evaluate_model(dt_predictions, label_col, "Decision Tree")
    dt_path = save_model(
        dt_model,
        assembler,
        "hdfs://namenode:9000/ml/models",
        f"{feature_type}_decision_tree"
    )
    models_results["decision_tree"] = {"model": dt_model, "metrics": dt_metrics, "path": dt_path}
    
    # Find best model
    best_model_name = min(models_results.items(), key=lambda x: x[1]["metrics"]["rmse"])[0]
    best_rmse = models_results[best_model_name]["metrics"]["rmse"]
    
    print(f"\n🏆 Best Model: {best_model_name.upper()} (RMSE: {best_rmse:.4f})")
    
    return models_results

def main():
    """Main training pipeline"""
    start_time = datetime.now()
    print(f"\n🚀 Starting ML Training Pipeline - {start_time}")
    
    # Create Spark session
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")
    
    try:
        # Train speed prediction models
        print("\n" + "="*60)
        print("TRAINING SPEED PREDICTION MODELS")
        print("="*60)
        speed_results = train_all_models(spark, "speed")
        
        # Train volume prediction models
        print("\n" + "="*60)
        print("TRAINING VOLUME PREDICTION MODELS")
        print("="*60)
        volume_results = train_all_models(spark, "volume")
        
        # Summary
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print("\n" + "="*60)
        print("✅ ML TRAINING PIPELINE COMPLETE!")
        print("="*60)
        print(f"\n⏱️  Total Duration: {duration:.2f} seconds")
        print(f"\n📦 Trained Models:")
        print(f"   - 4 Speed prediction models")
        print(f"   - 4 Volume prediction models")
        print(f"   - Total: 8 models saved to HDFS")
        
        print(f"\n💾 Model Location: hdfs://namenode:9000/ml/models/")
        print(f"\n🎯 Best Speed Model: {min(speed_results.items(), key=lambda x: x[1]['metrics']['rmse'])[0]}")
        print(f"🎯 Best Volume Model: {min(volume_results.items(), key=lambda x: x[1]['metrics']['rmse'])[0]}")
        
        print("\n🚀 Ready for real-time predictions!")
        
    except Exception as e:
        print(f"\n❌ Error during training: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        spark.stop()

if __name__ == "__main__":
    main()

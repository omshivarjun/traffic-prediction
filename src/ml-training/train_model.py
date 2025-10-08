"""
ML Training Pipeline for Traffic Prediction
Trains Gradient Boosted Trees on 21.7M records with 56 features
Target: Achieve R² = 0.9996
"""

import sys
import json
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.ml import Pipeline
from pyspark.ml.feature import VectorAssembler, StandardScaler
from pyspark.ml.regression import GBTRegressor, RandomForestRegressor
from pyspark.ml.evaluation import RegressionEvaluator


def create_spark_session():
    """Initialize Spark with optimized configuration for ML"""
    return SparkSession.builder \
        .appName("Traffic_ML_Training") \
        .config("spark.sql.shuffle.partitions", "20") \
        .config("spark.default.parallelism", "20") \
        .config("spark.driver.maxResultSize", "2g") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .getOrCreate()


def load_features(spark, input_path):
    """Load engineered features from HDFS"""
    print(f"\n📖 Loading features from: {input_path}")
    df = spark.read.parquet(input_path)
    
    count = df.count()
    print(f"  ✅ Loaded {count:,} records")
    print(f"  ✅ Schema: {len(df.columns)} columns")
    
    # Show schema
    print("\n📋 Available features:")
    for i, col in enumerate(df.columns, 1):
        print(f"  {i:2d}. {col}")
    
    return df


def prepare_features(df):
    """Prepare feature vectors for ML training"""
    print("\n🔧 Preparing feature vectors...")
    
    # Target variable
    target_col = "speed"
    
    # Features to exclude from training
    exclude_cols = [
        target_col,
        "timestamp",
        "sensor_id",
        "highway",
        "road_type",
        "direction"
    ]
    
    # Select numeric feature columns
    feature_cols = [col for col in df.columns if col not in exclude_cols]
    
    print(f"  • Target: {target_col}")
    print(f"  • Features: {len(feature_cols)} columns")
    
    # Create feature vector
    assembler = VectorAssembler(
        inputCols=feature_cols,
        outputCol="features_raw",
        handleInvalid="skip"
    )
    
    # Scale features
    scaler = StandardScaler(
        inputCol="features_raw",
        outputCol="features",
        withStd=True,
        withMean=False
    )
    
    return assembler, scaler, feature_cols


def split_data(df, train_ratio=0.8):
    """Split data into train/test sets"""
    print(f"\n📊 Splitting data (train={train_ratio:.0%}, test={1-train_ratio:.0%})...")
    
    train_df, test_df = df.randomSplit([train_ratio, 1 - train_ratio], seed=42)
    
    train_count = train_df.count()
    test_count = test_df.count()
    
    print(f"  ✅ Training: {train_count:,} records")
    print(f"  ✅ Test: {test_count:,} records")
    
    return train_df, test_df


def train_gbt_model(train_df, assembler, scaler):
    """Train Gradient Boosted Trees model"""
    print("\n🎯 Training Gradient Boosted Trees...")
    print("  • Max depth: 8")
    print("  • Max iterations: 50")
    print("  • Learning rate: 0.1")
    
    gbt = GBTRegressor(
        featuresCol="features",
        labelCol="speed",
        predictionCol="prediction",
        maxDepth=8,
        maxIter=50,
        stepSize=0.1,
        seed=42
    )
    
    pipeline = Pipeline(stages=[assembler, scaler, gbt])
    
    print("\n⏳ Training started...")
    start_time = datetime.now()
    
    model = pipeline.fit(train_df)
    
    duration = (datetime.now() - start_time).total_seconds()
    print(f"  ✅ Completed in {duration:.1f}s ({duration/60:.1f}min)")
    
    return model


def evaluate_model(model, test_df):
    """Evaluate model performance"""
    print(f"\n📊 Evaluating model...")
    
    predictions = model.transform(test_df)
    
    evaluators = {
        "R²": RegressionEvaluator(labelCol="speed", predictionCol="prediction", metricName="r2"),
        "RMSE": RegressionEvaluator(labelCol="speed", predictionCol="prediction", metricName="rmse"),
        "MAE": RegressionEvaluator(labelCol="speed", predictionCol="prediction", metricName="mae")
    }
    
    metrics = {}
    for metric_name, evaluator in evaluators.items():
        value = evaluator.evaluate(predictions)
        metrics[metric_name] = value
        
        if metric_name == "R²":
            status = "✅" if value >= 0.995 else "⚠️" if value >= 0.99 else "❌"
            print(f"  • {metric_name}: {value:.6f} {status}")
        else:
            print(f"  • {metric_name}: {value:.4f}")
    
    print("\n📋 Sample predictions:")
    predictions.select("speed", "prediction").show(10, truncate=False)
    
    return metrics, predictions


def save_model(model, output_path, metrics, feature_cols):
    """Save trained model and metadata"""
    print(f"\n💾 Saving model to: {output_path}")
    
    model.write().overwrite().save(output_path)
    print(f"  ✅ Model saved")
    
    metadata = {
        "training_date": datetime.now().isoformat(),
        "metrics": metrics,
        "num_features": len(feature_cols),
        "feature_names": feature_cols,
        "target_variable": "speed",
        "model_type": "GradientBoostedTrees"
    }
    
    metadata_path = output_path.replace("/models/", "/models-metadata/")
    metadata_json = json.dumps(metadata, indent=2)
    
    import subprocess
    subprocess.run([
        "bash", "-c",
        f"echo '{metadata_json}' | hadoop fs -put -f - {metadata_path}/metadata.json"
    ])
    
    print(f"  ✅ Metadata saved")
    
    return metadata


def main():
    """Main training pipeline"""
    print("\n" + "="*70)
    print(" 🚀 ML TRAINING PIPELINE - TRAFFIC PREDICTION")
    print("="*70)
    
    if len(sys.argv) < 3:
        print("\n❌ Usage: train_model.py <input_path> <output_path>")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    
    spark = create_spark_session()
    
    df = load_features(spark, input_path)
    assembler, scaler, feature_cols = prepare_features(df)
    train_df, test_df = split_data(df)
    
    model = train_gbt_model(train_df, assembler, scaler)
    metrics, _ = evaluate_model(model, test_df)
    
    if metrics["R²"] >= 0.9996:
        print("\n🎉 TARGET ACHIEVED! R² >= 0.9996")
    elif metrics["R²"] >= 0.995:
        print("\n✅ EXCELLENT! R² >= 0.995")
    
    save_model(model, output_path, metrics, feature_cols)
    
    print("\n" + "="*70)
    print(" ✅ ML TRAINING COMPLETED SUCCESSFULLY")
    print("="*70)
    
    spark.stop()


if __name__ == "__main__":
    main()

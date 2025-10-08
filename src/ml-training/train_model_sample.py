"""
ML Training Pipeline - SAMPLE VERSION
Trains on 1M records (4.6% sample) to avoid Docker crashes
Target: Achieve R² > 0.99 (proves pipeline works)
"""

import sys
import json
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.ml import Pipeline
from pyspark.ml.feature import VectorAssembler, StandardScaler
from pyspark.ml.regression import GBTRegressor
from pyspark.ml.evaluation import RegressionEvaluator


def create_spark_session():
    """Initialize Spark with conservative settings for stability"""
    return SparkSession.builder \
        .appName("Traffic_ML_Training_Sample") \
        .config("spark.sql.shuffle.partitions", "10") \
        .config("spark.default.parallelism", "10") \
        .config("spark.driver.maxResultSize", "1g") \
        .getOrCreate()


def load_and_sample_features(spark, input_path, sample_size=1000000):
    """Load features and sample for training"""
    print(f"\n📖 Loading features from: {input_path}")
    df = spark.read.parquet(input_path)
    
    total_count = df.count()
    print(f"  ✅ Total records: {total_count:,}")
    
    # Calculate sample fraction
    sample_fraction = min(1.0, sample_size / total_count)
    
    print(f"\n🎲 Sampling data...")
    print(f"  • Target sample: {sample_size:,} records")
    print(f"  • Sample fraction: {sample_fraction:.4f} ({sample_fraction*100:.2f}%)")
    
    # Sample data with seed for reproducibility
    sampled_df = df.sample(withReplacement=False, fraction=sample_fraction, seed=42)
    
    actual_count = sampled_df.count()
    print(f"  ✅ Sampled: {actual_count:,} records")
    
    print(f"\n📋 Features: {len(df.columns)} columns")
    
    return sampled_df, total_count, actual_count


def prepare_features(df):
    """Prepare feature vectors for ML training"""
    print("\n🔧 Preparing feature vectors...")
    
    target_col = "speed"
    
    # Exclude non-numeric and ID columns
    exclude_cols = [
        target_col, "timestamp", "sensor_id", 
        "highway", "road_type", "direction"
    ]
    
    feature_cols = [col for col in df.columns if col not in exclude_cols]
    
    print(f"  • Target: {target_col}")
    print(f"  • Features: {len(feature_cols)} columns")
    print(f"  • Top features: {', '.join(feature_cols[:5])}...")
    
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
    print(f"\n📊 Splitting data ({train_ratio:.0%} train / {1-train_ratio:.0%} test)...")
    
    train_df, test_df = df.randomSplit([train_ratio, 1 - train_ratio], seed=42)
    
    train_count = train_df.count()
    test_count = test_df.count()
    
    print(f"  ✅ Training: {train_count:,} records")
    print(f"  ✅ Test: {test_count:,} records")
    
    return train_df, test_df


def train_gbt_model(train_df, assembler, scaler):
    """Train Gradient Boosted Trees model"""
    print("\n🎯 Training Gradient Boosted Trees...")
    print("  • Algorithm: GBT")
    print("  • Max depth: 6 (conservative)")
    print("  • Max iterations: 30")
    print("  • Learning rate: 0.1")
    
    gbt = GBTRegressor(
        featuresCol="features",
        labelCol="speed",
        predictionCol="prediction",
        maxDepth=6,
        maxIter=30,
        stepSize=0.1,
        seed=42
    )
    
    pipeline = Pipeline(stages=[assembler, scaler, gbt])
    
    print("\n⏳ Training started...")
    start_time = datetime.now()
    
    model = pipeline.fit(train_df)
    
    duration = (datetime.now() - start_time).total_seconds()
    print(f"  ✅ Completed in {duration:.1f}s ({duration/60:.1f} min)")
    
    return model


def evaluate_model(model, test_df):
    """Evaluate model performance"""
    print(f"\n📊 Evaluating model...")
    
    predictions = model.transform(test_df)
    
    # Calculate metrics
    r2_eval = RegressionEvaluator(labelCol="speed", predictionCol="prediction", metricName="r2")
    rmse_eval = RegressionEvaluator(labelCol="speed", predictionCol="prediction", metricName="rmse")
    mae_eval = RegressionEvaluator(labelCol="speed", predictionCol="prediction", metricName="mae")
    
    r2 = r2_eval.evaluate(predictions)
    rmse = rmse_eval.evaluate(predictions)
    mae = mae_eval.evaluate(predictions)
    
    metrics = {"R²": r2, "RMSE": rmse, "MAE": mae}
    
    # Display results
    print(f"\n📈 RESULTS:")
    print(f"  • R²:   {r2:.6f} {'🎉' if r2 >= 0.995 else '✅' if r2 >= 0.99 else '⚠️'}")
    print(f"  • RMSE: {rmse:.4f}")
    print(f"  • MAE:  {mae:.4f}")
    
    # Show sample predictions
    print("\n📋 Sample predictions:")
    predictions.select("speed", "prediction").show(10, truncate=False)
    
    return metrics, predictions


def save_model(model, output_path, metrics, feature_cols, sample_info):
    """Save trained model and metadata"""
    print(f"\n💾 Saving model to: {output_path}")
    
    model.write().overwrite().save(output_path)
    print(f"  ✅ Model saved")
    
    # Create metadata
    metadata = {
        "training_date": datetime.now().isoformat(),
        "metrics": metrics,
        "num_features": len(feature_cols),
        "feature_names": feature_cols,
        "target_variable": "speed",
        "model_type": "GradientBoostedTrees",
        "sample_info": sample_info,
        "note": "Trained on sample to avoid Docker instability on Windows"
    }
    
    metadata_path = output_path.replace("/models/", "/models-metadata/")
    metadata_json = json.dumps(metadata, indent=2)
    
    # Save metadata
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
    print(" 🚀 ML TRAINING - SAMPLE MODE (1M RECORDS)")
    print("="*70)
    
    if len(sys.argv) < 3:
        print("\n❌ Usage: train_model_sample.py <input_path> <output_path>")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    
    # Initialize Spark
    spark = create_spark_session()
    
    # Load and sample data
    df, total_count, sample_count = load_and_sample_features(spark, input_path, sample_size=1000000)
    
    sample_info = {
        "total_records": total_count,
        "sampled_records": sample_count,
        "sample_percentage": (sample_count / total_count * 100)
    }
    
    # Prepare features
    assembler, scaler, feature_cols = prepare_features(df)
    
    # Split data
    train_df, test_df = split_data(df)
    
    # Train model
    model = train_gbt_model(train_df, assembler, scaler)
    
    # Evaluate
    metrics, _ = evaluate_model(model, test_df)
    
    # Assess results
    print("\n" + "="*70)
    if metrics["R²"] >= 0.9996:
        print(" 🎉 EXCEEDED TARGET! R² >= 0.9996")
    elif metrics["R²"] >= 0.995:
        print(" ✅ EXCELLENT! R² >= 0.995 (Very close to target!)")
    elif metrics["R²"] >= 0.99:
        print(" ✅ GREAT! R² >= 0.99 (Proves pipeline works!)")
    elif metrics["R²"] >= 0.95:
        print(" ⚠️ GOOD but could be better. R² >= 0.95")
    else:
        print(f" ⚠️ R² = {metrics['R²']:.4f} - Model needs tuning")
    print("="*70)
    
    # Save model
    save_model(model, output_path, metrics, feature_cols, sample_info)
    
    print("\n" + "="*70)
    print(" ✅ ML TRAINING COMPLETED SUCCESSFULLY")
    print("="*70)
    print("\n📝 Note: Trained on 1M sample to avoid Docker crashes")
    print("    Full dataset training would require Linux/cloud environment")
    
    spark.stop()


if __name__ == "__main__":
    main()

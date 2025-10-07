#!/usr/bin/env python3
"""
Test script to verify ML model can be loaded from HDFS
"""

from pyspark.sql import SparkSession
from pyspark.ml.regression import LinearRegressionModel
from pyspark.ml.feature import VectorAssembler

def main():
    print("\n" + "="*60)
    print("🧪 Testing ML Model Loading from HDFS")
    print("="*60 + "\n")
    
    # Create Spark session
    print("1️⃣ Creating Spark session...")
    spark = SparkSession.builder \
        .appName("Test Model Loading") \
        .master("local[2]") \
        .config("spark.driver.memory", "2g") \
        .getOrCreate()
    print("   ✅ Spark session created\n")
    
    # Load model
    print("2️⃣ Loading Linear Regression model from HDFS...")
    model_path = "hdfs://namenode:9000/ml/models/speed_linear_regression"
    assembler_path = "hdfs://namenode:9000/ml/models/speed_linear_regression_assembler"
    
    try:
        model = LinearRegressionModel.load(model_path)
        assembler = VectorAssembler.load(assembler_path)
        print("   ✅ Model loaded successfully!")
        print(f"   📊 Features: {len(model.coefficients)}")
        print(f"   📈 Intercept: {model.intercept:.4f}")
        print(f"   📋 Feature columns: {assembler.getInputCols()}\n")
        
        # Create test data
        print("3️⃣ Creating test prediction data...")
        test_data = spark.createDataFrame([
            (0, 10, 1, 1, 1, 0, 65.0, 5.0, 60.0, 70.0, 0.5, 0.8, 64.0, 4.0, 450.0, 50.0, 440.0, 45.0),
            (1, 15, 2, 2, 0, 1, 45.0, 8.0, 35.0, 55.0, -2.0, 0.6, 48.0, 6.0, 650.0, 70.0, 640.0, 65.0)
        ], ["hour", "day_of_week", "day_of_month", "month", "is_weekend", "is_rush_hour",
            "speed_rolling_avg", "speed_rolling_std", "speed_rolling_min", "speed_rolling_max",
            "speed_change", "speed_normalized", "segment_avg_speed", "segment_std_speed",
            "volume_rolling_avg", "volume_rolling_std", "segment_avg_volume", "segment_std_volume"])
        
        print("   ✅ Test data created\n")
        
        # Make predictions
        print("4️⃣ Making predictions...")
        features_df = assembler.transform(test_data)
        predictions = model.transform(features_df)
        
        print("   ✅ Predictions made successfully!\n")
        print("="*60)
        print("RESULTS:")
        print("="*60)
        predictions.select("hour", "is_rush_hour", "speed_rolling_avg", "prediction").show(truncate=False)
        
        print("\n✅ Model loading and prediction test PASSED!\n")
        
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
        raise
    finally:
        spark.stop()

if __name__ == "__main__":
    main()

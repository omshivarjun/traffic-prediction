#!/usr/bin/env python3
"""
Debug version of streaming predictor with intermediate output
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *
from pyspark.ml.regression import LinearRegressionModel
from pyspark.ml.feature import VectorAssembler

def create_spark_session():
    """Create Spark session"""
    return SparkSession.builder \
        .appName("Traffic Predictions DEBUG") \
        .master("local[2]") \
        .config("spark.driver.memory", "2g") \
        .config("spark.sql.shuffle.partitions", "2") \
        .getOrCreate()

def load_models(spark):
    """Load ML model and assembler from HDFS"""
    print("📂 Loading model from HDFS...")
    model = LinearRegressionModel.load("hdfs://namenode:9000/ml/models/speed_linear_regression")
    assembler = VectorAssembler.load("hdfs://namenode:9000/ml/models/speed_linear_regression_assembler")
    print(f"✅ Model loaded! Features: {len(model.coefficients)}")
    print(f"✅ Assembler features: {assembler.getInputCols()}")
    return model, assembler

def create_schema():
    """Schema for Kafka traffic events"""
    return StructType([
        StructField("segment_id", StringType()),
        StructField("timestamp", LongType()),
        StructField("speed", DoubleType()),
        StructField("volume", LongType())
    ])

def read_stream(spark):
    """Read from Kafka"""
    print("🔌 Connecting to Kafka...")
    return spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", "kafka-broker1:9092,kafka-broker2:9093") \
        .option("subscribe", "traffic-events") \
        .option("startingOffsets", "latest") \
        .load()

def main():
    print("\n" + "="*60)
    print("🐛 DEBUG Real-time Traffic Prediction Service")
    print("="*60 + "\n")
    
    # Initialize
    spark = create_spark_session()
    model, assembler = load_models(spark)
    schema = create_schema()
    
    # Read stream
    kafka_df = read_stream(spark)
    
    # Parse JSON - DEBUG OUTPUT
    print("📊 Parsing Kafka messages...")
    
    # DEBUG: First show RAW JSON string
    print("🔍 DEBUG: Showing RAW Kafka messages...")
    debug_raw = kafka_df.selectExpr("CAST(value AS STRING) as json_str") \
        .writeStream \
        .outputMode("append") \
        .format("console") \
        .option("truncate", False) \
        .trigger(processingTime="5 seconds") \
        .queryName("DEBUG_RAW") \
        .start()
    
    parsed_df = kafka_df.selectExpr("CAST(value AS STRING) as json_str") \
        .select(from_json(col("json_str"), schema).alias("data")) \
        .select("data.*") \
        .withColumn("timestamp_dt", from_unixtime(col("timestamp") / 1000))
    
    # DEBUG: Show parsed data
    print("🔍 DEBUG: Showing parsed data...")
    debug_parsed = parsed_df \
        .writeStream \
        .outputMode("append") \
        .format("console") \
        .option("truncate", False) \
        .trigger(processingTime="5 seconds") \
        .queryName("DEBUG_PARSED") \
        .start()
    
    # Create features
    print("🔧 Creating features...")
    features_df = parsed_df \
        .withColumn("hour", hour("timestamp_dt")) \
        .withColumn("day_of_week", dayofweek("timestamp_dt")) \
        .withColumn("day_of_month", dayofmonth("timestamp_dt")) \
        .withColumn("month", month("timestamp_dt")) \
        .withColumn("is_weekend", when(col("day_of_week").isin([1,7]), 1).otherwise(0)) \
        .withColumn("is_rush_hour", when(col("hour").between(7,9) | col("hour").between(16,18), 1).otherwise(0)) \
        .withColumn("speed_rolling_avg", col("speed")) \
        .withColumn("speed_rolling_std", lit(5.0)) \
        .withColumn("speed_rolling_min", col("speed") - 10.0) \
        .withColumn("speed_rolling_max", col("speed") + 10.0) \
        .withColumn("speed_change", lit(0.0)) \
        .withColumn("speed_normalized", col("speed") / 80.0) \
        .withColumn("segment_avg_speed", col("speed")) \
        .withColumn("segment_std_speed", lit(5.0)) \
        .withColumn("volume_rolling_avg", col("volume").cast("double")) \
        .withColumn("volume_rolling_std", lit(50.0)) \
        .withColumn("segment_avg_volume", col("volume").cast("double")) \
        .withColumn("segment_std_volume", lit(50.0))
    
    # DEBUG: Show features
    print("🔍 DEBUG: Showing features...")
    debug_features = features_df \
        .select("segment_id", "timestamp", "speed", "volume", "hour", "day_of_week", 
                "is_rush_hour", "speed_rolling_avg", "volume_rolling_avg") \
        .writeStream \
        .outputMode("append") \
        .format("console") \
        .option("truncate", False) \
        .trigger(processingTime="5 seconds") \
        .queryName("DEBUG_FEATURES") \
        .start()
    
    # Apply model
    print("🤖 Applying ML model...")
    assembled_df = assembler.transform(features_df)
    
    # DEBUG: Show assembled
    print("🔍 DEBUG: Showing assembled data...")
    debug_assembled = assembled_df \
        .select("segment_id", "speed", "volume", "features") \
        .writeStream \
        .outputMode("append") \
        .format("console") \
        .option("truncate", False) \
        .trigger(processingTime="5 seconds") \
        .queryName("DEBUG_ASSEMBLED") \
        .start()
    
    predictions = model.transform(assembled_df)
    
    # DEBUG: Show predictions
    print("🔍 DEBUG: Showing model predictions...")
    debug_predictions = predictions \
        .select("segment_id", "speed", "volume", "prediction") \
        .writeStream \
        .outputMode("append") \
        .format("console") \
        .option("truncate", False) \
        .trigger(processingTime="5 seconds") \
        .queryName("DEBUG_PREDICTIONS") \
        .start()
    
    # Format output
    print("📤 Formatting predictions...")
    output_df = predictions.select(
        col("segment_id"),
        col("timestamp"),
        col("speed").alias("current_speed"),
        col("prediction").alias("predicted_speed"),
        col("volume").alias("current_volume"),
        current_timestamp().alias("prediction_time")
    ).withColumn("speed_diff", col("predicted_speed") - col("current_speed")) \
     .withColumn("category", 
        when(col("predicted_speed") < 30, "severe_congestion")
        .when(col("predicted_speed") < 45, "heavy_traffic")
        .when(col("predicted_speed") < 60, "moderate_traffic")
        .otherwise("free_flow"))
    
    # DEBUG: Show final output
    print("🔍 DEBUG: Showing final output...")
    debug_output = output_df \
        .writeStream \
        .outputMode("append") \
        .format("console") \
        .option("truncate", False) \
        .trigger(processingTime="5 seconds") \
        .queryName("DEBUG_OUTPUT") \
        .start()
    
    print("\n" + "="*60)
    print("✅ DEBUG Prediction service running!")
    print("📥 Reading from: traffic-events")
    print("🔍 Showing all transformation steps")
    print("="*60 + "\n")
    print("\nPress Ctrl+C to stop...")
    
    # Wait for termination
    debug_output.awaitTermination()

if __name__ == "__main__":
    main()

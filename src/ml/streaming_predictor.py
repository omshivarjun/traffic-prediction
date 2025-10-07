#!/usr/bin/env python3
"""
Real-time Traffic Prediction Service
Reads from Kafka 'traffic-events' topic, applies ML model, publishes to 'traffic-predictions'
Uses the best-performing Linear Regression model from HDFS
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *
from pyspark.ml.regression import LinearRegressionModel
from pyspark.ml.feature import VectorAssembler
from pyspark.ml import PipelineModel
import json
from datetime import datetime

def create_spark_session():
    """Create Spark session with Kafka support"""
    return SparkSession.builder \
        .appName("Real-time Traffic Prediction") \
        .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0") \
        .config("spark.sql.streaming.checkpointLocation", "/tmp/spark-checkpoints") \
        .config("spark.driver.memory", "2g") \
        .config("spark.executor.memory", "2g") \
        .getOrCreate()

def load_ml_model(spark):
    """Load the best ML model from HDFS"""
    print("📂 Loading Linear Regression model from HDFS...")
    
    model_path = "hdfs://namenode:9000/ml/models/speed_linear_regression"
    assembler_path = "hdfs://namenode:9000/ml/models/speed_linear_regression_assembler"
    
    try:
        model = LinearRegressionModel.load(model_path)
        assembler = VectorAssembler.load(assembler_path)
        print("✅ Model loaded successfully!")
        print(f"   Model coefficients: {len(model.coefficients)} features")
        print(f"   Intercept: {model.intercept:.4f}")
        return model, assembler
    except Exception as e:
        print(f"❌ Error loading model: {str(e)}")
        print(f"   Model path: {model_path}")
        raise

def create_traffic_schema():
    """Define schema for traffic events from Kafka"""
    return StructType([
        StructField("segment_id", StringType(), True),
        StructField("timestamp", StringType(), True),
        StructField("speed", DoubleType(), True),
        StructField("volume", LongType(), True),
        StructField("coordinates", StructType([
            StructField("latitude", DoubleType(), True),
            StructField("longitude", DoubleType(), True)
        ]), True),
        StructField("traffic_data", StructType([
            StructField("speed", DoubleType(), True),
            StructField("volume", LongType(), True)
        ]), True)
    ])

def read_traffic_stream(spark):
    """Read streaming traffic events from Kafka"""
    print("🔌 Connecting to Kafka topic 'traffic-events'...")
    
    df = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", "kafka-broker1:9092,kafka-broker2:9093") \
        .option("subscribe", "traffic-events") \
        .option("startingOffsets", "latest") \
        .option("failOnDataLoss", "false") \
        .load()
    
    print("✅ Connected to Kafka stream")
    return df

def parse_traffic_events(df):
    """Parse JSON traffic events from Kafka"""
    schema = create_traffic_schema()
    
    # Parse JSON from Kafka value
    parsed_df = df.selectExpr("CAST(value AS STRING) as json_str") \
        .select(from_json(col("json_str"), schema).alias("data")) \
        .select("data.*")
    
    # Handle nested traffic_data structure
    df_with_traffic = parsed_df.withColumn(
        "actual_speed",
        when(col("traffic_data").isNotNull(), col("traffic_data.speed"))
        .otherwise(col("speed"))
    ).withColumn(
        "actual_volume", 
        when(col("traffic_data").isNotNull(), col("traffic_data.volume"))
        .otherwise(col("volume"))
    )
    
    return df_with_traffic

def engineer_features(df):
    """Create ML features from raw traffic events"""
    
    # Parse timestamp and extract time features
    df_features = df.withColumn(
        "timestamp_dt",
        to_timestamp(col("timestamp"))
    ).withColumn(
        "hour", hour(col("timestamp_dt"))
    ).withColumn(
        "day_of_week", dayofweek(col("timestamp_dt"))
    ).withColumn(
        "day_of_month", dayofmonth(col("timestamp_dt"))
    ).withColumn(
        "month", month(col("timestamp_dt"))
    ).withColumn(
        "is_weekend",
        when(col("day_of_week").isin([1, 7]), 1).otherwise(0)
    ).withColumn(
        "is_rush_hour",
        when(
            (col("hour").between(7, 9)) | (col("hour").between(16, 18)),
            1
        ).otherwise(0)
    )
    
    # For streaming, we'll use simple rolling averages (can't use window functions easily)
    # In production, you'd maintain state for accurate rolling calculations
    df_features = df_features.withColumn(
        "speed_rolling_avg", col("actual_speed")
    ).withColumn(
        "speed_rolling_std", lit(10.0)  # Placeholder, use historical data
    ).withColumn(
        "speed_rolling_min", col("actual_speed") - 10
    ).withColumn(
        "speed_rolling_max", col("actual_speed") + 10
    ).withColumn(
        "speed_change", lit(0.0)  # Placeholder
    ).withColumn(
        "speed_normalized", col("actual_speed") / 120.0  # Max speed assumption
    ).withColumn(
        "segment_avg_speed", lit(60.0)  # Placeholder, should use historical
    ).withColumn(
        "segment_std_speed", lit(15.0)  # Placeholder
    ).withColumn(
        "volume_rolling_avg", col("actual_volume").cast(DoubleType())
    ).withColumn(
        "volume_rolling_std", lit(80.0)  # Placeholder
    ).withColumn(
        "segment_avg_volume", lit(450.0)  # Placeholder
    ).withColumn(
        "segment_std_volume", lit(90.0)  # Placeholder
    )
    
    return df_features

def apply_ml_model(df, model, assembler):
    """Apply ML model to generate predictions"""
    
    # Select features in correct order
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
    
    # Ensure all features exist and are properly typed
    for col_name in feature_cols:
        if col_name not in df.columns:
            df = df.withColumn(col_name, lit(0.0))
    
    # Assemble features
    df_assembled = assembler.transform(df)
    
    # Apply model
    predictions = model.transform(df_assembled)
    
    # Add prediction metadata
    predictions = predictions.withColumn(
        "prediction_timestamp", current_timestamp()
    ).withColumn(
        "model_name", lit("linear_regression")
    ).withColumn(
        "model_version", lit("v1.0")
    ).withColumn(
        "confidence", lit(0.9999)  # From R² score
    )
    
    return predictions

def format_prediction_output(predictions):
    """Format predictions for Kafka output"""
    
    output = predictions.select(
        col("segment_id"),
        col("timestamp"),
        col("actual_speed").alias("current_speed"),
        col("prediction").alias("predicted_speed"),
        col("actual_volume").alias("current_volume"),
        col("coordinates"),
        col("hour"),
        col("day_of_week"),
        col("is_rush_hour"),
        col("prediction_timestamp"),
        col("model_name"),
        col("model_version"),
        col("confidence")
    ).withColumn(
        "speed_difference", col("predicted_speed") - col("current_speed")
    ).withColumn(
        "prediction_category",
        when(col("predicted_speed") < 30, "severe_congestion")
        .when(col("predicted_speed") < 45, "heavy_congestion")
        .when(col("predicted_speed") < 60, "moderate_traffic")
        .otherwise("free_flow")
    )
    
    # Convert to JSON for Kafka
    json_output = output.select(
        to_json(struct("*")).alias("value")
    )
    
    return json_output

def write_to_kafka(predictions):
    """Write predictions to Kafka topic"""
    
    query = predictions.writeStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", "kafka-broker1:9092,kafka-broker2:9093") \
        .option("topic", "traffic-predictions") \
        .option("checkpointLocation", "/tmp/spark-checkpoints/predictions") \
        .outputMode("append") \
        .start()
    
    return query

def write_to_console(predictions):
    """Write predictions to console for debugging"""
    
    # Parse JSON back for display
    schema = StructType([
        StructField("segment_id", StringType()),
        StructField("current_speed", DoubleType()),
        StructField("predicted_speed", DoubleType()),
        StructField("speed_difference", DoubleType()),
        StructField("prediction_category", StringType())
    ])
    
    display_df = predictions.select(
        from_json(col("value"), schema).alias("pred")
    ).select(
        "pred.segment_id",
        "pred.current_speed",
        "pred.predicted_speed",
        "pred.speed_difference",
        "pred.prediction_category"
    )
    
    query = display_df.writeStream \
        .format("console") \
        .option("truncate", "false") \
        .outputMode("append") \
        .start()
    
    return query

def main():
    """Main streaming prediction pipeline"""
    print("\n" + "="*60)
    print("🚀 Starting Real-time Traffic Prediction Service")
    print("="*60 + "\n")
    
    start_time = datetime.now()
    
    # Create Spark session
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")
    
    try:
        # Load ML model
        model, assembler = load_ml_model(spark)
        
        # Read traffic stream
        raw_stream = read_traffic_stream(spark)
        
        # Parse events
        print("🔧 Parsing traffic events...")
        parsed_stream = parse_traffic_events(raw_stream)
        
        # Engineer features
        print("⚙️  Engineering features...")
        feature_stream = engineer_features(parsed_stream)
        
        # Apply ML model
        print("🤖 Applying ML model...")
        predictions = apply_ml_model(feature_stream, model, assembler)
        
        # Format output
        print("📦 Formatting predictions...")
        json_predictions = format_prediction_output(predictions)
        
        # Write to Kafka
        print("📤 Writing predictions to Kafka topic 'traffic-predictions'...")
        kafka_query = write_to_kafka(json_predictions)
        
        # Also write to console for debugging
        print("📺 Displaying predictions in console...")
        console_query = write_to_console(json_predictions)
        
        print("\n" + "="*60)
        print("✅ Real-time Prediction Service Started!")
        print("="*60)
        print(f"⏱️  Started at: {start_time}")
        print(f"📊 Model: Linear Regression (R² = 0.9999)")
        print(f"📥 Input: traffic-events (Kafka)")
        print(f"📤 Output: traffic-predictions (Kafka)")
        print(f"\n💡 Predictions updating in real-time...")
        print(f"🛑 Press Ctrl+C to stop\n")
        
        # Wait for termination
        kafka_query.awaitTermination()
        
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping prediction service...")
        spark.stop()
        print("✅ Service stopped gracefully")
    except Exception as e:
        print(f"\n❌ Error in prediction service: {str(e)}")
        import traceback
        traceback.print_exc()
        spark.stop()
        raise

if __name__ == "__main__":
    main()

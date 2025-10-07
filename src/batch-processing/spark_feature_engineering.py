#!/usr/bin/env python3
"""
Traffic Prediction Feature Engineering with PySpark
Reads traffic events from HDFS and generates ML features WITHOUT Hive
"""

import sys
import json
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import *
from pyspark.sql.window import Window

def create_spark_session():
    """Create Spark session configured for HDFS access"""
    return SparkSession.builder \
        .appName("TrafficFeatureEngineering") \
        .config("spark.sql.warehouse.dir", "hdfs://namenode:9000/warehouse") \
        .config("spark.executor.memory", "2g") \
        .config("spark.driver.memory", "1g") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
        .getOrCreate()

def load_traffic_data(spark, hdfs_path):
    """Load traffic data from HDFS (JSON or Parquet)"""
    print(f"📂 Loading traffic data from: {hdfs_path}")
    
    # Use basePath option to ignore partition discovery issues
    try:
        # Try loading as Parquet first (more efficient)
        df = spark.read.option("basePath", hdfs_path).option("recursiveFileLookup", "true").parquet(hdfs_path)
        print(f"✅ Loaded Parquet data: {df.count()} records")
        return df
    except Exception as e:
        print(f"⚠️  Parquet failed, trying JSON: {str(e)[:200]}")
        
        try:
            # Fallback to JSON with recursive lookup
            df = spark.read.option("recursiveFileLookup", "true").json(hdfs_path)
            print(f"✅ Loaded JSON data: {df.count()} records")
            
            # Flatten nested structs if present
            if "traffic_data" in df.columns:
                print("📊 Flattening nested traffic_data structure...")
                df = df.withColumn("speed", F.col("traffic_data.speed_mph")) \
                       .withColumn("volume", F.col("traffic_data.volume_vehicles_per_hour")) \
                       .withColumn("occupancy", F.col("traffic_data.occupancy_percentage")) \
                       .withColumn("congestion_level_raw", F.col("traffic_data.congestion_level"))
            
            if "location" in df.columns:
                print("📊 Flattening location structure...")
                df = df.withColumn("latitude", F.col("location.latitude")) \
                       .withColumn("longitude", F.col("location.longitude")) \
                       .withColumn("highway", F.col("location.highway")) \
                       .withColumn("direction", F.col("location.direction"))
                
            # Use sensor_id as segment_id
            if "sensor_id" in df.columns and "segment_id" not in df.columns:
                print("📊 Using sensor_id as segment_id...")
                df = df.withColumn("segment_id", F.col("sensor_id"))
            
            return df
        except Exception as e2:
            print(f"⚠️  JSON with recursive failed, trying specific path...")
            
            # Try loading from a specific file if directories fail
            try:
                df = spark.read.json(f"{hdfs_path}/year=2025/month=09/day=19/metr-la-historical.jsonl")
                print(f"✅ Loaded specific JSON file: {df.count()} records")
                return df
            except Exception as e3:
                print(f"❌ All attempts failed: {e3}")
                raise

def create_time_features(df):
    """Extract time-based features from timestamp"""
    print("🕐 Creating time-based features...")
    
    # Convert timestamp to proper datetime if needed
    if df.schema["timestamp"].dataType.typeName() == "long":
        # Assuming milliseconds timestamp
        df = df.withColumn("timestamp_dt", F.from_unixtime(F.col("timestamp") / 1000))
    else:
        df = df.withColumn("timestamp_dt", F.col("timestamp"))
    
    # Extract time features
    df = df.withColumn("hour", F.hour("timestamp_dt")) \
           .withColumn("day_of_week", F.dayofweek("timestamp_dt")) \
           .withColumn("day_of_month", F.dayofmonth("timestamp_dt")) \
           .withColumn("month", F.month("timestamp_dt")) \
           .withColumn("is_weekend", F.when(F.col("day_of_week").isin([1, 7]), 1).otherwise(0)) \
           .withColumn("is_rush_hour", F.when(
               (F.col("hour").between(7, 9)) | (F.col("hour").between(17, 19)), 1
           ).otherwise(0))
    
    return df

def create_segment_features(df):
    """Create aggregated features per segment"""
    print("📊 Creating segment-based aggregation features...")
    
    # Window specification for rolling statistics
    segment_window = Window.partitionBy("segment_id").orderBy("timestamp_dt") \
        .rowsBetween(-5, 0)  # Last 6 observations per segment
    
    # Rolling statistics
    df = df.withColumn("speed_rolling_avg", F.avg("speed").over(segment_window)) \
           .withColumn("speed_rolling_std", F.stddev("speed").over(segment_window)) \
           .withColumn("speed_rolling_min", F.min("speed").over(segment_window)) \
           .withColumn("speed_rolling_max", F.max("speed").over(segment_window))
    
    if "volume" in df.columns:
        df = df.withColumn("volume_rolling_avg", F.avg("volume").over(segment_window)) \
               .withColumn("volume_rolling_std", F.stddev("volume").over(segment_window))
    
    # Speed change (derivative)
    df = df.withColumn("speed_prev", F.lag("speed", 1).over(
        Window.partitionBy("segment_id").orderBy("timestamp_dt")
    ))
    df = df.withColumn("speed_change", F.col("speed") - F.col("speed_prev"))
    
    return df

def create_hourly_aggregates(df):
    """Create hourly aggregated statistics per segment"""
    print("📈 Creating hourly aggregates...")
    
    # Group by segment and hour
    hourly_agg = df.groupBy("segment_id", "hour", "day_of_week") \
        .agg(
            F.avg("speed").alias("avg_speed_hourly"),
            F.stddev("speed").alias("std_speed_hourly"),
            F.min("speed").alias("min_speed_hourly"),
            F.max("speed").alias("max_speed_hourly"),
            F.count("*").alias("event_count_hourly")
        )
    
    if "volume" in df.columns:
        volume_agg = df.groupBy("segment_id", "hour", "day_of_week") \
            .agg(
                F.avg("volume").alias("avg_volume_hourly"),
                F.stddev("volume").alias("std_volume_hourly")
            )
        hourly_agg = hourly_agg.join(volume_agg, ["segment_id", "hour", "day_of_week"], "left")
    
    return hourly_agg

def create_segment_profiles(df):
    """Create statistical profiles for each segment (historical averages)"""
    print("🗺️  Creating segment profiles...")
    
    segment_profiles = df.groupBy("segment_id") \
        .agg(
            F.avg("speed").alias("segment_avg_speed"),
            F.stddev("speed").alias("segment_std_speed"),
            F.min("speed").alias("segment_min_speed"),
            F.max("speed").alias("segment_max_speed"),
            F.count("*").alias("segment_total_events")
        )
    
    if "volume" in df.columns:
        volume_profiles = df.groupBy("segment_id") \
            .agg(
                F.avg("volume").alias("segment_avg_volume"),
                F.stddev("volume").alias("segment_std_volume")
            )
        segment_profiles = segment_profiles.join(volume_profiles, "segment_id", "left")
    
    return segment_profiles

def prepare_ml_features(df, segment_profiles):
    """Join all features and prepare final dataset for ML"""
    print("🔧 Preparing final ML feature set...")
    
    # Join with segment profiles
    df = df.join(segment_profiles, "segment_id", "left")
    
    # Calculate normalized features (speed relative to segment average)
    df = df.withColumn("speed_normalized", 
                       F.col("speed") / (F.col("segment_avg_speed") + 1))  # +1 to avoid division by zero
    
    # Calculate congestion indicator
    df = df.withColumn("congestion_level", F.when(
        F.col("speed") < F.col("segment_avg_speed") * 0.5, "severe"
    ).when(
        F.col("speed") < F.col("segment_avg_speed") * 0.7, "moderate"
    ).otherwise("normal"))
    
    # Select final feature columns
    feature_columns = [
        "segment_id", "timestamp", "timestamp_dt",
        "speed", "hour", "day_of_week", "day_of_month", "month",
        "is_weekend", "is_rush_hour",
        "speed_rolling_avg", "speed_rolling_std", "speed_rolling_min", "speed_rolling_max",
        "speed_change", "speed_normalized",
        "segment_avg_speed", "segment_std_speed", "congestion_level"
    ]
    
    # Add volume features if available
    if "volume" in df.columns:
        feature_columns.extend([
            "volume", "volume_rolling_avg", "volume_rolling_std",
            "segment_avg_volume", "segment_std_volume"
        ])
    
    # Add coordinates if available
    if "coordinates" in df.columns:
        feature_columns.append("coordinates")
    
    # Select only available columns
    available_columns = [col for col in feature_columns if col in df.columns]
    df = df.select(available_columns)
    
    # Drop rows with null values in critical columns
    df = df.dropna(subset=["speed", "segment_id", "timestamp"])
    
    return df

def main(input_path, output_path):
    """Main feature engineering pipeline"""
    print("=" * 60)
    print("🚀 Traffic Feature Engineering Pipeline (Spark SQL - No Hive)")
    print("=" * 60)
    
    # Create Spark session
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")  # Reduce noise
    
    try:
        # Load data
        df = load_traffic_data(spark, input_path)
        print(f"📊 Schema:")
        df.printSchema()
        
        # Show sample data
        print("\n📋 Sample data (first 5 rows):")
        df.show(5, truncate=False)
        
        # Create features
        df = create_time_features(df)
        df = create_segment_features(df)
        
        # Create segment profiles
        segment_profiles = create_segment_profiles(df)
        print(f"\n📈 Segment profiles created: {segment_profiles.count()} segments")
        segment_profiles.show(10)
        
        # Save segment profiles separately
        profiles_path = f"{output_path}/segment_profiles"
        print(f"\n💾 Saving segment profiles to: {profiles_path}")
        segment_profiles.write.mode("overwrite").parquet(profiles_path)
        
        # Create hourly aggregates
        hourly_agg = create_hourly_aggregates(df)
        print(f"\n📊 Hourly aggregates created: {hourly_agg.count()} records")
        hourly_agg.show(10)
        
        # Save hourly aggregates
        hourly_path = f"{output_path}/hourly_aggregates"
        print(f"\n💾 Saving hourly aggregates to: {hourly_path}")
        hourly_agg.write.mode("overwrite").partitionBy("segment_id").parquet(hourly_path)
        
        # Prepare final ML features
        df_features = prepare_ml_features(df, segment_profiles)
        print(f"\n✅ Final feature set: {df_features.count()} records")
        print(f"📊 Feature schema:")
        df_features.printSchema()
        
        # Show feature statistics
        print("\n📈 Feature statistics:")
        df_features.select("speed", "speed_rolling_avg", "speed_normalized").describe().show()
        
        # Save features to HDFS
        features_path = f"{output_path}/ml_features"
        print(f"\n💾 Saving ML features to: {features_path}")
        df_features.write.mode("overwrite") \
            .partitionBy("segment_id") \
            .parquet(features_path)
        
        print("\n" + "=" * 60)
        print("✅ Feature Engineering Complete!")
        print("=" * 60)
        print(f"📊 Features saved to: {features_path}")
        print(f"📈 Segment profiles saved to: {profiles_path}")
        print(f"📊 Hourly aggregates saved to: {hourly_path}")
        
        # Summary statistics
        print("\n📋 Summary:")
        print(f"   Total records processed: {df_features.count():,}")
        print(f"   Unique segments: {df_features.select('segment_id').distinct().count()}")
        print(f"   Features per record: {len(df_features.columns)}")
        print(f"   Date range: {df_features.agg(F.min('timestamp_dt'), F.max('timestamp_dt')).collect()[0]}")
        
    except Exception as e:
        print(f"\n❌ Error in feature engineering: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        spark.stop()

if __name__ == "__main__":
    # Default paths
    input_path = "hdfs://namenode:9000/traffic-data/raw"
    output_path = "hdfs://namenode:9000/traffic-data/features"
    
    # Allow command line arguments
    if len(sys.argv) > 1:
        input_path = sys.argv[1]
    if len(sys.argv) > 2:
        output_path = sys.argv[2]
    
    print(f"📍 Input path: {input_path}")
    print(f"📍 Output path: {output_path}")
    
    main(input_path, output_path)

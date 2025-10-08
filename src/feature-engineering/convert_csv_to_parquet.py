#!/usr/bin/env python3
"""
Convert METR-LA CSV to Parquet

Converts the raw CSV dataset to Parquet format for efficient processing.
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, to_timestamp
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, TimestampType, IntegerType
)


def create_spark_session():
    """Create Spark session with HDFS configuration."""
    return SparkSession.builder \
        .appName("Convert METR-LA CSV to Parquet") \
        .config("spark.hadoop.fs.defaultFS", "hdfs://namenode:9000") \
        .config("spark.sql.parquet.compression.codec", "snappy") \
        .getOrCreate()


def convert_to_parquet(
    input_path: str,
    output_path: str
):
    """
    Convert CSV to Parquet.
    
    Args:
        input_path: HDFS path to input CSV
        output_path: HDFS path for output Parquet
    """
    spark = create_spark_session()
    
    print("=" * 100)
    print("CONVERTING METR-LA CSV TO PARQUET")
    print("=" * 100)
    print(f"Input: {input_path}")
    print(f"Output: {output_path}")
    print()
    
    # Define schema for METR-LA dataset
    schema = StructType([
        StructField("timestamp", StringType(), False),
        StructField("sensor_id", StringType(), False),
        StructField("speed", DoubleType(), True),
        StructField("volume", DoubleType(), True),
        StructField("occupancy", DoubleType(), True),
        StructField("latitude", DoubleType(), True),
        StructField("longitude", DoubleType(), True),
        StructField("highway", StringType(), True)
    ])
    
    print("Reading CSV from HDFS...")
    df = spark.read \
        .option("header", "true") \
        .schema(schema) \
        .csv(input_path)
    
    # Convert timestamp string to timestamp type
    df = df.withColumn("timestamp", to_timestamp(col("timestamp"), "yyyy-MM-dd HH:mm:ss"))
    
    # Show schema and sample
    print("\nDataset Schema:")
    df.printSchema()
    
    print("\nSample Data:")
    df.show(5, truncate=False)
    
    print(f"\nTotal records: {df.count():,}")
    
    # Write as Parquet partitioned by sensor_id
    print(f"\nWriting Parquet to {output_path}...")
    print("Partitioning by sensor_id for efficient querying...")
    
    df.write \
        .mode("overwrite") \
        .partitionBy("sensor_id") \
        .parquet(output_path)
    
    print()
    print("=" * 100)
    print("CONVERSION COMPLETE")
    print("=" * 100)
    print(f"✓ Parquet dataset saved to: {output_path}")
    print("✓ Partitioned by sensor_id (207 partitions)")
    print()
    print("Next steps:")
    print("  1. Verify: docker exec namenode hadoop fs -ls /traffic-data/raw/metr-la-parquet")
    print("  2. Run feature engineering: python run-feature-engineering.py")
    print()
    
    spark.stop()


if __name__ == "__main__":
    import sys
    
    input_path = sys.argv[1] if len(sys.argv) > 1 else \
        "hdfs://namenode:9000/traffic-data/raw/metr-la/metr_la_traffic_data.csv"
    output_path = sys.argv[2] if len(sys.argv) > 2 else \
        "hdfs://namenode:9000/traffic-data/raw/metr-la-parquet"
    
    convert_to_parquet(input_path, output_path)

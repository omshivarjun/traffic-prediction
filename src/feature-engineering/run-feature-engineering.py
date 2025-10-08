#!/usr/bin/env python3
"""
Run Feature Engineering Pipeline

Submits the feature engineering pipeline to Spark cluster.
Generates ML features from raw traffic data and saves to HDFS.

Usage:
  python run-feature-engineering.py [input_path] [output_path] [mode]

Examples:
  # Default paths (process aggregates → ml-features)
  python run-feature-engineering.py
  
  # Custom input/output
  python run-feature-engineering.py hdfs://namenode:9000/traffic-data/raw/metr-la \
                                     hdfs://namenode:9000/traffic-data/features \
                                     overwrite
"""

import subprocess
import sys
import os


def submit_spark_job(
    input_path: str = "hdfs://namenode:9000/traffic-data/processed/aggregates",
    output_path: str = "hdfs://namenode:9000/traffic-data/ml-features",
    metadata_path: str = "hdfs://namenode:9000/traffic-data/ml-features-metadata",
    mode: str = "overwrite"
):
    """
    Submit feature engineering pipeline to Spark cluster.
    
    Args:
        input_path: HDFS path to input data
        output_path: HDFS path for output features
        metadata_path: HDFS path for metadata
        mode: Write mode ('overwrite' or 'append')
    """
    # Path to pipeline script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Copy Python files to Docker container
    print("=" * 100)
    print("COPYING PYTHON FILES TO SPARK CONTAINER")
    print("=" * 100)
    
    python_files = [
        "feature_pipeline.py",
        "time_features.py",
        "spatial_features.py",
        "traffic_features.py",
        "historical_features.py"
    ]
    
    for filename in python_files:
        local_path = os.path.join(script_dir, filename)
        print(f"Copying {filename}...")
        copy_cmd = [
            "docker", "cp",
            local_path,
            f"spark-master:/tmp/{filename}"
        ]
        subprocess.run(copy_cmd, check=True, capture_output=True)
    
    print("✓ All Python files copied to /tmp/ in spark-master container")
    print()
    
    # Spark submit command (using container paths)
    # Using local[*] mode to avoid worker registration issues
    # Set HADOOP_CONF_DIR to use the Hadoop configuration we copied
    spark_submit_cmd = [
        "docker", "exec",
        "-e", "HADOOP_CONF_DIR=/opt/bitnami/spark/conf",
        "spark-master",
        "spark-submit",
        "--master", "local[*]",  # Use all available cores in local mode
        "--driver-memory", "6g",  # Increased for local mode
        "--conf", "spark.hadoop.fs.defaultFS=hdfs://namenode:9000",
        "--conf", "spark.sql.parquet.compression.codec=snappy",
        "--conf", "spark.sql.shuffle.partitions=200",
        "--conf", "spark.driver.maxResultSize=2g",
        "--py-files", "/tmp/time_features.py,/tmp/spatial_features.py,/tmp/traffic_features.py,/tmp/historical_features.py",
        "/tmp/feature_pipeline.py",
        input_path,
        output_path,
        metadata_path,
        mode
    ]
    
    print("=" * 100)
    print("SUBMITTING FEATURE ENGINEERING PIPELINE TO SPARK CLUSTER")
    print("=" * 100)
    print(f"Input: {input_path}")
    print(f"Output: {output_path}")
    print(f"Metadata: {metadata_path}")
    print(f"Mode: {mode}")
    print()
    print("Command:")
    print(" ".join(spark_submit_cmd))
    print()
    print("Starting execution...")
    print("=" * 100)
    print()
    
    # Execute spark-submit
    try:
        result = subprocess.run(
            spark_submit_cmd,
            check=True,
            capture_output=False,
            text=True
        )
        
        print()
        print("=" * 100)
        print("FEATURE ENGINEERING PIPELINE COMPLETED SUCCESSFULLY")
        print("=" * 100)
        print()
        print("✓ Features generated with traffic_efficiency (81% importance target)")
        print(f"✓ Output saved to: {output_path}")
        print(f"✓ Metadata saved to: {metadata_path}")
        print()
        print("Next steps:")
        print("  1. Verify features in HDFS: docker exec namenode hadoop fs -ls /traffic-data/ml-features")
        print("  2. Check metadata: docker exec namenode hadoop fs -cat /traffic-data/ml-features-metadata/part-00000")
        print("  3. Run ML training: python src/ml-training/train_all_models.py")
        print()
        
        return 0
        
    except subprocess.CalledProcessError as e:
        print()
        print("=" * 100)
        print("FEATURE ENGINEERING PIPELINE FAILED")
        print("=" * 100)
        print(f"Error code: {e.returncode}")
        print()
        print("Check Spark logs for details:")
        print("  docker logs spark-master")
        print()
        
        return e.returncode


def main():
    """Main entry point."""
    # Parse command line arguments
    input_path = sys.argv[1] if len(sys.argv) > 1 else \
        "hdfs://namenode:9000/traffic-data/processed/aggregates"
    output_path = sys.argv[2] if len(sys.argv) > 2 else \
        "hdfs://namenode:9000/traffic-data/ml-features"
    metadata_path = sys.argv[3] if len(sys.argv) > 3 else \
        "hdfs://namenode:9000/traffic-data/ml-features-metadata"
    mode = sys.argv[4] if len(sys.argv) > 4 else "overwrite"
    
    # Submit job
    exit_code = submit_spark_job(input_path, output_path, metadata_path, mode)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

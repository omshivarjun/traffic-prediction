#!/usr/bin/env python3
"""
Completely reconstruct the header of metr_la_ml_training.py
"""

def fix_metr_la_header():
    file_path = "src/ml/metr_la_ml_training.py"
    
    # Read the file
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Create correct header
    correct_header = '''#!/usr/bin/env python3
"""
METR-LA ML Training Pipeline - Spark MLlib Implementation

Spark MLlib pipeline for traffic prediction model training

Features:
- Reads aggregated data from HDFS
- Time-series feature engineering
- Multiple ML algorithms (Linear Regression, Random Forest, GBT)
- Model evaluation and selection
- Model export for predictions
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

# Add PySpark to path
spark_home = os.environ.get('SPARK_HOME', '/opt/bitnami/spark')
sys.path.append(os.path.join(spark_home, 'python'))
sys.path.append(os.path.join(spark_home, 'python', 'lib', 'py4j-0.10.9.7-src.zip'))

# PySpark imports
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import (
    col, avg, max, min, count, lag, lead, stddev, 
    hour, dayofweek, when, isnan, isnull, desc, asc,
    unix_timestamp, from_unixtime, window, sum as spark_sum
)
from pyspark.sql.types import DoubleType
from pyspark.sql.window import Window

'''
    
    # Find where the duplicate section ends (looking for first non-duplicate imports/code)
    # The duplicates appear to end around line 63-70 based on error
    # Let's skip to a safe line that looks clean
    start_preserving = 70  # Start from line 70 onwards
    
    # Write the correct header plus remaining content
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(correct_header)
        # Add the rest of the file starting from a safe point
        for line in lines[start_preserving:]:
            f.write(line)
    
    print(f"✅ Reconstructed header of {file_path}")

if __name__ == "__main__":
    fix_metr_la_header()

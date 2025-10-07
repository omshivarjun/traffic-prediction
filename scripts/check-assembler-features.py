#!/usr/bin/env python3
"""Check what features the saved assembler expects"""

from pyspark.sql import SparkSession
from pyspark.ml.feature import VectorAssembler

spark = SparkSession.builder.appName("CheckAssembler").getOrCreate()
assembler = VectorAssembler.load("hdfs://namenode:9000/ml/models/speed_linear_regression_assembler")

print("\n" + "="*60)
print("📋 Expected Feature Columns:")
print("="*60)
for i, col in enumerate(assembler.getInputCols(), 1):
    print(f"{i:2d}. {col}")
print("="*60 + "\n")

spark.stop()

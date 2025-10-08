import sys
from pyspark.sql import SparkSession
from pyspark.sql.functions import col

# Get batch parameters
input_path = sys.argv[1]
output_base = sys.argv[2]
batch_num = int(sys.argv[3])
sensors_per_batch = int(sys.argv[4])

print(f"\n🎯 BATCH {batch_num} - Starting...")

# Initialize Spark with moderate resources
spark = SparkSession.builder \
    .appName(f"Feature_Engineering_Batch_{batch_num}") \
    .config("spark.sql.shuffle.partitions", "20") \
    .getOrCreate()

# Read full dataset
print(f"📖 Reading full dataset...")
df = spark.read.csv(input_path, header=True, inferSchema=True)
total_records = df.count()
print(f"  Total records: {total_records:,}")

# Get unique sensors
all_sensors = sorted([row.sensor_id for row in df.select("sensor_id").distinct().collect()])
print(f"  Total sensors: {len(all_sensors)}")

# Calculate batch range
start_idx = (batch_num - 1) * sensors_per_batch
end_idx = min(start_idx + sensors_per_batch, len(all_sensors))
batch_sensors = all_sensors[start_idx:end_idx]

print(f"\n📋 Batch {batch_num} sensors: {batch_sensors[0]} to {batch_sensors[-1]}")
print(f"  Processing {len(batch_sensors)} sensors")

# Filter to batch sensors
batch_df = df.filter(col("sensor_id").isin(batch_sensors))
batch_count = batch_df.count()
print(f"  Batch records: {batch_count:,}")

# Save batch as temporary CSV for feature pipeline
batch_output = f"/tmp/batch_{batch_num}_sensors.csv"
print(f"\n💾 Saving batch to: {batch_output}")
batch_df.coalesce(1).write.mode("overwrite").csv(batch_output, header=True)

# Find the actual CSV file (Spark creates part-* files)
import subprocess
result = subprocess.run(
    ["hadoop", "fs", "-ls", batch_output],
    capture_output=True, text=True
)
csv_file = [line.split()[-1] for line in result.stdout.split('\n') if 'part-' in line][0]
print(f"✅ Batch CSV: {csv_file}")
print(f"✅ Batch {batch_num} prepared - {batch_count:,} records")

spark.stop()

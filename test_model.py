from pyspark.sql import SparkSession
from pyspark.ml import PipelineModel

# Create Spark session
spark = SparkSession.builder \
    .appName("ModelTest") \
    .master("local[2]") \
    .config("spark.hadoop.fs.defaultFS", "hdfs://namenode:9000") \
    .getOrCreate()

print(" Spark session created")

# Load model
model_path = "hdfs://namenode:9000/traffic-data/models/gbt-sample-model"
model = PipelineModel.load(model_path)

print(f" Model loaded from {model_path}")
print(f" Model stages: {len(model.stages)}")
print(" MODEL TEST SUCCESSFUL!")

spark.stop()

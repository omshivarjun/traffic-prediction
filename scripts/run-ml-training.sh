#!/bin/bash
# Run ML Model Training in Spark
echo "🚀 Starting ML Model Training..."

# Run training script
python3 /opt/spark-apps/src/batch-processing/train_models.py

echo "✅ Training complete!"

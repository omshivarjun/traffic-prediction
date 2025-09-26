#!/bin/bash
# HDFS Data Access Script for METR-LA Dataset
# Generated: 2025-09-19
# Usage: Run these commands to access the uploaded METR-LA traffic data

echo "🌟 METR-LA Traffic Data - HDFS Access Guide"
echo "==========================================="

# List all data files
echo "📁 Available Data Files:"
docker exec namenode-alt hdfs dfs -ls -h -R /user/traffic

echo ""
echo "🔍 Quick Data Overview:"

# Show raw data files
echo "Raw Data Files:"
docker exec namenode-alt hdfs dfs -ls -h /user/traffic/raw/metr_la/

# Show processed data files  
echo "Processed Data Files:"
docker exec namenode-alt hdfs dfs -ls -h /user/traffic/processed/metr_la/

echo ""
echo "📊 Sample Data Preview (first 10 lines):"
echo "--- Sensor Metadata ---"
docker exec namenode-alt hdfs dfs -cat /user/traffic/raw/metr_la/metr_la_sensor_metadata.csv | head -n 10

echo ""
echo "--- Processed Traffic Data ---"
docker exec namenode-alt hdfs dfs -cat /user/traffic/processed/metr_la/metr_la_essential_features.csv | head -n 10

echo ""
echo "💡 Usage Examples:"
echo "# Copy file from HDFS to local:"
echo "docker exec namenode-alt hdfs dfs -get /user/traffic/processed/metr_la/metr_la_ml_ready.csv /tmp/local_file.csv"
echo "docker cp namenode-alt:/tmp/local_file.csv ./local_file.csv"
echo ""
echo "# View file contents:"
echo "docker exec namenode-alt hdfs dfs -cat /user/traffic/raw/metr_la/preprocessing_metadata.json"
echo ""
echo "# Check file size:"
echo "docker exec namenode-alt hdfs dfs -du -h /user/traffic/processed/metr_la/"

echo ""
echo "🎯 Data Summary:"
echo "- Total uploaded files: 6"
echo "- Raw data files: 3 (sensor metadata, traffic data, preprocessing metadata)"
echo "- Processed data files: 3 (full processed, essential features, ML-ready)"
echo "- Total data volume: ~12.3 MB"
echo ""
echo "✅ All METR-LA dataset files successfully uploaded to HDFS cluster!"
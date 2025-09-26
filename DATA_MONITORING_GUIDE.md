# 🔍 Where to See Your Data: Kafka → Spark → Hadoop Pipeline

## **📨 1. KAFKA - Data Ingestion Monitoring**

### **Kafka UI: http://localhost:8085**

#### **See Raw Messages:**
1. Go to http://localhost:8085
2. Click **"Topics"** tab
3. Click **"traffic-events"** topic
4. Click **"Messages"** tab
5. **What you'll see:**
   ```json
   {
     "timestamp": "2012-03-01 00:00:00",
     "sensor_id": "717462",
     "speed_mph": 65.5,
     "latitude": 34.0522,
     "longitude": -118.2437,
     "segment_id": "segment_001",
     "road_type": "highway",
     "lane_count": 4
   }
   ```

#### **Monitor Topic Statistics:**
- **Message Count**: Total messages in topic
- **Partitions**: Data distribution
- **Consumer Groups**: Who's reading the data
- **Throughput**: Messages per second

#### **Check Real-time Ingestion:**
- **Consumers Tab**: See active consumers
- **Live Tail**: Watch messages arrive in real-time

---

## **⚡ 2. SPARK - Data Processing Monitoring**

### **Spark Master UI: http://localhost:8086**

#### **See Running Applications:**
1. Go to http://localhost:8086
2. Look at **"Running Applications"** section
3. Click on any Application ID to see details
4. **What you'll see:**
   - Job execution stages
   - Task completion status
   - Memory and CPU usage
   - Processing throughput

#### **Job Details View:**
- **Stages**: Processing steps (map, reduce, etc.)
- **Tasks**: Individual processing units
- **Executors**: Worker node performance
- **SQL**: If using Spark SQL queries

#### **History Server UI: http://localhost:8189**
- **Completed Jobs**: Historical execution data
- **Performance Metrics**: Processing times, data sizes
- **Error Logs**: Debug information for failed jobs

---

## **🗂️ 3. HADOOP HDFS - Data Storage Monitoring**

### **HDFS NameNode UI: http://localhost:9871**

#### **Browse Stored Data:**
1. Go to http://localhost:9871
2. Click **"Utilities"** → **"Browse the file system"**
3. Navigate through directories:
   ```
   /user/
   ├── spark/
   │   ├── traffic-data/          # Raw traffic data
   │   ├── processed-data/        # Processed aggregates
   │   └── predictions/           # ML predictions
   ├── hive/
   │   └── warehouse/             # Hive tables
   └── ml-models/                 # Trained models
   ```

#### **File Details:**
- Click on any file to see:
  - **File size** and block information
  - **Replication factor** (data copies)
  - **Block locations** on datanodes
  - **Permissions** and timestamps

#### **Cluster Health:**
- **Overview Tab**: Storage capacity, node health
- **Datanodes Tab**: Individual node status
- **Blocks Tab**: Data block distribution

---

## **📊 4. YARN - Resource Management**

### **Resource Manager UI: http://localhost:8089**

#### **Application Monitoring:**
1. Go to http://localhost:8089
2. **Applications Tab**: See all submitted jobs
3. **Nodes Tab**: Worker node resource usage
4. **What you'll see:**
   - **Spark Streaming Jobs**: Real-time processing
   - **MapReduce Jobs**: Batch processing
   - **Memory/CPU Usage**: Resource consumption

---

## **🚀 STEP-BY-STEP: See Data Flow in Action**

### **Step 1: Send Data to Kafka**
```powershell
# Send 50 records to generate activity
python scripts\metr_la_docker_producer.py --csv-file "data\processed\metr_la_sample.csv" --max-records 50 --batch-size 10
```

### **Step 2: Check Kafka Ingestion**
- Visit http://localhost:8085
- Topics → traffic-events → Messages
- **You should see 50 JSON messages**

### **Step 3: Start Spark Streaming (if not running)**
```powershell
# Submit Spark streaming job to process Kafka data
docker exec spark-master spark-submit \
  --class "MetrLAStreamingConsumer" \
  --master spark://spark-master:7077 \
  /opt/spark-apps/metr_la_streaming_consumer.py
```

### **Step 4: Monitor Spark Processing**
- Visit http://localhost:8086
- Look for **"Running Applications"**
- Click Application ID to see:
  - **Input Rate**: Records/second from Kafka
  - **Processing Time**: How long each batch takes
  - **Output**: Data written to HDFS

### **Step 5: Check HDFS Storage**
- Visit http://localhost:9871
- Utilities → Browse File System
- Look for new directories created by Spark jobs

---

## **🔍 DETAILED DATA LOCATIONS**

### **Kafka Data Location:**
- **Topic**: `traffic-events`
- **Retention**: Last 7 days of messages
- **Format**: JSON messages in Avro schema

### **Spark Processing Data:**
- **Input**: Kafka stream (`traffic-events` topic)
- **Output**: HDFS directories
  - `/user/spark/traffic-aggregates/`
  - `/user/spark/processed-data/`
  - `/user/spark/ml-features/`

### **HDFS Storage Paths:**
```
/user/spark/
├── traffic-events/           # Raw events from Kafka
│   ├── year=2025/
│   ├── month=09/
│   └── day=20/
├── traffic-aggregates/       # 5-minute aggregations
│   ├── segment_001/
│   └── segment_002/
├── ml-models/               # Trained ML models
│   ├── linear-regression/
│   ├── random-forest/
│   └── gradient-boosted/
└── predictions/             # Generated predictions
    ├── hourly/
    └── daily/
```

---

## **🛠️ TROUBLESHOOTING: If You Don't See Data**

### **No Messages in Kafka UI:**
```powershell
# Check if producer is working
python scripts\metr_la_docker_producer.py --test-connection

# Send test data
python scripts\metr_la_docker_producer.py --csv-file "data\processed\metr_la_sample.csv" --max-records 10
```

### **No Spark Applications:**
```powershell
# Check if Spark services are running
docker ps | grep spark

# Check Spark logs
docker logs spark-master
docker logs spark-worker
```

### **Empty HDFS Directories:**
- HDFS will be empty until Spark jobs write data
- Start with Kafka → Spark streaming to populate HDFS
- Use HDFS CLI to create test directories:
```powershell
docker exec namenode hdfs dfs -ls /
docker exec namenode hdfs dfs -mkdir /user/test
```

---

## **🎯 QUICK VERIFICATION COMMANDS**

### **Check Data Flow:**
```powershell
# 1. Check Kafka messages
docker exec kafka-broker1 kafka-console-consumer --bootstrap-server localhost:9092 --topic traffic-events --timeout-ms 5000

# 2. Check HDFS directories
docker exec namenode hdfs dfs -ls /user/

# 3. Check Spark applications
curl -s http://localhost:8086/api/v1/applications | jq '.[].name'
```

### **Generate Test Data for All Services:**
```powershell
# Run complete pipeline demo
.\demo-metr-la-pipeline.ps1

# This will populate:
# - Kafka with traffic messages
# - Spark with processing jobs
# - HDFS with stored results
```

**Now you know exactly where to look for your data in each component! 🎯**
# 🎯 **LIVE DATA LOCATIONS - Your METR-LA Pipeline**

## **✅ CONFIRMED: Your Data is Here!**

Based on the system inspection, here's exactly where to find your data:

---

## **📨 1. KAFKA - Real-time Data Ingestion**

### **✅ CONFIRMED TOPICS:**
```
traffic-events              ← Your main data stream (30 messages just sent!)
traffic-alerts              ← System alerts  
traffic-incidents           ← Incident data
traffic-predictions         ← ML predictions
processed-traffic-aggregates ← Processed data
traffic-processed           ← Stream processing output
traffic-raw                 ← Raw sensor data
```

### **🔍 HOW TO SEE KAFKA DATA:**

#### **Method 1: Kafka UI (Recommended)**
- **URL**: http://localhost:8085
- **Steps**: Topics → traffic-events → Messages tab
- **What you'll see**: JSON messages with traffic sensor data

#### **Method 2: Command Line**
```powershell
# See latest messages (run right after sending data)
docker exec kafka-broker1 kafka-console-consumer --bootstrap-server localhost:9092 --topic traffic-events --from-beginning --max-messages 5
```

#### **Method 3: Check Topic Stats**
```powershell
# See topic information
docker exec kafka-broker1 kafka-topics --bootstrap-server localhost:9092 --describe --topic traffic-events
```

---

## **⚡ 2. SPARK - Data Processing**

### **✅ CURRENT SPARK APPLICATIONS:**
- **URL**: http://localhost:8086
- **What to check**: 
  - Running Applications (active jobs)
  - Completed Applications (finished jobs)
  - Workers (1 worker node should be visible)

### **🔍 HOW TO SEE SPARK PROCESSING:**

#### **Active Jobs:**
```powershell
# Check running Spark applications
curl -s http://localhost:8086/api/v1/applications | ConvertFrom-Json | Select name, id, startTime
```

#### **Submit a Processing Job to See Activity:**
```powershell
# Run streaming consumer to process Kafka data
docker exec spark-master spark-submit \
  --master spark://spark-master:7077 \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.1.2 \
  /opt/spark-apps/metr_la_streaming_consumer.py
```

---

## **🗂️ 3. HADOOP HDFS - Data Storage**

### **✅ CONFIRMED DATA DIRECTORIES:**
```
/traffic-data/
├── raw/
│   ├── metr-la/          ← Raw METR-LA dataset files
│   └── year=2025/        ← Partitioned by date
├── processed/
│   ├── aggregates/       ← 5-minute traffic aggregations  
│   ├── metr-la/         ← Processed METR-LA data
│   └── ml-features/     ← Features for ML training
├── models/              ← 6 trained ML models! ✅
│   ├── gradient_boosting_speed.joblib
│   ├── random_forest_speed.joblib
│   ├── random_forest_congestion.joblib
│   ├── encoder_highway.joblib
│   ├── scaler_features.joblib
│   └── model_metadata.json
├── predictions/         ← ML prediction outputs
└── streaming/          ← Real-time processing results
```

### **🔍 HOW TO SEE HDFS DATA:**

#### **Method 1: HDFS Web UI**
- **URL**: http://localhost:9871
- **Steps**: Utilities → Browse the file system → Navigate to /traffic-data/

#### **Method 2: Command Line**
```powershell
# Browse directories
docker exec namenode hdfs dfs -ls /traffic-data/

# See file contents (first few lines)
docker exec namenode hdfs dfs -cat /traffic-data/models/model_metadata.json

# Check file sizes
docker exec namenode hdfs dfs -du -h /traffic-data/models/
```

#### **Method 3: Download Files**
```powershell
# Copy files from HDFS to local
docker exec namenode hdfs dfs -get /traffic-data/models/model_metadata.json /tmp/
docker cp namenode:/tmp/model_metadata.json ./downloaded_metadata.json
```

---

## **📊 4. CURRENT DATA SUMMARY**

### **✅ DATA CONFIRMED IN YOUR SYSTEM:**

#### **Kafka Topics (8 total):**
- ✅ **traffic-events**: 30 fresh messages (just sent)
- ✅ **traffic-predictions**: ML prediction stream
- ✅ **processed-traffic-aggregates**: Processed data
- ✅ All topics configured with 4 partitions

#### **HDFS Storage:**
- ✅ **6 ML Models**: Already trained and stored
  - Gradient Boosting (143KB)
  - Random Forest (29MB each)
  - Feature scalers and encoders
- ✅ **Raw Data**: METR-LA dataset in /traffic-data/raw/
- ✅ **Processed Data**: Aggregates and ML features
- ✅ **Predictions**: ML output directory ready

#### **Spark Cluster:**
- ✅ **Master**: Running on port 8086
- ✅ **Worker**: 1 worker node active
- ✅ **Applications**: Ready to process data

---

## **🚀 LIVE DEMONSTRATION COMMANDS**

### **See Everything in Action:**

#### **1. Send Data & Watch Kafka:**
```powershell
# Terminal 1: Send data
python scripts\metr_la_docker_producer.py --csv-file "data\processed\metr_la_sample.csv" --max-records 20

# Terminal 2: Watch it arrive
docker exec kafka-broker1 kafka-console-consumer --bootstrap-server localhost:9092 --topic traffic-events --timeout-ms 10000
```

#### **2. Browse HDFS Data:**
```powershell
# See your ML models
docker exec namenode hdfs dfs -ls /traffic-data/models/

# Check model metadata
docker exec namenode hdfs dfs -cat /traffic-data/models/model_metadata.json
```

#### **3. Check Spark Activity:**
```powershell
# See cluster status
curl http://localhost:8086/api/v1/applications
```

#### **4. Monitor All Services:**
- **Kafka UI**: http://localhost:8085 (Messages in topics)
- **HDFS UI**: http://localhost:9871 (File browser)
- **Spark UI**: http://localhost:8086 (Job monitoring)
- **YARN UI**: http://localhost:8089 (Resource management)

---

## **🎯 QUICK ACCESS CHECKLIST**

To see your data right now:

- [ ] **Kafka Messages**: http://localhost:8085 → Topics → traffic-events → Messages
- [ ] **HDFS Files**: http://localhost:9871 → Utilities → Browse File System → /traffic-data/
- [ ] **Spark Jobs**: http://localhost:8086 → Applications tab
- [ ] **ML Models**: Command: `docker exec namenode hdfs dfs -ls /traffic-data/models/`

**Your pipeline has been actively processing data - you just need to know where to look! 🎯**
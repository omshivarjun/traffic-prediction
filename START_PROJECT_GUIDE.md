# 🚀 How to Start Your METR-LA Traffic Prediction Project

## **After Computer Restart - Required Startup Sequence**

### Step 1: Start Docker Services (REQUIRED)
```powershell
# Navigate to project directory
cd C:\traffic-prediction

# Start all Docker services (Hadoop, Kafka, Spark)
docker-compose up -d

# Wait 2-3 minutes for all services to fully initialize
```

### Step 2: Verify Services are Running
```powershell
# Check service status
docker ps

# Should show these containers running:
# - kafka-broker1 (port 9094)
# - namenode (HDFS - port 9871) 
# - spark-master (port 8086)
# - postgres (port 5433)
# - zookeeper (port 2185)
# - schema-registry (port 8082)
```

### Step 3: Start Next.js Dashboard
```powershell
# Only after Docker services are running
npm run dev

# Dashboard will be available at:
# http://localhost:3000 (or 3001 if 3000 is busy)
# Traffic heatmap at: http://localhost:3000/dashboard
```

## **Quick Demo Pipeline (Optional)**
```powershell
# Run complete demo to test everything
.\demo-metr-la-pipeline.ps1
```

## **Important Notes:**
- ❌ **Don't run** `npm run dev` first - it won't work without Docker services
- ✅ **Always start** Docker services before the Next.js app
- ⏱️ **Wait 2-3 minutes** after starting Docker for services to fully initialize
- 🔧 All Hadoop, Kafka, Spark run in **Docker containers** (no local CMD installation needed)

## **Service URLs for Development:**
- **Dashboard**: http://localhost:3000/dashboard (Traffic Heatmap)
- **Kafka UI**: http://localhost:8085 (Message monitoring) ✅
- **HDFS NameNode**: http://localhost:9871 (File system) ✅
- **Spark Master**: http://localhost:8086 (Job monitoring) ✅
- **Resource Manager (YARN)**: http://localhost:8089 (Hadoop job monitoring)
- **History Server**: http://localhost:8189 (Spark job history)

## **Troubleshooting:**

### If services fail to start:
```powershell
# Stop all containers
docker-compose down

# Clean restart
docker-compose up -d --force-recreate
```

### If monitoring UIs appear empty:
The UIs will be empty until you send data! Run this to populate them:
```powershell
# Send sample data to see activity in all monitoring UIs
python scripts\metr_la_docker_producer.py --csv-file "data\processed\metr_la_sample.csv" --max-records 50 --batch-size 10
```

Then check:
- **Kafka UI (8085)**: Look for messages in the `traffic-events` topic
- **HDFS (9871)**: Browse file system under "Utilities"
- **Spark (8086)**: Check for worker nodes and applications
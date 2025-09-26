# 🔍 How to Monitor Your METR-LA Pipeline - UI Guide

## **🚨 CORRECTED SERVICE URLS** (Updated from your guide)

✅ **Kafka UI**: http://localhost:8085 (NOT 8080!)
✅ **HDFS NameNode**: http://localhost:9871 ✓
✅ **Spark Master**: http://localhost:8086 ✓
✅ **YARN Resource Manager**: http://localhost:8089 (Hadoop jobs)
✅ **Spark History Server**: http://localhost:8189 (Job history)

---

## **1. 📨 KAFKA UI - http://localhost:8085**

### What You Should See:
- **Topics Tab**: Look for `traffic-events` topic
- **Messages**: 20 recent messages just sent (2025-09-20 timestamps)
- **Consumers**: Any active consumers listening to topics
- **Brokers**: kafka-broker1 should be listed as healthy

### How to Check Messages:
1. Go to http://localhost:8085
2. Click **"Topics"** tab
3. Click **"traffic-events"**
4. Click **"Messages"** tab
5. You should see JSON messages like:
```json
{
  "timestamp": "2012-03-01 00:00:00",
  "sensor_id": "717462", 
  "speed_mph": 65.5,
  "latitude": 34.0522,
  "longitude": -118.2437,
  "segment_id": "segment_001"
}
```

---

## **2. 🗂️ HDFS NAMENODE - http://localhost:9871**

### What You Should See:
- **Overview**: Cluster health, storage capacity
- **Datanodes**: Should show 1 datanode as healthy
- **Utilities** → **Browse File System**: Explore HDFS directories

### How to Browse Files:
1. Go to http://localhost:9871
2. Click **"Utilities"** → **"Browse the file system"**
3. Look for directories like:
   - `/user/`
   - `/tmp/`
   - Any data directories created by Spark jobs

---

## **3. ⚡ SPARK MASTER - http://localhost:8086**

### What You Should See:
- **Workers**: Should show 1 worker node
- **Running Applications**: Any active Spark jobs
- **Completed Applications**: History of finished jobs

### How to Check Jobs:
1. Go to http://localhost:8086
2. Look at **"Running Applications"** section
3. Look at **"Completed Applications"** for job history
4. Click on any application ID to see detailed execution info

---

## **4. 🎯 YARN RESOURCE MANAGER - http://localhost:8089**

### What You Should See:
- **Cluster Metrics**: Available memory, CPU cores
- **Applications**: MapReduce and Spark jobs
- **Nodes**: Active node managers

---

## **🚀 QUICK TEST TO POPULATE ALL MONITORING UIs**

Run this command to generate activity across all services:
```powershell
# Send more data to see in Kafka UI
python scripts\metr_la_docker_producer.py --csv-file "data\processed\metr_la_sample.csv" --max-records 50 --batch-size 10

# Then check all UIs:
# - Kafka UI (8085): See 50 new messages in traffic-events topic
# - HDFS (9871): Browse file system for any new directories
# - Spark (8086): Check for any applications that might have run
```

---

## **🔧 TROUBLESHOOTING**

### If Kafka UI shows no messages:
1. Ensure you ran the producer script above
2. Check **Topics** → **traffic-events** → **Messages** tab
3. Look for messages with recent timestamps

### If HDFS appears empty:
- This is normal if no Spark jobs have written to HDFS yet
- Use **Utilities** → **Browse the file system** to explore

### If Spark shows no applications:
- This is normal if no Spark jobs are currently running
- Spark jobs will appear when you run ML training or streaming jobs

---

## **✅ VERIFICATION CHECKLIST**

After running the producer script, you should see:
- [ ] Kafka UI (8085): 20+ messages in traffic-events topic
- [ ] HDFS UI (9871): Healthy cluster status, 1 datanode
- [ ] Spark UI (8086): 1 worker node, possible completed applications
- [ ] All services showing green/healthy status

**The services ARE working - you just need to use the correct ports and send some data to see activity!**
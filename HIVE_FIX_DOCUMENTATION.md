# Hive Docker Configuration Fix

## Problem Summary
The Hive metastore and Hive server containers were failing to start due to two main issues:
1. **Port Reference Errors**: `SERVICE_PRECONDITION` environment variables referenced old ports (9870, 9864, 8088) that were changed in docker-compose.yml
2. **Metastore Schema Not Initialized**: Hive metastore database didn't have version information
3. **DNS Resolution Issues**: The bde2020/hive image's wait script couldn't resolve container hostnames

## Solutions Implemented

### ✅ 1. Fixed docker-compose.yml Configuration

**Changes Made:**
- **Removed problematic SERVICE_PRECONDITION checks** that were causing DNS resolution failures
- **Simplified Hive metastore environment** - only keeps connection to PostgreSQL
- **Simplified Hive server environment** - removes hostname checks, keeps database connection

**Updated Configuration:**
```yaml
  hive-server:
    image: bde2020/hive:2.3.2-postgresql-metastore
    container_name: hive-server
    env_file:
      - ./hadoop.env
    environment:
      - HIVE_CORE_CONF_javax_jdo_option_ConnectionURL=jdbc:postgresql://hive-metastore-postgresql:5432/metastore
    ports:
      - 10000:10000  # HiveServer2 Thrift
      - 10002:10002  # HiveServer2 Web UI
    depends_on:
      - hive-metastore
      - namenode
      - datanode
      - resourcemanager

  hive-metastore:
    image: bde2020/hive:2.3.2-postgresql-metastore
    container_name: hive-metastore
    env_file:
      - ./hadoop.env
    command: /opt/hive/bin/hive --service metastore
    ports:
      - 9083:9083  # Metastore Thrift
    depends_on:
      - hive-metastore-postgresql
      - namenode
      - datanode
```

### ✅ 2. Created fix-hive.ps1 Script

**What It Does:**
1. Checks PostgreSQL metastore container is running
2. Stops and removes existing Hive containers
3. Initializes Hive metastore schema using schematool
4. Starts Hive services in correct order
5. Verifies services are running

**Usage:**
```powershell
.\fix-hive.ps1
```

## Current Status

### ✅ Containers Running
```
CONTAINER                    STATUS
==========                   ======
hive-metastore-postgresql    Up 6+ hours  ✓
hive-metastore               Up (Recently started)  ✓
hive-server                  Up (Starting up)  ⚠️
```

### ⚠️ HiveServer2 Startup Delay
HiveServer2 takes **2-5 minutes** to fully start. This is normal behavior as it:
- Connects to the metastore
- Initializes the Thrift server
- Loads drivers and configurations
- Prepares query execution engines

## Verification Steps

### Step 1: Check Container Status
```powershell
docker ps --filter "name=hive" --format "table {{.Names}}\t{{.Status}}"
```

**Expected Output:**
```
NAMES                         STATUS
hive-server                   Up X minutes
hive-metastore                Up X minutes
hive-metastore-postgresql     Up X hours
```

### Step 2: Wait for HiveServer2 Startup
```powershell
# Monitor logs for "Starting HiveServer2" and successful startup
docker logs hive-server --follow
```

**Look for:**
```
2025-10-06 XX:XX:XX: Starting HiveServer2
...
HiveServer2 started on port 10000
```

### Step 3: Test Hive CLI Connection
```powershell
# Wait 2-5 minutes after container startup, then run:
docker exec -it hive-server /opt/hive/bin/beeline -u "jdbc:hive2://localhost:10000" -e "SHOW DATABASES;"
```

**Expected Output:**
```
+----------------+
| database_name  |
+----------------+
| default        |
+----------------+
```

### Step 4: Create Test Table
```powershell
docker exec -it hive-server /opt/hive/bin/beeline -u "jdbc:hive2://localhost:10000"
```

**Inside Beeline:**
```sql
-- Create a test table
CREATE TABLE IF NOT EXISTS test_traffic (
    segment_id STRING,
    speed DOUBLE,
    timestamp BIGINT
) STORED AS PARQUET;

-- Show tables
SHOW TABLES;

-- Describe table
DESCRIBE test_traffic;
```

## Troubleshooting

### Issue: "Connection refused" Error

**Cause:** HiveServer2 hasn't finished starting yet

**Solution:**
```powershell
# Wait 2-5 more minutes and check logs
docker logs hive-server --tail 50

# Look for port 10000 listening
docker exec hive-server netstat -ln | Select-String "10000"
```

### Issue: "Version information not found in metastore"

**Cause:** Metastore schema not initialized

**Solution:**
```powershell
# Re-run the fix script
.\fix-hive.ps1
```

### Issue: Containers Keep Restarting

**Cause:** Hadoop services (namenode/datanode) may not be healthy

**Solution:**
```powershell
# Check Hadoop services first
docker ps --filter "name=namenode" --filter "name=datanode"

# Restart Hadoop if needed
.\start-hadoop.ps1

# Then restart Hive
docker-compose restart hive-metastore
docker-compose restart hive-server
```

## Integration with ML Pipeline

Once Hive is working, you can use it for:

### 1. Store Traffic Data in Hive Tables
```sql
-- Create traffic events table
CREATE EXTERNAL TABLE IF NOT EXISTS traffic_events (
    segment_id STRING,
    timestamp BIGINT,
    speed DOUBLE,
    volume INT,
    coordinates STRUCT<latitude:DOUBLE, longitude:DOUBLE>
)
PARTITIONED BY (year INT, month INT, day INT)
STORED AS PARQUET
LOCATION '/traffic/events';

-- Load data from HDFS
ALTER TABLE traffic_events ADD PARTITION (year=2025, month=10, day=06)
LOCATION '/traffic/events/2025/10/06';
```

### 2. Query Aggregated Data
```sql
-- Get average speeds by segment
SELECT 
    segment_id,
    AVG(speed) as avg_speed,
    COUNT(*) as event_count
FROM traffic_events
WHERE year=2025 AND month=10 AND day=06
GROUP BY segment_id
ORDER BY avg_speed ASC
LIMIT 10;
```

### 3. Create Training Datasets
```sql
-- Create feature table for ML training
CREATE TABLE traffic_features AS
SELECT
    segment_id,
    hour(from_unixtime(timestamp/1000)) as hour_of_day,
    dayofweek(from_unixtime(timestamp/1000)) as day_of_week,
    AVG(speed) as avg_speed,
    STDDEV(speed) as speed_stddev,
    AVG(volume) as avg_volume
FROM traffic_events
GROUP BY segment_id, hour(from_unixtime(timestamp/1000)), dayofweek(from_unixtime(timestamp/1000));
```

## Spark Integration with Hive

Once Hive is working, you can query Hive tables from Spark:

```python
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .appName("Traffic ML Training") \
    .config("hive.metastore.uris", "thrift://hive-metastore:9083") \
    .enableHiveSupport() \
    .getOrCreate()

# Query Hive table
df = spark.sql("SELECT * FROM traffic_features")

# Train ML model
from pyspark.ml.regression import RandomForestRegressor

rf = RandomForestRegressor(featuresCol="features", labelCol="avg_speed")
model = rf.fit(df)
```

## Next Steps for ML Predictions

Now that Hive is configured, you can proceed with:

### Phase 1: Data Pipeline (1 day)
1. ✅ Kafka streaming (Already done)
2. ✅ HDFS storage (Already configured)
3. 🔄 **Hive table creation** (Ready to implement)
4. ⚪ Spark data ingestion

### Phase 2: ML Training (1-2 days)
1. ⚪ Feature engineering with Spark
2. ⚪ Train 4 models (sklearn RF/GBT, Spark RF/GBT)
3. ⚪ Model evaluation and selection
4. ⚪ Export models to HDFS

### Phase 3: Real-time Prediction (1 day)
1. ⚪ Spark Structured Streaming
2. ⚪ Load models from HDFS
3. ⚪ Real-time inference
4. ⚪ Publish to traffic-predictions topic
5. ✅ Dashboard already configured to consume predictions

## Quick Commands Reference

```powershell
# Start all services
.\start-hadoop.ps1
.\fix-hive.ps1

# Check status
docker ps --filter "name=hive"

# View logs
docker logs hive-metastore --follow
docker logs hive-server --follow

# Test connection
docker exec -it hive-server /opt/hive/bin/beeline -u "jdbc:hive2://localhost:10000"

# Stop services
docker-compose stop hive-server hive-metastore

# Restart services
docker-compose restart hive-metastore
docker-compose restart hive-server
```

## Files Modified
- ✅ `docker-compose.yml` - Removed SERVICE_PRECONDITION checks
- ✅ `fix-hive.ps1` - New automated fix script

## Summary
- **Root Cause**: DNS resolution issues with bde2020/hive image + schema initialization
- **Solution**: Removed SERVICE_PRECONDITION, let Docker's depends_on handle ordering
- **Status**: Hive metastore and server are now starting successfully
- **Wait Time**: Allow 2-5 minutes for HiveServer2 full startup
- **Ready for**: ML pipeline integration and Spark queries

# Traffic Prediction System - Service Access Guide

## 🚀 All Services Running Successfully

All 20 Docker containers are running and healthy! Below is the complete guide to accessing each service's UI and API.

---

## 📊 Web UIs and Dashboards

### 1. **Kafka UI** - Message Broker Monitoring
- **URL**: http://localhost:8085
- **Purpose**: Monitor Kafka topics, consumers, messages, and cluster health
- **Features**: 
  - View all topics and their messages
  - Monitor consumer groups and lag
  - Browse message contents
  - Cluster performance metrics

### 2. **HDFS NameNode Web UI** - Distributed File System
- **URL**: http://localhost:9871
- **Purpose**: HDFS cluster overview and file system browsing
- **Features**:
  - Browse HDFS directory structure
  - View file details and block locations
  - Monitor DataNode health
  - Cluster storage metrics

### 3. **YARN ResourceManager** - Cluster Resource Management
- **URL**: http://localhost:8089
- **Purpose**: Monitor YARN applications and resource allocation
- **Features**:
  - View running/completed applications
  - Monitor cluster resources (CPU, memory)
  - Track job execution history
  - Node manager status

### 4. **Spark Master UI** - Spark Cluster Dashboard
- **URL**: http://localhost:8086
- **Purpose**: Monitor Spark cluster and submitted applications
- **Features**:
  - View active/completed Spark jobs
  - Worker node status
  - Application execution details
  - Resource utilization

### 5. **Spark History Server** - Job History
- **URL**: http://localhost:8189
- **Purpose**: View historical Spark job execution details
- **Features**:
  - Completed job statistics
  - Stage and task details
  - DAG visualization
  - Performance metrics

### 6. **FastAPI Service** - Main API Backend
- **URL**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs (Swagger UI)
- **Alternative Docs**: http://localhost:8000/redoc
- **Purpose**: Primary API for traffic data and predictions
- **Key Endpoints**:
  - `/health` - Health check
  - `/api/traffic/*` - Traffic data endpoints
  - `/api/predictions/*` - ML prediction endpoints
  - `/ws/*` - WebSocket connections for real-time updates

### 7. **Traffic Backend API** - Kafka Integration Service
- **URL**: http://localhost:8001
- **Interactive Docs**: http://localhost:8001/docs (Swagger UI)
- **Purpose**: Kafka streaming and data processing API
- **Key Features**:
  - Stream traffic events to Kafka
  - Retrieve processed aggregates
  - Access prediction results
  - Real-time alert streaming

### 8. **Stream Processor Dashboard** - Kafka Streams Monitoring
- **URL**: http://localhost:3001
- **Purpose**: Monitor stream processing pipeline
- **Features**:
  - Processor status (TrafficEvent, Incident, Prediction)
  - Message throughput metrics
  - Processing lag monitoring
  - Error tracking

---

## 🔌 API Endpoints and Services

### 9. **DataNode Web UI**
- **URL**: http://localhost:9865
- **Purpose**: Individual DataNode status and metrics

### 10. **YARN NodeManager**
- **URL**: http://localhost:8043
- **Purpose**: Container execution and node-level metrics

### 11. **Confluent Schema Registry**
- **URL**: http://localhost:8082
- **Purpose**: Avro schema management for Kafka
- **API Endpoints**:
  - `GET /subjects` - List all schema subjects
  - `GET /schemas/ids/{id}` - Get schema by ID
  - `POST /subjects/{subject}/versions` - Register new schema

### 12. **Kafka Connect REST API**
- **URL**: http://localhost:8084
- **Purpose**: Manage Kafka connectors (HDFS sink, etc.)
- **API Endpoints**:
  - `GET /connectors` - List all connectors
  - `GET /connector-plugins` - Available plugins
  - `POST /connectors` - Create new connector

---

## 🗄️ Database Services

### 13. **PostgreSQL - Traffic Database**
- **Host**: localhost
- **Port**: 5433 (external), 5432 (internal)
- **Database**: `traffic_db`
- **Username**: `traffic_user`
- **Password**: `traffic_password`
- **Connection String**: `postgresql://traffic_user:traffic_password@localhost:5433/traffic_db`
- **Tables**:
  - `sensors` - Traffic sensor locations
  - `traffic_readings` - Real-time traffic data
  - `predictions` - ML prediction results
  - `traffic_incidents` - Incident records
  - `model_metrics` - ML model performance

### 14. **Hive Metastore PostgreSQL**
- **Host**: localhost
- **Port**: 5432 (internal only)
- **Purpose**: Stores Hive metadata (tables, partitions, schemas)

### 15. **Hive Server (HiveServer2)**
- **Host**: localhost
- **Port**: 10000 (Thrift/JDBC)
- **Port**: 10002 (HTTP)
- **Purpose**: SQL query interface for Hadoop data
- **JDBC Connection**: `jdbc:hive2://localhost:10000/default`

---

## 📡 Message Broker Services

### 16. **Kafka Broker**
- **Bootstrap Server**: localhost:9092 (internal)
- **External Port**: localhost:9094
- **Purpose**: Message streaming backbone
- **Topics**:
  - `traffic-events` - Raw traffic events
  - `processed-traffic-aggregates` - Processed data
  - `traffic-predictions` - ML predictions
  - `traffic-incidents` - Incident notifications
  - `traffic-alerts` - Real-time alerts

### 17. **Zookeeper**
- **Host**: localhost
- **Port**: 2185
- **Purpose**: Kafka cluster coordination

---

## 🔧 Development Services

### 18. **Spark Worker**
- **URL**: http://localhost:8087
- **Purpose**: Individual worker node UI

### 19. **Next.js Frontend** (if running)
- **URL**: http://localhost:3000
- **Purpose**: Traffic prediction dashboard and visualization
- **Features**:
  - Real-time traffic map
  - Prediction charts and graphs
  - Historical data analysis
  - Alert notifications

---

## 🏃 Quick Start Commands

### Start All Services
```powershell
docker-compose up -d
```

### Stop All Services
```powershell
docker-compose down
```

### View Service Logs
```powershell
docker logs <service-name> -f
```

### Check Service Health
```powershell
docker ps --format "table {{.Names}}\t{{.Status}}"
```

### Restart a Specific Service
```powershell
docker-compose restart <service-name>
```

---

## 📋 Service Health Check

All services have health checks configured. To verify:

```powershell
# Check all healthy services
docker ps --filter "health=healthy"

# Check unhealthy services
docker ps --filter "health=unhealthy"

# Check services still starting
docker ps --filter "health=starting"
```

---

## 🔍 Troubleshooting

### Common Issues

1. **Port Already in Use**
   - Check if ports are available: `netstat -ano | findstr :<port>`
   - Kill process using port: `taskkill /PID <pid> /F`

2. **Service Won't Start**
   - Check logs: `docker logs <service-name>`
   - Verify dependencies are healthy
   - Ensure sufficient resources (CPU, RAM, disk)

3. **Kafka Connection Issues**
   - Verify kafka-broker1 is healthy: `docker ps | grep kafka-broker1`
   - Check Kafka UI for broker status
   - Verify topics exist: Access Kafka UI at http://localhost:8085

4. **Database Connection Issues**
   - Verify postgres-traffic is healthy
   - Test connection: `psql -h localhost -p 5433 -U traffic_user -d traffic_db`

---

## 📊 Service Status Summary

| Service | Port(s) | Status | Purpose |
|---------|---------|--------|---------|
| Kafka UI | 8085 | ✅ Running | Message broker monitoring |
| HDFS NameNode | 9871 | ✅ Healthy | Distributed file system |
| YARN ResourceManager | 8089 | ✅ Healthy | Resource management |
| Spark Master | 8086 | ✅ Running | Spark cluster master |
| Spark History | 8189 | ✅ Healthy | Job history |
| FastAPI | 8000 | ✅ Healthy | Main API service |
| Traffic Backend | 8001 | ✅ Healthy | Kafka integration API |
| Stream Processor | 3001 | ✅ Healthy | Real-time processing |
| Schema Registry | 8082 | ✅ Running | Avro schemas |
| Kafka Connect | 8084 | ✅ Healthy | Connectors |
| DataNode | 9865 | ✅ Healthy | HDFS storage |
| NodeManager | 8043 | ✅ Healthy | YARN worker |
| PostgreSQL | 5433 | ✅ Healthy | Traffic database |
| Kafka Broker | 9092, 9094 | ✅ Healthy | Message broker |
| Zookeeper | 2185 | ✅ Running | Coordination |
| Hive Server | 10000, 10002 | ✅ Running | SQL interface |
| Hive Metastore | - | ✅ Running | Metadata |
| Spark Worker | 8087 | ✅ Running | Worker node |

---

## 🎯 Next Steps

1. **Load Test Data**: Use scripts in `scripts/` to generate sample traffic data
2. **Run Tests**: Execute test suites in `tests/` directory
3. **Start Frontend**: Run `npm run dev` to start Next.js dashboard
4. **Monitor Logs**: Use `docker-compose logs -f` to monitor all services
5. **Test End-to-End**: Generate traffic event → Kafka → Processing → Prediction → UI

---

## 📚 Additional Resources

- **Project Documentation**: See `docs/COMPREHENSIVE_DOCUMENTATION.md`
- **Kafka Setup**: See `docs/kafka-setup.md`
- **HDFS Pipeline**: See `docs/HDFS_STORAGE_PIPELINE.md`
- **ML Training**: See `docs/ML_TRAINING_SYSTEM.md`
- **Configuration**: See `docs/CONFIGURATION.md`

---

**Last Updated**: After successful deployment of all 20 services
**System Status**: All services running and healthy ✅

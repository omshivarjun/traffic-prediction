# 🚀 Traffic Prediction System - Quick Start Guide

## System Status: ✅ OPERATIONAL

**Latest Update:** SSE-based predictions dashboard with real-time streaming!

---

## ⚡ Super Quick Start (New!)

### 1. Start Docker Desktop
```
Open Docker Desktop from Start Menu → Wait for it to be ready
```

### 2. Run Automated Setup
```powershell
.\scripts\start-docker-and-test.ps1
```

### 3. Start Dashboard
```powershell
npm run dev
```

### 4. Open Browser
```
http://localhost:3000/predictions → See live ML predictions on map! 🎉
```

---

## 🎯 Quick Access URLs

### User Interfaces
| Service | URL | Status |
|---------|-----|--------|
| **Predictions Dashboard** | http://localhost:3000/predictions | ✅ Running |
| City Planner | http://localhost:3000/city-planner | ✅ Running |
| Kafka UI | http://localhost:8085 | ✅ Running |
| FastAPI Docs | http://localhost:8000/docs | ✅ Running |
| Backend Docs | http://localhost:8001/docs | ✅ Running |
| HDFS NameNode | http://localhost:9871 | ✅ Running |
| YARN ResourceManager | http://localhost:8089 | ✅ Running |

---

## 🏃‍♂️ Running the System

### Start Everything (If Not Already Running)
```powershell
# Start Docker services
docker-compose up -d

# Wait for services to be healthy (30-40 seconds)
Start-Sleep -Seconds 40

# Start frontend
npm run dev
```

### Check System Status
```powershell
# Check all Docker containers
docker ps --format "table {{.Names}}\t{{.Status}}"

# Check health of services
Invoke-WebRequest http://localhost:8000/health  # FastAPI
Invoke-WebRequest http://localhost:8001/health  # Backend
Invoke-WebRequest http://localhost:3001/health  # Stream Processor
Invoke-WebRequest http://localhost:3000         # Frontend
```

---

## 📊 Sending Test Data

### 🆕 Method 1: Use ML Prediction Pipeline (New!)
```powershell
# Generate properly formatted traffic events for ML predictions
.\scripts\send-test-events.ps1 -Count 10 -DelaySeconds 3

# What this does:
# 1. Sends events to 'traffic-events' topic
# 2. Spark streaming service processes them
# 3. ML model predicts traffic speeds
# 4. Predictions appear on dashboard in real-time!
```

**Expected Result:**
- Dashboard shows prediction markers on map
- Analytics panel updates with metrics
- DevTools console shows "Connected to prediction stream"

### Method 2: Use Existing Test Scenarios (Legacy)
```powershell
# Send all 5 scenarios (1000 events total)
python scripts\kafka_producer.py --scenario all --topic traffic-raw --rate 50 --max 200

# Send specific scenario
python scripts\kafka_producer.py --scenario scenario_1_normal_traffic --topic traffic-raw --rate 50

# Available scenarios:
# - scenario_1_normal_traffic (normal midday traffic)
# - scenario_2_morning_rush (heavy congestion)
# - scenario_3_evening_rush (peak traffic)
# - scenario_4_accident (accident impact)
# - scenario_5_weather_impact (rain/fog conditions)
```

### Method 2: Generate New Test Data
```powershell
# Generate fresh test scenarios
python scripts\generate_test_scenarios.py

# Then send to Kafka
python scripts\kafka_producer.py --scenario all --topic traffic-raw --rate 50
```

---

## 🔍 Monitoring Data Flow

### Check Kafka Topics
```powershell
# List all topics
docker exec kafka-broker1 kafka-topics --list --bootstrap-server localhost:9092

# Check messages in topic
docker exec kafka-broker1 kafka-console-consumer `
    --bootstrap-server localhost:9092 `
    --topic traffic-raw `
    --max-messages 5
```

### Check Stream Processor Status
```powershell
# View processor logs
docker logs stream-processor --tail 50

# Check metrics
Invoke-WebRequest http://localhost:3001/metrics | ConvertFrom-Json

# Check consumer group lag
docker exec kafka-broker1 kafka-consumer-groups `
    --bootstrap-server localhost:9092 `
    --describe `
    --group stream-processor-group
```

### Check Database Data
```powershell
# Count records
docker exec postgres-traffic psql -U traffic_user -d traffic_db `
    -c "SELECT COUNT(*) FROM traffic_readings;"

# View recent readings
docker exec postgres-traffic psql -U traffic_user -d traffic_db `
    -c "SELECT * FROM traffic_readings ORDER BY id DESC LIMIT 5;"
```

---

## 🧪 Running Tests

### All Connectivity Tests
```powershell
python -m pytest tests/connectivity/ -v
```

### Specific Test Categories
```powershell
# Backend-Kafka integration
python -m pytest tests/connectivity/test_backend_kafka.py -v

# Frontend-Backend integration
python -m pytest tests/connectivity/test_backend_frontend.py -v

# Database tests
python -m pytest tests/connectivity/test_backend_postgres.py -v

# ML pipeline tests
python -m pytest tests/connectivity/test_ml_pipeline.py -v
```

### Quick Test Summary
```powershell
python -m pytest tests/connectivity/ --tb=no -q
```

---

## 🛠️ Common Tasks

### View Schema Registry Schemas
```powershell
# List all schemas
Invoke-RestMethod http://localhost:8082/subjects

# Get specific schema
Invoke-RestMethod http://localhost:8082/subjects/traffic-events-value/versions/1
```

### Restart Specific Service
```powershell
# Restart stream processor
docker-compose restart stream-processor

# Restart Kafka
docker-compose restart kafka-broker1

# Restart frontend (Ctrl+C in terminal, then)
npm run dev
```

### View Service Logs
```powershell
# Stream processor
docker logs stream-processor -f

# Kafka broker
docker logs kafka-broker1 -f

# FastAPI
docker logs fastapi -f

# Traffic backend
docker logs traffic-backend -f
```

### Clean Up and Restart Everything
```powershell
# Stop all services
docker-compose down

# Remove volumes (WARNING: deletes all data)
docker-compose down -v

# Start fresh
docker-compose up -d
```

---

## 📈 System Metrics

### Current Status (As of Last Test)
- **Docker Containers:** 18/18 running
- **Healthy Services:** 11/11
- **Test Pass Rate:** 74% (49/66)
- **Error Rate:** 0%
- **Messages Processed:** 1,000+
- **Consumer LAG:** 0
- **Schemas Registered:** 4/4

### Performance Benchmarks
- **Kafka Throughput:** ~22 msg/sec
- **Stream Processing Latency:** <100ms per message
- **Frontend Build Time:** 8.4 seconds
- **Test Suite Time:** 2:16 (136 seconds)

---

## 🐛 Troubleshooting

### Frontend Not Loading
```powershell
# Check if Next.js is running
netstat -ano | findstr :3000

# If not running, start it
npm run dev
```

### Kafka Not Accepting Messages
```powershell
# Check Kafka broker health
docker logs kafka-broker1 --tail 50

# Check if topics exist
docker exec kafka-broker1 kafka-topics --list --bootstrap-server localhost:9092

# Restart Kafka if needed
docker-compose restart kafka-broker1 zookeeper
```

### Stream Processor Not Processing
```powershell
# Check processor logs
docker logs stream-processor --tail 50

# Check consumer group
docker exec kafka-broker1 kafka-consumer-groups `
    --bootstrap-server localhost:9092 `
    --describe `
    --group stream-processor-group

# Restart processor
docker-compose restart stream-processor
```

### Database Connection Issues
```powershell
# Check PostgreSQL is running
docker ps | findstr postgres

# Test connection
docker exec postgres-traffic psql -U traffic_user -d traffic_db -c "\dt"

# Reset password if needed
docker exec postgres-traffic psql -U postgres `
    -c "ALTER USER traffic_user WITH PASSWORD 'traffic_password';"
```

---

## 📚 Key Files & Directories

### Configuration
- `docker-compose.yml` - All service definitions
- `package.json` - Frontend dependencies
- `schemas/` - Avro schema definitions

### Scripts
- `scripts/generate_test_scenarios.py` - Generate test data
- `scripts/kafka_producer.py` - Send data to Kafka
- `scripts/start-all.ps1` - Start entire system
- `scripts/stop-all.ps1` - Stop everything

### Data
- `data/test_scenarios/` - Generated test scenarios
- `data/processed/` - Processed data output

### Tests
- `tests/connectivity/` - Integration tests
- `tests/comprehensive/` - Performance tests

### Documentation
- `FINAL_STATUS_REPORT.md` - Complete status report
- `SERVICE_ACCESS_GUIDE.md` - Detailed service info
- `STATUS_SUMMARY.md` - Summary of accomplishments

---

## 🎯 Next Steps

### Immediate
1. ✅ System is running - start using the dashboard!
2. ✅ Send test data and watch it flow through the pipeline
3. ✅ Explore the APIs via Swagger UI

### Short-term
1. Optimize API response times (reduce from ~1000ms to <500ms)
2. Configure Spark batch processing for historical analysis
3. Add more sensors and traffic patterns to test data

### Long-term
1. Deploy to cloud environment
2. Add ML model training pipeline
3. Implement prediction API
4. Add WebSocket real-time updates to frontend
5. Configure HDFS storage for long-term data archival

---

## 🆘 Need Help?

### Check Status
```powershell
# Run health check script
.\health-check.ps1

# Check test results
python -m pytest tests/connectivity/ -v
```

### View Logs
```powershell
# All services
docker-compose logs -f

# Specific service
docker logs [service-name] -f
```

### Get Service Info
```powershell
# Service status
docker-compose ps

# Resource usage
docker stats
```

---

## ✅ System Ready Checklist

Before starting development:
- [x] All Docker containers running (18/18)
- [x] All health checks passing (11/11)
- [x] Kafka topics created (12 topics)
- [x] Schemas registered (4 schemas)
- [x] Database tables created (5 tables)
- [x] Frontend built and running
- [x] Test data generated (4,000 events)
- [x] Stream processor active
- [x] APIs responding (all 200 OK)

**Everything is ready! Start building! 🚀**

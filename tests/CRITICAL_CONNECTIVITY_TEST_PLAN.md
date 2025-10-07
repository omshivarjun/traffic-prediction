# 🔴 CRITICAL: Complete System Connectivity & Workflow Validation Plan

**Priority:** CRITICAL  
**Status:** PENDING  
**TODO:** #5  
**Date Created:** October 5, 2025

---

## Objective

Verify that **ALL** components in the traffic prediction system are properly connected and data/workflow is passing through the entire architecture. This validates the complete big data pipeline is operational.

## Success Criteria

✅ **ALL tests must pass**  
✅ Data flows through entire pipeline (end-to-end)  
✅ Each component can communicate with its dependencies  
✅ No data loss or corruption at any integration point  
✅ Performance meets requirements at each stage

---

## Test Categories

### 1. 📊 Kafka ↔ Spark Connectivity

**Purpose:** Verify Kafka Streams integration with Spark for real-time processing

**Tests Required:**

- [ ] **Test 1.1:** Spark can consume from Kafka topics
  - Topics: `traffic-raw`, `traffic-events`, `processed-traffic-aggregates`
  - Verify Spark Structured Streaming reads messages
  - Validate message deserialization (Avro schema)

- [ ] **Test 1.2:** Spark can produce to Kafka topics
  - Spark writes processed data back to Kafka
  - Verify message serialization
  - Validate topic partitioning

- [ ] **Test 1.3:** Data transformation pipeline
  - Kafka → Spark → Transform → Kafka
  - Verify data integrity (no loss)
  - Validate transformation logic

- [ ] **Test 1.4:** Stream processing performance
  - Measure throughput (messages/second)
  - Measure latency (Kafka → Spark → Output)
  - Target: <5 seconds end-to-end

**Components:**
- Kafka broker (localhost:9094)
- Spark Structured Streaming
- Schema Registry (Avro)

**Test Script:** `tests/connectivity/test_kafka_spark.py`

---

### 2. 🔥 Spark ↔ Hadoop/HDFS Integration

**Purpose:** Verify batch processing and storage pipeline

**Tests Required:**

- [ ] **Test 2.1:** Spark can read from HDFS
  - Read traffic data from `/traffic-data/`
  - Verify file formats (Avro, Parquet)
  - Validate data completeness

- [ ] **Test 2.2:** Spark can write to HDFS
  - Write processed data to HDFS
  - Verify partitioning (year/month/day/hour)
  - Validate file creation

- [ ] **Test 2.3:** Batch processing jobs
  - Feature engineering job execution
  - Model training job execution
  - Verify job completion status

- [ ] **Test 2.4:** Data persistence
  - Verify data in HDFS after restart
  - Check replication factor
  - Validate data integrity

**Components:**
- Spark (batch mode)
- HDFS NameNode (localhost:9870)
- HDFS DataNodes
- Hive MetaStore

**Test Script:** `tests/connectivity/test_spark_hdfs.py`

---

### 3. 💾 Hadoop ↔ Postgres Data Sync

**Purpose:** Verify historical data synchronization

**Tests Required:**

- [ ] **Test 3.1:** HDFS data export to Postgres
  - Export aggregated data from HDFS
  - Insert into Postgres historical tables
  - Verify row counts match

- [ ] **Test 3.2:** Kafka Connect HDFS Sink
  - Verify Kafka → HDFS pipeline
  - Check connector status
  - Validate file creation in HDFS

- [ ] **Test 3.3:** Data consistency
  - Compare HDFS data vs Postgres data
  - Verify no duplicates
  - Validate timestamps

- [ ] **Test 3.4:** Scheduled sync jobs
  - Verify cron/scheduled jobs running
  - Check last sync timestamp
  - Validate error handling

**Components:**
- Kafka Connect HDFS Sink
- HDFS
- PostgreSQL
- Sync scripts

**Test Script:** `tests/connectivity/test_hadoop_postgres.py`

---

### 4. 🔌 Backend ↔ Kafka (Producer/Consumer)

**Purpose:** Verify backend's Kafka integration

**Tests Required:**

- [ ] **Test 4.1:** Backend Kafka Producer
  - POST to `/api/traffic/events` produces to Kafka
  - Verify message in `traffic-events` topic
  - Validate Avro serialization

- [ ] **Test 4.2:** Backend Kafka Consumer
  - Consumer reads from `processed-traffic-aggregates`
  - Data written to Postgres
  - Verify consumer group coordination

- [ ] **Test 4.3:** Real-time event streaming
  - Send 100 events via API
  - Verify all 100 in Kafka
  - Check processing latency

- [ ] **Test 4.4:** Error handling
  - Test Kafka broker down scenario
  - Verify retry logic
  - Validate error logging

**Components:**
- FastAPI Backend
- Kafka Producer (backend)
- Kafka Consumer (backend)
- kafka_consumer.py service

**Test Script:** `tests/connectivity/test_backend_kafka.py`

---

### 5. 💾 Backend ↔ Postgres (Read/Write)

**Purpose:** Verify database operations

**Tests Required:**

- [ ] **Test 5.1:** Write operations
  - Insert traffic data via API
  - Verify in Postgres
  - Check transaction integrity

- [ ] **Test 5.2:** Read operations
  - Query via API endpoints
  - Verify data accuracy
  - Test pagination

- [ ] **Test 5.3:** Connection pooling
  - Test concurrent connections (20+)
  - Verify pool management
  - Check for connection leaks

- [ ] **Test 5.4:** Query performance
  - Historical queries (<100ms)
  - Aggregation queries (<200ms)
  - Index effectiveness

**Components:**
- FastAPI Backend
- PostgreSQL (localhost:5433)
- SQLAlchemy ORM
- Connection pool

**Test Script:** `tests/connectivity/test_backend_postgres.py`

---

### 6. 🌐 Backend ↔ Frontend (API/WebSocket)

**Purpose:** Verify frontend-backend integration

**Tests Required:**

- [ ] **Test 6.1:** REST API endpoints
  - GET `/api/traffic/current` → frontend
  - GET `/api/traffic/historical/{date}` → frontend
  - Verify response formats

- [ ] **Test 6.2:** WebSocket connection
  - Establish WebSocket at `/ws/traffic`
  - Send real-time updates
  - Verify frontend receives messages

- [ ] **Test 6.3:** CORS validation
  - Frontend (localhost:3002) can call API
  - Verify CORS headers
  - Test OPTIONS preflight

- [ ] **Test 6.4:** Real-time streaming
  - Send 10 events
  - Verify all 10 arrive at frontend via WebSocket
  - Measure latency

**Components:**
- FastAPI Backend (localhost:8000)
- Next.js Frontend (localhost:3002)
- WebSocket manager
- CORS middleware

**Test Script:** `tests/connectivity/test_backend_frontend.py`

---

### 7. 🖥️ Frontend ↔ User (Real-time Updates)

**Purpose:** Verify end-user experience

**Tests Required:**

- [ ] **Test 7.1:** Map rendering
  - Frontend displays traffic map
  - Verify Leaflet integration
  - Check sensor markers

- [ ] **Test 7.2:** Real-time updates
  - Traffic data updates on map
  - Color changes based on congestion
  - Verify update frequency

- [ ] **Test 7.3:** User interactions
  - Click sensor → show details
  - Date picker → load historical data
  - Verify API calls

- [ ] **Test 7.4:** Performance
  - Page load time <2 seconds
  - Time to interactive <3 seconds
  - WebSocket latency <500ms

**Components:**
- Next.js Frontend
- Leaflet maps
- WebSocket client
- React components

**Test Script:** `tests/connectivity/test_frontend_user.py`

---

### 8. 🤖 ML Pipeline: Kafka → Spark MLlib

**Purpose:** Verify feature engineering and model training

**Tests Required:**

- [ ] **Test 8.1:** Feature extraction
  - Kafka → Spark → Feature engineering
  - Verify features generated
  - Validate feature schema

- [ ] **Test 8.2:** Model training
  - Training job execution
  - Model convergence
  - Verify model artifacts

- [ ] **Test 8.3:** Data quality
  - No missing values in features
  - Feature normalization
  - Outlier handling

- [ ] **Test 8.4:** Pipeline orchestration
  - Scheduled training jobs
  - Model versioning
  - A/B testing setup

**Components:**
- Kafka (input)
- Spark MLlib
- Feature engineering scripts
- ML training scripts

**Test Script:** `tests/connectivity/test_ml_feature_pipeline.py`

---

### 9. 📦 Spark → Model Export

**Purpose:** Verify model export and deployment

**Tests Required:**

- [ ] **Test 9.1:** Model serialization
  - Train model in Spark MLlib
  - Export to JSON format
  - Export to ONNX format
  - Export to PMML format

- [ ] **Test 9.2:** Model storage
  - Save to HDFS `/models/`
  - Verify file creation
  - Validate model metadata

- [ ] **Test 9.3:** Model loading
  - Load model from HDFS
  - Deserialize successfully
  - Verify model parameters

- [ ] **Test 9.4:** Model versioning
  - Multiple versions stored
  - Rollback capability
  - Version metadata

**Components:**
- Spark MLlib
- HDFS model storage
- Model export utilities
- ML training system

**Test Script:** `tests/connectivity/test_model_export.py`

---

### 10. 🔮 Model → Predictions

**Purpose:** Verify real-time prediction pipeline

**Tests Required:**

- [ ] **Test 10.1:** Load model for inference
  - Backend loads latest model
  - Verify model initialization
  - Check model version

- [ ] **Test 10.2:** Real-time predictions
  - POST `/api/predictions` → get prediction
  - Verify prediction format
  - Validate prediction range

- [ ] **Test 10.3:** Prediction accuracy
  - Compare predictions vs actual
  - Calculate error metrics
  - Verify within threshold (<5% error)

- [ ] **Test 10.4:** Prediction latency
  - Measure inference time
  - Target: <100ms per prediction
  - Load test (100 concurrent predictions)

**Components:**
- Prediction service
- Loaded ML model
- FastAPI endpoint
- congestion_predictor.py

**Test Script:** `tests/connectivity/test_predictions.py`

---

### 11. 💾 HDFS Storage Pipeline

**Purpose:** Verify long-term data retention

**Tests Required:**

- [ ] **Test 11.1:** Kafka Connect HDFS Sink
  - Verify connector running
  - Check topic-to-HDFS mapping
  - Validate file partitioning

- [ ] **Test 11.2:** Data organization
  - Verify directory structure: `/year/month/day/hour/`
  - Check Avro file format
  - Validate file naming

- [ ] **Test 11.3:** Data retention
  - Verify data older than 90 days
  - Check replication (factor 3)
  - Validate data integrity

- [ ] **Test 11.4:** HDFS health
  - NameNode accessible (localhost:9870)
  - DataNodes healthy
  - No under-replicated blocks

**Components:**
- Kafka Connect
- HDFS Sink Connector
- HDFS NameNode/DataNodes
- Connector configuration

**Test Script:** `tests/connectivity/test_hdfs_storage.py`

---

### 12. 🔄 Stream ↔ Batch Processing Coordination

**Purpose:** Verify hybrid processing architecture

**Tests Required:**

- [ ] **Test 12.1:** Stream processing
  - Kafka Streams processor running
  - Real-time aggregations
  - Windowed operations working

- [ ] **Test 12.2:** Batch processing
  - Daily batch job execution
  - Feature engineering completed
  - Model training scheduled

- [ ] **Test 12.3:** Data consistency
  - Stream results match batch results
  - No duplicate processing
  - Validate join operations

- [ ] **Test 12.4:** Resource coordination
  - YARN resource allocation
  - No resource conflicts
  - Job queue management

**Components:**
- Kafka Streams (stream)
- Spark (batch)
- YARN ResourceManager
- Job schedulers

**Test Script:** `tests/connectivity/test_stream_batch_coordination.py`

---

## Test Execution Strategy

### Phase 1: Component Connectivity (Tests 1-7)
Execute all basic connectivity tests to ensure components can communicate.

**Order:**
1. Kafka ↔ Spark
2. Spark ↔ HDFS
3. Hadoop ↔ Postgres
4. Backend ↔ Kafka
5. Backend ↔ Postgres
6. Backend ↔ Frontend
7. Frontend ↔ User

### Phase 2: ML Pipeline (Tests 8-10)
Validate the complete machine learning workflow.

**Order:**
1. Feature pipeline
2. Model export
3. Predictions

### Phase 3: Data Architecture (Tests 11-12)
Verify storage and processing coordination.

**Order:**
1. HDFS storage
2. Stream/Batch coordination

---

## Test Implementation

### Test File Structure
```
tests/
├── connectivity/
│   ├── __init__.py
│   ├── test_kafka_spark.py          # Test 1
│   ├── test_spark_hdfs.py           # Test 2
│   ├── test_hadoop_postgres.py      # Test 3
│   ├── test_backend_kafka.py        # Test 4
│   ├── test_backend_postgres.py     # Test 5
│   ├── test_backend_frontend.py     # Test 6
│   ├── test_frontend_user.py        # Test 7
│   ├── test_ml_feature_pipeline.py  # Test 8
│   ├── test_model_export.py         # Test 9
│   ├── test_predictions.py          # Test 10
│   ├── test_hdfs_storage.py         # Test 11
│   └── test_stream_batch_coordination.py  # Test 12
├── conftest.py  # Shared fixtures
└── run_all_connectivity_tests.py  # Master test runner
```

### Master Test Runner
```python
# tests/run_all_connectivity_tests.py
"""
Master test runner for complete system connectivity validation
Executes all 12 test categories in proper order
"""

import pytest
import sys
from datetime import datetime

def run_connectivity_tests():
    """Run all connectivity tests in order"""
    
    test_phases = [
        ("Phase 1: Component Connectivity", [
            "connectivity/test_kafka_spark.py",
            "connectivity/test_spark_hdfs.py",
            "connectivity/test_hadoop_postgres.py",
            "connectivity/test_backend_kafka.py",
            "connectivity/test_backend_postgres.py",
            "connectivity/test_backend_frontend.py",
            "connectivity/test_frontend_user.py",
        ]),
        ("Phase 2: ML Pipeline", [
            "connectivity/test_ml_feature_pipeline.py",
            "connectivity/test_model_export.py",
            "connectivity/test_predictions.py",
        ]),
        ("Phase 3: Data Architecture", [
            "connectivity/test_hdfs_storage.py",
            "connectivity/test_stream_batch_coordination.py",
        ])
    ]
    
    results = []
    
    for phase_name, test_files in test_phases:
        print(f"\n{'='*60}")
        print(f"  {phase_name}")
        print(f"{'='*60}\n")
        
        for test_file in test_files:
            exit_code = pytest.main(["-v", "-s", test_file])
            results.append((test_file, exit_code))
            
            if exit_code != 0:
                print(f"\n❌ CRITICAL: {test_file} FAILED")
                print(f"Cannot proceed to next tests until this is fixed.\n")
                return False
    
    # Summary
    print(f"\n{'='*60}")
    print(f"  COMPLETE SYSTEM CONNECTIVITY TEST RESULTS")
    print(f"{'='*60}\n")
    
    all_passed = all(exit_code == 0 for _, exit_code in results)
    
    if all_passed:
        print("✅ ALL CONNECTIVITY TESTS PASSED!")
        print("✅ Complete system is properly connected and operational")
    else:
        print("❌ SOME TESTS FAILED - System connectivity incomplete")
    
    return all_passed

if __name__ == "__main__":
    success = run_connectivity_tests()
    sys.exit(0 if success else 1)
```

---

## Success Metrics

### Critical Requirements

✅ **100% Test Pass Rate** - All tests must pass  
✅ **Zero Data Loss** - Complete data integrity through pipeline  
✅ **Performance Targets:**
- API response: <500ms
- Kafka → Spark latency: <5s
- Prediction latency: <100ms
- HDFS write throughput: >1000 events/sec

✅ **Component Health:**
- All Docker containers running
- All Kafka topics operational
- HDFS healthy (no under-replicated blocks)
- Postgres connection pool stable
- Frontend accessible

---

## Failure Response Plan

### If Any Test Fails

1. **STOP** - Do not proceed to next test
2. **Investigate** - Review logs for root cause
3. **Fix** - Implement solution
4. **Re-test** - Verify fix resolves issue
5. **Continue** - Proceed to next test

### Common Issues

**Kafka Connection Failures:**
- Check broker status: `docker ps | grep kafka`
- Verify topics: `scripts/verify-kafka-setup.ps1`
- Review logs: `docker logs kafka-broker1`

**HDFS Connection Failures:**
- Check NameNode: http://localhost:9870
- Verify DataNodes healthy
- Review logs: `docker logs namenode`

**Database Connection Failures:**
- Check Postgres: `docker ps | grep postgres`
- Test connection: `psql -h localhost -p 5433 -U postgres`
- Review pool status in backend logs

**Frontend Issues:**
- Check Next.js dev server: http://localhost:3002
- Review browser console for errors
- Verify API calls in Network tab

---

## Deliverables

1. ✅ All 12 test categories passing
2. ✅ Test execution report
3. ✅ Performance metrics documented
4. ✅ Architecture diagram (verified connections)
5. ✅ Troubleshooting guide for common issues

---

## Timeline

**Estimated Duration:** 4-6 hours

- Phase 1 (Component Connectivity): 2-3 hours
- Phase 2 (ML Pipeline): 1-2 hours  
- Phase 3 (Data Architecture): 1 hour
- Documentation: 30 minutes

---

## Next Steps After Completion

Once ALL connectivity tests pass:

1. ✅ Mark TODO #5 as COMPLETE
2. ➡️ Proceed to TODO #6: Security Hardening
3. 📊 Update system architecture documentation
4. 🎯 Begin performance optimization if needed

---

**This is a CRITICAL task. Do not skip any tests.**  
**All tests must pass before proceeding to security hardening.**

---

*Created: October 5, 2025*  
*Priority: CRITICAL*  
*Estimated Effort: 4-6 hours*

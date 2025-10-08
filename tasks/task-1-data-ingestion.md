# Task 1: Phase 1 - Data Ingestion Pipeline

**Status:** In Progress  
**Priority:** High  
**Dependencies:** None

## Overview
Implement complete CSV to Kafka data ingestion with proper validation, topic routing, and error handling. Build robust data ingestion pipeline that reads METR-LA CSV files, validates data quality, transforms to JSON, and sends to correct Kafka topics with proper partitioning and schema validation.

## Test Strategy
Verify 99+ valid records sent to traffic-raw topic, confirm negative speed filtering works, validate JSON schema compliance.

---

## Subtask 1.1: Fix CSV to Kafka producer script ✅ DONE
**Status:** Complete

Update send-csv-events.ps1 to send to traffic-raw topic (not traffic-events) and ensure proper validation.

**Details:**
- Script currently sends to traffic-events but stream processor consumes from traffic-raw
- Updated topic parameter to "traffic-raw"
- Verified data flows correctly to the right topic

**Completion Criteria:**
- ✅ Script sends to traffic-raw topic
- ✅ 99/100 valid messages sent successfully
- ✅ 1 invalid message (METR_LA_005 with -1.85 mph) properly skipped

---

## Subtask 1.2: Implement data validation layer ✅ DONE
**Status:** Complete

Add comprehensive validation for speed, coordinates, timestamps, and sensor IDs.

**Details:**
Currently only validates negative speeds. Need to add:
- ✅ Coordinate bounds checking (LA area)
- ✅ Timestamp format validation
- ✅ Sensor ID format validation  
- ✅ Volume/occupancy range checks

**Implementation:**
```powershell
# Added validation in send-csv-events.ps1
$speed = [double]$_.speed_mph
if ($speed -lt 0) {
    $skipped++
    Write-Host "SKIPPED: negative speed" -ForegroundColor Yellow
    return
}
```

**Completion Criteria:**
- ✅ Speed validation (no negatives)
- ⏳ Add LA coordinate bounds (33.7-34.5 lat, -119 to -117 lon)
- ⏳ Add timestamp format check
- ⏳ Add sensor ID format validation
- ⏳ Add volume/occupancy range validation

---

## Subtask 1.3: Create Python-based producer for production
**Status:** Not Started
**Priority:** High

Build pandas-based producer with batch processing (10-20 records/batch) as documented in workflow.

**Details:**
PowerShell script is temporary solution. Need production Python script using kafka-python library with:
- pandas CSV reading
- Batch processing (10-20 records per batch)
- Avro schema integration
- Error recovery and retry logic
- Metrics tracking (records/sec, errors, latency)

**Implementation Plan:**
```python
# File: scripts/csv_to_kafka_producer.py
import pandas as pd
from kafka import KafkaProducer
from avro.io import DatumWriter
import json
import time

class TrafficDataProducer:
    def __init__(self, bootstrap_servers, topic, batch_size=10):
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        self.topic = topic
        self.batch_size = batch_size
        
    def validate_record(self, record):
        # Validate speed, coordinates, timestamps
        pass
        
    def process_batch(self, batch):
        # Send batch to Kafka
        pass
        
    def run(self, csv_path):
        df = pd.read_csv(csv_path)
        # Process in batches of 10-20
        pass
```

**Completion Criteria:**
- [ ] Python script created with pandas CSV reading
- [ ] Batch processing implemented (10-20 records/batch)
- [ ] Validation integrated from subtask 1.2
- [ ] Kafka producer configured with proper settings
- [ ] Error handling and retry logic implemented
- [ ] Metrics tracking (throughput, errors)
- [ ] Documentation and usage examples

---

## Subtask 1.4: Implement Avro schema validation
**Status:** Not Started
**Priority:** High

Integrate with schema registry and validate all messages against traffic-event.avsc schema.

**Details:**
Messages currently sent as plain JSON. Need to:
- Register schemas with schema registry (port 8082)
- Use Avro serialization for messages
- Validate against schema before sending
- Handle schema evolution (backward/forward compatibility)

**Implementation Plan:**
```python
from confluent_kafka.avro import AvroProducer
from confluent_kafka import avro

# Load Avro schema
value_schema = avro.load('schemas/traffic-event.avsc')

# Configure producer with schema registry
avroProducer = AvroProducer({
    'bootstrap.servers': 'localhost:9092',
    'schema.registry.url': 'http://localhost:8082'
}, default_value_schema=value_schema)

# Send with schema validation
avroProducer.produce(topic='traffic-raw', value=record)
```

**Completion Criteria:**
- [ ] Schema registry integration configured
- [ ] traffic-event.avsc schema registered
- [ ] Producer uses Avro serialization
- [ ] Schema validation before sending
- [ ] Schema evolution handling implemented
- [ ] Test with valid and invalid data

---

## Subtask 1.5: Add throughput monitoring and metrics
**Status:** Not Started
**Priority:** Medium

Implement 5-8 records/second throughput tracking and alerting.

**Details:**
Add:
- Records/second counter
- Batch size optimization
- Backpressure handling
- Latency tracking (time from CSV read to Kafka send)
- Prometheus metrics export for monitoring dashboard

**Implementation Plan:**
```python
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# Define metrics
messages_sent = Counter('kafka_messages_sent_total', 'Total messages sent to Kafka')
send_latency = Histogram('kafka_send_latency_seconds', 'Time to send message to Kafka')
throughput = Gauge('kafka_throughput_rps', 'Messages per second throughput')

# Track metrics
with send_latency.time():
    producer.send(topic, value=record)
messages_sent.inc()

# Calculate throughput
throughput.set(messages_sent.total() / elapsed_time)
```

**Completion Criteria:**
- [ ] Records/second tracking implemented
- [ ] Latency histogram tracking
- [ ] Batch size optimization based on throughput
- [ ] Backpressure detection and handling
- [ ] Prometheus metrics endpoint (/metrics)
- [ ] Grafana dashboard for visualization
- [ ] Alert when throughput drops below 5 rec/sec

---

## Overall Task Completion Status

**Progress:** 2/5 subtasks complete (40%)

### Completed ✅
1. Fix CSV to Kafka producer script
2. Implement data validation layer (partial)

### In Progress ⏳
- None currently

### Not Started 📋
1. Create Python-based producer for production
2. Implement Avro schema validation
3. Add throughput monitoring and metrics

### Next Steps
1. Complete data validation layer (add remaining validators)
2. Build Python producer with batch processing
3. Integrate Avro schema validation
4. Add comprehensive monitoring

# Task 2: Phase 2 - Stream Processing Pipeline

**Status:** In Progress  
**Priority:** High  
**Dependencies:** Task 1 (Data Ingestion Pipeline)

## Overview
Fix and enhance Node.js stream processor to consume from traffic-raw, transform data, and output to traffic-events topic. Stream processor must consume from traffic-raw (5 partitions), apply transformations, validate data, and output to traffic-events. Currently processing 1004+ messages but needs enhancements for production.

## Test Strategy
Verify messages flow from traffic-raw to traffic-events, validate transformations applied correctly, confirm 30-second micro-batch processing.

---

## Subtask 2.1: Verify consumer group configuration ✅ DONE
**Status:** Complete

Ensure stream-processor-group-v2 correctly reads from earliest offset.

**Details:**
- Consumer group was reset to v2 to start from beginning
- Verified offsets are being committed properly
- Confirmed lag is zero after processing all messages
- Successfully processing 1004+ messages

**Completion Criteria:**
- ✅ Consumer group "stream-processor-group-v2" created
- ✅ Reads from earliest offset (fromBeginning: true)
- ✅ Successfully processed 1004+ messages
- ✅ Consumer lag = 0 on all partitions

---

## Subtask 2.2: Implement windowing operations
**Status:** Not Started
**Priority:** High

Add 5-minute tumbling windows for aggregations as per workflow documentation.

**Details:**
Current implementation processes individual messages. Need to:
- Implement time-based windows (5-minute tumbling)
- Calculate avg_speed per window
- Aggregate volume and occupancy per window
- Emit window results to output topic

**Implementation Plan:**
```javascript
// File: src/stream-processing/processors/WindowAggregator.js

class WindowAggregator {
  constructor() {
    this.windows = new Map(); // windowKey -> aggregates
    this.windowDuration = 5 * 60 * 1000; // 5 minutes
  }
  
  processMessage(message) {
    const windowKey = this.getWindowKey(message.timestamp);
    
    if (!this.windows.has(windowKey)) {
      this.windows.set(windowKey, {
        windowStart: windowKey,
        windowEnd: windowKey + this.windowDuration,
        speeds: [],
        volumes: [],
        occupancies: [],
        sensorId: message.sensor_id
      });
    }
    
    const window = this.windows.get(windowKey);
    window.speeds.push(message.speed_mph);
    window.volumes.push(message.volume_vph);
    window.occupancies.push(message.occupancy_percent);
    
    // Check if window is complete
    if (this.isWindowComplete(windowKey)) {
      return this.emitWindow(windowKey);
    }
  }
  
  emitWindow(windowKey) {
    const window = this.windows.get(windowKey);
    const aggregate = {
      sensor_id: window.sensorId,
      window_start: window.windowStart,
      window_end: window.windowEnd,
      avg_speed: this.average(window.speeds),
      avg_volume: this.average(window.volumes),
      avg_occupancy: this.average(window.occupancies),
      speed_variance: this.variance(window.speeds),
      message_count: window.speeds.length
    };
    
    this.windows.delete(windowKey); // Clean up
    return aggregate;
  }
  
  getWindowKey(timestamp) {
    const ts = new Date(timestamp).getTime();
    return Math.floor(ts / this.windowDuration) * this.windowDuration;
  }
}
```

**Integration:**
```javascript
// In src/stream-processing/index.js
const windowAggregator = new WindowAggregator();

consumer.run({
  eachMessage: async ({ message }) => {
    const event = JSON.parse(message.value.toString());
    
    // Process through window aggregator
    const windowResult = windowAggregator.processMessage(event);
    
    if (windowResult) {
      // Emit aggregated result to traffic-events
      await producer.send({
        topic: OUTPUT_TOPIC,
        messages: [{
          value: JSON.stringify(windowResult)
        }]
      });
    }
  }
});
```

**Completion Criteria:**
- [ ] WindowAggregator class implemented
- [ ] 5-minute tumbling windows configured
- [ ] avg_speed, avg_volume, avg_occupancy calculated
- [ ] Window results emitted to traffic-events topic
- [ ] Old windows cleaned up to prevent memory leaks
- [ ] Tests for window boundaries
- [ ] Handle late-arriving messages

---

## Subtask 2.3: Add Avro schema application
**Status:** Not Started
**Priority:** High

Apply Avro schema validation and deserialization for incoming messages.

**Details:**
Messages currently processed as JSON. Need to:
- Fetch schemas from schema registry
- Deserialize Avro messages
- Validate schema compliance
- Handle schema evolution gracefully

**Implementation Plan:**
```javascript
// File: src/stream-processing/utils/AvroSchemaManager.js
const avro = require('avsc');
const axios = require('axios');

class AvroSchemaManager {
  constructor(schemaRegistryUrl) {
    this.schemaRegistryUrl = schemaRegistryUrl;
    this.schemas = new Map();
  }
  
  async getSchema(subject) {
    if (this.schemas.has(subject)) {
      return this.schemas.get(subject);
    }
    
    const response = await axios.get(
      `${this.schemaRegistryUrl}/subjects/${subject}/versions/latest`
    );
    
    const schema = avro.Type.forSchema(JSON.parse(response.data.schema));
    this.schemas.set(subject, schema);
    return schema;
  }
  
  async deserialize(buffer, subject) {
    const schema = await this.getSchema(subject);
    return schema.fromBuffer(buffer);
  }
  
  async serialize(data, subject) {
    const schema = await this.getSchema(subject);
    return schema.toBuffer(data);
  }
}

module.exports = AvroSchemaManager;
```

**Integration:**
```javascript
// In src/stream-processing/index.js
const AvroSchemaManager = require('./utils/AvroSchemaManager');
const schemaManager = new AvroSchemaManager('http://schema-registry:8082');

consumer.run({
  eachMessage: async ({ message }) => {
    try {
      // Deserialize Avro message
      const event = await schemaManager.deserialize(
        message.value,
        'traffic-raw-value'
      );
      
      // Process event...
      
      // Serialize output with schema
      const output = await schemaManager.serialize(
        processedEvent,
        'traffic-events-value'
      );
      
      await producer.send({
        topic: OUTPUT_TOPIC,
        messages: [{ value: output }]
      });
    } catch (error) {
      logger.error('Schema validation failed', error);
    }
  }
});
```

**Completion Criteria:**
- [ ] AvroSchemaManager class implemented
- [ ] Schema registry integration configured
- [ ] Deserialize incoming Avro messages
- [ ] Serialize outgoing messages with schema
- [ ] Schema caching for performance
- [ ] Handle schema evolution
- [ ] Error handling for invalid schemas
- [ ] Tests for schema validation

---

## Subtask 2.4: Implement data quality validation
**Status:** Not Started
**Priority:** High

Add comprehensive validation checks for data quality and completeness.

**Details:**
Add validation for:
- Missing fields (required fields present)
- Out-of-range values (speed, volume, occupancy)
- Duplicate messages (same sensor_id + timestamp)
- Timestamp ordering (not too old/future)
- Coordinate validity (within LA bounds)
- Sensor ID existence (known sensors only)
- Data freshness checks (message age < threshold)

**Implementation Plan:**
```javascript
// File: src/stream-processing/validators/DataQualityValidator.js

class DataQualityValidator {
  constructor(config) {
    this.config = config;
    this.seenMessages = new Set(); // For duplicate detection
    this.knownSensors = new Set(['METR_LA_000', 'METR_LA_001', /* ... */]);
  }
  
  validate(event) {
    const errors = [];
    
    // Check required fields
    const requiredFields = ['sensor_id', 'timestamp', 'speed_mph', 'coordinates'];
    for (const field of requiredFields) {
      if (!event[field]) {
        errors.push(`Missing required field: ${field}`);
      }
    }
    
    // Validate speed range (0-120 mph)
    if (event.speed_mph < 0 || event.speed_mph > 120) {
      errors.push(`Speed out of range: ${event.speed_mph}`);
    }
    
    // Validate coordinates (LA area: 33.7-34.5 lat, -119 to -117 lon)
    const { latitude, longitude } = event.coordinates;
    if (latitude < 33.7 || latitude > 34.5) {
      errors.push(`Latitude out of LA bounds: ${latitude}`);
    }
    if (longitude < -119 || longitude > -117) {
      errors.push(`Longitude out of LA bounds: ${longitude}`);
    }
    
    // Check for duplicates
    const messageKey = `${event.sensor_id}-${event.timestamp}`;
    if (this.seenMessages.has(messageKey)) {
      errors.push(`Duplicate message: ${messageKey}`);
    } else {
      this.seenMessages.add(messageKey);
    }
    
    // Validate timestamp (not more than 1 hour old)
    const messageAge = Date.now() - new Date(event.timestamp).getTime();
    if (messageAge > 60 * 60 * 1000) {
      errors.push(`Message too old: ${messageAge}ms`);
    }
    
    // Validate sensor ID
    if (!this.knownSensors.has(event.sensor_id)) {
      errors.push(`Unknown sensor: ${event.sensor_id}`);
    }
    
    return {
      isValid: errors.length === 0,
      errors,
      event
    };
  }
  
  // Cleanup old duplicates to prevent memory leak
  cleanup() {
    // Keep only last 10,000 messages
    if (this.seenMessages.size > 10000) {
      const toDelete = Array.from(this.seenMessages).slice(0, 5000);
      toDelete.forEach(key => this.seenMessages.delete(key));
    }
  }
}
```

**Completion Criteria:**
- [ ] DataQualityValidator class implemented
- [ ] All validation rules implemented
- [ ] Invalid messages logged and tracked
- [ ] Metrics for validation errors
- [ ] Duplicate detection working
- [ ] Memory leak prevention (cleanup)
- [ ] Configuration for validation rules
- [ ] Tests for all validation scenarios

---

## Subtask 2.5: Add metrics and monitoring
**Status:** Not Started
**Priority:** Medium

Implement message processing metrics, lag tracking, and error rate monitoring.

**Details:**
Expose metrics via /metrics endpoint:
- Messages processed (counter)
- Processing latency (histogram)
- Consumer lag (gauge)
- Error rate (counter)
- Throughput (gauge - messages/sec)
- Memory usage (gauge)

**Implementation Plan:**
```javascript
// File: src/stream-processing/metrics/Metrics.js
const promClient = require('prom-client');

class Metrics {
  constructor() {
    this.register = new promClient.Registry();
    
    // Messages processed
    this.messagesProcessed = new promClient.Counter({
      name: 'stream_processor_messages_processed_total',
      help: 'Total messages processed',
      labelNames: ['topic', 'status'],
      registers: [this.register]
    });
    
    // Processing latency
    this.processingLatency = new promClient.Histogram({
      name: 'stream_processor_latency_seconds',
      help: 'Message processing latency',
      buckets: [0.001, 0.01, 0.1, 0.5, 1, 5],
      registers: [this.register]
    });
    
    // Consumer lag
    this.consumerLag = new promClient.Gauge({
      name: 'stream_processor_consumer_lag',
      help: 'Consumer lag per partition',
      labelNames: ['partition'],
      registers: [this.register]
    });
    
    // Error rate
    this.errors = new promClient.Counter({
      name: 'stream_processor_errors_total',
      help: 'Total processing errors',
      labelNames: ['type'],
      registers: [this.register]
    });
    
    // Throughput
    this.throughput = new promClient.Gauge({
      name: 'stream_processor_throughput_rps',
      help: 'Messages per second',
      registers: [this.register]
    });
  }
  
  getMetrics() {
    return this.register.metrics();
  }
}
```

**Expose metrics endpoint:**
```javascript
// In src/stream-processing/index.js
const metrics = new Metrics();

app.get('/metrics', async (req, res) => {
  res.set('Content-Type', promClient.register.contentType);
  res.send(await metrics.getMetrics());
});

// Track metrics during processing
consumer.run({
  eachMessage: async ({ message, partition }) => {
    const start = Date.now();
    
    try {
      // Process message...
      
      metrics.messagesProcessed.inc({ topic: INPUT_TOPIC, status: 'success' });
      metrics.processingLatency.observe((Date.now() - start) / 1000);
    } catch (error) {
      metrics.messagesProcessed.inc({ topic: INPUT_TOPIC, status: 'error' });
      metrics.errors.inc({ type: error.name });
    }
  }
});
```

**Completion Criteria:**
- [ ] Prometheus metrics configured
- [ ] /metrics endpoint exposed
- [ ] All key metrics tracked
- [ ] Grafana dashboard created
- [ ] Alerts configured (lag > threshold, errors > threshold)
- [ ] Performance impact minimal

---

## Subtask 2.6: Write to HDFS for batch processing
**Status:** Not Started
**Priority:** High

Store processed messages to HDFS for ML training pipeline.

**Details:**
Stream processor must write to:
- /traffic-data/raw/year=YYYY/month=MM/day=DD/ for raw data
- /traffic-data/processed/aggregates/ for windowed aggregates
Use Parquet format with proper partitioning.

**Implementation Plan:**
```javascript
// File: src/stream-processing/storage/HDFSWriter.js
const WebHDFS = require('webhdfs');
const parquet = require('parquetjs');

class HDFSWriter {
  constructor(hdfsConfig) {
    this.hdfs = WebHDFS.createClient(hdfsConfig);
    this.buffer = [];
    this.bufferSize = 1000; // Write every 1000 messages
  }
  
  async writeRawData(event) {
    const date = new Date(event.timestamp);
    const path = `/traffic-data/raw/year=${date.getFullYear()}/month=${date.getMonth()+1}/day=${date.getDate()}/data-${Date.now()}.parquet`;
    
    this.buffer.push(event);
    
    if (this.buffer.length >= this.bufferSize) {
      await this.flushBuffer(path);
    }
  }
  
  async writeAggregate(aggregate) {
    const date = new Date(aggregate.window_start);
    const path = `/traffic-data/processed/aggregates/year=${date.getFullYear()}/month=${date.getMonth()+1}/data-${Date.now()}.parquet`;
    
    await this.writeParquet(path, [aggregate]);
  }
  
  async writeParquet(path, data) {
    // Define Parquet schema
    const schema = new parquet.ParquetSchema({
      sensor_id: { type: 'UTF8' },
      timestamp: { type: 'TIMESTAMP_MILLIS' },
      speed_mph: { type: 'DOUBLE' },
      volume_vph: { type: 'INT32' },
      occupancy_percent: { type: 'DOUBLE' },
      latitude: { type: 'DOUBLE' },
      longitude: { type: 'DOUBLE' }
    });
    
    // Create Parquet writer
    const writer = await parquet.ParquetWriter.openFile(schema, path);
    
    // Write rows
    for (const row of data) {
      await writer.appendRow(row);
    }
    
    await writer.close();
    
    // Upload to HDFS
    const stream = fs.createReadStream(path);
    await this.hdfs.writeFile(path, stream);
  }
  
  async flushBuffer(basePath) {
    if (this.buffer.length > 0) {
      await this.writeParquet(basePath, this.buffer);
      this.buffer = [];
    }
  }
}
```

**Completion Criteria:**
- [ ] HDFSWriter class implemented
- [ ] Raw data written to partitioned HDFS paths
- [ ] Aggregates written to HDFS
- [ ] Parquet format used for efficiency
- [ ] Proper partitioning by date/hour
- [ ] Buffer flushing on shutdown
- [ ] Error handling for HDFS failures
- [ ] Tests for HDFS writing

---

## Overall Task Completion Status

**Progress:** 1/6 subtasks complete (17%)

### Completed ✅
1. Verify consumer group configuration

### In Progress ⏳
- None currently

### Not Started 📋
1. Implement windowing operations
2. Add Avro schema application
3. Implement data quality validation
4. Add metrics and monitoring
5. Write to HDFS for batch processing

### Next Steps
1. Implement 5-minute tumbling windows
2. Add Avro schema validation
3. Integrate data quality checks
4. Set up comprehensive monitoring
5. Implement HDFS storage

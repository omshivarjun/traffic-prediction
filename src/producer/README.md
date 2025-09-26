# Traffic Data Producer Service - Task 8

A Python service that streams METR-LA traffic data to Kafka topics with configurable replay speed and comprehensive monitoring.

## Features

- **Data Streaming**: Reads METR-LA CSV data and streams to Kafka topics
- **Replay Speed Control**: Configurable speed for realistic time simulation
- **Batch Processing**: Optimized batch sending for high throughput
- **Comprehensive Monitoring**: Built-in metrics tracking and HTTP health endpoints
- **Error Handling**: Robust error handling with retry mechanisms
- **Configuration Management**: Flexible configuration via INI files and CLI arguments

## Quick Start

### Prerequisites

1. **Python 3.8+** with pip
2. **Kafka cluster** running (default: localhost:9092)
3. **Traffic data files** in data/raw/ directory

### Installation

1. Install dependencies:
```bash
cd src/producer
pip install -r requirements.txt
```

2. Create configuration file:
```bash
python traffic_producer.py --create-config
```

3. Run the producer:
```bash
python traffic_producer.py
```

## Configuration

### Configuration File (producer_config.ini)

```ini
[producer]
# Kafka Configuration
kafka_bootstrap_servers = localhost:9092
topic_name = traffic-raw

# Data Source Configuration
data_file = data/raw/metr_la_sample_data.csv
metadata_file = data/raw/metr_la_sensor_metadata.csv

# Streaming Configuration
replay_speed = 1.0      # 1.0 = real-time, 2.0 = 2x speed
batch_size = 100        # Messages per batch
max_records =           # Maximum records to send (empty = unlimited)
loop_data = false       # Loop dataset when reaching end

# Kafka Producer Configuration
compression_type = snappy
acks = 1               # 0=none, 1=leader, all=all replicas
retries = 3
max_in_flight = 5
linger_ms = 100
buffer_memory = 33554432

# Logging Configuration
log_level = INFO
log_file = logs/traffic_producer.log

# Monitoring Configuration
health_check_port = 8080
metrics_interval = 30
```

### Command Line Arguments

```bash
python traffic_producer.py [OPTIONS]

Options:
  -c, --config PATH          Configuration file path (default: producer_config.ini)
  --create-config           Create default configuration file
  -t, --topic TOPIC         Kafka topic name (overrides config)
  -s, --speed FLOAT         Replay speed multiplier (overrides config)
  -m, --max-records INT     Maximum records to send (overrides config)
  -l, --log-level LEVEL     Log level: DEBUG, INFO, WARNING, ERROR
```

## Data Format

### Input Data (METR-LA CSV)
- **File**: data/raw/metr_la_sample_data.csv
- **Format**: timestamp, sensor_id, speed_mph, volume_vehicles_per_hour, latitude, longitude, road_type, road_name, direction

### Output Data (Kafka JSON)
Messages sent to the `traffic-raw` topic follow this schema:

```json
{
  "event_id": "EVT_717447_1685577600000_123",
  "segment_id": "SEG_717447_US_101_N",
  "timestamp": 1685577600000,
  "coordinates": {
    "latitude": 34.0522,
    "longitude": -118.2437
  },
  "speed_kmh": 96.56,
  "volume_vph": 1200,
  "occupancy_percent": 15.5,
  "source": "SENSOR",
  "quality_score": 1.0,
  "metadata": {
    "sensor_id": "717447",
    "road_type": "Highway",
    "road_name": "US 101 N",
    "direction": "N",
    "lanes": "4",
    "original_timestamp": "2023-06-01 00:00:00"
  }
}
```

## Monitoring

### Health Check Endpoints

The producer provides HTTP endpoints for monitoring:

- **Health Check**: `http://localhost:8080/health`
  - Returns service status and connectivity information
  
- **Metrics**: `http://localhost:8080/metrics`
  - Returns real-time performance metrics

### Example Health Response

```json
{
  "status": "healthy",
  "producer_initialized": true,
  "sensors_loaded": 207,
  "kafka_connected": true,
  "timestamp": 1685577600000
}
```

### Example Metrics Response

```json
{
  "messages_sent": 15000,
  "messages_failed": 5,
  "total_messages": 15005,
  "bytes_sent": 2500000,
  "runtime_seconds": 300.5,
  "avg_throughput": 49.9,
  "current_throughput": 52.3,
  "success_rate": 0.9997,
  "failure_rate": 0.0003
}
```

### Console Metrics

The producer logs metrics periodically:

```
2023-06-10 14:30:00 - traffic_producer - INFO - Metrics - Sent: 15000, Failed: 5, Throughput: 52.30 msg/s, Success Rate: 99.97%, Runtime: 300.5s
```

## Data Processing Pipeline

1. **Load Sensor Metadata**: Reads sensor metadata from CSV file
2. **CSV Data Reading**: Sequentially reads traffic data with timestamp parsing
3. **Data Transformation**: Converts METR-LA format to JSON schema format
4. **Timing Simulation**: Implements realistic replay timing based on original timestamps
5. **Batch Processing**: Groups messages into configurable batch sizes
6. **Kafka Publishing**: Sends batches to Kafka with delivery confirmation
7. **Metrics Tracking**: Records success/failure rates and throughput

## Performance Tuning

### Throughput Optimization

- **Batch Size**: Increase `batch_size` for higher throughput (default: 100)
- **Compression**: Use `snappy` compression for best performance
- **Buffer Memory**: Increase `buffer_memory` for high-volume scenarios
- **Linger Time**: Adjust `linger_ms` to balance latency vs throughput

### Reliability Configuration

- **Acknowledgments**: Set `acks=all` for maximum durability
- **Retries**: Increase `retries` for unstable network conditions
- **In-Flight Requests**: Adjust `max_in_flight` based on ordering requirements

## Error Handling

The producer implements comprehensive error handling:

- **Connection Failures**: Automatic reconnection with backoff
- **Delivery Failures**: Retry mechanism with failure tracking
- **Data Quality Issues**: Skips invalid records with logging
- **Resource Exhaustion**: Graceful degradation and recovery

## Integration with Stream Processing

This producer creates events that are consumed by the stream processing pipeline:

1. **Traffic Events** → `traffic-raw` topic
2. **Stream Processors** → Process events into aggregates
3. **Downstream Topics** → `processed-traffic-aggregates`, `traffic-predictions`

## Development and Testing

### Running in Development Mode

```bash
# Test with limited records
python traffic_producer.py --max-records 1000 --log-level DEBUG

# Fast replay for testing
python traffic_producer.py --speed 10.0

# Continuous loop mode
python traffic_producer.py --config test_config.ini
```

### Monitoring During Development

```bash
# Check health
curl http://localhost:8080/health

# Get metrics
curl http://localhost:8080/metrics

# Follow logs
tail -f logs/traffic_producer.log
```

## Troubleshooting

### Common Issues

1. **Kafka Connection Failed**
   - Verify Kafka is running: `docker ps | grep kafka`
   - Check bootstrap servers configuration
   - Validate network connectivity

2. **Topic Not Found**
   - Topic will be auto-created on first message
   - Manually create topic: `kafka-topics.sh --create --topic traffic-raw`

3. **High Memory Usage**
   - Reduce `buffer_memory` setting
   - Decrease `batch_size`
   - Monitor JVM heap if using Kafka with Java

4. **Slow Performance**
   - Increase `batch_size`
   - Adjust `linger_ms`
   - Check network latency to Kafka

### Debug Mode

Enable debug logging for detailed information:

```bash
python traffic_producer.py --log-level DEBUG
```

## Architecture Integration

This producer is part of the larger traffic prediction system:

```
METR-LA Data → Traffic Producer → Kafka → Stream Processing → Aggregates → Predictions
```

The producer ensures reliable, high-performance data ingestion with monitoring and observability for the entire traffic prediction pipeline.
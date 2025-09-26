# Kafka Setup and Configuration Guide

## Overview

This document provides information about the Kafka setup for the Traffic Prediction System. Kafka is used as the central messaging backbone for streaming traffic data, processing events, and delivering predictions.

## Architecture

The Kafka setup consists of the following components:

- **Zookeeper**: Manages the Kafka cluster state
- **Kafka Broker**: Handles message storage and delivery
- **Schema Registry**: Enforces schema validation for messages
- **Kafka Connect**: Integrates Kafka with external systems (HDFS)
- **Kafka UI**: Web interface for monitoring and management

## Docker Compose Configuration

All Kafka services are configured in the `docker-compose.yml` file. The services are designed to work with the Hadoop ecosystem components also defined in the same file.

## Kafka Topics

The following Kafka topics are configured for the Traffic Prediction System:

### Raw Traffic Data Topics

| Topic Name | Partitions | Replication Factor | Retention | Description |
|------------|------------|-------------------|-----------|-------------|
| raw-traffic-events | 3 | 1 | 7 days | Raw traffic flow events from sensors |
| raw-traffic-incidents | 3 | 1 | 7 days | Traffic incidents (accidents, closures, etc.) |
| raw-traffic-sensors | 3 | 1 | 7 days | Sensor metadata and status updates |
| raw-weather-data | 3 | 1 | 7 days | Weather conditions affecting traffic |

### Processed Traffic Data Topics

| Topic Name | Partitions | Replication Factor | Retention | Description |
|------------|------------|-------------------|-----------|-------------|
| processed-traffic-aggregates | 3 | 1 | 3 days | Aggregated traffic metrics by time window |
| processed-traffic-segments | 3 | 1 | 3 days | Processed data for road segments |
| processed-congestion-levels | 3 | 1 | 3 days | Calculated congestion levels |

### Prediction and Alert Topics

| Topic Name | Partitions | Replication Factor | Retention | Description |
|------------|------------|-------------------|-----------|-------------|
| traffic-predictions | 3 | 1 | 1 day | Traffic predictions from ML models |
| traffic-alerts | 3 | 1 | 1 day | Alerts for unusual traffic conditions |

## Avro Schemas

All messages in the Kafka topics are validated against Avro schemas stored in the Schema Registry. The schemas are defined in the `schemas/` directory:

- `traffic-event.avsc`: Schema for raw traffic events
- `traffic-incident.avsc`: Schema for traffic incidents
- `processed-traffic-aggregate.avsc`: Schema for aggregated traffic data
- `traffic-prediction.avsc`: Schema for traffic predictions

## Kafka Connect Configuration

Kafka Connect is configured with an HDFS sink connector that writes data from Kafka topics to HDFS. The connector configuration is stored in `connectors/hdfs-sink-connector.json`.

Key features of the HDFS connector:

- Writes data in Avro format
- Partitions data by time (year/month/day/hour)
- Integrates with Hive metastore for SQL querying
- Handles schema evolution with backward compatibility

## Scripts

The following scripts are provided for managing the Kafka setup:

- `scripts/start-kafka-services.ps1`: Starts all Kafka-related services
- `scripts/create-kafka-topics.ps1`: Creates the required Kafka topics
- `scripts/deploy-hdfs-connector.ps1`: Deploys the HDFS sink connector
- `scripts/verify-kafka-setup.ps1`: Verifies the Kafka setup

## Getting Started

1. Start the Kafka services:
   ```powershell
   .\scripts\start-kafka-services.ps1
   ```

2. Verify the setup:
   ```powershell
   .\scripts\verify-kafka-setup.ps1
   ```

3. Access the Kafka UI:
   - Open http://localhost:8080 in your browser

## Troubleshooting

### Common Issues

1. **Kafka broker not starting**
   - Check if Zookeeper is running
   - Verify port 9092 is not in use by another application
   - Check Docker logs: `docker logs kafka-broker`

2. **Schema Registry errors**
   - Ensure Kafka broker is running before Schema Registry
   - Check Schema Registry logs: `docker logs schema-registry`

3. **HDFS connector issues**
   - Verify HDFS namenode is running
   - Check Kafka Connect logs: `docker logs kafka-connect`
   - Verify Hive metastore is accessible

## Maintenance

### Adding New Topics

To add new topics, modify the `scripts/create-kafka-topics.ps1` script and add the new topic configuration.

### Updating Schemas

When updating schemas, ensure backward compatibility to avoid breaking existing consumers. Test schema changes with the Schema Registry's compatibility API before deploying.

### Monitoring

Use the Kafka UI (http://localhost:8080) to monitor:
- Topic message rates
- Consumer group lag
- Broker health
- Schema Registry status
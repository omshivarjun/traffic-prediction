# Task 7.2: Kafka Topic Configuration Documentation
# This file documents all topic-level configurations for the Traffic Prediction System

## Core Topic Configuration Specifications

### Traffic-Raw Topic Configuration
Topic Name: traffic-raw
Partitions: 5
Replication Factor: 1
Retention: 168 hours (7 days)

**Configuration Parameters:**
- compression.type=snappy              # Snappy compression for optimal performance
- cleanup.policy=delete                # Delete old messages after retention period
- segment.ms=86400000                  # Log rolling every 24 hours (86400000 ms)
- retention.ms=604800000               # 7 days retention (168 hours)
- min.insync.replicas=1                # Minimum in-sync replicas for durability
- unclean.leader.election.enable=false # Prevent data loss during leader election
- max.message.bytes=1048576            # 1MB max message size
- segment.bytes=1073741824             # 1GB segment size before rolling

### Traffic-Processed Topic Configuration
Topic Name: traffic-processed
Partitions: 5
Replication Factor: 1
Retention: 168 hours (7 days)

**Configuration Parameters:**
- compression.type=snappy              # Snappy compression for optimal performance
- cleanup.policy=delete                # Delete old messages after retention period
- segment.ms=86400000                  # Log rolling every 24 hours
- retention.ms=604800000               # 7 days retention
- min.insync.replicas=1                # Minimum in-sync replicas for durability
- unclean.leader.election.enable=false # Prevent data loss during leader election
- max.message.bytes=2097152            # 2MB max message size (larger for aggregated data)
- segment.bytes=1073741824             # 1GB segment size before rolling

### Traffic-Alerts Topic Configuration  
Topic Name: traffic-alerts
Partitions: 2
Replication Factor: 1
Retention: 168 hours (7 days)

**Configuration Parameters:**
- compression.type=snappy              # Snappy compression for optimal performance
- cleanup.policy=delete                # Delete old messages after retention period
- segment.ms=86400000                  # Log rolling every 24 hours
- retention.ms=604800000               # 7 days retention
- min.insync.replicas=1                # Minimum in-sync replicas for durability
- unclean.leader.election.enable=false # Prevent data loss during leader election
- max.message.bytes=512000             # 512KB max message size (alerts are smaller)
- segment.bytes=536870912              # 512MB segment size (smaller for alert topic)

## Performance Optimization Settings

### Compression Strategy
- **Algorithm**: Snappy compression chosen for optimal balance of speed and compression ratio
- **Benefits**: ~40% space savings with minimal CPU overhead
- **Trade-offs**: Slightly less compression than LZ4 but better for mixed workloads

### Log Rolling Strategy
- **Interval**: 24 hours (segment.ms=86400000)
- **Size-based**: 1GB segments for main topics, 512MB for alerts
- **Benefits**: Balanced between storage efficiency and operational overhead

### Retention Policy
- **Time-based**: 7 days (168 hours) for all core topics
- **Policy**: Delete (cleanup.policy=delete)
- **Rationale**: Sufficient for real-time analytics while managing storage costs

## Topic-Specific Optimizations

### Raw Data Topics
- Higher throughput expected
- Larger message sizes from sensor payloads
- Optimized for write-heavy workloads

### Processed Data Topics  
- Medium throughput with aggregated data
- Structured for downstream consumption
- Balanced read/write optimization

### Alert Topics
- Lower throughput, high priority
- Smaller partition count for faster processing
- Optimized for low-latency delivery

## Monitoring and Metrics

### Key Metrics to Monitor
- Partition distribution and balance
- Consumer lag by consumer group
- Disk usage per topic
- Compression effectiveness
- Message throughput rates

### Alerting Thresholds
- Consumer lag > 10,000 messages
- Disk usage > 80% of allocated space
- Failed message rate > 1%
- Partition leader imbalance > 20%

## Operational Procedures

### Topic Maintenance
1. Monitor segment rolling frequency
2. Verify compression ratios
3. Check partition balance monthly
4. Validate retention policy effectiveness

### Configuration Changes
1. Test configuration changes in staging environment
2. Apply changes during low-traffic periods
3. Monitor impact on performance metrics
4. Document all configuration modifications

## Security Considerations

### Access Control
- Producer access limited to authorized services
- Consumer groups properly configured
- Network-level security via Docker networking

### Data Protection
- No sensitive data in topic names or keys
- Message payloads contain only operational traffic data
- Retention periods comply with data governance policies
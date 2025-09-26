# HDFS Storage Pipeline Documentation - Task 10
**Comprehensive HDFS Storage Implementation with Parquet Format, Batch Processing, and Data Validation**

## Overview

The HDFS Storage Pipeline is a comprehensive big data storage solution designed for the Traffic Prediction System. It provides efficient storage, processing, and validation of large-scale traffic data using Apache Spark, Hadoop HDFS, and Parquet format with advanced data quality monitoring.

## Architecture Components

### 1. Core Storage Pipeline (`src/spark/hdfs_storage.py`)
**Comprehensive HDFS storage orchestration with Parquet format support**

**Key Features:**
- **Parquet Writer**: Columnar storage with Snappy compression
- **Partitioning**: Date-based partitioning (year/month/day/hour)
- **Schema Evolution**: Automatic schema handling and validation
- **Data Quality**: Integrated validation and quality scoring
- **Batch Processing**: Daily aggregation job execution
- **PostgreSQL Integration**: Storing aggregated results

**Usage:**
```python
from hdfs_storage import HDFSStoragePipeline, HDFSStorageConfig

# Initialize with configuration
config = HDFSStorageConfig.from_file("config/hdfs_pipeline_config.json")
pipeline = HDFSStoragePipeline(config)

# Write data to HDFS
result = pipeline.write_parquet_data(df, "processed", enable_validation=True)

# Run daily aggregation
aggregation_result = pipeline.create_daily_aggregation(processing_date)
```

### 2. Directory Management (`src/hdfs/directory_manager.py`)
**HDFS directory management with retention policies and automated cleanup**

**Key Features:**
- **Directory Structure**: Automated creation of hierarchical directories
- **Retention Policies**: Automated cleanup based on configurable retention
- **File Naming**: Standardized naming conventions with timestamps
- **Backup Management**: Automated backup creation and management
- **Health Monitoring**: Directory health checks and statistics

**Usage:**
```python
from directory_manager import HDFSDirectoryManager, HDFSDirectoryConfig

# Initialize directory manager
config = HDFSDirectoryConfig(retention_days=30)
manager = HDFSDirectoryManager(config)

# Create directory structure
manager.create_directory_structure()

# Cleanup old files
cleanup_results = manager.cleanup_old_files("/hdfs/path", retention_days=30)

# Generate file names
filename = manager.generate_file_name("processed", datetime.now(), "seg_001")
```

### 3. Batch Processing (`src/batch/daily_aggregation_job.py`)
**Daily batch processing jobs with PostgreSQL integration**

**Key Features:**
- **Job Orchestration**: Automated daily aggregation workflows
- **PostgreSQL Storage**: Structured storage of aggregated results
- **Performance Metrics**: Comprehensive job performance tracking
- **Error Handling**: Robust error handling and recovery
- **Job History**: Complete job execution history and monitoring

**Usage:**
```python
from daily_aggregation_job import BatchJobOrchestrator, BatchJobConfig

# Initialize batch job orchestrator
batch_config = BatchJobConfig(job_name="daily_traffic_aggregation")
storage_config = HDFSStorageConfig.from_file("config/hdfs_pipeline_config.json")
orchestrator = BatchJobOrchestrator(batch_config, storage_config)

# Create PostgreSQL tables
orchestrator.create_aggregation_tables()

# Run daily aggregation job
result = orchestrator.run_daily_aggregation_job(processing_date)
```

### 4. Data Validation (`src/validation/data_validator.py`)
**Comprehensive data quality validation and reporting**

**Key Features:**
- **Validation Rules**: Configurable data quality rules
- **Quality Scoring**: Automated quality score calculation
- **Anomaly Detection**: Statistical anomaly detection
- **HTML Reports**: Interactive quality reports
- **Recommendations**: Automated improvement recommendations

**Usage:**
```python
from data_validator import HDFSDataValidator

# Initialize validator
validator = HDFSDataValidator("config/validation_rules.json")

# Validate HDFS data
report = validator.validate_hdfs_data("hdfs://localhost:9000/traffic/processed")

# Generate reports
json_path = validator.save_report(report)
html_path = validator.generate_html_report(report)
```

## Configuration

### Master Configuration (`config/hdfs_pipeline_config.json`)
**Centralized configuration for all pipeline components**

```json
{
  "hdfs_storage": {
    "hdfs_base_path": "hdfs://localhost:9000/traffic",
    "raw_data_path": "hdfs://localhost:9000/traffic/raw",
    "processed_data_path": "hdfs://localhost:9000/traffic/processed",
    "aggregated_data_path": "hdfs://localhost:9000/traffic/aggregated"
  },
  
  "parquet_settings": {
    "compression_codec": "snappy",
    "enable_dictionary": true,
    "enable_bloom_filter": true,
    "block_size": 134217728
  },
  
  "data_retention": {
    "retention_days": 30,
    "cleanup_schedule": "daily",
    "backup_before_cleanup": true
  },
  
  "spark_configuration": {
    "executor_memory": "4g",
    "num_executors": 4,
    "adaptive_enabled": true
  }
}
```

### Validation Rules Configuration
**Customizable data quality validation rules**

```json
{
  "validation_rules": [
    {
      "name": "speed_range_check",
      "description": "Speed values should be between 0 and 200 mph",
      "rule_type": "range",
      "column": "speed",
      "parameters": {"min_value": 0.0, "max_value": 200.0},
      "severity": "ERROR"
    }
  ]
}
```

## Directory Structure

The HDFS Storage Pipeline creates and manages the following directory structure:

```
hdfs://localhost:9000/traffic/
├── raw/                          # Raw streaming data
│   └── year=YYYY/month=MM/day=DD/hour=HH/
├── processed/                    # Processed and validated data
│   └── year=YYYY/month=MM/day=DD/hour=HH/
├── aggregated/                   # Daily aggregated summaries
│   └── year=YYYY/month=MM/day=DD/
├── streaming/                    # Real-time streaming output
│   └── year=YYYY/month=MM/day=DD/hour=HH/
├── validated/                    # Quality-validated data
│   └── year=YYYY/month=MM/day=DD/hour=HH/
├── backup/                       # Backup storage
│   └── backup_YYYYMMDD_HHMMSS/
├── temp/                         # Temporary processing files
├── reports/                      # Quality and processing reports
└── checkpoints/                  # Spark streaming checkpoints
```

## File Naming Conventions

All files follow standardized naming conventions:

- **Pattern**: `traffic_data_{type}_{timestamp}_{segment_id}.parquet.snappy`
- **Example**: `traffic_data_processed_20240115_143000_seg_001.parquet.snappy`
- **Timestamp Format**: `YYYYMMDD_HHMMSS`
- **Compression**: `.parquet.snappy` suffix for all Parquet files

## PowerShell Automation

### Main Pipeline Script (`scripts/run-hdfs-pipeline.ps1`)
**Comprehensive automation for all pipeline operations**

**Available Actions:**
```powershell
# Initialize pipeline
.\scripts\run-hdfs-pipeline.ps1 -Action setup

# Run daily aggregation
.\scripts\run-hdfs-pipeline.ps1 -Action run-daily -Date "2024-01-15"

# Validate data quality
.\scripts\run-hdfs-pipeline.ps1 -Action validate

# Cleanup old files
.\scripts\run-hdfs-pipeline.ps1 -Action cleanup -RetentionDays 7

# Health check
.\scripts\run-hdfs-pipeline.ps1 -Action health-check

# Create backup
.\scripts\run-hdfs-pipeline.ps1 -Action backup

# Run tests
.\scripts\run-hdfs-pipeline.ps1 -Action test
```

## PostgreSQL Integration

### Database Schema

The pipeline creates and manages the following PostgreSQL tables:

#### 1. Daily Traffic Summary
```sql
CREATE TABLE daily_traffic_summary (
    id SERIAL PRIMARY KEY,
    processing_date DATE NOT NULL,
    segment_id VARCHAR(50) NOT NULL,
    total_vehicles INTEGER NOT NULL DEFAULT 0,
    avg_speed FLOAT NOT NULL DEFAULT 0.0,
    max_speed FLOAT NOT NULL DEFAULT 0.0,
    min_speed FLOAT NOT NULL DEFAULT 0.0,
    avg_density FLOAT NOT NULL DEFAULT 0.0,
    incident_count INTEGER NOT NULL DEFAULT 0,
    congestion_hours FLOAT NOT NULL DEFAULT 0.0,
    quality_score FLOAT NOT NULL DEFAULT 0.0,
    data_completeness FLOAT NOT NULL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (processing_date, segment_id)
);
```

#### 2. Hourly Traffic Aggregates
```sql
CREATE TABLE hourly_traffic_aggregates (
    id SERIAL PRIMARY KEY,
    processing_hour TIMESTAMP NOT NULL,
    segment_id VARCHAR(50) NOT NULL,
    vehicle_count INTEGER NOT NULL DEFAULT 0,
    avg_speed FLOAT NOT NULL DEFAULT 0.0,
    speed_variance FLOAT NOT NULL DEFAULT 0.0,
    density FLOAT NOT NULL DEFAULT 0.0,
    flow_rate FLOAT NOT NULL DEFAULT 0.0,
    incident_impact FLOAT NOT NULL DEFAULT 0.0,
    weather_factor FLOAT NOT NULL DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (processing_hour, segment_id)
);
```

#### 3. Data Quality Reports
```sql
CREATE TABLE data_quality_reports (
    id SERIAL PRIMARY KEY,
    report_date DATE NOT NULL,
    report_type VARCHAR(50) NOT NULL,
    total_records INTEGER NOT NULL DEFAULT 0,
    valid_records INTEGER NOT NULL DEFAULT 0,
    duplicate_records INTEGER NOT NULL DEFAULT 0,
    missing_data_records INTEGER NOT NULL DEFAULT 0,
    quality_score FLOAT NOT NULL DEFAULT 0.0,
    issues_found JSONB,
    recommendations JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (report_date, report_type)
);
```

#### 4. Batch Job History
```sql
CREATE TABLE batch_job_history (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(100) NOT NULL UNIQUE,
    job_name VARCHAR(100) NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    status VARCHAR(20) NOT NULL,
    records_processed INTEGER DEFAULT 0,
    records_created INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    error_details TEXT,
    performance_metrics JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Data Quality Framework

### Validation Rules

The pipeline implements comprehensive validation rules:

#### Range Validation
- **Speed**: 0-200 mph
- **Density**: 0-1000 vehicles/mile
- **Flow Rate**: 0-8000 vehicles/hour

#### Completeness Validation
- **Critical Fields**: < 0.1% null values
- **Important Fields**: < 5% null values

#### Pattern Validation
- **Segment IDs**: Alphanumeric pattern `^[A-Z0-9_]{3,20}$`
- **Timestamps**: Valid timestamp format

#### Uniqueness Validation
- **Duplicate Records**: < 1% duplicate rate
- **Primary Keys**: Unique combinations

### Quality Scoring

Quality scores are calculated using weighted metrics:
- **Completeness**: 50% weight
- **Validity**: 25% weight  
- **Uniqueness**: 25% weight

**Score Ranges:**
- **Excellent**: 95-100
- **Good**: 85-94
- **Acceptable**: 70-84
- **Poor**: < 70

## Performance Optimization

### Spark Configuration
```json
{
  "spark_configuration": {
    "executor_memory": "4g",
    "executor_cores": 2,
    "num_executors": 4,
    "adaptive_enabled": true,
    "adaptive_coalesce_partitions": true,
    "sql_adaptive_skew_join": true
  }
}
```

### Parquet Optimization
```json
{
  "parquet_settings": {
    "compression_codec": "snappy",
    "enable_dictionary": true,
    "enable_bloom_filter": true,
    "block_size": 134217728,
    "page_size": 1048576
  }
}
```

### Partitioning Strategy
- **Time-based**: Year, Month, Day, Hour partitions
- **Segment-based**: Optional segment ID partitioning
- **Dynamic Overwrite**: Prevents data loss during updates

## Monitoring and Alerting

### Health Checks
The pipeline provides comprehensive health monitoring:

```powershell
# Run health check
.\scripts\run-hdfs-pipeline.ps1 -Action health-check
```

**Health Check Components:**
- HDFS directory accessibility
- File count and size monitoring
- Recent job success rates
- Data quality trends
- Storage utilization

### Logging
All components provide structured logging:

- **Log Location**: `logs/`
- **Log Format**: `[timestamp] [level] message`
- **Log Levels**: DEBUG, INFO, WARNING, ERROR
- **Log Rotation**: Daily rotation with retention

### Metrics
Performance metrics are tracked:

- **Processing Time**: Job execution duration
- **Throughput**: Records processed per second
- **Data Quality**: Quality score trends
- **Storage Utilization**: HDFS space usage
- **Error Rates**: Job failure rates

## Testing

### Test Suite (`tests/test_hdfs_pipeline.py`)
Comprehensive test coverage including:

#### Unit Tests
- Configuration loading and validation
- File naming and path generation
- Validation rule execution
- Quality score calculation

#### Integration Tests
- End-to-end workflow testing
- Database integration
- HDFS connectivity
- Component interaction

#### Performance Tests
- Partition path generation performance
- File naming performance benchmarks
- Large dataset processing tests

**Run Tests:**
```powershell
.\scripts\run-hdfs-pipeline.ps1 -Action test
```

## Troubleshooting

### Common Issues

#### 1. HDFS Connectivity Issues
```bash
# Check HDFS status
docker exec namenode-alt hdfs dfs -ls /

# Verify container health
docker ps --filter "name=namenode-alt"
```

#### 2. PostgreSQL Connection Issues
```bash
# Test PostgreSQL connection
docker exec postgres-container psql -U traffic_user -d traffic_prediction -c "\dt"
```

#### 3. Spark Memory Issues
```json
{
  "spark_configuration": {
    "executor_memory": "2g",  // Reduce if needed
    "driver_memory": "1g"     // Reduce if needed
  }
}
```

#### 4. Data Quality Issues
- Check validation rules configuration
- Review data quality reports
- Examine source data patterns
- Adjust validation thresholds

### Log Analysis

**Key Log Locations:**
- **Pipeline Logs**: `logs/hdfs_pipeline_YYYYMMDD.log`
- **Validation Logs**: `logs/data_validation.log`
- **Batch Processing**: `logs/batch_processing.log`
- **Directory Management**: `logs/hdfs_directory_manager.log`

**Log Analysis Commands:**
```powershell
# Search for errors
Select-String -Path "logs/*.log" -Pattern "ERROR"

# Check recent activity
Get-Content "logs/hdfs_pipeline_$(Get-Date -Format 'yyyyMMdd').log" -Tail 50
```

## Best Practices

### 1. Data Management
- **Regular Cleanup**: Run cleanup daily with appropriate retention
- **Backup Strategy**: Create backups before major operations
- **Quality Monitoring**: Monitor data quality trends
- **Schema Evolution**: Plan for schema changes

### 2. Performance
- **Partition Pruning**: Use time-based filtering in queries
- **File Size**: Maintain optimal file sizes (128-512MB)
- **Compression**: Use Snappy for balance of speed and size
- **Caching**: Cache frequently accessed data

### 3. Monitoring
- **Regular Health Checks**: Daily health check execution
- **Quality Thresholds**: Set appropriate quality thresholds
- **Alert Configuration**: Configure alerts for critical issues
- **Capacity Planning**: Monitor storage growth trends

### 4. Security
- **Access Control**: Implement proper HDFS permissions
- **Data Encryption**: Consider encryption for sensitive data
- **Audit Logging**: Enable comprehensive audit logging
- **Credential Management**: Secure credential storage

## Integration with Existing Systems

### Task 9 Integration
The HDFS Storage Pipeline integrates seamlessly with Task 9 (Spark Streaming):

- **Input Source**: Reads from Task 9 streaming output
- **Data Format**: Compatible Parquet format
- **Partitioning**: Consistent partitioning scheme
- **Quality Checks**: Validates streaming data quality

### Kafka Integration
- **Data Source**: Processes Kafka streaming data
- **Schema Registry**: Uses Avro schemas from Kafka
- **Offset Management**: Integrates with Kafka offset tracking

### PostgreSQL Analytics
- **Aggregated Data**: Stores processed results for analytics
- **Real-time Queries**: Enables real-time dashboard queries
- **Historical Analysis**: Supports long-term trend analysis

## Conclusion

The HDFS Storage Pipeline provides a comprehensive, production-ready solution for large-scale traffic data storage and processing. With its robust architecture, comprehensive monitoring, and automated operations, it forms the backbone of the Traffic Prediction System's data infrastructure.

**Key Benefits:**
- **Scalability**: Handles large-scale data processing
- **Reliability**: Robust error handling and recovery
- **Quality**: Comprehensive data validation and monitoring
- **Automation**: Fully automated operations and maintenance
- **Integration**: Seamless integration with existing systems

For support and additional documentation, refer to the logs and configuration files in the respective directories.